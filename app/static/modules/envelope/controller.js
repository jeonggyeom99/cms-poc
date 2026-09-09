import { baseLayout, getPlotly, renderPlot } from "../core/plot.js?v=plot-zoom-bounds";

let context = null;
let requestVersion = 0;
let result = null;
const el = (id) => document.getElementById(`envelope-${id}`);

function drawPlot(id, figure) {
  // The shared renderer clears child nodes; purge first so Plotly rebuilds them
  // when a band or fault selection changes with otherwise identical axes.
  getPlotly().purge(document.getElementById(id));
  renderPlot(id, figure);
}

export function resetEnvelope(message = "분석할 가속도 ALL 기록을 불러오는 중입니다.") {
  requestVersion += 1;
  context = null;
  result = null;
  el("record").replaceChildren();
  el("record").disabled = true;
  el("run").disabled = true;
  el("results").hidden = true;
  el("status").textContent = message;
  el("low").value = "1000";
  el("high").value = "2200";
  el("fault").value = "BPFO";
}

export function loadEnvelope(data, until) {
  context = { datasetId: data.meta.datasetId, until };
  const records = (data.fft?.records ?? []).filter((record) => record.measureMode.code === "0")
    .sort((a, b) => b.measuredAt.localeCompare(a.measuredAt) || b.id - a.id);
  el("record").replaceChildren(...records.map((record) => {
    const option = document.createElement("option");
    option.value = record.id;
    option.textContent = `${record.measuredAt} · ${record.measureFreq.label} · ${record.extractionType.label}`;
    return option;
  }));
  el("record").disabled = !records.length;
  el("run").disabled = !records.length;
  if (!records.length) {
    el("status").textContent = "현재 설비·조회 기준일에 가속도 ALL 원시 파형 기록이 없습니다.";
    return;
  }
  const selected = records.find((record) => record.measuredAt === data.fft.measuredAt) ?? records[0];
  el("record").value = selected.id;
  void runEnvelope();
}

function trace(x, y, color, name) {
  return { x, y, name, type: "scatter", mode: "lines", line: { color, width: 1.3 },
    hovertemplate: "%{x:.5f}<br>%{y:.5f} g<extra>%{fullData.name}</extra>" };
}

function layout(frequency = false) {
  const value = baseLayout();
  value.showlegend = false;
  value.margin.l = 65;
  value.xaxis.title = { text: frequency ? "주파수 (Hz)" : "시간 (s)" };
  value.yaxis.title = { text: "진폭 (g)" };
  return value;
}

function renderSpectrum() {
  if (!result) return;
  const faultType = el("fault").value;
  const fault = result.faults.find((item) => item.type === faultType);
  const figureLayout = layout(true);
  figureLayout.xaxis.range = [0, Math.min(600, result.sampling.frequencyHz / 2)];
  figureLayout.shapes = [];
  figureLayout.annotations = [];
  for (let order = 1; fault && order <= 4; order += 1) {
    const x = fault.baseFrequency * order;
    if (x > figureLayout.xaxis.range[1]) continue;
    figureLayout.shapes.push({ type: "line", x0: x, x1: x, y0: 0, y1: 1, yref: "paper",
      line: { color: "#94a3b8", width: 1, dash: "dot" } });
    figureLayout.annotations.push({ x, y: 1, yref: "paper", text: `${order}×${faultType}`,
      showarrow: false, yanchor: "bottom", font: { size: 10 } });
  }
  el("fault-note").textContent = fault
    ? `${faultType} 1× = ${fault.baseFrequency.toFixed(2)} Hz · 표시 범위 내 1~4배 기준선입니다. 피크와의 비교를 위한 참고값이며 자동 결함 판정이 아닙니다.`
    : "RPM 또는 베어링 결함계수가 없어 이 유형의 기준선을 표시할 수 없습니다. 포락선 스펙트럼은 확인할 수 있습니다.";
  drawPlot("envelope-spectrum", {
    traces: [trace(result.frequencies, result.amplitudes, "#c65321", "포락선 FFT")], layout: figureLayout,
  });
}

async function runEnvelope() {
  if (!context || !el("record").value) return;
  const version = ++requestVersion;
  result = null;
  el("results").hidden = true;
  el("status").textContent = "포락선을 분석하고 있습니다…";
  const query = new URLSearchParams({ low_hz: el("low").value, high_hz: el("high").value });
  if (context.until) query.set("until", context.until);
  try {
    const response = await fetch(`/api/dashboard/${encodeURIComponent(context.datasetId)}/fft/${el("record").value}/envelope?${query}`, { cache: "no-store" });
    const payload = await response.json();
    if (version !== requestVersion) return;
    if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "분석 입력값을 확인하세요.");
    result = payload;
    el("results").hidden = false;
    el("status").textContent = `${result.measuredAt} · Fs ${result.sampling.frequencyHz.toLocaleString()} Hz (${result.sampling.rule}) · ${result.raw.length} samples · 기록 ${result.durationSeconds.toFixed(4)} s · FFT 간격 ${result.frequencyResolutionHz.toFixed(3)} Hz · 대역 ${result.bandHz.join("~")} Hz`;
    drawPlot("envelope-raw", { traces: [trace(result.timeSeconds, result.raw, "#287cad", "원시 파형")], layout: layout() });
    drawPlot("envelope-filtered", { traces: [trace(result.timeSeconds, result.filtered, "#33916b", "필터 파형")], layout: layout() });
    drawPlot("envelope-wave", { traces: [
      trace(result.timeSeconds, result.filtered, "#cbd0d4", "필터 파형"),
      trace(result.timeSeconds, result.envelope, "#c65321", "포락선"),
    ], layout: layout() });
    renderSpectrum();
  } catch (error) {
    if (version === requestVersion) el("status").textContent = `분석 불가: ${error.message}`;
  }
}

export function bindEnvelope() {
  el("form").addEventListener("submit", (event) => { event.preventDefault(); void runEnvelope(); });
  el("record").addEventListener("change", () => { void runEnvelope(); });
  el("fault").addEventListener("change", renderSpectrum);
}
