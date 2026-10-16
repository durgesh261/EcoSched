"""
Evaluation scenarios and workload stress configurations for comprehensive benchmarking.
"""

from typing import List
from copy import deepcopy
from ..core.task import WorkloadTask
from ..core.models import TaskSpec


def create_scenario_nominal(base_tasks: List[WorkloadTask]) -> List[WorkloadTask]:
    """Scenario A: Standard mixed cluster workload (balanced arrival rate)."""
    return [WorkloadTask(t.spec) for t in base_tasks]


def create_scenario_tight_deadlines(base_tasks: List[WorkloadTask]) -> List[WorkloadTask]:
    """
    Scenario B: Tight SLA Regime.
    Reduces available slack time by 50% to test algorithm resilience under tight constraints.
    """
    tight_tasks = []
    for t in base_tasks:
        orig_slack = t.spec.deadline_min - (t.spec.arrival_time_min + t.spec.duration_min)
        tight_slack = max(5.0, orig_slack * 0.4)
        new_deadline = t.spec.arrival_time_min + t.spec.duration_min + tight_slack

        spec = TaskSpec(
            task_id=t.spec.task_id,
            job_type=t.spec.job_type,
            arrival_time_min=t.spec.arrival_time_min,
            duration_min=t.spec.duration_min,
            deadline_min=round(new_deadline, 1),
            cpu_cores=t.spec.cpu_cores,
            memory_gb=t.spec.memory_gb,
            gpu_units=t.spec.gpu_units,
            priority=t.spec.priority,
            data_size_gb=t.spec.data_size_gb
        )
        tight_tasks.append(WorkloadTask(spec))
    return tight_tasks


def create_scenario_heavy_load(base_tasks: List[WorkloadTask]) -> List[WorkloadTask]:
    """
    Scenario C: Flash Crowd / High Utilization.
    Compresses task arrival intervals by 2.0x, doubling cluster load.
    """
    heavy_tasks = []
    for t in base_tasks:
        compressed_arrival = round(t.spec.arrival_time_min * 0.5, 1)
        orig_slack = t.spec.deadline_min - (t.spec.arrival_time_min + t.spec.duration_min)
        compressed_deadline = round(compressed_arrival + t.spec.duration_min + orig_slack, 1)

        spec = TaskSpec(
            task_id=t.spec.task_id,
            job_type=t.spec.job_type,
            arrival_time_min=compressed_arrival,
            duration_min=t.spec.duration_min,
            deadline_min=compressed_deadline,
            cpu_cores=t.spec.cpu_cores,
            memory_gb=t.spec.memory_gb,
            gpu_units=t.spec.gpu_units,
            priority=t.spec.priority,
            data_size_gb=t.spec.data_size_gb
        )
        heavy_tasks.append(WorkloadTask(spec))
    return heavy_tasks
