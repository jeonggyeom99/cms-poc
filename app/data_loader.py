from __future__ import annotations

import ast
import csv
import logging
import math
import re
import struct
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)

DATASET_NUMBER_PATTERN = re.compile(r"^\s*(\d+)\.")
EQUIPMENT_CODE_PATTERN = re.compile(r"\b(V\d+)\b", re.IGNORECASE)
DATA_KIND_PATTERN = re.compile(r"^(?:FFT|Trend)[ _]*", re.IGNORECASE)
TRAILING_CODE_PATTERN = re.compile(r"\s+\(V\d+.*$", re.IGNORECASE)
INLINE_CODE_PATTERN = re.compile(r"-V\d+$", re.IGNORECASE)

FREQUENCY_RANGES_HZ = {
    "5": 500.0,
    "6": 1000.0,
}

TREND_MOVING_AVERAGE_POINTS = 72
TREND_REGRESSION_POINTS = 72
TREND_REQUIRED_POINTS = TREND_MOVING_AVERAGE_POINTS + TREND_REGRESSION_POINTS - 1
TREND_RISING_THRESHOLD = 1 / (24 * 14)


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


def _dataset_sort_key(dataset_id: str) -> tuple[int, str]:
    try:
        return int(dataset_id), dataset_id
    except ValueError:
        return 0, dataset_id


def _classify_csv(path: Path) -> tuple[str, str] | None:
    name = path.name
    dataset_match = DATASET_NUMBER_PATTERN.match(name)
    if dataset_match is None or "warningstatus" in name.lower():
        return None

    lowered_name = name.lower()
    if "fft" in lowered_name:
        kind = "fft"
    elif "trend" in lowered_name:
        kind = "trend"
    else:
        return None

    return dataset_match.group(1), kind


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


def _decode_float32_bytes(raw_value: str) -> list[float]:
    decoded = ast.literal_eval(raw_value)
    if not isinstance(decoded, bytes):
        raise ValueError("FFT ResultData가 bytes 리터럴이 아닙니다.")
    if len(decoded) % 4:
        raise ValueError("FFT ResultData 길이가 float32 크기와 맞지 않습니다.")

    value_count = len(decoded) // 4
    return list(struct.unpack(f"<{value_count}f", decoded))


def _load_fft(path: Path) -> dict[str, Any]:
    latest_row: dict[str, str] | None = None
    with path.open(encoding="utf-8-sig", newline="") as fft_file:
        reader = csv.DictReader(fft_file)
        required_columns = {"MeasureDate", "MeasureMode", "MeasureFreq", "MeasureLineNum", "ResultData"}
        if not required_columns.issubset(reader.fieldnames or []):
            missing = ", ".join(sorted(required_columns - set(reader.fieldnames or [])))
            raise ValueError(f"FFT CSV 필수 컬럼 누락: {missing}")

        for row in reader:
            if row["MeasureMode"] != "3":
                continue
            if latest_row is None or row["MeasureDate"] > latest_row["MeasureDate"]:
                latest_row = row

    if latest_row is None:
        raise ValueError("FFT CSV에 속도(MeasureMode=3) 데이터가 없습니다.")

    frequency_code = latest_row["MeasureFreq"]
    if frequency_code not in FREQUENCY_RANGES_HZ:
        raise ValueError(f"지원하지 않는 FFT 주파수 코드: {frequency_code}")

    amplitudes = _decode_float32_bytes(latest_row["ResultData"])
    line_count = int(latest_row["MeasureLineNum"])
    if len(amplitudes) != line_count:
        raise ValueError(
            f"FFT 라인 수 불일치: MeasureLineNum={line_count}, ResultData={len(amplitudes)}"
        )

    frequency_range = FREQUENCY_RANGES_HZ[frequency_code]
    frequency_step = frequency_range / line_count
    return {
        "measuredAt": latest_row["MeasureDate"],
        "frequencyUnit": "Hz",
        "amplitudeUnit": "mm/s",
        "frequencyRange": frequency_range,
        "frequencies": [index * frequency_step for index in range(line_count)],
        "amplitudes": amplitudes,
    }


def load_datasets(data_dir: Path) -> dict[str, dict[str, Any]]:
    grouped_files: dict[str, dict[str, Path]] = {}
    if data_dir.exists():
        for path in sorted(data_dir.glob("*.csv")):
            classification = _classify_csv(path)
            if classification is None:
                continue
            dataset_id, kind = classification
            grouped_files.setdefault(dataset_id, {}).setdefault(kind, path)

    datasets: dict[str, dict[str, Any]] = {}
    for dataset_id in sorted(grouped_files, key=_dataset_sort_key):
        files = grouped_files[dataset_id]
        metadata_source = files.get("trend") or files["fft"]
        equipment = _equipment_metadata(dataset_id, metadata_source)
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
                fft = _load_fft(fft_path)
            except (OSError, ValueError, SyntaxError, csv.Error) as error:
                LOGGER.warning("FFT CSV를 읽지 못했습니다: %s (%s)", fft_path, error)
                errors["fft"] = str(error)

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

        trend_analysis = trend["analysis"] if trend is not None else None
        if trend_analysis is None or trend_analysis["status"] == "insufficient_data":
            status, status_label, status_description, status_color = (
                "unknown", "추세 판단 불가", "우상향 판정에는 최소 143개의 시간별 VelAve 이력이 필요합니다.", "#94a3aa",
            )
        elif trend_analysis["status"] == "rising":
            status, status_label, status_description, status_color = (
                "caution", "상승 경향", "최근 72시간 이동평균의 기울기가 상승 임계값을 초과했습니다.", "#f1a526",
            )
        else:
            status, status_label, status_description, status_color = (
                "normal", "정상", "최근 VelAve에서 상승 경향이 검출되지 않았습니다.", "#14a47b",
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
                },
                "errors": errors,
            },
            "equipment": equipment,
            "current": {
                "velocity": current_velocity,
                "velocityUnit": "mm/s",
                "warningThreshold": None,
                "dangerThreshold": None,
                "acceleration": current_acceleration,
                "accelerationUnit": "g",
                "temperature": None,
                "temperatureUnit": "°C",
                "operatingRate": None,
            },
            "trend": trend,
            "fft": fft,
            "levelAnalysis": None,
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
                "availability": dataset["meta"]["availability"],
            }
        )
    return summaries
