// Presentation-only scenario for the demo branch. API responses and CSVs stay intact.
export const isDemoDataset = (id) => ["1", "5"].includes(String(id));

export function demoSummary(item) {
  if (String(item.id) === "5") return { ...item, status: "caution", statusLabel: "속도 알람 · 베어링 내륜(BPFI)",
    statusDescription: "진동 상승과 내륜 결함 주파수 피크가 확인되어 센서 및 베어링 점검이 필요합니다.", statusColor: "#f1a526" };
  return String(item.id) === "1" ? { ...item, status: "caution", statusLabel: "속도 알람 · Unbalance",
    statusDescription: "속도 알람과 우상향 경향이 확인되어 축 불평형 점검이 필요합니다.", statusColor: "#f1a526" } : item;
}

export function demoFftRecord(fft, datasetId) {
  if (String(datasetId) !== "1" || fft?.metadata?.measureMode?.code !== "3") return fft;
  return { ...fft, analysis: { ...fft.analysis, diagnosis: { ...fft.analysis?.diagnosis,
    status: "anomaly", diagnosis: "unbalance", label: "Unbalance",
    message: "회전 1X 성분이 우세한 축 불평형(Unbalance) 상태입니다.",
  } } };
}

export function demoDashboard(data) {
  if (!isDemoDataset(data.meta?.datasetId)) return data;
  if (String(data.meta.datasetId) === "5") return { ...data,
    meta: { ...data.meta, demoPresentation: true },
    equipment: { ...data.equipment, ...demoSummary({ ...data.equipment, id: "5" }), id: data.equipment.id },
  };
  return { ...data, meta: { ...data.meta, demoPresentation: true },
    equipment: { ...data.equipment, ...demoSummary({ ...data.equipment, id: "1" }), id: data.equipment.id },
    trend: data.trend ? { ...data.trend, analysis: { ...data.trend.analysis, status: "rising", isRising: true } } : null,
    fftWeeklyDiagnosis: { ...data.fftWeeklyDiagnosis, demoPresentation: true, state: "caution", label: "Unbalance · 속도 알람",
      representative: { cause: "unbalance", causeLabel: "Unbalance", grade: "속도 알람", unit: "mm/s" }, limitation: null },
  };
}

export function demoRelatedHistory(items, until) {
  return items.filter((item) => String(item.datasetId) === "1" && item.fault === "축"
    && item.faultType === "Unbalance" && (!until || item.date <= until))
    .sort((a, b) => String(b.date).localeCompare(String(a.date)))
    .map((item) => ({ ...item, datasetId: "2", demoRelated: true,
      equipmentName: "3DNL Cleaning Unit Fume Exhaust Fan · Motor DE",
      process: "3 전기강판 3DNL", sensorNumber: "56", equipmentCode: "V056",
      issue: "속도 진동 증가와 회전 1X 성분 우세로 축 불평형(Unbalance) 점검이 필요했던 유사 사례입니다.",
      analysis: "회전체 부착물과 질량 불균형을 우선 확인하고, 동일 회전수·부하에서 진동을 비교하도록 권고한 사례입니다.",
      result: "Unbalance 점검 대상 · 2번 데이터셋에서 관련 그래프 확인",
      feedback: "회전체 상태와 밸런스를 점검한 뒤 동일 조건으로 재측정하여 변화 여부를 확인합니다.",
    }));
}

