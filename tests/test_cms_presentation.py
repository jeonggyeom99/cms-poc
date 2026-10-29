import asyncio
import ast
from html.parser import HTMLParser
import json
from pathlib import Path
import re

import httpx
import pytest

from app.main import create_app


SLOTS = ("assets", "sidebar", "scripts", "body-attributes")
PAGE = '''<!doctype html><html><head><!-- cms:assets -->
<style>.example { color: red; }</style></head>
<body <!-- cms:body-attributes -->><!-- cms:sidebar -->
<main>$unrelated ${literal} 비용 $10</main><!-- cms:scripts --></body></html>'''
ROUTES = ("/", "/equipment-status2", "/dashboard_ui6", "/dashboard_ui2",
          "/history2", "/history", "/main_ct", "/main_sv", "/dashboard2", "/dashboard",
          "/static/equipment-status2.html", "/static/kpi-dashboard-concept.html",
          "/static/history.html", "/static/main-workspace.html", "/static/index.html",
          "/main_ct1", "/main_ct2", "/main_ct3", "/main_sv1", "/main_sv2", "/main_sv3",
          "/static/main-control.html", "/main", "/dashboard_ui1", "/dashboard_ui3",
          "/dashboard_ui4", "/dashboard_ui5", "/dashboard_ui1_canvas")
RETAINED = ("main", "dashboard-ui1-kpi", "dashboard-ui1-canvas", "design-lab",
                        "dashboard-ui5", "history2", "dashboard-ui1-fresh", "dashboard-lab",
                        "equipment-status")
MIGRATED_JS = (
    "core/cms-operations", "dashboard/controller", "equipment-status/controller",
    "equipment-status/equipment-status2", "history/controller", "main/controller",
    "main/control-dashboard", "main/dashboard-chart-panels", "main/dashboard-lab",
    "main/dashboard-ui1-canvas", "main/dashboard-ui5", "main/kpi-concept", "main/workspace",
)


def test_vscode_task_labels_resolve_unambiguously():
    tasks = json.loads(Path(".vscode/tasks.json").read_text(encoding="utf-8"))["tasks"]
    labels = [task["label"] for task in tasks]
    duplicates = sorted({label for label in labels if labels.count(label) > 1})
    assert not duplicates, duplicates


class Elements(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.tags = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_renderer_preserves_page_literals_and_escapes_attributes():
    from app.presentation import render_operations_page

    rendered = render_operations_page(
        PAGE, active_page='history" onload="bad', body_classes=('custom" onclick="bad',),
    )
    assert '<main>$unrelated ${literal} 비용 $10</main>' in rendered
    assert '.example { color: red; }' in rendered
    tags = Elements(rendered).tags
    body = next(attrs for tag, attrs in tags if tag == 'body')
    assert body['class'] == 'custom" onclick="bad'
    assert body['data-cms-active-page'] == 'history" onload="bad'
    assert 'onclick' not in body and 'onload' not in body
    assert '<!-- cms:' not in rendered


@pytest.mark.parametrize('slot', SLOTS)
@pytest.mark.parametrize('count', [0, 2])
def test_renderer_rejects_missing_or_duplicate_slots(slot, count):
    from app.presentation import render_operations_page

    marker = f'<!-- cms:{slot} -->'
    with pytest.raises(ValueError, match=slot):
        render_operations_page(PAGE.replace(marker, marker * count), active_page='history')


@pytest.mark.parametrize('path', ROUTES)
def test_shared_shell_assets_once(path):
    async def check():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app()), base_url='http://test',
        ) as client:
            response = await client.get(path)
        assert response.status_code == 200
        source = response.text
        tags = Elements(source).tags
        for asset in ('cms-tokens.css', 'cms-operations.css', 'cms-sidebar-icons.css'):
            matches = [attrs for tag, attrs in tags if tag == 'link'
                       and attrs.get('href', '').split('?')[0] == f'/static/{asset}']
            assert len(matches) == 1, (path, asset, len(matches))
        assert sum(tag == 'script' and attrs.get('src', '').split('?')[0]
                   == '/static/modules/core/cms-operations.js' for tag, attrs in tags) == 1
        assert sum(attrs.get('id') == 'cms-sidebar' for tag, attrs in tags) == 1
        assets = [attrs.get('href') if tag == 'link' else attrs.get('src')
              for tag, attrs in tags if tag == 'link' or tag == 'script' and attrs.get('src')]
        asset_paths = [asset.split('?')[0] for asset in assets if asset]
        assert len(asset_paths) == len(set(asset_paths)), (path, asset_paths)
        assert '<!-- cms:' not in source
        styles = [attrs['href'] for tag, attrs in tags if tag == 'link' and 'href' in attrs]
        assert styles[0].startswith('/static/cms-tokens.css')
        assert source.index('/static/cms-tokens.css') < source.index('<style') if '<style' in source else True
        assert next(attrs for tag, attrs in tags if tag == 'body')['data-cms-nav'] == 'expanded'

    asyncio.run(check())


