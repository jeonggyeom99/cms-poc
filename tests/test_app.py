import asyncio

import httpx

from app.main import app


def get(path: str) -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path)

    return asyncio.run(request())


def test_dashboard_page_is_served() -> None:
    response = get("/")

    assert response.status_code == 200
    assert "V032" in response.text
    assert "Trend Graph" in response.text
    assert "FFT Graph" in response.text
    assert "Level 분석 결과" in response.text
    assert "진단 결과" in response.text


def test_dashboard_api_returns_mock_v032_payload() -> None:
    response = get("/api/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["mock"] is True
    assert payload["equipment"]["id"] == "V032"
    assert payload["equipment"]["status"] == "caution"
    assert payload["current"]["velocity"] == 4.76
    assert payload["trend"]["points"]
    assert payload["fft"]["frequencies"]
    assert len(payload["fft"]["frequencies"]) == len(payload["fft"]["amplitudes"])
    assert payload["levelAnalysis"]["metrics"]
    assert payload["diagnosis"]["recommendations"]
