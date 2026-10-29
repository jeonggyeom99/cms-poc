from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

import pytest

from tests.ui.helpers import capture_page, open_page, text_metrics


pytestmark = pytest.mark.ui
DESKTOP_CASES = [(1280, 800, 1), (1440, 900, 1), (1920, 1080, 1), (1440, 900, 1.25)]
LONG_NAME = "제1냉연공장 연속소둔라인 집진설비 주전동기 구동측 베어링 진동 측정 설비 " * 4
LONG_SUMMARY = "최근 측정 근거와 과거 이력을 함께 확인해야 합니다. 진동 속도 12.345 mm/s와 주파수 123.456 Hz를 생략하지 않습니다. " * 24


def assert_unclipped(locator):
    assert locator.evaluate("""element => {
      const style = getComputedStyle(element);
      const range = document.createRange();
      range.selectNodeContents(element);
      const text = range.getBoundingClientRect();
      const box = element.getBoundingClientRect();
      return element.scrollWidth <= element.clientWidth + 1
        && text.bottom <= box.bottom + 1
        && !['hidden', 'clip'].includes(style.overflowY)
        && style.textOverflow !== 'ellipsis';
    }""")


@pytest.mark.parametrize("cms_desktop_case", DESKTOP_CASES, indirect=True)
@pytest.mark.parametrize("route", ["/dashboard2", "/dashboard"])
def test_metadata_alignment_and_long_equipment_name(cms_page, route):
    from playwright.sync_api import expect

    open_page(cms_page, f"{route}?dataset=1")
    expect(cms_page.locator("#ai-analysis-run")).to_be_enabled()
    expect(cms_page.locator(".equipment-metadata dt")).to_have_text(["공장", "센서번호"])
    expect(cms_page.locator("#equipment-title")).to_have_text("#2 Direct Cooling Pump DS")
    expect(cms_page.locator("#plant-name")).to_have_text("4 선재")
    expect(cms_page.locator("#sensor-number")).to_have_text("32")
    measured = []
    for equipment in [
        {"id": "1", "name": "NO.1 DUST COLLECT FAN", "plant": "1냉연", "sensorNumber": "V191"},
        {"id": "1", "name": LONG_NAME, "plant": "제1냉연공장 연속소둔라인 수처리 집진설비 " * 8,
         "sensorNumber": "구동측 진동 속도 센서 V191 장기 측정 위치 " * 8},
    ]:
        cms_page.evaluate("""async equipment => {
          const {populateSummary} = await import('/static/modules/summary/summary.js?v=korean-ui-v1');
          populateSummary({equipment});
        }""", equipment)
        expect(cms_page.locator("#equipment-title")).to_have_text(equipment["name"])
        expect(cms_page.locator("#plant-name")).to_have_text(equipment["plant"])
        expect(cms_page.locator("#sensor-number")).to_have_text(equipment["sensorNumber"])
        labels = [text_metrics(cms_page.locator(".equipment-metadata dt").nth(index)) for index in range(2)]
        values = [text_metrics(cms_page.locator(selector)) for selector in ("#plant-name", "#sensor-number")]
        assert all((metric["fontSize"], metric["lineHeight"]) == ("13px", "20px") for metric in labels)
        assert all((metric["fontSize"], metric["lineHeight"]) == ("14px", "22px") for metric in values)
        assert abs(labels[0]["rangeTop"] - labels[1]["rangeTop"]) <= 1
        assert abs(values[0]["rangeTop"] - values[1]["rangeTop"]) <= 1
        for selector in ("#equipment-title", "#plant-name", "#sensor-number"):
            assert_unclipped(cms_page.locator(selector))
        if equipment["name"] == LONG_NAME:
            assert values[0]["rangeBottom"] - values[0]["rangeTop"] > 22
        measured.append({"equipment":equipment, "labels":labels, "values":values})
    assert cms_page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    target = capture_page(cms_page, f"task5-metadata-long-{route.strip('/')}")
    target.with_suffix(".metrics.json").write_text(json.dumps(measured, ensure_ascii=False, indent=2), encoding="utf-8")


