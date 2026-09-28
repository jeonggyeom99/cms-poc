function element(tagName, className, text) {
  const node = document.createElement(tagName);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function elements() {
  return {
    result: document.getElementById("ai-analysis-result"),
    description: document.getElementById("ai-analysis-description"),
    run: document.getElementById("ai-analysis-run"),
    details: document.getElementById("ai-analysis-details"),
    reference: document.getElementById("ai-analysis-reference"),
  };
}

function setAction(run, label, disabled, completed = false) {
  run.textContent = label;
  run.disabled = disabled;
  run.dataset.analysisCompleted = String(completed);
}

function placeholder(details, heading, detail) {
  details.className = "analysis-placeholder ai-analysis-placeholder";
  details.removeAttribute("aria-busy");
  details.replaceChildren(
    element("strong", null, heading),
    element("p", null, detail),
  );
}

function value(value, fallback = "확인 불가") {
  return value === null || value === undefined || value === "" ? fallback : value;
}

function baselineSections(baseline) {
  if (!baseline?.fft) return [];
  const dashboard = baseline.dashboard ?? {};
  const trend = dashboard.trend ?? {};
  const trendAnalysis = trend.analysis ?? {};
  const velocity = (trend.metrics ?? []).find((metric) => metric.key === "velocity") ?? trend.metrics?.[0];
  const level = dashboard.levelAnalysis ?? {};
  const diagnosis = baseline.fft.analysis?.diagnosis ?? {};
  const spectrum = baseline.fft.analysis?.spectrum ?? {};
  const selectedFault = diagnosis.faults?.find((fault) => fault.type === baseline.selectedFaultType)
    ?? diagnosis.faults?.find((fault) => fault.type === diagnosis.defaultFaultType);

  const findings = [
    {
      heading: "추세 분석",
      detail: `상태 ${value(trendAnalysis.status)} · 최신 ${value(velocity?.latestValue)} ${velocity?.unit ?? ""} · 표본 ${value(trendAnalysis.usedPoints, trend.points?.length ?? 0)}건`,
    },
    {
      heading: "기준값 분석",
      detail: level.status === "unavailable"
        ? "최근 추세 데이터가 부족해 권고 기준값을 산출하지 못했습니다."
        : `권고 주의 ${value(level.recommended?.warningThreshold)} mm/s · 권고 위험 ${value(level.recommended?.dangerThreshold)} mm/s`,
    },
    {
      heading: "주파수 분석",
      detail: selectedFault
        ? `${selectedFault.type} ${selectedFault.label ?? ""} · 이상 ${selectedFault.hasAnomaly ? "감지" : "미감지"}`
        : `${value(diagnosis.label, diagnosis.message)} · 유의 피크 ${spectrum.peaks?.length ?? 0}개`,
    },
  ];
  return [listSection("규칙 기반 분석 근거", findings, findingItem)];
}

function renderBaseline(details, baseline, notice = null) {
  const content = element("div", "ai-analysis-details");
  baselineSections(baseline).filter(Boolean).forEach((section) => content.append(section));
  if (notice) {
    const section = element("section", "ai-analysis-section ai-analysis-notice");
    section.append(element("h3", null, notice.heading), element("p", null, notice.detail));
    content.append(section);
  }
  details.className = "ai-analysis-details";
  details.replaceChildren(content);
}

function renderReference(reference, baseline) {
  reference.textContent = baseline?.fft?.measuredAt
    ? `진단 기준 측정일시 ${baseline.fft.measuredAt}`
    : "진단 기준 측정일시 --";
}

function riskClass(riskLevel) {
  return ["normal", "caution", "danger"].includes(riskLevel) ? riskLevel : "unknown";
}

function listSection(title, items, createItem) {
  if (!Array.isArray(items) || !items.length) return null;
  const section = element("section", "ai-analysis-section");
  section.append(element("h3", null, title));
  const list = element("ul", "ai-analysis-list");
  items.forEach((item) => list.append(createItem(item)));
  section.append(list);
  return section;
}

function findingItem(finding) {
  const item = element("li", "ai-analysis-finding");
  item.append(
    element("strong", null, finding.heading || "분석 근거"),
    element("p", null, finding.detail || "--"),
  );
  return item;
}

function causeItem(cause) {
  const item = element("li", "ai-analysis-cause");
  const heading = element("div", "ai-analysis-item-heading");
  heading.append(
    element("strong", null, cause.cause || "가능 원인"),
    element("span", `ai-confidence ai-confidence-${cause.confidence || "low"}`, confidenceLabel(cause.confidence)),
  );
  item.append(heading, element("p", null, cause.rationale || "--"));
  return item;
}

function actionItem(action) {
  const item = element("li", "ai-analysis-action");
  const heading = element("div", "ai-analysis-item-heading");
  heading.append(
    element("strong", null, action.action || "점검 항목"),
    element("span", `ai-priority ai-priority-${action.priority || "planned"}`, priorityLabel(action.priority)),
  );
  item.append(heading, element("p", null, action.rationale || "--"));
  return item;
}

function textItem(value) {
  return element("li", "ai-analysis-text-item", value);
}

function confidenceLabel(value) {
  return { high: "높음", medium: "보통", low: "낮음" }[value] || "낮음";
}

function priorityLabel(value) {
  return { immediate: "즉시", high: "우선", planned: "계획" }[value] || "계획";
}

export function resetAiAnalysis({ available, heading, detail, baseline = null }) {
  const { result, description, run, details, reference } = elements();
  result.className = "result-chip unknown";
  result.textContent = "분석 대기";
  description.textContent = available
    ? "설비의 기본 주파수 기록, 추세, 기준값 및 연관 과거 이력을 종합해 분석합니다."
    : "주파수 데이터가 준비되면 인공지능 종합 분석을 실행할 수 있습니다.";
  renderReference(reference, baseline);
  setAction(run, "다시 분석", !available);
  if (baseline?.fft) renderBaseline(details, baseline);
  else placeholder(
      details,
      heading || "인공지능 분석에 사용할 주파수 기록이 없습니다.",
      detail || "설비 또는 주파수 기록을 선택해 주세요.",
    );
}

export function setAiAnalysisLoading(baseline) {
  const { result, description, run, details, reference } = elements();
  result.className = "result-chip unknown";
  result.textContent = "분석 중";
  description.textContent = "진단 기준 기록의 추세, 기준값, 주파수 및 과거 이력 근거를 종합하고 있습니다.";
  setAction(run, "인공지능 분석 중...", true);
  renderReference(reference, baseline);
  renderBaseline(details, baseline, {
    heading: "AI 분석 중",
    detail: "규칙 기반 근거를 유지한 상태로 인공지능 보강 결과를 기다리고 있습니다.",
  });
  details.setAttribute("aria-busy", "true");
}

export function renderAiAnalysis(payload) {
  const { result, description, run, details } = elements();
  const analysis = payload.analysis;
  result.className = `result-chip ${riskClass(analysis.riskLevel)}`;
  result.textContent = analysis.riskLabel || "분석 완료";
  description.textContent = analysis.headline || "인공지능 종합 분석 결과";
  setAction(run, "다시 분석", false, true);

  const content = element("div", "ai-analysis-details");
  const groups = [
    listSection("추세 근거", analysis.trendFindings, findingItem),
    listSection("주파수 근거", analysis.fftFindings, findingItem),
    listSection("과거 이력 근거", analysis.historyFindings, findingItem),
    listSection("가능 원인", analysis.likelyCauses, causeItem),
    listSection("반대 근거", analysis.counterEvidence, textItem),
    listSection("권장 점검", analysis.recommendedActions, actionItem),
  ];
  groups.filter(Boolean).forEach((group) => content.append(group));
  if (!content.childElementCount) {
    content.append(element("p", "ai-analysis-empty", "표시할 분석 근거가 없습니다."));
  }
  details.className = "ai-analysis-details";
  details.removeAttribute("aria-busy");
  details.replaceChildren(content);
}

export function renderAiAnalysisError(message, baseline) {
  const { result, description, run, details, reference } = elements();
  result.className = "result-chip unknown";
  result.textContent = "규칙 진단";
  description.textContent = "규칙 기반 진단을 표시합니다. 인공지능 보강은 완료하지 못했습니다.";
  renderReference(reference, baseline);
  setAction(run, "다시 시도", false);
  renderBaseline(details, baseline, { heading: "AI 보강 실패", detail: message });
}

export function bindAiAnalysis(onRun) {
  const { run } = elements();
  run.addEventListener("click", () => {
    onRun(run.dataset.analysisCompleted === "true");
  });
}
