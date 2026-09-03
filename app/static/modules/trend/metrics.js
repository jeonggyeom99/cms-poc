import { palette, trendMetricStyles } from "../core/constants.js";
import { formatMetricReading } from "../core/format.js";
import {
  getDashboardData,
  getSelectedTrendMetrics,
  setSelectedTrendMetrics,
} from "../core/state.js";

export function syncTrendMetricSelector() {
  const selectedTrendMetrics = getSelectedTrendMetrics();
  document.querySelectorAll("[data-trend-metric]").forEach((input) => {
    const selected = selectedTrendMetrics.has(input.dataset.trendMetric);
    input.checked = selected;
    input.closest(".trend-metric-option").classList.toggle("selected", selected);
  });
}

export function renderTrendMetricSelector(data = getDashboardData()) {
  const grid = document.getElementById("trend-metric-grid");
  const metrics = data?.trend?.metrics ?? [];
  const selectedTrendMetrics = getSelectedTrendMetrics();
  grid.innerHTML = metrics.map((metric) => {
    const style = trendMetricStyles[metric.key] ?? { color: palette.teal, digits: 2 };
    const selected = selectedTrendMetrics.has(metric.key);
    return `
      <label class="trend-metric-option${selected ? " selected" : ""}${metric.available ? "" : " unavailable"}" style="--metric-color: ${style.color}">
        <span class="trend-metric-option-header">
          <input type="checkbox" data-trend-metric="${metric.key}" ${selected ? "checked" : ""} ${metric.available ? "" : "disabled"}>
          <span class="trend-metric-swatch" aria-hidden="true"></span>
          <span>${metric.label}</span>
        </span>
        <dl class="trend-metric-values">
          <div><dt>최신값</dt><dd>${formatMetricReading(metric, metric.latestValue)}</dd></div>
          <div><dt>주의</dt><dd class="caution-value">${formatMetricReading(metric, metric.warningThreshold)}</dd></div>
          <div><dt>위험</dt><dd class="danger-value">${formatMetricReading(metric, metric.dangerThreshold)}</dd></div>
        </dl>
      </label>`;
  }).join("");
}

export function bindTrendMetricSelector(onSelectionChanged) {
  document.getElementById("trend-metric-grid").addEventListener("change", (event) => {
    const input = event.target.closest("[data-trend-metric]");
    if (!input) return;

    const selectedTrendMetrics = new Set(getSelectedTrendMetrics());
    const metricKey = input.dataset.trendMetric;
    if (input.checked) {
      if (metricKey === "velocity") selectedTrendMetrics.delete("displacement");
      if (metricKey === "displacement") selectedTrendMetrics.delete("velocity");
      selectedTrendMetrics.add(metricKey);
    } else if (selectedTrendMetrics.size > 1) {
      selectedTrendMetrics.delete(metricKey);
    }

    setSelectedTrendMetrics(selectedTrendMetrics);
    syncTrendMetricSelector();
    onSelectionChanged();
  });
}
