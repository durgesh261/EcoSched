"""
Data models and Enums for the EcoSched orchestrator.
"""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class TaskState(str, Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    MISSED_DEADLINE = "MISSED_DEADLINE"


class Region(str, Enum):
    DE = "DE"       # Germany (High renewables fluctuation, coal/gas peakers)
    SE = "SE"       # Sweden (Hydro/nuclear baseload, ultra-clean)
    US_CA = "US_CA" # California (Strong solar duck curve)
    FR = "FR"       # France (Nuclear baseload)


class TaskSpec(BaseModel):
    task_id: str
    job_type: str = "batch"
    arrival_time_min: float
    duration_min: float
    deadline_min: float
    cpu_cores: int = Field(ge=1)
    memory_gb: int = Field(ge=1)
    gpu_units: int = Field(default=0, ge=0)
    priority: int = Field(default=2, ge=1, le=3) # 1: Critical, 2: Moderate, 3: Deferrable
    data_size_gb: float = Field(default=5.0, ge=0.0)


class NodeSpec(BaseModel):
    node_id: str
    region: Region
    total_cpu_cores: int = 64
    total_memory_gb: int = 256
    total_gpu_units: int = 4
    idle_power_watts: float = 110.0
    standby_power_watts: float = 15.0 # Low-power sleep state when 0 active tasks
    peak_power_watts: float = 450.0
    gpu_idle_watts: float = 25.0
    gpu_peak_watts: float = 300.0
    pue: float = Field(default=1.2, description="Power Usage Effectiveness of the datacenter")
