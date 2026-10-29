import asyncio
from copy import deepcopy
import json
import sys
import types
from datetime import date, datetime, timedelta, timezone

from pydantic import BaseModel

from app.ai_analysis import (
    AiAnalysisPeriod,
    AiAnalysisService,
    AiDiagnosis,
    AiEvidenceError,
    AiFinding,
    AiLikelyCause,
    AiRecommendedAction,
    OpenAIAnalysisGateway,
    OpenAISettings,
    build_ai_context,
    analysis_cache_ttl_seconds,
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
        trend_summary="측정 기간의 추세를 확인했습니다.",
        fft_summary="주파수 측정 근거를 확인했습니다.",
        fft_analysis_period={"start": None, "end": None},
        fft_reference_record_ids=[],
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
        if kwargs.get("tool_choice") == "required":
            calls_for_tools = [
                types.SimpleNamespace(
                    id=f"call-{name}", type="function",
                    function=types.SimpleNamespace(name=name, arguments="{}"),
                )
                for name in ("get_trend_evidence", "get_fft_evidence", "get_related_history")
            ]
            message = types.SimpleNamespace(content=None, refusal=None, tool_calls=calls_for_tools)
        else:
            content = diagnosis().model_dump_json() if "tools" in kwargs else '{"headline":"ok"}'
            message = types.SimpleNamespace(content=content, refusal=None, tool_calls=None)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=message)]
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
        context = {
            "equipment": {"id": "V001"}, "fft": {"recordId": 1},
            "trend": {}, "levelAnalysis": {}, "relatedHistory": {},
            "dataQuality": {"notes": []}, "analysisTools": {"trend": "ready", "fft": "ready"},
        }
        await OpenAIAnalysisGateway(settings).analyze(context)
        await OpenAIReportGateway(settings).generate(
            "email-draft", "instructions", {}, SampleReport
        )

    asyncio.run(run())

    assert len(calls) == 3
    assert all("temperature" not in call for call in calls)
    analysis_instructions = calls[0]["messages"][0]["content"]
    assert "thresholdState" in analysis_instructions
    assert "detectedFrequency" in analysis_instructions
    assert "BPFI means" in analysis_instructions
    assert "NOT the shaft rotation's 1X" in analysis_instructions
    assert "counterEvidence" in analysis_instructions
    assert calls[0]["tool_choice"] == "required"
    assert {tool["function"]["name"] for tool in calls[0]["tools"]} == {
        "get_trend_evidence", "get_fft_evidence", "get_related_history"
    }


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


def test_single_accepts_first_schema_valid_answer_without_evidence_repair(monkeypatch) -> None:
    from tests.test_ai_reliability import client, response
    requests, inspected, closed = [], [], []
    expected = diagnosis().model_copy(update={
        "headline": "2099-12-31 진동은 9999 g로 상승했습니다.",
        "fft_reference_record_ids": [999],
    })

    async def create(**params):
        requests.append(params)
        return (response(calls=["get_trend_evidence", "get_fft_evidence", "get_related_history"])
                if len(requests) == 1 else response(expected.model_dump_json()))

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = client(create).chat
        async def close(self):
            closed.append(True)

    async def execute(name, arguments):
        inspected.append(name)
        return {"records": []}

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(AsyncOpenAI=FakeClient))
    result = asyncio.run(OpenAIAnalysisGateway(OpenAISettings("fake", "test", 1)).analyze(inner_race_context(), execute))
    assert result == expected
    assert inspected == ["get_trend_evidence", "get_fft_evidence", "get_related_history"]
    assert len(requests) == 2  # One evidence batch, one final answer.
    assert closed == [True]


@pytest.mark.parametrize("content", ['{"headline":', '{}', '{"SECRET_FIELD_DATA":123}'])
def test_single_malformed_json_does_not_retry(monkeypatch, caplog, content) -> None:
    from app.ai_analysis import AiResponseError
    from tests.test_ai_reliability import client, response
    requests, closed = [], []

    async def create(**params):
        requests.append(params)
        return (response(calls=["get_trend_evidence", "get_fft_evidence", "get_related_history"])
                if len(requests) == 1 else response(content))

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = client(create).chat
        async def close(self):
            closed.append(True)

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(AsyncOpenAI=FakeClient))
    with pytest.raises(AiResponseError) as failure:
        asyncio.run(OpenAIAnalysisGateway(OpenAISettings("fake", "test", 1)).analyze(inner_race_context()))
    assert failure.value.reason == "schema_validation"
    assert len(requests) == 2
    assert closed == [True]
    assert "SECRET_FIELD_DATA" not in caplog.text


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


