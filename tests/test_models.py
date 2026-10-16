"""
Tests for Core data models, Node power calculations, and Slack time logic.
"""

import pytest
from src.core.models import Region, NodeSpec, TaskSpec, TaskState
from src.core.node import ComputeNode
from src.core.task import WorkloadTask
from src.core.cluster import DistributedCluster
from src.core.grid import CarbonGridProvider


def test_compute_node_power_and_allocation():
    spec = NodeSpec(
        node_id="test_node_01",
        region=Region.DE,
        total_cpu_cores=64,
        total_memory_gb=256,
        total_gpu_units=2,
        idle_power_watts=100.0,
        peak_power_watts=400.0,
        pue=1.2
    )
    node = ComputeNode(spec)

    # Idle power test
    assert node.available_cpu == 64
    assert node.available_ram == 256
    assert node.available_gpu == 2
    assert node.cpu_utilization == 0.0

    standby_facility_power = node.get_instantaneous_power_watts()
    assert standby_facility_power == pytest.approx(15.0 * 1.2, rel=1e-3)

    # Allocation test
    ok = node.allocate("task_1", cpu=32, ram=128, gpu=1)
    assert ok is True
    assert node.available_cpu == 32
    assert node.cpu_utilization == 0.5

    active_power = node.get_instantaneous_power_watts()
    assert active_power > standby_facility_power

    # Release test
    node.release("task_1", cpu=32, ram=128, gpu=1)
    assert node.available_cpu == 64
    assert node.allocated_cpu == 0


def test_workload_task_slack_and_progress():
    spec = TaskSpec(
        task_id="t_01",
        job_type="batch",
        arrival_time_min=10.0,
        duration_min=60.0,
        deadline_min=100.0,
        cpu_cores=8,
        memory_gb=32,
        gpu_units=0
    )
    task = WorkloadTask(spec)

    # At arrival t=10, slack = 100 - (10 + 60) = 30
    assert task.slack_time(current_time=10.0) == 30.0
    assert task.slack_ratio(current_time=10.0) == 0.5
    assert task.is_critical(current_time=10.0, safety_margin_min=15.0) is False

    # At t=35, slack = 100 - (35 + 60) = 5 -> critical
    assert task.slack_time(current_time=35.0) == 5.0
    assert task.is_critical(current_time=35.0, safety_margin_min=10.0) is True

    # Progress execution
    task.mark_started(current_time=20.0, node_id="node_01", region=Region.DE)
    assert task.state == TaskState.RUNNING

    finished = task.progress(delta_time_min=30.0, current_time=50.0)
    assert finished is False
    assert task.remaining_duration == 30.0

    finished_now = task.progress(delta_time_min=30.0, current_time=80.0)
    assert finished_now is True
    assert task.state == TaskState.COMPLETED
    assert task.deadline_missed is False


def test_distributed_cluster_wan_latency():
    cluster = DistributedCluster.create_default_heterogeneous_cluster()
    assert len(cluster.nodes) == 27

    # Intra-region latency should be 0 for same region
    delay_local = cluster.compute_transfer_delay_min(Region.DE, Region.DE, data_size_gb=20.0)
    assert delay_local == 0.0

    # Cross-region latency from DE to SE (15 Gbps WAN)
    delay_se = cluster.compute_transfer_delay_min(Region.DE, Region.SE, data_size_gb=15.0)
    assert delay_se > 0.0

    # Intercontinental latency from DE to US_CA should be noticeably higher
    delay_us = cluster.compute_transfer_delay_min(Region.DE, Region.US_CA, data_size_gb=15.0)
    assert delay_us > delay_se
