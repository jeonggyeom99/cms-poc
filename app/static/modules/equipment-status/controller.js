import { fetchDatasetSummaries } from "../api/dashboard.js?v=demo-unbalance-v1";

const STATE_DETAILS = {
  normal: { label: "정상", description: "정상 상태입니다." },
  attention: { label: "주의", description: "주의가 필요한 상태입니다." },
  critical: { label: "심각", description: "즉시 확인이 필요한 상태입니다." },
  unknown: { label: "판단 불가", description: "상태를 판단할 Trend 이력이 충분하지 않습니다." },
};
const LIVE_STATE_BY_DATASET_STATUS = { normal: "normal", caution: "attention", unknown: "unknown" };
const STATE_PRIORITY = { normal: 0, unknown: 1, attention: 2, critical: 3 };
const CRITICAL_EQUIPMENT = new Set(["3전기강판|3DNL|V056"]);
const FACTORY_GROUP_ORDER = ["냉연", "전강", "전기강판", "열연", "선재", "연주", "고로", "제강", "FINEX", "APL"];

let equipmentItems = [];
let selectedGroupKey = null;

function groupKey(item) {
  return JSON.stringify([item.factory, item.process, item.equipmentType || item.type, item.name]);
}

function element(tagName, className, text) {
  const node = document.createElement(tagName);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function select(id) { return document.getElementById(id); }
function normalizedCode(code) { return typeof code === "string" ? code.trim().toUpperCase() : ""; }
function factorySort(left, right) {
  const group = (name) => name === "1냉연" ? 0 : name.includes("전강") || name.includes("전기강판") ? 1 : /^STS.*냉연/.test(name) ? 2 : FACTORY_GROUP_ORDER.findIndex((item) => name.includes(item)) + 10;
  return group(left) - group(right) || left.localeCompare(right, "ko", { numeric: true });
}
function unique(items, key) {
  return [...new Set(items.map((item) => item[key]).filter(Boolean))].sort((left, right) => left.localeCompare(right, "ko"));
}

function matchingSummary(item, summariesByCode) {
  const summary = summariesByCode.get(normalizedCode(item.tag));
  if (!summary) return null;
  const code = normalizedCode(item.tag);
  if (code === "V041") return item.factory === "1냉연" && item.process === "1CAL" && item.location.includes("3-4") ? summary : null;
  if (code === "V191") return item.factory === "1냉연" && item.process === "1CAL" && item.name.includes("NO.1 DUST COLLECT FAN") ? summary : null;
  if (code === "V056") return item.name === summary.name ? summary : null;
  return null;
}

function createEquipmentItems(summaries) {
  const byCode = new Map(summaries.map((item) => [normalizedCode(item.equipmentCode), item]));
  const source = Array.isArray(window.equipmentExcelData) ? window.equipmentExcelData : [];
  const items = source.map((item) => {
    const equipmentCode = normalizedCode(item.tag);
    const summary = matchingSummary(item, byCode);
    const isForcedCritical = CRITICAL_EQUIPMENT.has(`${item.factory}|${item.process}|${equipmentCode}`);
    const state = isForcedCritical
      ? "critical"
      : summary
        ? (LIVE_STATE_BY_DATASET_STATUS[summary.status] ?? "unknown")
        : "normal";
    return { ...item, equipmentCode, datasetId: summary?.id ?? null, isLive: Boolean(summary), state, stateLabel: STATE_DETAILS[state].label, stateDescription: summary?.statusDescription || STATE_DETAILS[state].description };
  });
  const includedCodes = new Set(items.filter((item) => item.isLive).map((item) => item.equipmentCode));
  summaries.forEach((summary) => {
    const equipmentCode = normalizedCode(summary.equipmentCode);
    if (!equipmentCode || includedCodes.has(equipmentCode)) return;
    const state = LIVE_STATE_BY_DATASET_STATUS[summary.status] ?? "unknown";
    items.push({
      factory: (summary.plant || "CMS 설비").replaceAll(" ", ""),
      process: summary.line || "기타",
      equipmentType: "기타",
      name: summary.displayName || summary.name || equipmentCode,
      location: summary.measurementPoint || "측정위치 미상",
      tag: equipmentCode,
      equipmentCode,
      datasetId: summary.id,
      isLive: true,
      state,
      stateLabel: STATE_DETAILS[state].label,
      stateDescription: summary.statusDescription || STATE_DETAILS[state].description,
    });
  });
  return items;
}

function populateOptions() {
  const factory = select("equipment-status-factory");
  const process = select("equipment-status-process");
  const type = select("equipment-status-type");
  factory.replaceChildren(new Option("전체", "all"), ...unique(equipmentItems, "factory").sort(factorySort).map((value) => new Option(value, value)));
  process.replaceChildren(new Option("전체", "all"), ...unique(equipmentItems, "process").map((value) => new Option(value, value)));
  type.replaceChildren(new Option("전체", "all"), ...unique(equipmentItems, "equipmentType").map((value) => new Option(value, value)));
}

function filteredItems() {
  const factory = select("equipment-status-factory").value;
  const process = select("equipment-status-process").value;
  const type = select("equipment-status-type").value;
  const state = select("equipment-status-state").value;
  const name = select("equipment-status-name").value.trim().toLocaleLowerCase("ko");
  return equipmentItems.filter((item) => (
    (factory === "all" || item.factory === factory)
    && (process === "all" || item.process === process)
    && (type === "all" || item.equipmentType === type)
    && (state === "all" || item.state === state)
    && (!name || item.name.toLocaleLowerCase("ko").includes(name))
  ));
}

function groupedItems(items) {
  const groups = new Map();
  items.forEach((item) => {
    const key = [item.factory, item.process, item.equipmentType, item.name].join("|");
    const group = groups.get(key) ?? { ...item, sensors: [], state: "normal" };
    group.sensors.push(item);
    if (STATE_PRIORITY[item.state] > STATE_PRIORITY[group.state]) group.state = item.state;
    groups.set(key, group);
  });
  return [...groups.values()];
}

function createSensor(sensor) {
  const node = sensor.isLive ? element("a", "equipment-status-sensor") : element("div", "equipment-status-sensor");
  if (sensor.isLive) node.href = `/dashboard2?dataset=${encodeURIComponent(sensor.datasetId)}`;
  node.append(
    element("i", `equipment-status-sensor__dot equipment-status-sensor__dot--${sensor.state}`),
    element("span", null, `${sensor.equipmentCode || "-"} · ${sensor.location || "측정위치 미상"}`),
    element("em", `equipment-status-sensor__state equipment-status-sensor__state--${sensor.state}`, STATE_DETAILS[sensor.state].label),
  );
  return node;
}

function createGroup(group) {
  const details = element("details", "equipment-status-equipment");
  const summary = element("summary", "equipment-status-equipment__summary equipment-status-item");
  summary.dataset.groupKey = groupKey(group);
  summary.setAttribute("aria-current", String(summary.dataset.groupKey === selectedGroupKey));
  const content = element("div", "equipment-status-item__details");
  content.append(element("strong", null, group.name), element("small", null, `${group.factory} · ${group.process} · ${group.equipmentType} · 센서 ${group.sensors.length}개`));
  summary.append(element("span", `equipment-status-dot equipment-status-dot--${group.state}`), content, element("span", `equipment-status-label equipment-status-label--${group.state}`, STATE_DETAILS[group.state].label));
  const sensors = element("div", "equipment-status-sensors");
  group.sensors.forEach((sensor) => sensors.append(createSensor(sensor)));
  details.append(summary, sensors);
  return details;
}

function renderEquipmentList() {
  const list = select("equipment-status-list");
  const groups = groupedItems(filteredItems());
  if (groups.length === 1) selectedGroupKey = groupKey(groups[0]);
  else if (!groups.some((group) => groupKey(group) === selectedGroupKey)) selectedGroupKey = null;
  select("equipment-status-count").textContent = `${groups.length}개 설비`;
  list.replaceChildren();
  if (!groups.length) list.append(element("p", "equipment-status-empty", "조건에 맞는 설비가 없습니다."));
  else groups.forEach((group) => list.append(createGroup(group)));
  list.removeAttribute("aria-busy");
  syncTreeSelection();
}

function syncTreeSelection() {
  const hasResults = Boolean(select("equipment-status-list").querySelector("details"));
  const selected = equipmentItems.find((item) => groupKey(item) === selectedGroupKey);
  const path = selected ? { factory: selected.factory, process: selected.process, type: selected.equipmentType, name: selected.name } : {
    factory: select("equipment-status-factory").value,
    process: select("equipment-status-process").value,
    type: select("equipment-status-type").value,
    name: select("equipment-status-name").value.trim(),
  };
  select("equipment-status-tree").querySelectorAll("[data-factory]").forEach((node) => {
    const matches = hasResults && ["factory", "process", "type", "name"].every((key) => (node.dataset[key] || "") === (path[key] || ""));
    node.setAttribute("aria-current", String(matches));
    if (matches) {
      let ancestor = node.tagName === "SUMMARY" ? node.parentElement.parentElement : node.parentElement;
      while (ancestor && ancestor !== select("equipment-status-tree")) {
        if (ancestor.tagName === "DETAILS") ancestor.open = true;
        ancestor = ancestor.parentElement;
      }
    }
  });
}

function healthState(factory, process, type, name) {
  const items = equipmentItems.filter((item) => (!factory || item.factory === factory) && (!process || item.process === process) && (!type || item.equipmentType === type) && (!name || item.name === name));
  return items.reduce((state, item) => STATE_PRIORITY[item.state] > STATE_PRIORITY[state] ? item.state : state, "normal");
}

function treeNode(label, children, depth, path = {}) {
  const factory = depth === 1 ? label : path.factory;
  const process = depth === 2 ? label : path.process;
  const type = depth === 3 ? label : path.type;
  const details = element("details");
  const summary = element("summary");
  Object.assign(summary.dataset, { factory: factory || "all", process: process || "all", type: type || "all" });
  summary.append(element("span", `equipment-status-tree__health equipment-status-tree__health--${healthState(factory, process, type)}`), document.createTextNode(label));
  const descendants = element("div", "equipment-status-tree__children");
  if (depth === 3) {
    children.forEach((name) => {
      const button = element("button", null, name);
      button.type = "button";
      Object.assign(button.dataset, { factory, process, type, name });
      button.prepend(element("span", `equipment-status-tree__health equipment-status-tree__health--${healthState(factory, process, type, name)}`));
      descendants.append(button);
    });
  } else Object.entries(children).forEach(([childLabel, value]) => descendants.append(treeNode(childLabel, value, depth + 1, { factory, process, type })));
  details.append(summary, descendants);
  return details;
}

function renderTree() {
  const tree = select("equipment-status-tree");
  const sourceTree = structuredClone(window.equipmentTreeData || {});
  equipmentItems.forEach((item) => {
    const factory = sourceTree[item.factory] ||= {};
    const process = factory[item.process] ||= {};
    const names = process[item.equipmentType] ||= [];
    if (!names.includes(item.name)) names.push(item.name);
  });
  const factories = new Set(Object.keys(sourceTree));
  equipmentItems.forEach((item) => factories.add(item.factory));
  tree.replaceChildren(...[...factories].sort(factorySort).map((factory) => treeNode(factory, sourceTree[factory] || {}, 1)));
}

function bindFilters() {
  const filterIds = ["equipment-status-factory", "equipment-status-process", "equipment-status-type", "equipment-status-state"];
  const applyFilters = () => { selectedGroupKey = null; renderEquipmentList(); };
  filterIds.forEach((id) => select(id).addEventListener("change", applyFilters));
  select("equipment-status-name").addEventListener("input", applyFilters);
  select("equipment-status-reset").addEventListener("click", () => {
    filterIds.forEach((id) => { select(id).value = "all"; });
    select("equipment-status-name").value = "";
    selectedGroupKey = null;
    renderEquipmentList();
  });
  select("equipment-status-tree").addEventListener("click", (event) => {
    const target = event.target.closest("[data-factory]");
    if (!target) return;
    select("equipment-status-factory").value = target.dataset.factory || "all";
    select("equipment-status-process").value = target.dataset.process || "all";
    select("equipment-status-type").value = target.dataset.type || "all";
    select("equipment-status-name").value = target.dataset.name || "";
    selectedGroupKey = null;
    renderEquipmentList();
  });
  select("equipment-status-list").addEventListener("click", (event) => {
    const summary = event.target.closest("summary[data-group-key]");
    if (!summary) return;
    selectedGroupKey = summary.dataset.groupKey;
    select("equipment-status-list").querySelectorAll("summary[data-group-key]").forEach((node) => {
      node.setAttribute("aria-current", String(node === summary));
    });
    syncTreeSelection();
  });
}

function setNotice(message) {
  const notice = select("equipment-status-notice");
  notice.textContent = message;
  notice.hidden = !message;
}

export async function initializeEquipmentStatusPage() {
  bindFilters();
  try {
    equipmentItems = createEquipmentItems(await fetchDatasetSummaries());
    if (!equipmentItems.length) setNotice("설비 분류 데이터를 불러오지 못했습니다.");
  } catch (error) {
    console.error("Equipment status list loading failed", error);
    equipmentItems = createEquipmentItems([]);
    setNotice("CMS 상세 데이터를 불러오지 못해 설비 분류만 표시합니다.");
  }
  populateOptions();
  const requestedFactory = new URLSearchParams(window.location.search).get("factory");
  const normalizedRequestedFactory = requestedFactory?.replaceAll(" ", "");
  const factoryOption = [...select("equipment-status-factory").options].find((option) => option.value.replaceAll(" ", "") === normalizedRequestedFactory);
  if (factoryOption) {
    select("equipment-status-factory").value = factoryOption.value;
  }
  renderTree();
  renderEquipmentList();
  document.querySelectorAll(".equipment-status-search input, .equipment-status-search select, .equipment-status-search button").forEach((node) => { node.disabled = false; });
}

window.addEventListener("DOMContentLoaded", initializeEquipmentStatusPage);
