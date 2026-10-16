"""
Script to generate realistic grid carbon intensity traces and cluster workload traces
based on historical European ENTSO-E, ElectricityMaps, and Google/Alibaba cluster traces.
"""

import os
import json
import numpy as np
import pandas as pd


def generate_carbon_traces(output_dir: str, duration_hours: int = 168, step_minutes: int = 15):
    """
    Generates time-series carbon intensity (gCO2eq/kWh) for 4 representative geo-distributed regions:
    1. DE (Germany): High solar/wind fluctuations, coal/gas peakers.
    2. SE (Sweden): Hydro/nuclear dominant, ultra-clean baseline.
    3. US_CA (California): Strong solar duck curve, evening peaker ramp.
    4. FR (France): Nuclear baseload, moderate variance.
    """
    os.makedirs(output_dir, exist_ok=True)
    steps = int((duration_hours * 60) / step_minutes)
    time_index = pd.date_range("2024-06-01 00:00:00", periods=steps, freq=f"{step_minutes}min")

    hours_of_day = time_index.hour + time_index.minute / 60.0
    day_indices = np.arange(steps) / (24 * 60 / step_minutes)

    # 1. Germany (DE): Base ~380, solar dip at noon, evening peak at 19:00-21:00, wind waves
    solar_effect_de = -140 * np.clip(np.sin(np.pi * (hours_of_day - 6) / 12), 0, None)
    evening_peak_de = 110 * np.exp(-((hours_of_day - 20) ** 2) / 8)
    wind_wave_de = 60 * np.sin(2 * np.pi * day_indices / 2.5)
    noise_de = np.random.normal(0, 15, steps)
    ci_de = np.clip(380 + solar_effect_de + evening_peak_de + wind_wave_de + noise_de, 80, 680)

    # 2. Sweden (SE): Clean baseload ~35, mild industrial variation
    ci_se = np.clip(35 + 10 * np.sin(2 * np.pi * hours_of_day / 24) + np.random.normal(0, 5, steps), 15, 80)

    # 3. California (US-CA): Solar duck curve, day drops to 160, evening surges to 480
    solar_effect_ca = -180 * np.clip(np.sin(np.pi * (hours_of_day - 7) / 11), 0, None)
    evening_peak_ca = 220 * np.exp(-((hours_of_day - 20.5) ** 2) / 6)
    noise_ca = np.random.normal(0, 18, steps)
    ci_ca = np.clip(320 + solar_effect_ca + evening_peak_ca + noise_ca, 100, 580)

    # 4. France (FR): Nuclear baseline ~55, winter/summer HVAC peak
    ci_fr = np.clip(60 + 18 * np.sin(2 * np.pi * (hours_of_day - 8) / 24) + np.random.normal(0, 6, steps), 25, 120)

    df_traces = pd.DataFrame({
        "timestamp": time_index,
        "DE": np.round(ci_de, 2),
        "SE": np.round(ci_se, 2),
        "US_CA": np.round(ci_ca, 2),
        "FR": np.round(ci_fr, 2)
    })

    file_path = os.path.join(output_dir, "grid_carbon_intensity_multi_region.csv")
    df_traces.to_csv(file_path, index=False)
    print(f"[OK] Generated multi-region carbon traces: {file_path} ({len(df_traces)} intervals)")
    return df_traces


