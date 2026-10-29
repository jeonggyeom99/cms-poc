from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from playwright.sync_api import Locator, Page, Response


def open_page(cms_page: Page, path: str) -> Response:
    response = cms_page.goto(path, wait_until="domcontentloaded")
    if response is None:
        raise AssertionError(f"No response while opening route: {path}")
    cms_page.wait_for_load_state("networkidle")
    cms_page.wait_for_function("document.fonts && document.fonts.status === 'loaded'")
    return response


def text_metrics(locator: Locator) -> dict[str, Any]:
    if locator.count() < 1:
        raise AssertionError("text_metrics locator did not match an element")
    return locator.first.evaluate(
        """
        (element) => {
          const computed = window.getComputedStyle(element);
          const range = document.createRange();
          range.selectNodeContents(element);
          const rect = range.getBoundingClientRect();
          return {
            fontSize: computed.fontSize,
            lineHeight: computed.lineHeight,
            fontWeight: computed.fontWeight,
            fontFamily: computed.fontFamily,
            rangeTop: rect.top,
            rangeBottom: rect.bottom,
          };
        }
        """
    )


def capture_page(cms_page: Page, name: str) -> Path:
    output_dir = Path(".cache") / "cms-ui"
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-")
    width, height, zoom = cms_page.cms_desktop_case
    target = output_dir / f"{safe_name}-{width}x{height}-zoom{round(zoom * 100)}.png"
    cms_page.screenshot(path=str(target), full_page=True)
    geometry = cms_page.evaluate("""() => {
      const main = document.querySelector('main')?.getBoundingClientRect();
      return {
        innerWidth, innerHeight, devicePixelRatio,
        rootClientWidth: document.documentElement.clientWidth,
        rootScrollWidth: document.documentElement.scrollWidth,
        visualViewport: {width: visualViewport.width, height: visualViewport.height, scale: visualViewport.scale},
        main: main ? {x: main.x, y: main.y, width: main.width, height: main.height, right: main.right} : null,
      };
    }""")
    geometry.update({"url": cms_page.url, "requestedViewport": {"width": width, "height": height}, "zoom": zoom,
                     "zoomMethod": "reduced CSS layout viewport plus raster scaling" if zoom != 1 else "native layout viewport"})
    target.with_suffix(".json").write_text(json.dumps(geometry, indent=2), encoding="utf-8")
    return target
