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
      : "AI 메일 초안을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.";
  const error = new Error(message);
  error.code = typeof detail?.code === "string" ? detail.code : "request_failed";
  error.status = response.status;
  return error;
}

export async function fetchEmailDraft(datasetId, request) {
  const response = await fetch(
    `/api/dashboard/${encodeURIComponent(datasetId)}/email-draft`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      body: JSON.stringify({
        recordId: request.recordId,
        selectedFaultType: request.selectedFaultType ?? null,
        until: request.until ?? null,
        force: Boolean(request.force),
      }),
    },
  );
  if (!response.ok) throw await responseError(response);
  return response.json();
}