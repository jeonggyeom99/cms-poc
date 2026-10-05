import { fetchDatasetSummaries } from "../api/dashboard.js";
import { fetchHistory } from "../api/history.js";

const q = (selector) => document.querySelector(selector);
const qs = (selector) => [...document.querySelectorAll(selector)];
const setText = (selector, value) => { const node = q(selector); if (node) node.textContent = value; };
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));
const key = (item) => item.status === "normal" ? "safe" : item.status === "caution" ? "attention" : "critical";
const label = (item) => item.statusLabel || (item.status === "normal" ? "정상" : item.status === "caution" ? "주의" : "심각");
const pct = (value, total) => total ? Math.round(value / total * 100) : 0;

function setShellText() {
  document.title = "CMS 설비 KPI 대시보드";
  setText(".brand span", "CMS Dashboard");
  setText(".nav-label", "CMS 운영");
  ["대시보드", "설비 성능", "운영 현황", "진단 리포트", "설정", "도움말"].forEach((value, index) => {
    const node = qs(".nav a span:last-child")[index]; if (node) node.textContent = value;
  });
  if (document.body.classList.contains("dashboard-ui6")) {
    const links = qs(".nav a");
    [["/dashboard_ui6", "대시보드"], ["/equipment-status2", "설비 알람 현황"], ["/history2", "진단 이력"], ["/main_ct", "중앙 관제"]].forEach(([href, label], index) => {
      if (!links[index]) return;
      const link = links[index].cloneNode(true);
      link.href = href;
      const textNode = link.querySelector("span:last-child"); if (textNode) textNode.textContent = label;
      links[index].replaceWith(link);
    });
  }
  setText(".avatar", "관"); setText(".profile b", "중앙 관제"); setText(".profile span", "CMS 운영팀");
  setText(".eyebrow", new Intl.DateTimeFormat("ko-KR", { dateStyle: "full" }).format(new Date()));
  setText(".top h1", "오늘의 설비 운영 현황");
  setText(".top p", "공장별 설비 상태와 최근 진단 이력을 한눈에 확인합니다.");
  setText(".actions .btn:first-child", "전체 공장⌄"); setText(".actions .btn.primary", "＋ 운영 리포트");
}

function renderBars(items) {
  const plants = [...new Set(items.map((item) => item.plant || "미지정 공장"))];
  const scale = Math.max(...plants.map((plant) => items.filter((item) => (item.plant || "미지정 공장") === plant).length), 1);
  const bars = q(".bars");
  if (bars) bars.innerHTML = plants.map((plant) => {
    const group = items.filter((item) => (item.plant || "미지정 공장") === plant);
    const normal = group.filter((item) => item.status === "normal").length;
    const issue = group.length - normal;
    return `<div class="bar-group"><div class="bar" style="height:${Math.max(8, normal / scale * 100)}%" title="정상 ${normal}대"></div><div class="bar dark" style="height:${Math.max(8, issue / scale * 100)}%" title="주의 이상 ${issue}대"></div><small>${esc(plant)}</small></div>`;
  }).join("") || `<span class="empty">설비 데이터가 없습니다.</span>`;
  setText(".columns .panel:first-child h3", "공장별 설비 상태");
  setText(".columns .panel:first-child .panel-head span", "정상 · 주의 이상");
  setText(".columns .panel:first-child .legend span:first-child", "정상");
  setText(".columns .panel:first-child .legend span:last-child", "주의 이상");
}

function renderHealth(items, counts) {
  const normal = pct(counts.normal, items.length); const caution = pct(counts.caution, items.length); const critical = Math.max(0, 100 - normal - caution);
  const donut = q(".donut");
  if (donut) { donut.style.background = `conic-gradient(var(--mint) 0 ${normal}%, var(--orange) ${normal}% ${normal + caution}%, var(--red) ${normal + caution}% 100%)`; donut.dataset.label = `${normal}%`; }
  setText(".columns .panel:nth-child(2) h3", "설비 상태 구성"); setText(".columns .panel:nth-child(2) .panel-head span", "전체 설비 기준");
  [["정상", normal], ["주의", caution], ["심각 이상", critical]].forEach(([name, value], index) => { const row = qs(".health-row")[index]; if (row) { row.querySelector("span").textContent = name; row.querySelector("b").textContent = `${value}%`; } });
}

