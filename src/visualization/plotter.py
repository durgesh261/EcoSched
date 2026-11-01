"""
High-resolution visualization generator producing benchmark figures for system performance analysis.
"""

import os
from typing import Dict, List, Optional
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np

# Apply clean visualization styling
plt.rcParams.update({
    "font.size": 11,
    "font.family": "sans-serif",
    "axes.labelsize": 12,
    "axes.titlesize": 13,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.titlesize": 14,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linestyle": "--",
    "lines.linewidth": 2.0,
})


class BenchmarkPlotter:
    """
    Generates high-resolution benchmark charts from simulation telemetry.
    """

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.palette = {
            "FIFO_Default": "#7f7f7f",            # Neutral gray
            "Energy_Greedy_Consolidation": "#1f77b4", # Blue
            "Spatial_Only_Carbon": "#ff7f0e",        # Orange
            "CarbonSlack_Novel": "#2ca02c"          # Forest Green
        }

    def plot_grid_carbon_traces(self, carbon_csv_path: str, save_filename: str = "fig1_grid_carbon_traces.png"):
        """Plot the 4-region carbon intensity dynamics over time."""
        df = pd.read_csv(carbon_csv_path)
        # Take first 72 hours
        df_sub = df.iloc[:288].copy()
        df_sub["time_hours"] = np.arange(len(df_sub)) * 0.25

        fig, ax = plt.subplots(figsize=(10, 4.5), dpi=300)
        ax.plot(df_sub["time_hours"], df_sub["DE"], label="Germany (DE) - High Wind/Solar Volatility", color="#d62728")
        ax.plot(df_sub["time_hours"], df_sub["US_CA"], label="California (US-CA) - Solar Duck Curve", color="#ff7f0e")
        ax.plot(df_sub["time_hours"], df_sub["FR"], label="France (FR) - Nuclear Baseload", color="#9467bd")
        ax.plot(df_sub["time_hours"], df_sub["SE"], label="Sweden (SE) - Ultra-Clean Hydro/Nuclear", color="#2ca02c")

        ax.set_xlabel("Elapsed Simulation Time (Hours)")
        ax.set_ylabel("Carbon Intensity (gCO$_2$eq / kWh)")
        ax.set_title("Multi-Region Grid Carbon Intensity Dynamics (ENTSO-E & CAISO Traces)")
        ax.legend(loc="upper right", framealpha=0.9)
        plt.tight_layout()

        out_path = os.path.join(self.output_dir, save_filename)
        plt.savefig(out_path)
        plt.close()
        print(f"[Plot] Saved: {out_path}")
        return out_path

    def plot_cumulative_carbon_emissions(
        self,
        results_dir: str,
        scenario_name: str = "Nominal_Workload",
        save_filename: str = "fig2_cumulative_carbon.png"
    ):
        """Plots cumulative carbon emissions over time for all schedulers in a scenario."""
        fig, ax = plt.subplots(figsize=(9, 5), dpi=300)

        for sched_name, color in self.palette.items():
            telemetry_path = os.path.join(results_dir, f"telemetry_{scenario_name}_{sched_name}.csv")
            if os.path.exists(telemetry_path):
                df = pd.read_csv(telemetry_path)
                df["time_hours"] = df["time_min"] / 60.0
                df["cumulative_carbon_kg"] = df["step_carbon_g"].cumsum() / 1000.0

                label_clean = sched_name.replace("_", " ")
                ax.plot(df["time_hours"], df["cumulative_carbon_kg"], label=label_clean, color=color)

        ax.set_xlabel("Simulation Horizon (Hours)")
        ax.set_ylabel("Cumulative Operational Carbon (kg CO$_2$eq)")
        ax.set_title(f"Cumulative Carbon Footprint Evolution ({scenario_name.replace('_', ' ')})")
        ax.legend(loc="upper left", framealpha=0.9)
        plt.tight_layout()

        out_path = os.path.join(self.output_dir, save_filename)
        plt.savefig(out_path)
        plt.close()
        print(f"[Plot] Saved: {out_path}")
        return out_path

    def plot_ablation_comparison_bar(
        self,
        summary_csv_path: str,
        save_filename: str = "fig3_ablation_carbon_savings.png"
    ):
        """Bar chart comparing carbon savings (%) and SLA compliance (%) across scenarios."""
        df = pd.read_csv(summary_csv_path)
        df["Savings_Num"] = df["Carbon Savings (%)"].str.rstrip("%").astype(float)
        df["SLA_Num"] = df["SLA Compliance (%)"].str.rstrip("%").astype(float)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5), dpi=300)

        # Plot 1: Carbon Savings %
        sns.barplot(
            data=df,
            x="Scenario",
            y="Savings_Num",
            hue="Scheduler",
            palette=self.palette,
            ax=ax1
        )
        ax1.set_ylabel("Carbon Reduction vs FIFO (%)")
        ax1.set_title("(a) Operational Carbon Reduction")
        ax1.set_xticks(range(len(df["Scenario"].unique())))
        ax1.set_xticklabels(df["Scenario"].unique(), rotation=15)
        ax1.legend_.remove()

        # Plot 2: SLA Compliance %
        sns.barplot(
            data=df,
            x="Scenario",
            y="SLA_Num",
            hue="Scheduler",
            palette=self.palette,
            ax=ax2
        )
        ax2.set_ylabel("SLA Deadline Compliance (%)")
        ax2.set_ylim(80, 102)
        ax2.set_title("(b) SLA / Deadline Compliance")
        ax2.set_xticks(range(len(df["Scenario"].unique())))
        ax2.set_xticklabels(df["Scenario"].unique(), rotation=15)
        ax2.legend(loc="lower left", fontsize=9)

        plt.tight_layout()
        out_path = os.path.join(self.output_dir, save_filename)
        plt.savefig(out_path)
        plt.close()
        print(f"[Plot] Saved: {out_path}")
        return out_path

    def plot_carbon_vs_latency_pareto(
        self,
        summary_csv_path: str,
        save_filename: str = "fig4_pareto_carbon_latency.png"
    ):
        """Scatter plot showing Pareto tradeoff between Carbon Footprint and Turnaround Latency."""
        df = pd.read_csv(summary_csv_path)
        nominal_df = df[df["Scenario"] == "Nominal_Workload"].copy()

        fig, ax = plt.subplots(figsize=(8, 5), dpi=300)

        for _, row in nominal_df.iterrows():
            sched = row["Scheduler"]
            color = self.palette.get(sched, "#333333")
            carbon = row["Total Carbon (kg)"]
            turnaround = row["Avg Turnaround (min)"]

            ax.scatter(turnaround, carbon, color=color, s=220, edgecolors="black", zorder=4)
            ax.annotate(
                sched.replace("_", " "),
                (turnaround, carbon),
                textcoords="offset points",
                xytext=(8, -4),
                fontsize=10,
                weight="bold"
            )

        ax.set_xlabel("Mean Job Turnaround Time (Minutes)")
        ax.set_ylabel("Total Operational Carbon (kg CO$_2$eq)")
        ax.set_title("Pareto Efficiency: Carbon Footprint vs. Job Completion Latency")
        plt.tight_layout()

        out_path = os.path.join(self.output_dir, save_filename)
        plt.savefig(out_path)
        plt.close()
        print(f"[Plot] Saved: {out_path}")
        return out_path
