import {
  fetchDashboard,
  fetchDatasetSummaries,
  fetchFftRecord,
} from "../api/dashboard.js?v=fft-load-fix";
import { renderLevelAnalysis } from "../analysis/level.js";
import {
  bindPeriodTabs,
  setExpandButtonEnabled,
  syncPeriodTabs,
} from "../controls/controls.js";
import {
  cacheFftRecord,
  createFftSelectionRequest,
  getCachedFftRecord,
  getCurrentPeriod,
  getDashboardData,
  getSelectedBearingFaultType,
  getExpandedGraph,
  getSelectedTrendMetrics,
  isCurrentFftSelectionRequest,
  resetCurrentPeriod,
  resetFftRecordState,
  resetSelectedTrendMetrics,
  resetSelectedBearingFaultType,
  setCurrentPeriod,
  setDashboardData,
  setSelectedBearingFaultType,
} from "../core/state.js?v=acceleration-bearing-fft";
import { renderPlot, setPlotEmpty } from "../core/plot.js?v=plot-zoom-bounds";
import { availabilityLabel } from "../core/format.js";
import { renderFftAnalysis, renderOverviewFftResult } from "../fft/analysis.js?v=acceleration-bearing-fft-v4";
import { buildFftFigure, renderFftChart } from "../fft/chart.js?v=acceleration-bearing-fft";
import {
  renderFftMetadata,
  renderFftHistoryList,
  renderFftRecordList,
  resetFftRecordFilters,
  setFftRecordStatus,
  setFftHistoryStatus,
  syncFftRecordSelection,
  toggleFftRecordFilter,
} from "../fft/records.js?v=acceleration-bearing-fft-v7";
import {
  bindRelatedHistory,
  matchingHistoryItems,
  relatedHistoryTag,
  renderRelatedHistory,
  resetRelatedHistoryExpansion,
} from "../fft/related-history.js?v=fft-related-history-v1";
import { fetchHistory } from "../api/history.js?v=cms-history-v1";
import { bindGraphModal, openExpandedGraph } from "../modal/modal.js?v=plot-zoom-bounds";
import { populateSummary } from "../summary/summary.js?v=compact-fft-summary";
import {
  buildExpandedTrendFigure,
  renderTrend,
} from "../trend/chart.js?v=plot-zoom-bounds";
import { bindTrendMetricSelector } from "../trend/metrics.js";

let historyItems = [];

function relatedHistoryFor(fft, selectedBearingFaultType) {
  const tag = relatedHistoryTag(fft, selectedBearingFaultType);
  const items = matchingHistoryItems(historyItems, tag);
  return { tag: items.length ? tag : null, items };
}

function renderFft() {
  const fft = getDashboardData()?.fft;
  if (fft?.analysis?.diagnosis?.faults?.length && !getSelectedBearingFaultType()) {
    resetSelectedBearingFaultType(fft);
  }
  const selectedBearingFaultType = getSelectedBearingFaultType();
  const relatedHistory = relatedHistoryFor(fft, selectedBearingFaultType);
  renderOverviewFftResult(fft);
  renderFftRecordList(fft);
  renderFftChart(fft, selectedBearingFaultType);
  if (fft?.isAlertFft) {
    renderFftMetadata(fft);
    renderFftAnalysis(fft, selectedBearingFaultType, {}, relatedHistory.tag);
    renderRelatedHistory(relatedHistory.tag, relatedHistory.items);
    return;
  }

  renderFftMetadata(null);
  renderFftAnalysis(null, null, fft ? {
    resultLabel: "대상 없음",
    description: "최대 진폭이 0.5를 초과하거나 주의·위험경보인 FFT 기록만 표시합니다.",
    heading: "표시할 FFT 분석 대상이 없습니다.",
    detail: "좌측 목록에 대상 기록이 생기면 그래프와 분석 결과를 확인할 수 있습니다.",
  } : {});
  renderRelatedHistory(null, []);
}

