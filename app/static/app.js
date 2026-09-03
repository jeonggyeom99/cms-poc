const palette = {
  muted: "#65757f",
  grid: "#e8edef",
  teal: "#0d7f78",
  tealFill: "rgba(13, 127, 120, 0.10)",
  caution: "#f1a526",
  danger: "#e25353",
};

const trendMetricStyles = {
  accelerationAll: { color: "#0d7f78", digits: 3 },
  accelerationBpf: { color: "#3478c5", digits: 3 },
  accelerationPeak: { color: "#52a447", digits: 3 },
  velocity: { color: "#7a3fb0", digits: 3 },
  displacement: { color: "#0aa8bd", digits: 2 },
};

const plotConfig = {
  responsive: true,
  displaylogo: false,
  displayModeBar: false,
  scrollZoom: true,
  doubleClick: "reset",
};

let dashboardData;
let currentPeriod = "90";
let expandedGraph = null;
let expandedGraphTrigger = null;
let selectedTrendMetrics = new Set(["velocity"]);
let fftRecordCache = new Map();
let fftSelectionRequest = 0;

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
  const measuredAt = equipment.lastMeasuredAt
    ? `최근 측정 ${equipment.lastMeasuredAt}`
    : "최근 측정 데이터 없음";
  document.getElementById("last-updated").textContent = measuredAt;
  document.getElementById("overview-measured-at").textContent = measuredAt;
  document.getElementById("status-measured-at").textContent = equipment.lastMeasuredAt ?? "데이터 없음";
  document.getElementById("dataset-availability").textContent = availabilityLabel(data.meta.availability);
  document.getElementById("status-label").textContent = equipment.statusLabel;
  document.getElementById("status-description").textContent = equipment.statusDescription;
  const overview = document.querySelector(".equipment-overview");
  const statusPanel = document.querySelector(".overview-status");
  const statusDot = document.querySelector(".status-dot");
  overview.style.setProperty("--status-color", equipment.statusColor);
  statusPanel.className = `overview-status ${equipment.status}`;
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

function setExpandButtonEnabled(graphType, enabled) {
  const button = document.querySelector(`[data-expand-graph="${graphType}"]`);
  const graphLabel = graphType === "trend" ? "Trend" : "FFT";
  button.disabled = !enabled;
  button.title = enabled ? `${graphLabel} Graph 크게 보기` : `${graphLabel} 데이터 없음`;
  button.setAttribute("aria-label", button.title);
}

function renderPlot(plotId, { traces, layout }) {
  const plot = document.getElementById(plotId);
  plot.className = plotId === "graph-modal-chart" ? "plot graph-modal-plot" : "plot";
  plot.textContent = "";
  Plotly.react(plot, traces, layout, plotConfig);
}

function filteredTrendPoints(period) {
  const points = dashboardData.trend.points;
  if (period === "all") return points;

  const latest = new Date(points.at(-1).timestamp.replace(" ", "T"));
  const start = new Date(latest);
  start.setDate(start.getDate() - Number(period));
  return points.filter((point) => new Date(point.timestamp.replace(" ", "T")) >= start);
}

function resetTrendMetricSelection() {
  const availableMetrics = dashboardData?.trend?.metrics?.filter((metric) => metric.available) ?? [];
  const defaultMetric = availableMetrics.find((metric) => metric.key === "velocity") ?? availableMetrics[0];
  selectedTrendMetrics = new Set(defaultMetric ? [defaultMetric.key] : []);
}

function formatMetricReading(metric, value) {
  if (value === null || !Number.isFinite(Number(value))) return "--";
  const digits = trendMetricStyles[metric.key]?.digits ?? 2;
  return `${formatNumber(value, digits)} ${metric.unit}`;
}

function syncTrendMetricSelector() {
  document.querySelectorAll("[data-trend-metric]").forEach((input) => {
    const selected = selectedTrendMetrics.has(input.dataset.trendMetric);
    input.checked = selected;
    input.closest(".trend-metric-option").classList.toggle("selected", selected);
  });
}

