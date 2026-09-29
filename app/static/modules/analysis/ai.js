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

function limitationSection(baseline) {
  const diagnosis = baseline?.fft?.analysis?.diagnosis ?? {};
  const reason = diagnosis.bearing?.reason;
  if (reason !== "bearing_not_configured" && reason !== "bearing_not_found") return null;
  return listSection("데이터 제한", [{
    heading: reason === "bearing_not_configured" ? "베어링 모델 정보 누락" : "베어링 계수 마스터 미등록 또는 불일치",
    detail: reason === "bearing_not_configured"
      ? "베어링 모델 정보가 없어 FFT 베어링 결함 판정을 수행할 수 없습니다."
      : "베어링 계수 마스터에 일치 항목이 없어 FFT 베어링 결함 판정을 수행할 수 없습니다.",
  }], findingItem);
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
    ? "AI 분석 결과를 기다리고 있습니다."
    : "주파수 데이터가 준비되면 인공지능 종합 분석을 실행할 수 있습니다.";
  renderReference(reference, baseline);
  setAction(run, "다시 분석", !available);
  if (baseline?.fft) {
    placeholder(
      details,
      "AI 분석 대기",
      "선택한 주파수 기록을 바탕으로 AI 분석 결과를 준비하고 있습니다.",
    );
  }
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
  description.textContent = "AI 분석 결과를 분석하고 있습니다. 잠시만 기다려 주세요.";
  setAction(run, "인공지능 분석 중...", true);
  renderReference(reference, baseline);
  placeholder(
    details,
    "AI 분석 중",
    "선택한 주파수 기록을 바탕으로 AI 분석 결과를 생성하고 있습니다.",
  );
  details.setAttribute("aria-busy", "true");
}

export function renderAiAnalysis(payload, baseline = null) {
  const { result, description, run, details } = elements();
  const analysis = payload.analysis;
  result.className = `result-chip ${riskClass(analysis.riskLevel)}`;
  result.textContent = analysis.riskLabel || "분석 완료";
  description.textContent = analysis.headline;
  setAction(run, "다시 분석", false, true);

  const content = element("div", "ai-analysis-details");
  const groups = [
    limitationSection(baseline),
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
  result.textContent = "AI 진단 실패";
  description.textContent = "AI 진단을 불러오지 못했습니다. 다시 시도해 주세요.";
  renderReference(reference, baseline);
  setAction(run, "다시 시도", false);
  placeholder(details, "AI 진단 실패", message);
}

export function bindAiAnalysis(onRun) {
  const { run } = elements();
  run.addEventListener("click", () => {
    onRun(run.dataset.analysisCompleted === "true");
  });
}
