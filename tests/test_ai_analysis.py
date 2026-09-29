import asyncio
from copy import deepcopy
import json
import sys
import types
from datetime import date

from pydantic import BaseModel

from app.ai_analysis import (
    AiAnalysisService,
    AiDiagnosis,
    AiFinding,
    AiLikelyCause,
    AiRecommendedAction,
    OpenAIAnalysisGateway,
    OpenAISettings,
    build_ai_context,
    diagnosis_quality_issues,
)
from app.analysis.fft import analyze_acceleration_bearing_fft
from app.reporting.ai import OpenAIReportGateway
from app.data_loader import load_datasets, load_history
from pathlib import Path
import pytest


def diagnosis() -> AiDiagnosis:
    return AiDiagnosis(
        headline="1X 성분을 재점검해야 합니다.",
        risk_level="caution",
        risk_label="주의",
        trend_findings=[AiFinding(heading="Trend", detail="완만한 상승입니다.")],
        fft_findings=[AiFinding(heading="FFT", detail="1X Peak가 우세합니다.")],
        history_findings=[],
        likely_causes=[
            AiLikelyCause(cause="Unbalance", confidence="medium", rationale="1X 성분이 있습니다.")
        ],
        counter_evidence=["현장 운전 조건이 없습니다."],
        recommended_actions=[
            AiRecommendedAction(
                priority="high",
                action="체결 상태를 확인합니다.",
                rationale="반복 측정이 필요합니다.",
            )
        ],
    )


def test_openai_gateways_omit_temperature_parameter(monkeypatch) -> None:
    calls: list[dict] = []

    async def create(**kwargs):
        calls.append(kwargs)
        content = diagnosis().model_dump_json()
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=content, refusal=None))]
        )

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs) -> None:
            self.chat = types.SimpleNamespace(
                completions=types.SimpleNamespace(create=create)
            )

        async def close(self) -> None:
            pass

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI))
    settings = OpenAISettings(api_key="test-key", model="gpt-5.6-luna", timeout_seconds=1)

    class SampleReport(BaseModel):
        headline: str

    async def run() -> None:
        await OpenAIAnalysisGateway(settings).analyze({"datasetId": "1"})
        await OpenAIReportGateway(settings).generate(
            "email-draft", "instructions", {}, SampleReport
        )

    asyncio.run(run())

    assert len(calls) == 2
    assert all("temperature" not in call for call in calls)
    analysis_instructions = calls[0]["messages"][0]["content"]
    assert "thresholdState" in analysis_instructions
    assert "detectedFrequency" in analysis_instructions
    assert "BPFI means" in analysis_instructions
    assert "NOT the shaft rotation's 1X" in analysis_instructions
    assert "counterEvidence" in analysis_instructions


def sample_dataset() -> dict:
    return {
        "equipment": {
            "id": "V001",
            "name": "Test Pump",
            "displayName": "Test Pump / DE",
            "plant": "Test Plant",
            "line": "Line A",
            "measurementPoint": "Motor DE",
            "rpm": 1800,
            "maker": "NSK",
            "bearing": "6318",
            "status": "caution",
            "lastMeasuredAt": "2026-01-15 00:00:00",
        },
        "trend": {
            "points": [
                {"timestamp": "2025-10-01 00:00:00", "value": 1.0, "acceleration": 0.1},
                {"timestamp": "2025-12-16 00:00:00", "value": 1.5, "acceleration": 0.2},
                {"timestamp": "2026-01-15 00:00:00", "value": 2.0, "acceleration": 0.3},
            ],
            "metrics": [
                {
                    "key": "velocity",
                    "pointKey": "value",
                    "label": "속도",
                    "unit": "mm/s",
                    "latestValue": 2.0,
                    "warningThreshold": 1.8,
                    "dangerThreshold": 3.0,
                }
            ],
            "analysis": {
                "status": "rising",
                "isRising": True,
                "slope": 0.01,
                "threshold": 0.003,
                "usedPoints": 143,
                "requiredPoints": 143,
            },
        },
        "levelAnalysis": {
            "status": "compared",
            "windowStart": "2025-10-15 00:00:00",
            "windowEnd": "2026-01-15 00:00:00",
            "usedPoints": 3,
            "normalMean": 1.2,
            "recommended": {"warningThreshold": 2.4, "dangerThreshold": 4.8},
            "configured": {"warningThreshold": 1.8, "dangerThreshold": 3.0},
            "difference": {"warningThreshold": -0.6, "dangerThreshold": -1.8},
        },
    }


