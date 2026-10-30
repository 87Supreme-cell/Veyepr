const history = [];
const maxHistory = 24;
let demoStep = 12;

const elements = {
  loss: document.querySelector("#loss-value"),
  gradient: document.querySelector("#gradient-value"),
  batch: document.querySelector("#batch-value"),
  step: document.querySelector("#step-value"),
  runId: document.querySelector("#run-id"),
  count: document.querySelector("#event-count"),
  summary: document.querySelector("#event-summary"),
  line: document.querySelector("#loss-line"),
  area: document.querySelector("#loss-area"),
  point: document.querySelector("#loss-point"),
};

function metricValue(metrics, name) {
  const expression = new RegExp(`^${name}\\{[^}]*\\}\\s+([^\\s]+)$`, "m");
  const match = metrics.match(expression);
  return match ? Number.parseFloat(match[1]) : null;
}

function metricLabel(metrics, name, label) {
  const expression = new RegExp(`^${name}\\{[^}]*${label}="([^"]+)"[^}]*\\}\\s+`, "m");
  const match = metrics.match(expression);
  return match ? match[1] : null;
}

function renderNumber(element, value, digits = 3) {
  element.textContent = Number.isFinite(value) ? value.toFixed(digits) : "—";
}

function drawHistory() {
  if (!elements.line || history.length < 1) return;
  const width = 640;
  const height = 260;
  const padding = 22;
  const min = Math.min(...history);
  const max = Math.max(...history);
  const range = Math.max(max - min, 0.06);
  const points = history.map((value, index) => {
    const x = history.length === 1 ? width / 2 : (index / (history.length - 1)) * (width - padding * 2) + padding;
    const y = height - padding - ((value - min) / range) * (height - padding * 2);
    return [x, y];
  });
  const pointString = points.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const last = points.at(-1);
  elements.line.setAttribute("points", pointString);
  elements.area.setAttribute("d", `M ${points[0][0]} ${height - padding} L ${pointString.replaceAll(",", " ")} L ${last[0]} ${height - padding} Z`);
  elements.point.setAttribute("cx", last[0]);
  elements.point.setAttribute("cy", last[1]);
}

function showSignal({ loss, gradient, batch, step, total, runId, event }) {
  renderNumber(elements.loss, loss, 4);
  renderNumber(elements.gradient, gradient, 3);
  renderNumber(elements.batch, batch, 0);
  renderNumber(elements.step, step, 0);
  elements.runId.textContent = runId ? `run / ${runId}` : "waiting for run";
  elements.count.textContent = `${Math.round(total || 0)} events accepted`;

  if (event) {
    elements.summary.textContent = event;
  }
  if (Number.isFinite(loss) && history.at(-1) !== loss) {
    history.push(loss);
    if (history.length > maxHistory) history.shift();
    drawHistory();
  }
}

function showPortfolioSimulation() {
  demoStep += 1;
  const loss = Math.max(0.06, 1.8 * Math.exp(-demoStep / 42) + Math.sin(demoStep * 1.7) * 0.025);
  const gradient = Math.max(0.08, 2.3 * Math.exp(-demoStep / 68) + Math.cos(demoStep) * 0.04);
  showSignal({
    loss,
    gradient,
    batch: 32,
    step: demoStep,
    total: demoStep,
    runId: "portfolio-preview",
    event: "Portfolio preview mode: simulated telemetry is running in your browser. Run the local service for live pipeline data.",
  });
}

async function updateSignal() {
  try {
    const [metricsResponse, eventsResponse] = await Promise.all([
      fetch("metrics", { cache: "no-store" }),
      fetch("events", { cache: "no-store" }),
    ]);
    if (!metricsResponse.ok || !eventsResponse.ok) throw new Error("Signal endpoint unavailable");

    const metrics = await metricsResponse.text();
    const events = await eventsResponse.json();
    const loss = metricValue(metrics, "ai_training_loss");
    const gradient = metricValue(metrics, "ai_training_gradient_norm");
    const batch = metricValue(metrics, "ai_training_batch_size");
    const step = metricValue(metrics, "ai_training_current_step");
    const total = metricValue(metrics, "ai_telemetry_events_total");
    const runId = metricLabel(metrics, "ai_training_loss", "run_id");
    const isPortfolioPreview = /^veyepr_portfolio_preview\s+1$/m.test(metrics);

    if (isPortfolioPreview) {
      showPortfolioSimulation();
      return;
    }

    const latest = events.at(-1);
    showSignal({
      loss,
      gradient,
      batch,
      step,
      total,
      runId,
      event: latest ? `Latest event: ${latest.run_id}, step ${latest.step}, captured ${new Date(latest.captured_at).toLocaleTimeString()}.` : null,
    });
  } catch (error) {
    showPortfolioSimulation();
  }
}

if (elements.loss) {
  updateSignal();
  window.setInterval(updateSignal, 2000);
}
