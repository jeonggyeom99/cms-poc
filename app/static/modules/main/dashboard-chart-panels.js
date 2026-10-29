import { fetchDatasetSummaries } from "../api/dashboard.js";
import { fetchHistory } from "../api/history.js";

const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));
const max = (values) => Math.max(...values, 1);

function card(title, subtitle, body) { return `<article class="cms-chart-card"><div class="cms-chart-head"><h3>${title}</h3><span>${subtitle}</span></div>${body}</article>`; }

async function init() {
  const dataTip = document.createElement("div"); dataTip.className = "cms-data-tooltip"; document.body.appendChild(dataTip);
  document.addEventListener("mouseover", (event) => { const target = event.target.closest("[title]"); if (!target || !target.title) return; dataTip.textContent = target.title; dataTip.style.display = "block"; });
  document.addEventListener("mousemove", (event) => { if (dataTip.style.display === "block") { dataTip.style.left = `${event.clientX + 12}px`; dataTip.style.top = `${event.clientY - 34}px`; } });
  document.addEventListener("mouseout", (event) => { if (event.target.closest("[title]")) dataTip.style.display = "none"; });
  const [datasets, historyPayload] = await Promise.all([fetchDatasetSummaries(), fetchHistory()]);
  const history = historyPayload.items || [];
  const dates = [...new Set(history.map((x) => x.date))].sort();
  const recentDates = dates.slice(-7);
  const daily = recentDates.map((date) => history.filter((x) => x.date === date).length);
  const faultMap = new Map(); history.forEach((item) => faultMap.set(item.faultType || item.fault || "기타", (faultMap.get(item.faultType || item.fault || "기타") || 0) + 1));
  const faults = [...faultMap.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);
  const total = datasets.length; const issue = datasets.filter((x) => x.status !== "normal").length;
  const processMap = new Map(); history.forEach((item) => { const name = item.process || "미지정 공정"; processMap.set(name, (processMap.get(name) || 0) + 1); });
  const processes = [...processMap.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6); const processActual = processes.map((entry) => entry[1]); const processTarget = processActual.map((value) => value + Math.max(2, Math.ceil(value * .25)));
  const periods = ["1분기", "2분기", "3분기", "4분기"];
  const actual = periods.map((_, index) => Math.round(history.length * (index + 1) / periods.length));
  const target = periods.map((_, index) => Math.max(actual[index], Math.round(Math.max(history.length, 4) * (index + 1) / periods.length) + 2));
  const lineValues = [72, 118, 84, 132, 91, 145, 106]; const targetValues = [128, 92, 140, 108, 150, 100, 138]; const lineMax = 160; const linePoints = lineValues.map((value, index) => `${30 + (index / (lineValues.length - 1)) * 640},${160 - (value / lineMax) * 130}`); const targetPoints = targetValues.map((value, index) => `${30 + (index / (targetValues.length - 1)) * 640},${160 - (value / lineMax) * 130}`); const points = linePoints.join(" "); const dayLabels = Array.from({ length: 7 }, (_, index) => { const date = new Date(); date.setDate(date.getDate() - (6 - index)); return `${date.toLocaleDateString("ko-KR", { weekday: "short" })} ${date.getMonth() + 1}/${date.getDate()}`; });
  const grid = document.createElement("section"); grid.className = "cms-chart-grid";
  grid.setAttribute("aria-label", "데모 운영 지표");
  grid.innerHTML = card("설비알람 개발수 (누계)", `<span class="chart-legend"><i></i>실제 <i class="target"></i>목표</span>`, `<div class="cms-vbars">${processes.map((entry, i) => `<div class="cms-vgroup"><i class="cms-vbar target" title="${esc(entry[0])} · 목표 ${processTarget[i]}건" style="height:${processTarget[i] / max(processTarget) * 100}%"></i><i class="cms-vbar actual" title="${esc(entry[0])} · 실제 ${processActual[i]}건" style="height:${processActual[i] / max(processTarget) * 100}%"></i><small>${esc(entry[0])}</small></div>`).join("") || '<span class="empty">공정 데이터가 없습니다.</span>'}</div>`) + card("설비알람 발생수 (누계)", `<span class="chart-legend"><i></i>발생 건수</span>`, `<div class="cms-vbars">${processes.map((entry, i) => `<div class="cms-vgroup"><i class="cms-vbar actual" title="${esc(entry[0])} · 발생 ${processActual[i]}건" style="height:${Math.max(8, processActual[i] / max(processActual) * 100)}%"></i><small>${esc(entry[0])}</small></div>`).join("") || '<span class="empty">공정 데이터가 없습니다.</span>'}</div>`) + card("생산 장애 유형비 (누계)", `<span class="chart-legend"><i class="mint"></i>장애 건수</span>`, `<div class="cms-hbars">${faults.map(([name, value]) => `<div class="cms-hrow"><span>${esc(name)}</span><div class="cms-htrack"><i title="${esc(name)} · ${value}건" style="width:${value / max(faults.map((x) => x[1])) * 100}%"></i></div><b>${value}</b></div>`).join("") || '<span class="empty">장애 유형 데이터가 없습니다.</span>'}</div>`) + card("생산량 (일별)", `<span class="chart-legend"><i></i>목표량 (ton) <i class="orange"></i>생산량 (ton)</span>`, `<div class="cms-line-wrap"><svg class="cms-line" viewBox="0 0 700 180"><line x1="30" y1="30" x2="670" y2="30"/><line x1="30" y1="95" x2="670" y2="95"/><line x1="30" y1="160" x2="670" y2="160"/><polyline class="target-line" points="${targetPoints.join(" ")}" /><polyline points="${points}" />${linePoints.map((point, index) => { const [x, y] = point.split(","); return `<circle cx="${x}" cy="${y}" r="4" /><text x="${x}" y="${Number(y) - 10}" text-anchor="middle">${lineValues[index]}</text>`; }).join("")}</svg></div><div class="cms-axis">${["월", "화", "수", "목", "금", "토", "일"].map((day) => `<span>${day}</span>`).join("")}</div>`);
  grid.querySelectorAll(".cms-vbars").forEach((bars, index) => {
    const scale = max(index === 0 ? processTarget : processActual);
    bars.dataset.ticks = [1, .75, .5, .25, 0]
      .map((fraction) => Number((scale * fraction).toFixed(1))).join("\n");
  });
  if (document.body.hasAttribute("data-cms-operations")) {
    const cards = grid.querySelectorAll(".cms-chart-card");
    cards[0].querySelector("h3").textContent = "설비 알람 건수 (목표 대비)";
    cards[1].querySelector("h3").textContent = "설비 알람 발생 건수 (누계)";
    cards[3].querySelector(".chart-legend").innerHTML = '<i></i>생산량 (ton) <i class="orange"></i>목표량 (ton)';
  }
  const typeCard = grid.querySelectorAll(".cms-chart-card")[2];
  if (typeCard) typeCard.innerHTML = `<div class="cms-chart-head"><h3>생산 장애 유형비 (누계)</h3><span class="chart-legend"><i class="type-a"></i>A <i class="type-b"></i>B <i class="type-c"></i>C <i class="type-d"></i>D</span></div><div class="cms-type-bars">${processes.map(([name, value], index) => { const values = [Math.max(1, value - index), Math.max(1, Math.round(value * .32)), Math.max(1, Math.round(value * .2)), Math.max(1, Math.round(value * .12))]; const totalValue = values.reduce((sum, current) => sum + current, 0); return `<div class="cms-type-row"><span>${esc(name)}</span><div class="cms-type-track">${values.map((part, typeIndex) => `<i class="${"abcd"[typeIndex]}" style="width:${part / totalValue * 100}%"></i>`).join("")}</div><b>${totalValue}</b></div>`; }).join("") || '<span class="empty">공정 데이터가 없습니다.</span>'}</div>`;
  const productionCard = grid.querySelectorAll(".cms-chart-card")[3];
  productionCard?.querySelectorAll("circle").forEach((circle, index) => { const title = document.createElementNS("http://www.w3.org/2000/svg", "title"); title.textContent = `${dayLabels[index]} · 생산량 ${lineValues[index]} ton · 목표량 ${targetValues[index]} ton`; circle.appendChild(title); });
  if (productionCard) {
    productionCard.querySelector(".cms-axis").innerHTML = dayLabels.map((day) => `<span>${day}</span>`).join("");
    const wrap = productionCard.querySelector(".cms-line-wrap"); const tooltip = document.createElement("div"); tooltip.className = "cms-point-tooltip"; wrap.appendChild(tooltip);
    productionCard.querySelectorAll("circle").forEach((circle, index) => { circle.addEventListener("mouseenter", (event) => { tooltip.innerHTML = `<b>${dayLabels[index]}</b><br>생산량 ${lineValues[index]} ton · 목표량 ${targetValues[index]} ton`; tooltip.style.display = "block"; tooltip.style.left = `${Math.min(event.offsetX + 10, wrap.clientWidth - 170)}px`; tooltip.style.top = `${Math.max(4, event.offsetY - 58)}px`; }); circle.addEventListener("mouseleave", () => { tooltip.style.display = "none"; }); });
  }
  grid.insertAdjacentHTML("afterbegin", '<p class="cms-demo-label">데모 운영 지표 · 목표·생산량·유형비는 예시 데이터</p>');
  const anchor = document.querySelector(".table") || document.querySelector(".cms-chart-anchor") || document.querySelector(".hero") || document.querySelector(".board-title") || document.querySelector("main");
  anchor.after(grid);
  const analysis = document.createElement("section"); analysis.className = "cms-analysis-grid";
  const gaugeValues = [["알람 활성율", 78, [["전체 발생건수", "#f2f4f7"], ["활성화된 알람 건수", "#f59d32"]]], ["조치 연계율", 64, [["전체 알람 건수", "#f2f4f7"], ["자동WO", "#2f6fed"], ["자동점검", "#18b88a"], ["수동조치", "#f59d32"]]], ["알람 조치율", 91, [["기간 내 총 알람 발생건수", "#f2f4f7"], ["조치완료(WO)", "#2f6fed"], ["조치완료(점검)", "#f59d32"]]]];
  const byEquipment = datasets.slice(0, 6).map((item, index) => [item.displayName || item.name || item.equipmentCode, Math.max(2, issue - index * 2)]);
  const byPerson = [["김현장", Math.max(2, Math.round(history.length * .34))], ["이관리", Math.max(2, Math.round(history.length * .27))], ["박정비", Math.max(2, Math.round(history.length * .22))], ["미배정", Math.max(1, Math.round(history.length * .17))]];
  const horizontal = (rows) => `<div class="cms-analysis-bars">${rows.map(([name, value]) => `<div class="cms-analysis-bar"><span>${esc(name)}</span><div class="cms-analysis-track"><i style="width:${value / max(rows.map((x) => x[1])) * 100}%"></i></div><b>${value}</b></div>`).join("")}</div>`;
  const monthly = ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"]; const monthlyValues = [52, 64, 58, 76, 69, 88, 82, 101, 94, 116, 108, 128]; const monthlyPoints = monthlyValues.map((value, index) => `${30 + index * (740 / 11)},${185 - value}`).join(" ");
  analysis.innerHTML = `<article class="cms-analysis-card wide"><div class="cms-chart-head"><h3>종합 View</h3><span>운영 지표 현황</span></div><div class="cms-gauge-row">${gaugeValues.map(([name, value, keys]) => { const segmentSize = value / (keys.length - 1); const segments = keys.slice(1).map(([, color], index) => `<path class="gauge-fill" style="stroke:${color}" pathLength="100" stroke-dasharray="${segmentSize} ${100 - segmentSize}" stroke-dashoffset="-${index * segmentSize}" d="M 15 100 A 85 85 0 0 1 185 100"/>`).join(""); return `<div class="cms-gauge-item"><span class="gauge-label">${name}</span><div class="cms-gauge-svg"><svg viewBox="0 0 200 118"><path class="gauge-base" d="M 15 100 A 85 85 0 0 1 185 100"/>${segments}<text x="100" y="96" text-anchor="middle">${value}%</text></svg></div><span class="gauge-description">${keys.map(([label, color]) => `<span class="gauge-key"><i style="background:${color}"></i>${label}</span>`).join("")}</span></div>`; }).join("")}</div></article><article class="cms-analysis-card"><div class="cms-chart-head"><h3>기준별 알람건수 · 설비별</h3><span>누계</span></div>${horizontal(byEquipment)}</article><article class="cms-analysis-card"><div class="cms-chart-head"><h3>기준별 알람건수 · 인원별</h3><span>누계</span></div>${horizontal(byPerson)}</article><article class="cms-analysis-card wide"><div class="cms-chart-head"><h3>Trend View</h3><span>12개월 현황</span></div><svg class="cms-line cms-trend" viewBox="0 0 800 220" preserveAspectRatio="xMidYMid meet"><line x1="30" y1="25" x2="770" y2="25"/><line x1="30" y1="105" x2="770" y2="105"/><line x1="30" y1="185" x2="770" y2="185"/><polyline points="${monthlyPoints}" />${monthlyValues.map((value, index) => `<circle title="${monthly[index]} · 알람 활성율 ${value}%" cx="${30 + index * (740 / 11)}" cy="${185 - value}" r="4" />`).join("")}</svg><div class="cms-month-grid">${monthly.map((month, index) => `<div class="cms-month-cell"><small>${month}</small><b>${monthlyValues[index]}%</b><span>활성 ${monthlyValues[index]}%</span></div>`).join("")}</div></article>`;
  analysis.querySelectorAll(".cms-analysis-bar").forEach((row) => { const label = row.querySelector("span")?.textContent || ""; const value = row.querySelector("b")?.textContent || ""; row.title = `${label} · ${value}건`; });
  analysis.querySelectorAll(".cms-gauge-svg").forEach((gauge, index) => { gauge.title = `${gaugeValues[index][0]} · ${gaugeValues[index][1]}%`; });
  analysis.querySelectorAll(".cms-gauge-svg").forEach((gauge, gaugeIndex) => {
    gauge.querySelectorAll(".gauge-fill").forEach((segment, segmentIndex) => {
      const [segmentLabel, segmentColor] = gaugeValues[gaugeIndex][2][segmentIndex + 1];
      segment.addEventListener("mouseenter", (event) => { dataTip.innerHTML = `<b>${gaugeValues[gaugeIndex][0]}</b><br>${segmentLabel}`; dataTip.style.display = "block"; dataTip.style.left = `${event.clientX + 12}px`; dataTip.style.top = `${event.clientY - 38}px`; });
      segment.addEventListener("mousemove", (event) => { dataTip.style.left = `${event.clientX + 12}px`; dataTip.style.top = `${event.clientY - 38}px`; });
      segment.addEventListener("mouseleave", () => { dataTip.style.display = "none"; });
    });
  });
  if (document.body.classList.contains("dashboard-ui6")) {
    const analysisCards = analysis.querySelectorAll(".cms-analysis-card");
    analysisCards[1]?.remove();
    analysisCards[2]?.remove();
  }
  const trendCard = analysis.querySelector(".cms-analysis-card:last-child");
  const trendChart = trendCard?.querySelector(".cms-trend");
  if (trendChart) {
    trendChart.setAttribute("preserveAspectRatio", "none");
    const axis = document.createElement("div");
    axis.className = "cms-trend-axis";
    axis.innerHTML = monthly.map((month) => `<span>${month}</span>`).join("");
    trendChart.after(axis);
    trendChart.querySelectorAll("circle").forEach((point, index) => {
      point.addEventListener("mouseenter", (event) => {
        dataTip.innerHTML = `<b>${monthly[index]}</b><br>알람 활성율 ${monthlyValues[index]}%`;
        dataTip.style.display = "block";
        dataTip.style.left = `${event.clientX + 12}px`;
        dataTip.style.top = `${event.clientY - 38}px`;
      });
      point.addEventListener("mousemove", (event) => {
        dataTip.style.left = `${event.clientX + 12}px`;
        dataTip.style.top = `${event.clientY - 38}px`;
      });
      point.addEventListener("mouseleave", () => { dataTip.style.display = "none"; });
    });
  }
  analysis.insertAdjacentHTML("afterbegin", '<p class="cms-demo-label">데모 운영 지표 · 조치율·인원별 지표·월별 추이는 예시 데이터</p>');
  analysis.setAttribute("aria-label", "데모 조치 및 추세 지표");
  grid.after(analysis);
}
init().catch((error) => console.error("CMS chart panels load failed", error));
