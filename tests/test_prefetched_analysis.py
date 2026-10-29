import asyncio
import json
import sys
import types

import pytest

from app.ai_analysis import AiAnalysisPeriod, OpenAIAnalysisGateway, OpenAISettings
from app.equipment_analysis import normalize_equipment_period_timezone
from app.equipment_evidence import prepare_fft_evidence
from tests.test_ai_reliability import client, equipment_result, mixed_trace, response
from tests.test_equipment_analysis import history_dataset


def prepared_context():
    records = [item["fft"] for call in mixed_trace() for item in call["result"].get("records", [])]
    return {"equipmentAnalysis": True, "equipment": {}, "scope": "설비",
            "trend": {"metrics": []}, "preparedFftEvidence": {
                "representativeRecords": records, "groups": [], "relatedHistory": []}}


def install_client(monkeypatch, create):
    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = client(create).chat

        async def close(self):
            pass
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(AsyncOpenAI=FakeClient))


def test_initial_evidence_finishes_in_one_request_without_tools(monkeypatch):
    requests = []
    result = equipment_result().model_copy(update={
        "fft_reference_record_ids": [1, 2],
        "fft_analysis_period": AiAnalysisPeriod(start="2026-01-01", end="2026-01-02"),
        "fft_summary": "1X 성분은 1.2 mm/s이며 불평형 가능성이 있습니다. 체결 상태를 점검하세요.",
    })

    async def create(**params):
        requests.append(params)
        return response(result.model_dump_json())

    async def execute(*args):
        pytest.fail("No additional query is needed for this evidence")

    install_client(monkeypatch, create)
    actual = asyncio.run(OpenAIAnalysisGateway(OpenAISettings("fake", "test", 1)).analyze(prepared_context(), execute))
    assert actual == result
    assert len(requests) == 1
    assert requests[0]["tool_choice"] == "auto"
    payload = json.loads(requests[0]["messages"][1]["content"])
    assert len(payload["fftEvidence"]["representativeRecords"]) == 2
    assert {tool["function"]["name"] for tool in requests[0]["tools"]} == {
        "get_fft_evidence", "get_fft_history_evidence", "get_related_history"}


def test_additional_queries_stop_after_two_rounds_and_keep_initial_evidence(monkeypatch):
    requests = []
    result = equipment_result().model_copy(update={
        "fft_reference_record_ids": [1, 3],
        "fft_analysis_period": AiAnalysisPeriod(start="2026-01-01", end="2026-01-03"),
    })

    async def create(**params):
        requests.append(params)
        return response(calls=["get_fft_evidence"]) if len(requests) <= 2 else response(result.model_dump_json())

    async def execute(name, arguments):
        return {"fft": {"recordId": 3, "measuredAt": "2026-01-03", "amplitudeUnit": "mm/s"}}

    install_client(monkeypatch, create)
    actual = asyncio.run(OpenAIAnalysisGateway(OpenAISettings("fake", "test", 1)).analyze(prepared_context(), execute))
    assert actual == result
    assert [request["tool_choice"] for request in requests] == ["auto", "auto", "none"]


def test_prefetched_malformed_json_does_not_retry(monkeypatch):
    from app.ai_analysis import AiResponseError
    requests, queries = [], []

    async def create(**params):
        requests.append(params)
        return response("{}")

    async def execute(*args):
        queries.append(args)

    install_client(monkeypatch, create)
    with pytest.raises(AiResponseError) as failure:
        asyncio.run(OpenAIAnalysisGateway(OpenAISettings("fake", "test", 1)).analyze(prepared_context(), execute))
    assert failure.value.reason == "schema_validation"
    assert len(requests) == 1 and not queries


def test_full_history_summary_preserves_midperiod_extrema_and_separates_modes(tmp_path):
    _, context, _ = history_dataset(tmp_path)
    prepared = context["preparedFftEvidence"]
    assert prepared["recordCount"] == prepared["inspectedCount"] == 62
    assert len(prepared["groups"]) == 2
    velocity = next(group for group in prepared["groups"] if group["measureMode"] == "3")
    assert velocity["recordCount"] == 61
    assert all(len(group["representativeRecordIds"]) <= 6 for group in prepared["groups"])
    january = next(month for month in velocity["monthlyComponents"] if month["month"] == "2026-01")
    assert january["components"]["shaft1X"]["maximum"]["amplitude"] == pytest.approx(1.6)
    assert january["components"]["shaft1X"]["maximum"]["measuredAt"].startswith("2026-01-31")
    assert velocity["firstAnomaly"]["measuredAt"].startswith("2026-01-01")
    serialized = json.dumps(prepared)
    assert '"amplitudes"' not in serialized and '"frequencies"' not in serialized
    references = {record["recordId"] for record in prepared["representativeRecords"]}
    assert {item["recordId"] for item in prepared["relatedHistory"]} == references


def test_measurement_conditions_create_distinct_groups_and_failed_records_are_reported(tmp_path, monkeypatch):
    from app import equipment_evidence
    dataset, _, _ = history_dataset(tmp_path)
    original = equipment_evidence.load_fft_record

    def load(fft, record_id):
        if record_id == 2:
            raise ValueError("corrupt record")
        result = original(fft, record_id)
        if record_id == 3:
            result["analysis"]["diagnosis"]["rpm"] = 1500
        return result

    monkeypatch.setattr(equipment_evidence, "load_fft_record", load)
    prepared = prepare_fft_evidence("1", dataset, [], None)
    assert prepared["unavailableRecordIds"] == [2]
    assert prepared["inspectedCount"] == 61
    assert len(prepared["groups"]) == 3


def test_prefetched_monthly_component_period_normalizes_timezone(tmp_path):
    _, context, _ = history_dataset(tmp_path)
    group = next(group for group in context["preparedFftEvidence"]["groups"] if group["measureMode"] == "3")
    sample = group["monthlyComponents"][0]["components"]["shaft1X"]["maximum"]
    refs = group["representativeRecordIds"]
    result = equipment_result().model_copy(update={
        "fft_reference_record_ids": refs,
        "fft_summary": f"월내 최대 1X 진폭은 {sample['amplitude']} mm/s입니다. " + ' '.join(context['weeklyExplanationFacts']),
        "fft_analysis_period": AiAnalysisPeriod(start=group["start"], end=group["end"]),
        "counter_evidence": ["베어링 모델 정보가 없습니다."],
    })
    normalized = normalize_equipment_period_timezone(result, [], context)
    assert normalized.fft_analysis_period.start.tzinfo is None
