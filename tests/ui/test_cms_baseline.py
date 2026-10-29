from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page

from tests.ui.helpers import capture_page, open_page, text_metrics


pytestmark = pytest.mark.ui


ROUTES = [
    "/",
    "/equipment-status2",
    "/dashboard_ui6",
    "/dashboard",
    "/dashboard2",
    "/history",
    "/history2",
    "/main_ct",
    "/main_sv",
    "/main_ct1",
    "/main_ct2",
    "/main_ct3",
    "/main_sv1",
    "/main_sv2",
    "/main_sv3",
    "/main",
    "/dashboard_ui1",
    "/dashboard_ui2",
    "/dashboard_ui3",
    "/dashboard_ui4",
    "/dashboard_ui5",
    "/dashboard_ui1_canvas",
    "/static/history2.html",
    "/static/dashboard-ui1-fresh.html",
    "/static/dashboard-lab.html",
]


@pytest.mark.parametrize("path", ROUTES)
@pytest.mark.parametrize("cms_desktop_case", [(1280, 800, 1), (1440, 900, 1), (1920, 1080, 1)], indirect=True)
def test_primary_routes_render(cms_page: Page, path: str) -> None:
    page_errors: list[str] = []
    cms_page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    response = open_page(cms_page, path)
    capture_page(cms_page, f"baseline-route-{path.strip('/').replace('/', '-') or 'root'}")

    assert response is not None
    assert response.status == 200
    assert cms_page.locator("main").count() >= 1
    assert page_errors == []


def test_negative_state_inventory(cms_page: Page, cms_api_controls) -> None:
    from playwright.sync_api import expect

    gate = cms_api_controls.hold("/api/datasets")
    response = cms_page.goto("/equipment-status2", wait_until="domcontentloaded")
    expect(cms_page.locator("#equipment-status-list")).to_contain_text("불러오는 중")
    cms_page.wait_for_function("() => document.readyState === 'complete'")
    assert gate.wait_until_intercepted(cms_page) >= 1
    capture_page(cms_page, "negative-loading-equipment-status2")
    assert response.status == 200
    gate.release()
    expect(cms_page.locator(".equipment-status-equipment").first).to_be_visible()

    cms_page.locator("#equipment-status-name").fill("__cms_no_matching_equipment__")
    expect(cms_page.locator("#equipment-status-count")).to_have_text("0개 설비")
    expect(cms_page.locator("#equipment-status-list .equipment-status-empty")).to_have_text("조건에 맞는 설비가 없습니다.")
    expect(cms_page.locator(".equipment-status-equipment")).to_have_count(0)
    capture_page(cms_page, "negative-empty-equipment-status2")

    empty = cms_api_controls.empty_history()
    open_page(cms_page, "/history2")
    assert empty.hits == 1
    expect(cms_page.locator("#history-list")).to_contain_text("조건에 맞는 이력이 없습니다.")
    capture_page(cms_page, "negative-empty-history2")

    error = cms_api_controls.error("/api/history")
    open_page(cms_page, "/history2")
    assert error.hits == 1
    expect(cms_page.locator("#history-notice")).to_be_visible()
    expect(cms_page.locator("#history-notice")).to_contain_text("UI local API error")
    capture_page(cms_page, "negative-error-history2")


def test_desktop_navigation_and_font_baseline(cms_page: Page) -> None:
    open_page(cms_page, "/equipment-status2")
    capture_page(cms_page, "baseline-links-equipment-status2")
    assert cms_page.locator('a[href="/dashboard_ui6"]').count() >= 1
    assert cms_page.locator('a[href="/history2"]').count() >= 1
    assert cms_page.locator('a[href="/main_ct"]').count() >= 1

    metrics = text_metrics(cms_page.locator("body"))
    assert isinstance(metrics.get("fontFamily"), str)
    assert metrics["fontFamily"].strip() != ""
