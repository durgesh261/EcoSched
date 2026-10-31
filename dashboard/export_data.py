"""
Serializes EcoSched simulation results, grid traces, cluster nodes, and telemetry
into a compact JSON payload for the interactive web Digital Twin dashboard.
"""

import os
import json
import pandas as pd
import numpy as np

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data", "traces")
OUTPUT_DIR = os.path.join(ROOT_DIR, "output", "results")
DASHBOARD_DIR = os.path.join(ROOT_DIR, "dashboard")


def export_dashboard_payload():
    os.makedirs(DASHBOARD_DIR, exist_ok=True)
    print("[*] Preparing EcoSched Digital Twin dashboard data payload...")

    # 1. Load multi-region grid traces (15-min intervals over 72 hours = 288 steps)
    grid_csv = os.path.join(DATA_DIR, "grid_carbon", "grid_carbon_intensity_multi_region.csv")
    df_grid = pd.read_csv(grid_csv)
    # 72 hours = 288 intervals of 15 mins
    df_grid_72h = df_grid.iloc[:288].copy()

    grid_traces = {
        "intervals": 288,
        "step_minutes": 15,
        "horizon_hours": 72,
        "DE": df_grid_72h["DE"].round(1).tolist(),
        "SE": df_grid_72h["SE"].round(1).tolist(),
        "US_CA": df_grid_72h["US_CA"].round(1).tolist(),
        "FR": df_grid_72h["FR"].round(1).tolist(),
    }

    # 2. Cluster topology metadata
    regions = [
        {"id": "DE", "name": "Germany (Frankfurt)", "pue": 1.22, "nodes_cpu": 6, "nodes_gpu": 2, "base_ci": 380, "renewables": "Solar / Wind Volatility", "flag": "🇩🇪"},
        {"id": "SE", "name": "Sweden (Stockholm)", "pue": 1.12, "nodes_cpu": 6, "nodes_gpu": 2, "base_ci": 35, "renewables": "Hydro / Nuclear Baseload", "flag": "🇸🇪"},
        {"id": "US_CA", "name": "California (Silicon Valley)", "pue": 1.25, "nodes_cpu": 4, "nodes_gpu": 2, "base_ci": 320, "renewables": "Solar Duck Curve / Peakers", "flag": "🇺🇸"},
        {"id": "FR", "name": "France (Paris)", "pue": 1.18, "nodes_cpu": 4, "nodes_gpu": 1, "base_ci": 60, "renewables": "Nuclear Baseload", "flag": "🇫🇷"},
    ]

    nodes_list = []
    for reg in regions:
        r_id = reg["id"]
        # CPU nodes
        for i in range(reg["nodes_cpu"]):
            nodes_list.append({
                "id": f"node_{r_id.lower()}_cpu_{i:02d}",
                "region": r_id,
                "type": "CPU",
                "cpu": 64,
                "ram": 256,
                "gpu": 0,
                "idle_w": 95,
                "peak_w": 380,
                "standby_w": 15,
                "pue": reg["pue"]
            })
        # GPU nodes
        for j in range(reg["nodes_gpu"]):
            nodes_list.append({
                "id": f"node_{r_id.lower()}_gpu_{j:02d}",
                "region": r_id,
                "type": "GPU-AI",
                "cpu": 96,
                "ram": 512,
                "gpu": 4,
                "idle_w": 140,
                "peak_w": 480,
                "standby_w": 25,
                "pue": reg["pue"]
            })

    # 3. Read benchmark summary matrix
    summary_csv = os.path.join(OUTPUT_DIR, "benchmark_summary_matrix.csv")
    df_summary = pd.read_csv(summary_csv)
    summary_benchmarks = df_summary.to_dict(orient="records")

    # 4. Telemetry series for each policy in Nominal Workload & Heavy Contention
    # Subsample steps (every 15 min or 30 min) to keep JSON light and snappy (< 1.5 MB)
    scenarios = ["Nominal_Workload", "Tight_SLA_Deadlines", "Heavy_Contention"]
    schedulers = [
        "CarbonSlack_Novel",
        "Spatial_Only_Carbon",
        "Energy_Greedy_Consolidation",
        "FIFO_Default"
    ]

    telemetry_data = {}
    for sc in scenarios:
        telemetry_data[sc] = {}
        for sch in schedulers:
            fn = f"telemetry_{sc}_{sch}.csv"
            path = os.path.join(OUTPUT_DIR, fn)
            if os.path.exists(path):
                df_t = pd.read_csv(path)
                # Resample every 3rd step (15 min interval) up to 72 hours
                df_sub = df_t.iloc[::3].copy().reset_index(drop=True)
                # Cap to 288 steps (72 hours)
                if len(df_sub) > 288:
                    df_sub = df_sub.iloc[:288]

                cum_carbon = (df_sub["step_carbon_g"].cumsum() / 1000.0).round(2).tolist()
                cum_energy = df_sub["step_energy_kwh"].cumsum().round(2).tolist()

                telemetry_data[sc][sch] = {
                    "time_hours": (df_sub["time_min"] / 60.0).round(2).tolist(),
                    "running_tasks": df_sub["running_tasks"].astype(int).tolist(),
                    "queued_tasks": df_sub["queued_tasks"].astype(int).tolist(),
                    "cpu_util": df_sub["cpu_utilization_pct"].round(1).tolist(),
                    "step_carbon_kg": (df_sub["step_carbon_g"] / 1000.0).round(4).tolist(),
                    "cum_carbon_kg": cum_carbon,
                    "cum_energy_kwh": cum_energy,
                }

    # 5. Sample sample tasks for the live feed display
    workload_json = os.path.join(DATA_DIR, "workloads", "synthetic_cluster_workload.json")
    with open(workload_json, "r") as f:
        all_tasks = json.load(f)

    # Take first 40 diverse tasks
    sample_tasks = all_tasks[:40]

    payload = {
        "project": "EcoSched",
        "version": "0.1.0",
        "author": "Durgesh Kanjariya",
        "total_nodes": len(nodes_list),
        "total_cluster_cpu": sum(n["cpu"] for n in nodes_list),
        "total_cluster_gpu": sum(n["gpu"] for n in nodes_list),
        "regions": regions,
        "nodes": nodes_list,
        "grid_traces": grid_traces,
        "benchmarks": summary_benchmarks,
        "telemetry": telemetry_data,
        "sample_tasks": sample_tasks
    }

    out_file = os.path.join(DASHBOARD_DIR, "data.json")
    with open(out_file, "w") as f:
        json.dump(payload, f)

    file_size_kb = os.path.getsize(out_file) / 1024
    print(f"[+] Successfully exported EcoSched digital twin payload: {out_file} ({file_size_kb:.1f} KB)")


if __name__ == "__main__":
    export_dashboard_payload()
