let dashboardData;
let currentPeriod = "90";
let expandedGraph = null;
let expandedGraphTrigger = null;
let selectedTrendMetrics = new Set(["velocity"]);
let fftRecordCache = new Map();
let fftSelectionRequest = 0;
let selectedBearingFaultType = null;

export function getDashboardData() {
  return dashboardData;
}

export function setDashboardData(data) {
  dashboardData = data;
}

export function getCurrentPeriod() {
  return currentPeriod;
}

export function setCurrentPeriod(period) {
  currentPeriod = period;
}

export function resetCurrentPeriod() {
  currentPeriod = "90";
  return currentPeriod;
}

export function getExpandedGraph() {
  return expandedGraph;
}

export function setExpandedGraph(graphType, trigger) {
  expandedGraph = graphType;
  expandedGraphTrigger = trigger;
}

export function clearExpandedGraph() {
  const trigger = expandedGraphTrigger;
  expandedGraph = null;
  expandedGraphTrigger = null;
  return trigger;
}

export function getSelectedTrendMetrics() {
  return selectedTrendMetrics;
}

export function setSelectedTrendMetrics(metrics) {
  selectedTrendMetrics = new Set(metrics);
}

export function resetSelectedTrendMetrics(data = dashboardData) {
  const availableMetrics = data?.trend?.metrics?.filter((metric) => metric.available) ?? [];
  const defaultMetric = availableMetrics.find((metric) => metric.key === "velocity") ?? availableMetrics[0];
  selectedTrendMetrics = new Set(defaultMetric ? [defaultMetric.key] : []);
  return selectedTrendMetrics;
}

export function resetFftRecordState() {
  fftSelectionRequest += 1;
  fftRecordCache = new Map();
  selectedBearingFaultType = null;
}

export function getSelectedBearingFaultType() {
  return selectedBearingFaultType;
}

export function setSelectedBearingFaultType(faultType) {
  selectedBearingFaultType = faultType;
}

export function resetSelectedBearingFaultType(fft) {
  selectedBearingFaultType = fft?.analysis?.diagnosis?.defaultFaultType ?? null;
  return selectedBearingFaultType;
}

export function createFftSelectionRequest() {
  fftSelectionRequest += 1;
  return fftSelectionRequest;
}

export function isCurrentFftSelectionRequest(requestId) {
  return requestId === fftSelectionRequest;
}

export function getCachedFftRecord(recordId) {
  return fftRecordCache.get(recordId);
}

export function cacheFftRecord(recordId, record) {
  fftRecordCache.set(recordId, record);
}
