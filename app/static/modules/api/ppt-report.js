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
  let validation = { status: "unverified", repairs: 0, issues: ["UI 검증 결과를 받지 못했습니다."] };
  try {
    const header = response.headers.get("X-PPT-Validation");
    if (header) {
      const parsed = JSON.parse(decodeURIComponent(header));
      if (["passed", "warning", "unverified"].includes(parsed.status)
          && Number.isInteger(parsed.repairs) && parsed.repairs >= 0 && parsed.repairs <= 2
          && Array.isArray(parsed.issues) && parsed.issues.every((issue) => typeof issue === "string")) {
        validation = parsed;
      }
    }
  } catch {
    // A metadata error must not prevent downloading a valid PPTX.
  }
  return { blob: payload, validation };
}
