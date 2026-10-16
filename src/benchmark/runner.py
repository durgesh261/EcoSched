"""
Automated benchmark runner orchestrating multi-scenario evaluations across all schedulers.
"""

import os
import json
from typing import List, Dict, Any
import pandas as pd
try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

from ..core.cluster import DistributedCluster
from ..core.grid import CarbonGridProvider
from ..core.task import WorkloadTask
from ..core.models import TaskSpec
from ..simulator.engine import SimulationEngine
from ..simulator.metrics import SimulationSummary
from ..schedulers.fifo import FIFOScheduler
from ..schedulers.energy_greedy import EnergyGreedyScheduler
from ..schedulers.spatial_only import SpatialOnlyCarbonScheduler
from ..schedulers.carbon_slack import CarbonSlackScheduler
from .scenarios import create_scenario_nominal, create_scenario_tight_deadlines, create_scenario_heavy_load


class BenchmarkRunner:
    """
    Executes automated comparative evaluation and ablation studies across all schedulers.
    """

    def __init__(
        self,
        workload_json_path: str,
        carbon_csv_path: str,
        output_results_dir: str
    ):
        self.workload_json_path = workload_json_path
        self.carbon_csv_path = carbon_csv_path
        self.output_results_dir = output_results_dir
        os.makedirs(output_results_dir, exist_ok=True)

        self.grid_provider = CarbonGridProvider(carbon_csv_path)
        self.base_tasks = self._load_tasks(workload_json_path)

    def _load_tasks(self, path: str) -> List[WorkloadTask]:
        with open(path, "r") as f:
            raw_list = json.load(f)
        tasks = []
        for item in raw_list:
            spec = TaskSpec(**item)
            tasks.append(WorkloadTask(spec))
        return tasks

    def run_scenario(self, scenario_name: str, tasks: List[WorkloadTask]) -> List[SimulationSummary]:
        print(f"\n=======================================================")
        print(f"   Executing Scenario: {scenario_name} ({len(tasks)} tasks)")
        print(f"=======================================================")

        schedulers = [
            FIFOScheduler(),
            EnergyGreedyScheduler(),
            SpatialOnlyCarbonScheduler(),
            CarbonSlackScheduler(carbon_weight=0.70, energy_weight=0.15, slack_risk_weight=0.15)
        ]

        summaries: List[SimulationSummary] = []
        baseline_carbon = None

        for scheduler in schedulers:
            cluster = DistributedCluster.create_default_heterogeneous_cluster()
            # Deepcopy tasks for independent runs
            scenario_tasks = [WorkloadTask(t.spec) for t in tasks]

            engine = SimulationEngine(
                cluster=cluster,
                grid_provider=self.grid_provider,
                tasks=scenario_tasks,
                scheduler=scheduler,
                step_minutes=5.0
            )

            print(f" -> Running [{scheduler.name}]...", end="", flush=True)
            summary = engine.run()

            # Record baseline carbon from FIFO
            if baseline_carbon is None:
                baseline_carbon = summary.total_carbon_kg
                summary.carbon_savings_pct = 0.0
            else:
                savings = ((baseline_carbon - summary.total_carbon_kg) / baseline_carbon) * 100.0
                summary.carbon_savings_pct = round(savings, 2)

            summaries.append(summary)
            print(f" Done. Carbon: {summary.total_carbon_kg} kg ({summary.carbon_savings_pct:+0.2f}%), SLA Compliance: {summary.deadline_compliance_pct}%")

            # Save detailed time series telemetry
            ts_df = pd.DataFrame(engine.metrics_collector.time_series_records)
            ts_path = os.path.join(self.output_results_dir, f"telemetry_{scenario_name}_{scheduler.name}.csv")
            ts_df.to_csv(ts_path, index=False)

        return summaries

    def run_all(self) -> Dict[str, List[SimulationSummary]]:
        scenarios = {
            "Nominal_Workload": create_scenario_nominal(self.base_tasks),
            "Tight_SLA_Deadlines": create_scenario_tight_deadlines(self.base_tasks),
            "Heavy_Contention": create_scenario_heavy_load(self.base_tasks),
        }

        all_results = {}
        for sc_name, sc_tasks in scenarios.items():
            summaries = self.run_scenario(sc_name, sc_tasks)
            all_results[sc_name] = summaries

        self._export_summary_tables(all_results)
        return all_results

    def _export_summary_tables(self, results: Dict[str, List[SimulationSummary]]):
        rows = []
        for sc_name, summaries in results.items():
            for s in summaries:
                rows.append({
                    "Scenario": sc_name,
                    "Scheduler": s.scheduler_name,
                    "Total Carbon (kg)": s.total_carbon_kg,
                    "Carbon Savings (%)": f"{s.carbon_savings_pct:+0.2f}%",
                    "Total Energy (kWh)": s.total_energy_kwh,
                    "SLA Compliance (%)": f"{s.deadline_compliance_pct}%",
                    "Avg Wait (min)": s.average_waiting_time_min,
                    "Avg Turnaround (min)": s.average_turnaround_time_min,
                    "Avg CPU Util (%)": f"{s.average_cpu_utilization_pct}%"
                })

        df_all = pd.DataFrame(rows)
        csv_path = os.path.join(self.output_results_dir, "benchmark_summary_matrix.csv")
        df_all.to_csv(csv_path, index=False)

        print("\n" + "=" * 80)
        print("                 ECOSCHED COMPREHENSIVE BENCHMARK SUMMARY")
        if HAS_TABULATE:
            print(tabulate(df_all, headers="keys", tablefmt="github", showindex=False))
        else:
            print(df_all.to_string(index=False))
        print("=" * 80)
        print(f"[OK] Summary table saved to: {csv_path}")
