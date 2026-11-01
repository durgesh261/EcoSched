"""
Main execution script to run complete benchmark evaluation suite and generate all figures.
Usage:
    python scripts/run_experiments.py
"""

import os
import sys

# Ensure root directory is on python path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.benchmark.runner import BenchmarkRunner
from src.visualization.plotter import BenchmarkPlotter
from scripts.generate_sample_data import generate_carbon_traces, generate_workload_traces


def main():
    print("================================================================================")
    print("      ECOSCHED: Carbon-Aware Workload Orchestrator Benchmark Suite")
    print("================================================================================")

    data_dir = os.path.join(root_dir, "data", "traces")
    grid_csv = os.path.join(data_dir, "grid_carbon", "grid_carbon_intensity_multi_region.csv")
    workload_json = os.path.join(data_dir, "workloads", "synthetic_cluster_workload.json")

    results_dir = os.path.join(root_dir, "output", "results")
    figures_dir = os.path.join(root_dir, "output", "figures")
    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(figures_dir, exist_ok=True)

    # 1. Ensure traces exist
    if not os.path.exists(grid_csv):
        print("[!] Generating grid carbon traces...")
        generate_carbon_traces(os.path.dirname(grid_csv))

    if not os.path.exists(workload_json):
        print("[!] Generating synthetic cluster workload traces...")
        generate_workload_traces(os.path.dirname(workload_json))

    # 2. Execute full benchmark suite across all scenarios
    runner = BenchmarkRunner(
        workload_json_path=workload_json,
        carbon_csv_path=grid_csv,
        output_results_dir=results_dir
    )

    results = runner.run_all()

    # 3. Generate high-resolution benchmark figures
    print("\n--------------------------------------------------------------------------------")
    print("            Generating High-Resolution Benchmark Figures (300 DPI)")
    print("--------------------------------------------------------------------------------")
    plotter = BenchmarkPlotter(output_dir=figures_dir)

    plotter.plot_grid_carbon_traces(grid_csv)
    plotter.plot_cumulative_carbon_emissions(results_dir, scenario_name="Nominal_Workload")
    plotter.plot_cumulative_carbon_emissions(results_dir, scenario_name="Heavy_Contention", save_filename="fig2b_cumulative_carbon_heavy.png")

    summary_csv = os.path.join(results_dir, "benchmark_summary_matrix.csv")
    if os.path.exists(summary_csv):
        plotter.plot_ablation_comparison_bar(summary_csv)
        plotter.plot_carbon_vs_latency_pareto(summary_csv)

    print("\n[SUCCESS] Benchmark suite completed successfully!")
    print(f"Results stored in: {results_dir}")
    print(f"Figures stored in: {figures_dir}")
    print("================================================================================")


if __name__ == "__main__":
    main()
