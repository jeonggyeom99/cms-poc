const palette = {
  ink: "#15242d",
  muted: "#65757f",
  grid: "#e8edef",
  teal: "#0d7f78",
  tealFill: "rgba(13, 127, 120, 0.10)",
  caution: "#f1a526",
  danger: "#e25353",
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
  doubleClick: "reset+autosize",
};

let dashboardData;

function formatNumber(value, digits = 2) {
  return Number(value).toFixed(digits);
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

function populateSummary(data) {
  const { equipment, current } = data;
  document.getElementById("plant-name").textContent = equipment.plant;
  document.getElementById("line-name").textContent = equipment.line;
  document.getElementById("equipment-title").textContent = equipment.name;
  document.getElementById("measurement-point").textContent = `측정 위치 · ${equipment.measurementPoint}`;
  document.getElementById("last-updated").textContent = `최근 측정 ${equipment.lastMeasuredAt}`;
  document.getElementById("status-label").textContent = equipment.statusLabel;
  document.getElementById("velocity-value").textContent = formatNumber(current.velocity);
  document.getElementById("velocity-unit").textContent = current.velocityUnit;
  document.getElementById("warning-value").textContent = formatNumber(current.warningThreshold);
  document.getElementById("danger-value").textContent = formatNumber(current.dangerThreshold);
  document.getElementById("acceleration-value").textContent = formatNumber(current.acceleration);
  document.getElementById("acceleration-unit").textContent = current.accelerationUnit;
  document.getElementById("temperature-value").textContent = formatNumber(current.temperature, 1);
  document.getElementById("temperature-unit").textContent = current.temperatureUnit;
  document.getElementById("operating-rate").textContent = formatNumber(current.operatingRate, 1);
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
  const points = filteredTrendPoints(period);
  const { warningThreshold, dangerThreshold } = dashboardData.current;
  const x = points.map((point) => point.timestamp);
  const y = points.map((point) => point.value);
  const latestPoint = points.at(-1);

  const traces = [
    {
      x,
      y,
      type: "scatter",
      mode: "lines+markers",
      name: "진동 속도",
      line: { color: palette.teal, width: 2.5, shape: "spline" },
      marker: { color: "#ffffff", line: { color: palette.teal, width: 2 }, size: 6 },
      fill: "tozeroy",
      fillcolor: palette.tealFill,
      hovertemplate: "%{x}<br><b>%{y:.2f} mm/s</b><extra></extra>",
    },
    {
      x: [x[0], x.at(-1)],
      y: [warningThreshold, warningThreshold],
      type: "scatter",
      mode: "lines",
      name: "경고 기준",
      line: { color: palette.caution, width: 1.5, dash: "dash" },
      hovertemplate: "경고 %{y:.2f} mm/s<extra></extra>",
    },
    {
      x: [x[0], x.at(-1)],
      y: [dangerThreshold, dangerThreshold],
      type: "scatter",
      mode: "lines",
      name: "위험 기준",
      line: { color: palette.danger, width: 1.5, dash: "dot" },
      hovertemplate: "위험 %{y:.2f} mm/s<extra></extra>",
    },
    {
      x: [latestPoint.timestamp],
      y: [latestPoint.value],
      type: "scatter",
      mode: "markers",
      name: "현재",
      marker: { color: palette.caution, line: { color: "#ffffff", width: 2 }, size: 11 },
      hovertemplate: "현재 <b>%{y:.2f} mm/s</b><extra></extra>",
    },
  ];

  const layout = baseLayout();
  layout.yaxis.title = { text: "속도 (mm/s)", standoff: 8, font: { size: 10 } };
  layout.yaxis.range = [0, Math.max(8.5, ...y) + 0.5];
  layout.xaxis.hoverformat = "%Y-%m-%d";
  Plotly.react("trend-chart", traces, layout, plotConfig);
}

function renderFft() {
  const fft = dashboardData.fft;
  const traces = [
    {
      x: fft.frequencies,
      y: fft.amplitudes,
      type: "scatter",
      mode: "lines",
      name: "진폭",
      line: { color: palette.teal, width: 2 },
      fill: "tozeroy",
      fillcolor: palette.tealFill,
      hovertemplate: "%{x:.1f} Hz<br><b>%{y:.2f} mm/s</b><extra></extra>",
    },
    {
      x: fft.peaks.map((peak) => peak.frequency),
      y: fft.peaks.map((peak) => peak.amplitude),
      text: fft.peaks.map((peak) => peak.label),
      type: "scatter",
      mode: "markers+text",
      name: "주요 피크",
      textposition: "top center",
      textfont: { color: palette.caution, size: 10 },
      marker: { color: palette.caution, size: 9, line: { color: "#ffffff", width: 2 } },
      hovertemplate: "%{text}<br>%{x:.1f} Hz · <b>%{y:.2f} mm/s</b><extra></extra>",
    },
  ];

  const layout = baseLayout();
  layout.margin = { l: 45, r: 15, t: 36, b: 43 };
  layout.showlegend = false;
  layout.xaxis.title = { text: "Frequency (Hz)", standoff: 8, font: { size: 10 } };
  layout.yaxis.title = { text: "진폭", standoff: 8, font: { size: 10 } };
  layout.yaxis.range = [0, 3.5];
  Plotly.newPlot("fft-chart", traces, layout, plotConfig);

  document.getElementById("peak-list").innerHTML = fft.peaks
    .map(
      (peak) => `<div class="peak-item"><span>${peak.label} · ${peak.frequency.toFixed(1)} Hz</span><b>${peak.amplitude.toFixed(2)}</b></div>`,
    )
    .join("");
}

function renderAnalysis(data) {
  const level = data.levelAnalysis;
  document.getElementById("level-result").textContent = level.resultLabel;
  document.getElementById("level-description").textContent = level.description;
  document.getElementById("level-metrics").innerHTML = level.metrics
    .map(
      (metric) => `
        <div class="level-metric">
          <div class="level-label-row">
            <span>${metric.name}</span>
            <span>${formatNumber(metric.value)} ${metric.unit}</span>
          </div>
          <div class="level-track" role="progressbar" aria-label="${metric.name}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${metric.percent}">
            <div class="level-fill ${metric.status}" style="width:${metric.percent}%"></div>
          </div>
        </div>`,
    )
    .join("");

  const diagnosis = data.diagnosis;
  document.getElementById("confidence-value").textContent = `${diagnosis.confidence}%`;
  document.getElementById("diagnosis-title").textContent = diagnosis.title;
  document.getElementById("diagnosis-category").textContent = diagnosis.category;
  document.getElementById("diagnosis-summary").textContent = diagnosis.summary;
  document.getElementById("recommendation-list").innerHTML = diagnosis.recommendations
    .map((recommendation) => `<li>${recommendation}</li>`)
    .join("");
}

function bindPeriodTabs() {
  document.querySelectorAll("[data-period]").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll("[data-period]").forEach((tab) => tab.classList.remove("active"));
      button.classList.add("active");
      renderTrend(button.dataset.period);
    });
  });
}

function showLoadError() {
  document.querySelectorAll(".plot").forEach((plot) => {
    plot.className = "plot loading-error";
    plot.textContent = "대시보드 데이터를 불러오지 못했습니다.";
  });
}

async function initializeDashboard() {
  try {
    const response = await fetch("/api/dashboard");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    dashboardData = await response.json();

    populateSummary(dashboardData);
    renderTrend("90");
    renderFft();
    renderAnalysis(dashboardData);
    bindPeriodTabs();
  } catch (error) {
    console.error("Dashboard initialization failed", error);
    showLoadError();
  }
}

window.addEventListener("DOMContentLoaded", initializeDashboard);
