"""
Abstract base class defining the Scheduler interface.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple
from ..core.task import WorkloadTask
from ..core.node import ComputeNode
from ..core.cluster import DistributedCluster
from ..core.grid import CarbonGridProvider


class BaseScheduler(ABC):
    """
    Abstract interface for cluster workload schedulers.
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def schedule(
        self,
        current_time_min: float,
        queued_tasks: List[WorkloadTask],
        cluster: DistributedCluster,
        grid_provider: CarbonGridProvider
    ) -> List[Tuple[WorkloadTask, ComputeNode, float]]:
        """
        Evaluates queued tasks and determines placement onto cluster nodes.

        Returns:
            List of tuples: (task, target_node, transfer_delay_minutes)
        """
        pass
