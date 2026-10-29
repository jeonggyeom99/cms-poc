import asyncio
import json
import sys
import types

import pytest

from app.ai_analysis import AiAnalysisPeriod, AiResponseError, OpenAIAnalysisGateway, OpenAISettings
from app.equipment_analysis import recent_trend_evidence
from app.tool_calling import complete_with_tools
from tests.test_ai_analysis import diagnosis


def tool(name):
    return {"type": "function", "function": {"name": name}}


def response(content=None, calls=(), finish="stop", refusal=None):
    message = types.SimpleNamespace(content=content, tool_calls=[
        types.SimpleNamespace(id=f"call-{name}", type="function",
                              function=types.SimpleNamespace(name=name, arguments="{}"))
        for name in calls
    ], refusal=refusal)
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message, finish_reason=finish)])


def client(create):
    return types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))


async def execute(name, arguments):
    return {"records": []}


def test_required_tools_are_reserved_before_optional_calls_exhaust_budget():
    requests = []

    async def create(**params):
        requests.append(params)
        if params["tool_choice"] == "none":
            return response("done")
        name = "optional" if len(requests) == 1 else params["tools"][0]["function"]["name"]
        return response(calls=[name])

    content, trace = asyncio.run(complete_with_tools(
        client(create), "test", [], [tool(name) for name in ("a", "b", "optional")], execute,
        required_tools={"a", "b"}, max_tool_rounds=3, prioritize_required=True,
    ))
    assert content == "done"
    assert [item["name"] for item in trace] == ["optional", "a", "b"]
    assert [item["function"]["name"] for item in requests[1]["tools"]] == ["a", "b"]
    assert [item["function"]["name"] for item in requests[2]["tools"]] == ["b"]


@pytest.mark.parametrize("reply, options, reason", [
    (response("partial", finish="length"), {}, "response_truncated"),
    (response(refusal="SECRET"), {}, "refusal"),
    (response(), {}, "empty_response"),
    (response("premature"), {"required_tools": {"a"}}, "required_tools_missing"),
    (response(calls=["a"]), {"max_tool_calls": 0}, "tool_call_limit"),
    (response(), {"required_tools": {"a"}, "max_tool_rounds": 0}, "required_tool_round_limit"),
])
def test_tool_failures_have_distinct_safe_reasons(reply, options, reason):
    async def create(**params):
        return reply

    with pytest.raises(AiResponseError) as failure:
        asyncio.run(complete_with_tools(client(create), "test", [], [tool("a")], execute, **options))
    assert failure.value.reason == reason
    assert failure.value.code == "invalid_response"
    assert "SECRET" not in failure.value.message


def test_truncated_final_preserves_inspected_evidence():
    replies = iter([response(calls=["a"]), response("partial", finish="length")])

    async def create(**params):
        return next(replies)

    with pytest.raises(AiResponseError) as failure:
        asyncio.run(complete_with_tools(client(create), "test", [], [tool("a")], execute, required_tools={"a"}))
    assert failure.value.reason == "response_truncated"
    assert failure.value.trace[0]["name"] == "a"
    assert failure.value.diagnostics["phase"] == "final"
    assert failure.value.diagnostics["missing_required"] == []


def equipment_result():
    return diagnosis().model_copy(update={
        "headline": "조회한 측정 근거를 확인하고 추가 점검하세요.",
        "trend_findings": [], "fft_findings": [], "likely_causes": [],
    })


@pytest.mark.parametrize("equipment", [True, False])
@pytest.mark.parametrize("bad_reply, reason", [
    (response('{"headline":"SECRET_MEASUREMENT"}'), "schema_validation"),
    (response('{"SECRET_FIELD_DATA":123}'), "schema_validation"),
    (response("truncated", finish="length"), "response_truncated"),
    (response(), "empty_response"),
])
def test_gateway_output_failure_does_not_retry(monkeypatch, caplog, equipment, bad_reply, reason):
    requests, inspected, closed = [], [], []

    async def create(**params):
        requests.append(params)
        return (response(calls=["get_fft_evidence", "get_related_history", "get_fft_history_evidence"]
                         if equipment else ["get_trend_evidence", "get_fft_evidence", "get_related_history"])
                if len(requests) == 1 else bad_reply)

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = client(create).chat
        async def close(self):
            closed.append(True)

    async def inspect(name, arguments):
        inspected.append(name)
        return {"records": []}

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(AsyncOpenAI=FakeClient))
    context = {"equipmentAnalysis": equipment, "datasetId": "1", "equipment": {}, "fftInventory": {},
               "scope": "설비", "trend": {"metrics": []}, "fft": {}}
    with pytest.raises(AiResponseError) as failure:
        asyncio.run(OpenAIAnalysisGateway(OpenAISettings("fake", "test", 1)).analyze(context, inspect))
    assert failure.value.reason == reason
    assert len(requests) == 2
    assert len(inspected) == 3
    assert closed == [True]
    assert "SECRET_MEASUREMENT" not in caplog.text
    assert "SECRET_FIELD_DATA" not in caplog.text


