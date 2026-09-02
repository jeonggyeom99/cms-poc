import asyncio
import csv
import struct
from pathlib import Path

import httpx
import pytest

from app.data_loader import TREND_RISING_THRESHOLD, _fill_low_outliers, analyze_velave_trend, load_datasets
from app.main import create_app


TREND_COLUMNS = [
    "SignalID",
    "DataDate",
    "AccAllAve",
    "AccBpfAve",
    "AccPeakAve",
    "VelAve",
    "CrestfactorAve",
]
FFT_COLUMNS = [
    "SignalID",
    "MeasureDate",
    "ExtractionType",
    "DaiagMode",
    "MeasureMode",
    "MeasureFreq",
    "MeasureLineNum",
    "TimeWaveSampling",
    "ResultData",
]


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def trend_row(timestamp: str, velocity: float, acceleration: float) -> dict[str, str]:
    return {
        "SignalID": "1",
        "DataDate": timestamp,
        "AccAllAve": str(acceleration),
        "AccBpfAve": "0.1",
        "AccPeakAve": "0.2",
        "VelAve": str(velocity),
        "CrestfactorAve": "3.0",
    }


def trend_points(values: list[float]) -> list[dict[str, float | str]]:
    return [
        {"timestamp": f"2026-01-{index // 24 + 1:02d} {index % 24:02d}:00:00", "value": value}
        for index, value in enumerate(values)
    ]


def fft_row(
    measured_at: str,
    amplitudes: list[float],
    *,
    measure_mode: str = "3",
    frequency_code: str = "5",
) -> dict[str, str]:
    result_data = struct.pack(f"<{len(amplitudes)}f", *amplitudes)
    return {
        "SignalID": "1",
        "MeasureDate": measured_at,
        "ExtractionType": "2",
        "DaiagMode": "1",
        "MeasureMode": measure_mode,
        "MeasureFreq": frequency_code,
        "MeasureLineNum": str(len(amplitudes)),
        "TimeWaveSampling": repr(b""),
        "ResultData": repr(result_data),
    }


def make_data_dir(tmp_path: Path) -> Path:
    write_csv(
        tmp_path / "1.Trend_Area_Test Pump_Point A (V001).csv",
        TREND_COLUMNS,
        [
            trend_row("2026-01-02 00:00:00", 2.0, 0.2),
            trend_row("2026-01-01 00:00:00", 1.0, 0.1),
        ],
    )
    write_csv(
        tmp_path / "1.FFT_Area_Test Pump_Point A (V001).csv",
        FFT_COLUMNS,
        [
            fft_row("2026-01-03 00:00:00", [9.0, 9.0], measure_mode="2"),
            fft_row("2026-01-01 00:00:00", [0.1, 0.2]),
            fft_row("2026-01-04 00:00:00", [0.3, 0.4]),
        ],
    )
    write_csv(
        tmp_path / "2.FFT_Second Pump_Point B (V002).csv",
        FFT_COLUMNS,
        [fft_row("2026-02-01 00:00:00", [1.0, 2.0, 3.0, 4.0], frequency_code="6")],
    )
    write_csv(
        tmp_path / "3.Trend_Third Pump_Point C (V003).csv",
        TREND_COLUMNS,
        [trend_row("2026-03-01 00:00:00", 3.0, 0.3)],
    )
    write_csv(
        tmp_path / "4. WarningStatus Ignored Pump (V004).csv",
        ["GenerationTime", "VELMeasureValue"],
        [{"GenerationTime": "2026-04-01 00:00:00", "VELMeasureValue": "4.0"}],
    )
    return tmp_path


