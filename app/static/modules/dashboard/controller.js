import {
  fetchDashboard,
  fetchDatasetSummaries,
  fetchFftRecord,
} from "../api/dashboard.js?v=fft-load-fix";
import { fetchAiAnalysis } from "../api/ai-analysis.js?v=ai-analysis-v1";
import {
  bindAiAnalysis,
  renderAiAnalysis,
  renderAiAnalysisError,
  resetAiAnalysis,
  setAiAnalysisLoading,
} from "../analysis/ai.js?v=korean-ui-v1";
import {
  bindEmailDraft,
  resetEmailDraft,
  setEmailDraftAvailable,
} from "../report/email-draft.js?v=korean-ui-v1";
import {
  bindPptExport,
  resetPptExport,
  setPptExportAvailable,
} from "../report/ppt-export.js?v=korean-ui-v1";
import { renderLevelAnalysis } from "../analysis/level.js?v=korean-ui-v1";
import {
  bindPeriodTabs,
  setExpandButtonEnabled,
  syncPeriodTabs,
} from "../controls/controls.js?v=korean-ui-v1";
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
import { availabilityLabel } from "../core/format.js?v=korean-ui-v2";
import { renderFftAnalysis, renderOverviewFftResult } from "../fft/analysis.js?v=korean-ui-v1";
import { buildFftFigure, renderFftChart } from "../fft/chart.js?v=korean-ui-v2";
import { buildTimeWaveFigure, renderTimeWaveChart } from "../timewave/chart.js?v=korean-ui-v2";
import {
  renderFftMetadata,
  renderFftHistoryList,
  renderFftRecordList,
  resetFftRecordFilters,
  setFftRecordStatus,
  setFftHistoryStatus,
  syncFftRecordSelection,
  toggleFftRecordFilter,
} from "../fft/records.js?v=korean-ui-v2";
import {
  bindRelatedHistory,
  renderRelatedHistory,
  resetRelatedHistoryExpansion,
} from "../fft/related-history.js?v=korean-ui-v1";
import { fetchRelatedHistory } from "../api/history.js?v=cms-history-v1";
import { bindGraphModal, openExpandedGraph } from "../modal/modal.js?v=korean-ui-v1";
import { populateSummary } from "../summary/summary.js?v=korean-ui-v1";
import {
  buildExpandedTrendFigure,
  renderTrend,
} from "../trend/chart.js?v=korean-ui-v2";
import { bindTrendMetricSelector } from "../trend/metrics.js";
import { bindEnvelope, loadEnvelope, resetEnvelope } from "../envelope/controller.js?v=korean-ui-v1";
import { syncDashboardChatContext } from "../chat/controller.js?v=dashboard-chat-v1";

let aiAnalysisRequest = 0;
let relatedHistoryRequest = 0;

function buildReportRequest() {
  const dashboardData = getDashboardData();
  const recordId = dashboardData?.fft?.recordId;
  if (!dashboardData?.meta?.datasetId || !Number.isInteger(recordId)) return null;
  return {
    datasetId: dashboardData.meta.datasetId,
    recordId,
    selectedFaultType: getSelectedBearingFaultType(),
    until: requestedUntil(),
    force: false,
  };
}

function resetReportActionsFor(fft) {
  const available = Boolean(fft?.recordId);
  resetPptExport();
  resetEmailDraft();
  setPptExportAvailable(available);
  setEmailDraftAvailable(available);
}

function resetAiAnalysisFor(fft) {
  aiAnalysisRequest += 1;
  resetAiAnalysis({ available: Boolean(fft?.recordId) });
  resetReportActionsFor(fft);
}

async function loadRelatedHistoryFor(fft, selectedBearingFaultType) {
  const dashboard = getDashboardData();
  if (!dashboard?.meta?.datasetId || !fft?.recordId) return renderRelatedHistory(null, []);
  const requestId = ++relatedHistoryRequest;
  try {
    const payload = await fetchRelatedHistory(
      dashboard.meta.datasetId, fft.recordId, selectedBearingFaultType, requestedUntil(),
    );
    // A newer FFT/fault selection owns the screen; never let an old response overwrite it.
    if (requestId !== relatedHistoryRequest) return;
    renderRelatedHistory(payload.faultTag, payload.items);
  } catch (error) {
    if (requestId !== relatedHistoryRequest) return;
    console.error("Related CMS history loading failed", error);
    renderRelatedHistory(null, []);
  }
}