def test_static_presentation_has_single_owner():
    static = Path("app/static")
    main = ast.parse(Path("app/main.py").read_text(encoding="utf-8"))
    assert not [node.value for node in ast.walk(main)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
                and re.search(r"<style\b", node.value, re.I)]
    for owner in MIGRATED_JS:
        source = (static / "modules" / f"{owner}.js").read_text(encoding="utf-8")
        assert not re.search(r"createElement\s*\(\s*['\"`]style['\"`]", source), owner
        assert not re.search(r"\b\w*[Ss]tyle\.textContent\s*=|<style\b", source), owner
    for path in static.glob("*.css"):
        source = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        for selector, declarations in re.findall(r"([^{}]+)\{([^{}]*)\}", source):
            if re.search(r"sidebar|cms-nav", selector) and re.search(r":hover|:focus", selector):
                properties = re.findall(r"(?:^|;)\s*([\w-]+)\s*:", declarations)
                forbidden = [name for name in properties if name in {
                    "width", "min-width", "max-width", "inline-size", "min-inline-size", "max-inline-size",
                } or name.startswith(("grid", "margin"))]
                assert not forbidden, (path, selector, forbidden)


def test_kpi_alias_preserves_comparison_controls():
    async def check():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app()), base_url='http://test',
        ) as client:
            response = await client.get('/dashboard_ui2')
        tags = Elements(response.text).tags
        body = next(attrs for tag, attrs in tags if tag == 'body')
        assert 'dashboard-ui6' not in body['class'].split()
        controls = [attrs.get('href') for tag, attrs in tags
                    if tag == 'a' and 'btn' in attrs.get('class', '').split()]
        assert controls == ['/dashboard_ui1', '/dashboard_ui2']

    asyncio.run(check())


@pytest.mark.parametrize("owner", RETAINED)
def test_retained_static_is_complete_and_explicitly_assembled(owner):
    from app.presentation import render_retained_page

    source = (Path("app/static") / f"{owner}.html").read_text(encoding="utf-8")
    assert "<!-- cms:" not in source
    for candidate in (source, render_retained_page(source, active_page="overview")):
        tags = Elements(candidate).tags
        assert sum(attrs.get("id") == "cms-sidebar" for tag, attrs in tags) == 1
        for asset in ("cms-tokens.css", "cms-operations.css", "cms-sidebar-icons.css"):
            assert sum(tag == "link" and attrs.get("href", "").split("?")[0] == f"/static/{asset}" for tag, attrs in tags) == 1
        assert sum(tag == "script" and attrs.get("src", "").split("?")[0] == "/static/modules/core/cms-operations.js" for tag, attrs in tags) == 1
        assert "<!-- cms:" not in candidate
    with pytest.raises(ValueError, match="assets"):
        render_retained_page(source.replace("<!-- cms-static:assets -->", ""), active_page="overview")