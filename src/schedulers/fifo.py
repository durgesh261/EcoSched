"""
Baseline Scheduler 1: Standard First-In-First-Out (FIFO) First-Fit policy.
Represents conventional Kubernetes/Slurm carbon-blind scheduling.
"""

from typing import List, Tuple
from .base import BaseScheduler
from ..core.task import WorkloadTask
from ..core.node import ComputeNode
from ..core.cluster import DistributedCluster
from ..core.grid import CarbonGridProvider
from ..core.models import Region


class FIFOScheduler(BaseScheduler):
    """
    Standard First-Come-First-Served scheduler.
    Schedules tasks strictly by arrival order onto the first available node with sufficient resources.
    Completely carbon-blind and energy-blind.
    """

    def __init__(self, default_home_region: Region = Region.DE):
        super().__init__(name="FIFO_Default")
        self.default_home_region = default_home_region

    def schedule(
        self,
        current_time_min: float,
        queued_tasks: List[WorkloadTask],
        cluster: DistributedCluster,
        grid_provider: CarbonGridProvider
    ) -> List[Tuple[WorkloadTask, ComputeNode, float]]:
        assignments: List[Tuple[WorkloadTask, ComputeNode, float]] = []

        # Sort strictly by arrival time
        sorted_tasks = sorted(queued_tasks, key=lambda t: t.arrival_time)

        # Track tentative allocations in this cycle
        tentative_allocations = {n.node_id: (n.available_cpu, n.available_ram, n.available_gpu) for n in cluster.nodes.values()}

        for task in sorted_tasks:
            # First attempt to place in home region, then anywhere in cluster
            placed = False
            for node in cluster.nodes.values():
                avail_cpu, avail_ram, avail_gpu = tentative_allocations[node.node_id]

                if avail_cpu >= task.cpu and avail_ram >= task.ram and avail_gpu >= task.gpu:
                    # Found first fit
                    delay = cluster.compute_transfer_delay_min(self.default_home_region, node.region, task.data_size_gb)
                    assignments.append((task, node, delay))

                    # Update tentative
                    tentative_allocations[node.node_id] = (
                        avail_cpu - task.cpu,
                        avail_ram - task.ram,
                        avail_gpu - task.gpu
                    )
                    placed = True
                    break

        return assignments
