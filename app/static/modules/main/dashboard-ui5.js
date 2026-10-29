import { fetchDatasetSummaries } from "../api/dashboard.js";
import { fetchHistory } from "../api/history.js";
const safe = (v) => String(v || "미지정");
const state = (i) =>
  i.status === "caution"
    ? "attention"
    : i.status === "normal"
      ? "normal"
      : "critical";
function render(items, history) {
  const c = { normal: 0, attention: 0, critical: 0 };
  items.forEach((i) => c[state(i)]++);
  document.querySelector("#report-date").textContent =
    new Date().toLocaleDateString("ko-KR");
  document.querySelector("#summary").textContent =
    `전체 ${items.length}개 설비 중 정상 ${c.normal}개, 주의 이상 ${c.attention + c.critical}개 · 현재 주의 이상 비율 ${Math.round(((c.attention + c.critical) / Math.max(items.length, 1)) * 100)}%`;
  const groups = new Map();
  items.forEach((i) => {
    const g = groups.get(i.plant) || { normal: 0, attention: 0, critical: 0 };
    g[state(i)]++;
    groups.set(i.plant, g);
  });
  document.querySelector("#bar-chart").innerHTML = [...groups.entries()]
    .slice(0, 9)
    .map(([name, g]) => {
      const n = Object.values(g).reduce((a, b) => a + b, 0);
      return `<div class="bar-line"><label>${safe(name)}</label><em>${g.critical + g.attention}</em><div class="track"><i class="normal" style="height:${(g.normal / n) * 100}%"></i><i class="attention" style="height:${(g.attention / n) * 100}%"></i><i class="critical" style="height:${(g.critical / n) * 100}%"></i></div></div>`;
    })
    .join("");
  document.querySelector("#timeline").innerHTML =
    history
      .slice(0, 7)
      .map(
        (h) =>
          `<div class="timeline-row"><time>${safe(h.date)}</time><i></i><span><strong>${safe(h.equipmentName)}</strong><small>${safe(h.process)} · ${safe(h.result || h.faultType || "진단 기록")}</small></span></div>`,
      )
      .join("") || "<p>진단 이력이 없습니다.</p>";
  const rows = items
    .filter((i) => ["caution", "critical"].includes(i.status))
    .slice(0, 10);
  document.querySelector("#table-count").textContent =
    `${rows.length}개 우선 표시`;
  document.querySelector("#table-body").innerHTML =
    rows
      .map(
        (i) =>
          `<a class="table-row" href="/dashboard?dataset=${encodeURIComponent(i.id)}"><span class="state state-${state(i)}"><i></i>${safe(i.statusLabel)}</span><strong>${safe(i.displayName || i.name)}</strong><span>${safe(i.plant)}</span><span>${safe(i.line)}</span><em>보기</em></a>`,
      )
      .join("") || "<p>주의 이상 설비가 없습니다.</p>";
}
Promise.all([fetchDatasetSummaries(), fetchHistory()]).then(([items, h]) =>
  render(items, h.items || []),
);
document
  .querySelector(".report header nav")
  .insertAdjacentHTML(
    "afterbegin",
    '<a class="connect-link" href="/">설비</a><a class="connect-link" href="/main_ct">CT</a><a class="connect-link" href="/main_sv">SV</a><a class="connect-link" href="/history">이력</a>',
  );