function renderExpandedGraph() {
  const dashboardData = getDashboardData();
  if (getExpandedGraph() === "trend") {
    renderPlot(
      "graph-modal-chart",
      buildExpandedTrendFigure(
        getCurrentPeriod(),
        dashboardData,
        getSelectedTrendMetrics(),
      ),
    );
  } else if (getExpandedGraph() === "fft" && dashboardData?.fft) {
    renderPlot("graph-modal-chart", buildFftFigure(dashboardData.fft, getSelectedBearingFaultType()));
  }
}

function handlePeriodChange(period) {
  setCurrentPeriod(period);
  syncPeriodTabs(getCurrentPeriod());
  renderTrend(getCurrentPeriod(), getDashboardData());
  if (getExpandedGraph() === "trend") renderExpandedGraph();
}

function handleTrendMetricSelectionChange() {
  if (getExpandedGraph() === "trend") renderExpandedGraph();
}

function handleOpenExpandedGraph(graphType, trigger) {
  if (graphType === "fft") renderFftHistoryList(getDashboardData()?.fft);
  openExpandedGraph(graphType, trigger, renderExpandedGraph);
}

function requestedDatasetId(items) {
  const datasetId = new URLSearchParams(window.location.search).get("dataset");
  return items.some((item) => item.id === datasetId) ? datasetId : items[0].id;
}

function requestedUntil() {
  return new URLSearchParams(window.location.search).get("until");
}

function replaceDatasetIdInUrl(datasetId) {
  const url = new URL(window.location.href);
  url.searchParams.set("dataset", datasetId);
  url.searchParams.delete("until");
  window.history.replaceState(window.history.state, "", url);
}

async function selectFftRecord(recordId) {
  const dashboardData = getDashboardData();
  const fft = dashboardData?.fft;
  const recordExists = fft?.records?.some((record) => record.id === recordId);
  if (!fft || !recordExists || recordId === fft.recordId) return;

  const requestId = createFftSelectionRequest();
  resetRelatedHistoryExpansion();
  const list = document.getElementById("fft-record-list");
  list.setAttribute("aria-busy", "true");
  syncFftRecordSelection(fft, recordId);
  setFftRecordStatus("선택한 FFT를 불러오는 중...");
  setFftHistoryStatus("선택한 FFT를 불러오는 중...");

  try {
    let record = getCachedFftRecord(recordId);
    if (!record) {
      const datasetId = dashboardData.meta.datasetId;
      record = await fetchFftRecord(datasetId, recordId, requestedUntil());
      cacheFftRecord(recordId, record);
    }
    if (!isCurrentFftSelectionRequest(requestId)) return;
    if (!record || !Array.isArray(record.frequencies) || !Array.isArray(record.amplitudes)) {
      throw new Error("Invalid FFT record structure");
    }

    const updatedDashboardData = {
      ...dashboardData,
      fft: { ...fft, ...record, records: fft.records },
    };
    setDashboardData(updatedDashboardData);
    resetSelectedBearingFaultType(updatedDashboardData.fft);
    renderFft();
    setFftHistoryStatus(`${fft.records.length.toLocaleString("ko-KR")}개 측정 기록`);
    if (getExpandedGraph() === "fft") {
      renderExpandedGraph();
    }
  } catch (error) {
    if (!isCurrentFftSelectionRequest(requestId)) return;
    console.error("FFT record loading failed", error);
    syncFftRecordSelection(fft);
    setFftRecordStatus("선택한 FFT를 불러오지 못했습니다.", true);
    setFftHistoryStatus("선택한 FFT를 불러오지 못했습니다.", true);
  } finally {
    if (isCurrentFftSelectionRequest(requestId)) list.removeAttribute("aria-busy");
  }
}

