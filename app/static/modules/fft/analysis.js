import { formatCodedLabel, formatNumber, formatRatio } from "../core/format.js";
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

export function fftDiagnosisClass(diagnosis) {
  if (diagnosis?.diagnosis === "misalignment") return "danger";
  if (diagnosis?.diagnosis === "unbalance" || diagnosis?.diagnosis === "complex") return "caution";
  return "unknown";
}

export function renderFftAnalysis(fft, emptyState = {}) {
  const result = document.getElementById("fft-analysis-result");
  const description = document.getElementById("fft-analysis-description");
  const details = document.getElementById("fft-analysis-details");
  const existingChart = document.getElementById("fft-analysis-chart");
  if (existingChart?.data) getPlotly().purge(existingChart);
  if (!fft) {
    const {
      resultLabel = "분석 불가",
      description: emptyDescription = "FFT CSV가 없어 스펙트럼 피크를 분석할 수 없습니다.",
      heading = "FFT 분석에 필요한 스펙트럼 데이터가 없습니다.",
      detail = "FFT 측정 기록이 제공되면 최대 피크를 표시합니다.",
    } = emptyState;
    result.className = "result-chip unknown";
    result.textContent = resultLabel;
    description.textContent = emptyDescription;
    details.className = "analysis-placeholder";
    details.innerHTML = `<strong>${heading}</strong><p>${detail}</p>`;
    return;
  }

  const extractionType = fft.metadata?.extractionType;
  const analysis = fft.analysis;
  const diagnosis = analysis?.diagnosis;
  const hasPeaks = analysis?.status === "analyzed";
  const hasVelocityDiagnosis = diagnosis?.status === "analyzed";
  const resultClass = hasVelocityDiagnosis
    ? fftDiagnosisClass(diagnosis)
    : (hasPeaks ? (fftExtractionClass(extractionType?.code) || "normal") : "unknown");
  result.className = `result-chip ${resultClass}`;
  result.textContent = hasVelocityDiagnosis ? diagnosis.label : (hasPeaks ? diagnosis?.label ?? "피크 검출" : diagnosis?.label ?? "주요 피크 없음");
  description.textContent = `${fft.measuredAt} · ${formatCodedLabel(fft.metadata?.measureMode)} · ${formatCodedLabel(fft.metadata?.diagMode)}`;

  if (!hasPeaks && !diagnosis) {
    details.className = "analysis-placeholder";
    details.innerHTML = `<strong>${analysis?.message ?? "FFT 분석 결과를 계산할 수 없습니다."}</strong>`;
    return;
  }

  const frequencyUnit = fft.frequencyUnit === "Hz" ? "Hz" : "bin";
  const amplitudeUnit = fft.amplitudeUnit ?? "";
  const harmonicDetails = diagnosis?.harmonics ?? [];
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
      ${hasVelocityDiagnosis ? `
      <section class="fft-analysis-item">
        <span>2X / 1X · 3X / 1X</span>
        <strong>${formatRatio(diagnosis.ratios.twoToOne)} · ${formatRatio(diagnosis.ratios.threeToOne)}</strong>
      </section>` : ""}
      ${hasPeaks ? analysis.peaks.map((peak, index) => `
      <section class="fft-analysis-item">
        <span>주요 피크 ${index + 1}</span>
        <strong>${formatNumber(peak.amplitude, 4)} ${amplitudeUnit}</strong>
        <small>${formatNumber(peak.frequency, 2)} ${frequencyUnit}</small>
      </section>`).join("") : ""}
      <section class="fft-analysis-item">
        <span>진단 대상</span>
        <strong>${formatCodedLabel(fft.metadata?.diagMode)}</strong>
      </section>
    </div>
    ${showDiagnosisChart ? `
    <section class="fft-analysis-chart-section" aria-labelledby="fft-analysis-chart-title">
      <div class="fft-analysis-chart-heading">
        <strong id="fft-analysis-chart-title">회전 주파수 분석 그래프</strong>
        <span>점: 실제 검출 피크 · 점선: 목표 회전 주파수</span>
      </div>
      <div id="fft-analysis-chart" class="plot fft-analysis-chart" role="img" aria-label="회전 주파수 FFT 분석 그래프"></div>
    </section>` : ""}
    <p class="fft-analysis-note">${diagnosis?.message ?? analysis.message}</p>
    ${hasPeaks ? `<p class="fft-analysis-note">상위 10개 피크를 ${formatNumber(analysis.frequencyTolerance, 1)} ${frequencyUnit} 이내로 그룹화 · ${formatNumber(analysis.amplitudeThreshold, 2)} ${amplitudeUnit} 이상 최대 5개 표시</p>` : ""}`;
  if (showDiagnosisChart) renderPlot("fft-analysis-chart", buildFftDiagnosisFigure(fft));
}