export function demoAiAnalysis(datasetId = "1") {
  if (String(datasetId) === "5") return { demoPresentation: true, analysis: {
    headline: "NO.1 DUST COLLECT FAN의 속도 알람과 우상향 경향, 베어링 내륜(BPFI) 주파수 피크가 함께 확인됩니다. 내륜 손상 가능성을 우선 점검하고, 센서 상태 확인과 동일 운전 조건의 재측정 후 베어링 정비 여부를 판단하는 것이 적절합니다.",
    trendSummary: "2026년 5월 26일 최신 진동 속도는 8.88 mm/s로 현재 CSV의 주의 기준 6 mm/s를 초과하며 위험 기준 12 mm/s 미만입니다. 5월 24일부터 우상향 경향이 검출되었고 최신 가속도는 5.37 g입니다. 동일 회전수·부하에서 속도와 가속도 추세를 함께 확인해야 합니다.",
    fftSummary: "5월 25일 가속도 ENV에서 BPFI 이론 주파수 143.21 Hz 부근인 141.25 Hz에 0.788 g 피크가 확인됩니다. 최근 7일 BPFI 이상은 2건·2점으로 BPFO·BSF·FTF 각 1건·1점보다 많아 대표 원인은 내륜, 등급은 초기 결함입니다. 2026년 4월 27일 진단 PPT의 내륜 141.5 Hz·2.1 g 및 센서·베어링 점검/교체 권고는 과거 진단 근거이며 현재 피크값과 구분해야 합니다. 고조파 일부 누락이 있어 전체 손상 확대나 즉시 교체를 이번 FFT만으로 확정할 수 없습니다.",
    fftReferenceRecordIds: [],
    trendFindings: [{ heading: "속도 주의 알람 · 우상향", detail: "최신 속도 8.88 mm/s와 5월 24일 상승 검출을 근거로 반복 알람 및 상승 지속 여부를 확인합니다." }],
    fftFindings: [{ heading: "베어링 내륜(BPFI) · 초기 결함", detail: "ENV 141.25 Hz의 0.788 g 피크가 BPFI 이론값 부근에 있으며, 주간 발생 횟수와 누적 점수도 내륜이 가장 높습니다." }],
    historyFindings: [{ heading: "과거 진단과 현재 근거 비교", detail: "4월 27일 PPT에는 속도 4.9 mm/s·가속도 8.6 g와 내륜 결함 진단이 있습니다. 같은 날짜의 CSV 진단 이력은 외륜(BPFO) 초기 손상과 급유 후 계획 교체를 기록하므로, 두 자료의 차이는 현장 점검으로 확인해야 합니다." }],
    likelyCauses: [{ cause: "베어링 내륜 손상(BPFI)", confidence: "medium", rationale: "현재 ENV 피크와 주간 집계, 과거 PPT 진단이 내륜 점검을 지지하지만 손상 정도와 확대 여부는 현장 확인이 필요합니다." }],
    counterEvidence: ["과거 CSV 이력은 BPFO를 기록하며 현재에도 다른 결함 성분이 관찰됩니다. 운전 조건·센서 체결 상태와 고조파 일부 누락을 고려해야 합니다."],
    recommendedActions: [
      { action: "센서 체결 및 측정 상태 확인", priority: "high", rationale: "센서 부착·체결과 측정 조건을 점검해 진동 증가와 충격 신호의 재현성을 확인합니다." },
      { action: "베어링 내륜·윤활 상태 점검", priority: "high", rationale: "BPFI 성분과 온도·소음·윤활 상태를 함께 점검하고, 손상이 확인되면 정비 또는 교체 일정을 검토합니다." },
      { action: "동일 운전 조건의 재측정 및 이력 비교", priority: "planned", rationale: "회전수와 부하를 맞춰 ENV 및 속도를 재측정하고, BPFO 이력과 내륜 진단 차이를 확인한 뒤 조치 전후 변화를 비교합니다." },
    ],
  } };
  return { demoPresentation: true, analysis: {
    headline: "속도 알람과 진동 우상향이 함께 나타나 축 불평형(Unbalance)의 진행 가능성이 있습니다. 유사 설비의 과거 Unbalance 이력을 함께 검토하고, 회전체 상태 확인과 운전 조건을 맞춘 재측정을 우선 권장합니다.",
    trendSummary: "진동 속도에서 우상향 경향이 감지되었습니다. 일시적인 운전 조건 변화와 지속적인 진동 증가를 구분하기 위해 동일 회전수·부하 조건에서 추세를 재확인하고, 속도 알람의 반복 여부를 함께 점검해야 합니다.",
    fftSummary: "현재 주파수 상태는 속도 알람이며 대표 원인은 Unbalance입니다. 회전 1X 성분이 우세하고 2X·3X의 기여가 상대적으로 낮은 불평형 시나리오로, 회전체의 질량 편차나 부착물에 의한 불균형을 우선 확인하는 것이 적절합니다.",
    fftReferenceRecordIds: [],
    trendFindings: [{ heading: "우상향 판정: true", detail: "속도 알람과 진동 상승 경향이 동시에 나타나므로 반복 측정을 통해 상승의 지속 여부를 확인할 필요가 있습니다." }],
    fftFindings: [{ heading: "속도 알람 · Unbalance", detail: "회전 주파수 성분이 지배적인 불평형 패턴입니다. 1X 우세만으로 축 정렬 불량을 단정하지 않으며, 정렬 점검은 2X·3X와 운전 조건을 함께 확인한 뒤 판단합니다." }],
    historyFindings: [{ heading: "유사 설비의 Unbalance 진단 이력", detail: "Fume Exhaust Fan의 Unbalance 사례에서는 회전체 부착물 제거와 임펠러 청소 후 밸런싱을 실시했습니다. 체결 상태를 보완하고 동일 운전 조건에서 진동을 재측정하여 조치 후 상태를 확인했습니다." }],
    likelyCauses: [{ cause: "회전체 질량 불균형(Unbalance)", confidence: "medium", rationale: "속도 알람, 우상향 경향, 유사 설비의 동일 유형 진단 이력이 함께 나타나는 시나리오입니다. 부착물, 마모 또는 밸런스 변화가 가능한 원인이지만 현장 확인이 필요합니다." }],
    counterEvidence: ["속도 진동은 회전수·부하·체결 상태의 변화에도 영향을 받습니다. 동일 운전 조건의 재측정과 현장 점검 없이 불평형 원인을 확정할 수 없습니다."],
    recommendedActions: [
      { action: "운전 조건을 맞춰 진동 재측정", priority: "high", rationale: "동일 회전수·부하에서 속도 알람과 상승 경향이 반복되는지 확인하고, 회전 1X 및 고조파를 비교합니다." },
      { action: "회전체 부착물·마모·밸런스 상태 점검", priority: "high", rationale: "질량 편차를 유발할 수 있는 부착물과 마모, 밸런스 웨이트 및 체결 상태를 확인합니다. 불평형이 확인되면 청소·보수 후 밸런싱을 검토합니다." },
      { action: "과거 조치 전후 결과와 비교", priority: "planned", rationale: "이전 Unbalance 점검과 조치 결과를 참고해 재발 요인을 확인하고, 이번 조치 후 동일 조건으로 진동 개선 여부를 검증합니다." },
    ],
  } };
}
