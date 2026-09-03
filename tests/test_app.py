import asyncio
import csv
import struct
from pathlib import Path

import httpx
import pytest

from app.data_loader import (
    TREND_RISING_THRESHOLD,
    _fill_low_outliers,
    analyze_velave_level,
    analyze_velave_trend,
    load_datasets,
)
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
WARNING_STATUS_COLUMNS = [
    "GenerationTime",
    "ACCALLJudgeWarnValue",
    "ACCALLJudgeDangValue",
    "ACCBPFJudgeWarnValue",
    "ACCBPFJudgeDangValue",
    "ACCPEAKJudgeWarnValue",
    "ACCPEAKJudgeDangValue",
    "VELJudgeWarnValue",
    "VELJudgeDangValue",
    "DISPJudgeWarnValue",
    "DISPJudgeDangValue",
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


def warning_status_row(measured_at: str, warning: float, danger: float) -> dict[str, str]:
    return {
        "GenerationTime": measured_at,
        "ACCALLJudgeWarnValue": "2.19",
        "ACCALLJudgeDangValue": "2.56",
        "ACCBPFJudgeWarnValue": "1.68",
        "ACCBPFJudgeDangValue": "2.02",
        "ACCPEAKJudgeWarnValue": "15.0",
        "ACCPEAKJudgeDangValue": "20.0",
        "VELJudgeWarnValue": str(warning),
        "VELJudgeDangValue": str(danger),
        "DISPJudgeWarnValue": "60.0",
        "DISPJudgeDangValue": "71.0",
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
        tmp_path / "1. WarningStatus Area_Test Pump_Point A (V001).csv",
        WARNING_STATUS_COLUMNS,
        [
            warning_status_row("2026-01-01 00:00:00", 4.0, 8.0),
            warning_status_row("2026-01-05 00:00:00", 4.72, 5.44),
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


def test_csv_loader_groups_files_and_ignores_warning_status_only_dataset(tmp_path: Path) -> None:
    datasets = load_datasets(make_data_dir(tmp_path))

    assert list(datasets) == ["1", "2", "3"]
    assert datasets["1"]["meta"]["mock"] is False
    assert datasets["1"]["meta"]["availability"] == {
        "trend": True,
        "fft": True,
        "warningStatus": True,
    }
    assert datasets["2"]["meta"]["availability"] == {
        "trend": False,
        "fft": True,
        "warningStatus": False,
    }
    assert datasets["3"]["meta"]["availability"] == {
        "trend": True,
        "fft": False,
        "warningStatus": False,
    }


def test_csv_loader_sorts_trend_and_decodes_latest_velocity_fft(tmp_path: Path) -> None:
    datasets = load_datasets(make_data_dir(tmp_path))
    dataset = datasets["1"]

    assert [point["value"] for point in dataset["trend"]["points"]] == [1.0, 2.0]
    assert dataset["trend"]["points"][-1] == {
        "timestamp": "2026-01-02 00:00:00",
        "value": 2.0,
        "acceleration": 0.2,
        "accelerationBpf": 0.1,
        "accelerationPeak": 0.2,
        "displacement": 3.0,
    }
    metrics = {metric["key"]: metric for metric in dataset["trend"]["metrics"]}
    assert metrics["accelerationAll"] == {
        "key": "accelerationAll",
        "pointKey": "acceleration",
        "label": "가속도 ALL",
        "unit": "g",
        "latestValue": 0.2,
        "warningThreshold": pytest.approx(2.19),
        "dangerThreshold": pytest.approx(2.56),
        "available": True,
    }
    assert metrics["accelerationBpf"]["warningThreshold"] == pytest.approx(1.68)
    assert metrics["accelerationPeak"]["dangerThreshold"] == pytest.approx(20.0)
    assert metrics["velocity"]["latestValue"] == 2.0
    assert metrics["velocity"]["warningThreshold"] == pytest.approx(4.72)
    assert metrics["displacement"]["pointKey"] == "displacement"
    assert metrics["displacement"]["latestValue"] == 3.0
    assert metrics["displacement"]["unit"] == "µm"
    assert metrics["displacement"]["dangerThreshold"] == pytest.approx(71.0)
    assert dataset["current"]["velocity"] == 2.0
    assert dataset["current"]["acceleration"] == 0.2
    assert dataset["current"]["warningThreshold"] == pytest.approx(4.72)
    assert dataset["current"]["dangerThreshold"] == pytest.approx(5.44)
    assert dataset["levelAnalysis"]["configured"]["measuredAt"] == "2026-01-05 00:00:00"
    assert dataset["fft"]["measuredAt"] == "2026-01-04 00:00:00"
    assert dataset["fft"]["frequencies"] == [0.0, 250.0]
    assert dataset["fft"]["amplitudes"] == pytest.approx([0.3, 0.4])

    fft_only = datasets["2"]
    assert fft_only["fft"]["frequencyRange"] == 1000.0
    assert fft_only["fft"]["frequencies"] == [0.0, 250.0, 500.0, 750.0]


def test_velave_level_uses_three_calendar_months_and_excludes_iqr_outlier() -> None:
    points = [
        {"timestamp": "2026-01-31 12:00:00", "value": 1000.0},
        {"timestamp": "2026-02-28 12:00:00", "value": 1.0},
        {"timestamp": "2026-03-15 12:00:00", "value": 2.0},
        {"timestamp": "2026-04-15 12:00:00", "value": 2.0},
        {"timestamp": "2026-05-01 12:00:00", "value": 2.0},
        {"timestamp": "2026-05-30 12:00:00", "value": 3.0},
        {"timestamp": "2026-05-31 12:00:00", "value": 100.0},
    ]
    configured = {
        "measuredAt": "2026-06-01 00:00:00",
        "warningThreshold": 5.0,
        "dangerThreshold": 7.0,
    }

    analysis = analyze_velave_level(points, configured)

    assert analysis["status"] == "compared"
    assert analysis["windowStart"] == "2026-02-28 12:00:00"
    assert analysis["windowEnd"] == "2026-05-31 12:00:00"
    assert analysis["usedPoints"] == 6
    assert analysis["normalPoints"] == 5
    assert analysis["outlierPoints"] == 1
    assert analysis["normalMean"] == pytest.approx(2.0)
    assert analysis["recommended"] == pytest.approx(
        {"warningThreshold": 4.0, "dangerThreshold": 8.0}
    )
    assert analysis["difference"] == pytest.approx(
        {"warningThreshold": 1.0, "dangerThreshold": -1.0}
    )


def test_velave_level_returns_recommendation_without_configured_levels() -> None:
    analysis = analyze_velave_level(
        [{"timestamp": "2026-05-31 12:00:00", "value": 2.5}]
    )

    assert analysis["status"] == "recommendation_only"
    assert analysis["configured"] is None
    assert analysis["difference"] is None
    assert analysis["recommended"] == pytest.approx(
        {"warningThreshold": 5.0, "dangerThreshold": 10.0}
    )


def test_invalid_warning_status_is_reported_without_discarding_trend(tmp_path: Path) -> None:
    write_csv(
        tmp_path / "1.Trend_Test Pump_Point (V001).csv",
        TREND_COLUMNS,
        [trend_row("2026-01-01 00:00:00", 2.0, 0.1)],
    )
    write_csv(
        tmp_path / "1. WarningStatus Test Pump_Point (V001).csv",
        ["GenerationTime", "VELJudgeWarnValue"],
        [{"GenerationTime": "2026-01-01 00:00:00", "VELJudgeWarnValue": "4.0"}],
    )

    dataset = load_datasets(tmp_path)["1"]

    assert dataset["meta"]["availability"]["trend"] is True
    assert dataset["meta"]["availability"]["warningStatus"] is False
    assert "VELJudgeDangValue" in dataset["meta"]["errors"]["warningStatus"]
    assert dataset["levelAnalysis"]["status"] == "recommendation_only"


def test_non_finite_warning_status_value_is_reported(tmp_path: Path) -> None:
    write_csv(
        tmp_path / "1.Trend_Test Pump_Point (V001).csv",
        TREND_COLUMNS,
        [trend_row("2026-01-01 00:00:00", 2.0, 0.1)],
    )
    write_csv(
        tmp_path / "1. WarningStatus Test Pump_Point (V001).csv",
        WARNING_STATUS_COLUMNS,
        [warning_status_row("2026-01-01 00:00:00", float("nan"), 8.0)],
    )

    dataset = load_datasets(tmp_path)["1"]

    assert dataset["meta"]["availability"]["warningStatus"] is False
    assert "유효한 숫자" in dataset["meta"]["errors"]["warningStatus"]
    assert dataset["current"]["warningThreshold"] is None


def test_optional_metric_thresholds_do_not_invalidate_velocity_status(tmp_path: Path) -> None:
    write_csv(
        tmp_path / "1.Trend_Test Pump_Point (V001).csv",
        TREND_COLUMNS,
        [trend_row("2026-01-01 00:00:00", 2.0, 0.1)],
    )
    write_csv(
        tmp_path / "1. WarningStatus Test Pump_Point (V001).csv",
        [
            "GenerationTime",
            "ACCALLJudgeWarnValue",
            "ACCALLJudgeDangValue",
            "VELJudgeWarnValue",
            "VELJudgeDangValue",
        ],
        [
            {
                "GenerationTime": "2026-01-01 00:00:00",
                "ACCALLJudgeWarnValue": "not-a-number",
                "ACCALLJudgeDangValue": "3.0",
                "VELJudgeWarnValue": "4.0",
                "VELJudgeDangValue": "8.0",
            }
        ],
    )

    dataset = load_datasets(tmp_path)["1"]
    metrics = {metric["key"]: metric for metric in dataset["trend"]["metrics"]}

    assert dataset["meta"]["availability"]["warningStatus"] is True
    assert dataset["current"]["warningThreshold"] == 4.0
    assert metrics["accelerationAll"]["warningThreshold"] is None
    assert metrics["accelerationAll"]["dangerThreshold"] == 3.0
    assert metrics["accelerationBpf"]["warningThreshold"] is None
    assert metrics["velocity"]["warningThreshold"] == 4.0


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
        assert payload["levelAnalysis"]["status"] == "recommendation_only"
        assert payload["equipment"]["status"] == equipment_status
        assert payload["equipment"]["statusLabel"] == status_label
        assert payload["equipment"]["statusDescription"]
        assert payload["equipment"]["statusColor"].startswith("#")


def test_dashboard_page_is_served(tmp_path: Path) -> None:
    response = get(create_app(make_data_dir(tmp_path)), "/")

    assert response.status_code == 200
    assert 'id="dataset-select"' in response.text
    assert "CSV DATA" in response.text
    assert 'class="equipment-overview"' in response.text
    assert 'id="dataset-availability"' in response.text
    assert 'id="status-measured-at"' in response.text
    assert 'class="overview-metrics"' in response.text
    assert "Trend Graph" in response.text
    assert "FFT Graph" in response.text
    assert 'id="trend-expand"' in response.text
    assert 'id="fft-expand"' in response.text
    assert 'id="graph-modal"' in response.text
    assert 'id="graph-modal-chart"' in response.text
    assert 'id="trend-metric-selector"' in response.text
    assert 'id="trend-metric-grid"' in response.text
    assert "후속 단계" in response.text


def test_dataset_and_dashboard_apis_return_csv_payloads(tmp_path: Path) -> None:
    target_app = create_app(make_data_dir(tmp_path))

    list_response = get(target_app, "/api/datasets")
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert [item["id"] for item in items] == ["1", "2", "3"]
    assert items[1]["equipmentCode"] == "V002"
    assert items[1]["availability"] == {
        "trend": False,
        "fft": True,
        "warningStatus": False,
    }

    detail_response = get(target_app, "/api/dashboard/3")
    assert detail_response.status_code == 200
    payload = detail_response.json()
    assert payload["meta"]["source"] == "csv"
    assert payload["meta"]["mock"] is False
    assert payload["trend"]["points"]
    assert payload["trend"]["analysis"]["status"] == "insufficient_data"
    assert payload["trend"]["analysis"]["requiredPoints"] == 143
    assert payload["levelAnalysis"]["status"] == "recommendation_only"
    assert payload["fft"] is None
    assert payload["diagnosis"] is None
    assert payload["equipment"]["status"] == "unknown"
    assert payload["equipment"]["statusLabel"] == "추세 판단 불가"


def test_dashboard_api_returns_level_comparison_states(tmp_path: Path) -> None:
    target_app = create_app(make_data_dir(tmp_path))

    compared = get(target_app, "/api/dashboard/1").json()
    unavailable = get(target_app, "/api/dashboard/2").json()
    recommendation_only = get(target_app, "/api/dashboard/3").json()

    assert compared["levelAnalysis"]["status"] == "compared"
    assert compared["levelAnalysis"]["difference"] is not None
    assert unavailable["levelAnalysis"]["status"] == "unavailable"
    assert recommendation_only["levelAnalysis"]["status"] == "recommendation_only"


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