def sample_fft() -> dict:
    return {
        "recordId": 7,
        "measuredAt": "2026-01-15 12:00:00",
        "frequencyUnit": "Hz",
        "amplitudeUnit": "mm/s",
        "frequencyRange": 500,
        "lineCount": 4,
        "maxAmplitude": 1.2,
        "hasAnalysisAnomaly": True,
        "isAlertFft": True,
        "frequencies": [125.0, 250.0, 375.0, 500.0],
        "amplitudes": [0.1, 1.2, 0.2, 0.1],
        "metadata": {
            "extractionType": {"code": "3", "label": "주의경보"},
            "diagMode": {"code": "1", "label": "기구부"},
            "measureMode": {"code": "3", "label": "속도"},
            "measureFreq": {"code": "5", "label": "500 Hz"},
        },
        "analysis": {
            "spectrum": {
                "status": "analyzed",
                "amplitudeThreshold": 0.5,
                "peaks": [{"frequency": 30.0, "amplitude": 1.2, "count": 1}],
            },
            "diagnosis": {
                "status": "analyzed",
                "diagnosis": "unbalance",
                "label": "Unbalance",
                "message": "1X 성분이 우세합니다.",
                "rpm": 1800,
                "rpmSource": "equipment_config",
                "shaftFrequency": 30.0,
                "defaultFaultType": None,
                "dominance": None,
                "ratios": {"twoToOne": 0.1, "threeToOne": 0.05},
                "harmonics": [
                    {
                        "order": 1,
                        "targetFrequency": 30.0,
                        "detectedFrequency": 30.0,
                        "amplitude": 1.2,
                        "detected": True,
                        "significant": True,
                    }
                ],
            },
        },
        "records": [
            {
                "id": 7,
                "measuredAt": "2026-01-15 12:00:00",
                "isAlertFft": True,
                "extractionType": {"code": "3", "label": "주의경보"},
                "measureMode": {"code": "3", "label": "속도"},
                "maxAmplitude": 1.2,
                "hasAnalysisAnomaly": True,
            }
        ],
        "alertRecordCount": 1,
    }


def history_item(record_id: str, record_date: str, dataset_id: str | None, fault_type: str) -> dict:
    return {
        "id": record_id,
        "number": int(record_id),
        "date": record_date,
        "datasetId": dataset_id,
        "equipmentName": f"History {record_id}",
        "sensorNumber": "001" if record_id == "2" else "999",
        "fault": "축",
        "faultType": fault_type,
        "issue": "진동 상승",
        "analysis": "1X 성분 확인",
        "result": "불평형 추정",
        "feedback": "밸런싱",
        "rpm": 1800,
        "bearingModel": "6318",
        "trend": {"factor": "VelAve"},
        "fft": {"factor": "1X"},
    }


def test_build_ai_context_summarizes_signals_and_excludes_future_history() -> None:
    context = build_ai_context(
        "1",
        sample_dataset(),
        sample_fft(),
        [
            history_item("1", "2026-01-10", "1", "Misalignment"),
            history_item("2", "2026-01-12", None, "Unbalance"),
            history_item("3", "2026-02-01", None, "Unbalance"),
        ],
        until=date(2026, 1, 20),
    )

    assert context["trend"]["analysis"]["status"] == "rising"
    assert context["trend"]["metrics"][0]["thresholdState"] == "caution"
    assert context["trend"]["metrics"][0]["change30Days"] == 0.5
    assert context["fft"]["diagnosis"]["diagnosis"] == "unbalance"
    assert context["relatedHistory"]["faultTag"] == {"fault": "축", "faultType": "Unbalance"}
    assert [item["recordNumber"] for item in context["relatedHistory"]["items"]] == [2]
    assert [item["relation"] for item in context["relatedHistory"]["items"]] == ["same_equipment"]
    compact_context = json.dumps(context)
    assert "frequencies" not in compact_context
    assert "amplitudes" not in compact_context
    assert "2026-02-01" not in compact_context