function renderFft() {
  const fft = getDashboardData()?.fft;
  if (fft?.analysis?.diagnosis?.faults?.length && !getSelectedBearingFaultType()) {
    resetSelectedBearingFaultType(fft);
  }
  const selectedBearingFaultType = getSelectedBearingFaultType();
  renderOverviewFftResult(fft);
  renderFftRecordList(fft);
  renderFftChart(fft, selectedBearingFaultType);
  renderTimeWaveChart(fft);
  if (fft?.isAlertFft) {
    renderFftMetadata(fft);
    renderFftAnalysis(fft, selectedBearingFaultType, {}, null);
    loadRelatedHistoryFor(fft, selectedBearingFaultType);
    return;
  }

  renderFftMetadata(null);
  renderFftAnalysis(null, null, fft ? {
    resultLabel: "대상 없음",
    description: "최대 진폭이 0.5를 초과하거나 주의·위험경보인 주파수 기록만 표시합니다.",
    heading: "표시할 주파수 분석 대상이 없습니다.",
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
  } else if (getExpandedGraph() === "timewave" && dashboardData?.fft) {
    renderPlot("graph-modal-chart", buildTimeWaveFigure(dashboardData.fft));
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
  if (["fft", "timewave"].includes(graphType)) renderFftHistoryList(getDashboardData()?.fft);
  openExpandedGraph(graphType, trigger, renderExpandedGraph);
}

function requestedDatasetId(items) {
  const datasetId = new URLSearchParams(window.location.search).get("dataset");
  return items.some((item) => item.id === datasetId) ? datasetId : items[0].id;
}

function requestedUntil() {
  return new URLSearchParams(window.location.search).get("until");
}

function requestedStart() {
  return new URLSearchParams(window.location.search).get("start");
}

function replaceDatasetIdInUrl(datasetId) {
  const url = new URL(window.location.href);
  url.searchParams.set("dataset", datasetId);
  url.searchParams.delete("until");
  url.searchParams.delete("start");
  window.history.replaceState(window.history.state, "", url);
}

async function runAiAnalysis(force) {
  const dashboardData = getDashboardData();
  const fft = dashboardData?.fft;
  if (!dashboardData?.meta?.datasetId || !fft?.recordId) {
    resetAiAnalysisFor(null);
    return;
  }

  const requestId = ++aiAnalysisRequest;
  setAiAnalysisLoading();
  try {
    const payload = await fetchAiAnalysis(dashboardData.meta.datasetId, {
      recordId: fft.recordId,
      selectedFaultType: getSelectedBearingFaultType(),
      until: requestedUntil(),
      force,
    });
    if (requestId !== aiAnalysisRequest) return;
    renderAiAnalysis(payload);
  } catch (error) {
    if (requestId !== aiAnalysisRequest) return;
    console.error("AI analysis loading failed", error);
    renderAiAnalysisError(error.message || "인공지능 분석을 실행하지 못했습니다. 잠시 후 다시 시도해 주세요.");
  }
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
  setFftRecordStatus("선택한 주파수 기록을 불러오는 중...");
  setFftHistoryStatus("선택한 주파수 기록을 불러오는 중...");

  try {
    let record = getCachedFftRecord(recordId);
    if (!record) {
      const datasetId = dashboardData.meta.datasetId;
      record = await fetchFftRecord(datasetId, recordId, requestedUntil(), requestedStart());
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
    syncDashboardChatContext();
    resetAiAnalysisFor(updatedDashboardData.fft);
    setFftHistoryStatus(`${fft.records.length.toLocaleString("ko-KR")}개 측정 기록`);
    if (getExpandedGraph() === "fft") {
      renderExpandedGraph();
    }
  } catch (error) {
    if (!isCurrentFftSelectionRequest(requestId)) return;
    console.error("FFT record loading failed", error);
    syncFftRecordSelection(fft);
    setFftRecordStatus("선택한 주파수 기록을 불러오지 못했습니다.", true);
    setFftHistoryStatus("선택한 주파수 기록을 불러오지 못했습니다.", true);
  } finally {
    if (isCurrentFftSelectionRequest(requestId)) list.removeAttribute("aria-busy");
  }
}

export async function loadDashboard(datasetId) {
  resetEnvelope();
  const select = document.getElementById("dataset-select");
  resetFftRecordState();
  resetRelatedHistoryExpansion();
  resetFftRecordFilters();
  resetAiAnalysisFor(null);
  select.disabled = true;
  setExpandButtonEnabled("trend", false);
  setExpandButtonEnabled("fft", false);
  setExpandButtonEnabled("timewave", false);
  try {
    const dashboardData = await fetchDashboard(datasetId, requestedUntil(), requestedStart());
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
    syncDashboardChatContext();
    renderLevelAnalysis(dashboardData);
    loadEnvelope(dashboardData, requestedUntil());
    resetAiAnalysisFor(dashboardData.fft);
  } catch (error) {
    console.error("Dashboard data loading failed", error);
    resetEnvelope("설비 데이터를 불러오지 못해 포락선 분석을 준비할 수 없습니다.");
    setExpandButtonEnabled("trend", false);
    setExpandButtonEnabled("fft", false);
    setExpandButtonEnabled("timewave", false);
    setPlotEmpty("trend-chart", "설비 데이터를 불러오지 못했습니다.", true);
    setPlotEmpty("fft-chart", "설비 데이터를 불러오지 못했습니다.", true);
    setPlotEmpty("timewave-chart", "설비 데이터를 불러오지 못했습니다.", true);
    renderOverviewFftResult(null);
    renderFftRecordList(null);
    renderFftMetadata(null);
    renderFftAnalysis(null, null, {
      resultLabel: "불러오기 실패",
      description: "주파수 분석 데이터를 불러오지 못했습니다.",
      heading: "주파수 분석을 표시할 수 없습니다.",
      detail: "설비 데이터를 다시 선택해 주세요.",
    });
    renderRelatedHistory(null, []);
    renderLevelAnalysis({ levelAnalysis: null });
    resetAiAnalysis({
      available: false,
      heading: "설비 데이터를 불러오지 못했습니다.",
      detail: "설비 데이터를 다시 선택한 후 인공지능 분석을 실행해 주세요.",
    });
    resetReportActionsFor(null);
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
      setPlotEmpty("trend-chart", "데이터 폴더에서 추세 파일을 찾지 못했습니다.");
      setPlotEmpty("fft-chart", "데이터 폴더에서 주파수 파일을 찾지 못했습니다.");
      setPlotEmpty("timewave-chart", "데이터 폴더에서 주파수 파일을 찾지 못했습니다.");
      setExpandButtonEnabled("trend", false);
      setExpandButtonEnabled("fft", false);
      setExpandButtonEnabled("timewave", false);
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
    setPlotEmpty("timewave-chart", "CSV 목록을 불러오지 못했습니다.", true);
    setExpandButtonEnabled("trend", false);
    setExpandButtonEnabled("fft", false);
    setExpandButtonEnabled("timewave", false);
  }
}

export function initializeDashboardApplication() {
  bindEnvelope();
  bindPeriodTabs(handlePeriodChange);
  bindGraphModal({
    onExpandGraph: handleOpenExpandedGraph,
    onFftRecordSelect: selectFftRecord,
  });
  bindTrendMetricSelector(handleTrendMetricSelectionChange);
  bindRelatedHistory();
  bindAiAnalysis(runAiAnalysis);
  bindPptExport(buildReportRequest);
  bindEmailDraft(buildReportRequest);
  document.getElementById("fft-analysis-details").addEventListener("click", (event) => {
    const button = event.target.closest("[data-bearing-fault]");
    if (!button) return;
    setSelectedBearingFaultType(button.dataset.bearingFault);
    renderFft();
    syncDashboardChatContext();
    resetAiAnalysisFor(getDashboardData()?.fft);
    if (getExpandedGraph() === "fft") renderExpandedGraph();
  });
  document.getElementById("fft-record-browser").addEventListener("click", (event) => {
    const button = event.target.closest("[data-fft-filter-group]");
    if (!button) return;
    toggleFftRecordFilter(button.dataset.fftFilterGroup, button.dataset.fftFilterValue);
    renderFftRecordList(getDashboardData()?.fft);
  });
  initializeDashboard();
}