function renderTrendMetricSelector() {
  const grid = document.getElementById("trend-metric-grid");
  const metrics = dashboardData?.trend?.metrics ?? [];
  grid.innerHTML = metrics.map((metric) => {
    const style = trendMetricStyles[metric.key] ?? { color: palette.teal, digits: 2 };
    const selected = selectedTrendMetrics.has(metric.key);
    return `
      <label class="trend-metric-option${selected ? " selected" : ""}${metric.available ? "" : " unavailable"}" style="--metric-color: ${style.color}">
        <span class="trend-metric-option-header">
          <input type="checkbox" data-trend-metric="${metric.key}" ${selected ? "checked" : ""} ${metric.available ? "" : "disabled"}>
          <span class="trend-metric-swatch" aria-hidden="true"></span>
          <span>${metric.label}</span>
        </span>
        <dl class="trend-metric-values">
          <div><dt>최신값</dt><dd>${formatMetricReading(metric, metric.latestValue)}</dd></div>
          <div><dt>주의</dt><dd class="caution-value">${formatMetricReading(metric, metric.warningThreshold)}</dd></div>
          <div><dt>위험</dt><dd class="danger-value">${formatMetricReading(metric, metric.dangerThreshold)}</dd></div>
        </dl>
      </label>`;
  }).join("");
}

function bindTrendMetricSelector() {
  document.getElementById("trend-metric-grid").addEventListener("change", (event) => {
    const input = event.target.closest("[data-trend-metric]");
    if (!input) return;

    const metricKey = input.dataset.trendMetric;
    if (input.checked) {
      if (metricKey === "velocity") selectedTrendMetrics.delete("displacement");
      if (metricKey === "displacement") selectedTrendMetrics.delete("velocity");
      selectedTrendMetrics.add(metricKey);
    } else if (selectedTrendMetrics.size > 1) {
      selectedTrendMetrics.delete(metricKey);
    }

    syncTrendMetricSelector();
    if (expandedGraph === "trend") renderExpandedGraph();
  });
}

function trendAxisTitle(unit) {
  if (unit === "g") return "가속도 (g)";
  if (unit === "µm") return "변위 (µm)";
  return "속도 (mm/s)";
}

