"""
WorkloadTask abstraction tracking lifecycle, execution progress, slack time, and SLA metrics.
"""

from typing import Optional
from .models import TaskSpec, TaskState, Region


class WorkloadTask:
    """
    Represents an active compute task with deadline slack tracking and SLA state machine.
    """

    def __init__(self, spec: TaskSpec):
        self.spec = spec
        self.task_id = spec.task_id
        self.job_type = spec.job_type
        self.arrival_time = spec.arrival_time_min
        self.duration = spec.duration_min
        self.deadline = spec.deadline_min
        self.cpu = spec.cpu_cores
        self.ram = spec.memory_gb
        self.gpu = spec.gpu_units
        self.priority = spec.priority
        self.data_size_gb = spec.data_size_gb

        # Runtime state
        self.state = TaskState.PENDING
        self.assigned_node_id: Optional[str] = None
        self.assigned_region: Optional[Region] = None

        self.start_time: Optional[float] = None
        self.completion_time: Optional[float] = None
        self.remaining_duration: float = spec.duration_min
        self.network_transfer_delay_min: float = 0.0

    def slack_time(self, current_time: float) -> float:
        """
        Calculates remaining slack time before the task must be started to meet its deadline:
        S(t) = Deadline - (CurrentTime + RemainingDuration)
        A negative slack implies the task will inevitably miss its deadline.
        """
        return self.deadline - (current_time + self.remaining_duration)

    def slack_ratio(self, current_time: float) -> float:
        """Normalized slack relative to total execution duration."""
        if self.duration <= 0:
            return 0.0
        return self.slack_time(current_time) / self.duration

    def is_critical(self, current_time: float, safety_margin_min: float = 10.0) -> bool:
        """Returns True if task must be scheduled immediately to guarantee SLA."""
        return self.slack_time(current_time) <= safety_margin_min

    def mark_started(self, current_time: float, node_id: str, region: Region, transfer_delay_min: float = 0.0):
        self.state = TaskState.RUNNING
        self.start_time = current_time + transfer_delay_min
        self.assigned_node_id = node_id
        self.assigned_region = region
        self.network_transfer_delay_min = transfer_delay_min

    def progress(self, delta_time_min: float, current_time: float) -> bool:
        """
        Advances task execution. Returns True if task finished in this step.
        """
        if self.state != TaskState.RUNNING:
            return False

        # If data is currently in transit across regions, count down transfer delay first
        if self.network_transfer_delay_min > 0:
            if delta_time_min <= self.network_transfer_delay_min:
                self.network_transfer_delay_min -= delta_time_min
                return False
            else:
                delta_time_min -= self.network_transfer_delay_min
                self.network_transfer_delay_min = 0.0

        self.remaining_duration = max(0.0, self.remaining_duration - delta_time_min)

        if self.remaining_duration <= 0.0:
            self.completion_time = current_time
            if self.completion_time <= self.deadline:
                self.state = TaskState.COMPLETED
            else:
                self.state = TaskState.MISSED_DEADLINE
            return True

        # Check if deadline passed while still running
        if current_time > self.deadline and self.state == TaskState.RUNNING:
            # We allow it to continue running until completion, but flag SLA miss
            pass

        return False

    @property
    def waiting_time(self) -> float:
        """Time spent waiting in queue before execution began."""
        if self.start_time is None:
            return 0.0
        return max(0.0, self.start_time - self.arrival_time)

    @property
    def turnaround_time(self) -> float:
        """Total time elapsed from submission to completion."""
        if self.completion_time is None:
            return 0.0
        return max(0.0, self.completion_time - self.arrival_time)

    @property
    def deadline_missed(self) -> bool:
        """Whether the task finished after its deadline."""
        if self.completion_time is None:
            return False
        return self.completion_time > self.deadline

    def reset(self):
        """Resets runtime state for new simulation iteration."""
        self.state = TaskState.PENDING
        self.assigned_node_id = None
        self.assigned_region = None
        self.start_time = None
        self.completion_time = None
        self.remaining_duration = self.duration
        self.network_transfer_delay_min = 0.0
