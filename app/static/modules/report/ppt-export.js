import { fetchDiagnosticPpt } from "../api/ppt-report.js?v=ppt-ui-validation-v1";
import { captureDashboardCharts } from "./chart-capture.js?v=ppt-ui-validation-v1";

const READY_LABEL = "진단 보고서 저장";
const BUSY_LABEL = "PPT 생성 및 UI 검증 중...";

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
  setStatus("PPT 생성 및 UI 검증 중입니다. 필요하면 배치를 자동 수정합니다.", "busy");
  try {
    const { trendImageDataUrl, fftImageDataUrl } = await captureDashboardCharts({
      fft: request.fftRecord,
      selectedFaultType: request.selectedFaultType,
      presentation: true,
    });
    if (request.demoPresentation) {
      const escape = (value) => String(value || "").replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
      const title = escape(document.getElementById('equipment-title').textContent);
      const sections = [
        ['AI 분석', 'ai-analysis-description'], ['AI 추세 분석', 'trend-ai-summary'],
        ['AI 주파수 분석', 'fft-ai-summary'],
      ].map(([label, id]) => `<h2>${label}</h2><p>${escape(document.getElementById(id)?.textContent)}</p>`).join('');
      const html = `<!doctype html><html lang="ko"><meta charset="utf-8"><title>${title} 진단 보고서</title><style>body{max-width:1000px;margin:40px auto;padding:24px;font-family:sans-serif;color:#233c4c;line-height:1.8}h1{font-size:30px}h2{font-size:20px;color:#138580}img{width:100%;border:1px solid #e1eaf1;border-radius:12px}</style><h1>${title}</h1><p>설비 진단 보고서 · 데모</p>${sections}<h2>추세 그래프</h2><img alt="추세 그래프" src="${trendImageDataUrl}"><h2>주파수 그래프</h2><img alt="주파수 그래프" src="${fftImageDataUrl}"></html>`;
      const url = URL.createObjectURL(new Blob([html], {type:'text/html;charset=utf-8'}));
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = `diagnostic-demo-${request.datasetId}.html`; anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setStatus('데모 진단 보고서를 저장했습니다.', 'success');
      return;
    }
    const { blob, validation } = await fetchDiagnosticPpt(request.datasetId, {
      recordId: request.recordId,
      selectedFaultType: request.selectedFaultType,
      until: request.until,
      trendImageDataUrl,
      fftImageDataUrl,
    });
    downloadPpt(blob, request.datasetId);
    if (validation.status === "passed") {
      setStatus("UI 검증을 통과한 진단 보고서를 다운로드했습니다.", "success");
    } else {
      const summary = validation.issues.slice(0, 3).join(" / ");
      const label = validation.status === "warning" ? "UI 검증 경고" : "UI 검증 미완료";
      setStatus(`${label}: ${summary || "슬라이드 배치를 확인해 주세요."} 보고서는 다운로드했습니다.`, "warning");
    }
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