function buildExpandedTrendFigure(period = "90") {
  const points = filteredTrendPoints(period);
  const metrics = dashboardData.trend.metrics.filter(
    (metric) => metric.available && selectedTrendMetrics.has(metric.key),
  );
  const units = [...new Set(metrics.map((metric) => metric.unit))];
  const usesDualAxis = units.length > 1;
  const traces = [];

  metrics.forEach((metric) => {
    const style = trendMetricStyles[metric.key] ?? { color: palette.teal, digits: 2 };
    const axis = usesDualAxis && metric.unit !== "g" ? "y2" : "y";
    const x = points.map((point) => point.timestamp);
    const y = points.map((point) => point[metric.pointKey]);
    const latestPoint = [...points].reverse().find((point) => point[metric.pointKey] !== null);

    traces.push({
      x,
      y,
      yaxis: axis,
      type: "scatter",
      mode: "lines",
      name: metric.label,
      legendgroup: metric.key,
      line: { color: style.color, width: 2 },
      hovertemplate: `%{x}<br><b>%{y:.${style.digits}f} ${metric.unit}</b><extra>${metric.label}</extra>`,
    });

    [
      ["주의", metric.warningThreshold, palette.caution, "dash"],
      ["위험", metric.dangerThreshold, palette.danger, "dot"],
    ].forEach(([label, value, color, dash]) => {
      if (value === null || !Number.isFinite(Number(value))) return;
      traces.push({
        x: [x[0], x.at(-1)],
        y: [value, value],
        yaxis: axis,
        type: "scatter",
        mode: "lines",
        name: `${metric.label} ${label}`,
        legendgroup: metric.key,
        showlegend: false,
        line: { color, width: 1.2, dash },
        opacity: 0.8,
        hovertemplate: `${metric.label} ${label} <b>%{y:.${style.digits}f} ${metric.unit}</b><extra></extra>`,
      });
    });

    if (latestPoint) {
      traces.push({
        x: [latestPoint.timestamp],
        y: [latestPoint[metric.pointKey]],
        yaxis: axis,
        type: "scatter",
        mode: "markers",
        name: `${metric.label} 최신값`,
        legendgroup: metric.key,
        showlegend: false,
        marker: { color: style.color, line: { color: "#ffffff", width: 2 }, size: 9 },
        hovertemplate: `최신 <b>%{y:.${style.digits}f} ${metric.unit}</b><extra>${metric.label}</extra>`,
      });
    }
  });

  const layout = baseLayout();
  layout.margin = { l: 62, r: usesDualAxis ? 70 : 24, t: 54, b: 44 };
  layout.legend.y = 1.12;
  layout.yaxis.title = {
    text: trendAxisTitle(usesDualAxis ? "g" : units[0]),
    standoff: 8,
    font: { size: 10 },
  };
  layout.yaxis.rangemode = "tozero";
  layout.xaxis.hoverformat = "%Y-%m-%d %H:%M";
  if (usesDualAxis) {
    const secondaryUnit = units.find((unit) => unit !== "g");
    layout.yaxis2 = {
      title: { text: trendAxisTitle(secondaryUnit), standoff: 8, font: { size: 10 } },
      overlaying: "y",
      side: "right",
      rangemode: "tozero",
      showgrid: false,
      linecolor: palette.grid,
      tickfont: { color: palette.muted, size: 10 },
      zeroline: false,
    };
  }

  return { traces, layout };
}

function buildTrendFigure(period = "90") {
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
  ];

  const thresholdDefinitions = [
    {
      value: dashboardData.current.warningThreshold,
      name: "현재 주의 Level",
      color: palette.caution,
      dash: "dash",
    },
    {
      value: dashboardData.current.dangerThreshold,
      name: "현재 위험 Level",
      color: palette.danger,
      dash: "dot",
    },
  ];
  thresholdDefinitions.forEach((threshold) => {
    if (threshold.value === null || !Number.isFinite(Number(threshold.value))) return;
    traces.push({
      x: [x[0], x.at(-1)],
      y: [threshold.value, threshold.value],
      type: "scatter",
      mode: "lines",
      name: threshold.name,
      line: { color: threshold.color, width: 1.5, dash: threshold.dash },
      hovertemplate: `${threshold.name} <b>%{y:.2f} mm/s</b><extra></extra>`,
    });
  });
  traces.push({
    x: [latestPoint.timestamp],
    y: [latestPoint.value],
    type: "scatter",
    mode: "markers",
    name: "최신 측정",
    marker: { color: palette.caution, line: { color: "#ffffff", width: 2 }, size: 10 },
    hovertemplate: "최신 <b>%{y:.3f} mm/s</b><extra></extra>",
  });

  const layout = baseLayout();
  layout.margin.t = 58;
  layout.yaxis.title = { text: "속도 (mm/s)", standoff: 8, font: { size: 10 } };
  layout.yaxis.rangemode = "tozero";
  layout.xaxis.hoverformat = "%Y-%m-%d %H:%M";

  return { traces, layout };
}

function renderTrend(period = "90") {
  if (!dashboardData.trend) {
    setPeriodTabsEnabled(false);
    setExpandButtonEnabled("trend", false);
    setPlotEmpty("trend-chart", "이 설비에는 Trend CSV가 없습니다.");
    return;
  }

  setPeriodTabsEnabled(true);
  setExpandButtonEnabled("trend", true);
  renderPlot("trend-chart", buildTrendFigure(period));
}

