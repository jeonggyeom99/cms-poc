import { demoChatReply } from "../demo.js?v=demo-chat-v1";

async function responseError(response) {
  let payload;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  const detail = payload?.detail;
  const message = typeof detail === "string"
    ? detail
    : typeof detail?.message === "string"
      ? detail.message
      : "AI 답변을 생성하지 못했습니다. 잠시 후 다시 시도해 주세요.";
  const error = new Error(message);
  error.code = typeof detail?.code === "string" ? detail.code : "request_failed";
  return error;
}

export async function sendDashboardChat(datasetId, request) {
  if (String(datasetId) === "1") return demoChatReply(request.message);
  const response = await fetch(`/api/dashboard/${encodeURIComponent(datasetId)}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    body: JSON.stringify({
      recordId: request.recordId,
      selectedFaultType: request.selectedFaultType ?? null,
      until: request.until ?? null,
      message: request.message,
      history: request.history,
    }),
  });
  if (!response.ok) throw await responseError(response);
  return response.json();
}
