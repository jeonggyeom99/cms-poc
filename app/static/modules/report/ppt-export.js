import { fetchDiagnosticPpt } from "../api/ppt-report.js?v=diagnostic-ppt-v1";
import { captureDashboardCharts } from "./chart-capture.js?v=report-capture-v1";

const READY_LABEL = "진단 보고서 저장";
const BUSY_LABEL = "진단 보고서 생성 중...";

let buildRequestForExport = null;
let boundButton = null;
let available = false;
let exporting = false;

function elements() {
  return {
    button: document.getElementById("diagnostic-ppt-export"),
    status: document.getElementById("report-action-status"),
  };
}

function setStatus(message, state = "ready") {
  const { status } = elements();
  if (!status) return;
  status.textContent = message;
  status.dataset.state = state;
}

function renderButton() {
  const { button } = elements();
  if (!button) return;
  button.disabled = !available || exporting;
  button.textContent = exporting ? BUSY_LABEL : READY_LABEL;
  button.setAttribute("aria-busy", String(exporting));
}

function downloadName(datasetId) {
  const safeDatasetId = String(datasetId).replace(/[^A-Za-z0-9_-]+/g, "-") || "equipment";
  return `diagnostic-ppt-${safeDatasetId}.pptx`;
}

function downloadPpt(payload, datasetId) {
  const objectUrl = URL.createObjectURL(payload);
  try {
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = downloadName(datasetId);
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

async function exportDiagnosticPpt() {
  if (exporting || !buildRequestForExport) return;

  const request = await Promise.resolve(buildRequestForExport());
  if (!request?.datasetId || !request?.recordId) {
    setStatus("선택한 주파수 기록이 없어 진단 보고서를 만들 수 없습니다.", "error");
    return;
  }

  exporting = true;
  renderButton();
  setStatus("추세와 주파수 그래프를 캡처하여 진단 보고서를 생성하고 있습니다.", "busy");
  try {
    const { trendImageDataUrl, fftImageDataUrl } = await captureDashboardCharts();
    const payload = await fetchDiagnosticPpt(request.datasetId, {
      recordId: request.recordId,
      selectedFaultType: request.selectedFaultType,
      until: request.until,
      trendImageDataUrl,
      fftImageDataUrl,
    });
    downloadPpt(payload, request.datasetId);
    setStatus("진단 보고서를 다운로드했습니다.", "success");
  } catch (error) {
    console.error("Diagnostic PPT export failed", error);
    setStatus(
      error.message || "진단 보고서를 생성하지 못했습니다. 잠시 후 다시 시도해 주세요.",
      "error",
    );
  } finally {
    exporting = false;
    renderButton();
  }
}

function handleClick() {
  void exportDiagnosticPpt();
}

export function bindPptExport(buildRequest) {
  buildRequestForExport = typeof buildRequest === "function" ? buildRequest : null;
  const { button } = elements();
  if (!button) return;
  if (boundButton && boundButton !== button) {
    boundButton.removeEventListener("click", handleClick);
  }
  if (boundButton !== button) {
    button.addEventListener("click", handleClick);
    boundButton = button;
  }
  renderButton();
}

export function setPptExportAvailable(nextAvailable) {
  available = Boolean(nextAvailable);
  renderButton();
}

export function resetPptExport() {
  available = false;
  exporting = false;
  renderButton();
  setStatus("진단 보고서 저장을 준비 중입니다.", "ready");
}