def inner_race_context() -> dict:
    fft = deepcopy(sample_fft())
    fft["metadata"]["measureMode"] = {"code": "2", "label": "가속도 ENV"}
    fft["amplitudeUnit"] = "g"
    fft["analysis"]["diagnosis"] = analyze_acceleration_bearing_fft(
        [30.0, 147.0],
        [0.1, 0.7],
        1800,
        {"maker": "NSK", "number": "6318"},
        {"available": True, "coefficients": {"BPFI": 4.9}},
    )

    return build_ai_context("1", sample_dataset(), fft, [])


def test_ai_context_exposes_inner_race_harmonic_separately_from_shaft_1x() -> None:
    context = inner_race_context()

    assert context["trend"]["analysis"]["status"] == "rising"
    assert context["trend"]["metrics"][0]["thresholdState"] == "caution"
    assert context["fft"]["measurement"]["measureMode"]["code"] == "2"
    assert context["fft"]["diagnosis"]["shaftFrequency"] == 30.0
    assert context["fft"]["diagnosis"]["diagnosis"] == "bearing_inner_race"
    bpfi = next(fault for fault in context["fft"]["diagnosis"]["faults"] if fault["type"] == "BPFI")
    assert bpfi["harmonics"][0] == {
        "order": 1,
        "targetFrequency": 147.0,
        "detectedFrequency": 147.0,
        "amplitude": 0.7,
        "detected": True,
        "significant": True,
    }


def test_ai_diagnosis_quality_requires_supported_insight_and_rejects_false_bearing_cause() -> None:
    expected = diagnosis().model_copy(update={
        "headline": (
            "속도 진동이 주의 구간에서 상승 중이며, 가속도 FFT의 BPFI 1X 결함주파수 "
            "147 Hz에서 0.7 g 피크가 확인됩니다. 베어링 내륜 결함 후보로 보고 재측정이 필요합니다."
        ),
        "likely_causes": [AiLikelyCause(cause="베어링 내륜 결함 후보", confidence="medium", rationale="BPFI 1X 147 Hz에서 0.7 g입니다.")],
        "fft_findings": [AiFinding(heading="BPFI", detail="BPFI 1X 결함주파수 147 Hz에서 0.7 g 피크가 확인됩니다.")],
    })
    bearing_context = inner_race_context()
    assert diagnosis_quality_issues(bearing_context, expected) == []
    assert diagnosis_quality_issues(bearing_context, diagnosis())
    verbose = expected.model_copy(update={"headline": expected.headline + " 추가 설명" * 30})
    assert any("140자" in issue for issue in diagnosis_quality_issues(bearing_context, verbose))
    keyword_only = expected.model_copy(update={
        "headline": "주의 상승 BPFI 147 0.7 가능성",
        "fft_findings": [AiFinding(heading="FFT", detail="피크가 있습니다.")],
        "likely_causes": [AiLikelyCause(cause="BPFI", confidence="medium", rationale="추가 검토가 필요합니다.")],
    })
    assert diagnosis_quality_issues(bearing_context, keyword_only)

    velocity_context = build_ai_context("1", sample_dataset(), sample_fft(), [])
    assert any("베어링" in issue for issue in diagnosis_quality_issues(velocity_context, expected))
    velocity_expected = diagnosis().model_copy(update={
        "headline": "속도 진동이 주의 구간에서 상승 중이며 속도 FFT의 1X 30 Hz 피크가 1.2 mm/s입니다. 불평형 후보로 보고 재측정이 필요합니다."
    })
    assert diagnosis_quality_issues(velocity_context, velocity_expected) == []
    assert diagnosis_quality_issues(velocity_context, diagnosis())

    unavailable = deepcopy(bearing_context)
    unavailable["fft"]["diagnosis"]["status"] = "unavailable"
    unsupported = expected.model_copy(update={"counter_evidence": ["베어링"]})
    assert any("counterEvidence" in issue for issue in diagnosis_quality_issues(unavailable, unsupported))


