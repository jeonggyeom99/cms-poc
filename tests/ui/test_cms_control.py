from __future__ import annotations

import pytest
import json
import re
from urllib.parse import parse_qs, urlsplit

from tests.ui.helpers import capture_page, open_page


pytestmark = pytest.mark.ui
DESKTOP_CASES = [(1280, 800, 1), (1440, 900, 1), (1920, 1080, 1), (1440, 900, 1.25)]


@pytest.mark.parametrize("path", ["/dashboard_ui1", "/dashboard_ui6"])
def test_shared_chart_yaxis_generated_ticks_match_bar_domain(cms_page, path):
    from playwright.sync_api import expect

    page = cms_page
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    open_page(page, path)
    charts = page.locator(".cms-vbars")
    expect(charts).to_have_count(2)
    metrics = charts.evaluate_all("""nodes => nodes.map(node => {
        const style = getComputedStyle(node, '::before');
        return {ticks: node.dataset.ticks ?? null, content: style.content,
            display: style.display, visibility: style.visibility, opacity: style.opacity,
            whiteSpace: style.whiteSpace, fontSize: style.fontSize, height: style.height,
            bars: [...node.querySelectorAll('.cms-vbar')].map(bar => ({title: bar.title, height: bar.style.height}))};
    })""")
    target = capture_page(page, "task6-fix1-yaxis" + path)
    target.with_suffix(".ticks.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    for chart in metrics:
        domain_max = max(int(re.search(r"(\d+)건$", bar["title"]).group(1)) for bar in chart["bars"])
        rendered_ticks = [float(value) for value in re.findall(r"\d+(?:\.\d+)?", chart["content"])]
        assert len(rendered_ticks) == 5, chart
        assert rendered_ticks == pytest.approx([domain_max, domain_max * .75, domain_max * .5, domain_max * .25, 0], abs=.051), chart
        assert chart["ticks"] is not None, chart
        assert rendered_ticks == [float(value) for value in chart["ticks"].splitlines()], chart
        assert chart["display"] != "none" and chart["visibility"] == "visible", chart
        assert float(chart["opacity"]) > 0 and float(chart["fontSize"].removesuffix("px")) > 0, chart
        assert chart["whiteSpace"] == "pre" and float(chart["height"].removesuffix("px")) > 0, chart
    assert not errors, errors


@pytest.mark.parametrize("cms_desktop_case", DESKTOP_CASES, indirect=True)
@pytest.mark.parametrize("path", ["/dashboard_ui2", "/dashboard_ui6"])
def test_dashboard_reading_order(cms_page, path):
    from playwright.sync_api import expect

    page = cms_page
    open_page(page, path)
    expect(page.locator(".grid")).to_have_count(1)
    assert page.locator(".kpi strong").first.inner_text().isdigit()
    order = page.evaluate("""() => {
        const nodes = ['.grid', '.hero', '.columns', '.table'].map(selector => document.querySelector(selector));
        return nodes.slice(1).map((node, index) => Boolean(nodes[index].compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING));
    }""")
    assert order == [True, True, True], "Expected KPI > risk > trend > actions in actual DOM"
    assert_layout(page, "task6-dashboard" + path)


def assert_layout(page, name):
    geometry = page.evaluate("""() => ({width: innerWidth, scroll: document.documentElement.scrollWidth,
        clipped: ['html', 'body', 'main'].some(selector => ['hidden', 'clip'].includes(getComputedStyle(document.querySelector(selector)).overflowX))})""")
    assert geometry["scroll"] <= geometry["width"] + 1, geometry
    assert not geometry["clipped"], geometry
    target = capture_page(page, name)
    metrics = page.evaluate("""() => {
        const measure = selector => [...document.querySelectorAll(selector)].filter(node => node.getClientRects().length).map(node => {
            const style = getComputedStyle(node); const box = node.getBoundingClientRect();
            return {text: node.textContent, size: style.fontSize, leading: style.lineHeight,
                weight: style.fontWeight, radius: style.borderRadius, spacing: style.letterSpacing,
                width: box.width, height: box.height};
        });
        return {headings: measure('main h1'), sections: measure('main h2, main h3'),
            controls: measure('main select, main input, main button, .header-link, .actions .btn'),
            badges: measure('.status, .work-row em, .history-diagnosis-tag')};
    }""")
    assert all(item["size"] == "24px" and item["leading"] == "32px" for item in metrics["headings"])
    assert all(item["size"] == "16px" and item["leading"] == "24px" for item in metrics["sections"])
    assert all(item["size"] == "14px" and item["height"] >= 36 for item in metrics["controls"])
    target.with_suffix(".roles.json").write_text(json.dumps({"geometry": geometry, **metrics}, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.mark.parametrize("cms_desktop_case", DESKTOP_CASES, indirect=True)
@pytest.mark.parametrize("path", ["/main_ct", "/main_sv", "/main_ct1", "/main_ct2", "/main_ct3", "/main_sv1", "/main_sv2", "/main_sv3"])
def test_control_desktop_layout_and_existing_links(cms_page, path):
    from playwright.sync_api import expect

    page = cms_page
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    open_page(page, path)
    expect(page.locator("#total")).to_have_text("9")
    assert_layout(page, "task6" + path.replace("/", "-"))
    if page.locator(".priority-head").count():
        expect(page.locator(".priority-head > span")).to_have_count(5)
        heading = page.locator(".priority-head > span").nth(2)
        expect(heading).to_have_text("설비")
        assert abs(heading.bounding_box()["x"] - page.locator(".priority-row strong").first.bounding_box()["x"]) <= 1
    link = page.locator(".work-row, .priority-row").first
    expected_path = "/dashboard2" if path == "/main_ct" else "/dashboard"
    href = link.get_attribute("href")
    assert urlsplit(href).path == expected_path
    expected_dataset = parse_qs(urlsplit(href).query)["dataset"][0]
    link.click()
    expect(page.locator("#dataset-select")).to_have_value(expected_dataset)
    page.wait_for_load_state("networkidle")
    assert not errors, errors


@pytest.mark.parametrize("path", ["/main_ct", "/main_sv"])
def test_control_scope_process_reset_priority_and_states(cms_page, cms_api_controls, path):
    from playwright.sync_api import expect

    page = cms_page
    gate = cms_api_controls.hold("/api/datasets")
    page.goto(path, wait_until="domcontentloaded")
    gate.wait_until_intercepted(page)
    expect(page.locator("#scope-select")).to_be_disabled()
    expect(page.locator("#risk-map")).to_have_attribute("aria-busy", "true")
    expect(page.locator("#risk-map")).to_contain_text("불러오는 중")
    capture_page(page, "task6-control-loading" + path)
    gate.release()
    expect(page.locator("#scope-select")).to_be_enabled()
    items = page.request.get("/api/datasets").json()["items"]
    expected = [item for item in items if item["status"] in {"critical", "caution"}]
    expected.sort(key=lambda item: item["status"] != "critical")
    assert [parse_qs(urlsplit(href).query)["dataset"][0] for href in page.locator(".work-row").evaluate_all("nodes => nodes.map(node => node.href)")] == [str(item["id"]) for item in expected[:5]]
    first = items[0]
    page.locator("#scope-select").select_option(first["plant"])
    page.locator("#process-select").select_option(first["line"])
    selected_items = [item for item in items if item["plant"] == first["plant"] and item["line"] == first["line"]]
    expect(page.locator("#total")).to_have_text(str(len(selected_items)))
    capture_page(page, "task6-control-selected" + path)
    page.locator("#scope-select").select_option("all")
    expect(page.locator("#process-select")).to_have_value("all")
    expect(page.locator("#total")).to_have_text("9")
    capture_page(page, "task6-control-selected-reset" + path)
    page.locator("#process-select").evaluate("node => node.add(new Option('No matching process', 'none'))")
    page.locator("#process-select").select_option("none")
    expect(page.locator("#total")).to_have_text("0")
    expect(page.locator("#work-rows")).to_contain_text("점검 대상이 없습니다")
    expect(page.locator("#recent-activity")).to_contain_text("최근 진단 활동이 없습니다")
    capture_page(page, "task6-control-empty" + path)
    cms_api_controls.error("/api/datasets")
    open_page(page, path)
    expect(page.locator("#risk-map")).to_contain_text("불러오지 못했습니다")
    expect(page.locator("#scope-select")).to_be_disabled()
    capture_page(page, "task6-control-error" + path)


@pytest.mark.parametrize("cms_desktop_case", DESKTOP_CASES, indirect=True)
@pytest.mark.parametrize("path", ["/main_ct", "/main_sv"])
def test_workspace_long_names_remain_accessible(cms_page, path):
    from playwright.sync_api import expect

    page = cms_page
    payload = page.request.get("/api/datasets").json()
    long_name = "긴 설비명과 공장별 점검 대상 " * 24
    payload["items"][0].update(displayName=long_name, status="critical", statusLabel="심각")
    page.route("**/api/datasets", lambda route: route.fulfill(json=payload))
    open_page(page, path)
    target = page.locator(".work-row strong").first
    expect(target).to_have_text(long_name.strip())
    assert target.evaluate("node => node.scrollWidth <= node.clientWidth + 1 && getComputedStyle(node).fontSize === '14px'")
    assert_layout(page, "task6-workspace-long" + path)


@pytest.mark.parametrize("path", ["/dashboard_ui2", "/dashboard_ui6"])
def test_dashboard_loading_empty_error_and_demo_boundary(cms_page, cms_api_controls, path):
    from playwright.sync_api import expect

    page = cms_page
    gate = cms_api_controls.hold("/api/datasets")
    page.goto(path, wait_until="domcontentloaded")
    gate.wait_until_intercepted(page)
    expect(page.locator("main")).to_have_attribute("aria-busy", "true")
    expect(page.locator("#dashboard-status")).to_contain_text("불러오는 중")
    capture_page(page, "task6-overview-loading" + path)
    gate.release()
    expect(page.locator("main")).to_have_attribute("aria-busy", "false")
    expect(page.locator(".cms-chart-grid")).to_have_attribute("aria-label", "데모 운영 지표")
    expect(page.locator(".cms-analysis-grid")).to_contain_text("데모")
    page.route("**/api/datasets", lambda route: route.fulfill(json={"items": []}))
    cms_api_controls.empty_history()
    open_page(page, path)
    expect(page.locator(".kpi strong").first).to_have_text("0")
    expect(page.locator("#dashboard-status")).to_contain_text("설비가 없습니다")
    capture_page(page, "task6-overview-empty" + path)
    page.unroute("**/api/datasets")
    cms_api_controls.error("/api/datasets")
    open_page(page, path)
    expect(page.locator("#dashboard-status")).to_contain_text("불러오지 못했습니다")
    expect(page.locator(".kpi strong").first).to_have_text("-")
    capture_page(page, "task6-overview-error" + path)


@pytest.mark.parametrize("path", ["/main_ct1", "/main_sv2"])
def test_control_variant_loading_empty_error_and_long_names(cms_page, cms_api_controls, path):
    from playwright.sync_api import expect

    page = cms_page
    gate = cms_api_controls.hold("/api/datasets")
    page.goto(path, wait_until="domcontentloaded")
    gate.wait_until_intercepted(page)
    expect(page.locator("#primary-chart")).to_have_attribute("aria-busy", "true")
    expect(page.locator("#primary-chart")).to_contain_text("불러오는 중")
    capture_page(page, "task6-variant-loading" + path)
    gate.release()
    expect(page.locator("#primary-chart")).to_have_attribute("aria-busy", "false")
    payload = page.request.get("/api/datasets").json()
    payload["items"][0]["displayName"] = "긴 설비 이름 및 현장 확인 정보 " * 20
    payload["items"][0]["status"] = "critical"
    page.route("**/api/datasets", lambda route: route.fulfill(json=payload))
    open_page(page, path)
    assert_layout(page, "task6-variant-long" + path)
    priority = page.locator(".priority-row strong").first
    expect(priority).to_contain_text("긴 설비 이름")
    assert priority.evaluate("node => node.scrollWidth <= node.clientWidth + 1")
    page.unroute("**/api/datasets")
    page.route("**/api/datasets", lambda route: route.fulfill(json={"items": []}))
    cms_api_controls.empty_history()
    open_page(page, path)
    expect(page.locator("#total")).to_have_text("0")
    expect(page.locator("#primary-chart")).to_contain_text("설비가 없습니다")
    assert "NaN" not in page.locator("#donut-chart").get_attribute("style")
    capture_page(page, "task6-variant-empty" + path)
    page.unroute("**/api/datasets")
    cms_api_controls.error("/api/datasets")
    open_page(page, path)
    expect(page.locator("#primary-chart")).to_have_attribute("aria-busy", "false")
    expect(page.locator("#primary-chart")).to_contain_text("불러오지 못했습니다")
    capture_page(page, "task6-variant-error" + path)


@pytest.mark.parametrize("path", ["/dashboard_ui6", "/history2", "/main_ct", "/main_sv1"])
def test_task6_shared_role_tokens_and_chart_styles(cms_page, path):
    from playwright.sync_api import expect

    page = cms_page
    open_page(page, path)
    assert_layout(page, "task6-roles" + path)
    page.evaluate("document.documentElement.style.setProperty('--cms-type-section', '19px')")
    assert page.locator("main h2, main h3").first.evaluate("node => getComputedStyle(node).fontSize") == "19px"
    if path == "/history2":
        assert page.locator("#history-keyword").evaluate("node => parseFloat(getComputedStyle(node).paddingLeft)") >= 36
    if path == "/dashboard_ui6":
        expect(page.locator("#cms-chart-panel-style")).to_have_count(0)
        assert page.locator("head style").count() == 0
        bar = page.locator(".cms-vbar[title]").first
        bar.hover()
        tooltip = page.locator(".cms-data-tooltip")
        expect(tooltip).to_be_visible()
        assert tooltip.evaluate("node => getComputedStyle(node).fontSize") == "12px"
        before = tooltip.bounding_box()
        page.mouse.move(before["x"] + 30, before["y"] + 40)
        after = tooltip.bounding_box()
        assert after != before
        capture_page(page, "task6-chart-tooltip")