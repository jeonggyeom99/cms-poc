"""The single structured analysis path used by UI APIs and chat tools."""
from datetime import date, datetime, time
from typing import Any

from app.analysis.trend import summarize_trend_metrics
from app.data_loader import dataset_between, load_fft_record


def select_fft_analysis_record(fft: dict[str, Any], record_id: int) -> dict[str, Any]:
    return load_fft_record(fft, record_id)


def range_snapshot(dataset: dict[str, Any], start: date | None, end: date | None) -> dict[str, Any] | None:
    """Return the one inclusive date-range snapshot for every consumer."""
    return dataset_between(
        dataset,
        datetime.combine(start, time.min) if start else None,
        datetime.combine(end, time.max) if end else None,
    )


def trend_tool(dataset: dict[str, Any], start: date | None, end: date | None) -> dict[str, Any]:
    scoped = range_snapshot(dataset, start, end)
    if scoped is None or scoped.get("trend") is None:
        return {"status": "unavailable", "reason": "no_trend_data_in_range", "start": str(start) if start else None, "end": str(end) if end else None}
    return {
        "status": "ready", "start": str(start) if start else None, "end": str(end) if end else None,
        "trend": trend_analysis_result(scoped), "level": scoped["levelAnalysis"],
    }


def trend_analysis_result(dataset: dict[str, Any]) -> dict[str, Any]:
    """Reusable non-diagnostic Trend facts for UI, tools, and templates."""
    trend = dataset["trend"]
    return {
        "points": trend["points"], "metrics": trend["metrics"], "analysis": trend["analysis"],
        "summary": summarize_trend_metrics(trend["points"], trend["metrics"]),
    }


def fft_tool(dataset: dict[str, Any], record_id: int | None, start: date | None, end: date | None, *, fallback_to_default: bool = False) -> dict[str, Any]:
    scoped = range_snapshot(dataset, start, end)
    if scoped is None or scoped.get("fft") is None:
        return {"status": "unavailable", "reason": "no_fft_data_in_range", "start": str(start) if start else None, "end": str(end) if end else None}
    fft = scoped["fft"]
    chosen = record_id if record_id is not None else fft.get("recordId")
    try:
        record = select_fft_analysis_record(fft, chosen)
    except KeyError:
        if fallback_to_default:
            chosen = fft.get("recordId")
            record = select_fft_analysis_record(fft, chosen)
        else:
            return {"status": "unavailable", "reason": "fft_record_not_found", "recordId": chosen, "start": str(start) if start else None, "end": str(end) if end else None}
    return {"status": "ready", "start": str(start) if start else None, "end": str(end) if end else None, "record": record}


def bearing_fft_tool(dataset: dict[str, Any], record_id: int | None, start: date | None, end: date | None, *, fallback_to_default: bool = False) -> dict[str, Any]:
    result = fft_tool(dataset, record_id, start, end, fallback_to_default=fallback_to_default)
    if result["status"] != "ready":
        return result
    record = result["record"]
    return {**result, "bearingAnalysis": record.get("analysis", {}).get("diagnosis", {})}
