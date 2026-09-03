import {
  fetchDashboard,
  fetchDatasetSummaries,
  fetchFftRecord,
} from "../api/dashboard.js";
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
  getExpandedGraph,
  getSelectedTrendMetrics,
  isCurrentFftSelectionRequest,
  resetCurrentPeriod,
  resetFftRecordState,
  resetSelectedTrendMetrics,
  setCurrentPeriod,
  setDashboardData,
} from "../core/state.js";
import { renderPlot, setPlotEmpty } from "../core/plot.js?v=plot-zoom-bounds";
import { availabilityLabel } from "../core/format.js";
import { renderFftAnalysis, renderOverviewFftResult } from "../fft/analysis.js?v=compact-fft-summary";
import { buildFftFigure, renderFftChart } from "../fft/chart.js?v=plot-zoom-bounds";
import {
  renderFftMetadata,
  renderFftRecordList,
  setFftRecordStatus,
  syncFftRecordSelection,
} from "../fft/records.js";
import { bindGraphModal, openExpandedGraph } from "../modal/modal.js?v=plot-zoom-bounds";
import { populateSummary } from "../summary/summary.js?v=compact-fft-summary";
import {
  buildExpandedTrendFigure,
  renderTrend,
} from "../trend/chart.js?v=plot-zoom-bounds";
import { bindTrendMetricSelector } from "../trend/metrics.js";

function renderFft() {
  const fft = getDashboardData()?.fft;
  renderOverviewFftResult(fft);
  renderFftRecordList(fft);
  renderFftChart(fft);
  if (fft?.isAlertFft) {
    renderFftMetadata(fft);
    renderFftAnalysis(fft);
    return;
  }

  renderFftMetadata(null);
  renderFftAnalysis(null, fft ? {
    resultLabel: "대상 없음",
    description: "주의·위험경보 중 최대 진폭이 0.5를 초과한 FFT 기록만 표시합니다.",
    heading: "표시할 경보 FFT가 없습니다.",
    detail: "좌측 목록에 대상 기록이 생기면 그래프와 분석 결과를 확인할 수 있습니다.",
  } : {});
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
    renderPlot("graph-modal-chart", buildFftFigure(dashboardData.fft));
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
  openExpandedGraph(graphType, trigger, renderExpandedGraph);
}

function requestedDatasetId(items) {
  const datasetId = new URLSearchParams(window.location.search).get("dataset");
  return items.some((item) => item.id === datasetId) ? datasetId : items[0].id;
}

function replaceDatasetIdInUrl(datasetId) {
  const url = new URL(window.location.href);
  url.searchParams.set("dataset", datasetId);
  window.history.replaceState(window.history.state, "", url);
}

async function selectFftRecord(recordId) {
  const dashboardData = getDashboardData();
  const fft = dashboardData?.fft;
  const isAlertRecord = fft?.records?.some(
    (record) => record.id === recordId && record.isAlertFft,
  );
  if (!fft || !isAlertRecord || recordId === fft.recordId) return;

  const requestId = createFftSelectionRequest();
  const list = document.getElementById("fft-record-list");
  list.setAttribute("aria-busy", "true");
  syncFftRecordSelection(fft, recordId);
  setFftRecordStatus("선택한 FFT를 불러오는 중...");

  try {
    let record = getCachedFftRecord(recordId);
    if (!record) {
      const datasetId = dashboardData.meta.datasetId;
      record = await fetchFftRecord(datasetId, recordId);
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
    renderFft();
    if (getExpandedGraph() === "fft") {
      renderExpandedGraph();
    }
  } catch (error) {
    if (!isCurrentFftSelectionRequest(requestId)) return;
    console.error("FFT record loading failed", error);
    syncFftRecordSelection(fft);
    setFftRecordStatus("선택한 FFT를 불러오지 못했습니다.", true);
  } finally {
    if (isCurrentFftSelectionRequest(requestId)) list.removeAttribute("aria-busy");
  }
}

export async function loadDashboard(datasetId) {
  const select = document.getElementById("dataset-select");
  resetFftRecordState();
  select.disabled = true;
  setExpandButtonEnabled("trend", false);
  setExpandButtonEnabled("fft", false);
  try {
    const dashboardData = await fetchDashboard(datasetId);
    setDashboardData(dashboardData);
    if (dashboardData.fft) {
      const { records, ...selectedRecord } = dashboardData.fft;
      cacheFftRecord(selectedRecord.recordId, selectedRecord);
    }
    resetCurrentPeriod();
    syncPeriodTabs(getCurrentPeriod());
    resetSelectedTrendMetrics(dashboardData);
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
    renderFftAnalysis(null, {
      resultLabel: "불러오기 실패",
      description: "FFT 분석 데이터를 불러오지 못했습니다.",
      heading: "FFT 분석을 표시할 수 없습니다.",
      detail: "설비 데이터를 다시 선택해 주세요.",
    });
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

export function initializeDashboardApplication() {
  bindPeriodTabs(handlePeriodChange);
  bindGraphModal({
    onExpandGraph: handleOpenExpandedGraph,
    onFftRecordSelect: selectFftRecord,
  });
  bindTrendMetricSelector(handleTrendMetricSelectionChange);
  initializeDashboard();
}
