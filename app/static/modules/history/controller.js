import { fetchHistory } from "../api/history.js?v=cms-history-v1";

let historyItems = [];
let expandedHistoryId = null;

function element(tagName, className, text) {
  const node = document.createElement(tagName);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function displayValue(value, suffix = "") {
  return value === null || value === undefined || value === "" ? "—" : `${value}${suffix}`;
}

function displayDate(value) {
  const [year, month, day] = String(value).split("-");
  return year && month && day ? `${year}.${month}.${day}` : displayValue(value);
}

function normalizedSearchValue(value) {
  return String(value ?? "").trim().toLocaleLowerCase("ko");
}

function searchableText(item) {
  return [
    item.process,
    item.equipmentName,
    item.sensorNumber,
    item.issue,
    item.analysis,
    item.result,
    item.fault,
    item.faultType,
    item.feedback,
  ].map(normalizedSearchValue).join(" ");
}

function filteredItems() {
  const keyword = normalizedSearchValue(document.getElementById("history-keyword").value);
  const process = document.getElementById("history-process").value;
  return historyItems.filter((item) => (
    (process === "all" || item.process === process)
    && (!keyword || searchableText(item).includes(keyword))
  ));
}

function appendDefinition(list, label, value, suffix = "") {
  const wrapper = element("div");
  wrapper.append(element("dt", null, label), element("dd", null, displayValue(value, suffix)));
  list.append(wrapper);
}

function detailArticle(title, content, emphasized = false) {
  const article = element("article", emphasized ? "history-detail-card history-detail-card--result" : "history-detail-card");
  article.append(element("h3", null, title), element("p", null, displayValue(content)));
  return article;
}

function diagnosisTagClass(fault) {
  const category = {
    "베어링": "bearing",
    "축": "shaft",
    "기타": "other",
  }[fault] ?? "unknown";
  return `history-diagnosis-tag--${category}`;
}

function createDiagnosisTag(label, value, fault) {
  const tag = element("span", `history-diagnosis-tag ${diagnosisTagClass(fault)}`);
  tag.append(
    element("span", "history-diagnosis-tag__label", label),
    element("strong", null, displayValue(value)),
  );
  return tag;
}

function createGraphButton(item) {
  const graph = element("button", "history-graph-button", "그래프 보기");
  graph.type = "button";
  graph.disabled = !item.datasetId;
  graph.title = item.datasetId ? "진단일 기준 그래프 보기" : "연결된 대시보드 데이터가 없습니다.";
  graph.dataset.dashboardDataset = item.datasetId ?? "";
  graph.dataset.historyId = item.id;
  graph.setAttribute("aria-label", item.datasetId ? "진단일 기준 그래프 보기" : "연결된 그래프 데이터가 없습니다.");
  return graph;
}

function createDetailRow(item) {
  const row = element("tr", "history-detail-row");
  const cell = element("td");
  cell.colSpan = 6;

  const panel = element("div", "history-detail");
  panel.id = `history-detail-${item.id}`;
  panel.setAttribute("aria-label", `${item.equipmentName} 진단 상세`);

  const narrative = element("div", "history-detail-grid");
  narrative.append(
    detailArticle("현상 및 문제점", item.issue),
    detailArticle("분석 내용", item.analysis),
    detailArticle("분석 결과", item.result, true),
    detailArticle("피드백 및 조치", item.feedback),
  );

  const data = element("dl", "history-data-grid");
  appendDefinition(data, "추세 주요 인자", item.trend.factor);
  appendDefinition(data, "추세 파일명", item.trend.fileName);
  appendDefinition(data, "주파수 주요 인자", item.fft.factor);
  appendDefinition(data, "주파수 파일명", item.fft.fileName);
  appendDefinition(data, "주요 인자", item.primaryFactor);
  appendDefinition(data, "알람 발생 이력", item.alarmHistory);
  appendDefinition(data, "모터 용량", item.motorKw, item.motorKw === null ? "" : " kW");
  appendDefinition(data, "RPM", item.rpm);
  appendDefinition(data, "베어링 형번", item.bearingModel);

  panel.append(narrative, data);
  cell.append(panel);
  row.append(cell);
  return row;
}

function createSummaryRow(item) {
  const row = element("tr", "history-summary-row");
  row.dataset.historyId = item.id;
  const resultCell = element("td", "history-result");
  const resultTags = element("div", "history-result__tags");
  resultTags.append(
    createDiagnosisTag("결함", item.fault, item.fault),
    createDiagnosisTag("유형", item.faultType, item.fault),
  );
  resultCell.append(resultTags);
  row.append(
    element("td", "history-date", displayDate(item.date)),
    element("td", "history-process", item.process),
    element("td", "history-equipment", item.equipmentName),
    element("td", "history-sensor", item.sensorNumber),
    resultCell,
  );

  const actionCell = element("td", "history-action");
  const button = element(
    "button",
    "history-detail-button",
    expandedHistoryId === item.id ? "접기" : "상세",
  );
  button.type = "button";
  button.dataset.historyId = item.id;
  button.setAttribute("aria-controls", `history-detail-${item.id}`);
  button.setAttribute("aria-expanded", String(expandedHistoryId === item.id));
  const actions = element("div", "history-action__controls");
  actions.append(button, createGraphButton(item));
  if (!item.datasetId) actions.append(element("span", "history-graph-unavailable", "그래프 데이터 없음"));
  actionCell.append(actions);
  row.append(actionCell);
  return row;
}

function renderHistory() {
  const list = document.getElementById("history-list");
  const count = document.getElementById("history-count");
  const items = filteredItems();

  if (expandedHistoryId && !items.some((item) => item.id === expandedHistoryId)) {
    expandedHistoryId = null;
  }

  count.textContent = `${items.length}건`;
  list.replaceChildren();
  if (!items.length) {
    const row = element("tr");
    const cell = element("td", "history-empty", "조건에 맞는 이력이 없습니다.");
    cell.colSpan = 6;
    row.append(cell);
    list.append(row);
  } else {
    items.forEach((item) => {
      list.append(createSummaryRow(item));
      if (expandedHistoryId === item.id) list.append(createDetailRow(item));
    });
  }
  list.removeAttribute("aria-busy");
}

function populateProcessOptions(items) {
  const select = document.getElementById("history-process");
  const processes = [...new Set(items.map((item) => item.process).filter(Boolean))]
    .sort((left, right) => left.localeCompare(right, "ko"));
  select.replaceChildren(new Option("전체", "all"));
  processes.forEach((process) => select.add(new Option(process, process)));
}

function setNotice(message) {
  const notice = document.getElementById("history-notice");
  notice.textContent = message;
  notice.hidden = !message;
}

function bindControls() {
  const keyword = document.getElementById("history-keyword");
  const process = document.getElementById("history-process");
  const reset = document.getElementById("history-reset");
  const list = document.getElementById("history-list");

  keyword.addEventListener("input", renderHistory);
  process.addEventListener("change", renderHistory);
  reset.addEventListener("click", () => {
    keyword.value = "";
    process.value = "all";
    expandedHistoryId = null;
    renderHistory();
    keyword.focus();
  });
  list.addEventListener("click", (event) => {
    const graphButton = event.target.closest("[data-dashboard-dataset]");
    if (graphButton && !graphButton.disabled) {
      const item = historyItems.find((entry) => entry.id === graphButton.dataset.historyId);
      if (item) window.location.href = `/dashboard?dataset=${encodeURIComponent(item.datasetId)}&until=${encodeURIComponent(item.date)}`;
      return;
    }
    const button = event.target.closest("[data-history-id]");
    if (!button || !button.classList.contains("history-detail-button")) return;
    expandedHistoryId = expandedHistoryId === button.dataset.historyId
      ? null
      : button.dataset.historyId;
    renderHistory();
    document.querySelector(`[data-history-id="${button.dataset.historyId}"] .history-detail-button`)?.focus();
  });
}

export async function initializeHistoryPage() {
  bindControls();
  try {
    const payload = await fetchHistory();
    historyItems = payload.items;
    document.getElementById("history-source").textContent = `${payload.source} · 2026년`;
    populateProcessOptions(historyItems);
    renderHistory();
  } catch (error) {
    console.error("CMS history loading failed", error);
    setNotice(`과거 이력을 불러오지 못했습니다. ${error.message}`);
    renderHistory();
  }
}

window.addEventListener("DOMContentLoaded", initializeHistoryPage);
