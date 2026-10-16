"""
Unit tests validating Schedulers behavior and constraint satisfaction.
"""

import pytest
from src.core.models import Region, TaskSpec
from src.core.task import WorkloadTask
from src.core.cluster import DistributedCluster
from src.core.grid import CarbonGridProvider
from src.schedulers.fifo import FIFOScheduler
from src.schedulers.energy_greedy import EnergyGreedyScheduler
from src.schedulers.spatial_only import SpatialOnlyCarbonScheduler
from src.schedulers.carbon_slack import CarbonSlackScheduler


@pytest.fixture
def test_setup():
    cluster = DistributedCluster.create_default_heterogeneous_cluster()
    grid_provider = CarbonGridProvider()
    tasks = [
        WorkloadTask(TaskSpec(
            task_id=f"test_task_{i}",
            arrival_time_min=0.0,
            duration_min=45.0,
            deadline_min=150.0,
            cpu_cores=16,
            memory_gb=64,
            gpu_units=1 if i % 2 == 0 else 0
        )) for i in range(10)
    ]
    return cluster, grid_provider, tasks


def test_schedulers_interface_and_capacity(test_setup):
    cluster, grid_provider, tasks = test_setup

    schedulers = [
        FIFOScheduler(),
        EnergyGreedyScheduler(),
        SpatialOnlyCarbonScheduler(),
        CarbonSlackScheduler()
    ]

    for sched in schedulers:
        assignments = sched.schedule(
            current_time_min=0.0,
            queued_tasks=tasks,
            cluster=cluster,
            grid_provider=grid_provider
        )

        assert len(assignments) > 0
        for task, node, delay in assignments:
            assert node.node_id in cluster.nodes
            assert delay >= 0.0
            # Ensure assigned resources don't exceed node physical specs
            assert task.cpu <= node.total_cpu
            assert task.ram <= node.total_ram
            assert task.gpu <= node.total_gpu
