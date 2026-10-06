import asyncio
import json
import sys
import types

import pytest

from app.ai_analysis import AiAnalysisPeriod, AiResponseError, OpenAIAnalysisGateway, OpenAISettings
from app.equipment_analysis import equipment_issue_codes, equipment_quality_issues, recent_trend_evidence
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


@pytest.mark.parametrize("bad_reply, stage", [
    (response('{"headline":"SECRET_MEASUREMENT"}'), "stage=schema"),
    (response('{"SECRET_FIELD_DATA":123}'), "stage=schema"),
    (response("truncated", finish="length"), "reason=response_truncated"),
    (response(), "reason=empty_response"),
    (response(equipment_result().model_copy(update={"fft_summary": "축정렬 불량이 확실합니다."}).model_dump_json()), "stage=evidence"),
])
def test_gateway_repairs_output_without_repeating_evidence_tools(monkeypatch, caplog, bad_reply, stage):
    requests = []
    replies = iter([
        response(calls=["get_trend_evidence", "get_fft_evidence", "get_related_history", "get_fft_history_evidence"]),
        bad_reply, response(equipment_result().model_dump_json()),
    ])

    async def create(**params):
        requests.append(params)
        return next(replies)

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = client(create).chat

        async def close(self):
            pass

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(AsyncOpenAI=FakeClient))
    context = {"equipmentAnalysis": True, "datasetId": "1", "equipment": {}, "fftInventory": {},
               "scope": "설비", "trend": {"metrics": []}, "fft": {}}
    gateway = OpenAIAnalysisGateway(OpenAISettings("fake", "test", 1))
    result = asyncio.run(gateway.analyze(context, execute))
    assert result == equipment_result()
    assert len(requests) == 3
    assert requests[-1]["tool_choice"] == "none"
    assert requests[-1]["max_completion_tokens"] == 4800
    assert stage in caplog.text
    assert "SECRET_MEASUREMENT" not in caplog.text
    assert "SECRET_FIELD_DATA" not in caplog.text


def test_schema_repairs_stop_after_three_outputs(monkeypatch):
    requests = []

    async def create(**params):
        requests.append(params)
        if len(requests) == 1:
            return response(calls=["get_trend_evidence", "get_fft_evidence", "get_related_history", "get_fft_history_evidence"])
        return response("{}")

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = client(create).chat

        async def close(self):
            pass

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(AsyncOpenAI=FakeClient))
    context = {"equipmentAnalysis": True, "equipment": {}, "fftInventory": {}, "scope": "설비", "fft": {}}
    with pytest.raises(AiResponseError, match="형식"):
        asyncio.run(OpenAIAnalysisGateway(OpenAISettings("fake", "test", 1)).analyze(context, execute))
    assert len(requests) == 4  # One evidence batch and three output attempts.


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


def test_equipment_cause_can_be_supported_by_a_nonrepresentative_record():
    result = equipment_result().model_copy(update={
        "headline": "내륜 결함 가능성이 있어 베어링을 점검하세요.",
        "fft_summary": "BPFI 1차 147 Hz에서 0.7 g가 관측됩니다.",
        "fft_analysis_period": AiAnalysisPeriod(start="2026-01-01", end="2026-01-02"),
        "fft_reference_record_ids": [1, 2],
    })
    context = {"trend": {"metrics": []}}
    assert equipment_quality_issues(context, result, mixed_trace()) == []
    unsupported = result.model_copy(update={"headline": "외륜 결함 가능성이 있어 점검하세요."})
    assert "unsupported_cause" in equipment_issue_codes(equipment_quality_issues(context, unsupported, mixed_trace()))
    wrong = result.model_copy(update={"fft_summary": "BPFI는 9.9 g입니다."})
    assert "unsupported_measurement" in equipment_issue_codes(equipment_quality_issues(context, wrong, mixed_trace()))
    bad_period = result.model_copy(update={"fft_analysis_period": AiAnalysisPeriod(start="2026-01-03", end="2026-01-04")})
    assert "observation_period" in equipment_issue_codes(equipment_quality_issues(context, bad_period, mixed_trace()))
    bad_units = result.model_copy(update={"fft_summary": "진폭은 1.2 mm/s에서 0.7 g로 증가했습니다."})
    assert "mixed_units" in equipment_issue_codes(equipment_quality_issues(context, bad_units, mixed_trace()))


