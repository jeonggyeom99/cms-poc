export function renderTrendDirection(data, state = "ready") {
  const details = document.getElementById("trend-direction-details");
  const status = document.getElementById("trend-direction-status");
  const description = document.getElementById("trend-direction-description");
  const analysis = data?.trend?.analysis;
  let label = "판단 불가";
  let message = "우상향 판정에 필요한 진동 속도 추세 데이터가 없습니다.";
  let tone = "neutral";

  if (state === "loading") {
    label = "확인 중";
    message = "진동 속도 추세를 확인하고 있습니다.";
  } else if (state === "error") {
    message = "추세 데이터를 불러오지 못했습니다. 설비를 다시 선택해 주세요.";
  } else if (analysis?.status === "rising") {
    label = "상승 경향";
    message = "진동 속도 추세에서 우상향 경향이 감지되었습니다.";
    tone = "caution";
  } else if (analysis?.status === "stable") {
    label = "안정";
    message = "진동 속도 추세에서 우상향 경향이 감지되지 않았습니다.";
    tone = "normal";
  } else if (analysis?.status === "insufficient_data") {
    message = `추세 표본이 부족합니다. 현재 ${analysis.usedPoints}개 / 필요 ${analysis.requiredPoints}개로 우상향 여부를 판단할 수 없습니다.`;
  }

  details.className = `trend-direction-details is-${tone}`;
  details.setAttribute("aria-busy", String(state === "loading"));
  status.textContent = label;
  description.textContent = message;
}
