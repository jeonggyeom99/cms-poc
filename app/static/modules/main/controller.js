import { fetchDatasetSummaries } from "../api/dashboard.js";
import { fetchHistory } from "../api/history.js";

const labels = { normal: "정상", caution: "주의", critical: "심각", unknown: "판단 불가" };
const stateOf = (item) => item.status === "caution" ? "attention" : item.status === "critical" ? "critical" : item.status === "normal" ? "normal" : "unknown";
const escapeText = (value) => String(value || "미지정");

function render(items) {
  const counts = { normal: 0, attention: 0, critical: 0, unknown: 0 };
  const factories = new Map();
  items.forEach((item) => {
    const state = stateOf(item); counts[state] += 1;
    const factory = item.plant || "공장 미지정";
    const group = factories.get(factory) || { items: [], processes: new Set() };
    group.items.push({ ...item, state }); group.processes.add(item.line || "공정 미지정"); factories.set(factory, group);
  });
  document.querySelector("#metric-total").textContent = items.length;
  document.querySelector("#metric-normal").textContent = counts.normal;
  document.querySelector("#metric-attention").textContent = counts.attention;
  document.querySelector("#metric-critical").textContent = counts.critical;
  document.querySelector("#main-count").textContent = `${factories.size}개 공장 · ${items.length}개 설비`;
  document.querySelector("#main-updated").textContent = `마지막 조회 ${new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}`;
  const list = document.querySelector("#factory-list"); list.replaceChildren();
  [...factories.entries()].sort(([a], [b]) => a.localeCompare(b, "ko", { numeric: true })).forEach(([name, group]) => {
    const local = { normal: 0, attention: 0, critical: 0, unknown: 0 }; group.items.forEach((item) => { local[item.state] += 1; });
    const total = group.items.length; const card = document.createElement("a"); card.className = "factory-card"; card.href = `/?factory=${encodeURIComponent(name)}`; card.setAttribute("aria-label", `${name} 설비 모니터링 보기`);
    const state = local.critical ? "critical" : local.attention ? "attention" : "normal";
    card.dataset.state = state;
    card.innerHTML = `<div class="factory-name"><i class="state-mark state-${state}"></i><span>${escapeText(name)}</span><small>${group.processes.size}개 공정 · ${total}개 설비</small></div><div class="factory-middle"><div class="factory-bar" aria-label="${escapeText(name)} 상태 비율">${Object.entries(local).filter(([, count]) => count).map(([state, count]) => `<i class="bar-${state}" style="width:${count / total * 100}%" title="${labels[state]} ${count}개"></i>`).join("")}</div><small>${group.items.filter((item) => item.state === "critical" || item.state === "attention").length ? "점검이 필요한 설비가 있습니다" : "모든 설비가 안정 상태입니다"}</small></div><div class="factory-stats"><b>${local.critical} 심각</b><span>${local.attention} 주의</span><span>${local.normal} 정상</span></div>`;
    list.append(card);
  });
  const alerts = items.filter((item) => ["critical", "caution"].includes(item.status)).slice(0, 5);
  const alertList = document.querySelector("#alert-list"); alertList.replaceChildren();
  if (!alerts.length) alertList.innerHTML = '<p class="empty-alert">현재 감지된 이상 징후가 없습니다.</p>';
  alerts.forEach((item) => { const node = document.createElement("a"); node.className = `alert-item alert-${stateOf(item)}`; node.href = `/dashboard?dataset=${encodeURIComponent(item.id)}`; node.innerHTML = `<i></i><span><strong>${escapeText(item.displayName || item.name)}</strong><small>${escapeText(item.plant)} · ${escapeText(item.line)}</small></span><em>${labels[stateOf(item)]}</em>`; alertList.append(node); });
}

function renderHistory(payload) {
  const list = document.querySelector("#recent-history"); list.replaceChildren();
  const items = (payload.items || []).slice().sort((a, b) => String(b.date).localeCompare(String(a.date))).slice(0, 4);
  if (!items.length) { list.innerHTML = '<p class="loading">최근 진단 이력이 없습니다.</p>'; return; }
  items.forEach((item) => { const node = document.createElement("a"); node.className = "recent-history__item"; node.href = item.datasetId ? `/dashboard?dataset=${encodeURIComponent(item.datasetId)}` : "/history"; node.innerHTML = `<time>${escapeText(item.date)}</time><span><strong>${escapeText(item.equipmentName)}</strong><small>${escapeText(item.process)} · ${escapeText(item.faultType || item.fault || "진단 기록")}</small></span>`; list.append(node); });
}

async function init() { try { const [datasets, history] = await Promise.all([fetchDatasetSummaries(), fetchHistory()]); render(datasets); renderHistory(history); } catch (error) { document.querySelector("#factory-list").innerHTML = `<p class="loading">데이터를 불러오지 못했습니다: ${error.message}</p>`; } }
window.addEventListener("DOMContentLoaded", init);
