import asyncio
import json
import sys
import types
from copy import deepcopy
from datetime import datetime, timedelta

import pytest

from app.ai_analysis import AiAnalysisPeriod, OpenAIAnalysisGateway, OpenAISettings
from app.data_loader import load_datasets
from app.equipment_analysis import (
    build_equipment_context, build_equipment_tool_executor,
    normalize_equipment_period_timezone, recent_trend_evidence,
)
from app.main import create_app
from tests.test_ai_analysis import diagnosis
from tests.test_app import (
    FFT_COLUMNS, FakeAiGateway, fft_row, make_data_dir, post, write_csv,
)


def test_three_month_means_use_observations_and_mark_partial_months():
    data = {"trend": {"points": [
        {"timestamp": "2025-12-01 00:00:00", "value": 100},
        {"timestamp": "2026-01-20 00:00:00", "value": 3},
        {"timestamp": "2026-01-31 00:00:00", "value": 4},
        {"timestamp": "2026-02-01 00:00:00", "value": 4},
        {"timestamp": "2026-02-28 00:00:00", "value": 4},
        {"timestamp": "2026-03-01 00:00:00", "value": 4},
        {"timestamp": "2026-03-31 00:00:00", "value": 5},
        {"timestamp": "2026-03-30 00:00:00", "value": float("nan")},
    ], "metrics": [{"key": "velocity", "pointKey": "value", "unit": "mm/s"}]}}
    evidence = recent_trend_evidence(data)
    means = evidence["metrics"][0]["monthlyAverages"]
    assert [month["mean"] for month in means] == [3.5, 4, 4.5]
    assert [month["sampleCount"] for month in means] == [2, 2, 2]
    assert [month["partialMonth"] for month in means] == [True, False, False]
    assert evidence["period"]["start"] == "2026-01-20 00:00:00"
    assert evidence["analysis"]["status"] == "insufficient_data"
    assert recent_trend_evidence({})["available"] is False


def test_month_means_distinguish_isolated_spike_from_persistent_increase():
    data = {"trend": {"points": [
        {"timestamp": "2026-01-01 00:00:00", "value": 3},
        {"timestamp": "2026-02-01 00:00:00", "value": 3},
        {"timestamp": "2026-02-02 00:00:00", "value": 12},
        {"timestamp": "2026-03-01 00:00:00", "value": 3},
    ]}}
    means = recent_trend_evidence(data)["metrics"][0]["monthlyAverages"]
    assert [item["mean"] for item in means] == [3, 7.5, 3]


def history_dataset(tmp_path):
    make_data_dir(tmp_path)
    start = datetime(2026, 1, 1)
    rows = []
    for index in range(61):
        # MeasureFreq 6 spans 1000 Hz: 1000 bins give 1 Hz resolution.
        amplitudes = [0.01] * 1000
        amplitudes[29] = 1 + index * 0.02
        amplitudes[59] = 0.55
        amplitudes[89] = 0.35
        rows.append(fft_row((start + timedelta(days=index)).isoformat(sep=" "), amplitudes, frequency_code="6"))
    rows.append(fft_row("2026-02-10 12:00:00", [0.1] * 1000, measure_mode="2"))
    write_csv(tmp_path / "1.FFT_Area_Test Pump_Point A (V001).csv", FFT_COLUMNS, rows)
    dataset = load_datasets(tmp_path)["1"]
    dataset["fft"]["_rpm"] = 1800
    context = build_equipment_context("1", dataset, [], None)
    execute = build_equipment_tool_executor("1", dataset, [], None, context)
    return dataset, context, execute


def test_history_tool_paginates_chronologically_with_real_harmonics(tmp_path):
    _, _, execute = history_dataset(tmp_path)
    query = {"start": None, "end": None, "measure_mode": "3", "offset": 0}
    first = asyncio.run(execute("get_fft_history_evidence", query))
    second = asyncio.run(execute("get_fft_history_evidence", {**query, "offset": first["nextOffset"]}))
    assert first["totalCount"] == 61
    assert len(first["records"]) == 50 and len(second["records"]) == 11
    assert second["nextOffset"] is None
    assert first["records"][-1]["measuredAt"] < second["records"][0]["measuredAt"]
    one_x = first["records"][0]["fft"]["diagnosis"]["harmonics"][0]
    assert one_x["detectedFrequency"] == 30
    assert one_x["amplitude"] == pytest.approx(1)
    assert "frequencies" not in json.dumps(first) and "amplitudes" not in json.dumps(first)
    acceleration = asyncio.run(execute("get_fft_history_evidence", {**query, "measure_mode": "2"}))
    assert acceleration["totalCount"] == 1
    assert acceleration["records"][0]["fft"]["amplitudeUnit"] == "g"


@pytest.mark.parametrize("extra", [
    {"start": "invalid"}, {"start": "2026-03-01", "end": "2026-01-01"},
    {"offset": -1}, {"offset": True}, {"measure_mode": "99"},
    {"equipment_code": "V002"}, {"end": "2099-01-01"},
])
def test_history_tool_rejects_invalid_scope(tmp_path, extra):
    _, _, execute = history_dataset(tmp_path)
    result = asyncio.run(execute("get_fft_history_evidence", {
        "start": None, "end": None, "measure_mode": None, "offset": 0, **extra,
    }))
    assert result["status"] == "unavailable"