function renderTable(items, history) {
  const risk = items.filter((item) => item.status !== "normal"); const rows = risk.length ? risk : items;
  const tbody = q(".table tbody");
  if (tbody) tbody.innerHTML = rows.slice(0, 6).map((item) => {
    const latest = history.find((entry) => entry.datasetId === item.id);
    return `<tr><td><b>${esc(item.displayName || item.name || item.equipmentCode)}</b><br><span class="empty">${esc(item.equipmentCode)}</span></td><td>${esc(item.plant || "-")} · ${esc(item.line || "-")}</td><td>${esc(latest?.date || item.lastMeasuredAt || "-")}</td><td>${esc(item.measurementPoint || "-")}</td><td><span class="status ${key(item)}">${esc(label(item))}</span></td></tr>`;
  }).join("") || `<tr><td colspan="5" class="empty">표시할 설비가 없습니다.</td></tr>`;
  ["설비", "공장 · 공정", "최근 진단", "측정 포인트", "상태"].forEach((value, index) => { const node = qs(".table th")[index]; if (node) node.textContent = value; });
  setText(".table h3", "점검 우선순위 설비"); setText(".table .panel-head span", `주의 이상 ${risk.length}대 · 전체 보기 →`);
}

async function init() {
  setShellText();
  try {
    const [items, historyPayload] = await Promise.all([fetchDatasetSummaries(), fetchHistory()]);
    const history = historyPayload.items || []; const counts = { normal: items.filter((x) => x.status === "normal").length, caution: items.filter((x) => x.status === "caution").length, critical: items.filter((x) => !["normal", "caution"].includes(x.status)).length };
    const total = items.length; const risk = total - counts.normal; const normalRate = pct(counts.normal, total);
    setText(".hero-card .eyebrow", "CMS OPERATIONS PULSE"); setText(".hero-card h2", risk ? `${risk}개 설비의 확인이 필요합니다.` : "전체 설비가 정상 운영 중입니다."); setText(".hero-card p", `전체 ${total}대 설비의 최신 상태와 ${history.length}건의 진단 이력을 기준으로 집계했습니다.`);
    const metrics = qs(".hero-metric strong"); if (metrics[0]) metrics[0].textContent = `${normalRate}%`; if (metrics[1]) metrics[1].textContent = `${risk}대`;
    const metricLabels = qs(".hero-metric small"); if (metricLabels[0]) metricLabels[0].textContent = "정상 설비 비율"; if (metricLabels[1]) metricLabels[1].textContent = "주의 이상 설비";
    setText(".snapshot h3", "최근 진단 활동"); setText(".snapshot .empty", "최근 진단 건수"); setText(".snapshot .tag", `총 ${history.length}건`);
    const kpis = [["전체 설비", total, "↗"], ["정상 설비", counts.normal, "✓"], ["주의 설비", counts.caution, "!"], ["심각 설비", counts.critical, "!"]];
    qs(".kpi").forEach((card, index) => { const [name, value, icon] = kpis[index]; card.querySelector(".kpi-top span").textContent = name; card.querySelector(".kpi-icon").textContent = icon; card.querySelector("strong").textContent = value; card.querySelector(".delta").textContent = index === 0 ? "현재 조회 기준" : `${pct(value, total)}% · 전체 대비`; });
    renderBars(items); renderHealth(items, counts); renderTable(items, history); setText(".footnote", `마지막 조회 ${new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })} · CMS 설비/진단 데이터 기준`);
  } catch (error) { setText(".hero-card h2", "데이터를 불러오지 못했습니다."); setText(".hero-card p", "CMS API 연결 상태를 확인해 주세요."); console.error(error); }
}
init();
