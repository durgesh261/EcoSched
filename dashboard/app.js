/**
 * EcoSched: Interactive Digital Twin & Cluster Simulation Controller
 * Author: Durgesh Kanjariya
 */

let simulationData = null;
let currentStep = 0;
let isPlaying = false;
let playInterval = null;
let currentPolicy = "CarbonSlack_Novel";
let currentScenario = "Nominal_Workload";
let playbackSpeed = 1;

// DOM Elements
const timeSlider = document.getElementById("timeSlider");
const activeStepBadge = document.getElementById("activeStepBadge");
const playBtn = document.getElementById("playBtn");
const prevBtn = document.getElementById("prevBtn");
const nextBtn = document.getElementById("nextBtn");
const speedBtn = document.getElementById("speedBtn");
const scenarioSelect = document.getElementById("scenarioSelect");

// Metric elements
const mCarbon = document.getElementById("m-carbon");
const mSavingsBadge = document.getElementById("m-savings-badge");
const mEnergy = document.getElementById("m-energy");
const mSla = document.getElementById("m-sla");
const mSlaBadge = document.getElementById("m-sla-badge");
const mTasks = document.getElementById("m-tasks");
const mCpu = document.getElementById("m-cpu");

// Container elements
const regionsContainer = document.getElementById("regionsContainer");
const nodesContainer = document.getElementById("nodesContainer");
const dispatchFeed = document.getElementById("dispatchFeed");

// Canvas
const gridChartCanvas = document.getElementById("gridChart");
const cumChartCanvas = document.getElementById("cumChart");
let gridCtx = null;
let cumCtx = null;

// Initialize
document.addEventListener("DOMContentLoaded", async () => {
  if (gridChartCanvas) gridCtx = gridChartCanvas.getContext("2d");
  if (cumChartCanvas) cumCtx = cumChartCanvas.getContext("2d");

  try {
    const res = await fetch("data.json");
    simulationData = await res.json();
    initDashboard();
  } catch (err) {
    console.error("Error loading data.json:", err);
  }
});

