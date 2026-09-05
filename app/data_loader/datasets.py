from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

from .constants import EQUIPMENT_METADATA_CONFIG_PATH
from .csv_loader import _classify_csv, _load_fft, _load_trend, _load_warning_status
from .level import analyze_velave_level
from .metadata import _build_trend_metrics, _equipment_metadata
from .numeric import _optional_finite_float


LOGGER = logging.getLogger(__name__)


def _dataset_sort_key(dataset_id: str) -> tuple[int, str]:
    try:
        return int(dataset_id), dataset_id
    except ValueError:
        return 0, dataset_id


def _load_equipment_metadata(
    path: Path = EQUIPMENT_METADATA_CONFIG_PATH,
) -> dict[str, dict[str, Any]]:
    """Read configured, presentation-sourced equipment metadata by sensor code."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        LOGGER.warning("설비 메타데이터 설정을 읽지 못했습니다: %s", error)
        return {}

    configured_equipment = payload.get("equipment", {})
    if not isinstance(configured_equipment, dict):
        LOGGER.warning("설비 메타데이터 설정 형식이 올바르지 않습니다.")
        return {}

    metadata: dict[str, dict[str, Any]] = {}
    for equipment_code, values in configured_equipment.items():
        if not isinstance(values, dict):
            LOGGER.warning("유효하지 않은 설비 메타데이터를 무시합니다: %s", equipment_code)
            continue
        rpm = _optional_finite_float(values.get("rpm"))
        if rpm is None or rpm <= 0:
            LOGGER.warning("유효하지 않은 RPM 설정을 무시합니다: %s", equipment_code)
            continue
        metadata[str(equipment_code).strip().upper()] = {**values, "rpm": rpm}
    return metadata


def load_datasets(data_dir: Path) -> dict[str, dict[str, Any]]:
    grouped_files: dict[str, dict[str, Path]] = {}
    if data_dir.exists():
        for path in sorted(data_dir.glob("*.csv")):
            classification = _classify_csv(path)
            if classification is None:
                continue
            dataset_id, kind = classification
            grouped_files.setdefault(dataset_id, {}).setdefault(kind, path)

    configured_equipment = _load_equipment_metadata()
    datasets: dict[str, dict[str, Any]] = {}
    for dataset_id in sorted(grouped_files, key=_dataset_sort_key):
        files = grouped_files[dataset_id]
        if "trend" not in files and "fft" not in files:
            continue
        metadata_source = files.get("trend") or files["fft"]
        equipment = _equipment_metadata(dataset_id, metadata_source)
        presentation_metadata = configured_equipment.get(equipment["id"])
        if presentation_metadata is not None:
            equipment.update(presentation_metadata)
        rpm = equipment.get("rpm")
        bearing = {"maker": equipment.get("maker"), "number": equipment.get("bearing")}
        errors: dict[str, str] = {}

        trend = None
        if trend_path := files.get("trend"):
            try:
                trend = _load_trend(trend_path)
            except (OSError, ValueError, csv.Error) as error:
                LOGGER.warning("Trend CSV를 읽지 못했습니다: %s (%s)", trend_path, error)
                errors["trend"] = str(error)

        fft = None
        if fft_path := files.get("fft"):
            try:
                fft = _load_fft(fft_path, rpm, bearing)
            except (OSError, ValueError, SyntaxError, csv.Error) as error:
                LOGGER.warning("FFT CSV를 읽지 못했습니다: %s (%s)", fft_path, error)
                errors["fft"] = str(error)

        warning_status = None
        if warning_status_path := files.get("warningStatus"):
            try:
                warning_status = _load_warning_status(warning_status_path)
            except (OSError, ValueError, csv.Error) as error:
                LOGGER.warning(
                    "WarningStatus CSV를 읽지 못했습니다: %s (%s)", warning_status_path, error
                )
                errors["warningStatus"] = str(error)

        if trend is not None:
            trend["metrics"] = _build_trend_metrics(trend, warning_status)

        measured_dates: list[str] = []
        current_velocity = None
        current_acceleration = None
        if trend is not None:
            latest_point = trend["points"][-1]
            measured_dates.append(latest_point["timestamp"])
            current_velocity = latest_point["value"]
            current_acceleration = latest_point["acceleration"]
        if fft is not None:
            measured_dates.append(fft["measuredAt"])
        if warning_status is not None:
            measured_dates.append(warning_status["measuredAt"])

        trend_analysis = trend["analysis"] if trend is not None else None
        if trend_analysis is None or trend_analysis["status"] == "insufficient_data":
            status, status_label, status_description, status_color = (
                "unknown",
                "추세 판단 불가",
                "우상향 판정에는 최소 143개의 시간별 VelAve 이력이 필요합니다.",
                "#94a3aa",
            )
        elif trend_analysis["status"] == "rising":
            status, status_label, status_description, status_color = (
                "caution",
                "상승 경향",
                "최근 72시간 이동평균의 기울기가 상승 임계값을 초과했습니다.",
                "#f1a526",
            )
        else:
            status, status_label, status_description, status_color = (
                "normal",
                "정상",
                "최근 VelAve에서 상승 경향이 검출되지 않았습니다.",
                "#14a47b",
            )

        equipment.update(
            {
                "lastMeasuredAt": max(measured_dates) if measured_dates else None,
                "status": status,
                "statusLabel": status_label,
                "statusDescription": status_description,
                "statusColor": status_color,
            }
        )

        datasets[dataset_id] = {
            "meta": {
                "mock": False,
                "source": "csv",
                "datasetId": dataset_id,
                "availability": {
                    "trend": trend is not None,
                    "fft": fft is not None,
                    "warningStatus": warning_status is not None,
                },
                "errors": errors,
            },
            "equipment": equipment,
            "current": {
                "velocity": current_velocity,
                "velocityUnit": "mm/s",
                "warningThreshold": (
                    warning_status["warningThreshold"] if warning_status is not None else None
                ),
                "dangerThreshold": (
                    warning_status["dangerThreshold"] if warning_status is not None else None
                ),
                "acceleration": current_acceleration,
                "accelerationUnit": "g",
                "temperature": None,
                "temperatureUnit": "°C",
                "operatingRate": None,
            },
            "trend": trend,
            "fft": fft,
            "levelAnalysis": analyze_velave_level(
                trend["points"] if trend is not None else [], warning_status
            ),
            "diagnosis": None,
        }

    return datasets


def dataset_summaries(datasets: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    summaries = []
    for dataset_id in sorted(datasets, key=_dataset_sort_key):
        dataset = datasets[dataset_id]
        equipment = dataset["equipment"]
        summaries.append(
            {
                "id": dataset_id,
                "equipmentCode": equipment["id"],
                "name": equipment["name"],
                "measurementPoint": equipment["measurementPoint"],
                "displayName": equipment["displayName"],
                "plant": equipment["plant"],
                "line": equipment["line"],
                "status": equipment["status"],
                "statusLabel": equipment["statusLabel"],
                "statusDescription": equipment["statusDescription"],
                "statusColor": equipment["statusColor"],
                "lastMeasuredAt": equipment["lastMeasuredAt"],
                "availability": dataset["meta"]["availability"],
            }
        )
    return summaries
