import { formatCodedLabel } from "../core/format.js";
import { fftExtractionClass } from "./analysis.js";

export function setFftRecordStatus(message, isError = false) {
  const status = document.getElementById("fft-record-list-status");
  status.textContent = message;
  status.classList.toggle("error", isError);
}

export function syncFftRecordSelection(fft, pendingId = null) {
  document.querySelectorAll("[data-fft-record-id]").forEach((button) => {
    const recordId = Number(button.dataset.fftRecordId);
    const selected = recordId === fft?.recordId;
    button.classList.toggle("active", selected);
    button.classList.toggle("pending", recordId === pendingId);
    button.setAttribute("aria-pressed", String(selected));
  });
}

export function renderFftRecordList(fft) {
  const records = (fft?.records ?? []).filter((record) => record.isAlertFft);
  const list = document.getElementById("fft-record-list");
  document.getElementById("fft-record-count").textContent = `${records.length.toLocaleString("ko-KR")}건`;

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
    button.append(time, badges);
    return button;
  });
  list.replaceChildren(...buttons);
  syncFftRecordSelection(fft);
  setFftRecordStatus(
    records.length
      ? `0.5 초과 주의·위험경보 FFT ${records.length.toLocaleString("ko-KR")}개`
      : "0.5 초과 주의·위험경보 FFT가 없습니다.",
  );
  list.querySelector(".fft-record-item.active")?.scrollIntoView({ block: "nearest" });
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
