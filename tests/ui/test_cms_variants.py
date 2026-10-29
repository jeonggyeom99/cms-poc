from __future__ import annotations

import json

import pytest

from tests.ui.helpers import capture_page, open_page
from tests.ui.test_cms_baseline import ROUTES


pytestmark = pytest.mark.ui
DESKTOP_CASES = [(1280, 800, 1), (1440, 900, 1), (1920, 1080, 1), (1440, 900, 1.25)]
LAB_ROUTES = ["/dashboard_ui3", "/dashboard_ui4", "/static/dashboard-lab.html", "/static/design-lab.html"]
DIRECT_ROUTES = [f"/static/{owner}.html" for owner in ("main", "dashboard-ui1-kpi", "dashboard-ui1-canvas", "design-lab", "dashboard-ui5", "equipment-status")]
CONTENT = {
    "/main": ["공장별 운영 현황", "이상 징후", "최근 진단 이력"],
    "/dashboard_ui1": ["Asset Segment", "Diagnosis Segment", "운영 건전성", "데모"],
    "/dashboard_ui1_canvas": ["공장 목록", "설비 상태 분포", "설비 상태 레지스터"],
    "/dashboard_ui3": ["설비 분석 리포트", "전체 상태 구성", "최근 진단 활동", "예시 비율"],
    "/dashboard_ui4": ["Daily Maintenance Board", "오늘 점검 대상 공장", "최근 진단 활동", "예시 비율"],
    "/dashboard_ui5": ["공장별 상태 비교", "상태별 설비 목록", "진단 이력 타임라인"],
    "/static/history2.html": ["진단 이력", "전체 진단 건수", "조치 필요"],
    "/static/dashboard-ui1-fresh.html": ["설비 상태를 한눈에", "공장별 설비 분포", "우선 조치", "예시 비율"],
    "/static/dashboard-lab.html": ["통합 설비 운영 현황", "공장별 설비 상태 분포", "최근 진단 활동", "예시 비율"],
}


