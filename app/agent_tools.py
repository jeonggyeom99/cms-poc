"""Bounded server-side analysis tools exposed to model function calling."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.ai_analysis import build_ai_context
from app.chat import _tool_evidence
from app.services.analysis import bearing_fft_tool, fft_tool, trend_tool


_ARGUMENT_PROPERTIES = {
    "equipment_code": {"type": ["string", "null"], "description": "Known equipment code such as V032, or null for the selected equipment."},
    "record_id": {"type": ["integer", "null"], "description": "FFT record ID, or null to select the record from the requested date range."},
    "start": {"type": ["string", "null"], "description": "Inclusive ISO date range start, or null."},
    "end": {"type": ["string", "null"], "description": "Inclusive ISO date range end, or null."},
    "selected_fault_type": {"type": ["string", "null"], "description": "Selected bearing fault type when known, otherwise null."},
}


def dashboard_tool_definitions() -> list[dict[str, Any]]:
    descriptions = {
        "get_trend": "Get deterministic Trend metrics, trend direction, and Level thresholds for one known CMS equipment and optional date range.",
        "get_fft": "Get compact deterministic spectrum and velocity FFT diagnosis for a selected or date-selected FFT record.",
        "get_bearing_fft": "Get compact deterministic acceleration bearing fault harmonics and diagnostic limitations for an FFT record.",
        "get_related_history": "Get strictly pre-measurement same-equipment history matching the selected FFT fault.",
    }
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": _ARGUMENT_PROPERTIES,
                    "required": list(_ARGUMENT_PROPERTIES),
                    "additionalProperties": False,
                },
            },
        }
        for name, description in descriptions.items()
    ]


def _as_date(value: Any) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("날짜는 ISO 형식 문자열이어야 합니다.")
    return date.fromisoformat(value)


def _compact_trend(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("status") != "ready":
        return result
    from app.analysis.trend import summarize_trend_metrics

    trend = result["trend"]
    points = trend.get("points", [])
    return {
        "status": "ready",
        "start": result.get("start"),
        "end": result.get("end"),
        "trend": {
            "pointCount": len(points),
            "firstTimestamp": points[0].get("timestamp") if points else None,
            "lastTimestamp": points[-1].get("timestamp") if points else None,
            "metrics": trend.get("metrics", []),
            "analysis": trend.get("analysis", {}),
            "summary": summarize_trend_metrics(points, trend.get("metrics", [])),
        },
        "level": result.get("level"),
    }


def build_dashboard_tool_executor(
    datasets: dict[str, dict[str, Any]],
    selected_dataset_id: str,
    default_record_id: int,
    history_items: list[dict[str, Any]],
    selected_fault_type: str | None,
    default_until: date | None,
):
    """Bind tool calls to loaded datasets and validate all model-supplied scope."""

    async def execute(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        allowed = {"equipment_code", "record_id", "start", "end", "selected_fault_type"}
        if set(arguments) != allowed:
            return {"status": "unavailable", "reason": "invalid_tool_arguments"}
        code = arguments["equipment_code"]
        if code is None:
            dataset_id = selected_dataset_id
        elif isinstance(code, str):
            selected_code = datasets[selected_dataset_id].get("equipment", {}).get("id", "").upper()
            match = selected_dataset_id if selected_code == code.upper() else next(
                (key for key, dataset in datasets.items() if dataset.get("equipment", {}).get("id", "").upper() == code.upper()),
                None,
            )
            if match is None:
                return {"status": "unavailable", "reason": "dataset_not_found", "equipmentCode": code}
            dataset_id = match
        else:
            return {"status": "unavailable", "reason": "invalid_tool_arguments"}

        record_id = arguments["record_id"]
        if record_id is not None and (isinstance(record_id, bool) or not isinstance(record_id, int) or record_id <= 0):
            return {"status": "unavailable", "reason": "invalid_tool_arguments"}
        try:
            start = _as_date(arguments["start"])
            end = _as_date(arguments["end"])
        except (TypeError, ValueError):
            return {"status": "unavailable", "reason": "invalid_tool_arguments"}
        if start and end and start > end:
            return {"status": "unavailable", "reason": "invalid_tool_arguments"}
        if start is None and end is None:
            end = default_until
        fault_type = arguments["selected_fault_type"] or selected_fault_type
        dataset = datasets[dataset_id]

        if name == "get_trend":
            return _compact_trend(trend_tool(dataset, start, end))
        if name not in {"get_fft", "get_bearing_fft", "get_related_history"}:
            return {"status": "unavailable", "reason": "unknown_tool"}

        chosen_record = record_id
        if chosen_record is None and dataset_id == selected_dataset_id and start is None and end == default_until:
            chosen_record = default_record_id
        result = (bearing_fft_tool if name == "get_bearing_fft" else fft_tool)(
            dataset, chosen_record, start, end
        )
        if result.get("status") != "ready":
            return result

        record = result["record"]
        measure_mode = ((record.get("metadata") or {}).get("measureMode") or {}).get("code")
        if name == "get_bearing_fft" and measure_mode not in {"0", "2"}:
            return {
                "status": "unavailable",
                "reason": "bearing_analysis_requires_acceleration_fft",
                "recordId": record.get("recordId"),
                "measureMode": measure_mode,
            }

        context = build_ai_context(
            dataset_id, dataset, record, history_items, fault_type, end
        )
        if name == "get_related_history":
            return {"status": "ready", "recordId": record.get("recordId"), "relatedHistory": context["relatedHistory"]}

        compact = context["fft"]
        return {
            "status": "ready",
            "start": result.get("start"),
            "end": result.get("end"),
            "recordId": record.get("recordId"),
            "measuredAt": record.get("measuredAt"),
            "fft": compact,
        }

    return execute


def public_tool_trace(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": item["name"],
            "arguments": item["arguments"],
            "result": _tool_evidence(item["result"]),
        }
        for item in trace
    ]
