"""
Compute Node abstraction with realistic power modeling and resource allocation tracking.
"""

from typing import List, Dict, Any, Optional
from .models import NodeSpec, Region


class ComputeNode:
    """
    Represents a physical or virtual compute server in a specific datacenter region.
    Models non-linear power consumption curves calibrated from SPECpower benchmarks.
    """

    def __init__(self, spec: NodeSpec):
        self.spec = spec
        self.node_id = spec.node_id
        self.region = spec.region

        # Resource limits
        self.total_cpu = spec.total_cpu_cores
        self.total_ram = spec.total_memory_gb
        self.total_gpu = spec.total_gpu_units

        # Resource allocations
        self.allocated_cpu = 0
        self.allocated_ram = 0
        self.allocated_gpu = 0
        self.active_task_ids: List[str] = []

        # Energy & Carbon accumulators
        self.cumulative_energy_kwh = 0.0
        self.cumulative_carbon_gco2 = 0.0

    @property
    def available_cpu(self) -> int:
        return self.total_cpu - self.allocated_cpu

    @property
    def available_ram(self) -> int:
        return self.total_ram - self.allocated_ram

    @property
    def available_gpu(self) -> int:
        return self.total_gpu - self.allocated_gpu

    @property
    def cpu_utilization(self) -> float:
        return self.allocated_cpu / self.total_cpu if self.total_cpu > 0 else 0.0

    @property
    def gpu_utilization(self) -> float:
        return self.allocated_gpu / self.total_gpu if self.total_gpu > 0 else 0.0

    def can_accommodate(self, cpu: int, ram: int, gpu: int) -> bool:
        """Checks whether the node has sufficient remaining capacity."""
        return (self.available_cpu >= cpu and
                self.available_ram >= ram and
                self.available_gpu >= gpu)

    def allocate(self, task_id: str, cpu: int, ram: int, gpu: int) -> bool:
        """Allocates resources to a task."""
        if not self.can_accommodate(cpu, ram, gpu):
            return False
        self.allocated_cpu += cpu
        self.allocated_ram += ram
        self.allocated_gpu += gpu
        self.active_task_ids.append(task_id)
        return True

    def release(self, task_id: str, cpu: int, ram: int, gpu: int) -> None:
        """Releases resources when a task completes."""
        if task_id in self.active_task_ids:
            self.active_task_ids.remove(task_id)
        self.allocated_cpu = max(0, self.allocated_cpu - cpu)
        self.allocated_ram = max(0, self.allocated_ram - ram)
        self.allocated_gpu = max(0, self.allocated_gpu - gpu)

    def get_instantaneous_power_watts(self) -> float:
        """
        Calculates instantaneous power in Watts.
        Uses a SPECpower-calibrated polynomial curve for CPU and discrete power states for GPU.
        Multiplied by Datacenter PUE (Power Usage Effectiveness).
        """
        u_cpu = self.cpu_utilization
        # If node has no active tasks, it enters deep low-power standby state
        if u_cpu <= 0.0 and self.allocated_gpu == 0:
            return self.spec.standby_power_watts * self.spec.pue

        if u_cpu <= 0.0:
            cpu_power = self.spec.idle_power_watts
        else:
            dyn_factor = (2.0 * u_cpu - (u_cpu ** 1.4))
            cpu_power = self.spec.idle_power_watts + (self.spec.peak_power_watts - self.spec.idle_power_watts) * dyn_factor

        # GPU Power
        if self.allocated_gpu == 0:
            gpu_power = 0.0
        else:
            # Active GPUs consume baseline + dynamic power
            gpu_power = self.allocated_gpu * (
                self.spec.gpu_idle_watts + (self.spec.gpu_peak_watts - self.spec.gpu_idle_watts) * 0.90
            )

        total_it_power = cpu_power + gpu_power
        total_facility_power = total_it_power * self.spec.pue
        return total_facility_power

    def update_energy_and_carbon(self, delta_time_min: float, carbon_intensity_g_per_kwh: float) -> float:
        """
        Advances the node clock by delta_time_min, computes energy consumed (kWh)
        and operational carbon emitted (gCO2eq).
        Returns the incremental carbon emitted in gCO2eq.
        """
        power_watts = self.get_instantaneous_power_watts()
        # Convert Watts * minutes to kWh: (W * min / 60) / 1000
        delta_kwh = (power_watts * delta_time_min / 60.0) / 1000.0
        delta_carbon_g = delta_kwh * carbon_intensity_g_per_kwh

        self.cumulative_energy_kwh += delta_kwh
        self.cumulative_carbon_gco2 += delta_carbon_g
        return delta_carbon_g

    def reset_metrics(self):
        """Resets accumulators for new simulation runs."""
        self.cumulative_energy_kwh = 0.0
        self.cumulative_carbon_gco2 = 0.0
        self.allocated_cpu = 0
        self.allocated_ram = 0
        self.allocated_gpu = 0
        self.active_task_ids.clear()
