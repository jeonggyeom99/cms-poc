import { fetchDatasetSummaries } from "../api/dashboard.js";
import { fetchHistory } from "../api/history.js";

const site = location.pathname === "/main_sv";
const detailPath = site ? "/dashboard" : "/dashboard2";
const historyPath = site ? "/history" : "/history2";
const state = (item) => item.status === "caution" ? "attention"
  : item.status === "normal" ? "normal" : item.status === "unknown" ? "unknown" : "critical";
const safe = (value) => String(value ?? "미지정").replace(/[&<>"']/g, (character) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[character]
));
const setText = (selector, value) => {
  const node = document.querySelector(selector);
  if (node) node.textContent = value;
};
const empty = (message) => `<p class="workspace-empty">${message}</p>`;
const detailUrl = (id) => `${detailPath}?dataset=${encodeURIComponent(id)}`;

function render(items, history) {
  const counts = { normal: 0, attention: 0, critical: 0, unknown: 0 };
  items.forEach((item) => counts[state(item)]++);
  setText("#total", items.length);
  setText("#ring-critical", counts.critical);
  setText("#ring-attention", counts.attention);
  setText("#ring-normal", counts.normal);
  setText("#risk-rate", `${Math.round((counts.critical + counts.attention) / Math.max(items.length, 1) * 100)}%`);
  setText("#history-count", history.length);
  // The CMS sidebar shows a team label; the legacy site sidebar has a clock.
  setText("#sidebar-time", new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" }));

  const groups = new Map();
  for (const item of items) {
    const key = site ? (item.line || "공정 미지정") : (item.plant || "공장 미지정");
    const group = groups.get(key) || { normal: 0, attention: 0, critical: 0, unknown: 0, total: 0 };
    group[state(item)]++;
    group.total++;
    groups.set(key, group);
  }
  document.querySelector("#risk-map").innerHTML = [...groups.entries()]
    .sort((a, b) => (b[1].critical + b[1].attention) - (a[1].critical + a[1].attention))
    .slice(0, 8).map(([name, group]) => {
      const risk = (group.critical * 3 + group.attention) / group.total;
      return `<div class="risk-cell ${risk >= 1.5 ? "risk-high" : risk >= .5 ? "risk-mid" : ""}"><strong>${safe(name)}</strong><b>${group.critical + group.attention}</b><small>${group.total}대 중 주의 이상 · 정상 ${group.normal}대</small></div>`;
    }).join("") || empty("조회 조건에 해당하는 설비가 없습니다.");

  const work = items.filter((item) => ["attention", "critical"].includes(state(item)))
    .sort((a, b) => Number(state(b) === "critical") - Number(state(a) === "critical"))
    .slice(0, 5);
  document.querySelector("#signals").innerHTML = work.map((item) => (
    `<div class="signal ${state(item)}"><i></i><span><strong>${safe(item.displayName || item.name)}</strong><small>${safe(item.plant)} · ${safe(item.line)}</small></span><em>${safe(item.statusLabel)}</em></div>`
  )).join("") || empty("현재 이상 신호가 없습니다.");
  setText("#work-count", `${work.length}건`);
  document.querySelector("#work-rows").innerHTML = work.map((item, index) => (
    `<a class="work-row ${state(item)}" href="${detailUrl(item.id)}"><b>${String(index + 1).padStart(2, "0")}</b><strong>${safe(item.displayName || item.name)}</strong><span>${safe(item.plant)} · ${safe(item.line)}</span><em>${safe(item.statusLabel)}</em><i class="${state(item)}"></i></a>`
  )).join("") || empty("점검 대상이 없습니다.");

  document.querySelector("#recent-activity").innerHTML = [...history]
    .sort((a, b) => String(b.date).localeCompare(String(a.date)))
    .slice(0, 5).map((item) => (
      `<a class="activity" href="${item.datasetId ? detailUrl(item.datasetId) : historyPath}"><time>${safe(item.date)}</time><span><strong>${safe(item.equipmentName)}</strong><small>${safe(item.process)} · ${safe(item.faultType || item.fault || "진단 기록")}</small></span></a>`
    )).join("") || empty("최근 진단 활동이 없습니다.");

  const byDate = new Map();
  history.forEach((item) => byDate.set(item.date, (byDate.get(item.date) || 0) + 1));
  const dates = [...byDate.keys()].sort().slice(-7);
  const maximum = Math.max(...dates.map((date) => byDate.get(date)), 1);
  document.querySelector("#trend-bars").innerHTML = dates.map((date) => (
    `<div class="trend-column"><b style="height:${byDate.get(date) / maximum * 100}%"><span>${byDate.get(date)}</span></b><small>${safe(date.slice(5))}</small></div>`
  )).join("") || empty("진단 이력이 없습니다.");
}

async function init() {
  setText("#workspace-title", site ? "현장 설비 운영 현황" : "전사 설비 운영 현황");
  setText("#role-label", site ? "SITE OPERATIONS" : new Intl.DateTimeFormat("ko-KR", { dateStyle: "full" }).format(new Date()));
  setText("#hero-title", site ? "지금 점검할 설비" : "오늘 먼저 봐야 할 설비");
  setText("#hero-description", site ? "현재 현장의 이상 신호와 공정 상태를 기준으로 점검 순서를 정리했습니다." : "전 공장 상태와 진단 이력을 기준으로 조치 우선순위를 정리했습니다.");
  setText("#chart-title", site ? "공정별 리스크 분포" : "공장별 리스크 분포");
  const [items, payload] = await Promise.all([fetchDatasetSummaries(), fetchHistory()]);
  const history = payload.items || [];
  const scope = document.querySelector("#scope-select");
  const process = document.querySelector("#process-select");
  const plants = [...new Set(items.map((item) => item.plant).filter(Boolean))].sort();
  scope.replaceChildren(new Option("전체 공장", "all"), ...plants.map((plant) => new Option(plant, plant)));

  function updateProcesses() {
    const available = items.filter((item) => scope.value === "all" || item.plant === scope.value);
    const processes = [...new Set(available.map((item) => item.line).filter(Boolean))].sort();
    process.replaceChildren(new Option("전체 공정", "all"), ...processes.map((line) => new Option(line, line)));
    process.value = "all";
  }

  function applyFilters() {
    const filtered = items.filter((item) => (scope.value === "all" || item.plant === scope.value)
      && (process.value === "all" || item.line === process.value));
    const ids = new Set(filtered.map((item) => String(item.id)));
    const filteredHistory = scope.value === "all" && process.value === "all"
      ? history : history.filter((item) => ids.has(String(item.datasetId)));
    render(filtered, filteredHistory);
  }

  scope.addEventListener("change", () => { updateProcesses(); applyFilters(); });
  process.addEventListener("change", applyFilters);
  updateProcesses();
  applyFilters();
  for (const selector of ["#scope-select", "#process-select"]) {
    document.querySelector(selector).disabled = false;
  }
  for (const selector of ["#risk-map", "#signals", "#work-rows", "#recent-activity", "#trend-bars"]) {
    document.querySelector(selector).ariaBusy = "false";
  }
}

window.addEventListener("DOMContentLoaded", () => init().catch((error) => {
  setText("#hero-description", "데이터를 불러오지 못했습니다. 잠시 후 다시 열어 주세요.");
  for (const selector of ["#risk-map", "#signals", "#work-rows", "#recent-activity", "#trend-bars"]) {
    document.querySelector(selector).innerHTML = empty("데이터를 불러오지 못했습니다.");
    document.querySelector(selector).ariaBusy = "false";
  }
  console.error("workspace load failed", error);
}));