def test_ai_context_corrects_bearing_summary_to_significant_harmonics() -> None:
    data_dir = Path(__file__).resolve().parents[1] / "data"
    dataset = load_datasets(data_dir)["8"]
    history = load_history(data_dir)["items"]
    record = next(item for item in dataset["fft"]["records"] if item["id"] == 2)

    context = build_ai_context("8", dataset, record, history, until=date(2026, 9, 7))
    diagnosis = context["fft"]["diagnosis"]
    bpfi = next(item for item in diagnosis["faults"] if item["type"] == "BPFI")

    assert [item["significant"] for item in bpfi["harmonics"]] == [True, True, False]
    assert diagnosis["message"] == "BPFI의 유의 고조파는 1, 2X입니다."


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


def test_service_does_not_fetch_model_only_fft_references() -> None:
    class ModelOnlyGateway(CountingGateway):
        async def analyze(self, context):
            return diagnosis().model_copy(update={'fft_reference_record_ids': [7, 999999]})

    calls = []
    async def execute(name, arguments):
        calls.append((name, arguments))
        return {'status': 'ready', 'fft': {'recordId': 999999, 'severityAssessments': []}}

    value = {'equipmentAnalysis': True, 'preparedFftEvidence': {'representativeRecords': [
        {'recordId': 7, 'severityAssessments': [{'recordId': 7, 'status': 'caution'}]}]}}
    result = asyncio.run(AiAnalysisService(ModelOnlyGateway(), 'test').analyze(value, execute=execute))
    assert calls == []
    assert result.fft_severity_assessments == [{'recordId': 7, 'status': 'caution'}]
    assert result.analysis.fft_reference_record_ids == [7, 999999]


@pytest.mark.parametrize('tool_name', ['get_fft_evidence', 'get_fft_history_evidence'])
def test_service_reuses_legitimate_tool_fft_assessments(monkeypatch, tool_name) -> None:
    from tests.test_prefetched_analysis import install_client, prepared_context
    from tests.test_ai_reliability import response
    requests = []; tool_calls = []
    grade = {'recordId': 3, 'status': 'danger', 'label': '정지'}

    async def create(**params):
        requests.append(params)
        if len(requests) == 1:
            return types.SimpleNamespace(choices=[types.SimpleNamespace(finish_reason='tool_calls',
                message=types.SimpleNamespace(content=None, refusal=None, tool_calls=[
                    types.SimpleNamespace(id='legitimate', type='function', function=types.SimpleNamespace(
                        name=tool_name, arguments=json.dumps({'record_id': 3} if tool_name == 'get_fft_evidence'
                        else {'start': None, 'end': None, 'measure_mode': None, 'offset': 0})))]))])
        return response(diagnosis().model_copy(update={'fft_reference_record_ids': [3, 999999]}).model_dump_json())

    async def execute(name, arguments):
        tool_calls.append((name, arguments))
        evidence = {'recordId': 3, 'measuredAt': '2026-01-03', 'severityAssessments': [grade]}
        if name == 'get_fft_evidence':
            return {'status': 'ready', 'fft': evidence}
        return {'status': 'ready', 'records': [{'recordId': 3, 'measuredAt': '2026-01-03', 'fft': evidence}]}

    install_client(monkeypatch, create)
    backend = OpenAIAnalysisGateway(OpenAISettings('fake', 'test', 1))
    result = asyncio.run(AiAnalysisService(backend, 'test').analyze(prepared_context(), execute=execute))
    assert len(requests) == 2 and len(tool_calls) == 1
    assert tool_calls[0][0] == tool_name
    assert result.fft_severity_assessments == [grade]
    assert result.analysis.fft_reference_record_ids == [3, 999999]


def test_cached_equipment_period_strips_timezone_without_changing_observation_times() -> None:
    class EquipmentGateway(CountingGateway):
        async def analyze(self, context: dict) -> AiDiagnosis:
            self.calls += 1
            return diagnosis().model_copy(update={
                "fft_analysis_period": AiAnalysisPeriod(start="2026-01-01T10:00:00Z", end="2026-01-02T11:00:00Z"),
            })

    async def run():
        service = AiAnalysisService(EquipmentGateway(), "test-model")
        context = {"fftInventory": {"start": "2026-01-01 09:00:00", "end": "2026-01-02 12:00:00"}}
        await service.analyze(context)
        cached = await service.analyze(context)
        return cached.analysis.fft_analysis_period

    period = asyncio.run(run())
    assert period.start.isoformat(sep=" ") == "2026-01-01 10:00:00"
    assert period.end.isoformat(sep=" ") == "2026-01-02 11:00:00"


