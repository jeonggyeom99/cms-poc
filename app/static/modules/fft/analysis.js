import { formatNumber } from "../core/format.js";
import { getPlotly, renderPlot } from "../core/plot.js?v=plot-zoom-bounds";
import { buildFftDiagnosisFigure } from "./chart.js?v=plot-zoom-bounds";

const COMPACT_FFT_DIAGNOSES = Object.freeze({
  unbalance: { label: "Unbalance", state: "caution" },
  misalignment: { label: "Misalignment", state: "danger" },
  bearing_inner_race: { label: "베어링 내륜", state: "danger" },
  bearing_outer_race: { label: "베어링 외륜", state: "danger" },
  other: { label: "기타/복합", state: "neutral" },
});

function compactFftDiagnosis(diagnosis) {
  const diagnosisKey = diagnosis?.diagnosis;
  return Object.hasOwn(COMPACT_FFT_DIAGNOSES, diagnosisKey)
    ? COMPACT_FFT_DIAGNOSES[diagnosisKey]
    : COMPACT_FFT_DIAGNOSES.other;
}

export function renderOverviewFftResult(fft) {
  const panel = document.querySelector(".overview-fft-result");
  const result = document.getElementById("overview-fft-result");
  if (!panel || !result) return;

  const { label, state } = compactFftDiagnosis(fft?.analysis?.diagnosis);
  panel.className = `overview-fft-result is-${state}`;
  result.textContent = label;
}

export function fftExtractionClass(code) {
  if (code === "3") return "caution";
  if (code === "4") return "danger";
  return "";
}

function fftDiagnosisClass(diagnosis) {
  if (diagnosis?.diagnosis === "misalignment") return "danger";
  if (diagnosis?.diagnosis === "unbalance") return "caution";
  return "unknown";
}

export function renderFftAnalysis(fft, emptyState = {}) {
  const result = document.getElementById("fft-analysis-result");
  const details = document.getElementById("fft-analysis-details");
  const existingChart = document.getElementById("fft-analysis-chart");
  if (existingChart?.data) getPlotly().purge(existingChart);
  result.hidden = true;
  if (!fft) {
    const {
      heading = "FFT 분석에 필요한 스펙트럼 데이터가 없습니다.",
      detail = "FFT 측정 기록이 제공되면 최대 피크를 표시합니다.",
    } = emptyState;
    details.className = "analysis-placeholder";
    details.innerHTML = `<strong>${heading}</strong><p>${detail}</p>`;
    return;
  }

  const analysis = fft.analysis;
  const diagnosis = analysis?.diagnosis;

  if (!diagnosis) {
    details.className = "analysis-placeholder";
    details.innerHTML = `<strong>${analysis?.message ?? "회전수 기반 FFT 분석 결과를 계산할 수 없습니다."}</strong>`;
    return;
  }

  if (diagnosis.status === "analyzed") {
    result.className = `result-chip ${fftDiagnosisClass(diagnosis)}`;
    result.textContent = diagnosis.label;
    result.hidden = false;
  }

  const frequencyUnit = fft.frequencyUnit === "Hz" ? "Hz" : "bin";
  const amplitudeUnit = fft.amplitudeUnit ?? "";
  const harmonicDetails = (diagnosis?.harmonics ?? []).filter(
    (harmonic) => harmonic.order >= 1 && harmonic.order <= 3,
  );
  const showDiagnosisChart = fft.frequencyUnit === "Hz" && harmonicDetails.length > 0;
  details.className = "fft-analysis-details";
  details.innerHTML = `
    <div class="fft-analysis-grid">
      ${diagnosis ? `
      <section class="fft-analysis-item peak">
        <span>회전수 / 회전 주파수</span>
        <strong>${formatNumber(diagnosis.rpm, 0)} RPM</strong>
        <small>${formatNumber(diagnosis.shaftFrequency, 2)} Hz</small>
      </section>` : ""}
      ${harmonicDetails.map((harmonic) => `
      <section class="fft-analysis-item${harmonic.order === 1 ? " peak" : ""}">
        <span>${harmonic.order}X 피크</span>
        <strong>${formatNumber(harmonic.amplitude, 4)} ${amplitudeUnit}</strong>
        <small>${harmonic.detected ? `${formatNumber(harmonic.detectedFrequency, 2)} ${frequencyUnit}` : "검출 범위 없음"}</small>
      </section>`).join("")}
    </div>
    ${showDiagnosisChart ? `
    <section class="fft-analysis-chart-section">
      <div id="fft-analysis-chart" class="plot fft-analysis-chart" role="img" aria-label="회전 주파수 FFT 분석 그래프"></div>
    </section>` : ""}`;
  if (showDiagnosisChart) renderPlot("fft-analysis-chart", buildFftDiagnosisFigure(fft));
}