@pytest.mark.parametrize("field,text", [
    ("headline", "2099-12-31 진동 9999 g로 지속 상승합니다."),
    ("fft_summary", "500 Hz 피크와 BPFO 외륜 결함이 확실합니다."),
    ("trend_summary", "현재 측정값은 -9.9 mm/s입니다."),
    ("risk_label", "진동 9999 g"),
    ("counter_evidence", "2099-12-31 측정값은 9999 g입니다."),
    ("likely_causes", "FTF 결함은 9999 g입니다."),
    ("recommended_actions", "9999 g 측정값으로 점검하세요."),
    ("history_findings", "조회하지 않은 설비의 2099-12-31 9999 g 사례입니다."),
    ("trend_findings", "측정값은 9999 g입니다."),
    ("fft_findings", "피크 9999 Hz입니다."),
])
def test_equipment_single_accepts_first_answer_without_evidence_repair(monkeypatch, field, text):
    from app.ai_analysis import AiFinding, AiLikelyCause, AiRecommendedAction
    requests, inspected = [], []
    expected = equipment_result().model_copy(update={
        "fft_reference_record_ids": [999],
        "fft_analysis_period": AiAnalysisPeriod(start="2099-01-01", end="2099-01-02"),
    })
    if field == "counter_evidence":
        value = [text]
    elif field == "likely_causes":
        value = [AiLikelyCause(cause=text, confidence="low", rationale="추가 점검")]
    elif field == "recommended_actions":
        value = [AiRecommendedAction(priority="high", action=text, rationale="추가 점검")]
    elif field.endswith("findings"):
        value = [AiFinding(heading="분석", detail=text)]
    else:
        value = text
    setattr(expected, field, value)

    async def create(**params):
        requests.append(params)
        return (response(calls=["get_fft_evidence", "get_related_history", "get_fft_history_evidence"])
                if len(requests) == 1 else response(expected.model_dump_json()))

    async def inspect(name, arguments):
        inspected.append(name)
        return {"records": []}

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = client(create).chat
        async def close(self):
            pass

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(AsyncOpenAI=FakeClient))
    context = {"equipmentAnalysis": True, "equipment": {}, "scope": "설비", "trend": {"metrics": []}}
    actual = asyncio.run(OpenAIAnalysisGateway(OpenAISettings("fake", "test", 1)).analyze(context, inspect))
    assert actual == expected
    assert inspected == ["get_fft_evidence", "get_related_history", "get_fft_history_evidence"]
    assert len(requests) == 2


def mixed_trace():
    velocity = {"recordId": 1, "measuredAt": "2026-01-01 00:00:00", "amplitudeUnit": "mm/s",
                "measurement": {"measureMode": {"code": "3"}},
                "diagnosis": {"status": "analyzed", "diagnosis": "unbalance",
                              "harmonics": [{"detectedFrequency": 20, "amplitude": 1.2}]}}
    bearing = {"recordId": 2, "measuredAt": "2026-01-02 00:00:00", "amplitudeUnit": "g",
               "measurement": {"measureMode": {"code": "2"}},
               "diagnosis": {"status": "analyzed", "faults": [{"type": "BPFI", "harmonics": [
                   {"significant": True, "detectedFrequency": 147, "amplitude": .7}]}]}}
    return [{"name": "get_fft_history_evidence", "result": {"records": [
        {"recordId": 1, "fft": velocity}, {"recordId": 2, "fft": bearing},
    ]}}]


def test_monthly_changes_are_computed_from_observed_monthly_means():
    evidence = recent_trend_evidence({"trend": {"points": [
        {"timestamp": "2026-01-15 00:00:00", "value": 3},
        {"timestamp": "2026-02-15 00:00:00", "value": 5},
        {"timestamp": "2026-03-15 00:00:00", "value": 4},
    ]}})
    months = evidence["metrics"][0]["monthlyAverages"]
    assert [month["changeFromPreviousMonth"] for month in months] == [None, 2, -1]
    assert all(month["partialMonth"] for month in months)
