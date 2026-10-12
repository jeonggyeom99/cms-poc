import asyncio
import csv
import json
from datetime import datetime, timedelta
import struct
from pathlib import Path

import httpx
import pytest

from app.ai_analysis import (
    AiDiagnosis,
    AiFinding,
    AiLikelyCause,
    AiRecommendedAction,
    OpenAIAnalysisGateway,
    OpenAISettings,
)
from app.chat import OpenAIDashboardChatGateway
from app.data_loader import (
    TREND_RISING_THRESHOLD,
    _fill_low_outliers,
    _build_fft_record,
    _load_equipment_metadata,
    analyze_acceleration_bearing_fft,
    analyze_fft_spectrum,
    analyze_fft_diagnosis,
    analyze_velocity_fft,
    analyze_velave_level,
    analyze_velave_trend,
    load_datasets,
    load_fft_record,
)
from app.main import create_app


TREND_COLUMNS = [
    "SignalID",
    "DataDate",
    "AccAllAve",
    "AccBpfAve",
    "AccPeakAve",
    "VelAve",
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
    extraction_type: str = "2",
    diag_mode: str = "1",
    time_wave_samples: list[float] | None = None,
) -> dict[str, str]:
    result_data = struct.pack(f"<{len(amplitudes)}f", *amplitudes)
    time_wave_data = (
        struct.pack(f"<{len(time_wave_samples)}f", *time_wave_samples)
        if time_wave_samples is not None
        else b""
    )
    return {
        "SignalID": "1",
        "MeasureDate": measured_at,
        "ExtractionType": extraction_type,
        "DaiagMode": diag_mode,
        "MeasureMode": measure_mode,
        "MeasureFreq": frequency_code,
        "MeasureLineNum": str(len(amplitudes)),
        "TimeWaveSampling": repr(time_wave_data),
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
            fft_row(
                "2026-01-03 00:00:00",
                [9.0, 9.0],
                measure_mode="2",
                time_wave_samples=[-0.25, 0.5, 0.125],
            ),
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


def post(target_app, path: str, payload: dict) -> httpx.Response:
    async def request() -> httpx.Response:
        async with target_app.router.lifespan_context(target_app):
            transport = httpx.ASGITransport(app=target_app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.post(path, json=payload)

    return asyncio.run(request())


class FakeAiGateway:
    def __init__(self) -> None:
        self.contexts: list[dict] = []

    async def analyze(self, context: dict) -> AiDiagnosis:
        self.contexts.append(context)
        return AiDiagnosis(
            headline="선택 FFT에서 점검이 필요한 성분을 확인했습니다.",
            risk_level="caution",
            risk_label="주의",
            trend_summary="측정 기간의 추세를 확인했습니다.",
            fft_summary="주파수 측정 근거를 확인했습니다.",
            fft_analysis_period={"start": None, "end": None},
            fft_reference_record_ids=[],
            trend_findings=[AiFinding(heading="Trend", detail="속도값을 확인했습니다.")],
            fft_findings=[AiFinding(heading="FFT", detail="주요 Peak를 확인했습니다.")],
            history_findings=[],
            likely_causes=[
                AiLikelyCause(
                    cause="시험 진단",
                    confidence="medium",
                    rationale="Fake gateway 응답입니다.",
                )
            ],
            counter_evidence=["현장 운전 조건은 제공되지 않았습니다."],
            recommended_actions=[
                AiRecommendedAction(
                    priority="high",
                    action="다음 측정에서 Peak를 재확인합니다.",
                    rationale="변화 추세 확인이 필요합니다.",
                )
            ],
        )


class FakeChatGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[dict, list, str]] = []

    async def respond(self, context: dict, history: list, message: str) -> str:
        self.calls.append((context, history, message))
        return "선택한 측정 기록을 먼저 재확인해 주세요."


def test_dashboard_until_rebuilds_snapshot_and_limits_fft_records(tmp_path: Path) -> None:
    target_app = create_app(make_data_dir(tmp_path))

    snapshot = get(target_app, "/api/dashboard/1?until=2026-01-01")
    latest = get(target_app, "/api/dashboard/1")
    fft_record = get(target_app, "/api/dashboard/1/fft/3?until=2026-01-01")
    future_fft_record = get(target_app, "/api/dashboard/1/fft/4?until=2026-01-01")
    invalid = get(target_app, "/api/dashboard/1?until=not-a-date")
    empty = get(target_app, "/api/dashboard/1?until=2025-12-31")

    assert snapshot.status_code == 200
    payload = snapshot.json()
    assert [point["timestamp"] for point in payload["trend"]["points"]] == ["2026-01-01 00:00:00"]
    assert payload["current"]["velocity"] == 1.0
    assert payload["current"]["warningThreshold"] == 4.0
    assert [record["id"] for record in payload["fft"]["records"]] == [3]
    assert payload["fft"]["recordId"] == 3
    assert latest.json()["current"]["velocity"] == 2.0
    assert fft_record.status_code == 200
    assert future_fft_record.status_code == 404
    assert invalid.status_code == 422
    assert empty.status_code == 404


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


def test_warning_status_with_different_file_number_matches_equipment_code(tmp_path: Path) -> None:
    write_csv(
        tmp_path / "2.Trend_Area_Test Pump_Point A (V056).csv",
        TREND_COLUMNS,
        [trend_row("2026-01-02 00:00:00", 2.0, 0.2)],
    )
    write_csv(
        tmp_path / "9.WarningStatus_Area_Test Pump_Point A (V056).csv",
        WARNING_STATUS_COLUMNS,
        [warning_status_row("2026-01-05 00:00:00", 1.4, 2.8)],
    )

    dataset = load_datasets(tmp_path)["2"]

    assert dataset["meta"]["availability"]["warningStatus"] is True
    assert dataset["current"]["warningThreshold"] == 1.4
    assert dataset["current"]["dangerThreshold"] == 2.8
    assert dataset["levelAnalysis"]["configured"]["warningThreshold"] == 1.4
    velocity_metric = next(
        metric for metric in dataset["trend"]["metrics"] if metric["key"] == "velocity"
    )
    assert velocity_metric["warningThreshold"] == 1.4


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
    assert dataset["current"]["velocity"] == 2.0
    assert dataset["current"]["acceleration"] == 0.2
    assert dataset["current"]["warningThreshold"] == pytest.approx(4.72)
    assert dataset["current"]["dangerThreshold"] == pytest.approx(5.44)
    assert dataset["levelAnalysis"]["configured"]["measuredAt"] == "2026-01-05 00:00:00"
    # The dashboard current state follows the latest analysable FFT, even when
    # an older record has the larger amplitude.
    assert dataset["fft"]["measuredAt"] == "2026-01-04 00:00:00"
    assert dataset["fft"]["recordId"] == 4
    assert [record["id"] for record in dataset["fft"]["records"]] == [4, 2, 3]
    assert dataset["fft"]["records"][0]["hasHighAmplitude"] is False
    assert dataset["fft"]["records"][1]["hasHighAmplitude"] is True
    assert dataset["fft"]["records"][1]["measureMode"] == {
        "code": "2",
        "label": "가속도ENV",
    }
    assert dataset["fft"]["metadata"]["extractionType"] == {
        "code": "2",
        "label": "정기",
    }
    assert dataset["fft"]["metadata"]["diagMode"] == {"code": "1", "label": "기구부"}
    assert dataset["fft"]["metadata"]["measureFreq"] == {
        "code": "5",
        "label": "500 Hz",
        "frequencyRange": 500.0,
    }
    assert dataset["fft"]["lineCount"] == 2
    assert dataset["fft"]["amplitudeUnit"] == "mm/s"
    assert dataset["fft"]["frequencies"] == [250.0, 500.0]
    assert dataset["fft"]["amplitudes"] == pytest.approx([0.3, 0.4])

    fft_only = datasets["2"]
    assert fft_only["fft"]["frequencyRange"] == 1000.0
    assert fft_only["fft"]["frequencies"] == [250.0, 500.0, 750.0, 1000.0]


def test_fft_analysis_records_include_alert_type_or_strict_amplitude_threshold(tmp_path: Path) -> None:
    write_csv(
        tmp_path / "1.FFT_Test Pump_Point (V001).csv",
        FFT_COLUMNS,
        [
            fft_row("2026-01-01 00:00:00", [0.51], extraction_type="3"),
            fft_row("2026-01-05 00:00:00", [0.9], extraction_type="4"),
            fft_row("2026-01-06 00:00:00", [0.5], extraction_type="3"),
            fft_row("2026-01-07 00:00:00", [0.9], extraction_type="2"),
            fft_row("2026-01-08 00:00:00", [0.4], extraction_type="4"),
        ],
    )

    fft = load_datasets(tmp_path)["1"]["fft"]
    records = {record["id"]: record for record in fft["records"]}

    assert fft["recordId"] == 6
    assert fft["isAlertFft"] is True
    assert fft["alertRecordCount"] == 5
    assert records[2]["maxAmplitude"] == pytest.approx(0.51)
    assert records[2]["isAlertFft"] is True
    assert records[3]["isAlertFft"] is True
    assert records[4]["hasHighAmplitude"] is False
    assert records[4]["isAlertFft"] is True
    assert records[5]["hasHighAmplitude"] is True
    assert records[5]["isAlertFft"] is True
    assert records[6]["isAlertFft"] is True


def test_fft_default_selection_excludes_acceleration_all_records(tmp_path: Path) -> None:
    write_csv(
        tmp_path / "1.FFT_Test Pump_Point (V001).csv",
        FFT_COLUMNS,
        [
            fft_row("2026-01-03 00:00:00", [0.8], measure_mode="0"),
            fft_row("2026-01-02 00:00:00", [0.7], measure_mode="2"),
        ],
    )

    fft = load_datasets(tmp_path)["1"]["fft"]

    assert fft["recordId"] == 3
    assert fft["metadata"]["measureMode"]["code"] == "2"


def test_fft_supports_canonical_diag_header_all_modes_and_frequency_codes(tmp_path: Path) -> None:
    canonical_columns = ["DiagMode" if column == "DaiagMode" else column for column in FFT_COLUMNS]
    rows = []
    for measured_at, mode, frequency, extraction, diag in (
        ("2026-01-01 00:00:00", "0", "9", "3", "11"),
        ("2026-01-02 00:00:00", "2", "10", "4", "12"),
    ):
        row = fft_row(
            measured_at,
            [1.0, 2.0],
            measure_mode=mode,
            frequency_code=frequency,
            extraction_type=extraction,
            diag_mode=diag,
        )
        row["DiagMode"] = row.pop("DaiagMode")
        rows.append(row)
    write_csv(tmp_path / "1.FFT_Test Pump_Point (V001).csv", canonical_columns, rows)

    fft = load_datasets(tmp_path)["1"]["fft"]

    assert fft["measuredAt"] == "2026-01-02 00:00:00"
    assert fft["metadata"]["measureMode"] == {"code": "2", "label": "가속도ENV"}
    assert fft["metadata"]["measureFreq"]["frequencyRange"] == 20000.0
    assert fft["metadata"]["diagMode"] == {"code": "12", "label": "기어1"}
    assert fft["metadata"]["extractionType"] == {"code": "4", "label": "위험경보"}
    assert fft["amplitudeUnit"] == "g"
    assert fft["frequencies"] == [10000.0, 20000.0]
    assert fft["records"][1]["measureFreq"]["frequencyRange"] == 10000.0


def test_fft_unknown_metadata_codes_are_preserved(tmp_path: Path) -> None:
    write_csv(
        tmp_path / "1.FFT_Test Pump_Point (V001).csv",
        FFT_COLUMNS,
        [
            fft_row(
                "2026-01-01 00:00:00",
                [1.0, 2.0],
                measure_mode="99",
                frequency_code="99",
                extraction_type="99",
                diag_mode="99",
            )
        ],
    )

    fft = load_datasets(tmp_path)["1"]["fft"]

    assert fft["metadata"]["measureMode"] == {"code": "99", "label": "알 수 없음"}
    assert fft["metadata"]["measureFreq"] == {
        "code": "99",
        "label": "알 수 없음",
        "frequencyRange": None,
    }
    assert fft["metadata"]["extractionType"] == {"code": "99", "label": "알 수 없음"}
    assert fft["metadata"]["diagMode"] == {"code": "99", "label": "알 수 없음"}
    assert fft["frequencyUnit"] == "bin"
    assert fft["amplitudeUnit"] is None
    assert fft["frequencies"] == [1.0, 2.0]


def test_fft_analysis_groups_top_peaks_and_applies_velocity_threshold() -> None:
    analysis = analyze_fft_spectrum(
        [float(index) for index in range(12)],
        [10.0, 0.4, 0.7, 0.9, 0.8, 0.3, 0.6, 0.1, 0.2, 0.55, 0.54, 0.53],
        "3",
    )

    assert analysis["status"] == "analyzed"
    assert analysis["amplitudeThreshold"] == 0.5
    assert analysis["frequencyTolerance"] == 1.0
    assert analysis["peaks"][0]["frequency"] == 3.0
    assert analysis["peaks"][0]["amplitude"] == pytest.approx(0.9)
    assert analysis["peaks"][0]["groupFrequencies"] == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    assert all(peak["amplitude"] >= 0.5 for peak in analysis["peaks"])


def test_fft_analysis_reports_unknown_mode_and_no_significant_peak() -> None:
    assert analyze_fft_spectrum([0.0, 1.0], [0.0, 1.0], "99")["status"] == "unavailable"
    analysis = analyze_fft_spectrum([0.0, 10.0], [0.0, 0.19], "2")
    assert analysis["status"] == "no_significant_peak"
    assert analysis["peaks"] == []


def velocity_spectrum(one_x: float, two_x: float, three_x: float) -> tuple[list[float], list[float]]:
    frequencies = [float(index + 1) for index in range(500)]
    amplitudes = [0.0] * len(frequencies)
    amplitudes[29] = one_x
    amplitudes[58] = two_x
    amplitudes[88] = three_x
    return frequencies, amplitudes


@pytest.mark.parametrize(
    ("one_x", "two_x", "three_x", "diagnosis", "label"),
    [
        (1.0, 0.1, 0.05, "unbalance", "Unbalance"),
        (1.0, 0.5, 0.1, "misalignment", "Misalignment"),
        (1.0, 0.3, 0.2, "complex", "복합 또는 판정 불확실"),
    ],
)
def test_velocity_fft_diagnosis_uses_reference_harmonic_ratios(
    one_x: float, two_x: float, three_x: float, diagnosis: str, label: str
) -> None:
    frequencies, amplitudes = velocity_spectrum(one_x, two_x, three_x)

    analysis = analyze_velocity_fft(frequencies, amplitudes, 1780.0)

    assert analysis["status"] == "analyzed"
    assert analysis["diagnosis"] == diagnosis
    assert analysis["label"] == label
    assert analysis["shaftFrequency"] == pytest.approx(1780 / 60)
    assert [harmonic["detectedFrequency"] for harmonic in analysis["harmonics"]] == [30.0, 59.0, 89.0]
    assert analysis["ratios"]["twoToOne"] == pytest.approx(two_x / one_x)
    assert analysis["ratios"]["threeToOne"] == pytest.approx(three_x / one_x)


def test_velocity_fft_diagnosis_requires_rpm_and_sufficient_1x_peak() -> None:
    frequencies, amplitudes = velocity_spectrum(0.4, 0.5, 0.4)

    assert analyze_velocity_fft(frequencies, amplitudes, None)["status"] == "unavailable"
    analysis = analyze_velocity_fft(frequencies, amplitudes, 1780.0)
    assert analysis["status"] == "insufficient_1x"
    assert analysis["diagnosis"] == "inconclusive"


def test_acceleration_fft_diagnosis_reports_missing_bearing_metadata() -> None:
    analysis = analyze_fft_diagnosis([0.0, 1.0], [0.0, 1.0], "2", 1780.0)

    assert analysis["status"] == "unavailable"
    assert analysis["bearing"]["reason"] == "bearing_not_configured"


def test_acceleration_bearing_fft_selects_anomalous_fault_and_bpfo_when_normal() -> None:
    frequencies = [float(index) for index in range(400)]
    amplitudes = [0.0] * len(frequencies)
    # NSK 6318 at 1800 RPM: BPFI 1X is 147 Hz.  The 0.7 g peak is significant.
    amplitudes[147] = 0.7

    analysis = analyze_acceleration_bearing_fft(
        frequencies, amplitudes, 1800.0, {"maker": "NSK", "number": "6318"}
    )

    assert analysis["status"] == "analyzed"
    assert analysis["defaultFaultType"] == "BPFI"
    assert analysis["diagnosis"] == "bearing_inner_race"
    bpfi = next(fault for fault in analysis["faults"] if fault["type"] == "BPFI")
    assert bpfi["harmonics"][0]["targetFrequency"] == pytest.approx(147.0)
    assert bpfi["harmonics"][0]["detectedFrequency"] == 147.0
    assert bpfi["harmonics"][0]["significant"] is True

    normal = analyze_acceleration_bearing_fft(
        frequencies, [0.49] * len(frequencies), 1800.0, {"maker": "NSK", "number": "6318"}
    )
    assert normal["status"] == "no_anomaly"
    assert normal["defaultFaultType"] == "BPFO"
    assert normal["amplitudeThreshold"] == 0.5


def test_v032_uses_configured_rpm_for_velocity_fft(tmp_path: Path) -> None:
    frequencies, amplitudes = velocity_spectrum(1.0, 0.1, 0.05)
    write_csv(
        tmp_path / "1.FFT_Area_Test Pump_Point A (V032).csv",
        FFT_COLUMNS,
        [fft_row("2026-01-01 00:00:00", amplitudes)],
    )

    fft = load_datasets(tmp_path)["1"]["fft"]

    assert fft["analysis"]["diagnosis"]["rpm"] == 1780.0
    assert fft["analysis"]["diagnosis"]["rpmSource"] == "equipment_config"
    assert fft["analysis"]["diagnosis"]["diagnosis"] == "unbalance"


def test_velocity_fft_diagnosis_marks_record_as_alert_even_at_threshold(tmp_path: Path) -> None:
    frequencies, amplitudes = velocity_spectrum(0.5, 0.1, 0.05)
    write_csv(
        tmp_path / "1.FFT_Area_Test Pump_Point A (V032).csv",
        FFT_COLUMNS,
        [fft_row("2026-01-01 00:00:00", amplitudes)],
    )

    fft = load_datasets(tmp_path)["1"]["fft"]

    assert fft["analysis"]["diagnosis"]["status"] == "analyzed"
    assert fft["hasAnalysisAnomaly"] is True
    assert fft["isAlertFft"] is True
    assert fft["records"][0]["hasAnalysisAnomaly"] is True
    assert fft["records"][0]["isAlertFft"] is True
    assert fft["alertRecordCount"] == 1


def test_equipment_metadata_config_contains_presentation_values() -> None:
    configured_equipment = _load_equipment_metadata()

    assert configured_equipment["V191"] == {
        "plant": "1 냉연",
        "name": "1CAL_NO.1 DUST COLLECT FAN IMPELLER SIDE",
        "maker": "NSK",
        "sensorNumber": 191,
        "rpm": 1750.0,
        "bearing": "6315",
    }


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


def test_equipment_status_page_is_served(tmp_path: Path) -> None:
    response = get(create_app(make_data_dir(tmp_path)), "/")

    assert response.status_code == 200
    assert '<link rel="stylesheet" href="/static/equipment-status.css?v=topbar-layout-v3">' in response.text
    assert 'src="/static/equipment-status-demo/equipment-status-excel-data.js"' in response.text
    assert 'src="/static/equipment-status-demo/equipment-status-tree-data.js"' in response.text
    assert 'src="/static/modules/equipment-status/controller.js?v=factory-filter-v2"' in response.text
    assert "설비 현황" in response.text
    assert 'id="equipment-status-factory"' in response.text
    assert 'id="equipment-status-process"' in response.text
    assert 'id="equipment-status-type"' in response.text
    assert 'id="equipment-status-state"' in response.text
    assert 'id="equipment-status-name"' in response.text
    assert 'id="equipment-status-reset"' in response.text
    assert 'id="equipment-status-tree"' in response.text
    assert 'id="equipment-status-list"' in response.text


def test_equipment_status2_styles_are_not_nested(tmp_path: Path) -> None:
    response = get(create_app(make_data_dir(tmp_path)), "/equipment-status2")

    assert response.status_code == 200
    # Nested opening tags are treated as CSS text and can discard style rules.
    from html.parser import HTMLParser

    class StyleParser(HTMLParser):
        def handle_data(self, data: str) -> None:
            if self.cdata_elem == "style":
                assert "<style>" not in data

    StyleParser().feed(response.text)


def test_favicon_is_served(tmp_path: Path) -> None:
    response = get(create_app(make_data_dir(tmp_path)), "/favicon.ico")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/x-icon"
    assert response.content.startswith(b"\x00\x00\x01\x00")


def test_dashboard_page_is_served(tmp_path: Path) -> None:
    target_app = create_app(make_data_dir(tmp_path))
    response = get(target_app, "/dashboard")
    app_module = (Path(__file__).resolve().parents[1] / "app/static/app.js").read_text(
        encoding="utf-8"
    )

    assert response.status_code == 200
    assert 'type="module" src="/static/app.js?v=work-order-v8"' in response.text
    assert 'controller.js?v=work-order-v8' in app_module
    assert 'id="dataset-select"' in response.text
    assert 'class="dashboard-home-link" href="/"' in response.text
    assert 'class="equipment-overview"' in response.text
    assert 'id="plant-name"' in response.text
    assert 'id="line-name"' not in response.text
    assert 'id="sensor-number"' in response.text
    assert 'id="equipment-title"' in response.text
    assert 'class="overview-fft-result is-neutral"' in response.text
    assert 'id="overview-fft-result"' in response.text
    assert 'class="overview-status' not in response.text
    assert 'class="overview-metrics"' not in response.text
    assert "추세 그래프" in response.text
    assert "주파수 그래프" in response.text
    assert 'class="card chart-card fft-card"' not in response.text
    assert 'id="fft-chart"' not in response.text
    assert "선택 이력 주파수 분석" not in response.text
    assert response.text.count("<h2>주파수 그래프</h2>") == 1
    chart_grid = response.text[response.text.index('<section class="chart-grid"'):response.text.index('<dialog class="graph-modal"')]
    assert chart_grid.index("추세 그래프") < chart_grid.index("기준값 분석 결과")
    assert chart_grid.index("기준값 분석 결과") < chart_grid.index("우상향 판정")
    assert 'class="trend-analysis-column"' in chart_grid
    assert 'id="trend-direction-details" aria-live="polite" aria-busy="true"' in chart_grid
    assert 'class="card diagnosis-card"' not in chart_grid
    diagnosis = response.text[response.text.index('<article class="card diagnosis-card"'):response.text.index('<section class="related-history-section"')]
    assert 'id="fft-expand"' in diagnosis
    assert 'id="trend-expand"' in response.text
    assert 'id="fft-expand"' in response.text
    assert 'id="graph-modal"' in response.text
    assert 'id="graph-modal-chart"' in response.text
    assert 'id="fft-history-browser"' in response.text
    assert 'id="fft-history-list"' in response.text
    assert 'id="trend-metric-selector"' in response.text
    assert 'id="trend-metric-grid"' in response.text
    assert 'id="fft-record-list"' in response.text
    assert 'id="fft-metadata-grid"' in response.text
    assert 'id="fft-meta-measure-date"' in response.text
    assert "주파수 분석 결과" in response.text
    assert 'id="fft-analysis-workspace"' in response.text
    assert 'id="fft-analysis-details"' in response.text
    assert 'id="fft-analysis-result"' not in response.text
    assert 'id="fft-related-history"' in response.text
    assert 'id="fft-related-history-count"' in response.text
    assert 'id="fft-related-history-list"' in response.text
    assert '<h2 id="ai-analysis-title">AI 분석</h2>' in response.text
    assert 'id="ai-analysis-description"' in response.text
    assert 'id="ai-analysis-run"' in response.text
    assert 'id="ai-analysis-details"' not in response.text
    assert 'id="ai-analysis-reference"' not in response.text
    assert 'id="ai-analysis-details-title"' not in response.text
    assert 'id="chat-panel"' in response.text
    assert 'id="chat-open"' in response.text
    assert 'id="chat-form"' in response.text
    assert 'id="chat-messages"' in response.text
    equipment_card = response.text[
        response.text.index('<section class="equipment-overview"'):
        response.text.index('<section class="chart-grid"')
    ]
    assert equipment_card.index('id="overview-fft-measured-at"') < equipment_card.index('class="equipment-ai-diagnosis"')
    assert 'id="ai-analysis-details"' not in equipment_card
    assert 'class="card ai-analysis-card"' not in response.text
    assert 'id="fft-analysis-description"' not in response.text


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
    assert items[0]["plant"] == "Area"
    assert items[0]["line"] == "CSV Dataset #1"
    assert items[0]["status"] == "unknown"
    assert items[0]["statusLabel"] == "추세 판단 불가"
    assert items[0]["statusDescription"]
    assert items[0]["statusColor"] == "#94a3aa"
    assert items[0]["lastMeasuredAt"] == "2026-01-05 00:00:00"

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


def test_fft_record_api_returns_selected_spectrum_without_internal_fields(tmp_path: Path) -> None:
    target_app = create_app(make_data_dir(tmp_path))

    dashboard_response = get(target_app, "/api/dashboard/1")
    assert dashboard_response.status_code == 200
    fft = dashboard_response.json()["fft"]
    assert fft["recordId"] == 4
    assert "_sourcePath" not in fft
    assert len(fft["records"]) == 3
    assert all("amplitudes" not in record for record in fft["records"])

    record_response = get(target_app, "/api/dashboard/1/fft/2")
    assert record_response.status_code == 200
    record = record_response.json()
    assert record["recordId"] == 2
    assert record["measuredAt"] == "2026-01-03 00:00:00"
    assert record["metadata"]["measureMode"] == {"code": "2", "label": "가속도ENV"}
    assert record["amplitudeUnit"] == "g"
    assert record["frequencyRange"] == 500.0
    assert record["frequencies"] == [250.0, 500.0]
    assert record["amplitudes"] == pytest.approx([9.0, 9.0])
    assert record["timeWaveSamples"] == pytest.approx([-0.25, 0.5, 0.125])
    diagnosis = record["analysis"]["diagnosis"]
    assert diagnosis["status"] == "unavailable"
    assert diagnosis["diagnosis"] == "unavailable"
    assert diagnosis["rpmSource"] == "unavailable"
    assert "records" not in record

    assert get(target_app, "/api/dashboard/1/fft/999").status_code == 404
    assert get(target_app, "/api/dashboard/3/fft/2").status_code == 404
    assert get(target_app, "/api/dashboard/99/fft/2").status_code == 404


def test_malformed_time_wave_does_not_make_fft_record_unavailable() -> None:
    row = fft_row("2026-01-03 00:00:00", [0.1, 0.2])
    row["TimeWaveSampling"] = "not a bytes literal"

    record = _build_fft_record(row, 2)

    assert record["amplitudes"] == pytest.approx([0.1, 0.2])
    assert record["timeWaveSamples"] is None


def test_fft_record_can_be_loaded_after_its_source_file_is_removed(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    fft = load_datasets(data_dir)["1"]["fft"]
    (data_dir / "1.FFT_Area_Test Pump_Point A (V001).csv").unlink()

    record = load_fft_record(fft, 2)

    assert record["recordId"] == 2
    assert record["amplitudes"] == pytest.approx([9.0, 9.0])


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


def test_ai_analysis_api_uses_equipment_scope_and_compact_context(tmp_path: Path) -> None:
    gateway = FakeAiGateway()
    response = post(
        create_app(make_data_dir(tmp_path), ai_gateway=gateway, ai_cache_dir=tmp_path / "cache"),
        "/api/dashboard/1/ai-analysis",
        {"recordId": 2},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["cached"] is False
    assert response.json()["analysis"]["riskLevel"] == "caution"
    assert len(gateway.contexts) == 1
    context = gateway.contexts[0]
    assert context["equipmentAnalysis"] is True
    assert context["analysisTools"] == {
        "trend": "ready", "fft": "ready", "bearingFft": "not_applicable",
    }
    assert context["fft"]["recordId"] == 4
    assert context["fft"]["measurement"]["measureMode"]["code"] == "3"
    assert context["fftInventory"]["count"] == 3
    trend_metrics = {metric["key"]: metric for metric in context["trend"]["metrics"]}
    assert trend_metrics["velocity"]["latestValue"] == 2.0
    assert "frequencies" not in context["fft"]
    assert "amplitudes" not in context["fft"]

    missing_record = post(
        create_app(make_data_dir(tmp_path), ai_gateway=gateway, ai_cache_dir=tmp_path / "cache"),
        "/api/dashboard/1/ai-analysis",
        {"recordId": 999},
    )
    assert missing_record.status_code == 404


def test_ai_analysis_api_reports_missing_openai_key(tmp_path: Path) -> None:
    gateway = OpenAIAnalysisGateway(
        OpenAISettings(api_key=None, model="test-model", timeout_seconds=1.0)
    )
    response = post(
        create_app(make_data_dir(tmp_path), ai_gateway=gateway, ai_cache_dir=tmp_path / "cache"),
        "/api/dashboard/1/ai-analysis",
        {"recordId": 2},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "missing_api_key",
        "message": "OPENAI_API_KEY가 설정되지 않아 AI 분석을 실행할 수 없습니다.",
    }


def test_dashboard_chat_uses_selected_tool_and_returns_structured_result(tmp_path: Path) -> None:
    gateway = FakeChatGateway()
    response = post(
        create_app(make_data_dir(tmp_path), chat_gateway=gateway),
        "/api/dashboard/1/chat",
        {
            "recordId": 2,
            "selectedFaultType": "Unbalance",
            "until": "2026-01-04",
            "message": "무엇을 먼저 확인하나요?",
            "history": [{"role": "user", "content": "이전 질문"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"]["content"] == "선택한 측정 기록을 먼저 재확인해 주세요."
    assert payload["model"] != "deterministic-tool-template"
    assert payload["toolName"] == "trend"
    assert payload["toolArguments"]["end"] == "2026-01-04"
    assert payload["toolResult"]["status"] == "ready"
    assert payload["toolResult"]["trend"]["analysis"]["status"] == "insufficient_data"
    assert len(gateway.calls) == 1
    context, history, message = gateway.calls[0]
    assert context["toolName"] == "trend"
    assert context["toolResult"]["trend"]["summary"]["velocity"]["latestValue"] == 2.0
    assert history[0].content == "이전 질문"
    assert message == "무엇을 먼저 확인하나요?"


def test_dashboard_chat_rejects_unknown_record_and_excess_history(tmp_path: Path) -> None:
    target_app = create_app(make_data_dir(tmp_path), chat_gateway=FakeChatGateway())
    missing = post(target_app, "/api/dashboard/1/chat", {"recordId": 999, "message": "FFT record 999를 분석해줘"})
    excessive_history = post(
        target_app,
        "/api/dashboard/1/chat",
        {
            "recordId": 2,
            "message": "질문",
            "history": [{"role": "user", "content": "질문"}] * 13,
        },
    )

    assert missing.status_code == 200
    assert missing.json()["toolResult"] == {
        "status": "unavailable",
        "reason": "fft_record_not_found",
        "recordId": 999,
        "start": None,
        "end": None,
    }
    assert excessive_history.status_code == 422


def test_dashboard_chat_reports_missing_openai_key_for_model_tool_selection(tmp_path: Path) -> None:
    response = post(
        create_app(
            make_data_dir(tmp_path),
            chat_gateway=OpenAIDashboardChatGateway(
                OpenAISettings(api_key=None, model="test-model", timeout_seconds=1.0)
            ),
        ),
        "/api/dashboard/1/chat",
        {"recordId": 2, "message": "질문"},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "missing_api_key"


def test_ai_analysis_api_reuses_json_after_restart_and_forces_refresh(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AI_ANALYSIS_CACHE_TTL_SECONDS", "3600")
    gateway = FakeAiGateway()
    data_dir = make_data_dir(tmp_path)
    cache_dir = tmp_path / "cache"
    url = "/api/dashboard/1/ai-analysis"
    first = post(create_app(data_dir, ai_gateway=gateway, ai_cache_dir=cache_dir), url, {"recordId": 2})
    cached = post(create_app(data_dir, ai_gateway=gateway, ai_cache_dir=cache_dir), url, {"recordId": 2})
    assert first.status_code == cached.status_code == 200
    assert not first.json()["cached"] and cached.json()["cached"]
    assert first.json()["generatedAt"] == cached.json()["generatedAt"]
    assert len(gateway.contexts) == 1
    refreshed = post(create_app(data_dir, ai_gateway=gateway, ai_cache_dir=cache_dir), url, {"recordId": 2, "force": True})
    assert refreshed.status_code == 200 and not refreshed.json()["cached"]
    assert len(gateway.contexts) == 2
    stored = json.loads(next(cache_dir.glob("*.json")).read_text())
    assert datetime.fromisoformat(stored["expiresAt"]) - datetime.fromisoformat(stored["response"]["generatedAt"]) == timedelta(hours=1)


def test_ai_analysis_tool_execution_preserves_persistent_cache(tmp_path: Path) -> None:
    class ToolGateway(OpenAIAnalysisGateway):
        def __init__(self):
            super().__init__(OpenAISettings(api_key="test-key", model="test-model", timeout_seconds=1))
            self.fake = FakeAiGateway()
            self.evidence = []

        async def analyze(self, context, execute=None):
            assert execute is not None
            results = {}
            for name in ("get_trend_evidence", "get_fft_evidence", "get_related_history"):
                results[name] = await execute(name, {} if name == "get_trend_evidence" else {"record_id": None})
            assert results["get_trend_evidence"]["trend"] == context["trend"]
            assert results["get_fft_evidence"]["fft"]["recordId"] == context["fft"]["recordId"]
            assert results["get_related_history"]["relatedHistory"] == context["relatedHistory"]
            self.evidence.append(results)
            return await self.fake.analyze(context)

    gateway = ToolGateway()
    data_dir = make_data_dir(tmp_path)
    cache_dir = tmp_path / "tool-cache"
    url = "/api/dashboard/1/ai-analysis"
    first = post(create_app(data_dir, ai_gateway=gateway, ai_cache_dir=cache_dir), url, {"recordId": 2})
    assert first.status_code == 200 and not first.json()["cached"]
    assert len(gateway.evidence) == 1
    cached = post(create_app(data_dir, ai_gateway=gateway, ai_cache_dir=cache_dir), url, {"recordId": 2})
    assert cached.status_code == 200 and cached.json()["cached"]
    assert cached.json()["analysis"] == first.json()["analysis"]
    assert len(gateway.evidence) == 1
    refreshed = post(create_app(data_dir, ai_gateway=gateway, ai_cache_dir=cache_dir), url, {"recordId": 2, "force": True})
    assert refreshed.status_code == 200 and not refreshed.json()["cached"]
    assert len(gateway.evidence) == 2
    stored = json.loads(next(cache_dir.glob("*.json")).read_text())
    assert stored["response"]["analysis"] == refreshed.json()["analysis"]
