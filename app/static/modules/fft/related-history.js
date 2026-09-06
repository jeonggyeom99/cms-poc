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

function relatedHistoryCard(item) {
  const card = element("article", "related-history-card");
  const heading = element("div", "related-history-card-heading");
  const date = element("time", "related-history-date", displayDate(item.date));
  date.dateTime = item.date;
  const tags = element("div", "related-history-card-tags");
  tags.append(
    element("span", "related-history-tag related-history-tag-category", item.fault),
    element("span", "related-history-tag", item.faultType),
  );
  heading.append(date, tags);

  const equipment = element("strong", "related-history-equipment", item.equipmentName);
  const metadata = element("p", "related-history-metadata", `${item.process} · 센서 ${item.sensorNumber}`);
  const button = element("button", "related-history-detail-button", expandedHistoryId === item.id ? "상세 접기" : "상세 보기");
  button.type = "button";
  button.dataset.relatedHistoryId = item.id;
  button.setAttribute("aria-expanded", String(expandedHistoryId === item.id));
  button.setAttribute("aria-controls", `related-history-detail-${item.id}`);
  card.append(heading, equipment, metadata, button);

  if (expandedHistoryId === item.id) {
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
  relatedHistory = items;
  section.hidden = !tag || !items.length;
  if (section.hidden) return;

  count.textContent = `${items.length.toLocaleString("ko-KR")}건`;
  list.replaceChildren(...items.map(relatedHistoryCard));
}

export function bindRelatedHistory() {
  document.getElementById("fft-related-history").addEventListener("click", (event) => {
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
