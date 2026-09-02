const palette = {
  muted: "#65757f",
  grid: "#e8edef",
  teal: "#0d7f78",
  tealFill: "rgba(13, 127, 120, 0.10)",
  caution: "#f1a526",
};

const plotConfig = {
  responsive: true,
  displaylogo: false,
  modeBarButtonsToRemove: [
    "select2d",
    "lasso2d",
    "autoScale2d",
    "toggleSpikelines",
  ],
  scrollZoom: true,
  doubleClick: "reset",
};

let dashboardData;
let currentPeriod = "90";

function formatNumber(value, digits = 2) {
  return Number.isFinite(Number(value)) && value !== null ? Number(value).toFixed(digits) : "--";
}

function baseLayout() {
  return {
    autosize: true,
    margin: { l: 48, r: 18, t: 28, b: 44 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    dragmode: "zoom",
    hoverlabel: {
      bgcolor: "#0d2f3c",
      bordercolor: "#0d2f3c",
      font: { color: "#ffffff", family: "Arial, sans-serif", size: 11 },
    },
    font: { color: palette.muted, family: "Arial, sans-serif", size: 11 },
    xaxis: {
      gridcolor: palette.grid,
      linecolor: palette.grid,
      tickfont: { color: palette.muted, size: 10 },
      zeroline: false,
    },
    yaxis: {
      gridcolor: palette.grid,
      linecolor: palette.grid,
      tickfont: { color: palette.muted, size: 10 },
      zeroline: false,
    },
    showlegend: true,
    legend: {
      orientation: "h",
      x: 0,
      y: 1.13,
      font: { size: 10 },
    },
  };
}

function setMetricState(id, hasData) {
  const element = document.getElementById(id);
  element.className = `mini-state ${hasData ? "normal" : "unknown"}`;
  element.textContent = hasData ? "CSV" : "데이터 없음";
}

function populateSummary(data) {
  const { equipment, current } = data;
  const hasVelocity = current.velocity !== null;
  const hasAcceleration = current.acceleration !== null;

  document.getElementById("plant-name").textContent = equipment.plant;
  document.getElementById("line-name").textContent = equipment.line;
  document.getElementById("equipment-code").textContent = equipment.id;
  document.getElementById("equipment-title").textContent = equipment.name;
  document.getElementById("measurement-point").textContent = `측정 위치 · ${equipment.measurementPoint}`;
  document.getElementById("last-updated").textContent = equipment.lastMeasuredAt
    ? `최근 측정 ${equipment.lastMeasuredAt}`
    : "최근 측정 데이터 없음";
  document.getElementById("status-label").textContent = equipment.statusLabel;
  document.getElementById("status-description").textContent = equipment.statusDescription;
  const statusPanel = document.querySelector(".status-panel");
  const statusDot = document.querySelector(".status-dot");
  statusPanel.className = `status-panel ${equipment.status}`;
  statusPanel.style.setProperty("--status-color", equipment.statusColor);
  statusDot.className = `status-dot ${equipment.status}`;
  document.getElementById("velocity-value").textContent = formatNumber(current.velocity);
  document.getElementById("velocity-unit").textContent = current.velocityUnit;
  document.getElementById("warning-value").textContent = formatNumber(current.warningThreshold);
  document.getElementById("danger-value").textContent = formatNumber(current.dangerThreshold);
  document.getElementById("acceleration-value").textContent = formatNumber(current.acceleration, 3);
  document.getElementById("acceleration-unit").textContent = current.accelerationUnit;
  document.getElementById("temperature-value").textContent = formatNumber(current.temperature, 1);
  document.getElementById("temperature-unit").textContent = current.temperatureUnit;
  document.getElementById("operating-rate").textContent = formatNumber(current.operatingRate, 1);
  setMetricState("velocity-state", hasVelocity);
  setMetricState("acceleration-state", hasAcceleration);
  document.title = `${equipment.id} | CMS AI Dashboard`;
}

function setPlotEmpty(plotId, message, isError = false) {
  const plot = document.getElementById(plotId);
  Plotly.purge(plot);
  plot.className = `plot ${isError ? "loading-error" : "plot-empty"}`;
  plot.textContent = message;
}

function setPeriodTabsEnabled(enabled) {
  document.querySelectorAll("[data-period]").forEach((button) => {
    button.disabled = !enabled;
  });
}

function filteredTrendPoints(period) {
  const points = dashboardData.trend.points;
  if (period === "all") return points;

  const latest = new Date(points.at(-1).timestamp.replace(" ", "T"));
  const start = new Date(latest);
  start.setDate(start.getDate() - Number(period));
  return points.filter((point) => new Date(point.timestamp.replace(" ", "T")) >= start);
}

function renderTrend(period = "90") {
  if (!dashboardData.trend) {
    setPeriodTabsEnabled(false);
    setPlotEmpty("trend-chart", "이 설비에는 Trend CSV가 없습니다.");
    return;
  }

  setPeriodTabsEnabled(true);
  const points = filteredTrendPoints(period);
  const x = points.map((point) => point.timestamp);
  const y = points.map((point) => point.value);
  const latestPoint = points.at(-1);
  const traces = [
    {
      x,
      y,
      type: "scatter",
      mode: "lines",
      name: "진동 속도 평균",
      line: { color: palette.teal, width: 2 },
      fill: "tozeroy",
      fillcolor: palette.tealFill,
      hovertemplate: "%{x}<br><b>%{y:.3f} mm/s</b><extra></extra>",
    },
    {
      x: [latestPoint.timestamp],
      y: [latestPoint.value],
      type: "scatter",
      mode: "markers",
      name: "최신 측정",
      marker: { color: palette.caution, line: { color: "#ffffff", width: 2 }, size: 10 },
      hovertemplate: "최신 <b>%{y:.3f} mm/s</b><extra></extra>",
    },
  ];

  const layout = baseLayout();
  layout.yaxis.title = { text: "속도 (mm/s)", standoff: 8, font: { size: 10 } };
  layout.yaxis.rangemode = "tozero";
  layout.xaxis.hoverformat = "%Y-%m-%d %H:%M";

  const plot = document.getElementById("trend-chart");
  plot.className = "plot";
  plot.textContent = "";
  Plotly.react(plot, traces, layout, plotConfig);
}

function renderFft() {
  const fft = dashboardData.fft;
  if (!fft) {
    setPlotEmpty("fft-chart", "이 설비에는 FFT CSV가 없습니다.");
    document.getElementById("fft-range").textContent = "주파수 범위 --";
    document.getElementById("fft-summary").textContent = "FFT 측정 정보가 없습니다.";
    return;
  }

  const traces = [
    {
      x: fft.frequencies,
      y: fft.amplitudes,
      type: "scatter",
      mode: "lines",
      name: "진폭",
      line: { color: palette.teal, width: 1.6 },
      fill: "tozeroy",
      fillcolor: palette.tealFill,
      hovertemplate: "%{x:.2f} Hz<br><b>%{y:.4f} mm/s</b><extra></extra>",
    },
  ];

  const layout = baseLayout();
  layout.margin = { l: 52, r: 15, t: 36, b: 43 };
  layout.showlegend = false;
  layout.xaxis.title = { text: "Frequency (Hz)", standoff: 8, font: { size: 10 } };
  layout.yaxis.title = { text: "진폭 (mm/s)", standoff: 8, font: { size: 10 } };
  layout.yaxis.rangemode = "tozero";

  const plot = document.getElementById("fft-chart");
  plot.className = "plot";
  plot.textContent = "";
  Plotly.react(plot, traces, layout, plotConfig);

  document.getElementById("fft-range").textContent = `주파수 범위 ${formatNumber(fft.frequencyRange, 0)} Hz`;
  document.getElementById("fft-summary").textContent = `측정 ${fft.measuredAt} · ${fft.amplitudes.length} Lines`;
}

function resetPeriodTabs() {
  currentPeriod = "90";
  document.querySelectorAll("[data-period]").forEach((button) => {
    button.classList.toggle("active", button.dataset.period === currentPeriod);
  });
}

function bindPeriodTabs() {
  document.querySelectorAll("[data-period]").forEach((button) => {
    button.addEventListener("click", () => {
      currentPeriod = button.dataset.period;
      document.querySelectorAll("[data-period]").forEach((tab) => tab.classList.remove("active"));
      button.classList.add("active");
      renderTrend(currentPeriod);
    });
  });
}

function availabilityLabel(availability) {
  const available = [];
  if (availability.trend) available.push("Trend");
  if (availability.fft) available.push("FFT");
  return available.length ? available.join(" + ") : "사용 가능 데이터 없음";
}

async function loadDashboard(datasetId) {
  const select = document.getElementById("dataset-select");
  select.disabled = true;
  try {
    const response = await fetch(`/api/dashboard/${encodeURIComponent(datasetId)}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    dashboardData = await response.json();
    resetPeriodTabs();
    populateSummary(dashboardData);
    renderTrend(currentPeriod);
    renderFft();
  } catch (error) {
    console.error("Dashboard data loading failed", error);
    setPlotEmpty("trend-chart", "설비 데이터를 불러오지 못했습니다.", true);
    setPlotEmpty("fft-chart", "설비 데이터를 불러오지 못했습니다.", true);
  } finally {
    select.disabled = false;
  }
}

async function initializeDashboard() {
  const select = document.getElementById("dataset-select");
  try {
    const response = await fetch("/api/datasets");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const { items } = await response.json();
    if (!items.length) {
      select.innerHTML = '<option value="">사용 가능한 CSV 데이터가 없습니다.</option>';
      setPlotEmpty("trend-chart", "data/ 폴더에서 Trend CSV를 찾지 못했습니다.");
      setPlotEmpty("fft-chart", "data/ 폴더에서 FFT CSV를 찾지 못했습니다.");
      return;
    }

    select.replaceChildren(
      ...items.map(
        (item) => new Option(
          `#${item.id} · ${item.equipmentCode} · ${item.name} (${availabilityLabel(item.availability)})`,
          item.id,
        ),
      ),
    );
    select.disabled = false;
    select.addEventListener("change", () => loadDashboard(select.value));
    await loadDashboard(items[0].id);
  } catch (error) {
    console.error("Dataset list loading failed", error);
    select.innerHTML = '<option value="">CSV 목록을 불러오지 못했습니다.</option>';
    setPlotEmpty("trend-chart", "CSV 목록을 불러오지 못했습니다.", true);
    setPlotEmpty("fft-chart", "CSV 목록을 불러오지 못했습니다.", true);
  }
}

window.addEventListener("DOMContentLoaded", () => {
  bindPeriodTabs();
  initializeDashboard();
});