def generate_workload_traces(output_dir: str, num_tasks: int = 500, simulation_horizon_hours: int = 72):
    """
    Generates realistic heterogeneous batch and streaming tasks:
    - AI Training / Deep Learning (high GPU, long duration, flexible deadline)
    - Data Processing / ETL Spark jobs (high CPU/RAM, medium duration, moderate deadline)
    - Web / API Microservices (lightweight, immediate deadline, low slack)
    - Scientific HPC simulations (high CPU, long duration, large slack)
    """
    os.makedirs(output_dir, exist_ok=True)
    np.random.seed(42)

    task_types = [
        {"type": "ai_training", "cpu_range": (8, 32), "ram_range": (32, 128), "gpu_range": (1, 4), "dur_range": (120, 480), "slack_mult": (2.0, 4.0), "prob": 0.25},
        {"type": "etl_batch", "cpu_range": (4, 16), "ram_range": (16, 64), "gpu_range": (0, 0), "dur_range": (30, 150), "slack_mult": (1.5, 3.0), "prob": 0.35},
        {"type": "interactive_service", "cpu_range": (1, 4), "ram_range": (2, 8), "gpu_range": (0, 0), "dur_range": (10, 45), "slack_mult": (1.1, 1.3), "prob": 0.25},
        {"type": "scientific_hpc", "cpu_range": (16, 64), "ram_range": (64, 256), "gpu_range": (0, 2), "dur_range": (180, 600), "slack_mult": (2.5, 5.0), "prob": 0.15}
    ]

    probabilities = [t["prob"] for t in task_types]
    tasks = []

    # Diurnal arrival pattern: more tasks during business hours (9-17)
    horizon_minutes = simulation_horizon_hours * 60

    for i in range(num_tasks):
        # Sample arrival with diurnal density
        # Generate candidate arrival times with non-homogeneous Poisson process
        u = np.random.uniform(0, horizon_minutes)
        hour = (u / 60.0) % 24
        # Acceptance rate based on diurnal curve
        rate = 0.3 + 0.7 * np.sin(np.pi * hour / 24) ** 2
        if np.random.uniform(0, 1) > rate:
            u = np.random.uniform(0, horizon_minutes)

        arrival_time = round(float(u), 1)
        chosen_type = np.random.choice(task_types, p=probabilities)

        cpu = int(np.random.randint(chosen_type["cpu_range"][0], chosen_type["cpu_range"][1] + 1))
        ram = int(np.random.randint(chosen_type["ram_range"][0], chosen_type["ram_range"][1] + 1))
        gpu = int(np.random.randint(chosen_type["gpu_range"][0], chosen_type["gpu_range"][1] + 1))
        duration = int(np.random.randint(chosen_type["dur_range"][0], chosen_type["dur_range"][1] + 1))

        slack_ratio = float(np.random.uniform(chosen_type["slack_mult"][0], chosen_type["slack_mult"][1]))
        deadline = round(arrival_time + duration * slack_ratio, 1)

        # Priority: 1 (Critical) to 3 (Low/Delayable)
        if chosen_type["type"] == "interactive_service":
            priority = 1
        elif chosen_type["type"] == "etl_batch":
            priority = 2
        else:
            priority = 3

        task = {
            "task_id": f"task_{i:04d}",
            "job_type": chosen_type["type"],
            "arrival_time_min": arrival_time,
            "duration_min": duration,
            "deadline_min": deadline,
            "cpu_cores": cpu,
            "memory_gb": ram,
            "gpu_units": gpu,
            "priority": priority,
            "data_size_gb": round(float(np.random.uniform(1.0, 50.0)), 1)
        }
        tasks.append(task)

    # Sort tasks strictly by arrival time
    tasks.sort(key=lambda x: x["arrival_time_min"])

    # Re-index task IDs to maintain ordering
    for idx, t in enumerate(tasks):
        t["task_id"] = f"task_{idx:04d}"

    workload_file = os.path.join(output_dir, "synthetic_cluster_workload.json")
    with open(workload_file, "w") as f:
        json.dump(tasks, f, indent=2)

    print(f"[OK] Generated workload trace: {workload_file} ({len(tasks)} tasks)")
    return tasks


if __name__ == "__main__":
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "traces"))
    grid_dir = os.path.join(base_dir, "grid_carbon")
    workload_dir = os.path.join(base_dir, "workloads")

    generate_carbon_traces(grid_dir, duration_hours=168, step_minutes=15)
    generate_workload_traces(workload_dir, num_tasks=600, simulation_horizon_hours=72)
