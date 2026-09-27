from __future__ import annotations

import csv
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from .constants import DATASET_NUMBER_PATTERN, TREND_METRIC_DEFINITIONS
from .fft import _build_fft_record, _fft_record_summary
from .metadata import _equipment_metadata
from .numeric import _optional_finite_float
from .trend import analyze_velave_trend


def _classify_csv(path: Path) -> tuple[str, str] | None:
    name = path.name
    dataset_match = DATASET_NUMBER_PATTERN.match(name)
    if dataset_match is None:
        return None

    lowered_name = name.lower()
    if "warningstatus" in lowered_name:
        kind = "warningStatus"
    elif "fft" in lowered_name:
        kind = "fft"
    elif "trend" in lowered_name:
        kind = "trend"
    else:
        return None

    return dataset_match.group(1), kind


def _load_trend(path: Path) -> dict[str, Any]:
    points: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig", newline="") as trend_file:
        reader = csv.DictReader(trend_file)
        required_columns = {"DataDate", "VelAve", "AccAllAve"}
        if not required_columns.issubset(reader.fieldnames or []):
            missing = ", ".join(sorted(required_columns - set(reader.fieldnames or [])))
            raise ValueError(f"Trend CSV 필수 컬럼 누락: {missing}")

        for row in reader:
            points.append(
                {
                    "timestamp": row["DataDate"],
                    "value": float(row["VelAve"]),
                    "acceleration": float(row["AccAllAve"]),
                    "accelerationBpf": _optional_finite_float(row.get("AccBpfAve")),
                    "accelerationPeak": _optional_finite_float(row.get("AccPeakAve")),
                }
            )

    if not points:
        raise ValueError("Trend CSV에 데이터 행이 없습니다.")

    points.sort(key=lambda point: point["timestamp"])
    return {
        "unit": "mm/s",
        "points": points,
        "analysis": analyze_velave_trend(points),
    }


def _load_warning_status(path: Path) -> dict[str, Any]:
    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8-sig", newline="") as status_file:
        reader = csv.DictReader(status_file)
        required_columns = {"GenerationTime", "VELJudgeWarnValue", "VELJudgeDangValue"}
        if not required_columns.issubset(reader.fieldnames or []):
            missing = ", ".join(sorted(required_columns - set(reader.fieldnames or [])))
            raise ValueError(f"WarningStatus CSV 필수 컬럼 누락: {missing}")

        for row in reader:
            datetime.fromisoformat(str(row["GenerationTime"]))
            rows.append(row)

    return _warning_status_from_rows(rows)


def _warning_status_from_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    latest_row = max(rows, key=lambda row: datetime.fromisoformat(str(row["GenerationTime"])), default=None)

    if latest_row is None:
        raise ValueError("WarningStatus CSV에 데이터 행이 없습니다.")

    warning_threshold = float(str(latest_row["VELJudgeWarnValue"]))
    danger_threshold = float(str(latest_row["VELJudgeDangValue"]))
    if not math.isfinite(warning_threshold) or not math.isfinite(danger_threshold):
        raise ValueError("WarningStatus CSV의 속도 Level이 유효한 숫자가 아닙니다.")

    thresholds = {
        metric["key"]: {
            "warningThreshold": _optional_finite_float(
                latest_row.get(f'{metric["thresholdPrefix"]}JudgeWarnValue')
            ),
            "dangerThreshold": _optional_finite_float(
                latest_row.get(f'{metric["thresholdPrefix"]}JudgeDangValue')
            ),
        }
        for metric in TREND_METRIC_DEFINITIONS
    }
    thresholds["velocity"] = {
        "warningThreshold": warning_threshold,
        "dangerThreshold": danger_threshold,
    }

    return {
        "measuredAt": latest_row["GenerationTime"],
        "warningThreshold": warning_threshold,
        "dangerThreshold": danger_threshold,
        "thresholds": thresholds,
        "_rows": rows,
    }


