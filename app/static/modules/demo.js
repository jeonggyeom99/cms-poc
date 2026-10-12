// Presentation-only scenario for the demo branch. API responses and CSVs stay intact.
export const isDemoDataset = (id) => String(id) === "1";

export function demoSummary(item) {
  return isDemoDataset(item.id) ? { ...item, status: "caution", statusLabel: "속도 알람 · Unbalance",
    statusDescription: "속도 알람과 우상향 경향이 확인되어 축 불평형 점검이 필요합니다.", statusColor: "#f1a526" } : item;
}

export function demoDashboard(data) {
  if (!isDemoDataset(data.meta?.datasetId)) return data;
  return { ...data, meta: { ...data.meta, demoPresentation: true },
    equipment: { ...data.equipment, ...demoSummary({ ...data.equipment, id: "1" }), id: data.equipment.id },
    trend: data.trend ? { ...data.trend, analysis: { ...data.trend.analysis, status: "rising", isRising: true } } : null,
    fftWeeklyDiagnosis: { ...data.fftWeeklyDiagnosis, demoPresentation: true, state: "caution", label: "Unbalance · 속도 알람",
      representative: { cause: "unbalance", causeLabel: "Unbalance", grade: "속도 알람", unit: "mm/s" }, limitation: null },
  };
}

export function demoRelatedHistory(items, until) {
  return items.filter((item) => isDemoDataset(item.datasetId) && item.fault === "축"
    && item.faultType === "Unbalance" && (!until || item.date <= until))
    .sort((a, b) => String(b.date).localeCompare(String(a.date)));
}

export function demoAiAnalysis() {
  return { demoPresentation: true, analysis: {
    headline: "속도 알람과 진동 우상향이 함께 나타나 축 불평형(Unbalance)의 진행 가능성이 있습니다. 동일 설비의 과거 Unbalance 이력을 함께 검토하고, 회전체 상태 확인과 운전 조건을 맞춘 재측정을 우선 권장합니다.",
    trendSummary: "진동 속도에서 우상향 경향이 감지되었습니다. 일시적인 운전 조건 변화와 지속적인 진동 증가를 구분하기 위해 동일 회전수·부하 조건에서 추세를 재확인하고, 속도 알람의 반복 여부를 함께 점검해야 합니다.",
    fftSummary: "현재 주파수 상태는 속도 알람이며 대표 원인은 Unbalance입니다. 회전 1X 성분이 우세하고 2X·3X의 기여가 상대적으로 낮은 불평형 시나리오로, 회전체의 질량 편차나 부착물에 의한 불균형을 우선 확인하는 것이 적절합니다.",
    fftReferenceRecordIds: [],
    trendFindings: [{ heading: "우상향 판정: true", detail: "속도 알람과 진동 상승 경향이 동시에 나타나므로 반복 측정을 통해 상승의 지속 여부를 확인할 필요가 있습니다." }],
    fftFindings: [{ heading: "속도 알람 · Unbalance", detail: "회전 주파수 성분이 지배적인 불평형 패턴입니다. 1X 우세만으로 축 정렬 불량을 단정하지 않으며, 정렬 점검은 2X·3X와 운전 조건을 함께 확인한 뒤 판단합니다." }],
    historyFindings: [{ heading: "동일 설비의 Unbalance 진단 이력", detail: "연관 과거 이력에도 축 불평형이 기록되어 있습니다. 이전 점검·조치 내용과 현재 운전 조건을 비교해 재발 가능성과 조치 효과를 확인하는 것이 필요합니다." }],
    likelyCauses: [{ cause: "회전체 질량 불균형(Unbalance)", confidence: "medium", rationale: "속도 알람, 우상향 경향, 과거 동일 유형의 진단 이력이 함께 나타나는 시나리오입니다. 부착물, 마모 또는 밸런스 변화가 가능한 원인이지만 현장 확인이 필요합니다." }],
    counterEvidence: ["속도 진동은 회전수·부하·체결 상태의 변화에도 영향을 받습니다. 동일 운전 조건의 재측정과 현장 점검 없이 불평형 원인을 확정할 수 없습니다."],
    recommendedActions: [
      { action: "운전 조건을 맞춰 진동 재측정", priority: "high", rationale: "동일 회전수·부하에서 속도 알람과 상승 경향이 반복되는지 확인하고, 회전 1X 및 고조파를 비교합니다." },
      { action: "회전체 부착물·마모·밸런스 상태 점검", priority: "high", rationale: "질량 편차를 유발할 수 있는 부착물과 마모, 밸런스 웨이트 및 체결 상태를 확인합니다. 불평형이 확인되면 청소·보수 후 밸런싱을 검토합니다." },
      { action: "과거 조치 전후 결과와 비교", priority: "planned", rationale: "이전 Unbalance 점검과 조치 결과를 참고해 재발 요인을 확인하고, 이번 조치 후 동일 조건으로 진동 개선 여부를 검증합니다." },
    ],
  } };
}
