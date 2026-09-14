import { sendDashboardChat } from "../api/chat.js?v=dashboard-chat-v1";
import { getDashboardData, getSelectedBearingFaultType } from "../core/state.js?v=acceleration-bearing-fft";

const STORAGE_PREFIX = "cms-dashboard-chat-v1:";
const MAX_HISTORY = 12;
let activeContextKey = null;
let open = false;
let bound = false;

function elements() {
  return {
    panel: document.getElementById("chat-panel"),
    open: document.getElementById("chat-open"),
    close: document.getElementById("chat-close"),
    backdrop: document.getElementById("chat-backdrop"),
    reset: document.getElementById("chat-reset"),
    messages: document.getElementById("chat-messages"),
    form: document.getElementById("chat-form"),
    input: document.getElementById("chat-input"),
    send: document.getElementById("chat-send"),
    chips: document.getElementById("chat-prompt-chips"),
    status: document.getElementById("chat-status"),
  };
}

function requestedUntil() {
  return new URLSearchParams(window.location.search).get("until");
}

function context() {
  const data = getDashboardData();
  const recordId = data?.fft?.recordId;
  if (!data?.meta?.datasetId || !Number.isInteger(recordId)) return null;
  return {
    datasetId: data.meta.datasetId,
    recordId,
    selectedFaultType: getSelectedBearingFaultType(),
    until: requestedUntil(),
  };
}

function storageKey(value) {
  return STORAGE_PREFIX + [value.datasetId, value.recordId, value.selectedFaultType || "none", value.until || "latest"]
    .map(encodeURIComponent).join(":");
}

function readMessages() {
  if (!activeContextKey) return [];
  try {
    const value = JSON.parse(window.sessionStorage.getItem(activeContextKey) || "[]");
    return Array.isArray(value)
      ? value.filter((item) => item && ["user", "assistant"].includes(item.role) && typeof item.content === "string")
      : [];
  } catch {
    return [];
  }
}

function saveMessages(messages) {
  if (!activeContextKey) return;
  window.sessionStorage.setItem(activeContextKey, JSON.stringify(messages.slice(-MAX_HISTORY)));
}

function messageNode(message) {
  const article = document.createElement("article");
  article.className = `chat-message ${message.role}`;
  const avatar = document.createElement("span");
  avatar.setAttribute("aria-hidden", "true");
  avatar.textContent = message.role === "assistant" ? "AI" : "나";
  const copy = document.createElement("p");
  copy.textContent = message.content;
  article.append(avatar, copy);
  return article;
}

function renderMessages(messages = readMessages()) {
  const { messages: target } = elements();
  target.replaceChildren();
  if (!messages.length) {
    target.append(messageNode({
      role: "assistant",
      content: "선택한 설비 데이터와 연관 이력을 바탕으로 점검 우선순위와 판단 근거를 안내합니다.",
    }));
  } else {
    messages.forEach((message) => target.append(messageNode(message)));
  }
  target.scrollTop = target.scrollHeight;
}

function setBusy(busy) {
  const { input, send } = elements();
  input.disabled = busy || !activeContextKey;
  send.disabled = busy || !activeContextKey;
  send.setAttribute("aria-busy", String(busy));
}

function setOpen(next, returnFocus = true) {
  open = next;
  const { panel, open: trigger, backdrop, input } = elements();
  panel.classList.toggle("is-open", open);
  backdrop.classList.toggle("is-open", open);
  panel.setAttribute("aria-hidden", String(!open));
  trigger.setAttribute("aria-expanded", String(open));
  if (open) input.focus();
  else if (returnFocus) trigger.focus();
}

function appendAndSave(message) {
  const messages = readMessages();
  messages.push(message);
  saveMessages(messages);
  renderMessages(messages);
}

async function submit(message) {
  const selected = context();
  if (!selected || !activeContextKey) return;
  const { input, status } = elements();
  const history = readMessages();
  appendAndSave({ role: "user", content: message });
  input.value = "";
  status.textContent = "AI 답변을 생성하고 있습니다.";
  setBusy(true);
  try {
    const response = await sendDashboardChat(selected.datasetId, {
      ...selected,
      message,
      history: history.slice(-MAX_HISTORY),
    });
    if (activeContextKey !== storageKey(selected)) return;
    appendAndSave(response.message);
    status.textContent = "";
  } catch (error) {
    if (activeContextKey !== storageKey(selected)) return;
    const detail = error.code === "missing_api_key"
      ? "OPENAI_API_KEY가 설정되지 않았습니다. 서버의 .env 설정을 확인해 주세요."
      : `답변을 생성하지 못했습니다: ${error.message}`;
    appendAndSave({ role: "assistant", content: detail });
    status.textContent = "";
  } finally {
    if (activeContextKey === storageKey(selected)) {
      setBusy(false);
      input.focus();
    }
  }
}

function bindEvents() {
  if (bound) return;
  bound = true;
  const { open: trigger, close, backdrop, reset, form, input, chips } = elements();
  trigger.addEventListener("click", () => setOpen(true));
  close.addEventListener("click", () => setOpen(false));
  backdrop.addEventListener("click", () => setOpen(false));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && open) setOpen(false);
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const message = input.value.trim();
    if (message) submit(message);
  });
  reset.addEventListener("click", () => {
    if (!activeContextKey) return;
    window.sessionStorage.removeItem(activeContextKey);
    renderMessages([]);
    elements().status.textContent = "현재 설비 맥락의 대화를 초기화했습니다.";
    input.focus();
  });
  chips.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    if (button.dataset.action === "email-draft") {
      document.getElementById("email-draft-open")?.click();
      return;
    }
    input.value = button.textContent;
    form.requestSubmit();
  });
}

export function syncDashboardChatContext() {
  const selected = context();
  activeContextKey = selected ? storageKey(selected) : null;
  const { status } = elements();
  renderMessages();
  setBusy(false);
  status.textContent = selected ? "" : "분석할 주파수 기록을 선택해 주세요.";
}

export function initializeDashboardChat() {
  bindEvents();
  syncDashboardChatContext();
}
