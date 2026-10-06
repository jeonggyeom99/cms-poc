import asyncio
import json
import sys
import types
from datetime import date

import pytest

from app.agent_tools import build_dashboard_tool_executor
from app.chat import OpenAIDashboardChatGateway
from app.ai_analysis import OpenAISettings
from app.main import DATA_DIR
from app.data_loader import load_datasets, load_history
from app.services.analysis import bearing_fft_tool
from app.services.history import select_ai_related_history
from app.tool_calling import complete_with_tools


def test_dashboard_tool_executor_scopes_records_and_sanitizes_fft_arrays() -> None:
    datasets = load_datasets(DATA_DIR)
    history = load_history(DATA_DIR)["items"]
    execute = build_dashboard_tool_executor(datasets, "9", 4, history, None, None)
    arguments = {
        "equipment_code": None,
        "record_id": 4,
        "start": "2026-09-07",
        "end": "2026-09-07",
        "selected_fault_type": None,
    }

    result = asyncio.run(execute("get_fft", arguments))

    assert result["status"] == "ready"
    assert result["recordId"] == 4
    assert result["fft"]["diagnosis"]["diagnosis"] == "unbalance"
    assert "frequencies" not in json.dumps(result)
    assert "amplitudes" not in json.dumps(result)


def test_bearing_tool_rejects_velocity_fft() -> None:
    execute = build_dashboard_tool_executor(load_datasets(DATA_DIR), "9", 4, [], None, date(2026, 9, 7))
    arguments = {
        "equipment_code": "V056",
        "record_id": 4,
        "start": None,
        "end": None,
        "selected_fault_type": None,
    }

    result = asyncio.run(execute("get_bearing_fft", arguments))

    assert result == {
        "status": "unavailable",
        "reason": "bearing_analysis_requires_acceleration_fft",
        "recordId": 4,
        "measureMode": "3",
    }


def test_dashboard_tool_executor_keeps_selected_dataset_when_equipment_code_is_duplicated() -> None:
    datasets = load_datasets(DATA_DIR)
    execute = build_dashboard_tool_executor(datasets, "9", 4, [], None, date(2026, 9, 7))
    arguments = {
        "equipment_code": "V056",
        "record_id": 4,
        "start": None,
        "end": None,
        "selected_fault_type": None,
    }

    result = asyncio.run(execute("get_fft", arguments))

    assert result["status"] == "ready"
    assert result["recordId"] == 4
    assert result["measuredAt"].startswith("2026-09-07")
    assert result["fft"]["diagnosis"]["diagnosis"] == "unbalance"


def test_dashboard_tool_executor_rejects_unknown_equipment_and_invalid_ranges() -> None:
    execute = build_dashboard_tool_executor(load_datasets(DATA_DIR), "9", 4, [], None, None)
    base = {
        "equipment_code": "V999",
        "record_id": None,
        "start": None,
        "end": None,
        "selected_fault_type": None,
    }
    unknown = asyncio.run(execute("get_trend", base))
    invalid = asyncio.run(execute("get_trend", {**base, "equipment_code": None, "start": "2026-09-08", "end": "2026-09-07"}))

    assert unknown["reason"] == "dataset_not_found"
    assert invalid["reason"] == "invalid_tool_arguments"


def test_related_history_excludes_cutoff_day_and_future_records() -> None:
    dataset = load_datasets(DATA_DIR)["8"]
    record = bearing_fft_tool(dataset, 2, None, None)["record"]
    history = [
        {"id": str(index), "date": day, "sensorNumber": "191", "fault": "베어링", "faultType": "BPFI"}
        for index, day in enumerate(("2026-09-06", "2026-09-07", "2026-09-08"), start=1)
    ]

    result = select_ai_related_history(
        "8", record, history, "BPFI", date.fromisoformat("2026-09-07"), equipment=dataset["equipment"]
    )

    assert [item["date"] for item in result["items"]] == ["2026-09-06"]


