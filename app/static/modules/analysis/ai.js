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

export function resetAiAnalysis({ available, heading, detail }) {
  const { result, description, run, details } = elements();
  result.className = "result-chip unknown";
  result.textContent = "분석 대기";
  description.textContent = available
    ? "선택한 FFT, Trend, 설비 정보 및 연관 과거 이력을 종합해 분석합니다."
    : "FFT 데이터가 준비되면 AI 종합 분석을 실행할 수 있습니다.";
  setAction(run, "AI 분석 실행", !available);
  placeholder(
    details,
    heading || (available ? "선택한 FFT 기준으로 AI 분석을 실행할 수 있습니다." : "AI 분석에 사용할 FFT가 없습니다."),
    detail || (available ? "Trend, FFT, 설비 정보 및 과거 이력 요약을 서버에서 안전하게 분석합니다." : "설비 또는 FFT 레코드를 선택해 주세요."),
  );
}

export function setAiAnalysisLoading() {
  const { result, description, run, details } = elements();
  result.className = "result-chip unknown";
  result.textContent = "분석 중";
  description.textContent = "선택한 FFT 레코드의 Trend, FFT, 과거 이력 근거를 종합하고 있습니다.";
  setAction(run, "AI 분석 중...", true);
  placeholder(details, "AI 분석 중입니다.", "결과가 준비되면 이 영역에 표시합니다.");
  details.setAttribute("aria-busy", "true");
}

export function renderAiAnalysis(payload) {
  const { result, description, run, details } = elements();
  const analysis = payload.analysis;
  result.className = `result-chip ${riskClass(analysis.riskLevel)}`;
  result.textContent = analysis.riskLabel || "분석 완료";
  description.textContent = analysis.headline || "AI 종합 분석 결과";
  setAction(run, "다시 분석", false, true);

  const content = element("div", "ai-analysis-details");
  const groups = [
    listSection("Trend 근거", analysis.trendFindings, findingItem),
    listSection("FFT 근거", analysis.fftFindings, findingItem),
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

export function renderAiAnalysisError(message) {
  const { result, description, run, details } = elements();
  result.className = "result-chip unknown";
  result.textContent = "분석 불가";
  description.textContent = "AI 종합 분석을 완료하지 못했습니다.";
  setAction(run, "다시 시도", false);
  placeholder(details, "AI 분석을 실행하지 못했습니다.", message);
}

export function bindAiAnalysis(onRun) {
  const { run } = elements();
  run.addEventListener("click", () => {
    onRun(run.dataset.analysisCompleted === "true");
  });
}
