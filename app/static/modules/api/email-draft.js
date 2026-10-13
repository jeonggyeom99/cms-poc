import { demoAiAnalysis, isDemoDataset } from "../demo.js?v=demo-datasets-v7";

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
      : "인공지능 이메일 초안을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.";
  const error = new Error(message);
  error.code = typeof detail?.code === "string" ? detail.code : "request_failed";
  error.status = response.status;
  return error;
}

export async function fetchEmailDraft(datasetId, request) {
  if (request.demoPresentation && isDemoDataset(datasetId)) {
    const analysis = demoAiAnalysis(datasetId).analysis;
    const innerRace = String(datasetId) === "5";
    return { draft: {
      subject: innerRace ? "[설비 점검 요청] NO.1 DUST COLLECT FAN · 베어링 내륜(BPFI)" : "[설비 점검 요청] Direct Cooling Pump DS · 초기 결함 / Unbalance",
      greeting: "설비보전 담당자님, 안녕하세요.", status: analysis.headline,
      trend: analysis.trendSummary, fft: analysis.fftSummary,
      priorityActions: analysis.recommendedActions,
      limitations: ["고정 데모 분석을 바탕으로 작성한 점검 요청입니다."],
      closing: innerRace ? "센서 및 베어링 점검과 동일 운전 조건의 재측정 일정을 확인해 주시기 바랍니다." : "회전체 점검과 동일 운전 조건의 재측정 일정을 확인해 주시기 바랍니다.",
    } };
  }
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
