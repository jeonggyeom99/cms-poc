from __future__ import annotations

import json

import pytest

from tests.ui.helpers import capture_page, open_page
from tests.ui.test_cms_baseline import ROUTES


pytestmark = pytest.mark.ui
KOREAN_PLANT = "3 \uc804\uae30\uac15\ud310 3DNL"
LONG_PLANT = KOREAN_PLANT + " \ub0c9\uc5f0 \uc0dd\uc0b0\ub77c\uc778 \uc124\ube44 \uc9c4\ub3d9 \uc0c1\ud0dc \uac10\uc2dc \uc13c\uc11c \uc810\uac80 \uad6c\uc5ed" * 5
CASES = [(1280, 800, 1), (1440, 900, 1), (1920, 1080, 1), (1440, 900, 1.25)]


def platform_fonts(page, probes):
    session = page.context.new_cdp_session(page)
    try:
        session.send("DOM.enable")
        session.send("CSS.enable")
        root = session.send("DOM.getDocument")["root"]["nodeId"]
        for role, probe in probes.items():
            node = session.send("DOM.querySelector", {"nodeId": root,
              "selector": f'[data-task8-font-{role}]'})["nodeId"]
            probe["fonts"] = session.send("CSS.getPlatformFontsForNode", {"nodeId": node})["fonts"]
    finally:
        session.detach()
    return probes


