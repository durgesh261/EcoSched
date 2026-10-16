"""
Discrete-Event Simulation (DES) Engine orchestrating tasks, nodes, grid signals, and scheduling policies.
"""

from typing import List, Dict, Optional, Tuple, Any
from copy import deepcopy
import pandas as pd
from ..core.cluster import DistributedCluster
from ..core.grid import CarbonGridProvider
from ..core.task import WorkloadTask
from ..core.models import TaskState
from .metrics import MetricsCollector, SimulationSummary


class SimulationEngine:
    """
    Execution engine simulating workload execution, dynamic carbon intensity updates,
    hardware energy curves, and SLA tracking across geo-distributed regions.
    """

    def __init__(
        self,
        cluster: DistributedCluster,
        grid_provider: CarbonGridProvider,
        tasks: List[WorkloadTask],
        scheduler: Any,
        step_minutes: float = 5.0
    ):
        self.cluster = cluster
        self.grid_provider = grid_provider
        self.tasks = tasks
        self.scheduler = scheduler
        self.step_minutes = step_minutes

        self.current_time_min = 0.0
        self.queued_tasks: List[WorkloadTask] = []
        self.running_tasks: List[WorkloadTask] = []
        self.completed_tasks: List[WorkloadTask] = []

        self.metrics_collector = MetricsCollector(scheduler_name=scheduler.name)

    def run(self, max_duration_hours: Optional[float] = None) -> SimulationSummary:
        """
        Executes the discrete-time simulation until all tasks complete or max duration is hit.
        """
        # Reset all states
        self.cluster.reset()
        for t in self.tasks:
            t.reset()

        self.current_time_min = 0.0
        self.queued_tasks.clear()
        self.running_tasks.clear()
        self.completed_tasks.clear()

        # Tasks to arrive
        pending_tasks = sorted(self.tasks, key=lambda x: x.arrival_time)
        next_arrival_idx = 0
        total_tasks_count = len(self.tasks)

        max_time_min = (max_duration_hours * 60.0) if max_duration_hours else 20000.0

        while self.current_time_min < max_time_min:
            # 1. Admit new arrivals
            while next_arrival_idx < total_tasks_count:
                cand = pending_tasks[next_arrival_idx]
                if cand.arrival_time <= self.current_time_min:
                    cand.state = TaskState.QUEUED
                    self.queued_tasks.append(cand)
                    next_arrival_idx += 1
                else:
                    break

            # 2. Invoke scheduler on queued tasks
            if self.queued_tasks:
                assignments = self.scheduler.schedule(
                    current_time_min=self.current_time_min,
                    queued_tasks=self.queued_tasks,
                    cluster=self.cluster,
                    grid_provider=self.grid_provider
                )

                # Process returned assignments: List of (task, target_node, transfer_delay_min)
                for task, node, delay in assignments:
                    if task in self.queued_tasks:
                        self.queued_tasks.remove(task)

                    allocated = node.allocate(task.task_id, task.cpu, task.ram, task.gpu)
                    if allocated:
                        task.mark_started(
                            current_time=self.current_time_min,
                            node_id=node.node_id,
                            region=node.region,
                            transfer_delay_min=delay
                        )
                        self.running_tasks.append(task)
                    else:
                        # Allocation failed, re-queue
                        self.queued_tasks.append(task)

            # 3. Progress currently running tasks
            finished_in_this_step = []
            for task in list(self.running_tasks):
                is_done = task.progress(self.step_minutes, self.current_time_min)
                if is_done:
                    # Release node resources
                    node = self.cluster.nodes[task.assigned_node_id]
                    node.release(task.task_id, task.cpu, task.ram, task.gpu)
                    self.running_tasks.remove(task)
                    self.completed_tasks.append(task)
                    finished_in_this_step.append(task)

            # 4. Update energy and carbon across all cluster nodes
            step_total_energy = 0.0
            step_total_carbon = 0.0

            for node in self.cluster.nodes.values():
                ci = self.grid_provider.get_intensity(node.region, self.current_time_min)
                d_carbon = node.update_energy_and_carbon(self.step_minutes, ci)
                step_total_carbon += d_carbon

                # Instantaneous energy in kWh
                power_w = node.get_instantaneous_power_watts()
                step_energy = (power_w * self.step_minutes / 60.0) / 1000.0
                step_total_energy += step_energy

            # 5. Record telemetry
            self.metrics_collector.record_step(
                time_min=self.current_time_min,
                cluster=self.cluster,
                step_energy_kwh=step_total_energy,
                step_carbon_g=step_total_carbon,
                running_tasks_count=len(self.running_tasks),
                queued_tasks_count=len(self.queued_tasks)
            )

            # 6. Check termination condition
            if len(self.completed_tasks) == total_tasks_count:
                break

            # Advance clock
            self.current_time_min += self.step_minutes

        return self.metrics_collector.generate_summary(
            all_tasks=self.tasks,
            cluster=self.cluster,
            sim_time_min=self.current_time_min
        )
