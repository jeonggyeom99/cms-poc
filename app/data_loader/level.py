from __future__ import annotations

import calendar
import math
from datetime import datetime
from typing import Any

from .constants import LEVEL_ANALYSIS_MONTHS


def _subtract_months(value: datetime, months: int) -> datetime:
    month_index = value.year * 12 + value.month - 1 - months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _linear_quantile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return ordered[lower_index]
    fraction = position - lower_index
    return ordered[lower_index] + (ordered[upper_index] - ordered[lower_index]) * fraction


def analyze_velave_level(
    points: list[dict[str, Any]], configured: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Calculate recommended VelAve alarm levels from the latest three calendar months."""
    analysis: dict[str, Any] = {
        "status": "unavailable",
        "windowStart": None,
        "windowEnd": None,
        "usedPoints": 0,
        "normalPoints": 0,
        "outlierPoints": 0,
        "lowerBound": None,
        "upperBound": None,
        "normalMean": None,
        "recommended": {
            "warningThreshold": None,
            "dangerThreshold": None,
        },
        "configured": configured,
        "difference": None,
    }
    if not points:
        return analysis

    dated_values = [
        (datetime.fromisoformat(str(point["timestamp"])), float(point["value"]))
        for point in points
        if math.isfinite(float(point["value"]))
    ]
    if not dated_values:
        return analysis

    latest_date = max(timestamp for timestamp, _ in dated_values)
    start_date = _subtract_months(latest_date, LEVEL_ANALYSIS_MONTHS)
    recent_values = [
        value for timestamp, value in dated_values if start_date <= timestamp <= latest_date
    ]
    if not recent_values:
        return analysis

    first_quartile = _linear_quantile(recent_values, 0.25)
    third_quartile = _linear_quantile(recent_values, 0.75)
    interquartile_range = third_quartile - first_quartile
    lower_bound = first_quartile - 1.5 * interquartile_range
    upper_bound = third_quartile + 1.5 * interquartile_range
    normal_values = [value for value in recent_values if lower_bound <= value <= upper_bound]
    normal_mean = sum(normal_values) / len(normal_values)
    recommended = {
        "warningThreshold": normal_mean * 2,
        "dangerThreshold": normal_mean * 4,
    }

    difference = None
    if configured is not None:
        difference = {
            "warningThreshold": configured["warningThreshold"] - recommended["warningThreshold"],
            "dangerThreshold": configured["dangerThreshold"] - recommended["dangerThreshold"],
        }

    analysis.update(
        {
            "status": "compared" if configured is not None else "recommendation_only",
            "windowStart": start_date.isoformat(sep=" "),
            "windowEnd": latest_date.isoformat(sep=" "),
            "usedPoints": len(recent_values),
            "normalPoints": len(normal_values),
            "outlierPoints": len(recent_values) - len(normal_values),
            "lowerBound": lower_bound,
            "upperBound": upper_bound,
            "normalMean": normal_mean,
            "recommended": recommended,
            "difference": difference,
        }
    )
    return analysis