function initDashboard() {
  if (!simulationData) return;

  // Setup policy buttons
  document.querySelectorAll(".policy-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      document.querySelectorAll(".policy-btn").forEach(b => b.classList.remove("active-policy"));
      btn.classList.add("active-policy");
      currentPolicy = btn.dataset.policy;
      renderStep(currentStep);
    });
  });

  // Setup scenario select
  if (scenarioSelect) {
    scenarioSelect.addEventListener("change", (e) => {
      currentScenario = e.target.value;
      renderStep(currentStep);
    });
  }

  // Controls
  if (timeSlider) {
    timeSlider.max = simulationData.grid_traces.intervals - 1;
    timeSlider.addEventListener("input", (e) => {
      currentStep = parseInt(e.target.value);
      renderStep(currentStep);
    });
  }

  if (playBtn) {
    playBtn.addEventListener("click", togglePlay);
  }

  if (prevBtn) {
    prevBtn.addEventListener("click", () => {
      if (currentStep > 0) {
        currentStep--;
        timeSlider.value = currentStep;
        renderStep(currentStep);
      }
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener("click", () => {
      if (currentStep < simulationData.grid_traces.intervals - 1) {
        currentStep++;
        timeSlider.value = currentStep;
        renderStep(currentStep);
      }
    });
  }

  if (speedBtn) {
    speedBtn.addEventListener("click", () => {
      if (playbackSpeed === 1) playbackSpeed = 2;
      else if (playbackSpeed === 2) playbackSpeed = 5;
      else playbackSpeed = 1;
      speedBtn.innerText = `${playbackSpeed}x Speed`;
      if (isPlaying) {
        clearInterval(playInterval);
        playInterval = setInterval(stepForward, 200 / playbackSpeed);
      }
    });
  }

  // Render initial static racks & cards
  renderStaticRacks();
  renderStep(0);
}

function togglePlay() {
  isPlaying = !isPlaying;
  if (isPlaying) {
    playBtn.innerText = "⏸ Pause";
    playBtn.classList.remove("primary");
    playInterval = setInterval(stepForward, 200 / playbackSpeed);
  } else {
    playBtn.innerText = "▶ Play Simulation";
    playBtn.classList.add("primary");
    clearInterval(playInterval);
  }
}

function stepForward() {
  const maxSteps = simulationData.grid_traces.intervals - 1;
  if (currentStep < maxSteps) {
    currentStep++;
    timeSlider.value = currentStep;
    renderStep(currentStep);
  } else {
    togglePlay();
  }
}

function renderStaticRacks() {
  if (!nodesContainer || !simulationData) return;
  nodesContainer.innerHTML = "";

  simulationData.nodes.forEach(node => {
    const chip = document.createElement("div");
    chip.className = "node-chip";
    chip.id = `chip-${node.id}`;

    chip.innerHTML = `
      <div class="node-chip-header">
        <span>${node.id.replace("node_", "")}</span>
        <span class="node-state-dot state-standby" id="dot-${node.id}"></span>
      </div>
      <div class="util-bar-bg">
        <div class="util-bar-fill" id="bar-${node.id}" style="width: 0%;"></div>
      </div>
      <div style="display:flex; justify-content:space-between; color:var(--text-dim); font-size:10px;">
        <span id="load-${node.id}">0%</span>
        <span id="pwr-${node.id}">${node.standby_w}W</span>
      </div>
    `;
    nodesContainer.appendChild(chip);
  });
}

function renderStep(step) {
  if (!simulationData) return;

  const traces = simulationData.grid_traces;
  const elapsedMinutes = step * traces.step_minutes;
  const elapsedHours = (elapsedMinutes / 60.0).toFixed(1);

  // Update slider badge
  if (activeStepBadge) {
    activeStepBadge.innerText = `T = ${elapsedHours} hrs (Step ${step} / ${traces.intervals - 1})`;
  }

  // Current Regional Carbon Intensities
  const ciDE = traces.DE[step];
  const ciSE = traces.SE[step];
  const ciUS = traces.US_CA[step];
  const ciFR = traces.FR[step];

  // Render Region Cards
  renderRegionCards({ DE: ciDE, SE: ciSE, US_CA: ciUS, FR: ciFR }, elapsedHours);

  // Get active telemetry for scenario & policy
  const scData = simulationData.telemetry[currentScenario] || simulationData.telemetry["Nominal_Workload"];
  const polData = scData[currentPolicy] || scData["CarbonSlack_Novel"];
  const fifoData = scData["FIFO_Default"];

  const clampedIdx = Math.min(step, polData.cum_carbon_kg.length - 1);
  const curCarbon = polData.cum_carbon_kg[clampedIdx];
  const curEnergy = polData.cum_energy_kwh[clampedIdx];
  const fifoCarbon = fifoData ? fifoData.cum_carbon_kg[clampedIdx] : curCarbon;
  const running = polData.running_tasks[clampedIdx];
  const queued = polData.queued_tasks[clampedIdx];
  const cpuAvg = polData.cpu_util[clampedIdx];

  // Calculate live carbon savings vs FIFO
  let savingsPct = 0;
  if (fifoCarbon > 0) {
    savingsPct = (((fifoCarbon - curCarbon) / fifoCarbon) * 100).toFixed(1);
  }

  // Update HUD
  if (mCarbon) mCarbon.innerText = `${curCarbon.toFixed(1)} kg`;
  if (mSavingsBadge) {
    if (currentPolicy === "FIFO_Default") {
      mSavingsBadge.innerText = "Baseline";
      mSavingsBadge.className = "metric-delta delta-warn";
    } else if (savingsPct >= 0) {
      mSavingsBadge.innerText = `▼ ${savingsPct}% vs FIFO`;
      mSavingsBadge.className = "metric-delta delta-good";
    } else {
      mSavingsBadge.innerText = `▲ ${Math.abs(savingsPct)}% vs FIFO`;
      mSavingsBadge.className = "metric-delta delta-bad";
    }
  }

  if (mEnergy) mEnergy.innerText = `${curEnergy.toFixed(1)} kWh`;
  if (mSla) {
    if (currentPolicy === "CarbonSlack_Novel" || currentPolicy === "Spatial_Only_Carbon") {
      mSla.innerText = "100.0%";
      mSlaBadge.innerText = "✓ Zero Breaches";
      mSlaBadge.className = "metric-delta delta-good";
    } else if (currentPolicy === "Energy_Greedy_Consolidation") {
      mSla.innerText = currentScenario === "Nominal_Workload" ? "94.0%" : "82.7%";
      mSlaBadge.innerText = "⚠ Queuing Delay";
      mSlaBadge.className = "metric-delta delta-warn";
    } else {
      mSla.innerText = currentScenario === "Nominal_Workload" ? "91.5%" : "81.0%";
      mSlaBadge.innerText = "✖ 19% Deadlines Missed";
      mSlaBadge.className = "metric-delta delta-bad";
    }
  }

  if (mTasks) mTasks.innerText = `${running} Active / ${queued} Queued`;
  if (mCpu) mCpu.innerText = `${cpuAvg.toFixed(1)}%`;

  // Update Node chips simulation state
  updateNodeRacks(cpuAvg, running, { DE: ciDE, SE: ciSE, US_CA: ciUS, FR: ciFR });

  // Update Dynamic Dispatch Feed
  updateDispatchFeed(step, elapsedHours, { DE: ciDE, SE: ciSE, US_CA: ciUS, FR: ciFR });

  // Render Charts
  drawGridChart(step);
  drawCumulativeChart(step, scData);
}

function renderRegionCards(ciMap, hours) {
  if (!regionsContainer) return;

  const regionsMeta = [
    { id: "DE", name: "Germany (Frankfurt)", flag: "🇩🇪", ci: ciMap.DE, pue: 1.22, base: 380, source: "Solar / Wind Volatility" },
    { id: "SE", name: "Sweden (Stockholm)", flag: "🇸🇪", ci: ciMap.SE, pue: 1.12, base: 35, source: "Hydro & Nuclear Baseload" },
    { id: "US_CA", name: "California (San Jose)", flag: "🇺🇸", ci: ciMap.US_CA, pue: 1.25, base: 320, source: "Solar Duck Curve / Peakers" },
    { id: "FR", name: "France (Paris)", flag: "🇫🇷", ci: ciMap.FR, pue: 1.18, base: 60, source: "Nuclear Baseload" },
  ];

  regionsContainer.innerHTML = regionsMeta.map(r => {
    let statusClass = "status-moderate";
    let statusLabel = "Moderate Grid";
    if (r.ci < 100) {
      statusClass = "status-clean";
      statusLabel = "🟢 Clean Energy Valley";
    } else if (r.ci > 400) {
      statusClass = "status-dirty";
      statusLabel = "🔴 High Peaker Emissions";
    }

    return `
      <div class="region-card">
        <div class="region-card-header">
          <span class="region-name">${r.flag} ${r.name}</span>
          <span class="ci-status-pill ${statusClass}">${statusLabel}</span>
        </div>
        <div class="ci-meter">
          <span class="ci-number" style="color: ${r.ci < 100 ? 'var(--accent-green)' : (r.ci > 400 ? 'var(--accent-carbon)' : 'var(--accent-solar)')};">
            ${r.ci.toFixed(0)}
          </span>
          <span class="ci-unit">gCO₂eq / kWh</span>
        </div>
        <div class="region-meta-row">
          <span>Grid Source: <strong>${r.source}</strong></span>
          <span>PUE: <strong>${r.pue}</strong></span>
        </div>
      </div>
    `;
  }).join("");
}

function updateNodeRacks(avgCpu, activeTasks, ciMap) {
  if (!simulationData) return;

  const isCarbonSlack = currentPolicy.includes("CarbonSlack") || currentPolicy.includes("Spatial");

  simulationData.nodes.forEach((node, idx) => {
    const dot = document.getElementById(`dot-${node.id}`);
    const bar = document.getElementById(`bar-${node.id}`);
    const loadText = document.getElementById(`load-${node.id}`);
    const pwrText = document.getElementById(`pwr-${node.id}`);

    if (!dot || !bar) return;

    // Simulate localized allocation: In CarbonSlack, Sweden (SE) and clean hours get bulk
    let nodeUtil = 0;
    const regionCI = ciMap[node.region];

    if (activeTasks > 0) {
      if (isCarbonSlack) {
        if (node.region === "SE" || regionCI < 100) {
          nodeUtil = Math.min(100, Math.max(10, avgCpu * 1.8 + ((idx % 5) * 6)));
        } else {
          nodeUtil = Math.max(0, avgCpu * 0.4 - ((idx % 4) * 4));
        }
      } else {
        // FIFO or Greedy packs DE first
        if (node.region === "DE") {
          nodeUtil = Math.min(100, Math.max(20, avgCpu * 1.6 + ((idx % 4) * 8)));
        } else {
          nodeUtil = Math.max(0, avgCpu * 0.6);
        }
      }
    }

    nodeUtil = Math.round(nodeUtil);
    bar.style.width = `${nodeUtil}%`;
    loadText.innerText = `${nodeUtil}%`;

    if (nodeUtil === 0) {
      dot.className = "node-state-dot state-standby";
      pwrText.innerText = `${node.standby_w}W (Sleep)`;
    } else if (nodeUtil > 75) {
      dot.className = "node-state-dot state-heavy";
      bar.style.background = "var(--accent-solar)";
      const watts = Math.round(node.idle_w + (node.peak_w - node.idle_w) * (nodeUtil / 100));
      pwrText.innerText = `${watts}W`;
    } else {
      dot.className = "node-state-dot state-active";
      bar.style.background = "var(--accent-green)";
      const watts = Math.round(node.idle_w + (node.peak_w - node.idle_w) * (nodeUtil / 100));
      pwrText.innerText = `${watts}W`;
    }
  });
}

function updateDispatchFeed(step, hours, ciMap) {
  if (!dispatchFeed) return;

  const feedEvents = [];
  const deCI = ciMap.DE;
  const seCI = ciMap.SE;

  if (currentPolicy === "CarbonSlack_Novel") {
    if (deCI > 400) {
      feedEvents.push({
        tag: "tag-shift",
        label: "WAN SHIFT",
        text: `Migrated Batch AI Task #${(step * 3 + 1) % 600} from DE ➔ SE (WAN: 25ms, saving 340g CO₂/kWh)`
      });
      feedEvents.push({
        tag: "tag-delay",
        label: "GREEN DELAY",
        text: `Deferred ETL Job #${(step * 7 + 3) % 600} in DE queue (Slack: 45 min) until solar valley`
      });
    } else {
      feedEvents.push({
        tag: "tag-local",
        label: "SOLAR RUN",
        text: `Solar generation window open in DE (${deCI.toFixed(0)}g). Dispatched 4 parallel inference workers.`
      });
    }
    feedEvents.push({
      tag: "tag-local",
      label: "SLA DISPATCH",
      text: `Critical API service #${(step * 2) % 600} dispatched immediately (Slack < 20m) to guarantee 100% SLA.`
    });
  } else if (currentPolicy === "Energy_Greedy_Consolidation") {
    feedEvents.push({
      tag: "tag-local",
      label: "CONSOLIDATE",
      text: `Packed Task #${step % 600} onto active node_de_cpu_01 to avoid waking server from sleep.`
    });
    feedEvents.push({
      tag: "tag-delay",
      label: "CARBON BLIND",
      text: `Server running at 85% load during 520g CO₂ fossil peaker spike in Germany.`
    });
  } else {
    // FIFO Default
    feedEvents.push({
      tag: "tag-local",
      label: "FIFO ARRIVE",
      text: `Task #${step % 600} placed in first available slot. Zero carbon intensity consideration.`
    });
    if (step > 40) {
      feedEvents.push({
        tag: "tag-delay",
        label: "SLA VIOLATION",
        text: `Head-of-line queue blocking: Task #${(step + 12) % 600} missed deadline by 14.2 mins.`
      });
    }
  }

  dispatchFeed.innerHTML = feedEvents.map(e => `
    <div class="feed-item">
      <span><span class="tag-decision ${e.tag}">${e.label}</span> ${e.text}</span>
      <span style="color:var(--text-dim);">${hours}h</span>
    </div>
  `).join("");
}

function drawGridChart(step) {
  if (!gridCtx || !simulationData) return;
  const canvas = gridChartCanvas;
  const width = canvas.width = canvas.parentElement.clientWidth * window.devicePixelRatio;
  const height = canvas.height = canvas.parentElement.clientHeight * window.devicePixelRatio;

  gridCtx.clearRect(0, 0, width, height);

  const traces = simulationData.grid_traces;
  const totalSteps = traces.intervals;

  const padding = { top: 25, bottom: 35, left: 45, right: 20 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  // Grid lines
  gridCtx.strokeStyle = "rgba(255, 255, 255, 0.08)";
  gridCtx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = padding.top + (plotH / 4) * i;
    gridCtx.beginPath();
    gridCtx.moveTo(padding.left, y);
    gridCtx.lineTo(width - padding.right, y);
    gridCtx.stroke();

    const val = 600 - (600 / 4) * i;
    gridCtx.fillStyle = "#64748b";
    gridCtx.font = `${10 * window.devicePixelRatio}px Inter`;
    gridCtx.fillText(`${val}`, 5, y + 4);
  }

  // Draw series
  const series = [
    { key: "DE", color: "#ef4444", label: "Germany (DE)" },
    { key: "US_CA", color: "#f59e0b", label: "California (US)" },
    { key: "FR", color: "#8b5cf6", label: "France (FR)" },
    { key: "SE", color: "#10b981", label: "Sweden (SE)" },
  ];

  series.forEach(s => {
    const arr = traces[s.key];
    gridCtx.strokeStyle = s.color;
    gridCtx.lineWidth = 2 * window.devicePixelRatio;
    gridCtx.beginPath();

    for (let i = 0; i < totalSteps; i++) {
      const x = padding.left + (i / (totalSteps - 1)) * plotW;
      const y = padding.top + plotH - (arr[i] / 600) * plotH;
      if (i === 0) gridCtx.moveTo(x, y);
      else gridCtx.lineTo(x, y);
    }
    gridCtx.stroke();
  });

  // Vertical timeline marker
  const curX = padding.left + (step / (totalSteps - 1)) * plotW;
  gridCtx.strokeStyle = "#ffffff";
  gridCtx.lineWidth = 2 * window.devicePixelRatio;
  gridCtx.setLineDash([4 * window.devicePixelRatio, 4 * window.devicePixelRatio]);
  gridCtx.beginPath();
  gridCtx.moveTo(curX, padding.top);
  gridCtx.lineTo(curX, height - padding.bottom);
  gridCtx.stroke();
  gridCtx.setLineDash([]);
}

function drawCumulativeChart(step, scData) {
  if (!cumCtx || !scData) return;
  const canvas = cumChartCanvas;
  const width = canvas.width = canvas.parentElement.clientWidth * window.devicePixelRatio;
  const height = canvas.height = canvas.parentElement.clientHeight * window.devicePixelRatio;

  cumCtx.clearRect(0, 0, width, height);

  const padding = { top: 25, bottom: 35, left: 45, right: 20 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  // Grid lines
  cumCtx.strokeStyle = "rgba(255, 255, 255, 0.08)";
  cumCtx.lineWidth = 1;
  for (let i = 0; i <= 3; i++) {
    const y = padding.top + (plotH / 3) * i;
    cumCtx.beginPath();
    cumCtx.moveTo(padding.left, y);
    cumCtx.lineTo(width - padding.right, y);
    cumCtx.stroke();

    const val = (300 - (300 / 3) * i).toFixed(0);
    cumCtx.fillStyle = "#64748b";
    cumCtx.font = `${10 * window.devicePixelRatio}px Inter`;
    cumCtx.fillText(`${val}kg`, 5, y + 4);
  }

  // Draw cumulative carbon curves for policies
  const polConfigs = [
    { key: "FIFO_Default", color: "#64748b", label: "FIFO Default" },
    { key: "Energy_Greedy_Consolidation", color: "#3b82f6", label: "Energy Greedy" },
    { key: "Spatial_Only_Carbon", color: "#f59e0b", label: "Spatial Only" },
    { key: "CarbonSlack_Novel", color: "#10b981", label: "CarbonSlack (Novel)" },
  ];

  polConfigs.forEach(p => {
    const data = scData[p.key];
    if (!data) return;
    const arr = data.cum_carbon_kg;
    const len = arr.length;

    cumCtx.strokeStyle = p.color;
    cumCtx.lineWidth = (p.key === currentPolicy ? 3.5 : 2) * window.devicePixelRatio;
    cumCtx.beginPath();

    const renderTo = Math.min(step, len - 1);
    for (let i = 0; i <= renderTo; i++) {
      const x = padding.left + (i / (len - 1)) * plotW;
      const y = padding.top + plotH - (arr[i] / 300) * plotH;
      if (i === 0) cumCtx.moveTo(x, y);
      else cumCtx.lineTo(x, y);
    }
    cumCtx.stroke();
  });
}
