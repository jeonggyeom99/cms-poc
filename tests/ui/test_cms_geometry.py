from __future__ import annotations

import json

import pytest

from tests.ui.helpers import capture_page, open_page, text_metrics


pytestmark = pytest.mark.ui


@pytest.mark.parametrize("cms_desktop_case", [(1280, 800, 1), (1440, 900, 1), (1920, 1080, 1), (1440, 900, 1.25)], indirect=True)
def test_desktop_geometry(cms_page, cms_desktop_case):
    from PIL import Image

    open_page(cms_page, "/equipment-status2")
    target = capture_page(cms_page, "desktop-geometry-equipment-status2")
    geometry = json.loads(target.with_suffix(".json").read_text(encoding="utf-8"))
    width, height, zoom = cms_desktop_case
    assert geometry["innerWidth"] == round(width / zoom)
    assert geometry["innerHeight"] == round(height / zoom)
    assert geometry["rootClientWidth"] == round(width / zoom)
    assert geometry["devicePixelRatio"] == zoom
    assert geometry["requestedViewport"] == {"width": width, "height": height}
    assert geometry["main"]["width"] > 0
    assert geometry["main"]["x"] >= 0
    assert geometry["main"]["right"] <= geometry["innerWidth"] + 1
    with Image.open(target) as image:
        assert image.width == width
        assert image.height >= height


@pytest.mark.parametrize("block_fonts", [False, True], ids=["normal", "blocked-webfonts"])
def test_korean_font_availability(cms_page, block_fonts):
    if block_fonts:
        cms_page.route("**/*", lambda route: route.abort() if route.request.resource_type == "font" else route.fallback())
    open_page(cms_page, "/equipment-status2")
    heading = cms_page.locator("h1").first
    assert any("\uac00" <= character <= "\ud7a3" for character in heading.inner_text())
    metrics = text_metrics(heading)
    assert metrics["rangeBottom"] > metrics["rangeTop"]
    session = cms_page.context.new_cdp_session(cms_page)
    try:
        session.send("DOM.enable")
        session.send("CSS.enable")
        root = session.send("DOM.getDocument")["root"]["nodeId"]
        node = session.send("DOM.querySelector", {"nodeId": root, "selector": "h1"})["nodeId"]
        fonts = session.send("CSS.getPlatformFontsForNode", {"nodeId": node})["fonts"]
    finally:
        session.detach()
    approved = {"Pretendard", "Noto Sans KR", "Noto Sans CJK KR", "Malgun Gothic", "Apple SD Gothic Neo"}
    assert any(font["familyName"] in approved and font["glyphCount"] > 0 for font in fonts), fonts
    target = capture_page(cms_page, f"korean-font-{'blocked' if block_fonts else 'normal'}")
    target.with_suffix(".fonts.json").write_text(json.dumps({"metrics": metrics, "renderedFonts": fonts, "blockedWebfonts": block_fonts}, indent=2), encoding="utf-8")