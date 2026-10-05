import {
  fetchDashboard,
  fetchDatasetSummaries,
  fetchFftRecord,
} from "../api/dashboard.js?v=fft-load-fix";
import { fetchAiAnalysis } from "../api/ai-analysis.js?v=equipment-ai-v4";
import {
  bindAiAnalysis,
  renderAiAnalysis,
  renderAiAnalysisError,
  resetAiAnalysis,
  setAiAnalysisLoading,
} from "../analysis/ai.js?v=equipment-ai-v4";
import {
  bindEmailDraft,
  resetEmailDraft,
  setEmailDraftAvailable,
} from "../report/email-draft.js?v=equipment-ai-v1";
import {
  bindPptExport,
  resetPptExport,
  setPptExportAvailable,
} from "../report/ppt-export.js?v=ppt-ui-validation-v1";
import { renderLevelAnalysis } from "../analysis/level.js?v=korean-ui-v1";
import {
  setExpandButtonEnabled,
} from "../controls/controls.js?v=korean-ui-v1";
import {
  cacheFftRecord,
  createFftSelectionRequest,
  getAiDiagnosisReference,
  getCachedFftRecord,
  getCurrentPeriod,
  getDashboardData,
  getSelectedBearingFaultType,
  getSelectedFftRecord,
  getExpandedGraph,
  getSelectedTrendMetrics,
  isCurrentFftSelectionRequest,
  resetCurrentPeriod,
  resetFftRecordState,
  resetSelectedTrendMetrics,
  resetSelectedBearingFaultType,
  setAiDiagnosisReference,
  setDashboardData,
  setSelectedBearingFaultType,
  setSelectedFftRecord,
} from "../core/state.js?v=fft-current-history-v1";
import { renderPlot, setPlotEmpty } from "../core/plot.js?v=plot-zoom-bounds";
import { availabilityLabel } from "../core/format.js?v=fft-current-history-v2";
import { renderFftAnalysis, renderOverviewFftResult } from "../fft/analysis.js?v=fft-layout-restore-v1";
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
} from "../fft/records.js?v=fft-current-history-v2";
import {
  bindRelatedHistory,
  renderRelatedHistory,
  resetRelatedHistoryExpansion,
} from "../fft/related-history.js?v=korean-ui-v1";
import { fetchRelatedHistory } from "../api/history.js?v=cms-history-v1";
import { bindGraphModal, openExpandedGraph } from "../modal/modal.js?v=equipment-ai-v4-korean-ui-v1";
import { populateSummary } from "../summary/summary.js?v=korean-ui-v1";
import {
  buildExpandedTrendFigure,
  renderTrend,
} from "../trend/chart.js?v=korean-ui-v2";
import { bindTrendMetricSelector } from "../trend/metrics.js";
import { syncDashboardChatContext } from "../chat/controller.js?v=fft-current-history-v1";

let aiAnalysisRequest = 0;
let relatedHistoryRequest = 0;