function buildFftFigure(fft = dashboardData.fft) {
  const measureModeLabel = fft.metadata?.measureMode?.label ?? "진폭";
  const frequencySuffix = fft.frequencyUnit === "Hz" ? " Hz" : " bin";
  const amplitudeSuffix = fft.amplitudeUnit ? ` ${fft.amplitudeUnit}` : "";
  const traces = [
    {
      x: fft.frequencies,
      y: fft.amplitudes,
      type: "scatter",
      mode: "lines",
      name: measureModeLabel,
      line: { color: palette.teal, width: 1.6 },
      fill: "tozeroy",
      fillcolor: palette.tealFill,
      hovertemplate: `%{x:.2f}${frequencySuffix}<br><b>%{y:.4f}${amplitudeSuffix}</b><extra></extra>`,
    },
  ];

  const layout = baseLayout();
  layout.margin = { l: 52, r: 15, t: 36, b: 43 };
  layout.showlegend = false;
  layout.xaxis.title = {
    text: fft.frequencyUnit === "Hz" ? "Frequency (Hz)" : "FFT bin",
    standoff: 8,
    font: { size: 10 },
  };
  layout.yaxis.title = {
    text: fft.amplitudeUnit ? `${measureModeLabel} (${fft.amplitudeUnit})` : measureModeLabel,
    standoff: 8,
    font: { size: 10 },
  };
  layout.yaxis.rangemode = "tozero";

  return { traces, layout };
}

function renderFft() {
  const fft = dashboardData.fft;
  if (!fft) {
    setExpandButtonEnabled("fft", false);
    setPlotEmpty("fft-chart", "이 설비에는 FFT CSV가 없습니다.");
    document.getElementById("fft-range").textContent = "주파수 범위 --";
    return;
  }

  setExpandButtonEnabled("fft", true);
  renderPlot("fft-chart", buildFftFigure());

  document.getElementById("fft-range").textContent = fftRangeText(fft);
}

function formatCodedValue(value) {
  if (!value) return "--";
  return `${value.label || "알 수 없음"} (${value.code || "--"})`;
}

function fftSummaryText(fft) {
  const mode = fft.metadata?.measureMode?.label ?? "측정모드 미상";
  return `측정 ${fft.measuredAt} · ${mode} · ${fft.lineCount ?? fft.amplitudes.length} Lines`;
}

function fftRangeText(fft) {
  return fft.frequencyRange === null
    ? "주파수 범위 미상"
    : `주파수 범위 ${formatNumber(fft.frequencyRange, 0)} Hz`;
}

function fftExtractionClass(code) {
  if (code === "3") return "caution";
  if (code === "4") return "danger";
  return "";
}

function setFftRecordStatus(message, isError = false) {
  const status = document.getElementById("fft-record-list-status");
  status.textContent = message;
  status.classList.toggle("error", isError);
}

function syncFftRecordSelection(pendingId = null) {
  document.querySelectorAll("[data-fft-record-id]").forEach((button) => {
    const recordId = Number(button.dataset.fftRecordId);
    const selected = recordId === dashboardData?.fft?.recordId;
    button.classList.toggle("active", selected);
    button.classList.toggle("pending", recordId === pendingId);
    button.setAttribute("aria-pressed", String(selected));
  });
}

