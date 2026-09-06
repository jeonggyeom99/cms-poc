import { fetchDatasetSummaries } from "../api/dashboard.js?v=fft-load-fix";
import {
  equipmentStatusCatalog,
  featuredEquipmentCodes,
} from "./catalog.js?v=equipment-status-landing";

const STATE_DETAILS = {
  normal: {
    label: "정상",
    description: "정상 상태입니다.",
  },
  attention: {
    label: "주의",
    description: "주의가 필요한 상태입니다.",
  },
  critical: {
    label: "심각",
    description: "즉시 확인이 필요한 상태입니다.",
  },
  unknown: {
    label: "판단 불가",
    description: "상태를 판단할 Trend 이력이 충분하지 않습니다.",
  },
};

const LIVE_STATE_BY_DATASET_STATUS = {
  normal: "normal",
  caution: "attention",
  unknown: "unknown",
};

let equipmentItems = [];

function element(tagName, className, text) {
  const node = document.createElement(tagName);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function normalizedEquipmentCode(code) {
  return typeof code === "string" ? code.trim().toUpperCase() : "";
}

function displayMeasuredAt(value) {
  if (!value) return "최근 측정 데이터 없음";
  return value.replace(/:00$/, "");
}

function liveState(summary) {
  return LIVE_STATE_BY_DATASET_STATUS[summary.status] ?? "unknown";
}

function createLiveCatalogItem(catalogItem, summary) {
  const state = liveState(summary);
  const stateDetails = STATE_DETAILS[state];
  const sourceStatus = summary.statusLabel || stateDetails.label;
  const sourceDescription = summary.statusDescription || "";

  return {
    ...catalogItem,
    datasetId: summary.id,
    isLive: true,
    state,
    stateLabel: stateDetails.label,
    stateDescription: `CMS 상태: ${sourceStatus}${sourceDescription ? `. ${sourceDescription}` : ""}`,
    date: summary.lastMeasuredAt || catalogItem.date,
  };
}

function createDemoCatalogItem(catalogItem) {
  const stateDetails = STATE_DETAILS[catalogItem.state];
  return {
    ...catalogItem,
    datasetId: null,
    isLive: false,
    stateLabel: stateDetails.label,
    stateDescription: `${stateDetails.description} 데모 목록이며 상세 CSV 데이터가 없습니다.`,
  };
}

function createAdditionalLiveItem(summary, index) {
  const state = liveState(summary);
  const stateDetails = STATE_DETAILS[state];
  const sourceStatus = summary.statusLabel || stateDetails.label;
  const sourceDescription = summary.statusDescription || "";

  return {
    id: `csv-${summary.id}`,
    catalogIndex: equipmentStatusCatalog.length + index,
    date: summary.lastMeasuredAt,
    process: summary.plant || "CMS 설비",
    name: summary.displayName || summary.name || summary.equipmentCode,
    equipmentCode: summary.equipmentCode,
    datasetId: summary.id,
    isLive: true,
    state,
    stateLabel: stateDetails.label,
    stateDescription: `CMS 상태: ${sourceStatus}${sourceDescription ? `. ${sourceDescription}` : ""}`,
  };
}

function catalogSortKey(item) {
  const featuredIndex = featuredEquipmentCodes.indexOf(item.equipmentCode);
  return featuredIndex === -1
    ? featuredEquipmentCodes.length + item.catalogIndex
    : featuredIndex;
}

function mergeCatalogWithLiveData(summaries) {
  const summariesByCode = new Map();
  summaries.forEach((summary) => {
    const code = normalizedEquipmentCode(summary.equipmentCode);
    const matchingSummaries = summariesByCode.get(code) ?? [];
    matchingSummaries.push(summary);
    summariesByCode.set(code, matchingSummaries);
  });

  const displayedDatasetIds = new Set();
  const catalogItems = equipmentStatusCatalog.map((catalogItem) => {
    const matchingSummaries = summariesByCode.get(
      normalizedEquipmentCode(catalogItem.equipmentCode),
    );
    const summary = matchingSummaries?.at(-1);
    if (summary) displayedDatasetIds.add(summary.id);
    return summary ? createLiveCatalogItem(catalogItem, summary) : createDemoCatalogItem(catalogItem);
  });
  const additionalLiveItems = summaries
    .filter((summary) => !displayedDatasetIds.has(summary.id))
    .map(createAdditionalLiveItem);

  return [...catalogItems, ...additionalLiveItems].sort(
    (left, right) => catalogSortKey(left) - catalogSortKey(right),
  );
}

function populateProcessOptions(items) {
  const select = document.getElementById("equipment-status-process");
  const selectedValue = select.value;
  const processes = [...new Set(items.map((item) => item.process).filter(Boolean))].sort((left, right) => (
    left.localeCompare(right, "ko")
  ));

  select.replaceChildren(new Option("전체", "all"));
  processes.forEach((process) => select.add(new Option(process, process)));
  select.value = processes.includes(selectedValue) ? selectedValue : "all";
}

function currentFilteredItems() {
  const process = document.getElementById("equipment-status-process").value;
  const state = document.getElementById("equipment-status-state").value;

  return equipmentItems.filter((item) => (
    (process === "all" || item.process === process)
    && (state === "all" || item.state === state)
  ));
}

function createEquipmentItem(item) {
  const article = element(
    "article",
    `equipment-status-item equipment-status-item--${item.isLive ? "live" : "demo"}`,
  );
  article.setAttribute("role", "listitem");
  article.dataset.live = String(item.isLive);
  if (item.equipmentCode) article.dataset.equipmentCode = item.equipmentCode;

  const content = element(
    item.isLive ? "a" : "div",
    item.isLive ? "equipment-status-item__link" : "equipment-status-item__content",
  );
  if (item.isLive) {
    content.href = `/dashboard?dataset=${encodeURIComponent(item.datasetId)}`;
    content.dataset.dashboardLink = "true";
    content.setAttribute(
      "aria-label",
      `${item.name}, ${item.stateLabel}. 상세 대시보드 열기. ${item.stateDescription}`,
    );
  }
  const dot = element("span", `equipment-status-dot equipment-status-dot--${item.state}`);
  dot.setAttribute("aria-hidden", "true");

  const details = element("div", "equipment-status-item__details");
  details.append(element("strong", null, item.name));
  const metadata = element("small");
  metadata.append(document.createTextNode(
    `${displayMeasuredAt(item.date)} · ${item.process}${item.isLive ? ` · 데이터 #${item.datasetId}` : ""}`,
  ));
  if (!item.isLive) {
    metadata.append(document.createTextNode(" · "));
    metadata.append(element("span", "equipment-status-data-note", "상세 데이터 없음"));
  }
  details.append(metadata);

  const label = element(
    "span",
    `equipment-status-label equipment-status-label--${item.state}`,
    item.stateLabel,
  );
  label.title = item.stateDescription;

  content.append(dot, details, label);
  if (!item.isLive) {
    article.setAttribute("aria-label", `${item.name}, ${item.stateLabel}. ${item.stateDescription}`);
  }
  article.append(content);

  return article;
}

function renderEquipmentList() {
  const list = document.getElementById("equipment-status-list");
  const count = document.getElementById("equipment-status-count");
  const items = currentFilteredItems();

  count.textContent = `${items.length}개 설비`;
  list.replaceChildren();
  if (!items.length) {
    list.append(element("p", "equipment-status-empty", "조건에 맞는 설비가 없습니다."));
  } else {
    items.forEach((item) => list.append(createEquipmentItem(item)));
  }
  list.removeAttribute("aria-busy");
}

function setNotice(message) {
  const notice = document.getElementById("equipment-status-notice");
  notice.textContent = message;
  notice.hidden = !message;
}

function bindFilters() {
  const process = document.getElementById("equipment-status-process");
  const state = document.getElementById("equipment-status-state");
  const reset = document.getElementById("equipment-status-reset");

  process.addEventListener("change", renderEquipmentList);
  state.addEventListener("change", renderEquipmentList);
  reset.addEventListener("click", () => {
    process.value = "all";
    state.value = "all";
    renderEquipmentList();
  });
}

export async function initializeEquipmentStatusPage() {
  bindFilters();
  try {
    const summaries = await fetchDatasetSummaries();
    equipmentItems = mergeCatalogWithLiveData(summaries);
    if (!summaries.length) {
      setNotice("연결된 CSV 상세 데이터가 없어 Excel 진단 이력만 표시합니다.");
    }
  } catch (error) {
    console.error("Equipment status list loading failed", error);
    equipmentItems = mergeCatalogWithLiveData([]);
    setNotice("실시간 CMS 데이터를 불러오지 못해 Excel 진단 이력만 표시합니다.");
  }

  populateProcessOptions(equipmentItems);
  renderEquipmentList();
}

window.addEventListener("DOMContentLoaded", initializeEquipmentStatusPage);
