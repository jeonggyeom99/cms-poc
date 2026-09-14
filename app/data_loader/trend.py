from __future__ import annotations

import math
from typing import Any

from .constants import (
    TREND_MOVING_AVERAGE_POINTS,
    TREND_REGRESSION_POINTS,
    TREND_REQUIRED_POINTS,
    TREND_RISING_THRESHOLD,
)
from app.analysis.trend import analyze_velocity_trend


def _fill_low_outliers(values: list[float]) -> list[float]:
    """Linearly interpolate values below mean - 3σ, including edge runs."""
    mean = sum(values) / len(values)
    standard_deviation = math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))
    low_outlier_limit = mean - 3 * standard_deviation
    corrected: list[float | None] = values.copy()

    for index, value in enumerate(values):
        if value < low_outlier_limit:
            corrected[index] = None

    index = 0
    while index < len(corrected):
        if corrected[index] is not None:
            index += 1
            continue
        start = index
        while index < len(corrected) and corrected[index] is None:
            index += 1
        end = index
        left = corrected[start - 1] if start else None
        right = corrected[end] if end < len(corrected) else None
        if left is None:
            corrected[start:end] = [right] * (end - start)
        elif right is None:
            corrected[start:end] = [left] * (end - start)
        else:
            span = end - start + 1
            corrected[start:end] = [left + (right - left) * offset / span for offset in range(1, span)]

    return [float(value) for value in corrected]


def analyze_velave_trend(points: list[dict[str, Any]]) -> dict[str, Any]:
    """Determine whether VelAve has a sustained upward slope in hourly Trend data."""
    point_count = len(points)
    analysis: dict[str, Any] = {
        "status": "insufficient_data",
        "isRising": None,
        "detectedAt": None,
        "threshold": TREND_RISING_THRESHOLD,
        "thresholdUnit": "mm/s/hour",
        "slope": None,
        "usedPoints": point_count,
        "requiredPoints": TREND_REQUIRED_POINTS,
    }
    if point_count < TREND_REQUIRED_POINTS:
        return analysis

    values = _fill_low_outliers([float(point["value"]) for point in points])
    moving_averages = [
        sum(values[index : index + TREND_MOVING_AVERAGE_POINTS]) / TREND_MOVING_AVERAGE_POINTS
        for index in range(point_count - TREND_MOVING_AVERAGE_POINTS + 1)
    ]
    regression_values = moving_averages[-TREND_REGRESSION_POINTS:]
    mean_x = (TREND_REGRESSION_POINTS - 1) / 2
    mean_y = sum(regression_values) / TREND_REGRESSION_POINTS
    numerator = sum((index - mean_x) * (value - mean_y) for index, value in enumerate(regression_values))
    denominator = sum((index - mean_x) ** 2 for index in range(TREND_REGRESSION_POINTS))
    slope = numerator / denominator
    is_rising = slope > TREND_RISING_THRESHOLD
    analysis.update(
        {
            "status": "rising" if is_rising else "stable",
            "isRising": is_rising,
            "detectedAt": points[-TREND_REGRESSION_POINTS]["timestamp"] if is_rising else None,
            "slope": slope,
        }
    )
    return analysis


# Historical import path retained for integrations.
analyze_velave_trend = analyze_velocity_trend
