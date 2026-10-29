from __future__ import annotations

import re
import json

import pytest

from tests.ui.helpers import capture_page as capture_browser_page, open_page, text_metrics


pytestmark = pytest.mark.ui
DESKTOP_CASES = [(1280, 800, 1), (1440, 900, 1), (1920, 1080, 1), (1440, 900, 1.25)]
FAN = "NO.1 DUST COLLECT FAN"


def capture_page(page, name):
        page.evaluate("scrollTo(0, 0)")
        target = capture_browser_page(page, name)
        evidence = page.evaluate("""() => {
            const measure = selector => [...document.querySelectorAll(selector)].map(node => {
                const style = getComputedStyle(node); const box = node.getBoundingClientRect();
                return {size: style.fontSize, leading: style.lineHeight, weight: style.fontWeight,
                    height: box.height, width: box.width, scroll: node.scrollWidth};
            });
            return {scrollY, count: document.querySelector('[data-cms-result-count]').textContent,
                controls: measure('.equipment-status-search input, .equipment-status-search select, .equipment-status-search button'),
                rows: measure('.equipment-status-equipment__summary'),
                values: measure('.equipment-status-item__details strong, .equipment-status-sensor > span'),
                selection: [...document.querySelectorAll('main [aria-current="true"]')].map(node => node.textContent)};
        }""")
        target.with_suffix(".alarm.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        return target


def assert_count(page, expected=None):
    from playwright.sync_api import expect

    rows = page.locator("#equipment-status-list > details")
    if expected is not None:
        expect(rows).to_have_count(expected)
    count = page.locator("[data-cms-result-count]")
    expect(count).to_have_text(f"{rows.count()}개 설비")
    return rows


def select_fan_in_tree(page):
    tree = page.locator("#equipment-status-tree")
    for selector in (
        'summary[data-factory="1냉연"][data-process="all"]',
        'summary[data-factory="1냉연"][data-process="1CAL"][data-type="all"]',
        'summary[data-factory="1냉연"][data-process="1CAL"][data-type="FAN"]',
    ):
        branch = tree.locator(selector)
        if not branch.evaluate("node => node.parentElement.open"):
            branch.click()
    target = tree.get_by_role("button", name=FAN, exact=True)
    target.click()
    return target


@pytest.mark.parametrize("cms_desktop_case", DESKTOP_CASES, indirect=True)
def test_filters_tree_and_count_stay_in_sync(cms_page):
    from playwright.sync_api import expect

    page = cms_page
    open_page(page, "/equipment-status2")
    capture_page(page, "task4-reference-default")
    initial = assert_count(page).count()
    assert initial > 10
    page.locator("#equipment-status-factory").select_option(label="1냉연")
    factory_count = assert_count(page).count()
    assert 0 < factory_count < initial
    page.locator("#equipment-status-process").select_option(label="1CAL")
    page.locator("#equipment-status-type").select_option(label="FAN")
    page.locator("#equipment-status-name").fill(FAN)
    rows = assert_count(page, 1)
    expect(rows.locator("summary")).to_have_attribute("aria-current", "true")
    for state, label in (("attention", "주의"), ("normal", "정상")):
        page.locator("#equipment-status-state").select_option(state)
        rows = assert_count(page, 1)
        expect(rows.locator(".equipment-status-label")).to_have_text(label)
        expect(rows.locator(".equipment-status-sensor__state")).to_have_text([label])
    page.locator("#equipment-status-state").select_option("critical")
    assert_count(page, 0)
    select_fan_in_tree(page)
    assert_count(page, 0)
    expect(page.locator('#equipment-status-tree [aria-current="true"]')).to_have_count(0)
    expect(page.locator("#equipment-status-list")).to_contain_text("조건에 맞는 설비가 없습니다.")
    page.locator("#equipment-status-reset").click()
    assert_count(page, initial)
    target = select_fan_in_tree(page)
    expect(target).to_have_attribute("aria-current", "true")
    rows = assert_count(page, 1)
    expect(rows.locator("summary")).to_have_attribute("aria-current", "true")
    rows.locator("summary").click()
    live = rows.locator('a[href^="/dashboard2?dataset="]')
    expect(live.first).to_be_visible()
    assert re.search(r"dataset=\d+", live.first.get_attribute("href"))
    capture_page(page, "task4-reference-selected")
    page.locator("#equipment-status-reset").click()
    assert_count(page, initial)
    expect(page.locator('#equipment-status-tree [aria-current="true"]')).to_have_count(0)
    page.locator("#equipment-status-state").select_option("critical")
    critical = assert_count(page)
    assert critical.count() > 0
    expect(critical.locator(".equipment-status-label")).to_have_text(["심각"] * critical.count())
    page.locator("#equipment-status-reset").click()
    first = page.locator("#equipment-status-list > details").first
    name = first.locator("strong").inner_text()
    first.locator("summary").click()
    expect(page.locator('#equipment-status-tree [aria-current="true"]')).to_have_text(name)
    assert_count(page, initial)
    target = select_fan_in_tree(page)
    target.focus()
    page.keyboard.press("Enter")
    assert_count(page, 1)
    expect(target).to_have_attribute("aria-current", "true")
    bar = page.locator(".equipment-status2-plant").first
    bar.focus()
    expect(page.get_by_role("tooltip")).to_be_visible()
    expect(page.get_by_role("tooltip")).to_have_text(bar.get_attribute("aria-label"))
    page.keyboard.press("Escape")
    expect(page.get_by_role("tooltip")).to_be_hidden()
    geometry = page.evaluate("({width: innerWidth, scroll: document.documentElement.scrollWidth})")
    assert geometry["scroll"] <= geometry["width"] + 1


@pytest.mark.parametrize("cms_desktop_case", DESKTOP_CASES, indirect=True)
def test_alarm_loading_empty_error_and_long_names(cms_page, cms_api_controls):
        from playwright.sync_api import expect

        page = cms_page
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        gate = cms_api_controls.hold("/api/datasets")
        page.goto("/equipment-status2", wait_until="domcontentloaded")
        gate.wait_until_intercepted(page)
        expect(page.locator("#equipment-status-list")).to_have_attribute("aria-busy", "true")
        expect(page.locator("[data-cms-result-count]")).to_have_text("조회 중")
        expect(page.locator("#equipment-status-name")).to_be_disabled()
        expect(page.locator("#equipment-status-list")).to_contain_text("불러오는 중")
        capture_page(page, "task4-loading")
        gate.release()
        expect(page.locator("#equipment-status-name")).to_be_enabled()
        initial = assert_count(page).count()
        assert gate.hits > 0
        page.locator("#equipment-status-name").fill("실제로존재하지않는설비검색조건")
        assert_count(page, 0)
        expect(page.locator("#equipment-status-list")).to_contain_text("조건에 맞는 설비가 없습니다.")
        expect(page.locator('#equipment-status-tree [aria-current="true"]')).to_have_count(0)
        capture_page(page, "task4-empty")
        page.locator("#equipment-status-reset").click()
        assert_count(page, initial)
        error = cms_api_controls.error("/api/datasets")
        open_page(page, "/equipment-status2")
        expect(page.locator("#equipment-status-notice")).to_be_visible()
        expect(page.locator("#equipment-status-notice")).to_contain_text("분류만 표시")
        assert not page_errors, page_errors
        expect(page.locator("#equipment-status-chart-status")).to_contain_text("불러오지 못했습니다")
        assert error.hits > 0
        assert assert_count(page).count() > 0
        expect(page.locator('#equipment-status-list a[href^="/dashboard2"]')).to_have_count(0)
        capture_page(page, "task4-error")
        long_name = "열연공장설비상태확인을위한장문한글설비이름검증" * 4
        page.add_init_script(f"window.task4LongName = '{long_name}';" + """
            addEventListener('DOMContentLoaded', () => {
                    window.equipmentExcelData.push({factory: '장문공장', process: '장문공정', equipmentType: '장문유형', name: window.task4LongName,
                        location: window.task4LongName, tag: 'LONG-UI'});
            }, {once: true});
            """)
        open_page(page, "/equipment-status2")
        page.locator("#equipment-status-name").fill(long_name)
        rows = assert_count(page, 1)
        rows.locator("summary").click()
        for locator in (rows.locator("strong"), rows.locator(".equipment-status-sensor span")):
                assert text_metrics(locator)["fontSize"] == "14px"
                bounds = locator.evaluate("""node => {
                    const range = document.createRange(); range.selectNodeContents(node);
                    const text = range.getBoundingClientRect(); const box = node.getBoundingClientRect();
                    return {text: {left: text.left, right: text.right, bottom: text.bottom},
                        box: {left: box.left, right: box.right, bottom: box.bottom}, scroll: node.scrollWidth, width: node.clientWidth};
                }""")
                assert bounds["text"]["right"] <= bounds["box"]["right"] + 1
                assert bounds["text"]["bottom"] <= bounds["box"]["bottom"] + 1
                assert bounds["scroll"] <= bounds["width"] + 1
        capture_page(page, "task4-long-korean")


def test_alarm_styles_owned_by_page(cms_page):
        page = cms_page
        open_page(page, "/equipment-status2")
        assert page.locator("head style").count() == 0
        assert page.locator('link[href*="/equipment-status.css"]').count() == 0
        assert page.locator('link[href*="/equipment-status2.css"]').count() == 1
        assert page.locator(".equipment-status-panel .equipment-status-search").count() == 0
        violations = page.locator("main *").evaluate_all("""nodes => nodes.filter(node => {
            const style = getComputedStyle(node);
            return style.display !== 'none' && style.letterSpacing !== 'normal' && parseFloat(style.letterSpacing) !== 0;
        }).map(node => node.className)""")
        assert violations == []
        roles = page.evaluate("""() => {
            const size = selector => {const style = getComputedStyle(document.querySelector(selector));
                return [style.fontSize, style.lineHeight];};
            return {page: size('h1'), section: size('main h2'), body: size('.equipment-status-item__details strong'),
                label: size('.equipment-status-search label'), input: size('#equipment-status-name'),
                controls: [...document.querySelectorAll('.equipment-status-search input, .equipment-status-search select, .equipment-status-search button')].map(node => node.getBoundingClientRect().height),
                radii: [...document.querySelectorAll('main *')].filter(node => {
                    const style = getComputedStyle(node); const box = node.getBoundingClientRect();
                    return ['borderTopLeftRadius','borderTopRightRadius','borderBottomLeftRadius','borderBottomRightRadius'].some(key =>
                        style[key].endsWith('%') ? parseFloat(style[key]) * Math.min(box.width, box.height) / 100 > 8 : parseFloat(style[key]) > 8);
                }).map(node => node.className)};
        }""")
        assert roles["page"] == ["24px", "32px"]
        assert roles["section"] == ["16px", "24px"]
        assert roles["body"] == roles["input"] == ["14px", "22px"]
        assert roles["label"] == ["13px", "20px"]
        assert min(roles["controls"]) >= 36
        assert roles["radii"] == []


def test_unknown_status_does_not_appear_healthy(cms_page):
    from playwright.sync_api import expect

    page = cms_page
    payload = page.request.get("/api/datasets").json()
    matching = [item for item in payload["items"] if item["equipmentCode"] == "V191"]
    assert len(matching) == 3
    for item in matching:
        item.update(status="unknown", statusLabel="판단 불가", statusDescription="Trend 이력이 충분하지 않습니다.")
    intercepted = []

    def unknown_response(route):
        intercepted.append(route.request.url)
        route.fulfill(json=payload)

    page.route("**/api/datasets", unknown_response)
    open_page(page, "/equipment-status2")
    page.locator("#equipment-status-name").fill(FAN)
    rows = assert_count(page, 1)
    expect(rows.locator(".equipment-status-label")).to_have_text("판단 불가")
    expect(page.locator('#equipment-status-tree button[aria-current="true"] .equipment-status-tree__health--unknown')).to_have_count(1)
    page.locator("#equipment-status-state").select_option("unknown")
    rows = assert_count(page, 1)
    rows.locator("summary").click()
    expect(rows.locator(".equipment-status-sensor__state")).to_have_text(["판단 불가"])
    expect(page.locator(".equipment-status2-state-row").filter(has_text="판단 불가")).to_contain_text("3대")
    assert len(intercepted) >= 1
    capture_page(page, "task4-unknown-intercepted")