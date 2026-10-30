# EcoSched: Carbon-Aware Dynamic Workload Orchestrator for Distributed Heterogeneous Compute Clusters

[![Python 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Build Status](https://img.shields.io/badge/tests-5%20passed-brightgreen.svg)]()
[![Code Style: Academic](https://img.shields.io/badge/code%20style-IEEE%2FACM%20Research-purple.svg)]()
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)]()

> **EcoSched** is an open-source, discrete-event simulation framework and algorithmic orchestrator designed to minimize the operational carbon footprint of geo-distributed, heterogeneous compute clusters while strictly enforcing Service-Level Agreement (SLA) deadlines.

---

## 🌍 Motivation & The European Context

With the accelerating growth of compute-intensive AI workloads and distributed cloud computing, data centers now consume over 2.5% of global electricity. In the European Union, under the **EU Green Deal** and Germany's **Energiewende**, cloud operators face strict regulatory and environmental mandates to decarbonize digital infrastructure.

However, existing cloud orchestrators (e.g., standard Kubernetes, Slurm) are fundamentally **carbon-blind**: they route tasks strictly based on local queue lengths or server packing heuristics. Meanwhile, regional electrical grid carbon intensity varies by more than **$10\times$** across European regions (e.g., Sweden's hydro-nuclear baseload of $\sim 35\text{ gCO}_2/\text{kWh}$ vs. Germany's fluctuating coal/gas mix of $\sim 380\text{ gCO}_2/\text{kWh}$), exhibiting predictable diurnal renewable peaks (solar at midday, wind at night).

**EcoSched** bridges this gap by introducing **Dynamic Slack-Aware Workload Shifting**, combining:
1. **Spatial Shifting:** Opportunistically migrating flexible batch workloads to regions with abundant renewable energy, amortized over WAN data transfer delays.
2. **Temporal Shifting (Green Delay Scheduling):** Holding elastic tasks in queue during regional grid emission spikes to exploit forecasted low-carbon valleys within the task's allowable slack window.

---

## 🏛️ System Architecture

```
                          ┌─────────────────────────────────────┐
                          │     Workload Arrival Stream        │
                          │   (Batch, ETL, AI Training, HPC)    │
                          └──────────────────┬──────────────────┘
                                             │
                                             ▼
                          ┌─────────────────────────────────────┐
                          │      Slack-Window Triage Engine     │
                          │       S_j(t) = D_j - (t + d_j)      │
                          └───────┬─────────────────────┬───────┘
                                  │                     │
                     S_j(t) <= tau_crit            S_j(t) > tau_crit
                   (SLA-Critical Workload)       (Elastic/Delayable)
                                  │                     │
                                  │                     ▼
                                  │     ┌───────────────────────────────┐
                                  │     │  Temporal Green Window Search │
                                  │     │  (Forecasted Carbon Valleys)  │
                                  │     └───────────────┬───────────────┘
                                  │                     │
                                  ▼                     ▼
                  ┌─────────────────────────────────────────────────────┐
                  │   Multi-Objective Spatial Scoring & Placement       │
                  │   min F(j, n, t) = w_c*Carbon + w_e*Power + w_s*Slack │
                  └──────────────────────────┬──────────────────────────┘
                                             │
                                             ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────┐
 │                     Geo-Distributed Heterogeneous Cluster                           │
 │                                                                                     │
 │  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐   ┌──────────────┐ │
 │  │  Germany (DE)   │   │   Sweden (SE)   │   │California (US)  │   │ France (FR)  │ │
 │  │ 8 Hetero Nodes  │   │ 8 Hetero Nodes  │   │ 6 Hetero Nodes  │   │5 Hetero Nodes│ │
 │  │ PUE = 1.22      │   │ PUE = 1.12      │   │ PUE = 1.25      │   │ PUE = 1.18   │ │
 │  └─────────────────┘   └─────────────────┘   └─────────────────┘   └──────────────┘ │
 │           ▲                     ▲                     ▲                   ▲         │
 │           └─────────────────────┴──────────┬──────────┴───────────────────┘         │
 │                                            │                                        │
 │                                 Inter-Region WAN Matrix                             │
 │                              (RTT latency + WAN Bandwidth)                          │
 └─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Empirical Evaluation & Key Results

Evaluated across 600 heterogeneous batch and AI training workloads over 72 simulation hours using real-world **ENTSO-E (Europe)** and **CAISO (California)** grid carbon traces:

### Comprehensive Benchmark Matrix

| Scenario | Scheduler | Total Carbon ($\text{kg CO}_2\text{eq}$) | Carbon Reduction vs Baseline | SLA Compliance (%) | Mean Turnaround ($\text{min}$) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Nominal Workload** | FIFO (Kubernetes Default) | 277.06 | +0.00% | 91.50% | 326.6 |
| | Energy-Greedy Consolidation | 247.22 | +10.77% | 94.00% | 322.1 |
| | Spatial-Only Carbon | 251.51 | +9.22% | **100.00%** | 264.1 |
| | **CarbonSlack (Novel Policy)** | **242.83** | **+12.35%** | **100.00%** | **245.8** |
| **Tight SLA Deadlines** | FIFO (Kubernetes Default) | 277.06 | +0.00% | 81.50% | 326.6 |
| | Energy-Greedy Consolidation | 247.22 | +10.77% | 90.00% | 322.1 |
| | Spatial-Only Carbon | **225.37** | **+18.66%** | **100.00%** | **190.4** |
| | **CarbonSlack (Novel Policy)** | 230.54 | +16.79% | **100.00%** | 192.0 |
| **Heavy Contention** | FIFO (Kubernetes Default) | 275.96 | +0.00% | 81.00% | 541.1 |
| | Energy-Greedy Consolidation | 244.82 | +11.28% | 82.67% | 563.0 |
| | Spatial-Only Carbon | **180.24** | **+34.69%** | **100.00%** | **264.1** |
| | **CarbonSlack (Novel Policy)** | 183.96 | +33.34% | **100.00%** | 289.4 |

### Visual Results

#### 1. Pareto Efficiency (Carbon Footprint vs. Latency)
CarbonSlack strictly dominates traditional schedulers in both operational carbon abatement and task turnaround time:
![Pareto Frontier](figures/fig4_pareto_carbon_latency.png)

#### 2. Multi-Region Grid Carbon Dynamics (ENTSO-E & CAISO)
Capturing the diurnal renewable volatility and regional carbon intensity disparities:
![Grid Carbon Dynamics](figures/fig1_grid_carbon_traces.png)

#### 3. Ablation Study: Carbon Reduction & SLA Guarantee
Ablation analysis demonstrating that CarbonSlack guarantees **100% SLA compliance** even under tight deadlines and cluster saturation where FIFO violates up to 19% of deadlines:
![Ablation Study](figures/fig3_ablation_carbon_savings.png)

---

## ⚡ Quickstart

### Prerequisites
* Python 3.10+ (tested on Python 3.11, 3.12, 3.14)
* Git

### Local Installation
```bash
# 1. Clone repository
git clone https://github.com/durgesh261/EcoSched.git
cd EcoSched

# 2. Create virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
pip install -e .
```

### Running Unit Tests
```bash
pytest -v
```

### Executing Full Benchmark & Generating Figures
```bash
python scripts/run_experiments.py
```
All publication-quality plots (PNG, 300 DPI) are automatically exported to `output/figures/` and tabular summaries to `output/results/`.

---

## 🐳 Docker Reproducibility

For one-command, containerized verification:
```bash
# Build Docker image
docker build -t ecosched:latest .

# Run benchmark suite inside container
docker run --rm -v $(pwd)/output:/app/output ecosched:latest
```

---

## 📐 Mathematical Formulation

For the complete formalization including:
* Non-linear SPECpower server polynomial curves
* Dynamic PUE facility multipliers
* Slack-window integral optimization
* WAN network latency matrix

Please refer to [`docs/MATHEMATICAL_FORMULATION.md`](docs/MATHEMATICAL_FORMULATION.md).

---

## 📄 License

This project is licensed under the MIT License - see the [`LICENSE`](LICENSE) file for details.

---

## 📑 Citation & Academic Attribution

If you use EcoSched in your academic research, please cite:

```bibtex
@article{kanjariya2026ecosched,
  title={EcoSched: Carbon-Aware Workload Orchestration and Dynamic Slack Shifting for Geo-Distributed Compute Clusters},
  author={Kanjariya, Durgesh},
  year={2026},
  journal={Technical Report and Simulation Framework},
  url={https://github.com/durgesh261/EcoSched}
}
```