function renderFftRecordList() {
  const fft = dashboardData?.fft;
  const records = fft?.records ?? [];
  const list = document.getElementById("fft-record-list");
  document.getElementById("fft-record-count").textContent = `${records.length.toLocaleString("ko-KR")}건`;

  const buttons = records.map((record) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "fft-record-item";
    button.dataset.fftRecordId = String(record.id);
    button.setAttribute(
      "aria-label",
      `${record.measuredAt}, ${formatCodedValue(record.measureMode)}, ${formatCodedValue(record.extractionType)}`,
    );

    const time = document.createElement("span");
    time.className = "fft-record-time";
    time.textContent = record.measuredAt;

    const badges = document.createElement("span");
    badges.className = "fft-record-badges";
    const modeBadge = document.createElement("span");
    modeBadge.className = "fft-record-badge";
    modeBadge.textContent = formatCodedValue(record.measureMode);
    const extractionBadge = document.createElement("span");
    const extractionClass = fftExtractionClass(record.extractionType?.code);
    extractionBadge.className = `fft-record-badge${extractionClass ? ` ${extractionClass}` : ""}`;
    extractionBadge.textContent = formatCodedValue(record.extractionType);
    badges.append(modeBadge, extractionBadge);
    button.append(time, badges);
    return button;
  });
  list.replaceChildren(...buttons);
  syncFftRecordSelection();
  setFftRecordStatus(records.length ? `${records.length.toLocaleString("ko-KR")}개 측정 기록` : "측정 이력이 없습니다.");
  list.querySelector(".fft-record-item.active")?.scrollIntoView({ block: "nearest" });
}

function renderFftMetadata() {
  const metadata = dashboardData?.fft?.metadata;
  document.getElementById("fft-meta-measure-date").textContent = metadata?.measureDate ?? "--";
  document.getElementById("fft-meta-extraction-type").textContent = formatCodedValue(metadata?.extractionType);
  document.getElementById("fft-meta-diag-mode").textContent = formatCodedValue(metadata?.diagMode);
  document.getElementById("fft-meta-measure-mode").textContent = formatCodedValue(metadata?.measureMode);
  document.getElementById("fft-meta-measure-freq").textContent = formatCodedValue(metadata?.measureFreq);
}

function updateExpandedFftDetails() {
  const fft = dashboardData.fft;
  document.getElementById("graph-modal-fft-range").textContent = fftRangeText(fft);
  document.getElementById("graph-modal-summary").textContent = fftSummaryText(fft);
  renderFftMetadata();
  syncFftRecordSelection();
}

