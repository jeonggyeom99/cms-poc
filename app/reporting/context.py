"""Evidence-only context construction for report-specific AI prompts."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.ai_analysis import build_ai_context


REPORT_CONTEXT_VERSION = "cms-report-context-v1"


def build_report_context(
    report_kind: str,
    dataset_id: str,
    dataset: dict[str, Any],
    fft: dict[str, Any],
    history_items: list[dict[str, Any]],
    selected_fault_type: str | None = None,
    until: date | None = None,
) -> dict[str, Any]:
    """Wrap the existing compact diagnosis evidence with report intent metadata."""
    evidence = build_ai_context(
        dataset_id,
        dataset,
        fft,
        history_items,
        selected_fault_type,
        until,
    )
    source_equipment = dataset.get("equipment")
    sensor_number = (
        source_equipment.get("sensorNumber")
        if isinstance(source_equipment, dict)
        else None
    )
    if isinstance(sensor_number, (str, int, float)) and not isinstance(sensor_number, bool):
        evidence["equipment"]["sensorNumber"] = str(sensor_number)[:32]
    return {
        "reportKind": report_kind,
        "contextVersion": REPORT_CONTEXT_VERSION,
        "evidence": evidence,
    }