@pytest.mark.parametrize("positive_text", [
    "외륜 피크는 미만이지만 결함이 의심됩니다.",
    "외륜 피크가 없지만 외륜 결함 가능성이 높습니다.",
    "외륜 피크가 확인되지 않지만 외륜 결함이 의심됩니다.",
])
def test_negative_fault_finding_does_not_claim_an_unsupported_cause(positive_text):
    result = equipment_result().model_copy(update={
        "fft_reference_record_ids": [1, 2],
        "fft_analysis_period": AiAnalysisPeriod(start="2026-01-01", end="2026-01-02"),
        "fft_summary": "외륜 결함 피크가 없어 확인되지 않습니다.",
    })
    context = {"trend": {"metrics": []}}
    assert equipment_quality_issues(context, result, mixed_trace()) == []
    positive = result.model_copy(update={"fft_summary": positive_text})
    assert "unsupported_cause" in equipment_issue_codes(equipment_quality_issues(context, positive, mixed_trace()))


def test_tool_provided_changes_are_valid_only_as_changes_not_readings():
    context = {"trend": {"metrics": [{"unit": "mm/s", "latestValue": 5.0,
                                      "change30Days": -1.2, "monthlyAverages": []}]}}
    result = equipment_result().model_copy(update={"trend_summary": "30일 변화량은 -1.2 mm/s입니다."})
    assert equipment_quality_issues(context, result, []) == []
    reading = result.model_copy(update={"trend_summary": "현재 측정값은 -1.2 mm/s입니다."})
    assert "unsupported_measurement:trendSummary" in equipment_issue_codes(equipment_quality_issues(context, reading, []))
    invented = result.model_copy(update={"trend_summary": "30일 변화량은 -9.9 mm/s입니다."})
    assert equipment_quality_issues(context, invented, [])
    decrease = result.model_copy(update={"trend_summary": "30일간 1.2 mm/s 감소했습니다."})
    assert equipment_quality_issues(context, decrease, []) == []
    relative = result.model_copy(update={"trend_summary": "30일 전 대비 -1.2 mm/s입니다."})
    assert equipment_quality_issues(context, relative, []) == []
    named_change = result.model_copy(update={"trend_summary": "change30Days는 -1.2 mm/s입니다."})
    assert equipment_quality_issues(context, named_change, []) == []


@pytest.mark.parametrize("peak_text", ["피크는 500 Hz에서 관측됩니다.",
                                      "측정 대역 내 500 Hz 피크가 관측됩니다.",
                                      "측정 범위는 500 Hz이고 피크도 500 Hz입니다."])
def test_fft_frequency_range_is_allowed_as_metadata_not_a_peak(peak_text):
    trace = mixed_trace()
    trace[0]["result"]["records"][0]["fft"]["frequencyRange"] = 500
    result = equipment_result().model_copy(update={
        "fft_reference_record_ids": [1, 2],
        "fft_analysis_period": AiAnalysisPeriod(start="2026-01-01", end="2026-01-02"),
        "fft_summary": "FFT 분해능 설정은 500 Hz이며 추가 점검이 필요합니다.",
    })
    context = {"trend": {"metrics": []}}
    assert equipment_quality_issues(context, result, trace) == []
    peak = result.model_copy(update={"fft_summary": peak_text})
    assert "unsupported_measurement" in equipment_issue_codes(equipment_quality_issues(context, peak, trace))


def test_monthly_changes_are_computed_from_observed_monthly_means():
    evidence = recent_trend_evidence({"trend": {"points": [
        {"timestamp": "2026-01-15 00:00:00", "value": 3},
        {"timestamp": "2026-02-15 00:00:00", "value": 5},
        {"timestamp": "2026-03-15 00:00:00", "value": 4},
    ]}})
    months = evidence["metrics"][0]["monthlyAverages"]
    assert [month["changeFromPreviousMonth"] for month in months] == [None, 2, -1]
    assert all(month["partialMonth"] for month in months)
