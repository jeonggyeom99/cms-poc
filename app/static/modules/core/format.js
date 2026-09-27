import { trendMetricStyles } from "./constants.js";

export function formatNumber(value, digits = 2) {
  return Number.isFinite(Number(value)) && value !== null ? Number(value).toFixed(digits) : "--";
}

export function formatMetricReading(metric, value) {
  if (value === null || !Number.isFinite(Number(value))) return "--";
  const digits = trendMetricStyles[metric.key]?.digits ?? 2;
  return `${formatNumber(value, digits)} ${metric.unit}`;
}

export function formatCodedValue(value) {
  if (!value) return "--";
  return `${value.label || "알 수 없음"} (${value.code || "--"})`;
}

export function formatCodedLabel(value) {
  if (!value) return "--";
  return ({
    "가속도ALL": "전체 가속도",
    "가속도ENV": "가속도",
  })[value.label] || value.label || "알 수 없음";
}

export function formatRatio(value) {
  return Number.isFinite(Number(value)) ? formatNumber(value, 2) : "--";
}

export function levelDifferenceLabel(value) {
  if (value === null || !Number.isFinite(Number(value))) return "현재 설정값 없음";
  if (Math.abs(Number(value)) < 0.005) return "권고값과 동일";
  const direction = Number(value) > 0 ? "높음" : "낮음";
  return `권고보다 ${formatNumber(Math.abs(Number(value)))} mm/s ${direction}`;
}

export function availabilityLabel(availability) {
  const available = [];
  if (availability.trend) available.push("추세");
  if (availability.fft) available.push("주파수");
  return available.length ? available.join(" + ") : "사용 가능 데이터 없음";
}
