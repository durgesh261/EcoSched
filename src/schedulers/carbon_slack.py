"""
Novel Proposed Algorithm: CarbonSlack-Scheduler
Dynamic Spatial & Temporal Slack-Aware Workload Shifting for Distributed Clusters.
"""

from typing import List, Tuple, Optional
import numpy as np
from .base import BaseScheduler
from ..core.task import WorkloadTask
from ..core.node import ComputeNode
from ..core.cluster import DistributedCluster
from ..core.grid import CarbonGridProvider
from ..core.models import Region


class CarbonSlackScheduler(BaseScheduler):
    """
    Novel Carbon-Aware Dynamic Scheduler.
    Key Innovations:
    1. Slack-Window Triage: Classifies tasks into SLA-Critical vs Elastic.
    2. Temporal Carbon Valley Exploitation: Defers elastic tasks during grid emission peaks
       if a green valley is forecasted within the task's allowable slack window.
    3. Amortized Spatial Shifting: Dynamically migrates workloads across geo-regions
       accounting for WAN bandwidth, transfer latency, and regional PUE differences.
    4. Multi-Objective Cost Minimization: Balances carbon emission, hardware energy,
       and deadline violation risk.
    """

    def __init__(
        self,
        home_region: Region = Region.DE,
        carbon_weight: float = 0.65,
        energy_weight: float = 0.20,
        slack_risk_weight: float = 0.15,
        critical_slack_threshold_min: float = 20.0,
        deferral_carbon_diff_threshold: float = 50.0 # gCO2/kWh minimum expected drop to justify delaying
    ):
        super().__init__(name="CarbonSlack_Novel")
        self.home_region = home_region
        self.w_carbon = carbon_weight
        self.w_energy = energy_weight
        self.w_slack = slack_risk_weight
        self.crit_threshold_min = critical_slack_threshold_min
        self.deferral_ci_threshold = deferral_carbon_diff_threshold

    def schedule(
        self,
        current_time_min: float,
        queued_tasks: List[WorkloadTask],
        cluster: DistributedCluster,
        grid_provider: CarbonGridProvider
    ) -> List[Tuple[WorkloadTask, ComputeNode, float]]:
        assignments: List[Tuple[WorkloadTask, ComputeNode, float]] = []

        # Sort tasks prioritizing lowest remaining slack first (Earliest Deadline First with Slack)
        def task_urgency_key(t: WorkloadTask):
            # Priority 1 (critical) always first, then lowest slack
            return (t.priority, t.slack_time(current_time_min))

        sorted_tasks = sorted(queued_tasks, key=task_urgency_key)

        tentative_allocations = {
            n.node_id: [n.available_cpu, n.available_ram, n.available_gpu, n.allocated_cpu]
            for n in cluster.nodes.values()
        }

        for task in sorted_tasks:
            slack = task.slack_time(current_time_min)
            is_critical = slack <= self.crit_threshold_min

            # --- Innovation 1: Temporal Delay Decision (Green Wait) ---
            # If task has ample slack, evaluate whether delaying execution yields significant carbon drop
            if not is_critical and task.priority > 1:
                # Find best start window in home/cleanest region
                clean_region, _ = grid_provider.find_cleanest_region_now(current_time_min)
                current_ci = grid_provider.get_intensity(clean_region, current_time_min)

                # Search available slack window (leaving a safety buffer)
                usable_slack = max(0.0, slack - self.crit_threshold_min)
                optimal_start, forecasted_min_ci = grid_provider.find_optimal_green_window(
                    region=clean_region,
                    start_time_min=current_time_min,
                    window_duration_min=usable_slack,
                    task_duration_min=task.duration
                )

                # If waiting yields a large carbon reduction and cluster is not backlogged, keep task in queue
                if (current_ci - forecasted_min_ci) > self.deferral_ci_threshold and optimal_start > current_time_min + 5.0 and len(queued_tasks) < 50:
                    # Defer task for now!
                    continue

            # --- Innovation 2: Spatial & Node Placement Scoring ---
            best_node = None
            best_delay = 0.0
            lowest_cost = float("inf")

            for node in cluster.nodes.values():
                avail_cpu, avail_ram, avail_gpu, cur_alloc = tentative_allocations[node.node_id]

                if avail_cpu >= task.cpu and avail_ram >= task.ram and avail_gpu >= task.gpu:
                    # Compute network transfer delay from home region to node's region
                    delay = cluster.compute_transfer_delay_min(self.home_region, node.region, task.data_size_gb)

                    # Hard constraint: Check if transfer delay + execution time would violate deadline
                    effective_completion_time = current_time_min + delay + task.duration
                    if effective_completion_time > task.deadline:
                        # Cannot place here without guaranteed deadline breach
                        continue

                    # Carbon intensity at scheduled start time in target region
                    scheduled_start = current_time_min + delay
                    ci = grid_provider.get_intensity(node.region, scheduled_start)

                    # Dynamic power delta on this node
                    is_active = cur_alloc > 0
                    p_idle_penalty = 0.0 if is_active else node.spec.idle_power_watts
                    p_dynamic = (node.spec.peak_power_watts - node.spec.idle_power_watts) * (task.cpu / node.total_cpu)
                    total_power_w = (p_idle_penalty + p_dynamic) * node.spec.pue

                    # Projected carbon in gCO2eq: (Watts * duration_min / 60 / 1000) * CI
                    energy_kwh = (total_power_w * task.duration / 60.0) / 1000.0
                    projected_carbon_g = energy_kwh * ci

                    # Normalized metrics for multi-objective cost
                    norm_carbon = projected_carbon_g / 500.0 # scale
                    norm_energy = total_power_w / 600.0
                    norm_slack_risk = max(0.0, 1.0 - (slack / max(1.0, task.duration * 2.0)))
                    norm_transfer_penalty = delay / 10.0

                    composite_cost = (
                        self.w_carbon * norm_carbon +
                        self.w_energy * norm_energy +
                        self.w_slack * norm_slack_risk +
                        0.05 * norm_transfer_penalty
                    )

                    if composite_cost < lowest_cost:
                        lowest_cost = composite_cost
                        best_node = node
                        best_delay = delay

            if best_node is not None:
                assignments.append((task, best_node, best_delay))
                tentative_allocations[best_node.node_id][0] -= task.cpu
                tentative_allocations[best_node.node_id][1] -= task.ram
                tentative_allocations[best_node.node_id][2] -= task.gpu
                tentative_allocations[best_node.node_id][3] += task.cpu

        return assignments
