function element(tagName, className, text) {
  const node = document.createElement(tagName);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

let relatedHistory = [];
let relatedHistoryKey = null;
let expandedHistoryId = null;

export function relatedHistoryTag(fft, selectedFaultType = null) {
  const diagnosis = fft?.analysis?.diagnosis;
  if (diagnosis?.status !== "analyzed") return null;

  if (Array.isArray(diagnosis.faults)) {
    const fault = diagnosis.faults.find((item) => item.type === selectedFaultType)
      ?? diagnosis.faults.find((item) => item.type === diagnosis.defaultFaultType);
    if (!fault?.hasAnomaly) return null;
    return { fault: "베어링", faultType: fault.type };
  }

  const velocityFaultTypes = {
    unbalance: "Unbalance",
    misalignment: "Misalignment",
    complex: "Complex",
  };
  const faultType = velocityFaultTypes[diagnosis.diagnosis];
  return faultType ? { fault: "축", faultType } : null;
}

export function matchingHistoryItems(items, tag) {
  if (!tag) return [];
  return items.filter((item) => item.fault === tag.fault && item.faultType === tag.faultType);
}

export function resetRelatedHistoryExpansion() {
  expandedHistoryId = null;
}

function displayDate(value) {
  const [year, month, day] = String(value ?? "").split("-");
  return year && month && day ? `${year}.${month}.${day}` : "--";
}

function createGraphButton(item) {
  const graph = element("button", "related-history-graph-button", "그래프 보기");
  graph.type = "button";
  graph.disabled = !item.datasetId;
  const graphLabel = item.demoRelated ? "2번 데이터셋 최신 그래프 보기" : "진단일 기준 그래프 보기";
  graph.title = item.datasetId ? graphLabel : "연결된 대시보드 데이터가 없습니다.";
  graph.dataset.relatedDashboardDataset = item.datasetId ?? "";
  graph.dataset.relatedHistoryId = item.id;
  graph.setAttribute("aria-label", item.datasetId ? graphLabel : "연결된 그래프 데이터가 없습니다.");
  return graph;
}

function relatedHistoryCard(item) {
  const isExpanded = expandedHistoryId === item.id;
  const card = element("article", "related-history-card");
  card.classList.toggle("related-history-card--expanded", isExpanded);

  const summary = element("div", "related-history-card-summary");
  const button = element("button", "related-history-card-trigger");
  button.type = "button";
  button.dataset.relatedHistoryId = item.id;
  button.setAttribute("aria-expanded", String(isExpanded));
  button.setAttribute("aria-controls", `related-history-detail-${item.id}`);

  const date = element("time", "related-history-date", displayDate(item.date));
  date.dateTime = item.date;
  const content = element("span", "related-history-card-content");
  content.append(
    element("strong", "related-history-equipment", item.equipmentName),
    element("span", "related-history-metadata", `${item.process} · 센서 ${item.sensorNumber}`),
  );
  const tags = element("span", "related-history-card-tags");
  tags.append(
    element("span", "related-history-tag related-history-tag-category", item.fault),
    element("span", "related-history-tag", item.faultType),
  );
  const action = element("span", "related-history-card-action", isExpanded ? "상세 접기" : "상세 보기");
  const chevron = element("span", "related-history-card-chevron");
  chevron.setAttribute("aria-hidden", "true");
  button.append(date, content, tags, action, chevron);
  const actions = element("div", "related-history-card-actions");
  actions.append(createGraphButton(item));
  if (!item.datasetId) actions.append(element("span", "related-history-graph-unavailable", "그래프 데이터 없음"));
  summary.append(button, actions);
  card.append(summary);

  if (isExpanded) {
    const detail = element("div", "related-history-detail");
    detail.id = `related-history-detail-${item.id}`;
    detail.append(
      detailItem("현상", item.issue),
      detailItem("분석", item.analysis),
      detailItem("결과", item.result),
      detailItem("조치", item.feedback),
    );
    card.append(detail);
  }
  return card;
}

function detailItem(label, content) {
  const item = element("div", "related-history-detail-item");
  item.append(element("strong", null, label), element("p", null, content || "--"));
  return item;
}

export function renderRelatedHistory(tag, items) {
  const section = document.getElementById("fft-related-history");
  const count = document.getElementById("fft-related-history-count");
  const list = document.getElementById("fft-related-history-list");
  const key = tag ? `${tag.fault}:${tag.faultType}` : null;
  if (key !== relatedHistoryKey) expandedHistoryId = null;
  relatedHistoryKey = key;
  relatedHistory = Array.isArray(items) ? items : [];
  section.hidden = false;
  count.textContent = `${relatedHistory.length.toLocaleString("ko-KR")}건`;
  if (!relatedHistory.length) {
    list.replaceChildren(element("p", "related-history-empty", "일치하는 과거 이력이 없습니다."));
    return;
  }
  list.replaceChildren(...relatedHistory.map(relatedHistoryCard));
  if (relatedHistory.some((item) => item.demoRelated)) {
    const analysis = element("section", "graph-ai-analysis");
    analysis.setAttribute("aria-label", "연관 과거 이력 AI 분석");
    analysis.append(element("h3", null, "AI 분석"), element("p", null,
      "Fume Exhaust Fan의 Unbalance 사례에서는 회전체 부착물을 제거하고 임펠러를 청소한 뒤 밸런싱을 실시했습니다. 체결 상태를 보완하고 동일 운전 조건에서 진동을 재측정하여 조치 후 상태를 확인했습니다."));
    list.append(analysis);
  }
}

export function bindRelatedHistory() {
  document.getElementById("fft-related-history").addEventListener("click", (event) => {
    const graphButton = event.target.closest("[data-related-dashboard-dataset]");
    if (graphButton && !graphButton.disabled) {
      const item = relatedHistory.find((entry) => entry.id === graphButton.dataset.relatedHistoryId);
      if (item?.datasetId) {
        const query = new URLSearchParams({ dataset: item.datasetId });
        if (!item.demoRelated && item.date) query.set("until", item.date);
        window.location.href = `/dashboard2?${query}`;
      }
      return;
    }

    const button = event.target.closest("[data-related-history-id]");
    if (!button) return;
    expandedHistoryId = expandedHistoryId === button.dataset.relatedHistoryId
      ? null
      : button.dataset.relatedHistoryId;
    const tag = relatedHistoryKey
      ? { fault: relatedHistoryKey.split(":")[0], faultType: relatedHistoryKey.split(":")[1] }
      : null;
    renderRelatedHistory(tag, relatedHistory);
    document.querySelector(`[data-related-history-id="${button.dataset.relatedHistoryId}"]`)?.focus();
  });
}
