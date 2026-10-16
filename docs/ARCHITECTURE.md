# EcoSched Architecture & Software Engineering Specification

This document provides a detailed breakdown of the software modules, interfaces, and discrete-event simulation pipeline within **EcoSched**.

---

## 1. Directory & Package Layout

```
EcoSched/
├── .gitignore                      # Git exclusion rules
├── README.md                       # Repository overview, badges, visual results
├── pyproject.toml                  # Modern PEP 621 packaging metadata
├── requirements.txt                # Python runtime dependencies
├── Dockerfile                      # Containerized reproduction environment
├── LICENSE                         # Open-source MIT License
├── data/
│   └── traces/
│       ├── grid_carbon/            # Multi-region ENTSO-E / CAISO carbon intensity traces
│       └── workloads/              # Synthetic cluster batch & AI workload specifications
├── src/
│   ├── core/
│   │   ├── models.py               # Pydantic schemas (TaskSpec, NodeSpec, Region, TaskState)
│   │   ├── node.py                 # ComputeNode with SPECpower non-linear curves & standby states
│   │   ├── task.py                 # WorkloadTask with dynamic slack-window tracking
│   │   ├── grid.py                 # CarbonGridProvider with vectorized NumPy lookups & forecasting
│   │   └── cluster.py              # DistributedCluster topology and inter-region WAN latency matrix
│   ├── simulator/
│   │   ├── engine.py               # Discrete-Event Simulation (DES) core clock loop
│   │   └── metrics.py              # Telemetry collectors and SimulationSummary schemas
│   ├── schedulers/
│   │   ├── base.py                 # BaseScheduler abstract interface
│   │   ├── fifo.py                 # Baseline 1: Standard First-In-First-Out (Kubernetes default)
│   │   ├── energy_greedy.py        # Baseline 2: Power-minimizing server consolidation
│   │   ├── spatial_only.py         # Ablation: Real-time spatial migration without temporal delay
│   │   └── carbon_slack.py         # Novel Policy: Dynamic spatial & temporal slack shifting
│   ├── benchmark/
│   │   ├── scenarios.py            # Stress test scenario definitions (Nominal, Tight SLA, Contention)
│   │   └── runner.py               # Automated evaluation orchestrator
│   └── visualization/
│       └── plotter.py              # IEEE/ACM styled publication figure generator (300 DPI)
├── scripts/
│   ├── generate_sample_data.py     # Deterministic trace dataset generator
│   └── run_experiments.py          # Master benchmark execution and figure generation script
├── tests/
│   ├── test_models.py              # Unit tests for power curves, slack time, and cluster latency
│   ├── test_schedulers.py          # Unit tests for scheduler interface and physical constraints
│   └── test_simulator.py           # End-to-end integration test of DES engine
└── docs/
    ├── ARCHITECTURE.md             # This document
    ├── MATHEMATICAL_FORMULATION.md # Full analytical equations and optimization formulation
    └── BENCHMARK_RESULTS.md        # Detailed quantitative evaluation tables
```

---

## 2. Core Class Interfaces

### `ComputeNode` (`src/core/node.py`)
* `can_accommodate(cpu, ram, gpu) -> bool`
* `allocate(task_id, cpu, ram, gpu) -> bool`
* `release(task_id, cpu, ram, gpu) -> None`
* `get_instantaneous_power_watts() -> float`: Evaluates whether node is in sleep standby ($15\text{ W}$) or active SPECpower curve ($P_{\text{idle}} + \Delta P \cdot (2u - u^{1.4})$) multiplied by datacenter PUE.
* `update_energy_and_carbon(delta_time_min, carbon_intensity) -> float`

### `WorkloadTask` (`src/core/task.py`)
* `slack_time(current_time) -> float`: Evaluates $D_j - (t + d_j)$.
* `is_critical(current_time, safety_margin) -> bool`: Identifies whether immediate scheduling is required.
* `progress(delta_time_min, current_time) -> bool`: Advances compute countdown, deducts network transit latency, and transitions state to `COMPLETED` or `MISSED_DEADLINE`.

### `CarbonGridProvider` (`src/core/grid.py`)
* `get_intensity(region, time_min) -> float`: Sub-microsecond linear interpolation over calibrated historical grid traces.
* `find_optimal_green_window(region, start_time, window, duration) -> Tuple[float, float]`: Evaluates moving-average carbon minimum within task's slack window.

### `BaseScheduler` (`src/schedulers/base.py`)
* `schedule(current_time_min, queued_tasks, cluster, grid_provider) -> List[Tuple[WorkloadTask, ComputeNode, float]]`
