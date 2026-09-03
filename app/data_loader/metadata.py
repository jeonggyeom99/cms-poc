from __future__ import annotations

from pathlib import Path
from typing import Any

from .constants import (
    DATA_KIND_PATTERN,
    DATASET_NUMBER_PATTERN,
    DIAG_MODE_LABELS,
    EQUIPMENT_CODE_PATTERN,
    EXTRACTION_TYPE_LABELS,
    FREQUENCY_RANGES_HZ,
    INLINE_CODE_PATTERN,
    MEASURE_FREQ_LABELS,
    MEASURE_MODE_DEFINITIONS,
    TRAILING_CODE_PATTERN,
    TREND_METRIC_DEFINITIONS,
)


def _equipment_metadata(dataset_id: str, source_path: Path) -> dict[str, str]:
    source_name = DATASET_NUMBER_PATTERN.sub("", source_path.stem, count=1).strip()
    source_name = DATA_KIND_PATTERN.sub("", source_name, count=1).strip()

    code_match = EQUIPMENT_CODE_PATTERN.search(source_name)
    equipment_code = code_match.group(1).upper() if code_match else f"DATA-{dataset_id}"

    display_source = TRAILING_CODE_PATTERN.sub("", source_name).strip()
    parts = [INLINE_CODE_PATTERN.sub("", part.strip()) for part in display_source.split("_") if part.strip()]

    if len(parts) >= 3:
        plant = parts[0]
        equipment_name = parts[1]
        measurement_point = " / ".join(parts[2:])
    elif len(parts) == 2:
        plant = "CMS 설비"
        equipment_name, measurement_point = parts
    elif parts:
        plant = "CMS 설비"
        equipment_name = parts[0]
        measurement_point = "측정 위치 미제공"
    else:
        plant = "CMS 설비"
        equipment_name = f"Dataset #{dataset_id}"
        measurement_point = "측정 위치 미제공"

    return {
        "id": equipment_code,
        "name": equipment_name,
        "measurementPoint": measurement_point,
        "plant": plant,
        "line": f"CSV Dataset #{dataset_id}",
        "displayName": " / ".join(parts) if parts else equipment_name,
    }


def _coded_value(code: str, labels: dict[str, str]) -> dict[str, str]:
    return {"code": code, "label": labels.get(code, "알 수 없음")}


def _fft_metadata(row: dict[str, str]) -> dict[str, Any]:
    frequency_code = row["MeasureFreq"]
    measure_mode = row["MeasureMode"]
    diag_mode = row.get("DiagMode") or row.get("DaiagMode") or ""
    frequency = _coded_value(frequency_code, MEASURE_FREQ_LABELS)
    frequency["frequencyRange"] = FREQUENCY_RANGES_HZ.get(frequency_code)
    return {
        "measureDate": row["MeasureDate"],
        "extractionType": _coded_value(row["ExtractionType"], EXTRACTION_TYPE_LABELS),
        "diagMode": _coded_value(diag_mode, DIAG_MODE_LABELS),
        "measureMode": _coded_value(
            measure_mode,
            {code: definition["label"] for code, definition in MEASURE_MODE_DEFINITIONS.items()},
        ),
        "measureFreq": frequency,
    }


def _build_trend_metrics(
    trend: dict[str, Any], warning_status: dict[str, Any] | None
) -> list[dict[str, Any]]:
    thresholds = warning_status.get("thresholds", {}) if warning_status is not None else {}
    metrics = []
    for definition in TREND_METRIC_DEFINITIONS:
        point_key = definition["pointKey"]
        latest_value = next(
            (
                point[point_key]
                for point in reversed(trend["points"])
                if point.get(point_key) is not None
            ),
            None,
        )
        metric_thresholds = thresholds.get(definition["key"], {})
        metrics.append(
            {
                "key": definition["key"],
                "pointKey": point_key,
                "label": definition["label"],
                "unit": definition["unit"],
                "latestValue": latest_value,
                "warningThreshold": metric_thresholds.get("warningThreshold"),
                "dangerThreshold": metric_thresholds.get("dangerThreshold"),
                "available": latest_value is not None,
            }
        )
    return metrics