function buildReportRequest() {
  const dashboardData = getDashboardData();
  const reference = getAiDiagnosisReference();
  const recordId = reference?.record?.recordId;
  if (!dashboardData?.meta?.datasetId || !Number.isInteger(recordId)) return null;
  return {
    datasetId: dashboardData.meta.datasetId,
    recordId,
    selectedFaultType: reference.selectedFaultType,
    fftRecord: reference.record,
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

function diagnosisBaseline() {
  const reference = getAiDiagnosisReference();
  return reference?.record ? {
    dashboard: getDashboardData(),
    fft: reference.record,
    selectedFaultType: reference.selectedFaultType,
  } : null;
}

function resetAiAnalysisForEquipment() {
  aiAnalysisRequest += 1;
  const baseline = diagnosisBaseline();
  resetAiAnalysis({ available: Boolean(getDashboardData()?.meta?.datasetId), baseline });
  resetReportActionsFor(baseline?.fft);
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
  const currentFft = getDashboardData()?.fft;
  const selectedFft = getSelectedFftRecord();
  if (selectedFft?.analysis?.diagnosis?.faults?.length && !getSelectedBearingFaultType()) {
    resetSelectedBearingFaultType(selectedFft);
  }
  const selectedBearingFaultType = getSelectedBearingFaultType();
  renderOverviewFftResult(currentFft);
  renderFftRecordList(currentFft, selectedFft?.recordId);
  renderFftChart(selectedFft, selectedBearingFaultType);
  renderTimeWaveChart(selectedFft);
  if (selectedFft) {
    renderFftMetadata(selectedFft);
    renderFftAnalysis(selectedFft, selectedBearingFaultType, {}, null);
    loadRelatedHistoryFor(selectedFft, selectedBearingFaultType);
    return;
  }

  renderFftMetadata(null);
  renderFftAnalysis(null, null, currentFft ? {
    heading: "선택한 주파수 기록이 없습니다.",
    detail: "좌측 목록에서 날짜별 주파수 기록을 선택해 주세요.",
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
    renderPlot("graph-modal-chart", buildFftFigure(getSelectedFftRecord(), getSelectedBearingFaultType()));
  } else if (getExpandedGraph() === "timewave" && dashboardData?.fft) {
    renderPlot("graph-modal-chart", buildTimeWaveFigure(getSelectedFftRecord()));
  }
}

function handleTrendMetricSelectionChange() {
  if (getExpandedGraph() === "trend") renderExpandedGraph();
}

function handleOpenExpandedGraph(graphType, trigger) {
  if (["fft", "timewave"].includes(graphType)) {
    renderFftHistoryList({ ...getDashboardData()?.fft, recordId: getSelectedFftRecord()?.recordId });
  }
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
  const baseline = diagnosisBaseline();
  if (!dashboardData?.meta?.datasetId) return;

  const requestId = ++aiAnalysisRequest;
  resetReportActionsFor(null);
  setAiAnalysisLoading(baseline);
  try {
    const payload = await fetchAiAnalysis(dashboardData.meta.datasetId, {
      until: requestedUntil(),
      force,
    });
    if (requestId !== aiAnalysisRequest) return;
    const representativeId = payload.analysis.fftReferenceRecordIds?.[0];
    let representative = null;
    if (representativeId) {
      representative = getCachedFftRecord(representativeId);
      if (!representative) {
        try {
          representative = await fetchFftRecord(dashboardData.meta.datasetId, representativeId, requestedUntil());
        } catch (error) {
          console.error("AI representative FFT loading failed", error);
        }
      }
    }
    if (requestId !== aiAnalysisRequest) return;
    if (representative) cacheFftRecord(representativeId, representative);
    setAiDiagnosisReference(representative, representative?.analysis?.diagnosis?.defaultFaultType ?? null);
    resetReportActionsFor(representative);
    renderAiAnalysis(payload, diagnosisBaseline());
  } catch (error) {
    if (requestId !== aiAnalysisRequest) return;
    renderAiAnalysisError(
      error.message || "인공지능 분석을 실행하지 못했습니다. 잠시 후 다시 시도해 주세요.",
      baseline,
    );
  }
}

async function selectFftRecord(recordId) {
  const dashboardData = getDashboardData();
  const fft = dashboardData?.fft;
  const recordExists = fft?.records?.some((record) => record.id === recordId);
  if (!fft || !recordExists || recordId === getSelectedFftRecord()?.recordId) return;

  const requestId = createFftSelectionRequest();
  resetRelatedHistoryExpansion();
  const list = document.getElementById("fft-record-list");
  list.setAttribute("aria-busy", "true");
  syncFftRecordSelection(fft, recordId, getSelectedFftRecord()?.recordId);
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

    setSelectedFftRecord(record);
    resetSelectedBearingFaultType(record);
    renderFft();
    syncDashboardChatContext();
    setFftHistoryStatus(`${fft.records.length.toLocaleString("ko-KR")}개 측정 기록`);
    if (getExpandedGraph() === "fft") {
      renderExpandedGraph();
    }
  } catch (error) {
    if (!isCurrentFftSelectionRequest(requestId)) return;
    console.error("FFT record loading failed", error);
    syncFftRecordSelection(fft, null, getSelectedFftRecord()?.recordId);
    setFftRecordStatus("선택한 주파수 기록을 불러오지 못했습니다.", true);
    setFftHistoryStatus("선택한 주파수 기록을 불러오지 못했습니다.", true);
  } finally {
    if (isCurrentFftSelectionRequest(requestId)) list.removeAttribute("aria-busy");
  }
}

export async function loadDashboard(datasetId) {
  const select = document.getElementById("dataset-select");
  setDashboardData(null);
  resetFftRecordState();
  resetRelatedHistoryExpansion();
  resetFftRecordFilters();
  resetAiAnalysisForEquipment();
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
      setSelectedFftRecord(selectedRecord);
    }
    resetCurrentPeriod();
    resetSelectedTrendMetrics(dashboardData);
    resetSelectedBearingFaultType(dashboardData.fft);
    setAiDiagnosisReference(getSelectedFftRecord(), getSelectedBearingFaultType());
    populateSummary(dashboardData);
    renderTrend(getCurrentPeriod(), dashboardData);
    renderFft();
    syncDashboardChatContext();
    renderLevelAnalysis(dashboardData);
    resetAiAnalysisForEquipment();
    void runAiAnalysis(false);
  } catch (error) {
    console.error("Dashboard data loading failed", error);
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
  bindGraphModal({
    onExpandGraph: handleOpenExpandedGraph,
    onFftRecordSelect: selectFftRecord,
  });
  bindTrendMetricSelector(handleTrendMetricSelectionChange);
  bindRelatedHistory();
  bindAiAnalysis((force) => runAiAnalysis(force));
  bindPptExport(buildReportRequest);
  bindEmailDraft(buildReportRequest);
  document.getElementById("fft-analysis-details").addEventListener("click", (event) => {
    const button = event.target.closest("[data-bearing-fault]");
    if (!button) return;
    setSelectedBearingFaultType(button.dataset.bearingFault);
    renderFft();
    syncDashboardChatContext();
    if (getExpandedGraph() === "fft") renderExpandedGraph();
  });
  document.getElementById("fft-record-browser").addEventListener("click", (event) => {
    const button = event.target.closest("[data-fft-filter-group]");
    if (!button) return;
    toggleFftRecordFilter(button.dataset.fftFilterGroup, button.dataset.fftFilterValue);
    renderFftRecordList(getDashboardData()?.fft, getSelectedFftRecord()?.recordId);
  });
  initializeDashboard();
}
