# Mathematical Formulation of Carbon-Aware Workload Scheduling

This document details the formal mathematical model behind **EcoSched**, formalizing the multi-objective optimization problem of geo-distributed workload scheduling under dynamic grid carbon intensity signals and SLA deadline constraints.

---

## 1. System Topology & Regional Carbon Signals

Let $\mathcal{R}$ denote the set of geo-distributed datacenter regions:
$$\mathcal{R} = \{\text{DE}, \text{SE}, \text{US\_CA}, \text{FR}\}$$

Each region $r \in \mathcal{R}$ is characterized by:
1. **Time-Varying Marginal Grid Carbon Intensity** $I_r(t)$ measured in $\text{gCO}_2\text{eq} / \text{kWh}$ at continuous simulation time $t \ge 0$.
2. **Datacenter Power Usage Effectiveness (PUE)** $\text{PUE}_r \ge 1.0$, accounting for cooling and facility power overhead.

---

## 2. Server Hardware & Dynamic Power Consumption Model

The distributed cluster contains a set of heterogeneous compute nodes $\mathcal{N}$. Each node $n \in \mathcal{N}$ belongs to a region $r(n) \in \mathcal{R}$ and is characterized by:
* $C_n$: Total CPU cores
* $M_n$: Total memory capacity ($\text{GB}$)
* $G_n$: Total GPU units
* $P_{n,\text{idle}}$: Base active power draw ($\text{Watts}$)
* $P_{n,\text{standby}}$: Deep low-power standby state wattage ($\text{Watts}$) when $u_n(t) = 0$
* $P_{n,\text{peak}}$: Maximum load power draw ($\text{Watts}$)

### Instantaneous CPU Utilization:
$$u_n(t) = \frac{\sum_{j \in \mathcal{A}_n(t)} c_j}{C_n} \in [0, 1]$$
where $\mathcal{A}_n(t)$ is the set of tasks actively running on node $n$ at time $t$, and $c_j$ is the CPU cores assigned to task $j$.

### SPECpower-Calibrated Facility Power Curve:
$$P_n(t) = \begin{cases}
P_{n,\text{standby}} \cdot \text{PUE}_{r(n)}, & \text{if } u_n(t) = 0 \text{ and } g_n(t) = 0 \\
\left[ P_{n,\text{idle}} + (P_{n,\text{peak}} - P_{n,\text{idle}}) \cdot \left(2 u_n(t) - u_n(t)^{1.4}\right) + P_{n,\text{gpu}}(t) \right] \cdot \text{PUE}_{r(n)}, & \text{otherwise}
\end{cases}$$

---

## 3. Workload Specification & Slack Window Analysis

A workload batch consists of tasks $\mathcal{J} = \{j_1, j_2, \dots, j_M\}$. Each task $j \in \mathcal{J}$ is a tuple:
$$\tau_j = \langle a_j, d_j, D_j, c_j, m_j, g_j, p_j, \delta_j \rangle$$
where:
* $a_j$: Arrival time
* $d_j$: Execution duration
* $D_j$: Hard/Soft deadline
* $c_j, m_j, g_j$: Required CPU, RAM ($\text{GB}$), and GPU units
* $p_j \in \{1, 2, 3\}$: Priority class (1 = Critical, 2 = Batch, 3 = Elastic)
* $\delta_j$: Input dataset size ($\text{GB}$)

### Slack Window Definition:
At simulation time $t$, the remaining execution slack $S_j(t)$ is:
$$S_j(t) = D_j - (t + d_j)$$

* If $S_j(t) \le \tau_{\text{crit}}$ (where $\tau_{\text{crit}} = 20\text{ min}$): Task is **SLA-Critical** and must be dispatched immediately to prevent deadline violation.
* If $S_j(t) > \tau_{\text{crit}}$: Task is **Elastic**, permitting temporal delay scheduling and spatial cross-region migration.

---

## 4. Inter-Region WAN Latency & Data Transfer Delay

Migrating task $j$ with input data size $\delta_j$ ($\text{GB}$) from origin region $r_{\text{src}}$ to target region $r_{\text{dst}}$ incurs network transfer delay $\Delta t_{\text{net}}(r_{\text{src}}, r_{\text{dst}}, \delta_j)$:
$$\Delta t_{\text{net}} = \text{RTT}(r_{\text{src}}, r_{\text{dst}}) + \frac{\delta_j \times 8}{\text{Bandwidth}_{\text{WAN}}(r_{\text{src}}, r_{\text{dst}})} \quad [\text{converted to minutes}]$$

### Feasibility Condition:
A placement $(j, n)$ is feasible only if:
$$t + \Delta t_{\text{net}}(r_{\text{src}}, r(n), \delta_j) + d_j \le D_j$$

---

## 5. Multi-Objective Optimization Problem

The objective is to minimize total operational carbon emissions over the scheduling horizon $T$ while ensuring SLA deadline compliance:

$$\min \quad \mathcal{C}_{\text{total}} = \sum_{t=0}^{T} \sum_{n \in \mathcal{N}} \left( \frac{P_n(t) \cdot \Delta t}{60 \times 1000} \right) \cdot I_{r(n)}(t)$$

Subject to:
1. **Capacity Constraints:**
   $$\sum_{j \in \mathcal{A}_n(t)} c_j \le C_n, \quad \sum_{j \in \mathcal{A}_n(t)} m_j \le M_n, \quad \sum_{j \in \mathcal{A}_n(t)} g_j \le G_n \quad \forall n \in \mathcal{N}, \forall t$$
2. **Deadline Constraints:**
   $$\text{CompletionTime}(j) \le D_j \quad \forall j \in \mathcal{J}$$
3. **Non-Preemptive Execution:**
   Once task $j$ starts on node $n$, it runs uninterrupted for duration $d_j$.

### CarbonSlack Multi-Objective Placement Score:
For candidate task $j$ on node $n$ at time $t$:
$$\mathcal{F}(j, n, t) = w_c \cdot \frac{\hat{\mathcal{C}}(j, n)}{\mathcal{C}_{\text{scale}}} + w_e \cdot \frac{\Delta P_n}{P_{\text{scale}}} + w_s \cdot \left(1 - \frac{S_j(t)}{D_j - a_j}\right) + w_{\text{wan}} \cdot \Delta t_{\text{net}}$$

where $w_c = 0.70$, $w_e = 0.15$, $w_s = 0.15$, $w_{\text{wan}} = 0.05$.
Node $n^* = \arg\min_n \mathcal{F}(j, n, t)$ is selected for assignment.
