from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

from .rules import RULESET_VERSION, TREND_MOVING_AVERAGE_POINTS, TREND_REGRESSION_POINTS, TREND_REQUIRED_POINTS, TREND_RISING_THRESHOLD


def _fill_low_outliers(values: list[float]) -> list[float]:
    mean = sum(values) / len(values)
    deviation = math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))
    corrected: list[float | None] = values.copy()
    for index, value in enumerate(values):
        if value < mean - 3 * deviation:
            corrected[index] = None
    index = 0
    while index < len(corrected):
        if corrected[index] is not None:
            index += 1
            continue
        start = index
        while index < len(corrected) and corrected[index] is None:
            index += 1
        end, left = index, corrected[start - 1] if start else None
        right = corrected[end] if end < len(corrected) else None
        if left is None:
            corrected[start:end] = [right] * (end - start)
        elif right is None:
            corrected[start:end] = [left] * (end - start)
        else:
            span = end - start + 1
            corrected[start:end] = [left + (right - left) * offset / span for offset in range(1, span)]
    return [float(value) for value in corrected]


def analyze_velocity_trend(points: list[dict[str, Any]]) -> dict[str, Any]:
    """Preserve the hourly-sample-index VelAve rising rule."""
    analysis: dict[str, Any] = {"status": "insufficient_data", "isRising": None, "detectedAt": None, "threshold": TREND_RISING_THRESHOLD, "thresholdUnit": "mm/s/hour", "slope": None, "usedPoints": len(points), "requiredPoints": TREND_REQUIRED_POINTS, "ruleId": "trend.velave.rising", "rulesetVersion": RULESET_VERSION}
    if len(points) < TREND_REQUIRED_POINTS:
        return analysis
    values = _fill_low_outliers([float(point["value"]) for point in points])
    averages = [sum(values[index:index + TREND_MOVING_AVERAGE_POINTS]) / TREND_MOVING_AVERAGE_POINTS for index in range(len(points) - TREND_MOVING_AVERAGE_POINTS + 1)]
    regression_values = averages[-TREND_REGRESSION_POINTS:]
    mean_x, mean_y = (TREND_REGRESSION_POINTS - 1) / 2, sum(regression_values) / TREND_REGRESSION_POINTS
    numerator = sum((index - mean_x) * (value - mean_y) for index, value in enumerate(regression_values))
    denominator = sum((index - mean_x) ** 2 for index in range(TREND_REGRESSION_POINTS))
    slope = numerator / denominator
    rising = slope > TREND_RISING_THRESHOLD
    analysis.update({"status": "rising" if rising else "stable", "isRising": rising, "detectedAt": points[-TREND_REGRESSION_POINTS]["timestamp"] if rising else None, "slope": slope})
    return analysis


def summarize_trend_metrics(points: list[dict[str, Any]], metrics: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Reusable compact Trend features for AI/agents; no diagnosis is recalculated."""
    result: dict[str, Any] = {}
    metric_defs = metrics or [{"key": "velocity", "pointKey": "value"}]
    for metric in metric_defs:
        key, point_key = metric.get("key"), metric.get("pointKey", metric.get("key"))
        values = [(point.get("timestamp"), point.get(point_key)) for point in points if isinstance(point, dict)]
        valid = [(timestamp, float(value)) for timestamp, value in values if isinstance(value, (int, float)) and math.isfinite(value)]
        if not key or not valid:
            continue
        numbers = [value for _, value in valid]
        latest_timestamp, latest = valid[-1]
        def change(days: int) -> float | None:
            try:
                cutoff = datetime.fromisoformat(str(latest_timestamp)) - timedelta(days=days)
                prior = [(timestamp, value) for timestamp, value in valid if datetime.fromisoformat(str(timestamp)) <= cutoff]
            except ValueError:
                return None
            return latest - prior[-1][1] if prior else None
        result[str(key)] = {"latestValue": latest, "mean": sum(numbers) / len(numbers), "min": min(numbers), "max": max(numbers), "change30Days": change(30), "change90Days": change(90), "latestAt": latest_timestamp}
    return result
