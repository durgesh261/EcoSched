"""
Unit tests validating end-to-end discrete-event simulation engine and telemetry.
"""

import pytest
from src.core.models import TaskSpec
from src.core.task import WorkloadTask
from src.core.cluster import DistributedCluster
from src.core.grid import CarbonGridProvider
from src.simulator.engine import SimulationEngine
from src.schedulers.fifo import FIFOScheduler
from src.schedulers.carbon_slack import CarbonSlackScheduler


def test_simulation_engine_end_to_end():
    cluster = DistributedCluster.create_default_heterogeneous_cluster()
    grid_provider = CarbonGridProvider()

    # Create 15 small tasks
    tasks = [
        WorkloadTask(TaskSpec(
            task_id=f"sim_task_{i:02d}",
            arrival_time_min=float(i * 10),
            duration_min=30.0,
            deadline_min=float(i * 10 + 120),
            cpu_cores=8,
            memory_gb=32,
            gpu_units=0
        )) for i in range(15)
    ]

    scheduler = CarbonSlackScheduler()
    engine = SimulationEngine(
        cluster=cluster,
        grid_provider=grid_provider,
        tasks=tasks,
        scheduler=scheduler,
        step_minutes=5.0
    )

    summary = engine.run(max_duration_hours=24.0)

    assert summary.total_tasks == 15
    assert summary.completed_tasks == 15
    assert summary.total_energy_kwh > 0.0
    assert summary.total_carbon_kg > 0.0
    assert summary.deadline_compliance_pct >= 90.0
    assert len(engine.metrics_collector.time_series_records) > 0