def test_complete_with_tools_requires_named_evidence_before_final(monkeypatch) -> None:
    calls = []

    async def create(**kwargs):
        calls.append(kwargs)
        if kwargs["tool_choice"] == "required":
            tool_calls = [
                types.SimpleNamespace(
                    id=f"call-{len(calls)}-{name}", type="function",
                    function=types.SimpleNamespace(name=name, arguments="{}"),
                )
                for name in ("get_a", "get_b")
            ]
            message = types.SimpleNamespace(tool_calls=tool_calls, content=None, refusal=None)
        else:
            message = types.SimpleNamespace(tool_calls=None, content="done", refusal=None)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))
    results = []

    async def execute(name, arguments):
        results.append((name, arguments))
        return {"status": "ready"}

    content, trace = asyncio.run(complete_with_tools(
        client, "gpt-5.6-luna", [],
        [{"type": "function", "function": {"name": name}} for name in ("get_a", "get_b")], execute,
        required_tools={"get_a", "get_b"}, allow_additional_tools=False,
    ))

    assert content == "done"
    assert [item["name"] for item in trace] == ["get_a", "get_b"]
    assert len(calls) == 2
    assert calls[0]["tool_choice"] == "required"
    assert calls[-1]["tool_choice"] == "none"
    assert all(call["reasoning_effort"] == "none" for call in calls)
    assert all(call["parallel_tool_calls"] is False for call in calls)


def test_complete_with_tools_omits_reasoning_effort_for_legacy_models() -> None:
    calls = []

    async def create(**kwargs):
        calls.append(kwargs)
        message = types.SimpleNamespace(tool_calls=None, content="done", refusal=None)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))

    async def execute(name, arguments):
        return {"status": "ready"}

    content, _ = asyncio.run(complete_with_tools(
        client, "gpt-4o-mini", [], [], execute,
    ))

    assert content == "done"
    assert "reasoning_effort" not in calls[0]


def test_chat_gateway_calls_server_tool_and_returns_trace(monkeypatch) -> None:
    requests = []
    arguments = {
        "equipment_code": None,
        "record_id": 4,
        "start": "2026-09-07",
        "end": "2026-09-07",
        "selected_fault_type": None,
    }

    async def create(**kwargs):
        requests.append(kwargs)
        if len(requests) == 1:
            message = types.SimpleNamespace(
                refusal=None,
                content=None,
                tool_calls=[types.SimpleNamespace(
                    id="call-fft", type="function",
                    function=types.SimpleNamespace(name="get_fft", arguments=json.dumps(arguments)),
                )],
            )
        else:
            message = types.SimpleNamespace(
                refusal=None, tool_calls=None,
                content='{"answer":"속도 FFT에서 불평형 후보가 확인됩니다."}',
            )
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=create))

        async def close(self):
            pass

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI))
    gateway = OpenAIDashboardChatGateway(OpenAISettings("test-key", "test-model", 1))
    executed = []

    async def execute(name, call_arguments):
        executed.append((name, call_arguments))
        return {"status": "ready", "recordId": 4}

    answer, trace = asyncio.run(gateway.respond_with_tools(
        {"selectedEquipment": "V056", "selectedRecordId": 4}, [], "FFT 분석", execute
    ))

    assert answer == "속도 FFT에서 불평형 후보가 확인됩니다."
    assert executed == [("get_fft", arguments)]
    assert trace[0]["name"] == "get_fft"
    assert len(requests) == 2
    assert requests[0]["tool_choice"] == "required"
    assert requests[1]["tool_choice"] == "auto"
    assert any(item.get("role") == "tool" and item.get("tool_call_id") == "call-fft" for item in requests[1]["messages"] if isinstance(item, dict))
    assistant_turn = next(item for item in requests[1]["messages"] if not isinstance(item, dict))
    assert assistant_turn.tool_calls[0].id == "call-fft"
