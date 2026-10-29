import { fetchDatasetSummaries } from "../api/dashboard.js";
import { fetchHistory } from "../api/history.js";
const number = location.pathname.match(/^\/dashboard_ui([1-4])$/)?.[1] || "1",
  variant = `layout-${number}`,
  site = document.querySelector("#lab");
site.classList.add(variant);
const status = (i) =>
  i.status === "caution"
    ? "attention"
    : i.status === "normal"
      ? "normal"
      : i.status === "unknown"
        ? "unknown"
        : "critical";
const safe = (v) => String(v || "미지정");
const names = {
  1: [
    "UI 01 · Operations Grid",
    "통합 설비 운영 현황",
    "공장별 상태와 최근 진단 활동을 한 화면에서 확인합니다.",
  ],
  2: [
    "UI 02 · Night Control",
    "Night Operations Monitor",
    "어두운 관제 환경에서 이상 신호와 위험 설비를 빠르게 찾습니다.",
  ],
  3: [
    "UI 03 · Analysis Report",
    "설비 분석 리포트",
    "상태 분포와 이력 데이터를 비교해 관리 판단을 돕습니다.",
  ],
  4: [
    "UI 04 · Worklist",
    "Daily Maintenance Board",
    "오늘 점검할 설비와 작업 우선순위를 간결하게 정리합니다.",
  ],
};
function draw(items, history) {
  const c = { normal: 0, attention: 0, critical: 0, unknown: 0 };
  items.forEach((i) => c[status(i)]++);
  const total = items.length;
  document.querySelector("#variant-title").textContent = names[number][0];
  document.querySelector("#app").innerHTML =
    `<main class="lab-main"><div class="lab-title title-panel"><div><span class="eyebrow">LIVE CONDITION MONITORING</span><h1>${names[number][1]}</h1><p>${names[number][2]}</p></div><span class="eyebrow">${new Date().toLocaleDateString("ko-KR")}</span></div><section class="stat-row"><div class="stat"><small>전체 설비</small><b>${total}</b></div><div class="stat"><small>정상</small><b class="green">${c.normal}</b></div><div class="stat"><small>주의</small><b class="amber">${c.attention}</b></div><div class="stat"><small>심각</small><b class="red">${c.critical}</b></div></section><div class="content"><section class="panel bar-panel"><span class="eyebrow">EQUIPMENT DISTRIBUTION</span><h2>${number === "4" ? "오늘 점검 대상 공장" : "공장별 설비 상태 분포"}</h2><div id="bars" class="bar-chart"></div></section><section class="panel pie-panel"><span class="eyebrow">STATUS MIX</span><h2>전체 상태 구성</h2><div class="pie"><b>${total}</b></div><div class="legend"><div><span><i class="normal"></i>정상</span><b>${c.normal}</b></div><div><span><i class="attention"></i>주의</span><b>${c.attention}</b></div><div><span><i class="critical"></i>심각</span><b>${c.critical}</b></div><div><span><i class="unknown"></i>판단 불가</span><b>${c.unknown}</b></div></div></section><section class="panel activity-panel"><span class="eyebrow">RECENT ACTIVITY</span><h2>최근 진단 활동</h2><div id="activity"></div></section></div></main>`;
  document.querySelectorAll(".stat b, .pie b").forEach((value) => {
    value.dataset.cmsRole = "kpi";
  });
  const illustrativeLabel = document.createElement("small");
  illustrativeLabel.textContent = "예시 비율";
  document.querySelector(".pie-panel h2").append(" ", illustrativeLabel);
  const groups = new Map();
  items.forEach((i) => {
    const key = i.plant || "공장 미지정";
    const g = groups.get(key) || {
      normal: 0,
      attention: 0,
      critical: 0,
      unknown: 0,
    };
    g[status(i)]++;
    groups.set(key, g);
  });
  const chart = document.querySelector("#bars");
  chart.dataset.cmsRole = "chart";
  chart.innerHTML = [...groups.entries()]
    .slice(0, 8)
    .map(([name, g]) => {
      const n = Object.values(g).reduce((a, b) => a + b, 0);
      return `<div class="bar-line"><label>${safe(name)}</label><div class="track">${Object.entries(
        g,
      )
        .map(([k, v]) =>
          v ? `<i class="${k}" style="width:${(v / n) * 100}%"></i>` : "",
        )
        .join("")}</div><em>${g.critical + g.attention}건 주의</em></div>`;
    })
    .join("");
  document.querySelector("#activity").innerHTML =
    history
      .slice(0, 6)
      .map(
        (h) =>
          `<div class="activity"><time>${safe(h.date)}</time><span><strong>${safe(h.equipmentName)}</strong><small>${safe(h.process)} · ${safe(h.faultType || h.fault || "진단 기록")}</small></span></div>`,
      )
      .join("") || "<p>최근 진단 활동 없음</p>";
}
Promise.all([fetchDatasetSummaries(), fetchHistory()]).then(([items, h]) =>
  draw(items, h.items || []),
);
function convertBarsToVertical() {
  document.querySelectorAll(".track").forEach((track) => {
    track.style.flexDirection = "column-reverse";
    track.querySelectorAll("i").forEach((bar) => {
      const value = bar.style.width;
      bar.style.width = "100%";
      bar.style.height = value;
    });
  });
}
new MutationObserver(convertBarsToVertical).observe(
  document.querySelector("#app"),
  { childList: true, subtree: true },
);
