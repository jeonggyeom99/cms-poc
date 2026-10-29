from html import escape
from pathlib import Path
import re
from string import Template


STATIC_DIR = Path(__file__).resolve().parent / "static"
ASSETS = '''<link rel="stylesheet" href="/static/cms-tokens.css?v=20261029">
<link rel="stylesheet" href="/static/cms-operations.css?v=task3">
<link rel="stylesheet" href="/static/cms-sidebar-icons.css?v=20261006">'''
SCRIPTS = '<script type="module" src="/static/modules/core/cms-operations.js?v=task3"></script>'


def render_operations_page(
    page: str, *, active_page: str, body_classes: tuple[str, ...] = (),
) -> str:
    slots = ("assets", "sidebar", "scripts", "body-attributes")
    for slot in slots:
        if page.count(f"<!-- cms:{slot} -->") != 1:
            raise ValueError(f"Expected exactly one cms:{slot} slot")

    sidebar = Template(
        (STATIC_DIR / "partials" / "cms-sidebar.html").read_text(encoding="utf-8"),
    ).substitute({
        f"{name}_current": ' aria-current="page" class="active"' if active_page == name else ""
        for name in ("overview", "equipment", "history", "control")
    })
    attributes = (
        f'class="{escape(" ".join(body_classes), quote=True)}" data-cms-operations '
        f'data-cms-active-page="{escape(active_page, quote=True)}" data-cms-nav="expanded"'
    )
    fragments = {"assets": ASSETS, "sidebar": sidebar, "scripts": SCRIPTS,
                 "body-attributes": attributes}
    for slot, fragment in fragments.items():
        page = page.replace(f"<!-- cms:{slot} -->", fragment)
    return page


def render_retained_page(
    page: str, *, active_page: str, body_classes: tuple[str, ...] = (),
) -> str:
    for slot in ("assets", "sidebar", "scripts", "body-attributes"):
        start = f"<!-- cms-static:{slot} -->"
        end = f"<!-- /cms-static:{slot} -->"
        if page.count(start) != 1 or page.count(end) != 1:
            raise ValueError(f"Expected exactly one retained {slot} region")
        page, count = re.subn(
            re.escape(start) + r".*?" + re.escape(end),
            '<body <!-- cms:body-attributes -->>' if slot == "body-attributes" else f"<!-- cms:{slot} -->",
            page, flags=re.DOTALL,
        )
        if count != 1:
            raise ValueError(f"Invalid retained {slot} region")
    return render_operations_page(
        page, active_page=active_page, body_classes=("cms-retained", *body_classes),
    )