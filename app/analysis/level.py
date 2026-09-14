from __future__ import annotations

import calendar
import math
from datetime import datetime
from typing import Any

from .rules import LEVEL_ANALYSIS_MONTHS, RULESET_VERSION


def _subtract_months(value: datetime, months: int) -> datetime:
    year, zero_month = divmod(value.year * 12 + value.month - 1 - months, 12)
    return value.replace(year=year, month=zero_month + 1, day=min(value.day, calendar.monthrange(year, zero_month + 1)[1]))


def _linear_quantile(values: list[float], quantile: float) -> float:
    ordered = sorted(values); position = (len(ordered) - 1) * quantile
    lower, upper = math.floor(position), math.ceil(position)
    return ordered[lower] if lower == upper else ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def analyze_velave_level(points: list[dict[str, Any]], configured: dict[str, Any] | None = None) -> dict[str, Any]:
    analysis: dict[str, Any] = {"status": "unavailable", "windowStart": None, "windowEnd": None, "usedPoints": 0, "normalPoints": 0, "outlierPoints": 0, "lowerBound": None, "upperBound": None, "normalMean": None, "recommended": {"warningThreshold": None, "dangerThreshold": None}, "configured": configured, "difference": None, "ruleId": "level.velave.iqr", "rulesetVersion": RULESET_VERSION}
    if not points: return analysis
    dated = [(datetime.fromisoformat(str(point["timestamp"])), float(point["value"])) for point in points if math.isfinite(float(point["value"]))]
    if not dated: return analysis
    latest = max(timestamp for timestamp, _ in dated); start = _subtract_months(latest, LEVEL_ANALYSIS_MONTHS)
    values = [value for timestamp, value in dated if start <= timestamp <= latest]
    if not values: return analysis
    q1, q3 = _linear_quantile(values, .25), _linear_quantile(values, .75); iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr; normal = [value for value in values if lower <= value <= upper]
    mean = sum(normal) / len(normal); recommended = {"warningThreshold": mean * 2, "dangerThreshold": mean * 4}
    difference = None if configured is None else {key: configured[key] - recommended[key] for key in recommended}
    analysis.update({"status": "compared" if configured is not None else "recommendation_only", "windowStart": start.isoformat(sep=" "), "windowEnd": latest.isoformat(sep=" "), "usedPoints": len(values), "normalPoints": len(normal), "outlierPoints": len(values)-len(normal), "lowerBound": lower, "upperBound": upper, "normalMean": mean, "recommended": recommended, "difference": difference})
    return analysis