@pytest.mark.parametrize("value,expected", [(None, 86400), ("", 86400), ("3600", 3600), ("0", 86400), ("-1", 86400), ("bad", 86400), ("1.5", 86400)])
def test_cache_ttl_configuration(value, expected) -> None:
    assert analysis_cache_ttl_seconds(value) == expected


def test_analysis_cache_persists_markdown_and_expires(tmp_path: Path) -> None:
    async def run() -> None:
        now = datetime(2026, 10, 2, tzinfo=timezone.utc)
        gateway = CountingGateway()
        context = {"promptVersion": "v1", "value": 1}
        service = AiAnalysisService(gateway, "test", cache_dir=tmp_path, clock=lambda: now)
        first = await service.analyze(context, dataset_id="1")
        path = next(tmp_path.glob("*.json"))
        stored = json.loads(path.read_text())
        assert stored["formatVersion"] == 1
        assert stored["response"]["analysis"] == first.analysis.model_dump(by_alias=True)
        assert datetime.fromisoformat(stored["expiresAt"]) - first.generated_at == timedelta(days=1)
        markdown = stored["markdown"]
        for text in (first.analysis.headline, "위험도: 주의", "완만한 상승", "1X Peak", "Unbalance", "현장 운전 조건", "체결 상태", "반복 측정"):
            assert text in markdown
        assert not list(tmp_path.glob("*.tmp"))

        now += timedelta(days=1, microseconds=-1)
        assert (await service.analyze(context, dataset_id="1")).cached
        restarted = AiAnalysisService(gateway, "test", cache_dir=tmp_path, clock=lambda: now)
        cached = await restarted.analyze(context, dataset_id="1")
        assert cached.cached and cached.generated_at == first.generated_at
        assert gateway.calls == 1
        now += timedelta(microseconds=1)
        assert not (await restarted.analyze(context, dataset_id="1")).cached
        assert gateway.calls == 2
        # A fresh service must also reject an expired file.
        now += timedelta(days=1)
        assert not (await AiAnalysisService(gateway, "test", cache_dir=tmp_path, clock=lambda: now).analyze(context, dataset_id="1")).cached
        assert gateway.calls == 3
        now += timedelta(seconds=1)
        forced = await restarted.analyze(context, force=True, dataset_id="1")
        assert not forced.cached and gateway.calls == 4
        final = await AiAnalysisService(gateway, "test", cache_dir=tmp_path, clock=lambda: now).analyze(context, dataset_id="1")
        assert final.cached and final.generated_at == forced.generated_at

    asyncio.run(run())


@pytest.mark.parametrize("change", ["context", "dataset", "model", "version"])
def test_analysis_cache_separates_inputs(tmp_path: Path, change: str) -> None:
    async def run() -> None:
        gateway = CountingGateway()
        context = {"value": 1, "promptVersion": "v1"}
        service = AiAnalysisService(gateway, "test", cache_dir=tmp_path)
        await service.analyze(context, dataset_id="1")
        if change == "context":
            context["value"] = 2
        elif change == "version":
            context["promptVersion"] = "v2"
        if change == "model":
            service = AiAnalysisService(gateway, "other", cache_dir=tmp_path)
        result = await service.analyze(context, dataset_id="2" if change == "dataset" else "1")
        assert not result.cached and gateway.calls == 2
        assert len(list(tmp_path.glob("*.json"))) == 2

    asyncio.run(run())


@pytest.mark.parametrize("damage", ["json", "version", "key", "naive_date", "response"])
def test_invalid_cache_is_regenerated(tmp_path: Path, damage: str) -> None:
    async def run() -> None:
        gateway = CountingGateway()
        await AiAnalysisService(gateway, "test", cache_dir=tmp_path).analyze({})
        path = next(tmp_path.glob("*.json"))
        payload = json.loads(path.read_text())
        if damage == "version":
            payload["formatVersion"] = 999
        elif damage == "key":
            payload["cacheKey"] = "wrong"
        elif damage == "naive_date":
            payload["expiresAt"] = "2099-01-01T00:00:00"
        elif damage == "response":
            payload["response"]["analysis"] = {}
        path.write_text("{broken" if damage == "json" else json.dumps(payload))
        assert not (await AiAnalysisService(gateway, "test", cache_dir=tmp_path).analyze({})).cached
        assert gateway.calls == 2
        assert json.loads(path.read_text())["formatVersion"] == 1

    asyncio.run(run())


