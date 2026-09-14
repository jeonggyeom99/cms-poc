import asyncio
from datetime import date

import httpx
import pytest

from app.main import DATA_DIR, create_app
from app.services.analysis import bearing_fft_tool, fft_tool, trend_tool


async def request(app, method: str, path: str, payload: dict | None = None) -> httpx.Response:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, json=payload)


def call(app, method: str, path: str, payload: dict | None = None) -> httpx.Response:
    return asyncio.run(request(app, method, path, payload))


def test_v032_trend_ui_and_tool_share_the_same_range_snapshot() -> None:
    app = create_app(DATA_DIR)
    ui = call(app, "GET", "/api/dashboard/1?start=2026-02-01&until=2026-05-14").json()
    tool = trend_tool(app.state.datasets["1"], date(2026, 2, 1), date(2026, 5, 14))

    assert tool["status"] == "ready"
    assert tool["trend"]["points"] == ui["trend"]["points"]
    assert tool["trend"]["metrics"] == ui["trend"]["metrics"]
    assert tool["trend"]["analysis"] == ui["trend"]["analysis"]
    assert tool["trend"] == ui["trend"]["analysisResult"]
    assert tool["level"] == ui["levelAnalysis"]


def test_v056_velocity_fft_ui_and_tool_select_the_same_record() -> None:
    app = create_app(DATA_DIR)
    ui = call(app, "GET", "/api/dashboard/9/fft/4?start=2026-09-07&until=2026-09-07").json()
    tool = fft_tool(app.state.datasets["9"], 4, date(2026, 9, 7), date(2026, 9, 7))

    record = tool["record"]
    assert record["recordId"] == ui["recordId"] == 4
    assert record["measuredAt"] == ui["measuredAt"]
    assert record["metadata"]["measureMode"] == ui["metadata"]["measureMode"]
    assert record["analysis"]["diagnosis"] == ui["analysis"]["diagnosis"]
    assert record["analysis"] == ui["analysis"]
    assert record["analysis"]["diagnosis"]["rpm"] == pytest.approx(1170.0)
    assert record["analysis"]["diagnosis"]["diagnosis"] == "unbalance"


def test_v191_bearing_ui_and_tool_share_harmonic_and_sideband_evidence() -> None:
    app = create_app(DATA_DIR)
    ui = call(app, "GET", "/api/dashboard/8/fft/2?start=2026-09-07&until=2026-09-07").json()
    tool = bearing_fft_tool(app.state.datasets["8"], 2, date(2026, 9, 7), date(2026, 9, 7))

    diagnosis = tool["bearingAnalysis"]
    assert tool["record"] == ui
    assert diagnosis == ui["analysis"]["diagnosis"]
    assert diagnosis["bearing"]["maker"] == "NSK"
    assert diagnosis["bearing"]["number"] == "6315"
    assert diagnosis["diagnosis"] == "bearing_inner_race"
    assert any(fault["sidebandEvidence"] for fault in diagnosis["faults"])


def test_chat_routes_date_bound_questions_to_tools_without_fabricating_data() -> None:
    app = create_app(DATA_DIR)
    trend = call(app, "POST", "/api/dashboard/1/chat", {
        "recordId": 2,
        "message": "V032의 2026년 6월 1일부터 9월 1일까지 Trend를 분석해줘",
    }).json()
    fft = call(app, "POST", "/api/dashboard/9/chat", {
        "recordId": 4,
        "message": "이 설비의 2026-09-07 FFT를 분석해줘",
    }).json()
    bearing = call(app, "POST", "/api/dashboard/8/chat", {
        "recordId": 2,
        "message": "이 설비의 베어링 결함을 확인해줘",
    }).json()

    assert trend["toolName"] == "trend"
    assert trend["toolArguments"]["start"] == "2026-06-01"
    assert trend["toolArguments"]["end"] == "2026-09-01"
    assert trend["toolResult"]["reason"] == "no_trend_data_in_range"
    assert fft["toolName"] == "fft"
    assert fft["toolResult"]["record"]["recordId"] == 4
    assert fft["toolResult"]["record"]["measuredAt"].startswith("2026-09-07")
    assert bearing["toolName"] == "bearing_fft"
    assert bearing["toolResult"]["bearingAnalysis"]["diagnosis"] == "bearing_inner_race"
