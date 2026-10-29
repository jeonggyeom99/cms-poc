import { fetchDatasetSummaries } from "../api/dashboard.js?v=demo-unbalance-v1";

const esc = (value) => String(value ?? "-").replace(/[&<>"']/g, (character) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[character]));
const states = [
  { key: "normal", label: "정상" },
  { key: "caution", label: "주의" },
  { key: "critical", label: "심각" },
  { key: "unknown", label: "판단 불가" },
];

function initializeTooltip() {
  const tooltip = document.createElement("div");
  tooltip.className = "equipment-status2-tooltip";
  tooltip.id = "equipment-status-chart-tooltip";
  tooltip.role = "tooltip";
  tooltip.hidden = true;
  document.body.append(tooltip);
  const show = (target) => {
    tooltip.textContent = target.dataset.tooltip;
    tooltip.hidden = false;
    const bounds = target.getBoundingClientRect();
    tooltip.style.left = `${Math.max(8, Math.min(bounds.left, innerWidth - tooltip.offsetWidth - 8))}px`;
    tooltip.style.top = `${Math.max(8, bounds.top - tooltip.offsetHeight - 8)}px`;
  };
  document.addEventListener("mouseover", (event) => {
    const target = event.target.closest("[data-tooltip]");
    if (target) show(target);
  });
  document.addEventListener("focusin", (event) => {
    const target = event.target.closest("[data-tooltip]");
    if (target) show(target);
  });
  document.addEventListener("mouseout", (event) => {
    if (event.target.closest("[data-tooltip]")) tooltip.hidden = true;
  });
  document.addEventListener("focusout", () => { tooltip.hidden = true; });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") tooltip.hidden = true; });
}

async function initializeCharts() {
  const charts = document.getElementById("equipment-status-charts");
  const status = document.getElementById("equipment-status-chart-status");
  initializeTooltip();
  try {
    const datasets = await fetchDatasetSummaries();
    status.textContent = `전체 CMS 연결 ${datasets.length}대`;
    if (!datasets.length) {
      charts.textContent = "연결된 CMS 설비가 없습니다.";
      return;
    }
    const counts = Object.fromEntries(states.map(({ key }) => [key, 0]));
    const plants = new Map();
    datasets.forEach((item) => {
      const state = states.some(({ key }) => key === item.status) ? item.status : "unknown";
      counts[state] += 1;
      const plant = item.plant || "미지정";
      const group = plants.get(plant) || { normal: 0, issue: 0, unknown: 0 };
      group[state === "normal" ? "normal" : state === "unknown" ? "unknown" : "issue"] += 1;
      plants.set(plant, group);
    });
    const maximum = Math.max(...[...plants.values()].map((group) => group.normal + group.issue + group.unknown), 1);
    charts.innerHTML = `<article aria-labelledby="equipment-status-plant-title"><h3 id="equipment-status-plant-title">공장별 연결 설비</h3>
      <div class="equipment-status2-plant-legend"><span><i class="normal"></i>정상</span><span><i class="issue"></i>주의 이상</span><span><i class="unknown"></i>판단 불가</span></div>
      <div class="equipment-status2-plant-bars">${[...plants].map(([name, group]) => {
        const label = `${name} · 정상 ${group.normal}대 · 주의 이상 ${group.issue}대 · 판단 불가 ${group.unknown}대`;
        return `<div class="equipment-status2-plant" tabindex="0" aria-label="${esc(label)}" aria-describedby="equipment-status-chart-tooltip" data-tooltip="${esc(label)}"><span>${esc(name)}</span><div class="equipment-status2-plant-track">${["normal", "issue", "unknown"].map((state) => `<i class="${state}" style="width:${group[state] / maximum * 100}%"></i>`).join("")}</div><b>${group.normal + group.issue + group.unknown}대</b></div>`;
      }).join("")}</div></article>
      <article aria-labelledby="equipment-status-state-title"><h3 id="equipment-status-state-title">연결 설비 상태</h3><div class="equipment-status2-state-list">${states.map(({ key, label }) => `<div class="equipment-status2-state-row"><span class="equipment-status2-state-label ${key}"><i></i>${label}</span><div class="equipment-status2-state-track"><i class="${key}" style="width:${counts[key] / datasets.length * 100}%"></i></div><b>${counts[key]}대</b></div>`).join("")}</div></article>`;
  } catch (error) {
    status.textContent = "CMS 상태를 불러오지 못했습니다.";
    charts.replaceChildren();
  } finally {
    charts.removeAttribute("aria-busy");
  }
}

initializeCharts();
