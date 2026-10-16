"""
Baseline Scheduler 2: Energy-Minimizing Greedy Consolidation policy.
Packs workloads onto existing active servers to minimize total electrical wattage,
but remains completely carbon-blind (ignores time-of-day solar/wind & regional grid CI).
"""

from typing import List, Tuple
from .base import BaseScheduler
from ..core.task import WorkloadTask
from ..core.node import ComputeNode
from ..core.cluster import DistributedCluster
from ..core.grid import CarbonGridProvider
from ..core.models import Region


class EnergyGreedyScheduler(BaseScheduler):
    """
    Minimizes electrical power (Watts) by server consolidation.
    Favors packing tasks onto already-busy nodes with lowest datacenter PUE,
    minimizing unneeded idle server power wakeups.
    """

    def __init__(self, home_region: Region = Region.DE):
        super().__init__(name="Energy_Greedy_Consolidation")
        self.home_region = home_region

    def schedule(
        self,
        current_time_min: float,
        queued_tasks: List[WorkloadTask],
        cluster: DistributedCluster,
        grid_provider: CarbonGridProvider
    ) -> List[Tuple[WorkloadTask, ComputeNode, float]]:
        assignments: List[Tuple[WorkloadTask, ComputeNode, float]] = []

        # Sort tasks by largest resource request first (Best-Fit Decreasing heuristic)
        sorted_tasks = sorted(queued_tasks, key=lambda t: (t.cpu + t.gpu * 10), reverse=True)

        tentative_allocations = {
            n.node_id: [n.available_cpu, n.available_ram, n.available_gpu, n.allocated_cpu]
            for n in cluster.nodes.values()
        }

        for task in sorted_tasks:
            best_node = None
            best_power_delta = float("inf")
            best_delay = 0.0

            for node in cluster.nodes.values():
                avail_cpu, avail_ram, avail_gpu, cur_alloc = tentative_allocations[node.node_id]

                if avail_cpu >= task.cpu and avail_ram >= task.ram and avail_gpu >= task.gpu:
                    # Calculate incremental power delta
                    # If server was idle (cur_alloc == 0), penalty of idle base power
                    is_currently_active = cur_alloc > 0
                    p_base = 0.0 if is_currently_active else node.spec.idle_power_watts
                    p_inc = (node.spec.peak_power_watts - node.spec.idle_power_watts) * (task.cpu / node.total_cpu)
                    total_p_delta = (p_base + p_inc) * node.spec.pue

                    if total_p_delta < best_power_delta:
                        best_power_delta = total_p_delta
                        best_node = node
                        best_delay = cluster.compute_transfer_delay_min(self.home_region, node.region, task.data_size_gb)

            if best_node is not None:
                assignments.append((task, best_node, best_delay))
                tentative_allocations[best_node.node_id][0] -= task.cpu
                tentative_allocations[best_node.node_id][1] -= task.ram
                tentative_allocations[best_node.node_id][2] -= task.gpu
                tentative_allocations[best_node.node_id][3] += task.cpu

        return assignments