export async function loadDashboard(datasetId) {
  const select = document.getElementById("dataset-select");
  resetFftRecordState();
  resetRelatedHistoryExpansion();
  resetFftRecordFilters();
  select.disabled = true;
  setExpandButtonEnabled("trend", false);
  setExpandButtonEnabled("fft", false);
  try {
    const dashboardData = await fetchDashboard(datasetId, requestedUntil());
    setDashboardData(dashboardData);
    if (dashboardData.fft) {
      const { records, ...selectedRecord } = dashboardData.fft;
      cacheFftRecord(selectedRecord.recordId, selectedRecord);
    }
    resetCurrentPeriod();
    syncPeriodTabs(getCurrentPeriod());
    resetSelectedTrendMetrics(dashboardData);
    resetSelectedBearingFaultType(dashboardData.fft);
    populateSummary(dashboardData);
    renderTrend(getCurrentPeriod(), dashboardData);
    renderFft();
    renderLevelAnalysis(dashboardData);
  } catch (error) {
    console.error("Dashboard data loading failed", error);
    setExpandButtonEnabled("trend", false);
    setExpandButtonEnabled("fft", false);
    setPlotEmpty("trend-chart", "설비 데이터를 불러오지 못했습니다.", true);
    setPlotEmpty("fft-chart", "설비 데이터를 불러오지 못했습니다.", true);
    renderOverviewFftResult(null);
    renderFftRecordList(null);
    renderFftMetadata(null);
    renderFftAnalysis(null, null, {
      resultLabel: "불러오기 실패",
      description: "FFT 분석 데이터를 불러오지 못했습니다.",
      heading: "FFT 분석을 표시할 수 없습니다.",
      detail: "설비 데이터를 다시 선택해 주세요.",
    });
    renderRelatedHistory(null, []);
    renderLevelAnalysis({ levelAnalysis: null });
  } finally {
    select.disabled = false;
  }
}

async function initializeDashboard() {
  const select = document.getElementById("dataset-select");
  try {
    const items = await fetchDatasetSummaries();
    if (!items.length) {
      select.innerHTML = '<option value="">사용 가능한 CSV 데이터가 없습니다.</option>';
      setPlotEmpty("trend-chart", "data/ 폴더에서 Trend CSV를 찾지 못했습니다.");
      setPlotEmpty("fft-chart", "data/ 폴더에서 FFT CSV를 찾지 못했습니다.");
      setExpandButtonEnabled("trend", false);
      setExpandButtonEnabled("fft", false);
      return;
    }

    select.replaceChildren(
      ...items.map(
        (item) => new Option(
          `#${item.id} · ${item.equipmentCode} · ${item.name} (${availabilityLabel(item.availability)})`,
          item.id,
        ),
      ),
    );
    select.disabled = false;
    select.addEventListener("change", () => {
      replaceDatasetIdInUrl(select.value);
      loadDashboard(select.value);
    });
    const initialDatasetId = requestedDatasetId(items);
    select.value = initialDatasetId;
    await loadDashboard(initialDatasetId);
  } catch (error) {
    console.error("Dataset list loading failed", error);
    select.innerHTML = '<option value="">CSV 목록을 불러오지 못했습니다.</option>';
    setPlotEmpty("trend-chart", "CSV 목록을 불러오지 못했습니다.", true);
    setPlotEmpty("fft-chart", "CSV 목록을 불러오지 못했습니다.", true);
    setExpandButtonEnabled("trend", false);
    setExpandButtonEnabled("fft", false);
  }
}

async function loadRelatedHistory() {
  try {
    const payload = await fetchHistory();
    historyItems = payload.items;
    renderFft();
  } catch (error) {
    console.error("Related CMS history loading failed", error);
  }
}

export function initializeDashboardApplication() {
  bindPeriodTabs(handlePeriodChange);
  bindGraphModal({
    onExpandGraph: handleOpenExpandedGraph,
    onFftRecordSelect: selectFftRecord,
  });
  bindTrendMetricSelector(handleTrendMetricSelectionChange);
  bindRelatedHistory();
  document.getElementById("fft-analysis-details").addEventListener("click", (event) => {
    const button = event.target.closest("[data-bearing-fault]");
    if (!button) return;
    setSelectedBearingFaultType(button.dataset.bearingFault);
    renderFft();
    if (getExpandedGraph() === "fft") renderExpandedGraph();
  });
  document.getElementById("fft-record-browser").addEventListener("click", (event) => {
    const button = event.target.closest("[data-fft-filter-group]");
    if (!button) return;
    toggleFftRecordFilter(button.dataset.fftFilterGroup, button.dataset.fftFilterValue);
    renderFftRecordList(getDashboardData()?.fft);
  });
  initializeDashboard();
  loadRelatedHistory();
}
