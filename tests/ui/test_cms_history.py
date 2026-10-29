from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

import pytest

from tests.ui.helpers import capture_page, open_page
from tests.ui.test_cms_control import DESKTOP_CASES, assert_layout


pytestmark = pytest.mark.ui


@pytest.mark.parametrize("cms_desktop_case", DESKTOP_CASES, indirect=True)
def test_history_filters_long_text_dates_and_detail_context(cms_page):
    from playwright.sync_api import expect

    page = cms_page
    payload = page.request.get("/api/history").json()
    record = next(item for item in payload["items"] if item["datasetId"])
    open_page(page, "/history2")
    expect(page.locator("#history-count")).to_have_text(f'{len(payload["items"])}건')
    assert_layout(page, "task6-history-normal")
    page.locator("#history-process").select_option(record["process"])
    page.locator("#history-keyword").fill(record["sensorNumber"])
    expected = [item for item in payload["items"] if item["process"] == record["process"] and record["sensorNumber"].lower() in " ".join(str(item.get(key, "")) for key in ["process", "equipmentName", "sensorNumber", "issue", "analysis", "result", "fault", "faultType", "feedback"]).lower()]
    expect(page.locator("#history-count")).to_have_text(f"{len(expected)}건")
    row = page.locator(f'tr.history-summary-row[data-history-id="{record["id"]}"]')
    expect(row.locator(".history-date")).to_have_text(record["date"].replace("-", "."))
    expect(row.locator(".history-diagnosis-tag strong")).to_have_text([record["fault"] or "—", record["faultType"] or "—"])
    row.locator(".history-detail-button").click()
    expect(row).to_have_attribute("aria-selected", "true")
    expect(page.locator(f'#history-detail-{record["id"]}')).to_contain_text(record["analysis"])
    capture_page(page, "task6-history-selected")
    graph = row.locator(".history-graph-button")
    dataset, until = str(record["datasetId"]), record["date"]
    with page.expect_response(lambda response: urlsplit(response.url).path == f"/api/dashboard/{dataset}") as fetched:
        graph.click()
    expect(page.locator("#dataset-select")).to_have_value(dataset)
    assert parse_qs(urlsplit(page.url).query) == {"dataset": [dataset], "until": [until]}
    assert parse_qs(urlsplit(fetched.value.url).query)["until"] == [until]
    target = capture_page(page, "task6-history-cutoff-destination")
    target.with_suffix(".navigation.json").write_text(json.dumps({"destination": page.url, "api": fetched.value.url, "record": record["id"]}), encoding="utf-8")
    long_record = {**record, "equipmentName": "긴 설비 이름 확인 " * 20, "analysis": "베어링 내륜 진단 근거와 점검 결과를 확인합니다. " * 80}
    page.route("**/api/history", lambda route: route.fulfill(json={"source": "UI local long history", "items": [long_record]}))
    open_page(page, f'/history2?dataset={dataset}&record={record["id"]}')
    expect(page.locator(".history-detail-card p").nth(1)).to_have_text(long_record["analysis"].strip())
    assert_layout(page, "task6-history-long")
    metrics = page.locator(".history-detail-card p").nth(1).evaluate("node => ({height: node.clientHeight, scroll: node.scrollHeight, size: getComputedStyle(node).fontSize})")
    assert metrics["height"] >= metrics["scroll"] - 1 and metrics["size"] == "14px", metrics
    page.locator("#history-keyword").fill("no matching record")
    expect(page.locator("#history-count")).to_have_text("0건")
    expect(page.locator(".history-detail-row")).to_have_count(0)
    capture_page(page, "task6-history-empty-filter")
    page.locator("#history-reset").click()
    expect(page.locator("#history-count")).to_have_text("1건")
    assert not urlsplit(page.url).query


@pytest.mark.parametrize("cms_desktop_case", DESKTOP_CASES, indirect=True)
def test_history_loading_empty_and_error(cms_page, cms_api_controls):
    from playwright.sync_api import expect

    page = cms_page
    gate = cms_api_controls.hold("/api/history")
    page.goto("/history2", wait_until="domcontentloaded")
    gate.wait_until_intercepted(page)
    expect(page.locator("#history-keyword")).to_be_disabled()
    expect(page.locator("#history-list")).to_have_attribute("aria-busy", "true")
    capture_page(page, "task6-history-loading")
    gate.release()
    expect(page.locator("#history-keyword")).to_be_enabled()
    cms_api_controls.empty_history()
    open_page(page, "/history2")
    expect(page.locator("#history-count")).to_have_text("0건")
    expect(page.locator("#history-list")).to_contain_text("조건에 맞는 이력이 없습니다")
    capture_page(page, "task6-history-empty")
    cms_api_controls.error("/api/history")
    open_page(page, "/history2")
    expect(page.locator("#history-notice")).to_contain_text("불러오지 못했습니다")
    expect(page.locator("#history-count")).to_have_text("조회 실패")
    expect(page.locator("#history-list")).not_to_contain_text("조건에 맞는 이력이 없습니다")
    capture_page(page, "task6-history-error")