def get(target_app, path: str) -> httpx.Response:
    async def request() -> httpx.Response:
        async with target_app.router.lifespan_context(target_app):
            transport = httpx.ASGITransport(app=target_app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.get(path)

    return asyncio.run(request())


def test_csv_loader_groups_files_and_ignores_warning_status(tmp_path: Path) -> None:
    datasets = load_datasets(make_data_dir(tmp_path))

    assert list(datasets) == ["1", "2", "3"]
    assert datasets["1"]["meta"]["mock"] is False
    assert datasets["1"]["meta"]["availability"] == {"trend": True, "fft": True}
    assert datasets["2"]["meta"]["availability"] == {"trend": False, "fft": True}
    assert datasets["3"]["meta"]["availability"] == {"trend": True, "fft": False}


def test_csv_loader_sorts_trend_and_decodes_latest_velocity_fft(tmp_path: Path) -> None:
    datasets = load_datasets(make_data_dir(tmp_path))
    dataset = datasets["1"]

    assert [point["value"] for point in dataset["trend"]["points"]] == [1.0, 2.0]
    assert dataset["current"]["velocity"] == 2.0
    assert dataset["current"]["acceleration"] == 0.2
    assert dataset["fft"]["measuredAt"] == "2026-01-04 00:00:00"
    assert dataset["fft"]["frequencies"] == [0.0, 250.0]
    assert dataset["fft"]["amplitudes"] == pytest.approx([0.3, 0.4])

    fft_only = datasets["2"]
    assert fft_only["fft"]["frequencyRange"] == 1000.0
    assert fft_only["fft"]["frequencies"] == [0.0, 250.0, 500.0, 750.0]


def test_velave_trend_detects_rising_slope() -> None:
    analysis = analyze_velave_trend(trend_points([1.0 + index * 0.01 for index in range(143)]))

    assert analysis["status"] == "rising"
    assert analysis["isRising"] is True
    assert analysis["slope"] > TREND_RISING_THRESHOLD
    assert analysis["detectedAt"] == "2026-01-03 23:00:00"
    assert analysis["usedPoints"] == analysis["requiredPoints"] == 143


def test_velave_trend_classifies_flat_data_as_stable() -> None:
    analysis = analyze_velave_trend(trend_points([2.5] * 143))

    assert analysis["status"] == "stable"
    assert analysis["isRising"] is False
    assert analysis["detectedAt"] is None
    assert analysis["slope"] == pytest.approx(0)


def test_velave_trend_interpolates_low_outliers_before_analysis() -> None:
    values = [1.0 + index * 0.01 for index in range(143)]
    values[80] = -1000.0

    corrected = _fill_low_outliers(values)
    analysis = analyze_velave_trend(trend_points(values))

    assert corrected[80] == pytest.approx((corrected[79] + corrected[81]) / 2)
    assert analysis["status"] == "rising"


def test_velave_trend_requires_at_least_143_points() -> None:
    analysis = analyze_velave_trend(trend_points([1.0] * 142))

    assert analysis["status"] == "insufficient_data"
    assert analysis["isRising"] is None
    assert analysis["detectedAt"] is None
    assert analysis["usedPoints"] == 142
    assert analysis["requiredPoints"] == 143


def test_dashboard_api_returns_trend_analysis_and_derived_statuses(tmp_path: Path) -> None:
    scenarios = {
        "1": ([1.0 + index * 0.01 for index in range(143)], "rising", "caution", "상승 경향"),
        "2": ([2.0] * 143, "stable", "normal", "정상"),
        "3": ([2.0] * 142, "insufficient_data", "unknown", "추세 판단 불가"),
    }
    for dataset_id, (values, _, _, _) in scenarios.items():
        write_csv(
            tmp_path / f"{dataset_id}.Trend_Test Pump_Point (V{dataset_id.zfill(3)}).csv",
            TREND_COLUMNS,
            [trend_row(point["timestamp"], point["value"], 0.1) for point in trend_points(values)],
        )

    target_app = create_app(tmp_path)
    for dataset_id, (_, analysis_status, equipment_status, status_label) in scenarios.items():
        payload = get(target_app, f"/api/dashboard/{dataset_id}").json()

        assert payload["trend"]["analysis"]["status"] == analysis_status
        assert payload["equipment"]["status"] == equipment_status
        assert payload["equipment"]["statusLabel"] == status_label
        assert payload["equipment"]["statusDescription"]
        assert payload["equipment"]["statusColor"].startswith("#")


def test_dashboard_page_is_served(tmp_path: Path) -> None:
    response = get(create_app(make_data_dir(tmp_path)), "/")

    assert response.status_code == 200
    assert 'id="dataset-select"' in response.text
    assert "CSV DATA" in response.text
    assert "Trend Graph" in response.text
    assert "FFT Graph" in response.text
    assert "후속 단계" in response.text


def test_dataset_and_dashboard_apis_return_csv_payloads(tmp_path: Path) -> None:
    target_app = create_app(make_data_dir(tmp_path))

    list_response = get(target_app, "/api/datasets")
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert [item["id"] for item in items] == ["1", "2", "3"]
    assert items[1]["equipmentCode"] == "V002"
    assert items[1]["availability"] == {"trend": False, "fft": True}

    detail_response = get(target_app, "/api/dashboard/3")
    assert detail_response.status_code == 200
    payload = detail_response.json()
    assert payload["meta"]["source"] == "csv"
    assert payload["meta"]["mock"] is False
    assert payload["trend"]["points"]
    assert payload["trend"]["analysis"]["status"] == "insufficient_data"
    assert payload["trend"]["analysis"]["requiredPoints"] == 143
    assert payload["fft"] is None
    assert payload["diagnosis"] is None
    assert payload["equipment"]["status"] == "unknown"
    assert payload["equipment"]["statusLabel"] == "추세 판단 불가"


def test_default_dashboard_and_missing_dataset_responses(tmp_path: Path) -> None:
    target_app = create_app(make_data_dir(tmp_path))

    default_response = get(target_app, "/api/dashboard")
    assert default_response.status_code == 200
    assert default_response.json()["meta"]["datasetId"] == "1"

    missing_response = get(target_app, "/api/dashboard/99")
    assert missing_response.status_code == 404


def test_empty_data_directory_returns_empty_list_and_no_default(tmp_path: Path) -> None:
    target_app = create_app(tmp_path)

    assert get(target_app, "/api/datasets").json() == {"items": []}
    assert get(target_app, "/api/dashboard").status_code == 404
