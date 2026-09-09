export function setPeriodTabsEnabled(enabled) {
  document.querySelectorAll("[data-period]").forEach((button) => {
    button.disabled = !enabled;
  });
}

export function setExpandButtonEnabled(graphType, enabled) {
  const button = document.querySelector(`[data-expand-graph="${graphType}"]`);
  const graphLabel = {
    trend: "Trend",
    fft: "FFT",
    timewave: "TimeWaveSampling",
  }[graphType] ?? graphType;
  button.disabled = !enabled;
  button.title = enabled ? `${graphLabel} Graph 크게 보기` : `${graphLabel} 데이터 없음`;
  button.setAttribute("aria-label", button.title);
}

export function syncPeriodTabs(currentPeriod) {
  document.querySelectorAll("[data-period]").forEach((button) => {
    button.classList.toggle("active", button.dataset.period === currentPeriod);
  });
}

export function bindPeriodTabs(onPeriodChange) {
  document.querySelectorAll("[data-period]").forEach((button) => {
    button.addEventListener("click", () => onPeriodChange(button.dataset.period));
  });
}