def test_detail_hierarchy_keeps_long_summary_and_actions(cms_page):
    from playwright.sync_api import expect

    open_page(cms_page, "/dashboard2?dataset=1")
    expect(cms_page.locator("#ai-analysis-run")).to_be_enabled()
    cms_page.locator("#ai-analysis-description").evaluate("(element, summary) => element.textContent = summary", LONG_SUMMARY)
    assert_unclipped(cms_page.locator("#ai-analysis-description"))
    actions = cms_page.locator(".ai-analysis-actions").bounding_box()
    summary = cms_page.locator("#ai-analysis-description").bounding_box()
    assert actions["y"] + actions["height"] <= summary["y"]
    expect(cms_page.locator("#diagnostic-ppt-export")).to_be_enabled()
    expect(cms_page.locator("#work-order-open")).to_be_enabled()
    capture_page(cms_page, "task5-hierarchy-long-summary")


@pytest.mark.parametrize("cms_desktop_case", DESKTOP_CASES, indirect=True)
def test_detail_chart_tracks_and_unframed_hierarchy(cms_page):
    from playwright.sync_api import expect

    open_page(cms_page, "/dashboard2?dataset=1")
    expect(cms_page.locator("#ai-analysis-run")).to_be_enabled()
    geometry = cms_page.evaluate("""() => {
      const style = getComputedStyle(document.querySelector('.equipment-overview'));
      const track = document.querySelector('.trend-card').getBoundingClientRect();
      const evidence = document.querySelector('.trend-analysis-column').getBoundingClientRect();
      return {radius: style.borderRadius, shadow: style.boxShadow,
        background: style.backgroundImage, track:track.width, evidence:evidence.width,
        chartHeight:document.querySelector('#trend-chart').getBoundingClientRect().height};
    }""")
    assert geometry["radius"] == "0px"
    assert geometry["shadow"] == "none"
    assert geometry["background"] == "none"
    assert geometry["track"] > geometry["evidence"]
    assert geometry["chartHeight"] >= 320
    expect(cms_page.locator("#ai-analysis-details")).to_have_count(0)
    target = capture_page(cms_page, "task5-detail-default")
    target.with_suffix(".tracks.json").write_text(json.dumps(geometry, indent=2), encoding="utf-8")


@pytest.mark.parametrize("cms_desktop_case", DESKTOP_CASES, indirect=True)
def test_detail_evidence_roles_and_complete_numeric_values(cms_page):
    from playwright.sync_api import expect

    open_page(cms_page, "/dashboard2?dataset=1")
    expect(cms_page.locator("#ai-analysis-run")).to_be_enabled()
    for selector in ("#ai-analysis-title", "#trend-ai-title", "#fft-ai-title", "#fft-related-history-title"):
        metrics = text_metrics(cms_page.locator(selector))
        assert (metrics["fontSize"], metrics["lineHeight"], metrics["fontWeight"]) == ("16px", "24px", "600")
    value = cms_page.locator(".fft-analysis-item strong").first
    value.evaluate("element => element.textContent = '1234567890.123456 mm/s'")
    assert text_metrics(value)["fontSize"] == "14px"
    assert_unclipped(value)
    assert cms_page.locator("#fft-related-history").evaluate("element => getComputedStyle(element).boxShadow") == "none"
    capture_page(cms_page, "task5-evidence-long-value")


def historical_record(page):
    items = page.request.get("/api/history").json()["items"]
    record = next(item for item in items if str(item.get("datasetId")) == "1")
    return str(record["datasetId"]), record["date"]


def select_other_fft(page, dataset, until, start):
    from playwright.sync_api import expect

    selected = page.locator('#fft-record-list [aria-pressed="true"]').get_attribute("data-fft-record-id")
    candidate = page.locator(f'#fft-record-list [data-fft-record-id]:not([data-fft-record-id="{selected}"])').first
    record_id = candidate.get_attribute("data-fft-record-id")
    with page.expect_response(lambda response: urlsplit(response.url).path == f"/api/dashboard/{dataset}/fft/{record_id}") as fetched:
        candidate.click()
    expect(page.locator(f'#fft-record-list [data-fft-record-id="{record_id}"]')).to_have_attribute("aria-pressed", "true")
    query = parse_qs(urlsplit(fetched.value.url).query)
    assert query == {"until": [until], "start": [start]}
    assert fetched.value.json()["recordId"] == int(record_id)
    expect(page.locator("#fft-meta-measure-date")).to_have_text(fetched.value.json()["metadata"]["measureDate"])
    return fetched.value.url, int(record_id)


