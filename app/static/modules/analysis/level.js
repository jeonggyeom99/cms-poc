import { formatNumber, levelDifferenceLabel } from "../core/format.js?v=korean-ui-v1";

export function renderLevelAnalysis(data) {
  const analysis = data.levelAnalysis;
  const details = document.getElementById("level-details");

  if (!analysis || analysis.status === "unavailable") {
    details.className = "analysis-placeholder";
    details.innerHTML = "<strong>기준값 분석에 필요한 추세 데이터가 없습니다.</strong><p>경보 설정값은 종합 상태 판정에 사용하지 않습니다.</p>";
    return;
  }

  const rows = [
    ["주의 기준값", "warningThreshold", "caution"],
    ["위험 기준값", "dangerThreshold", "danger"],
  ];
  details.className = "level-analysis-details";
  details.innerHTML = `
    <div class="level-comparison-grid">
      ${rows.map(([label, key, status]) => `
        <section class="level-comparison-item ${status}">
          <h3>${label}</h3>
          <dl>
            <div><dt>현재 설정</dt><dd>${formatNumber(analysis.configured?.[key])} mm/s</dd></div>
            <div><dt>권고값</dt><dd>${formatNumber(analysis.recommended[key])} mm/s</dd></div>
          </dl>
          <p>${levelDifferenceLabel(analysis.difference?.[key] ?? null)}</p>
        </section>`).join("")}
    </div>`;
}
