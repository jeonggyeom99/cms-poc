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
      : "진단 PPT를 생성하지 못했습니다. 잠시 후 다시 시도해 주세요.";
  const error = new Error(message);
  error.code = typeof detail?.code === "string" ? detail.code : "request_failed";
  error.status = response.status;
  return error;
}

export async function fetchDiagnosticPpt(datasetId, request) {
  const response = await fetch(
    `/api/dashboard/${encodeURIComponent(datasetId)}/diagnostic-ppt`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      body: JSON.stringify({
        recordId: request.recordId,
        selectedFaultType: request.selectedFaultType ?? null,
        until: request.until ?? null,
        trendImageDataUrl: request.trendImageDataUrl,
        fftImageDataUrl: request.fftImageDataUrl,
      }),
    },
  );
  if (!response.ok) throw await responseError(response);

  const payload = await response.blob();
  if (!payload.size) {
    throw new Error("생성된 진단 PPT 파일이 비어 있습니다.");
  }
  return payload;
}