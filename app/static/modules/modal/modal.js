import {
  clearExpandedGraph,
  getDashboardData,
  setExpandedGraph,
} from "../core/state.js";
import { getPlotly } from "../core/plot.js?v=plot-zoom-bounds";
import { renderTrendMetricSelector } from "../trend/metrics.js";

function cleanupExpandedGraph() {
  if (!document.body.classList.contains("graph-modal-open")) return;

  const modal = document.getElementById("graph-modal");
  const modalPlot = document.getElementById("graph-modal-chart");
  getPlotly().purge(modalPlot);
  modalPlot.className = "plot graph-modal-plot";
  modalPlot.textContent = "";
  modal.querySelector(".graph-modal-body").classList.remove("fft-expanded");
  document.body.classList.remove("graph-modal-open");
  const trigger = clearExpandedGraph();
  trigger?.focus();
}

export function openExpandedGraph(graphType, trigger, renderExpandedGraph) {
  const dashboardData = getDashboardData();
  if (!dashboardData?.[graphType]) return;

  const modal = document.getElementById("graph-modal");
  const modalBody = modal.querySelector(".graph-modal-body");
  const isTrend = graphType === "trend";
  setExpandedGraph(graphType, trigger);

  document.getElementById("graph-modal-title").textContent = isTrend
    ? "Trend Graph"
    : "FFT Graph";
  document.getElementById("graph-modal-chart").setAttribute(
    "aria-label",
    isTrend ? "확대된 진동 속도 추세 그래프" : "확대된 FFT 주파수 스펙트럼 그래프",
  );

  const periodTabs = document.getElementById("graph-modal-period-tabs");
  const trendMetricSelector = document.getElementById("trend-metric-selector");
  const fftHistoryBrowser = document.getElementById("fft-history-browser");
  periodTabs.hidden = !isTrend;
  trendMetricSelector.hidden = !isTrend;
  fftHistoryBrowser.hidden = isTrend;
  modalBody.classList.toggle("fft-expanded", !isTrend);
  if (isTrend) {
    renderTrendMetricSelector(dashboardData);
  }

  modal.showModal();
  document.body.classList.add("graph-modal-open");
  renderExpandedGraph();
  requestAnimationFrame(renderExpandedGraph);
}

export function closeExpandedGraph() {
  const modal = document.getElementById("graph-modal");
  if (modal.open) modal.close();
  cleanupExpandedGraph();
}

export function bindGraphModal({ onExpandGraph, onFftRecordSelect }) {
  const modal = document.getElementById("graph-modal");
  const modalPlot = document.getElementById("graph-modal-chart");

  document.querySelectorAll("[data-expand-graph]").forEach((button) => {
    button.addEventListener("click", () => onExpandGraph(button.dataset.expandGraph, button));
  });
  document.getElementById("graph-modal-close").addEventListener("click", closeExpandedGraph);
  ["fft-record-list", "fft-history-list"].forEach((listId) => document.getElementById(listId).addEventListener("click", (event) => {
    const button = event.target.closest("[data-fft-record-id]");
    if (button) onFftRecordSelect(Number(button.dataset.fftRecordId));
  }));
  ["fft-record-list", "fft-history-list"].forEach((listId) => document.getElementById(listId).addEventListener("keydown", (event) => {
    if (event.key !== "ArrowDown") return;
    const current = event.target.closest("[data-fft-record-id]");
    const next = current?.nextElementSibling;
    if (!next?.matches("[data-fft-record-id]")) return;
    event.preventDefault();
    next.focus();
    onFftRecordSelect(Number(next.dataset.fftRecordId));
  }));
  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeExpandedGraph();
  });
  modal.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeExpandedGraph();
    }
  });
  modal.addEventListener("close", cleanupExpandedGraph);
  window.addEventListener("resize", () => {
    if (modal.open && modalPlot.data) getPlotly().Plots.resize(modalPlot);
  });
}