async function selectFftRecord(recordId) {
  const fft = dashboardData?.fft;
  if (!fft || recordId === fft.recordId) return;

  const requestId = ++fftSelectionRequest;
  const list = document.getElementById("fft-record-list");
  list.setAttribute("aria-busy", "true");
  syncFftRecordSelection(recordId);
  setFftRecordStatus("선택한 FFT를 불러오는 중...");

  try {
    let record = fftRecordCache.get(recordId);
    if (!record) {
      const datasetId = dashboardData.meta.datasetId;
      const response = await fetch(`/api/dashboard/${encodeURIComponent(datasetId)}/fft/${recordId}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      record = await response.json();
      fftRecordCache.set(recordId, record);
    }
    if (requestId !== fftSelectionRequest) return;

    dashboardData.fft = { ...record, records: fft.records };
    renderFft();
    if (expandedGraph === "fft") {
      updateExpandedFftDetails();
      renderExpandedGraph();
    }
    setFftRecordStatus(`${fft.records.length.toLocaleString("ko-KR")}개 측정 기록`);
  } catch (error) {
    if (requestId !== fftSelectionRequest) return;
    console.error("FFT record loading failed", error);
    syncFftRecordSelection();
    setFftRecordStatus("선택한 FFT를 불러오지 못했습니다.", true);
  } finally {
    if (requestId === fftSelectionRequest) list.removeAttribute("aria-busy");
  }
}

function levelDifferenceLabel(value) {
  if (value === null || !Number.isFinite(Number(value))) return "현재 설정값 없음";
  if (Math.abs(Number(value)) < 0.005) return "권고값과 동일";
  const direction = Number(value) > 0 ? "높음" : "낮음";
  return `권고보다 ${formatNumber(Math.abs(Number(value)))} mm/s ${direction}`;
}

function renderLevelAnalysis(data) {
  const analysis = data.levelAnalysis;
  const result = document.getElementById("level-result");
  const description = document.getElementById("level-description");
  const details = document.getElementById("level-details");

  if (!analysis || analysis.status === "unavailable") {
    result.className = "result-chip unknown";
    result.textContent = "분석 불가";
    description.textContent = "Trend CSV가 없어 최근 3개월 권고 Level을 산출할 수 없습니다.";
    details.className = "analysis-placeholder";
    details.innerHTML = "<strong>Level 분석에 필요한 Trend 데이터가 없습니다.</strong><p>WarningStatus 설정값은 종합 상태 판정에 사용하지 않습니다.</p>";
    return;
  }

  const compared = analysis.status === "compared";
  result.className = `result-chip ${compared ? "normal" : "caution"}`;
  result.textContent = compared ? "비교 완료" : "권고값 산출";
  const configuredNote = compared
    ? ` · 설정 기준 ${analysis.configured.measuredAt}`
    : " · 현재 WarningStatus 설정값 없음";
  description.textContent = `${analysis.windowStart} ~ ${analysis.windowEnd} · ${analysis.usedPoints}개 중 ${analysis.normalPoints}개 사용, ${analysis.outlierPoints}개 이상치 제외${configuredNote}`;

  const rows = [
    ["주의 Level", "warningThreshold", "caution"],
    ["위험 Level", "dangerThreshold", "danger"],
  ];
  details.className = "level-analysis-details";
  details.innerHTML = `
    <div class="level-comparison-grid">
      ${rows.map(([label, key, status]) => `
        <section class="level-comparison-item ${status}">
          <h3>${label}</h3>
          <dl>
            <div><dt>현재 설정</dt><dd>${formatNumber(analysis.configured?.[key])} mm/s</dd></div>
            <div><dt>권고값</dt><dd>${formatNumber(analysis.recommended[key])} mm/s</dd></div>
          </dl>
          <p>${levelDifferenceLabel(analysis.difference?.[key] ?? null)}</p>
        </section>`).join("")}
    </div>
    <p class="level-statistics">IQR 정상 범위 ${formatNumber(analysis.lowerBound)}–${formatNumber(analysis.upperBound)} mm/s · 정상 평균 ${formatNumber(analysis.normalMean)} mm/s</p>`;
}

function renderExpandedGraph() {
  if (expandedGraph === "trend") {
    renderPlot("graph-modal-chart", buildExpandedTrendFigure(currentPeriod));
  } else if (expandedGraph === "fft") {
    renderPlot("graph-modal-chart", buildFftFigure());
  }
}

function openExpandedGraph(graphType, trigger) {
  if (!dashboardData?.[graphType]) return;

  const modal = document.getElementById("graph-modal");
  const modalBody = modal.querySelector(".graph-modal-body");
  const isTrend = graphType === "trend";
  expandedGraph = graphType;
  expandedGraphTrigger = trigger;

  document.getElementById("graph-modal-eyebrow").textContent = isTrend
    ? "VIBRATION TREND"
    : "FREQUENCY SPECTRUM";
  document.getElementById("graph-modal-title").textContent = isTrend
    ? "Trend Graph"
    : "FFT Graph";
  document.getElementById("graph-modal-chart").setAttribute(
    "aria-label",
    isTrend ? "확대된 진동 속도 추세 그래프" : "확대된 FFT 주파수 스펙트럼 그래프",
  );

  const periodTabs = document.getElementById("graph-modal-period-tabs");
  const fftRange = document.getElementById("graph-modal-fft-range");
  const summary = document.getElementById("graph-modal-summary");
  const trendMetricSelector = document.getElementById("trend-metric-selector");
  const fftRecordBrowser = document.getElementById("fft-record-browser");
  const fftMetadataGrid = document.getElementById("fft-metadata-grid");
  periodTabs.hidden = !isTrend;
  fftRange.hidden = isTrend;
  summary.hidden = isTrend;
  trendMetricSelector.hidden = !isTrend;
  fftRecordBrowser.hidden = isTrend;
  fftMetadataGrid.hidden = isTrend;
  modalBody.classList.toggle("fft-expanded", !isTrend);
  if (isTrend) {
    renderTrendMetricSelector();
  } else {
    renderFftRecordList();
    updateExpandedFftDetails();
  }

  modal.showModal();
  document.body.classList.add("graph-modal-open");
  requestAnimationFrame(() => requestAnimationFrame(renderExpandedGraph));
}

function closeExpandedGraph() {
  const modal = document.getElementById("graph-modal");
  if (modal.open) modal.close();
}

function bindGraphModal() {
  const modal = document.getElementById("graph-modal");
  const modalPlot = document.getElementById("graph-modal-chart");

  document.querySelectorAll("[data-expand-graph]").forEach((button) => {
    button.addEventListener("click", () => openExpandedGraph(button.dataset.expandGraph, button));
  });
  document.getElementById("graph-modal-close").addEventListener("click", closeExpandedGraph);
  document.getElementById("fft-record-list").addEventListener("click", (event) => {
    const button = event.target.closest("[data-fft-record-id]");
    if (button) selectFftRecord(Number(button.dataset.fftRecordId));
  });
  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeExpandedGraph();
  });
  modal.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeExpandedGraph();
    }
  });
  modal.addEventListener("close", () => {
    Plotly.purge(modalPlot);
    modalPlot.className = "plot graph-modal-plot";
    modalPlot.textContent = "";
    modal.querySelector(".graph-modal-body").classList.remove("fft-expanded");
    document.body.classList.remove("graph-modal-open");
    expandedGraph = null;
    expandedGraphTrigger?.focus();
    expandedGraphTrigger = null;
  });
  window.addEventListener("resize", () => {
    if (modal.open && modalPlot.data) Plotly.Plots.resize(modalPlot);
  });
}

function syncPeriodTabs() {
  document.querySelectorAll("[data-period]").forEach((button) => {
    button.classList.toggle("active", button.dataset.period === currentPeriod);
  });
}

function resetPeriodTabs() {
  currentPeriod = "90";
  syncPeriodTabs();
}

function bindPeriodTabs() {
  document.querySelectorAll("[data-period]").forEach((button) => {
    button.addEventListener("click", () => {
      currentPeriod = button.dataset.period;
      syncPeriodTabs();
      renderTrend(currentPeriod);
      if (expandedGraph === "trend") renderExpandedGraph();
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
  fftSelectionRequest += 1;
  fftRecordCache = new Map();
  select.disabled = true;
  setExpandButtonEnabled("trend", false);
  setExpandButtonEnabled("fft", false);
  try {
    const response = await fetch(`/api/dashboard/${encodeURIComponent(datasetId)}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    dashboardData = await response.json();
    if (dashboardData.fft) {
      const { records, ...selectedRecord } = dashboardData.fft;
      fftRecordCache.set(selectedRecord.recordId, selectedRecord);
    }
    resetPeriodTabs();
    resetTrendMetricSelection();
    populateSummary(dashboardData);
    renderTrend(currentPeriod);
    renderFft();
    renderLevelAnalysis(dashboardData);
  } catch (error) {
    console.error("Dashboard data loading failed", error);
    setExpandButtonEnabled("trend", false);
    setExpandButtonEnabled("fft", false);
    setPlotEmpty("trend-chart", "설비 데이터를 불러오지 못했습니다.", true);
    setPlotEmpty("fft-chart", "설비 데이터를 불러오지 못했습니다.", true);
    renderLevelAnalysis({ levelAnalysis: null });
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
      setExpandButtonEnabled("trend", false);
      setExpandButtonEnabled("fft", false);
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
    setExpandButtonEnabled("trend", false);
    setExpandButtonEnabled("fft", false);
  }
}

window.addEventListener("DOMContentLoaded", () => {
  bindPeriodTabs();
  bindGraphModal();
  bindTrendMetricSelector();
  initializeDashboard();
});
