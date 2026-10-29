from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

import pytest

from tests.ui.helpers import capture_page, open_page


pytestmark = pytest.mark.ui


def test_equipment_detail_keeps_dataset(cms_page):
    from playwright.sync_api import expect

    open_page(cms_page, "/equipment-status2")
    sensor = cms_page.locator("a.equipment-status-sensor").first
    href = sensor.get_attribute("href")
    expected = parse_qs(urlsplit(href).query)["dataset"][0]
    sensor.locator("xpath=ancestor::details").locator("summary").click()
    expect(sensor).to_be_visible()
    capture_page(cms_page, "navigation-expanded-equipment")
    with cms_page.expect_response(lambda response: urlsplit(response.url).path == f"/api/dashboard/{expected}") as fetched:
        sensor.click()
    cms_page.wait_for_url("**/dashboard2?*")
    expect(cms_page.locator("#dataset-select")).to_have_value(expected)
    assert parse_qs(urlsplit(cms_page.url).query) == {"dataset": [expected]}
    assert fetched.value.json()["meta"]["datasetId"] == expected
    target = capture_page(cms_page, "navigation-equipment-detail")
    target.with_suffix(".navigation.json").write_text(json.dumps({"href": href, "expectedDataset": expected, "destination": cms_page.url, "apiUrl": fetched.value.url}, indent=2), encoding="utf-8")


def test_history_detail_keeps_dataset_and_diagnosis_date(cms_page):
    from playwright.sync_api import expect

    open_page(cms_page, "/history2")
    payload = cms_page.request.get("/api/history").json()
    graph = cms_page.locator("button.history-graph-button:not([disabled])").first
    record_id = graph.get_attribute("data-history-id")
    record = next(item for item in payload["items"] if str(item["id"]) == record_id)
    dataset, until = str(record["datasetId"]), record["date"]
    assert graph.get_attribute("data-dashboard-dataset") == dataset
    graph.locator("xpath=ancestor::tr").locator(".history-detail-button").click()
    expect(cms_page.locator(f"#history-detail-{record_id}")).to_be_visible()
    capture_page(cms_page, "navigation-expanded-history")
    with cms_page.expect_response(lambda response: urlsplit(response.url).path == f"/api/dashboard/{dataset}") as fetched:
        graph.click()
    cms_page.wait_for_url("**/dashboard2?*")
    expect(cms_page.locator("#dataset-select")).to_have_value(dataset)
    expected = {"dataset": [dataset], "until": [until]}
    assert parse_qs(urlsplit(cms_page.url).query) == expected
    assert parse_qs(urlsplit(fetched.value.url).query)["until"] == [until]
    assert fetched.value.json()["meta"]["datasetId"] == dataset
    target = capture_page(cms_page, "navigation-history-detail")
    target.with_suffix(".navigation.json").write_text(json.dumps({"recordId": record_id, "expected": expected, "destination": cms_page.url, "apiUrl": fetched.value.url}, indent=2), encoding="utf-8")