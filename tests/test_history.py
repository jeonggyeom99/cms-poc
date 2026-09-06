import asyncio
import csv
from pathlib import Path

import httpx

from app.data_loader import HISTORY_COLUMNS, HISTORY_FILE_NAME, load_history
from app.main import create_app


REPOSITORY_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def get(target_app, path: str) -> httpx.Response:
    async def request() -> httpx.Response:
        async with target_app.router.lifespan_context(target_app):
            transport = httpx.ASGITransport(app=target_app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.get(path)

    return asyncio.run(request())


def history_row() -> list[str]:
    return [
        "13",
        "4",
        "22",
        "STS2연주",
        "- 테스트 설비 <V215>",
        "215",
        "- 속도값 상승",
        "- 1X 성분 우세",
        "- 질량 불평형",
        "- 밸런싱 후 정상화",
        "VelAve",
        "Trend test.csv",
        "속도",
        "FFT test.csv",
        "Vel",
        "WarningStatus",
        "",
        "1780",
        "6316",
    ]


def write_history(path: Path, rows: list[list[str]], columns=HISTORY_COLUMNS) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(columns)
        writer.writerows(rows)


def test_history_loader_normalizes_csv_fields(tmp_path: Path) -> None:
    write_history(tmp_path / HISTORY_FILE_NAME, [history_row()])

    payload = load_history(tmp_path)

    assert payload["source"] == HISTORY_FILE_NAME
    assert payload["total"] == 1
    assert payload["items"] == [
        {
            "id": "13",
            "number": 13,
            "date": "2026-04-22",
            "process": "STS2연주",
            "equipmentName": "테스트 설비 <V215>",
            "sensorNumber": "215",
            "issue": "속도값 상승",
            "analysis": "1X 성분 우세",
            "result": "질량 불평형",
            "feedback": "밸런싱 후 정상화",
            "trend": {"factor": "VelAve", "fileName": "Trend test.csv"},
            "fft": {"factor": "속도", "fileName": "FFT test.csv"},
            "primaryFactor": "Vel",
            "alarmHistory": "WarningStatus",
            "motorKw": None,
            "rpm": 1780,
            "bearingModel": "6316",
        }
    ]


def test_repository_history_csv_contains_original_and_added_records() -> None:
    payload = load_history(REPOSITORY_DATA_DIR)

    assert payload["total"] == 13
    assert [item["number"] for item in payload["items"][:3]] == [3, 6, 12]
    assert [item["number"] for item in payload["items"][3:]] == list(range(13, 23))


def test_history_page_and_equipment_status_link_are_served(tmp_path: Path) -> None:
    target_app = create_app(tmp_path)

    history_response = get(target_app, "/history")
    status_response = get(target_app, "/")

    assert history_response.status_code == 200
    assert 'href="/static/history.css?v=cms-history-v1"' in history_response.text
    assert 'src="/static/modules/history/controller.js?v=cms-history-v1"' in history_response.text
    assert 'id="history-keyword"' in history_response.text
    assert 'id="history-process"' in history_response.text
    assert 'id="history-reset"' in history_response.text
    assert 'id="history-list"' in history_response.text
    assert 'class="equipment-status-history-link" href="/history"' in status_response.text


def test_history_api_returns_csv_payload(tmp_path: Path) -> None:
    write_history(tmp_path / HISTORY_FILE_NAME, [history_row()])

    response = get(create_app(tmp_path), "/api/history")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["date"] == "2026-04-22"


def test_history_api_reports_missing_and_invalid_csv(tmp_path: Path) -> None:
    target_app = create_app(tmp_path)
    missing_response = get(target_app, "/api/history")

    write_history(tmp_path / HISTORY_FILE_NAME, [history_row()], columns=("NO", "월"))
    invalid_response = get(target_app, "/api/history")

    assert missing_response.status_code == 404
    assert missing_response.json()["detail"] == "CMS 이력 CSV를 찾을 수 없습니다."
    assert invalid_response.status_code == 422
    assert "19개 컬럼" in invalid_response.json()["detail"]