@pytest.mark.parametrize("path", ROUTES + DIRECT_ROUTES)
@pytest.mark.parametrize("cms_desktop_case", DESKTOP_CASES, indirect=True)
def test_retained_variants_share_roles_without_losing_content(cms_page, path):
    page = cms_page
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    response = open_page(page, path)
    assert response.status == 200
    assert not errors, errors
    assert "<!-- cms:" not in response.text()
    assert len(page.locator("main").inner_text().strip()) > 80
    for text in CONTENT.get(path, []):
        assert text in page.locator("main").inner_text(), (path, text)
    assets = page.locator('link[rel="stylesheet"], script[src]').evaluate_all(
        "nodes => nodes.map(node => new URL(node.href || node.src).pathname)"
    )
    for asset in ["/static/cms-tokens.css", "/static/cms-operations.css", "/static/cms-sidebar-icons.css", "/static/modules/core/cms-operations.js"]:
        assert assets.count(asset) == 1, (path, asset, assets)
    assert len(assets) == len(set(assets)), assets
    styles = [asset for asset in assets if asset.endswith(".css")]
    assert styles[:3] == ["/static/cms-tokens.css", "/static/cms-operations.css", "/static/cms-sidebar-icons.css"]
    sidebar = page.locator("#cms-sidebar")
    assert sidebar.count() == 1
    before = sidebar.bounding_box()
    sidebar.hover()
    sidebar.locator("a").first.focus()
    after = sidebar.bounding_box()
    assert before["width"] == after["width"] == 244
    page.locator("#cms-sidebar-toggle").click()
    assert sidebar.bounding_box()["width"] == 76
    sidebar.hover()
    sidebar.locator("a").first.focus()
    assert sidebar.bounding_box()["width"] == 76
    page.locator("#cms-sidebar-toggle").click()
    page.mouse.move(page.viewport_size["width"] - 2, 0)
    page.wait_for_function("""() => [...document.querySelectorAll('canvas.canvas-track')].every(canvas =>
        Math.abs(canvas.width - canvas.getBoundingClientRect().width * devicePixelRatio) <= 1)""")
    metrics = page.evaluate("""() => {
        const measure = selector => [...document.querySelectorAll(selector)].filter(node => node.getClientRects().length).map(node => {
            const style = getComputedStyle(node); const box = node.getBoundingClientRect();
            return {text: node.textContent.trim().slice(0, 160), size: style.fontSize, leading: style.lineHeight,
                spacing: style.letterSpacing, width: box.width, height: box.height};
        });
        return {width: innerWidth, scroll: document.documentElement.scrollWidth,
            clipped: ['html', 'body', 'main'].some(selector => ['hidden', 'clip'].includes(getComputedStyle(document.querySelector(selector)).overflowX)),
            headings: measure('main h1'), sections: measure('main h2, main h3'),
            controls: measure('main button, main select, main input:not([type="checkbox"]):not([type="radio"])'),
            tiny: measure('main p, main td, main th, main label, main small, main a').filter(item => parseFloat(item.size) < 12),
            clippedText: [...document.querySelectorAll('body.cms-retained main p, body.cms-retained main strong, body.cms-retained main small, body.cms-retained main label, body.cms-retained main time')].filter(node => {
                const style = getComputedStyle(node);
                return node.getClientRects().length && ['hidden', 'clip'].includes(style.overflowX) && node.scrollWidth > node.clientWidth + 1;
            }).map(node => node.textContent),
            kpis: measure('[data-cms-role="kpi"], body.cms-retained .stat b, body.cms-retained .pie b, body.cms-retained .summary-row strong, body.cms-retained .hero-index strong, body.cms-retained .main-metrics strong, body.cms-retained .big-kpi > strong, body.cms-retained .gauge b'),
            canvases: [...document.querySelectorAll('main canvas')].map(canvas => {
                const context = canvas.getContext('2d');
                const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
                const colors = new Set();
                for (let offset = 0; offset < pixels.length; offset += Math.max(4, Math.floor(pixels.length / 16000 / 4) * 4)) {
                    colors.add([...pixels.slice(offset, offset + 4)].join(','));
                }
                const box = canvas.getBoundingClientRect();
                return {width: canvas.width, height: canvas.height, visibleWidth: box.width, visibleHeight: box.height,
                    colors: colors.size, values: JSON.parse(canvas.dataset.values || 'null'), font: context.font};
            })};
    }""")
    target = capture_page(page, "task7-route-" + path)
    target.with_suffix(".roles.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    assert metrics["scroll"] <= metrics["width"] + 1, metrics
    assert not metrics["clipped"], metrics
    assert metrics["headings"], metrics
    assert all(item["size"] == "24px" and item["leading"] == "32px" for item in metrics["headings"]), metrics["headings"]
    section_roles = {("16px", "24px")} if page.locator("body.cms-retained").count() else {("16px", "24px"), ("13px", "20px")}
    assert all((item["size"], item["leading"]) in section_roles for item in metrics["sections"]), metrics["sections"]
    assert all(item["size"] == "14px" and item["height"] >= 36 for item in metrics["controls"]), metrics["controls"]
    assert not metrics["tiny"], metrics["tiny"]
    assert not metrics["clippedText"], metrics["clippedText"]
    assert all(item["size"] == "28px" and item["leading"] == "36px" for item in metrics["kpis"]), metrics["kpis"]
    if path in {"/dashboard_ui1_canvas", "/static/dashboard-ui1-canvas.html"}:
        assert metrics["canvases"], "Canvas variant must render its actual status data, not only an empty canvas element"
        items = page.request.get("/api/datasets").json()["items"]
        plants = list(dict.fromkeys(item["plant"] for item in items))
        expected = [[sum(item["plant"] == plant and item["status"] == status for item in items) for status in ("normal", "caution", "critical")] for plant in plants]
        assert [canvas["values"] for canvas in metrics["canvases"]] == expected
    for canvas in metrics["canvases"]:
        assert min(canvas["width"], canvas["height"], canvas["visibleWidth"], canvas["visibleHeight"]) > 0, canvas
        assert canvas["colors"] > 1, canvas
        assert canvas["font"].startswith("12px "), canvas
    assert not errors, errors


@pytest.mark.parametrize("path", LAB_ROUTES)
@pytest.mark.parametrize("cms_desktop_case", DESKTOP_CASES, indirect=True)
def test_retained_lab_chart_labels_and_annotations_follow_shared_role(cms_page, path):
    errors = []
    cms_page.on("pageerror", lambda error: errors.append(str(error)))
    assert open_page(cms_page, path).status == 200
    cms_page.wait_for_selector("#bars .bar-line em")
    evidence = cms_page.evaluate("""() => {
        const root = document.documentElement;
        const measure = () => [...document.querySelectorAll('#bars .bar-line label, #bars .bar-line em')].map(node => {
            const style = getComputedStyle(node);
            return {tag: node.tagName, text: node.textContent, role: node.closest('[data-cms-role]')?.dataset.cmsRole,
                size: style.fontSize, leading: style.lineHeight};
        });
        const tokens = {'--cms-type-chart': '15px', '--cms-leading-chart': '23px'};
        const originals = Object.keys(tokens).map(name => [name, root.style.getPropertyValue(name)]);
        const baseline = measure();
        try {
            Object.entries(tokens).forEach(([name, value]) => root.style.setProperty(name, value));
            return {baseline, changed: measure()};
        } finally {
            originals.forEach(([name, value]) => value
                ? root.style.setProperty(name, value) : root.style.removeProperty(name));
        }
    }""")
    target = capture_page(cms_page, "task7-r1-chart-" + path)
    target.with_suffix(".roles.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    assert evidence["baseline"]
    assert {item["tag"] for item in evidence["baseline"]} == {"LABEL", "EM"}
    assert all(item.get("role") == "chart" and item["size"] == "12px" and item["leading"] == "18px"
               for item in evidence["baseline"]), evidence["baseline"]
    assert all(item["size"] == "15px" and item["leading"] == "23px"
               for item in evidence["changed"]), evidence["changed"]
    items = cms_page.request.get("/api/datasets").json()["items"]
    assert cms_page.locator(".stat b").all_text_contents() == [
        str(len(items)),
        str(sum(item["status"] == "normal" for item in items)),
        str(sum(item["status"] == "caution" for item in items)),
        str(sum(item["status"] == "critical" for item in items)),
    ]
    plants = list(dict.fromkeys(item["plant"] for item in items))[:8]
    assert cms_page.locator("#bars label").all_text_contents() == plants
    counts = [sum(item["plant"] == plant and item["status"] in {"caution", "critical"} for item in items)
              for plant in plants]
    assert cms_page.locator("#bars em").all_text_contents() == [f"{count}\uac74 \uc8fc\uc758" for count in counts]
    assert not errors, errors


@pytest.mark.parametrize("path", LAB_ROUTES)
@pytest.mark.parametrize("cms_desktop_case", DESKTOP_CASES, indirect=True)
def test_retained_lab_labels_annotations_and_status_kpis_have_readable_contrast(cms_page, path):
    errors = []
    cms_page.on("pageerror", lambda error: errors.append(str(error)))
    assert open_page(cms_page, path).status == 200
    cms_page.wait_for_selector("#bars .bar-line em")
    evidence = cms_page.evaluate(r"""path => {
        const rgba = color => color.match(/[\d.]+/g).map(Number);
        const composite = (foreground, background) => {
            const alpha = foreground[3] ?? 1;
            return foreground.slice(0, 3).map((value, index) => value * alpha + background[index] * (1 - alpha));
        };
        const luminance = color => {
            const channels = color.map(value => value / 255)
                .map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
            return channels[0] * .2126 + channels[1] * .7152 + channels[2] * .0722;
        };
        const measure = () => [...document.querySelectorAll('.lab-main .eyebrow, .stat small, .stat b, #bars label, #bars em')]
            .filter(node => node.getClientRects().length).map(node => {
                const ancestors = [];
                for (let ancestor = node; ancestor; ancestor = ancestor.parentElement) ancestors.unshift(ancestor);
                const styles = ancestors.map(ancestor => getComputedStyle(ancestor));
                const background = styles.reduce((color, style) => composite(rgba(style.backgroundColor), color), [255, 255, 255]);
                const style = getComputedStyle(node);
                const foreground = composite(rgba(style.color), background);
                const light = [luminance(foreground), luminance(background)];
                const large = parseFloat(style.fontSize) >= 24 || (parseFloat(style.fontSize) >= 18.66 && +style.fontWeight >= 700);
                return {tag: node.tagName, classes: node.className, text: node.textContent, color: style.color,
                    foreground, background, contrast: (Math.max(...light) + .05) / (Math.min(...light) + .05),
                    minimum: large ? 3 : 4.5, size: style.fontSize, leading: style.lineHeight,
                    unsupported: styles.filter(item => item.backgroundImage !== 'none' || +item.opacity !== 1)
                        .map(item => ({image: item.backgroundImage, opacity: item.opacity})),
                    token: node.matches('b.amber') ? 'caution' : node.matches('b') ? null
                        : node.matches('.eyebrow') && path === '/static/dashboard-lab.html' ? 'accent' : 'text'};
            });
        const root = document.documentElement;
        const tokens = {'--cms-color-text': '#123456', '--cms-color-caution': '#654321', '--cms-color-accent': '#234567'};
        const originals = Object.keys(tokens).map(name => [name, root.style.getPropertyValue(name)]);
        const baseline = measure();
        try {
            Object.entries(tokens).forEach(([name, value]) => root.style.setProperty(name, value));
            return {baseline, changed: measure()};
        } finally {
            originals.forEach(([name, value]) => value
                ? root.style.setProperty(name, value) : root.style.removeProperty(name));
        }
    }""", path)
    target = capture_page(cms_page, "task7-r1-contrast-" + path)
    target.with_suffix(".contrast.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    assert len([item for item in evidence["baseline"] if item["tag"] == "B"]) == 4
    assert {item["tag"] for item in evidence["baseline"]} >= {"LABEL", "EM", "SMALL", "B", "SPAN"}
    assert not [item for item in evidence["baseline"] if item["unsupported"]], evidence["baseline"]
    failures = [item for item in evidence["baseline"] if item["contrast"] < item["minimum"]]
    assert not failures, failures
    expected_colors = {"text": "rgb(18, 52, 86)", "caution": "rgb(101, 67, 33)", "accent": "rgb(35, 69, 103)"}
    assert all(item["color"] == expected_colors[item["token"]]
               for item in evidence["changed"] if item["token"]), evidence["changed"]
    assert not errors, errors


def test_retained_status_labels_and_report_rows_are_complete(cms_page):
    page = cms_page
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    open_page(page, "/main")
    labels = page.locator(".alert-item em").all_text_contents()
    assert labels and set(labels) <= {"정상", "주의", "심각", "판단 불가"}, labels
    open_page(page, "/dashboard_ui5")
    rows = page.locator("#table-body .table-row")
    assert rows.count() > 0
    for row in rows.all():
        assert row.locator(":scope > *").count() == 5
        assert row.locator("a").count() == 0, "A row navigation link must not contain a second nested anchor"
        cells = row.locator(":scope > *").evaluate_all("nodes => nodes.map(node => node.getBoundingClientRect().top)")
        assert max(cells) - min(cells) < 30, cells
    assert not errors, errors


def test_retained_worklist_kpi_has_readable_contrast(cms_page):
    open_page(cms_page, "/dashboard_ui4")
    contrast = cms_page.locator(".stat").first.evaluate("""node => {
        const luminance = color => {
            const channels = color.match(/[\\d.]+/g).slice(0, 3).map(Number).map(value => value / 255)
                .map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
            return channels[0] * .2126 + channels[1] * .7152 + channels[2] * .0722;
        };
        const foreground = luminance(getComputedStyle(node.querySelector('b')).color);
        const background = luminance(getComputedStyle(node).backgroundColor);
        return (Math.max(foreground, background) + .05) / (Math.min(foreground, background) + .05);
    }""")
    assert contrast >= 4.5, contrast