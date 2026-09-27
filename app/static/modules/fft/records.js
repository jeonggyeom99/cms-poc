import { formatCodedLabel } from "../core/format.js?v=korean-ui-v2";
import { fftExtractionClass } from "./analysis.js?v=korean-ui-v1";

const fftRecordFilters = {
  measureMode: new Set(),
  extractionType: new Set(),
  abnormal: new Set(),
};

export function resetFftRecordFilters() {
  Object.values(fftRecordFilters).forEach((filters) => filters.clear());
}

export function toggleFftRecordFilter(group, value) {
  const filters = fftRecordFilters[group];
  if (!filters) return;
  if (filters.has(value)) filters.delete(value);
  else filters.add(value);
}

function hasActiveFftRecordFilters() {
  return Object.values(fftRecordFilters).some((filters) => filters.size > 0);
}

function matchesFftRecordFilters(record) {
  const isAbnormal = record.hasAnalysisAnomaly
    || (record.measureMode?.code === "2" && Number(record.maxAmplitude) >= 0.5);
  const extractionMatches = !fftRecordFilters.extractionType.size
    || fftRecordFilters.extractionType.has(record.extractionType?.code)
    || (
      fftRecordFilters.extractionType.has("alert")
      && ["3", "4"].includes(record.extractionType?.code)
    );
  return (
    (!fftRecordFilters.measureMode.size || fftRecordFilters.measureMode.has(record.measureMode?.code))
    && extractionMatches
    && (!fftRecordFilters.abnormal.size || isAbnormal)
  );
}

function syncFftRecordFilters() {
  document.querySelectorAll("[data-fft-filter-group]").forEach((button) => {
    const selected = fftRecordFilters[button.dataset.fftFilterGroup]?.has(button.dataset.fftFilterValue);
    button.classList.toggle("active", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
}

export function setFftRecordStatus(message, isError = false) {
  const status = document.getElementById("fft-record-list-status");
  status.textContent = message;
  status.classList.toggle("error", isError);
}

export function setFftHistoryStatus(message, isError = false) {
  const status = document.getElementById("fft-history-list-status");
  status.textContent = message;
  status.classList.toggle("error", isError);
}

export function syncFftRecordSelection(fft, pendingId = null, selectedRecordId = fft?.recordId) {
  document.querySelectorAll("[data-fft-record-id]").forEach((button) => {
    const recordId = Number(button.dataset.fftRecordId);
    const selected = recordId === selectedRecordId;
    button.classList.toggle("active", selected);
    button.classList.toggle("pending", recordId === pendingId);
    button.setAttribute("aria-pressed", String(selected));
  });
}

function renderRecordList(fft, records, { listId, countId, setStatus, statusText, selectedRecordId }) {
  const list = document.getElementById(listId);
  const count = document.getElementById(countId);
  if (count) count.textContent = `${records.length.toLocaleString("ko-KR")}건`;

  const buttons = records.map((record) => {
    const button = document.createElement("button");
    button.type = "button";
    const extractionClass = fftExtractionClass(record.extractionType?.code);
    button.className = `fft-record-item${extractionClass ? ` alert-${extractionClass}` : ""}`;
    button.dataset.fftRecordId = String(record.id);
    button.setAttribute(
      "aria-label",
      `${record.measuredAt}, ${formatCodedLabel(record.measureMode)}, ${formatCodedLabel(record.extractionType)}`,
    );

    const time = document.createElement("span");
    time.className = "fft-record-time";
    time.textContent = record.measuredAt;

    const badges = document.createElement("span");
    badges.className = "fft-record-badges";
    const modeBadge = document.createElement("span");
    modeBadge.className = "fft-record-badge";
    modeBadge.textContent = formatCodedLabel(record.measureMode);
    const extractionBadge = document.createElement("span");
    extractionBadge.className = `fft-record-badge${extractionClass ? ` ${extractionClass}` : ""}`;
    extractionBadge.textContent = formatCodedLabel(record.extractionType);
    badges.append(modeBadge, extractionBadge);
    if (record.hasAnalysisAnomaly) {
      const diagnosisBadge = document.createElement("span");
      diagnosisBadge.className = "fft-record-badge abnormal";
      diagnosisBadge.textContent = "진단 이상";
      badges.append(diagnosisBadge);
    }
    if (record.hasHighAmplitude) {
      const amplitudeBadge = document.createElement("span");
      amplitudeBadge.className = "fft-record-badge abnormal";
      amplitudeBadge.textContent = "고진폭";
      badges.append(amplitudeBadge);
    }
    if (["3", "4"].includes(record.extractionType?.code)) {
      const alertBadge = document.createElement("span");
      alertBadge.className = "fft-record-badge abnormal";
      alertBadge.textContent = "경보 채취";
      badges.append(alertBadge);
    }
    button.append(time, badges);
    return button;
  });
  list.replaceChildren(...buttons);
  syncFftRecordSelection(fft, null, selectedRecordId);
  setStatus(statusText(records));
  list.querySelector(".fft-record-item.active")?.scrollIntoView({ block: "nearest" });
}

export function renderFftRecordList(fft, selectedRecordId) {
  const allRecords = fft?.records ?? [];
  const records = allRecords.filter(matchesFftRecordFilters);
  syncFftRecordFilters();
  renderRecordList(fft, records, {
    listId: "fft-record-list",
    setStatus: setFftRecordStatus,
    selectedRecordId,
    statusText: (items) => items.length
      ? (hasActiveFftRecordFilters()
        ? `필터 결과 ${items.length.toLocaleString("ko-KR")}개`
        : `전체 주파수 측정 이력 ${allRecords.length.toLocaleString("ko-KR")}개`)
      : (hasActiveFftRecordFilters()
        ? "선택한 필터 조건에 맞는 주파수 기록이 없습니다."
        : "주파수 측정 이력이 없습니다."),
  });
}

export function renderFftHistoryList(fft) {
  const records = fft?.records ?? [];
  renderRecordList(fft, records, {
    listId: "fft-history-list",
    countId: "fft-history-count",
    setStatus: setFftHistoryStatus,
    selectedRecordId: fft?.recordId,
    statusText: (items) => items.length
      ? `${items.length.toLocaleString("ko-KR")}개 측정 기록`
      : "측정 이력이 없습니다.",
  });
}

export function renderFftMetadata(fft) {
  const metadata = fft?.metadata;
  document.getElementById("fft-metadata-grid").hidden = !metadata;
  document.getElementById("fft-meta-measure-date").textContent = metadata?.measureDate ?? "--";
  document.getElementById("fft-meta-extraction-type").textContent = formatCodedLabel(metadata?.extractionType);
  document.getElementById("fft-meta-diag-mode").textContent = formatCodedLabel(metadata?.diagMode);
  document.getElementById("fft-meta-measure-mode").textContent = formatCodedLabel(metadata?.measureMode);
  document.getElementById("fft-meta-measure-freq").textContent = formatCodedLabel(metadata?.measureFreq);
}
