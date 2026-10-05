import { formatNumber } from "../core/format.js?v=korean-ui-v1";
import { getPlotly, renderPlot } from "../core/plot.js?v=plot-zoom-bounds";
import { buildFftDiagnosisFigure } from "./chart.js?v=korean-ui-v1";

const COMPACT_FFT_DIAGNOSES = Object.freeze({
  normal: { label: "정상", state: "normal" },
  unbalance: { label: "불균형", state: "caution" },
  misalignment: { label: "축정렬 불량", state: "danger" },
  bearing_inner_race: { label: "베어링 내륜", state: "danger" },
  bearing_outer_race: { label: "베어링 외륜", state: "danger" },
  other: { label: "기타/복합", state: "neutral" },
});

function compactFftDiagnosis(diagnosis) {
  if (!diagnosis || diagnosis.status === "unavailable") {
    return { label: "분석 불가", state: "neutral" };
  }
  const diagnosisKey = diagnosis?.diagnosis;
  return Object.hasOwn(COMPACT_FFT_DIAGNOSES, diagnosisKey)
    ? COMPACT_FFT_DIAGNOSES[diagnosisKey]
    : COMPACT_FFT_DIAGNOSES.other;
}

export function renderOverviewFftResult(fft) {
  const panel = document.querySelector(".overview-fft-result");
  const result = document.getElementById("overview-fft-result");
  const measuredAt = document.getElementById("overview-fft-measured-at");
  if (!panel || !result || !measuredAt) return;

  const { label, state } = compactFftDiagnosis(fft?.analysis?.diagnosis);
  panel.className = `overview-fft-result is-${state}`;
  result.textContent = label;
  measuredAt.textContent = fft?.measuredAt ? `기준 측정일시 ${fft.measuredAt}` : "기준 측정일시 --";
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

function bearingFaultView(fft, selectedFaultType) {
  const diagnosis = fft.analysis?.diagnosis;
  return diagnosis?.faults?.find((fault) => fault.type === selectedFaultType)
    ?? diagnosis?.faults?.find((fault) => fault.type === diagnosis.defaultFaultType)
    ?? null;
}

export function renderFftAnalysis(fft, selectedFaultType = null, emptyState = {}, relatedHistoryTag = null) {
  const details = document.getElementById("fft-analysis-details");
  const existingChart = document.getElementById("fft-analysis-chart");
  if (existingChart?.data) getPlotly().purge(existingChart);
  if (!fft) {
    const {
      heading = "주파수 분석에 필요한 스펙트럼 데이터가 없습니다.",
      detail = "주파수 측정 기록이 제공되면 최대 피크를 표시합니다.",
    } = emptyState;
    details.className = "analysis-placeholder";
    details.innerHTML = `<strong>${heading}</strong><p>${detail}</p>`;
    return;
  }

  const analysis = fft.analysis;
  const diagnosis = analysis?.diagnosis;

  if (!diagnosis) {
    details.className = "analysis-placeholder";
    details.innerHTML = `<strong>${analysis?.message ?? "회전수 기반 주파수 분석 결과를 계산할 수 없습니다."}</strong>`;
    return;
  }

  const isAccelerationEnv = fft.metadata?.measureMode?.code === "2";
  if (diagnosis.status === "unavailable" && !(isAccelerationEnv && fft.frequencyUnit === "Hz")) {
    details.className = "analysis-placeholder";
    details.innerHTML = `<strong>주파수 진단 대상 아님</strong><p>${diagnosis.message ?? "선택한 측정모드는 회전·베어링 주파수 진단을 지원하지 않습니다."}</p>`;
    return;
  }

  const bearingFault = bearingFaultView(fft, selectedFaultType);
  const hasBearingDiagnosis = Array.isArray(diagnosis?.faults);
  const hasVelocityDiagnosis = !hasBearingDiagnosis;

  const frequencyUnit = fft.frequencyUnit === "Hz" ? "Hz" : "bin";
  const amplitudeUnit = fft.amplitudeUnit ?? "";
  const harmonicDetails = (bearingFault?.harmonics ?? diagnosis?.harmonics ?? []).filter(
    (harmonic) => harmonic.order >= 1 && harmonic.order <= 3,
  );
  // 베어링 정보가 없어 고조파를 계산하지 못해도 ENV 스펙트럼 자체는 확인할 수 있다.
  const showDiagnosisChart = fft.frequencyUnit === "Hz"
    && (harmonicDetails.length > 0 || isAccelerationEnv);
  details.className = "fft-analysis-details";
  const bearingControls = hasBearingDiagnosis ? `
    <div class="bearing-analysis-summary" aria-label="가속도 베어링 분석">
      <div class="bearing-analysis-heading">
        <span>베어링</span>
        <strong>${diagnosis.bearing?.maker ?? "--"} ${diagnosis.bearing?.number ?? "--"}</strong>
      </div>
      ${diagnosis.bearing?.available ? `
        <div class="bearing-fault-selector" role="group" aria-label="베어링 결함 유형 선택">
          ${diagnosis.faults.map((fault) => `<button type="button" data-bearing-fault="${fault.type}" class="${fault.type === bearingFault?.type ? "active" : ""}" aria-pressed="${fault.type === bearingFault?.type}"><span>${fault.type}</span><small>계수 ${formatNumber(fault.coefficient, 4)}</small></button>`).join("")}
        </div>` : ""}
    </div>` : "";
  const bearingCard = hasBearingDiagnosis && bearingFault ? `
    <section class="fft-diagnosis-card ${bearingFault.hasAnomaly ? "danger" : "normal"}" aria-label="가속도 베어링 분석 결과">
      <span>가속도 주파수 베어링 분석</span>
      <strong>${bearingFault.type} · ${bearingFault.label}</strong>
      <small>결함계수 ${formatNumber(bearingFault.coefficient, 2)} · 기준주파수 ${formatNumber(bearingFault.baseFrequency, 2)} Hz · 점수 ${formatNumber(bearingFault.score, 3)}</small>
      <small>대표 판정: ${diagnosis.message}</small>
    </section>` : hasBearingDiagnosis ? `
    <section class="fft-diagnosis-card unknown" aria-label="가속도 베어링 분석 결과">
      <span>가속도 주파수 베어링 분석</span>
      <strong>${diagnosis.label}</strong>
      <small>${diagnosis.message}</small>
    </section>` : "";
  const historyTags = relatedHistoryTag ? `
    <div class="fft-related-history-tags" aria-label="연관 과거 이력 태그">
      <span>과거 이력</span>
      <strong>${relatedHistoryTag.fault} · ${relatedHistoryTag.faultType}</strong>
    </div>` : "";
  details.innerHTML = `
    <div class="fft-analysis-grid">
      ${diagnosis ? `
      <section class="fft-analysis-item peak">
        <span>회전수 / 회전 주파수</span>
        <strong>${formatNumber(diagnosis.rpm, 0)} RPM</strong>
        <small>${formatNumber(diagnosis.shaftFrequency, 2)} Hz</small>
      </section>` : ""}
      ${harmonicDetails.map((harmonic) => `
      <section class="fft-analysis-item${harmonic.significant || harmonic.order === 1 ? " peak" : ""}">
        <span>${bearingFault ? `${bearingFault.type} ${harmonic.order}X` : `${harmonic.order}X`} 피크</span>
        <strong>${formatNumber(harmonic.amplitude, 4)} ${amplitudeUnit}</strong>
        <small>${harmonic.detected ? `${formatNumber(harmonic.detectedFrequency, 2)} ${frequencyUnit}` : "검출 범위 없음"}</small>
      </section>`).join("")}
    </div>
    ${showDiagnosisChart ? `
    <section class="fft-analysis-chart-section">
      ${bearingControls}
      <div id="fft-analysis-chart" class="plot fft-analysis-chart" role="img" aria-label="회전 주파수 분석 그래프"></div>
    </section>` : ""}
    ${bearingCard}
    ${hasVelocityDiagnosis ? `
    <section class="fft-diagnosis-card ${diagnosis.status === "no_anomaly" ? "normal" : fftDiagnosisClass(diagnosis)}" aria-label="속도 주파수 진단 결과">
      <span>속도 주파수 진단 결과</span>
      <strong>${diagnosis.label}</strong>
      <small>${diagnosis.message ?? ""}</small>
    </section>` : ""}
    ${historyTags}`;
  if (showDiagnosisChart) renderPlot("fft-analysis-chart", buildFftDiagnosisFigure(fft, bearingFault?.type));
}