def test_ai_gateway_rewrites_generic_answer_once(monkeypatch) -> None:
    calls: list[dict] = []
    expected = diagnosis().model_copy(update={
        "headline": (
            "속도 진동이 주의 구간에서 상승 중이며, 가속도 FFT의 BPFI 1X 결함주파수 "
            "147 Hz에서 0.7 g 피크가 확인됩니다. 베어링 내륜 결함 후보로 보고 재측정이 필요합니다."
        ),
        "likely_causes": [AiLikelyCause(cause="베어링 내륜 결함 후보", confidence="medium", rationale="BPFI 1X 147 Hz에서 0.7 g입니다.")],
        "fft_findings": [AiFinding(heading="BPFI", detail="BPFI 1X 결함주파수 147 Hz에서 0.7 g 피크가 확인됩니다.")],
    })

    async def create(**kwargs):
        calls.append(kwargs)
        content = diagnosis().model_dump_json() if len(calls) == 1 else expected.model_dump_json()
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=content, refusal=None))]
        )

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs) -> None:
            self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=create))

        async def close(self) -> None:
            pass

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI))
    gateway = OpenAIAnalysisGateway(OpenAISettings(api_key="test-key", model="test-model", timeout_seconds=1))

    result = asyncio.run(gateway.analyze(inner_race_context()))

    assert result.headline == expected.headline
    assert len(calls) == 2
    assert len(calls[1]["messages"]) == 4
    assert "진단 근거 검사" in calls[1]["messages"][-1]["content"]


def test_repository_datasets_have_compact_ai_context_contract() -> None:
    data_dir = Path(__file__).resolve().parents[1] / "data"
    datasets, history = load_datasets(data_dir), load_history(data_dir)["items"]
    expected_limitations = {
        "2": "bearing_not_configured",
        "3": "bearing_not_found",
        "7": "bearing_not_configured",
        "9": "bearing_not_configured",
    }

    assert set(datasets) == {str(number) for number in range(1, 10)}
    for dataset_id, dataset in datasets.items():
        fft = dataset["fft"]
        context = build_ai_context(dataset_id, dataset, fft, history)
        raw_spectrum = fft["analysis"]
        assert context["fft"]["spectrum"]["status"] == raw_spectrum["status"]
        assert context["fft"]["spectrum"]["amplitudeThreshold"] == raw_spectrum["amplitudeThreshold"]
        assert len(context["fft"]["spectrum"]["peaks"]) == len(raw_spectrum["peaks"][:5])
        for summarized, raw_peak in zip(context["fft"]["spectrum"]["peaks"], raw_spectrum["peaks"][:5]):
            assert summarized["frequency"] == raw_peak["frequency"]
            assert summarized["amplitude"] == pytest.approx(raw_peak["amplitude"])
            assert summarized["count"] == raw_peak["count"]
        assert context["levelAnalysis"]["comparisonAvailable"] == (dataset["levelAnalysis"]["status"] == "compared")
        assert context["fft"]["diagnosticLimitation"] == (
            None if dataset_id not in expected_limitations else {
                "code": expected_limitations[dataset_id],
                "label": {
                    "bearing_not_configured": "베어링 모델 정보 누락",
                    "bearing_not_found": "베어링 계수 마스터 미등록 또는 불일치",
                }[expected_limitations[dataset_id]],
                "message": context["fft"]["diagnosis"]["message"],
            }
        )
        compact = json.dumps(context)
        assert "frequencies" not in compact and "amplitudes" not in compact


class CountingGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def analyze(self, context: dict) -> AiDiagnosis:
        self.calls += 1
        return diagnosis()


def test_ai_analysis_service_caches_and_refreshes_on_force() -> None:
    async def run() -> tuple[bool, bool, bool, int]:
        gateway = CountingGateway()
        service = AiAnalysisService(gateway, "test-model")
        context = build_ai_context("1", sample_dataset(), sample_fft(), [])
        first = await service.analyze(context)
        cached = await service.analyze(context)
        refreshed = await service.analyze(context, force=True)
        return first.cached, cached.cached, refreshed.cached, gateway.calls

    assert asyncio.run(run()) == (False, True, False, 2)
