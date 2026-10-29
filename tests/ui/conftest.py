from __future__ import annotations

import os
import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.ui.api_controls import ApiControls
from tests.ui.side_effects import SafeSideEffects


@pytest.fixture()
def cms_api_controls(cms_page):
    controls = ApiControls(cms_page)
    try:
        yield controls
    finally:
        for control in controls.controls.values():
            control.release()


def _stub_side_effect_endpoints(page, base_url=None) -> SafeSideEffects:
    return SafeSideEffects(page, base_url or os.environ.get("CMS_UI_BASE_URL", "http://127.0.0.1:8000"))


@pytest.fixture()
def cms_side_effects(cms_page):
    return cms_page.cms_side_effects


@pytest.fixture(scope="session")
def cms_base_url() -> str:
    return os.environ.get("CMS_UI_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


@pytest.fixture(scope="session")
def playwright_instance() -> Iterator:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        yield playwright


@pytest.fixture(scope="session")
def cms_browser(playwright_instance) -> Iterator:
    browser = playwright_instance.chromium.launch(headless=True)
    try:
        yield browser
    finally:
        browser.close()


@pytest.fixture()
def cms_desktop_case(request):
    return getattr(request, "param", (1440, 900, 1))


@pytest.fixture()
def cms_page(cms_browser, cms_base_url, cms_desktop_case, request):
    width, height, zoom = cms_desktop_case
    context = cms_browser.new_context(
        base_url=cms_base_url,
        viewport={"width": round(width / zoom), "height": round(height / zoom)},
        device_scale_factor=zoom,
        locale="ko-KR",
        service_workers="block",
        accept_downloads=True,
    )
    context.set_default_timeout(20000)
    page = context.new_page()
    page.cms_desktop_case = cms_desktop_case
    page.cms_side_effects = _stub_side_effect_endpoints(page, cms_base_url)
    try:
        yield page
    finally:
        page.unroute_all(behavior="wait")
        context.unroute_all(behavior="wait")
        artifact_dir = Path(".cache/cms-ui")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        identity = re.sub(r"[^A-Za-z0-9._-]+", "-", request.node.name)
        audit = {"intercepted": [{key: value for key, value in item.items() if key != "request"} | {
            "recordId": item["request"].get("recordId"), "until": item["request"].get("until"),
        } for item in page.cms_side_effects.requests], "blocked": page.cms_side_effects.blocked}
        (artifact_dir / f"{identity}-{width}x{height}-zoom{round(zoom * 100)}.audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
        context.close()
        unexpected = [item for item in audit["blocked"] if item["reason"] == "unregistered API or write" and item["url"] not in page.cms_side_effects.expected_blocked]
        assert not unexpected, f"Unexpected requests were safely blocked: {unexpected}"