@pytest.mark.parametrize("route", ["/dashboard2", "/dashboard"])
def test_historical_detail_keeps_cutoff_and_fft(cms_page, cms_side_effects, route):
    from playwright.sync_api import expect

    dataset, until = historical_record(cms_page)
    start = "2020-01-01"
    path = f"{route}?dataset={dataset}&until={until}&start={start}"
    with cms_page.expect_response(lambda response: urlsplit(response.url).path == f"/api/dashboard/{dataset}") as fetched:
        open_page(cms_page, path)
    expect(cms_page.locator("#ai-analysis-run")).to_be_enabled()
    assert parse_qs(urlsplit(fetched.value.url).query) == {"until": [until], "start": [start]}
    expect(cms_page.locator("#dataset-select")).to_have_value(dataset)
    expect(cms_page.locator("#dashboard-until")).to_have_text(f'{until.replace("-", ".")} 기준')
    fft_url, record_id = select_other_fft(cms_page, dataset, until, start)
    assert parse_qs(urlsplit(cms_page.url).query) == {"dataset": [dataset], "until": [until], "start": [start]}
    target = capture_page(cms_page, f"task5-historical-{route.strip('/')}")
    target.with_suffix(".navigation.json").write_text(json.dumps({"entry": path, "dashboard": fetched.value.url,
        "fft": fft_url, "recordId": record_id, "destination": cms_page.url}, indent=2), encoding="utf-8")
    cms_page.locator("#dataset-select-toggle").click()
    with cms_page.expect_response(lambda response: urlsplit(response.url).path == "/api/dashboard/2") as changed:
        cms_page.locator("#dataset-select").select_option("2")
    expect(cms_page.locator("#dashboard-until")).to_be_hidden()
    assert parse_qs(urlsplit(cms_page.url).query) == {"dataset": ["2"]}
    assert not urlsplit(changed.value.url).query


def test_ai_representative_fft_keeps_start(cms_page, cms_side_effects):
    from playwright.sync_api import expect

    dataset, until = historical_record(cms_page)
    start = "2020-01-01"
    payload = cms_page.request.get(f"/api/dashboard/{dataset}", params={"until": until, "start": start}).json()
    record_id = next(record["id"] for record in payload["fft"]["records"] if record["id"] != payload["fft"]["recordId"] and record["measureMode"]["code"] != "0")
    cms_side_effects.ai_record_id = record_id
    with cms_page.expect_response(lambda response: urlsplit(response.url).path == f"/api/dashboard/{dataset}/fft/{record_id}") as fetched:
        open_page(cms_page, f"/dashboard2?dataset={dataset}&until={until}&start={start}")
    expect(cms_page.locator("#diagnostic-ppt-export")).to_be_enabled()
    assert parse_qs(urlsplit(fetched.value.url).query) == {"until": [until], "start": [start]}


@pytest.mark.parametrize("demo_related", [False, True])
def test_related_history_link_keeps_its_date_contract(cms_page, demo_related):
    from playwright.sync_api import expect

    item = next(item for item in cms_page.request.get("/api/history").json()["items"] if str(item.get("datasetId")) == "1")
    item["demoRelated"] = demo_related
    item["equipmentName"] = LONG_NAME
    item["issue"] = LONG_SUMMARY
    if demo_related:
        item["datasetId"] = "2"
    open_page(cms_page, "/dashboard2?dataset=1&until=2026-10-29&start=2020-01-01")
    expect(cms_page.locator("#ai-analysis-run")).to_be_enabled()
    cms_page.evaluate("""async item => {
      const {renderRelatedHistory} = await import('/static/modules/fft/related-history.js?v=demo-datasets-v8');
      renderRelatedHistory({fault:item.fault,faultType:item.faultType}, [item]);
    }""", item)
    trigger = cms_page.locator(".related-history-card-trigger")
    trigger.click()
    expect(trigger).to_have_attribute("aria-expanded", "true")
    expect(cms_page.locator(".related-history-detail")).to_be_visible()
    for selector in (".related-history-equipment", ".related-history-detail-item p"):
        metrics = text_metrics(cms_page.locator(selector))
        assert (metrics["fontSize"], metrics["lineHeight"]) == ("14px", "22px")
        assert_unclipped(cms_page.locator(selector).first)
    capture_page(cms_page, f"task5-related-expanded-{demo_related}")
    with cms_page.expect_response(lambda response: urlsplit(response.url).path == f'/api/dashboard/{item["datasetId"]}') as fetched:
        cms_page.locator(".related-history-graph-button").click()
    cms_page.wait_for_load_state("networkidle")
    expected = {"dataset": [str(item["datasetId"])]}
    if not demo_related:
        expected["until"] = [item["date"]]
    assert parse_qs(urlsplit(cms_page.url).query) == expected
    assert parse_qs(urlsplit(fetched.value.url).query) == ({"until": [item["date"]]} if not demo_related else {})
    target = capture_page(cms_page, f"task5-related-destination-{demo_related}")
    target.with_suffix(".navigation.json").write_text(json.dumps({"expected": expected, "destination":cms_page.url,
        "apiUrl":fetched.value.url}, indent=2), encoding="utf-8")