def test_cache_save_failure_returns_result_and_keeps_memory(tmp_path: Path, caplog) -> None:
    async def run() -> None:
        blocked = tmp_path / "file"
        blocked.write_text("not a directory")
        gateway = CountingGateway()
        service = AiAnalysisService(gateway, "test", cache_dir=blocked)
        assert not (await service.analyze({})).cached
        assert (await service.analyze({})).cached
        assert gateway.calls == 1
        assert "Failed to persist AI analysis cache" in caplog.text

    asyncio.run(run())


def test_failed_analysis_preserves_cache_and_allows_retry(tmp_path: Path) -> None:
    class FailingGateway(CountingGateway):
        fail = False

        async def analyze(self, context):
            if self.fail:
                raise AiEvidenceError()
            return await super().analyze(context)

    async def run() -> None:
        now = datetime(2026, 10, 2, tzinfo=timezone.utc)
        gateway = FailingGateway()
        service = AiAnalysisService(gateway, "test", cache_dir=tmp_path, clock=lambda: now)
        await service.analyze({})
        path = next(tmp_path.glob("*.json"))
        original = path.read_bytes()
        gateway.fail = True
        with pytest.raises(AiEvidenceError):
            await service.analyze({}, force=True)
        assert path.read_bytes() == original
        assert (await service.analyze({})).cached
        now += timedelta(days=1)
        with pytest.raises(AiEvidenceError):
            await service.analyze({})
        assert path.read_bytes() == original
        gateway.fail = False
        assert not (await service.analyze({})).cached
        assert gateway.calls == 2

    asyncio.run(run())


def test_concurrent_analysis_and_force_share_one_call(tmp_path: Path) -> None:
    async def run() -> None:
        entered = asyncio.Event()
        release = asyncio.Event()

        class SlowGateway(CountingGateway):
            async def analyze(self, context):
                entered.set()
                await release.wait()
                return await super().analyze(context)

        gateway = SlowGateway()
        service = AiAnalysisService(gateway, "test", cache_dir=tmp_path)
        first = asyncio.create_task(service.analyze({}))
        await entered.wait()
        second = asyncio.create_task(service.analyze({}))
        forced = asyncio.create_task(service.analyze({}, force=True))
        await asyncio.sleep(0)
        release.set()
        results = await asyncio.gather(first, second, forced)
        assert gateway.calls == 1
        assert all(not result.cached for result in results)
        assert (await service.analyze({})).cached

    asyncio.run(run())


def test_atomic_replace_failure_preserves_file(tmp_path: Path, monkeypatch, caplog) -> None:
    async def run() -> None:
        gateway = CountingGateway()
        service = AiAnalysisService(gateway, "test", cache_dir=tmp_path)
        await service.analyze({})
        path = next(tmp_path.glob("*.json"))
        original = path.read_bytes()

        def failed_replace(self, target):
            raise OSError("simulated replacement failure")

        monkeypatch.setattr(Path, "replace", failed_replace)
        assert not (await service.analyze({}, force=True)).cached
        assert path.read_bytes() == original
        assert not list(tmp_path.glob("*.tmp"))
        assert (await service.analyze({})).cached
        assert gateway.calls == 2
        assert "Failed to persist AI analysis cache" in caplog.text

    asyncio.run(run())


def test_cancelled_caller_does_not_cancel_shared_analysis(tmp_path: Path) -> None:
    async def run() -> None:
        entered = asyncio.Event()
        release = asyncio.Event()

        class SlowGateway(CountingGateway):
            async def analyze(self, context):
                entered.set()
                await release.wait()
                return await super().analyze(context)

        gateway = SlowGateway()
        service = AiAnalysisService(gateway, "test", cache_dir=tmp_path)
        first = asyncio.create_task(service.analyze({}))
        await entered.wait()
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        second = asyncio.create_task(service.analyze({}))
        await asyncio.sleep(0)
        release.set()
        assert not (await second).cached
        assert gateway.calls == 1
        assert not service._in_flight
        assert (await service.analyze({})).cached

    asyncio.run(run())