@pytest.mark.parametrize("cms_desktop_case", CASES, indirect=True)
@pytest.mark.parametrize("sidebar", ["expanded", "collapsed"])
@pytest.mark.parametrize("plant", [KOREAN_PLANT, LONG_PLANT], ids=["korean", "long"])
def test_task8_fix1_detail_roles_and_hit_tested_chat(cms_page, sidebar, plant):
    from playwright.sync_api import expect

    errors = []
    cms_page.on("pageerror", lambda error: errors.append(str(error)))
    open_page(cms_page, "/dashboard2?dataset=1")
    expect(cms_page.locator("#diagnostic-ppt-export")).to_be_enabled()
    cms_page.evaluate("""async plant => {
      const {populateSummary} = await import('/static/modules/summary/summary.js?v=korean-ui-v1');
      populateSummary({equipment: {id: '1', name: '#2 Direct Cooling Pump DS', plant, sensorNumber: '56'}});
      await document.fonts.ready;
    }""", plant)
    if sidebar == "collapsed":
        cms_page.locator("#cms-sidebar-toggle").click()
    roles = cms_page.evaluate("""() => {
      const root = document.documentElement;
      const measure = () => [...document.querySelectorAll('.overview-fft-stats dt, .overview-fft-stats dd')].map(node => {
        const style = getComputedStyle(node);
        return {tag: node.tagName, text: node.textContent, size: style.fontSize,
          leading: style.lineHeight, weight: style.fontWeight};
      });
      const tokens = {'--cms-type-label': '17px', '--cms-leading-label': '26px',
        '--cms-type-body': '18px', '--cms-leading-body': '28px', '--cms-weight-strong': '500'};
      const originals = Object.keys(tokens).map(name =>
        [name, root.style.getPropertyValue(name), root.style.getPropertyPriority(name)]);
      const baseline = measure();
      try {
        Object.entries(tokens).forEach(([name, value]) => root.style.setProperty(name, value));
        return {baseline, changed: measure()};
      } finally {
        originals.forEach(([name, value, priority]) => value
          ? root.style.setProperty(name, value, priority) : root.style.removeProperty(name));
      }
    }""")
    measure = r"""() => {
      const launcher = document.querySelector('#chat-open');
      const floating = launcher.getBoundingClientRect();
      const collisions = [], clipped = [];
      let textCount = 0;
      for (const node of document.querySelectorAll(
        '#level-details strong, #level-details dt, #level-details dd, #level-details h3, #level-details p, '
        + '.overview-fft-stats dt, .overview-fft-stats dd, .equipment-metadata dt, .equipment-metadata dd, '
        + '.topbar a, .topbar label, .topbar select')) {
        if (!node.getClientRects().length || getComputedStyle(node).visibility === 'hidden') continue;
        textCount++;
        const range = document.createRange(); range.selectNodeContents(node);
        for (const rect of range.getClientRects()) {
          if (!rect.width || !rect.height) continue;
          for (let ancestor = node; ancestor && ancestor !== document.body; ancestor = ancestor.parentElement) {
            const box = ancestor.getBoundingClientRect(), style = getComputedStyle(ancestor);
            if ((['hidden', 'clip'].includes(style.overflowX) && (rect.left < box.left - 1 || rect.right > box.right + 1))
              || (['hidden', 'clip'].includes(style.overflowY) && (rect.top < box.top - 1 || rect.bottom > box.bottom + 1))) {
              clipped.push({text: node.textContent, ancestor: ancestor.id || ancestor.className});
            }
          }
          const left = Math.max(0, rect.left, floating.left), right = Math.min(innerWidth, rect.right, floating.right);
          const top = Math.max(0, rect.top, floating.top), bottom = Math.min(innerHeight, rect.bottom, floating.bottom);
          if (right <= left || bottom <= top) continue;
          const hit = document.elementFromPoint((left + right) / 2, (top + bottom) / 2);
          if (hit?.closest('#chat-open')) collisions.push({text: node.textContent,
            area: (right - left) * (bottom - top), hit: hit.id || hit.parentElement.id});
        }
      }
      const centerX = floating.x + floating.width / 2, centerY = floating.y + floating.height / 2;
      return {collisions, clipped, textCount, scrollY, width: innerWidth,
        scrollWidth: document.documentElement.scrollWidth,
        launcher: {x: floating.x, y: floating.y, width: floating.width, height: floating.height,
          reachable: !!document.elementFromPoint(centerX, centerY)?.closest('#chat-open')}};
    }"""
    states = {}
    cms_page.evaluate("scrollTo(0, 0)")
    states["top"] = cms_page.evaluate(measure)
    cms_page.locator("#level-details").evaluate("node => node.scrollIntoView({block: 'center'})")
    states["threshold"] = cms_page.evaluate(measure)
    cms_page.evaluate("scrollTo(0, document.documentElement.scrollHeight)")
    states["bottom"] = cms_page.evaluate(measure)
    cms_page.evaluate("scrollTo(0, 0)")
    variant = "long" if plant == LONG_PLANT else "korean"
    target = capture_page(cms_page, f"task8-fix1-detail-{variant}-{sidebar}")
    evidence = {"sidebar": sidebar, "variant": variant, "roles": roles, "states": states}
    target.with_suffix(".occlusion.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    assert roles["baseline"] and {item["tag"] for item in roles["baseline"]} == {"DT", "DD"}
    for item in roles["baseline"]:
        expected = ("13px", "20px", "600") if item["tag"] == "DT" else ("14px", "22px", "600")
        assert (item["size"], item["leading"], item["weight"]) == expected, item
    for item in roles["changed"]:
        expected = ("17px", "26px", "500") if item["tag"] == "DT" else ("18px", "28px", "500")
        assert (item["size"], item["leading"], item["weight"]) == expected, item
    for state, metrics in states.items():
        assert metrics["textCount"] > 10, (state, metrics)
        assert not metrics["collisions"], (state, metrics["collisions"])
        assert not metrics["clipped"], (state, metrics["clipped"])
        assert metrics["scrollWidth"] <= metrics["width"] + 1
    assert states["top"]["launcher"]["reachable"]
    assert min(states["top"]["launcher"][axis] for axis in ("width", "height")) >= 36
    launcher = cms_page.get_by_role("button", name="AI \ubd84\uc11d \ub300\ud654 \uc5f4\uae30", exact=True)
    launcher.focus()
    cms_page.keyboard.press("Enter")
    expect(launcher).to_have_attribute("aria-expanded", "true")
    expect(cms_page.locator("#chat-input")).to_be_focused()
    cms_page.locator("#chat-input").fill("Show the current measurement evidence")
    cms_page.locator("#chat-send").click()
    expect(cms_page.locator("#chat-messages")).to_contain_text("UI baseline stub chat")
    cms_page.keyboard.press("Escape")
    expect(launcher).to_have_attribute("aria-expanded", "false")
    expect(launcher).to_be_focused()
    cms_page.locator("#dataset-select-toggle").click()
    expect(cms_page.locator("#dataset-select")).to_be_visible()
    chooser = cms_page.evaluate(measure)
    assert not chooser["collisions"] and not chooser["clipped"], chooser
    assert not errors, errors


@pytest.mark.parametrize("cms_desktop_case", CASES, indirect=True)
@pytest.mark.parametrize("path", ROUTES)
def test_task8_final_route_roles_glyphs_and_geometry(cms_page, path):
    errors = []
    cms_page.on("pageerror", lambda error: errors.append(str(error)))
    assert open_page(cms_page, path).status == 200
    cms_page.wait_for_function("""() => [...document.querySelectorAll('canvas.canvas-track')].every(canvas =>
      Math.abs(canvas.width - canvas.getBoundingClientRect().width * devicePixelRatio) <= 1)""")
    measure_shell = """() => {
      const sidebar = document.querySelector('#cms-sidebar');
      const main = document.querySelector('main');
      const box = main.getBoundingClientRect();
      const style = getComputedStyle(main);
      return {sidebar: sidebar.getBoundingClientRect().width, mainX: box.x + scrollX,
        mainWidth: box.width, grid: style.gridTemplateColumns, margin: style.marginLeft};
    }"""
    shell = {}
    for mode, width in [("expanded", 244), ("collapsed", 76)]:
        before = cms_page.evaluate(measure_shell)
        assert before["sidebar"] == width
        cms_page.locator("#cms-sidebar").hover()
        assert cms_page.evaluate(measure_shell) == before
        cms_page.locator("#cms-sidebar-toggle").focus()
        cms_page.keyboard.press("Tab")
        assert cms_page.evaluate("document.activeElement.matches('#cms-sidebar nav a')")
        assert cms_page.evaluate(measure_shell) == before
        shell[mode] = before
        cms_page.locator("#cms-sidebar-toggle").click()
    cms_page.mouse.move(cms_page.viewport_size["width"] - 2, 0)
    cms_page.evaluate("scrollTo(0, 0)")
    evidence = cms_page.evaluate(r"""() => {
      const visible = node => node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden';
      const selectors = {
        page: 'main h1', section: 'main h2, main h3',
        label: 'main label, main dt, main th, main .eyebrow',
        value: 'main dd, main .fft-analysis-item strong, main [data-cms-role="kpi"]',
        table: 'main td, main .table-row > *',
        control: 'main button, main select, main input:not([type="checkbox"]):not([type="radio"])',
        badge: 'main .badge, main .status-badge, main .status-chip, main .pill, main .tag',
        chart: 'main svg text, main [data-cms-role="chart"] label, main [data-cms-role="chart"] em',
      };
      const probes = {};
      const roles = Object.fromEntries(Object.entries(selectors).map(([role, selector]) => {
        const nodes = [...document.querySelectorAll(selector)].filter(visible);
        const probe = nodes.find(node => node.tagName === 'BUTTON' && node.textContent.trim())
          || nodes.find(node => !['SELECT', 'INPUT'].includes(node.tagName) && node.textContent.trim());
        if (probe) {
          probe.setAttribute(`data-task8-font-${role}`, '');
          probes[role] = {text: probe.textContent.trim().slice(0, 100), tag: probe.tagName};
        }
        return [role, nodes.map(node => {
          const style = getComputedStyle(node);
          const box = node.getBoundingClientRect();
          const range = document.createRange(); range.selectNodeContents(node);
          const rects = [...range.getClientRects()].filter(rect => rect.width && rect.height);
          const clippedBy = [];
          let scrollableX = false, scrollableY = false;
          for (let ancestor = node; ancestor && ancestor !== document.body; ancestor = ancestor.parentElement) {
            const clip = ancestor.getBoundingClientRect(); const clipStyle = getComputedStyle(ancestor);
            if (rects.some(rect => (!scrollableX && ['hidden', 'clip'].includes(clipStyle.overflowX)
                && (rect.left < clip.left - 1 || rect.right > clip.right + 1))
              || (!scrollableY && ['hidden', 'clip'].includes(clipStyle.overflowY)
                && (rect.top < clip.top - 1 || rect.bottom > clip.bottom + 1)))) {
              clippedBy.push(ancestor.id || ancestor.className);
            }
            scrollableX ||= ['auto', 'scroll'].includes(clipStyle.overflowX) && ancestor.scrollWidth > ancestor.clientWidth;
            scrollableY ||= ['auto', 'scroll'].includes(clipStyle.overflowY) && ancestor.scrollHeight > ancestor.clientHeight;
          }
          return {text: node.textContent.trim().slice(0, 100), size: style.fontSize, leading: style.lineHeight,
            spacing: style.letterSpacing, width: box.width, height: box.height,
            glyphHeight: rects.length ? Math.max(...rects.map(rect => rect.bottom)) - Math.min(...rects.map(rect => rect.top)) : 0,
            clippedBy};
        })];
      }));
      const overlaps = [];
      for (const parent of document.querySelectorAll('.chart-grid, .equipment-metadata, .stat-grid, .kpi-grid')) {
        const children = [...parent.children].filter(visible);
        children.forEach((left, index) => children.slice(index + 1).forEach(right => {
          const first = left.getBoundingClientRect(), second = right.getBoundingClientRect();
          if (Math.min(first.right, second.right) - Math.max(first.left, second.left) > 2
            && Math.min(first.bottom, second.bottom) - Math.max(first.top, second.top) > 2) {
            overlaps.push({parent: parent.className, left: left.className, right: right.className});
          }
        }));
      }
      const canvases = [...document.querySelectorAll('main canvas')].map(canvas => {
        const context = canvas.getContext('2d');
        const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
        const colors = new Set();
        for (let offset = 0; offset < pixels.length; offset += Math.max(4, Math.floor(pixels.length / 16000 / 4) * 4)) {
          colors.add([...pixels.slice(offset, offset + 4)].join(','));
        }
        const box = canvas.getBoundingClientRect();
        return {width: canvas.width, height: canvas.height, visibleWidth: box.width,
          visibleHeight: box.height, colors: colors.size, font: context.font};
      });
      const plotly = [...document.querySelectorAll('main .js-plotly-plot')].map(node => ({
        id: node.id, traces: node.data?.length, font: node._fullLayout?.font,
        labels: node.querySelectorAll('svg text').length,
      }));
      return {roles, probes, overlaps, canvases, plotly, width: innerWidth,
        scrollWidth: document.documentElement.scrollWidth,
        assets: [...document.querySelectorAll('link[rel="stylesheet"], script[src]')]
          .map(node => new URL(node.href || node.src).pathname)};
    }""")
    evidence["probes"] = platform_fonts(cms_page, evidence["probes"])
    evidence["shell"] = shell
    target = capture_page(cms_page, "task8-final-route-" + (path.strip("/") or "root"))
    target.with_suffix(".acceptance.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    assert not errors, errors
    assert evidence["scrollWidth"] <= evidence["width"] + 1
    assert not evidence["overlaps"], evidence["overlaps"]
    assert len(evidence["assets"]) == len(set(evidence["assets"]))
    assert evidence["roles"]["page"]
    for role, items in evidence["roles"].items():
        assert all(not item["clippedBy"] for item in items), (path, role, items)
        assert all(item["spacing"] in {"0px", "normal"} for item in items), (path, role, items)
    assert all((item["size"], item["leading"]) == ("24px", "32px") for item in evidence["roles"]["page"])
    assert all(item["size"] == "14px" and item["height"] >= 36 for item in evidence["roles"]["control"])
    approved = {"Pretendard", "Noto Sans KR", "Noto Sans CJK KR", "Malgun Gothic", "Apple SD Gothic Neo"}
    for role, probe in evidence["probes"].items():
        assert sum(font["glyphCount"] for font in probe["fonts"]) > 0, (path, role, probe)
        if any("\uac00" <= character <= "\ud7a3" for character in probe["text"]):
            assert any(font["familyName"] in approved and font["glyphCount"] > 0 for font in probe["fonts"]), (path, role, probe)
    for canvas in evidence["canvases"]:
        assert min(canvas["width"], canvas["height"], canvas["visibleWidth"], canvas["visibleHeight"]) > 0
        assert canvas["colors"] > 1 and canvas["font"].startswith("12px "), canvas
    for chart in evidence["plotly"]:
        assert chart["traces"] > 0 and chart["labels"] > 0 and chart["font"]["size"] == 12, chart


@pytest.mark.parametrize("cms_desktop_case", CASES, indirect=True)
def test_task8_detail_tracks_stay_unequal_and_stable_on_hover_and_tab(cms_page):
    open_page(cms_page, "/dashboard2?dataset=1")
    cms_page.wait_for_function("document.querySelector('#trend-chart')?.data?.length > 0")
    measure = """() => {
      const grid = document.querySelector('.chart-grid');
      const children = [...grid.children].map(element => {
        const box = element.getBoundingClientRect();
        return {x: box.x + scrollX, y: box.y + scrollY, width: box.width,
          height: box.height, right: box.right + scrollX};
      });
      return {columns: getComputedStyle(grid).gridTemplateColumns, children};
    }"""
    baseline = cms_page.evaluate(measure)
    assert len(baseline["children"]) == 2
    trend, evidence = baseline["children"]
    assert trend["width"] > evidence["width"] >= 360
    assert abs(trend["y"] - evidence["y"]) <= 1
    assert evidence["x"] - trend["right"] == 24
    states = {"baseline": baseline}
    cms_page.locator(".trend-card").hover()
    states["hover"] = cms_page.evaluate(measure)
    cms_page.locator("#trend-expand").focus()
    cms_page.keyboard.press("Tab")
    focused = cms_page.evaluate("({id: document.activeElement.id, tag: document.activeElement.tagName})")
    assert focused["id"] != "trend-expand" and focused["tag"] != "BODY"
    states["tab"] = cms_page.evaluate(measure)
    assert states["hover"] == states["tab"] == baseline
    target = capture_page(cms_page, "task8-final-detail-stable-tracks")
    target.with_suffix(".tracks.json").write_text(json.dumps({"states": states, "focused": focused}, indent=2), encoding="utf-8")


@pytest.mark.parametrize("cms_desktop_case", CASES, indirect=True)
@pytest.mark.parametrize("plant", [KOREAN_PLANT, LONG_PLANT], ids=["korean-example", "long-name"])
def test_metadata_uses_role_typography(cms_page, cms_desktop_case, plant):
    open_page(cms_page, "/dashboard2?dataset=1")
    cms_page.wait_for_function("document.querySelector('#plant-name').textContent !== '--'")
    response = cms_page.context.request.get("/api/dashboard/1")
    assert response.ok
    dashboard = response.json()
    dashboard["equipment"].update(plant=plant, sensorNumber="56")
    cms_page.evaluate("""async data => {
      const { populateSummary } = await import('/static/modules/summary/summary.js?v=korean-ui-v1');
      populateSummary(data);
      await document.fonts.ready;
    }""", dashboard)
    assert cms_page.locator("#plant-name").inner_text() == plant
    assert cms_page.locator("#sensor-number").inner_text() == "56"
    metrics = cms_page.locator(".equipment-metadata").evaluate("""element => {
      function measure(node) {
        const style = getComputedStyle(node);
        const range = document.createRange();
        range.selectNodeContents(node);
        const rects = [...range.getClientRects()].filter(rect => rect.width > 0);
        const first = rects[0];
        const bounds = node.getBoundingClientRect();
        return { text: node.textContent, size: style.fontSize, leading: style.lineHeight,
          weight: style.fontWeight, letterSpacing: style.letterSpacing,
          firstTop: first.top, firstBottom: first.bottom, lines: rects.length,
          clipped: rects.some(rect => rect.left < bounds.left - 1 || rect.right > bounds.right + 1
            || rect.top < bounds.top - 1 || rect.bottom > bounds.bottom + 1),
          height: bounds.height };
      }
      return { labels: [...element.querySelectorAll('dt')].map(measure),
        values: [...element.querySelectorAll('dd')].map(measure) };
    }""")
    probes = {}
    for role, selector in {"label": ".equipment-metadata dt", "value": "#plant-name", "sensor": "#sensor-number"}.items():
        node = cms_page.locator(selector).first
        node.evaluate("(element, role) => element.setAttribute(`data-task8-font-${role}`, '')", role)
        probes[role] = {"text": node.inner_text()}
    metrics["renderedFonts"] = platform_fonts(cms_page, probes)
    assert all(sum(font["glyphCount"] for font in probe["fonts"]) > 0
               for probe in metrics["renderedFonts"].values())
    target = capture_page(cms_page, "task8-final-metadata-" + ("long" if plant == LONG_PLANT else "korean"))
    target.with_suffix(".typography.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    label_sizes = {item["size"] for item in metrics["labels"]}
    value_sizes = {item["size"] for item in metrics["values"]}
    value_line_heights = {item["leading"] for item in metrics["values"]}
    assert label_sizes == {"13px"}
    assert value_sizes == {"14px"}
    assert value_line_heights == {"22px"}
    assert {item["leading"] for item in metrics["labels"]} == {"20px"}
    for role in ("labels", "values"):
        items = metrics[role]
        assert max(item["firstTop"] for item in items) - min(item["firstTop"] for item in items) <= 1
        assert max(item["firstBottom"] for item in items) - min(item["firstBottom"] for item in items) <= 1
        assert not any(item["clipped"] for item in items)
        assert {item["letterSpacing"] for item in items} <= {"0px", "normal"}
    if plant == LONG_PLANT:
        assert metrics["values"][0]["lines"] > 1
        assert metrics["values"][0]["height"] > metrics["values"][1]["height"]


@pytest.mark.parametrize("block_fonts", [False, True], ids=["normal", "korean-fallback"])
def test_semantic_tokens_and_actual_korean_font(cms_page, block_fonts):
    if block_fonts:
        cms_page.route("**/*", lambda route: route.abort() if route.request.resource_type == "font" else route.fallback())
    open_page(cms_page, "/dashboard2?dataset=1")
    cms_page.evaluate("""async plant => {
      const { populateSummary } = await import('/static/modules/summary/summary.js?v=korean-ui-v1');
      populateSummary({ equipment: { id: '1', name: plant, plant, sensorNumber: '56' } });
      await document.fonts.ready;
    }""", KOREAN_PLANT)
    evidence = cms_page.evaluate("""() => {
      const style = getComputedStyle(document.documentElement);
      const tokens = Object.fromEntries([...style].filter(name => name.startsWith('--cms-'))
        .map(name => [name, style.getPropertyValue(name).trim()]));
      const links = [...document.querySelectorAll('link[rel=stylesheet]')].map(link => link.getAttribute('href'));
      return { tokens, links, heading: getComputedStyle(document.querySelector('#equipment-title')).fontSize };
    }""")
    session = cms_page.context.new_cdp_session(cms_page)
    try:
        session.send("DOM.enable")
        session.send("CSS.enable")
        root = session.send("DOM.getDocument")["root"]["nodeId"]
        node = session.send("DOM.querySelector", {"nodeId": root, "selector": "#plant-name"})["nodeId"]
        evidence["fonts"] = session.send("CSS.getPlatformFontsForNode", {"nodeId": node})["fonts"]
    finally:
        session.detach()
    target = capture_page(cms_page, "task2-tokens-" + ("fallback" if block_fonts else "normal"))
    target.with_suffix(".fonts.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    tokens = evidence["tokens"]
    for role, size, leading, weight in [("page", 24, 32, 700), ("section", 16, 24, 600),
            ("body", 14, 22, 400), ("label", 13, 20, 400), ("kpi", 28, 36, 700), ("chart", 12, 18, 400)]:
        assert tokens[f"--cms-type-{role}"] == f"{size}px"
        assert tokens[f"--cms-leading-{role}"] == f"{leading}px"
        assert tokens[f"--cms-weight-{role}"] == str(weight)
    for spacing in [4, 8, 12, 16, 24, 32]:
        assert tokens[f"--cms-space-{spacing}"] == f"{spacing}px"
    assert tokens["--cms-control-height"] == "36px"
    assert tokens["--cms-nav-expanded"] == "244px"
    assert tokens["--cms-nav-collapsed"] == "76px"
    assert evidence["heading"] == "24px"
    token_links = [link for link in evidence["links"] if "cms-tokens.css" in link]
    assert len(token_links) == 1
    assert evidence["links"].index(token_links[0]) < next(index for index, link in enumerate(evidence["links"]) if "styles.css" in link)
    approved = {"Pretendard", "Noto Sans KR", "Noto Sans CJK KR", "Malgun Gothic", "Apple SD Gothic Neo"}
    assert any(font["familyName"] in approved and font["glyphCount"] > 0 for font in evidence["fonts"])


@pytest.mark.parametrize("selector,role,weight_token,weight", [
    (".dashboard2 .topbar .dataset-select-wrap label", "label", "strong", "600"),
    (".dashboard2 .topbar #dataset-select", "body", "body", "400"),
    ("#fft-ai-period", "label", "label", "400"),
    ("#overview-fft-measured-at", "label", "label", "400"),
    (".overview-fft-stats div:first-child dt", "label", "strong", "600"),
    (".overview-fft-stats div:first-child dd", "body", "strong", "600"),
  ], ids=["equipment-label", "equipment-select", "fft-period-help", "measured-at-help",
      "fft-stat-label", "fft-stat-value"])
def test_equipment_selector_and_help_follow_role_tokens(cms_page, selector, role, weight_token, weight):
    open_page(cms_page, "/dashboard2?dataset=1")
    toggle = cms_page.locator("#dataset-select-toggle")
    toggle.click()
    assert toggle.get_attribute("aria-expanded") == "true"
    consumer = cms_page.locator(selector)
    assert consumer.count() == 1
    assert consumer.is_visible()
    evidence = cms_page.evaluate("""({ selector, role, weightToken }) => {
      const element = document.querySelector(selector);
      const root = document.documentElement;
      const measure = () => {
        const style = getComputedStyle(element);
        return { size: style.fontSize, leading: style.lineHeight, weight: style.fontWeight };
      };
      const tokens = {
        [`--cms-type-${role}`]: role === 'body' ? '18px' : '17px',
        [`--cms-leading-${role}`]: role === 'body' ? '28px' : '26px',
        [`--cms-weight-${weightToken}`]: '500',
      };
      const originals = Object.keys(tokens).map(name =>
        [name, root.style.getPropertyValue(name), root.style.getPropertyPriority(name)]);
      const baseline = measure();
      try {
        Object.entries(tokens).forEach(([name, value]) => root.style.setProperty(name, value));
        return { selector, baseline, changed: measure() };
      } finally {
        originals.forEach(([name, value, priority]) => value
          ? root.style.setProperty(name, value, priority) : root.style.removeProperty(name));
      }
    }""", {"selector": selector, "role": role, "weightToken": weight_token})
    target = capture_page(cms_page, "task2-review-" + selector.split()[-1].strip(".#"))
    target.with_suffix(".typography.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    assert evidence["baseline"] == {
        "size": "14px" if role == "body" else "13px",
        "leading": "22px" if role == "body" else "20px",
        "weight": weight,
    }
    assert evidence["changed"] == {
        "size": "18px" if role == "body" else "17px",
        "leading": "28px" if role == "body" else "26px",
        "weight": "500",
    }


def test_common_role_consumers_and_live_chart_fonts(cms_page):
    open_page(cms_page, "/dashboard2?dataset=1")
    cms_page.wait_for_function("document.querySelectorAll('.js-plotly-plot').length === 3")
    cms_page.locator("#work-order-open").click()
    selectors = {
        "page": "#equipment-title", "section": "#ai-analysis-title",
        "body": "#ai-analysis-description", "label": ".work-order-field",
        "input": ".work-order-field input", "button": "#ai-analysis-run",
        "kpi": "#overview-fft-result", "help": ".chart-period-label",
    }
    evidence = cms_page.evaluate("""selectors => {
      const roles = Object.fromEntries(Object.entries(selectors).map(([role, selector]) => {
        const element = document.querySelector(selector);
        const style = getComputedStyle(element);
        return [role, { size: style.fontSize, leading: style.lineHeight, weight: style.fontWeight,
          height: element.getBoundingClientRect().height, letterSpacing: style.letterSpacing }];
      }));
      const charts = [...document.querySelectorAll('.js-plotly-plot')].map(element => {
        const layout = element._fullLayout;
        return { id: element.id, fonts: [layout.font, layout.xaxis.tickfont, layout.yaxis.tickfont,
          layout.yaxis.title.font, layout.legend?.font, layout.hoverlabel.font].filter(Boolean) };
      });
      return { roles, charts };
    }""", selectors)
    target = capture_page(cms_page, "task2-role-consumers")
    target.with_suffix(".typography.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    for role, size, leading in [("page", 24, 32), ("section", 16, 24), ("body", 14, 22),
            ("label", 13, 20), ("input", 14, 22), ("button", 14, 22), ("kpi", 28, 36), ("help", 13, 20)]:
        assert evidence["roles"][role]["size"] == f"{size}px", role
        assert evidence["roles"][role]["leading"] == f"{leading}px", role
    assert evidence["roles"]["input"]["height"] >= 36
    assert len(evidence["charts"]) == 3
    for chart in evidence["charts"]:
        assert len(chart["fonts"]) >= 5
        assert {font["size"] for font in chart["fonts"]} == {12}, chart
        assert all("Pretendard" in font["family"] and "Malgun Gothic" in font["family"] for font in chart["fonts"])