def test_source_fingerprint_covers_unqueried_fft_and_same_equipment_history(tmp_path):
    dataset, context, _ = history_dataset(tmp_path)
    changed = deepcopy(dataset)
    oldest = next(iter(changed["fft"]["_recordsById"].values()))
    oldest["ResultData"] = oldest["ResultData"] + " "
    assert build_equipment_context("1", changed, [], None)["sourceFingerprint"] != context["sourceFingerprint"]
    # Identity-based history matching also invalidates, even without datasetId.
    history = [{"sensorNumber": "001", "date": "2020-01-01", "analysis": "추가 이력"}]
    assert build_equipment_context("1", dataset, history, None)["sourceFingerprint"] != context["sourceFingerprint"]


def test_analysis_cache_is_equipment_scoped_and_optional_record_id(tmp_path):
    gateway = FakeAiGateway()
    data_dir = make_data_dir(tmp_path)
    app = create_app(data_dir, ai_gateway=gateway, ai_cache_dir=tmp_path / "cache")
    url = "/api/dashboard/1/ai-analysis"
    first = post(app, url, {})
    second = post(app, url, {"recordId": 2, "selectedFaultType": "BPFI"})
    assert first.status_code == second.status_code == 200
    assert second.json()["cached"] is True
    assert len(gateway.contexts) == 1
    trend_only = post(app, "/api/dashboard/3/ai-analysis", {})
    assert trend_only.status_code == 200
    assert gateway.contexts[-1]["fft"]["available"] is False


def test_equipment_gateway_allows_model_selected_extra_history_calls(monkeypatch):
    calls = []
    observed = []
    result = diagnosis().model_copy(update={
        "headline": "설비 측정 근거를 확인하고 재측정하세요.",
        "likely_causes": [],
        "fft_reference_record_ids": [1],
        "fft_analysis_period": AiAnalysisPeriod(start="2026-01-01T00:00:00", end="2026-01-01T00:00:00"),
    })
    query = {"start": None, "end": None, "measure_mode": "3", "offset": 0}
    batches = [
        [("get_fft_evidence", {"record_id": 1}),
         ("get_related_history", {"record_id": 1}), ("get_fft_history_evidence", query)],
        [("get_fft_history_evidence", {**query, "start": "2026-01-01"})],
    ]
    async def create(**params):
        index = len(calls)
        calls.append(params)
        tool_calls = [types.SimpleNamespace(id=f"call-{index}-{name}", type="function",
                      function=types.SimpleNamespace(name=name, arguments=json.dumps(arguments)))
                      for name, arguments in batches[index]] if index < len(batches) else None
        message = types.SimpleNamespace(tool_calls=tool_calls, refusal=None,
                                        content=None if tool_calls else result.model_dump_json())
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])
    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
        async def close(self):
            pass
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(AsyncOpenAI=FakeClient))
    fft = {"recordId": 1, "measuredAt": "2026-01-01 00:00:00", "amplitudeUnit": "mm/s"}
    async def execute(name, arguments):
        observed.append((name, arguments))
        return {"fft": fft} if name == "get_fft_evidence" else {"records": []}
    context = {"equipmentAnalysis": True, "equipment": {}, "fftInventory": {}, "scope": "설비",
               "trend": {"metrics": []}, "fft": fft}
    actual = asyncio.run(OpenAIAnalysisGateway(OpenAISettings(api_key="fake", model="test", timeout_seconds=1)).analyze(context, execute))
    assert actual == result
    assert calls[0]["tool_choice"] == calls[1]["tool_choice"] == "auto"
    assert observed[-1][1]["start"] == "2026-01-01"


def test_equipment_period_does_not_invent_timezone_missing_from_measurements():
    result = diagnosis().model_copy(update={
        "fft_analysis_period": AiAnalysisPeriod(start="2026-01-01T00:00:00Z", end="2026-01-02T00:00:00Z"),
    })
    trace = [{"name": "get_fft_evidence", "result": {"fft": {
        "recordId": 1, "measuredAt": "2026-01-01 00:00:00",
    }}}, {"name": "get_fft_history_evidence", "result": {"records": [{
        "recordId": 2, "measuredAt": "2026-01-02 00:00:00",
    }]}}]
    normalized = normalize_equipment_period_timezone(result, trace)
    assert normalized.fft_analysis_period.start.tzinfo is None
    assert normalized.fft_analysis_period.end.tzinfo is None


def test_equipment_period_uses_actual_observation_times():
    result = diagnosis().model_copy(update={
        "fft_analysis_period": AiAnalysisPeriod(start="2026-01-01T00:00:00Z", end="2026-01-02T00:00:00Z"),
    })
    trace = [{"name": "get_fft_history_evidence", "result": {"records": [
        {"recordId": 1, "measuredAt": "2026-01-01 09:15:00", "fft": {"recordId": 1, "measuredAt": "2026-01-01 09:15:00"}},
        {"recordId": 2, "measuredAt": "2026-01-02 10:30:00", "fft": {"recordId": 2, "measuredAt": "2026-01-02 10:30:00"}},
    ]}}]
    normalized = normalize_equipment_period_timezone(result, trace)
    assert normalized.fft_analysis_period.start.isoformat(sep=" ") == "2026-01-01 09:15:00"
    assert normalized.fft_analysis_period.end.isoformat(sep=" ") == "2026-01-02 10:30:00"
