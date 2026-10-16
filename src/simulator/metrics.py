"""
Simulation metrics and telemetry collectors for EcoSched.
"""

from typing import List, Dict, Any
import numpy as np
from pydantic import BaseModel
from ..core.task import WorkloadTask
from ..core.cluster import DistributedCluster


class SimulationSummary(BaseModel):
    scheduler_name: str
    total_tasks: int
    completed_tasks: int
    missed_deadlines: int
    deadline_compliance_pct: float
    total_energy_kwh: float
    total_carbon_kg: float
    average_carbon_intensity_g_per_kwh: float
    average_waiting_time_min: float
    average_turnaround_time_min: float
    average_cpu_utilization_pct: float
    simulation_duration_hours: float
    carbon_savings_pct: float = 0.0 # Compared to default baseline


class MetricsCollector:
    """
    Collects fine-grained temporal traces and summary statistics for benchmarking.
    """

    def __init__(self, scheduler_name: str):
        self.scheduler_name = scheduler_name
        self.time_series_records: List[Dict[str, Any]] = []

    def record_step(
        self,
        time_min: float,
        cluster: DistributedCluster,
        step_energy_kwh: float,
        step_carbon_g: float,
        running_tasks_count: int,
        queued_tasks_count: int
    ):
        total_active_cpu = sum(n.allocated_cpu for n in cluster.nodes.values())
        total_cluster_cpu = sum(n.total_cpu for n in cluster.nodes.values())
        cpu_util = (total_active_cpu / total_cluster_cpu * 100.0) if total_cluster_cpu > 0 else 0.0

        self.time_series_records.append({
            "time_min": round(time_min, 1),
            "step_energy_kwh": step_energy_kwh,
            "step_carbon_g": step_carbon_g,
            "running_tasks": running_tasks_count,
            "queued_tasks": queued_tasks_count,
            "cpu_utilization_pct": round(cpu_util, 2)
        })

    def generate_summary(self, all_tasks: List[WorkloadTask], cluster: DistributedCluster, sim_time_min: float) -> SimulationSummary:
        completed = [t for t in all_tasks if t.completion_time is not None]
        missed = [t for t in completed if t.deadline_missed]

        total_tasks_count = len(all_tasks)
        completed_count = len(completed)
        missed_count = len(missed)

        compliance_pct = ((completed_count - missed_count) / completed_count * 100.0) if completed_count > 0 else 0.0

        total_energy_kwh = sum(n.cumulative_energy_kwh for n in cluster.nodes.values())
        total_carbon_g = sum(n.cumulative_carbon_gco2 for n in cluster.nodes.values())
        total_carbon_kg = total_carbon_g / 1000.0

        avg_ci = (total_carbon_g / total_energy_kwh) if total_energy_kwh > 0 else 0.0

        wait_times = [t.waiting_time for t in completed]
        turnaround_times = [t.turnaround_time for t in completed]

        avg_wait = float(np.mean(wait_times)) if wait_times else 0.0
        avg_turnaround = float(np.mean(turnaround_times)) if turnaround_times else 0.0

        cpu_utils = [r["cpu_utilization_pct"] for r in self.time_series_records]
        avg_cpu_util = float(np.mean(cpu_utils)) if cpu_utils else 0.0

        return SimulationSummary(
            scheduler_name=self.scheduler_name,
            total_tasks=total_tasks_count,
            completed_tasks=completed_count,
            missed_deadlines=missed_count,
            deadline_compliance_pct=round(compliance_pct, 2),
            total_energy_kwh=round(total_energy_kwh, 2),
            total_carbon_kg=round(total_carbon_kg, 2),
            average_carbon_intensity_g_per_kwh=round(avg_ci, 2),
            average_waiting_time_min=round(avg_wait, 1),
            average_turnaround_time_min=round(avg_turnaround, 1),
            average_cpu_utilization_pct=round(avg_cpu_util, 2),
            simulation_duration_hours=round(sim_time_min / 60.0, 1)
        )
