"""
Multi-region carbon intensity signal provider, forecast model, and green window detector.
"""

import os
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
from .models import Region


class CarbonGridProvider:
    """
    Manages historical and real-time regional carbon intensity signals (gCO2eq/kWh).
    Supports time-series querying, rolling horizon forecasting, and low-carbon window detection.
    """

    def __init__(self, trace_csv_path: Optional[str] = None):
        self.step_minutes = 15.0

        if trace_csv_path and os.path.exists(trace_csv_path):
            self.df_traces = pd.read_csv(trace_csv_path)
        else:
            # Fallback to default generated trace path if present
            default_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "data", "traces", "grid_carbon", "grid_carbon_intensity_multi_region.csv")
            )
            if os.path.exists(default_path):
                self.df_traces = pd.read_csv(default_path)
            else:
                self.df_traces = self._generate_in_memory_default()

        # Cache values as numpy arrays for sub-microsecond lookups
        self.region_columns = {
            Region.DE: "DE",
            Region.SE: "SE",
            Region.US_CA: "US_CA",
            Region.FR: "FR"
        }
        self.arrays = {
            r: self.df_traces[col].to_numpy(dtype=np.float64)
            for r, col in self.region_columns.items()
        }
        self.max_steps = len(self.df_traces)
        self.max_time_min = (self.max_steps - 1) * self.step_minutes

    def _generate_in_memory_default(self) -> pd.DataFrame:
        """In-memory generation fallback if file not found."""
        steps = 672
        de = 380 + 80 * np.sin(np.linspace(0, 14 * np.pi, steps))
        se = 40 + 10 * np.sin(np.linspace(0, 14 * np.pi, steps))
        us_ca = 280 + 120 * np.sin(np.linspace(0, 14 * np.pi, steps))
        fr = 60 + 15 * np.sin(np.linspace(0, 14 * np.pi, steps))
        return pd.DataFrame({"DE": de, "SE": se, "US_CA": us_ca, "FR": fr})

    def _time_to_index(self, time_min: float) -> int:
        idx = int(time_min // self.step_minutes)
        return idx % self.max_steps

    def get_intensity(self, region: Region, time_min: float) -> float:
        """
        Returns real-time carbon intensity in gCO2eq/kWh for the given region and time.
        Uses linear interpolation between discrete 15-minute grid sampling intervals.
        """
        exact_step = time_min / self.step_minutes
        idx_lower = int(np.floor(exact_step)) % self.max_steps
        idx_upper = (idx_lower + 1) % self.max_steps
        frac = exact_step - np.floor(exact_step)

        arr = self.arrays[region]
        val_lower = arr[idx_lower]
        val_upper = arr[idx_upper]
        return float(val_lower + frac * (val_upper - val_lower))

    def get_forecast(self, region: Region, start_time_min: float, horizon_min: float) -> List[Tuple[float, float]]:
        """
        Returns a list of (timestamp_min, forecasted_carbon_intensity) tuples
        over [start_time_min, start_time_min + horizon_min].
        """
        num_points = max(1, int(horizon_min / self.step_minutes))
        points = []
        for i in range(num_points + 1):
            t = start_time_min + i * self.step_minutes
            ci = self.get_intensity(region, t)
            points.append((t, ci))
        return points

    def find_cleanest_region_now(self, time_min: float) -> Tuple[Region, float]:
        """Identifies the region with the lowest instantaneous carbon intensity."""
        intensities = [(r, self.get_intensity(r, time_min)) for r in Region]
        intensities.sort(key=lambda x: x[1])
        return intensities[0]

    def find_optimal_green_window(
        self, region: Region, start_time_min: float, window_duration_min: float, task_duration_min: float
    ) -> Tuple[float, float]:
        """
        Searches within a slack window [start_time, start_time + window_duration]
        to find the start time t* that minimizes the integral of carbon intensity
        over the task's execution duration.
        Returns: (optimal_start_time_min, expected_average_intensity)
        """
        max_delay = max(0.0, window_duration_min)
        if max_delay <= 0.0:
            return start_time_min, self.get_intensity(region, start_time_min)

        candidate_step = self.step_minutes
        num_candidates = max(1, int(max_delay / candidate_step))

        best_start = start_time_min
        best_avg_intensity = float("inf")

        for step in range(num_candidates + 1):
            t_cand = start_time_min + step * candidate_step
            # Sample midpoint or average over task duration
            sample_t1 = t_cand
            sample_t2 = t_cand + task_duration_min * 0.5
            sample_t3 = t_cand + task_duration_min
            avg_cand = (self.get_intensity(region, sample_t1) +
                        self.get_intensity(region, sample_t2) +
                        self.get_intensity(region, sample_t3)) / 3.0

            if avg_cand < best_avg_intensity:
                best_avg_intensity = avg_cand
                best_start = t_cand

        return best_start, best_avg_intensity