def filter_warning_status_until(
    warning_status: dict[str, Any] | None, until: datetime
) -> dict[str, Any] | None:
    if warning_status is None:
        return None
    rows = [row for row in warning_status.get("_rows", []) if datetime.fromisoformat(str(row["GenerationTime"])) <= until]
    return _warning_status_from_rows(rows) if rows else None


def _load_fft(
    path: Path, rpm: float | None = None, bearing: dict[str, Any] | None = None
) -> dict[str, Any]:
    rows: list[tuple[int, dict[str, str]]] = []
    with path.open(encoding="utf-8-sig", newline="") as fft_file:
        reader = csv.DictReader(fft_file)
        fieldnames = set(reader.fieldnames or [])
        required_columns = {
            "MeasureDate",
            "ExtractionType",
            "MeasureMode",
            "MeasureFreq",
            "MeasureLineNum",
            "ResultData",
        }
        if not required_columns.issubset(reader.fieldnames or []):
            missing = ", ".join(sorted(required_columns - fieldnames))
            raise ValueError(f"FFT CSV 필수 컬럼 누락: {missing}")
        if not {"DiagMode", "DaiagMode"} & fieldnames:
            raise ValueError("FFT CSV 필수 컬럼 누락: DiagMode (또는 DaiagMode)")

        rows = [(row_number, row) for row_number, row in enumerate(reader, start=2)]

    if not rows:
        raise ValueError("FFT CSV에 데이터 행이 없습니다.")

    rows.sort(key=lambda item: (item[1]["MeasureDate"], item[0]), reverse=True)
    record_summaries = [
        _fft_record_summary(row, record_id, rpm, bearing) for record_id, row in rows
    ]
    alert_record_ids = {
        record["id"] for record in record_summaries if record["isAlertFft"]
    }
    default_record = _default_fft_record(rows)
    fft = _build_fft_record(default_record[1], default_record[0], rpm, bearing)
    fft["records"] = record_summaries
    fft["alertRecordCount"] = len(alert_record_ids)
    fft["_recordsById"] = {record_id: row for record_id, row in rows}
    fft["_rpm"] = rpm
    fft["_bearing"] = bearing
    return fft


def load_fft_record(fft: dict[str, Any], record_id: int) -> dict[str, Any]:
    row = fft.get("_recordsById", {}).get(record_id)
    if row is None:
        raise KeyError(record_id)
    return _build_fft_record(row, record_id, fft.get("_rpm"), fft.get("_bearing"))


def _default_fft_record(rows: list[tuple[int, dict[str, str]]]) -> tuple[int, dict[str, str]]:
    """Select the most recent record that supports frequency diagnosis.

    Rows are already sorted newest first.  Alert status intentionally does not
    influence this choice: the dashboard's current FFT state must describe the
    most recent analysable measurement, not a past alert.
    """
    return next((item for item in rows if item[1]["MeasureMode"] in {"2", "3"}), rows[0])


def filter_fft_until(fft: dict[str, Any] | None, until: datetime) -> dict[str, Any] | None:
    if fft is None:
        return None
    rows = [
        (record_id, row) for record_id, row in fft.get("_recordsById", {}).items()
        if datetime.fromisoformat(str(row["MeasureDate"])) <= until
    ]
    if not rows:
        return None
    rows.sort(key=lambda item: (item[1]["MeasureDate"], item[0]), reverse=True)
    rpm, bearing = fft.get("_rpm"), fft.get("_bearing")
    summaries = [_fft_record_summary(row, record_id, rpm, bearing) for record_id, row in rows]
    alerts = {record["id"] for record in summaries if record["isAlertFft"]}
    default = _default_fft_record(rows)
    result = _build_fft_record(default[1], default[0], rpm, bearing)
    result.update({"records": summaries, "alertRecordCount": len(alerts), "_recordsById": dict(rows), "_rpm": rpm, "_bearing": bearing})
    return result
