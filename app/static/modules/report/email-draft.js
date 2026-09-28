import { fetchEmailDraft } from "../api/email-draft.js?v=email-draft-v1";
import { captureDashboardCharts } from "./chart-capture.js?v=equipment-ai-v1";

const state = {
  available: false,
  busy: false,
  buildRequest: null,
  requestId: 0,
};

let bound = false;

function element(tagName, className, text) {
  const node = document.createElement(tagName);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function elements() {
  return {
    open: document.getElementById("email-draft-open"),
    dialog: document.getElementById("email-draft-dialog"),
    preview: document.getElementById("email-draft-preview"),
    close: document.getElementById("email-draft-close"),
    copy: document.getElementById("email-draft-copy"),
    status: document.getElementById("email-draft-status"),
  };
}

function status(message, isError = false) {
  const target = elements().status;
  if (!target) return;
  target.textContent = message;
  target.dataset.state = isError ? "error" : "ready";
}

function setBusy(busy) {
  state.busy = busy;
  const { open, copy, preview } = elements();
  if (open) {
    open.disabled = busy || !state.available;
    open.setAttribute("aria-busy", String(busy));
  }
  if (copy) copy.disabled = busy || !preview?.childElementCount;
}

function closeDialog(dialog) {
  if (!dialog?.open) return;
  if (typeof dialog.close === "function") {
    dialog.close();
    return;
  }
  dialog.removeAttribute("open");
}

function showDialog(dialog) {
  if (!dialog || dialog.open) return;
  if (typeof dialog.showModal !== "function") {
    dialog.setAttribute("open", "");
    return;
  }
  try {
    dialog.showModal();
  } catch (error) {
    console.error("Email draft dialog could not open", error);
    dialog.setAttribute("open", "");
  }
}

function text(value, fallback) {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function priorityLabel(priority) {
  return {
    immediate: "즉시",
    high: "우선",
    planned: "계획",
  }[priority] || "확인";
}

function textSection(title, value) {
  const section = element("section", "email-draft-section");
  section.append(
    element("h3", "email-draft-section-title", title),
    element("p", "email-draft-section-text", text(value, "제공된 근거가 없습니다.")),
  );
  return section;
}

function actionSection(actions) {
  const section = element("section", "email-draft-section email-draft-actions");
  section.append(element("h3", "email-draft-section-title", "우선 조치"));
  const list = element("ol", "email-draft-list");
  const items = Array.isArray(actions) ? actions : [];
  items.forEach((item) => {
    const row = element("li", "email-draft-action");
    row.append(
      element("strong", "email-draft-priority", priorityLabel(item?.priority)),
      element("span", "email-draft-action-text", text(item?.action, "추가 확인이 필요합니다.")),
    );
    list.append(row);
  });
  if (!list.childElementCount) {
    list.append(element("li", "email-draft-action", "추가 확인이 필요합니다."));
  }
  section.append(list);
  return section;
}

function limitationsSection(limitations) {
  const section = element("section", "email-draft-section email-draft-limitations");
  section.append(element("h3", "email-draft-section-title", "데이터 한계"));
  const list = element("ul", "email-draft-list");
  const items = Array.isArray(limitations) ? limitations : [];
  items.forEach((item) => list.append(element("li", null, text(item, "추가 확인이 필요합니다."))));
  if (!list.childElementCount) {
    list.append(element("li", null, "추가 확인이 필요합니다."));
  }
  section.append(list);
  return section;
}

function chartFigure(label, imageDataUrl) {
  if (typeof imageDataUrl !== "string" || !imageDataUrl.startsWith("data:image/png;base64,")) {
    return null;
  }
  const figure = element("figure", "email-draft-chart");
  const image = document.createElement("img");
  image.src = imageDataUrl;
  image.alt = `${label} 그래프`;
  image.decoding = "async";
  figure.append(image, element("figcaption", null, label));
  return figure;
}

function chartSection(images) {
  const trend = chartFigure("추세", images?.trendImageDataUrl);
  const fft = chartFigure("주파수", images?.fftImageDataUrl);
  if (!trend && !fft) return null;
  const section = element("section", "email-draft-section email-draft-charts");
  section.append(element("h3", "email-draft-section-title", "그래프"));
  const charts = element("div", "email-draft-chart-grid");
  if (trend) charts.append(trend);
  if (fft) charts.append(fft);
  section.append(charts);
  return section;
}

function renderDraft(draft, images) {
  const { preview, copy } = elements();
  if (!preview) return;

  const documentRoot = element("article", "email-draft-document");
  documentRoot.append(
    element("h2", "email-draft-subject", text(draft?.subject, "인공지능 이메일 초안")),
    element("p", "email-draft-greeting", text(draft?.greeting, "안녕하세요.")),
    textSection("현재 상태", draft?.status),
    textSection("추세", draft?.trend),
    textSection("주파수", draft?.fft),
    actionSection(draft?.priorityActions),
    limitationsSection(draft?.limitations),
  );
  const charts = chartSection(images);
  if (charts) documentRoot.append(charts);
  documentRoot.append(element("p", "email-draft-closing", text(draft?.closing, "검토 부탁드립니다.")));
  preview.replaceChildren(documentRoot);
  if (copy) copy.disabled = false;
}

function validRequest(request) {
  return Boolean(
    request
      && typeof request.datasetId === "string"
      && request.datasetId
      && Number.isInteger(request.recordId)
      && request.recordId > 0,
  );
}

async function openEmailDraft() {
  const request = state.buildRequest?.();
  if (!validRequest(request)) {
    status("선택한 주파수 기록이 없어 인공지능 이메일 초안을 만들 수 없습니다.", true);
    return;
  }

  const requestId = ++state.requestId;
  setBusy(true);
  status("추세와 주파수 그래프를 준비하고 인공지능 이메일 초안을 만들고 있습니다.");
  try {
    const images = await captureDashboardCharts({
      fft: request.fftRecord,
      selectedFaultType: request.selectedFaultType,
    });
    const payload = await fetchEmailDraft(request.datasetId, request);
    if (requestId !== state.requestId) return;
    renderDraft(payload?.draft, images);
    showDialog(elements().dialog);
    status("복사 가능한 인공지능 이메일 초안을 준비했습니다.");
  } catch (error) {
    if (requestId !== state.requestId) return;
    console.error("Email draft loading failed", error);
    status(error?.message || "인공지능 이메일 초안을 만들지 못했습니다. 잠시 후 다시 시도해 주세요.", true);
  } finally {
    if (requestId === state.requestId) setBusy(false);
  }
}

async function copyEmailDraft() {
  const { copy, preview } = elements();
  if (!preview?.childElementCount) {
    status("복사할 인공지능 이메일 초안이 없습니다.", true);
    return;
  }
  if (!navigator.clipboard?.write || typeof ClipboardItem !== "function") {
    status("이 브라우저는 서식 있는 클립보드 복사를 지원하지 않습니다.", true);
    return;
  }

  if (copy) copy.disabled = true;
  try {
    const plainText = preview.innerText || preview.textContent || "";
    const item = new ClipboardItem({
      "text/html": new Blob([preview.innerHTML], { type: "text/html;charset=utf-8" }),
      "text/plain": new Blob([plainText], { type: "text/plain;charset=utf-8" }),
    });
    await navigator.clipboard.write([item]);
    status("인공지능 이메일 초안을 클립보드에 복사했습니다.");
  } catch (error) {
    console.error("Email draft copy failed", error);
    status("서식 있는 클립보드 복사가 거부되었거나 완료되지 않았습니다.", true);
  } finally {
    if (copy) copy.disabled = false;
  }
}

export function setEmailDraftAvailable(available) {
  state.available = Boolean(available);
  if (!state.available) resetEmailDraft();
  setBusy(state.busy);
}

export function resetEmailDraft() {
  state.requestId += 1;
  const { dialog, preview } = elements();
  closeDialog(dialog);
  preview?.replaceChildren();
  status("");
  setBusy(false);
}

export function bindEmailDraft(buildRequest) {
  state.buildRequest = buildRequest;
  const { open, dialog, close, copy } = elements();
  if (bound || !open || !dialog || !close || !copy) {
    setBusy(false);
    return;
  }

  bound = true;
  open.addEventListener("click", () => {
    void openEmailDraft();
  });
  close.addEventListener("click", () => closeDialog(dialog));
  copy.addEventListener("click", () => {
    void copyEmailDraft();
  });
  setBusy(false);
}
