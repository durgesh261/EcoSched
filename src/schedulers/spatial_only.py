"""
Ablation Scheduler: Spatial-Only Carbon-Aware Scheduler.
Migrates tasks across regions to chase lowest instantaneous carbon intensity,
but does NOT perform temporal deferral/slack delay scheduling.
Used in scientific ablation studies to decouple the impact of spatial vs temporal shifting.
"""

from typing import List, Tuple
from .base import BaseScheduler
from ..core.task import WorkloadTask
from ..core.node import ComputeNode
from ..core.cluster import DistributedCluster
from ..core.grid import CarbonGridProvider
from ..core.models import Region


class SpatialOnlyCarbonScheduler(BaseScheduler):
    """
    Evaluates real-time carbon intensity across regions and WAN transfer delays,
    routing tasks to the greenest available region immediately (zero delay scheduling).
    """

    def __init__(self, home_region: Region = Region.DE):
        super().__init__(name="Spatial_Only_Carbon")
        self.home_region = home_region

    def schedule(
        self,
        current_time_min: float,
        queued_tasks: List[WorkloadTask],
        cluster: DistributedCluster,
        grid_provider: CarbonGridProvider
    ) -> List[Tuple[WorkloadTask, ComputeNode, float]]:
        assignments: List[Tuple[WorkloadTask, ComputeNode, float]] = []

        sorted_tasks = sorted(queued_tasks, key=lambda t: t.slack_time(current_time_min))

        tentative_allocations = {
            n.node_id: [n.available_cpu, n.available_ram, n.available_gpu]
            for n in cluster.nodes.values()
        }

        for task in sorted_tasks:
            best_node = None
            best_carbon = float("inf")
            best_delay = 0.0

            for node in cluster.nodes.values():
                avail_cpu, avail_ram, avail_gpu = tentative_allocations[node.node_id]

                if avail_cpu >= task.cpu and avail_ram >= task.ram and avail_gpu >= task.gpu:
                    delay = cluster.compute_transfer_delay_min(self.home_region, node.region, task.data_size_gb)

                    # Deadline constraint check
                    if current_time_min + delay + task.duration > task.deadline:
                        continue

                    # Instantaneous carbon intensity at scheduled start
                    ci = grid_provider.get_intensity(node.region, current_time_min + delay)
                    is_active = tentative_allocations[node.node_id][0] < node.total_cpu
                    p_idle_inc = 0.0 if is_active else node.spec.idle_power_watts
                    p_dyn = (node.spec.peak_power_watts - node.spec.idle_power_watts) * (task.cpu / node.total_cpu)
                    power_w = (p_idle_inc + p_dyn) * node.spec.pue
                    energy_kwh = (power_w * task.duration / 60.0) / 1000.0
                    carbon_g = energy_kwh * ci

                    if carbon_g < best_carbon:
                        best_carbon = carbon_g
                        best_node = node
                        best_delay = delay

            if best_node is not None:
                assignments.append((task, best_node, best_delay))
                tentative_allocations[best_node.node_id][0] -= task.cpu
                tentative_allocations[best_node.node_id][1] -= task.ram
                tentative_allocations[best_node.node_id][2] -= task.gpu

        return assignments