@pytest.mark.parametrize("cms_desktop_case", DESKTOP_CASES, indirect=True)
def test_detail_actions_and_states(cms_page, cms_side_effects, tmp_path):
    from playwright.sync_api import expect
    from pptx import Presentation

    errors = []
    cms_page.on("pageerror", lambda error: errors.append(str(error)))
    open_page(cms_page, "/dashboard2?dataset=1&until=2026-10-29&start=2020-01-01")
    run = cms_page.locator("#ai-analysis-run")
    expect(run).to_be_enabled()
    cms_page.wait_for_function("() => ['trend-chart','fft-analysis-chart'].every(id => document.getElementById(id)?.data?.length)")
    fonts = cms_page.evaluate("() => ['trend-chart','fft-analysis-chart'].map(id => document.getElementById(id).layout.font.size)")
    assert fonts == [12, 12]
    for kind in ("trend", "fft"):
        cms_page.locator(f"#{kind}-expand").click()
        expect(cms_page.locator("#graph-modal")).to_be_visible()
        cms_page.wait_for_function("document.getElementById('graph-modal-chart').data?.length > 0")
        original_range = cms_page.evaluate("[...document.getElementById('graph-modal-chart')._fullLayout.xaxis.range]")
        drag_area = cms_page.locator("#graph-modal-chart .nsewdrag").first.bounding_box()
        cms_page.mouse.move(drag_area["x"] + drag_area["width"] * 0.2, drag_area["y"] + drag_area["height"] * 0.2)
        cms_page.mouse.down()
        cms_page.mouse.move(drag_area["x"] + drag_area["width"] * 0.7, drag_area["y"] + drag_area["height"] * 0.7, steps=8)
        cms_page.mouse.up()
        cms_page.wait_for_function("original => JSON.stringify(document.getElementById('graph-modal-chart')._fullLayout.xaxis.range) !== JSON.stringify(original)", arg=original_range)
        capture_page(cms_page, f"task5-{kind}-modal-zoom")
        cms_page.locator("#graph-modal-close").click()
        expect(cms_page.locator("#graph-modal")).to_be_hidden()
    select_other_fft(cms_page, "1", "2026-10-29", "2020-01-01")
    original_reference = cms_side_effects.responses["ai-analysis"]["analysis"]["fftReferenceRecordIds"][0]
    cms_side_effects.ai_mode = "held"
    cms_side_effects.ai_headline = LONG_SUMMARY
    cms_side_effects.ai_summary = LONG_SUMMARY
    chart_heights = cms_page.evaluate("() => ['trend-chart','fft-analysis-chart'].map(id => document.getElementById(id).getBoundingClientRect().height)")
    try:
        run.click()
        expect(run).to_be_disabled()
        expect(cms_page.locator("#trend-ai-summary")).to_have_attribute("aria-busy", "true")
        expect(cms_page.locator("#work-order-open")).to_be_in_viewport()
        expect(cms_page.locator("#chat-open")).to_be_visible()
        capture_page(cms_page, "task5-ai-delayed")
    finally:
        cms_side_effects.release_ai()
    expect(run).to_be_enabled()
    expect(cms_page.locator("#ai-analysis-description")).to_have_text(LONG_SUMMARY)
    assert_unclipped(cms_page.locator("#ai-analysis-description"))
    for selector in ("#trend-ai-summary", "#fft-ai-summary"):
        expect(cms_page.locator(selector)).to_have_text(LONG_SUMMARY)
        assert_unclipped(cms_page.locator(selector))
    assert chart_heights == cms_page.evaluate("() => ['trend-chart','fft-analysis-chart'].map(id => document.getElementById(id).getBoundingClientRect().height)")
    capture_page(cms_page, "task5-ai-long")
    cms_side_effects.ai_mode = "error"
    run.click()
    expect(run).to_have_text("다시 시도")
    expect(cms_page.locator("#ai-analysis-description")).to_contain_text("불러오지 못했습니다")
    expect(cms_page.locator("#work-order-open")).to_be_enabled()
    capture_page(cms_page, "task5-ai-error")
    cms_side_effects.ai_mode = "success"
    cms_side_effects.ai_headline = None
    cms_side_effects.ai_summary = None
    run.click()
    expect(cms_page.locator("#diagnostic-ppt-export")).to_be_enabled()
    with cms_page.expect_download() as downloaded:
        cms_page.locator("#diagnostic-ppt-export").click()
    target = tmp_path / "task5-local.pptx"
    downloaded.value.save_as(target)
    assert len(Presentation(target).slides) == 1
    artifact = capture_page(cms_page, "task5-ppt-success")
    downloaded.value.save_as(artifact.with_suffix(".pptx"))
    expect(cms_page.locator("#report-action-status")).to_have_attribute("data-state", "success")
    cms_page.evaluate("""() => {
      globalThis.cmsCopied = [];
      Object.defineProperty(navigator, 'clipboard', {configurable:true, value:{write:async items => {
        for (const item of items) cmsCopied.push({html:await (await item.getType('text/html')).text(),
          text:await (await item.getType('text/plain')).text()});
      }}});
    }""")
    cms_page.locator("#email-draft-open").click()
    expect(cms_page.locator("#email-draft-dialog")).to_be_visible()
    expect(cms_page.locator("#email-draft-preview img")).to_have_count(2)
    cms_page.wait_for_function("() => [...document.querySelectorAll('#email-draft-preview img')].every(image => image.complete && image.naturalWidth > 0)")
    cms_page.locator("#email-draft-copy").click()
    expect(cms_page.locator("#email-draft-status")).to_contain_text("클립보드에 복사했습니다")
    copied = cms_page.evaluate("cmsCopied")
    assert len(copied) == 1 and "UI baseline" in copied[0]["text"]
    assert "data:image/png;base64," in copied[0]["html"]
    capture_page(cms_page, "task5-email-copy-success")
    cms_page.evaluate("() => {navigator.clipboard.write = async () => {throw new DOMException('Denied','NotAllowedError')};}")
    cms_page.locator("#email-draft-copy").click()
    expect(cms_page.locator("#email-draft-status")).to_contain_text("거부")
    expect(cms_page.locator("#email-draft-preview img")).to_have_count(2)
    capture_page(cms_page, "task5-email-copy-denied")
    cms_page.evaluate("Object.defineProperty(navigator, 'clipboard', {configurable:true,value:undefined})")
    cms_page.locator("#email-draft-copy").click()
    expect(cms_page.locator("#email-draft-status")).to_contain_text("지원하지 않습니다")
    cms_page.locator("#email-draft-close").click()
    cms_page.locator("#chat-open").click()
    cms_page.locator("#chat-input").fill("현재 측정 근거를 설명해 주세요")
    cms_page.locator("#chat-send").click()
    expect(cms_page.locator("#chat-messages")).to_contain_text("UI baseline stub chat")
    capture_page(cms_page, "task5-chat")
    cms_page.locator("#chat-close").click()
    cms_page.locator("#work-order-open").click()
    expect(cms_page.locator('#work-order-form [name="설비"]')).not_to_have_value("")
    with cms_page.expect_download() as work_order:
        cms_page.locator("#work-order-issue").click()
    order_file = tmp_path / "task5-order.json"
    work_order.value.save_as(order_file)
    assert json.loads(order_file.read_text(encoding="utf-8"))["상태"] == "발행 완료 (데모)"
    capture_page(cms_page, "task5-work-order")
    cms_page.locator("#work-order-close").click()
    reports = [item for item in cms_side_effects.requests if item["endpoint"] in {"diagnostic-ppt", "email-draft"}]
    assert all(item["request"]["recordId"] == original_reference for item in reports)
    assert all(item["request"]["until"] == "2026-10-29" for item in reports)
    assert fonts == cms_page.evaluate("() => ['trend-chart','fft-analysis-chart'].map(id => document.getElementById(id).layout.font.size)")
    assert not errors