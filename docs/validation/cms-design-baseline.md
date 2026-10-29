# CMS Design Baseline (Task 1)

## Scope

- Desktop baseline infrastructure only.
- Mobile behavior was not intentionally modified or validated.

## Baseline Test Status Before Task 1

- Command: `uv run python -m pytest -q`
- Result: `34 failed, 323 passed, 9 skipped`
- Output: `.superpowers/sdd/2026-10-29-cms-design-unification/artifacts/task1-baseline-pytest-utf8.txt`

## UI Route Inventory (Desktop)

- UI test file: `tests/ui/test_cms_baseline.py`
- Route set validated:
  - `/`
  - `/equipment-status2`
  - `/dashboard_ui6`
  - `/dashboard`
  - `/dashboard2`
  - `/history`
  - `/history2`
  - `/main_ct`
  - `/main_sv`
  - `/main_ct1`
  - `/main_ct2`
  - `/main_ct3`
  - `/main_sv1`
  - `/main_sv2`
  - `/main_sv3`
  - `/main`
  - `/dashboard_ui1`
  - `/dashboard_ui2`
  - `/dashboard_ui3`
  - `/dashboard_ui4`
  - `/dashboard_ui5`
  - `/dashboard_ui1_canvas`
  - `/static/history2.html`
  - `/static/dashboard-ui1-fresh.html`
  - `/static/dashboard-lab.html`

## Captures

- Current captures use `.cache/cms-ui/<name>-<width>x<height>-zoom<percent>.png` with adjacent `.json` browser geometry. Historical unsuffixed screenshots are not the current gate.
- All 25 routes run at 1280x800, 1440x900 and 1920x1080. The representative equipment page also runs at a 1440x900 physical-output / 1152x720 CSS-layout equivalent of 125% browser zoom.
- The zoom equivalent changes layout viewport dimensions as well as raster density. It is not a claim that the browser's native zoom menu was used. Geometry records `innerWidth`, `innerHeight`, root widths, visual viewport, DPR and main bounds; PNG width is checked independently. Media queries see the reduced CSS viewport. `device_scale_factor` alone is not the evidence.
- `negative-*` covers a held dataset request, a genuinely unmatched equipment filter, schema-shaped empty history, and a visible structured history API error. The old mislabelled empty-equipment screenshot was replaced with a real zero-result capture.
- `navigation-*` captures expanded equipment/history controls and destinations. `.navigation.json` records actual dataset/date parameters and API URLs.
- `korean-font-*` includes `.fonts.json` computed metrics and Chromium's actual platform glyph fonts, including a webfont-blocked fallback probe. Baseline observation: Noto Sans KR renders the Korean heading; this does not assert later design token values.
- `workflow-*` covers local report download, error, email preview/copy and chat. The successful `.pptx` is retained beside its PNG and parsed with python-pptx.
- Per-test `.audit.json` records intercepted endpoint names, dataset, record/cutoff and blocked requests without chart payloads or credentials.

## Runtime And Commands

- Leave `http://127.0.0.1:8010` running via VS Code task `shell: cms-ui-baseline-server-8010`. `CMS_UI_BASE_URL` overrides the fixture's default `http://127.0.0.1:8000`; connection failures are errors, never unconditional skips.
- Playwright is imported only during fixture execution. Every UI module can be collected without the package; default pytest deselects `ui`. Explicit UI execution still reports the missing package.
- Portable Node: `.cache/node/node-v20.18.0-win-x64/node.exe`, v20.18.0. Imported ambiguous `.js` files require `NODE_OPTIONS=--experimental-default-type=module`. `--input-type=module` alone is insufficient. Windows subprocess text handling also needs `PYTHONUTF8=1`.
- Scope Node mode to regression invocations: Playwright's bundled driver rejects this option. Do not leave it inherited when starting Playwright. No product `.js` or package metadata changes are needed.

```powershell
$env:PATH = "$PWD\.cache\node\node-v20.18.0-win-x64;$env:PATH"
$env:PYTHONUTF8 = '1'
$env:PYTHON_DOTENV_DISABLED = '1'
$env:NODE_OPTIONS = '--experimental-default-type=module'
node --version
uv run python -m pytest -q tests/test_operations_ui.py::test_workspace_missing_clock_filter_reset_empty_and_error_states
Remove-Item Env:NODE_OPTIONS
$env:CMS_UI_BASE_URL = 'http://127.0.0.1:8010'
uv run python -m pytest -q -m ui tests/ui
```

For durable UTF-8 logs and isolated environments, use the artifact-local verifier from the repository root. It disables dotenv loading and external Python socket connections, clears Node options for UI, and applies the portable PATH/mode only with `--node`:

```powershell
.\.venv\Scripts\python.exe .superpowers/sdd/2026-10-29-cms-design-unification/artifacts/task1-verify.py --node task1-node-check.txt -q tests/test_operations_ui.py::test_workspace_missing_clock_filter_reset_empty_and_error_states
.\.venv\Scripts\python.exe .superpowers/sdd/2026-10-29-cms-design-unification/artifacts/task1-verify.py task1-ui-check.txt -q -m ui tests/ui
```

## Retention Disposition

- Known operating routes and legacy `/dashboard`, `/history` remain in the inventory.
- Usage unconfirmed, retained pending owner confirmation: `/main`, `/main_sv`, `/main_ct1`, `/main_ct2`, `/main_ct3`, `/main_sv1`, `/main_sv2`, `/main_sv3`, `/dashboard_ui1`, `/dashboard_ui2`, `/dashboard_ui3`, `/dashboard_ui4`, `/dashboard_ui5`, `/dashboard_ui1_canvas`, `/static/history2.html`, `/static/dashboard-ui1-fresh.html`, `/static/dashboard-lab.html`.
- No deletion or redirect is authorized by this baseline. Owner confirmation remains pending; route appearance alone is not proof of production usage.

## Known Pre-existing Defect Observed During Baseline

- Route: `/static/dashboard-lab.html`
- Evidence: `test_primary_routes_render[/static/dashboard-lab.html]`
- Browser error: `Cannot read properties of undefined (reading '0')`
- This was documented as baseline debt and not patched in product code during Task 1.

## Side-effect Protection in UI Fixture

- Context-wide interception supplies local AI/chat/email responses for all pages and query strings. AI uses the real non-paid dashboard's selected FFT record for the requested dataset/cutoff; the consumed AI/chat/email bodies are checked against existing response models.
- Diagnostic PPT defaults to a real locally generated one-slide PPTX with the correct MIME type, filename and `X-PPT-Validation` metadata. The `passed` metadata is synthetic fixture data, not a provider validation claim. `cms_side_effects.ppt_mode = "error"` selects the independent 503 case.
- Unknown API reads, unregistered writes and external browser requests are blocked before reaching the server/provider. Unexpected local writes fail teardown after being safely blocked. Service workers are disabled.
- Direct Playwright APIRequestContext writes/fetch are disabled because they bypass browser routing. Only approved same-origin non-paid GET/HEAD paths are allowed. Loading/error/empty controls cannot override paid/write endpoints.
- Email copy is consumed in page memory, never the operating-system clipboard; no email is sent. Historical runs have no complete retrospective network audit. Current fixture barriers and per-test ledgers establish the repeatable protection used by the fix checks.

## Baseline Debt

- The strict route gate remains red for the pre-existing dashboard-lab TypeError, now tested independently at all three desktop sizes. No xfail, skip or relaxed `page_errors == []` assertion hides it. A later scoped owner (potentially Task 7) must repair or explicitly accept that debt.
- Final review-fix UI run: 85 passed, 3 failed (the same lab route at three widths). Final non-UI run: 351 passed, 17 failed, 88 deselected, no skips. All 17 failure IDs occur in the original 34-failure baseline; zero new failing IDs. Different safe/UTF-8/Node execution conditions mean improved counts are not a claim of product repairs.
- At 1280px, retained `/main_ct1`, `/main_ct2`, `/main_ct3`, `/main_sv1`, `/main_sv2`, `/main_sv3` have 1322px full-page/root scroll width, and `/main_sv` has 1292px. Evidence preserves this existing product overflow; no clipping or product fix disguises it. Screenshot names identify requested viewport, while geometry records the actual overflow.
- Reusable fixture interfaces and focused commands: `.superpowers/sdd/2026-10-29-cms-design-unification/task-1-interfaces.md`.

## Task 4 Accepted Equipment Reference

- The implemented representative reference is `/equipment-status2`, also assembled at `/` and `/static/equipment-status2.html`. This section records the Task 4 implementation acceptance checks, not a claim of separate stakeholder sign-off. The approved Task 3 sidebar, slots, aliases, persistence and Plotly resize behavior are unchanged.
- Use unframed full-width content bands with thin separators: CMS-connected inventory analysis, query conditions, then a classification navigation/list workspace. No floating section cards, nested decorative cards, shadows or extra override sheet. Controls use 6px radius, status labels 4px; all inspected effective radii are <=8px.
- Shared tokens are unchanged. Page 24/32px 700, section 16/24px 600, Korean body/equipment/sensor values 14/22px, labels/metadata/status 13/20px, chart legend 12/18px; letter spacing 0. Long Korean body/value text wraps without shrinking. Controls are 36px; tree/sensor targets >=44px; equipment summaries >=72px. Background #f4f6f8, text #20262e, border #dce1e6, accent #2563eb; normal/caution/danger #17824d/#a15b00/#c93434. Selection uses a restrained pale-blue fill and 3px leading accent, paired with accessible current state.
- The analytics population is explicitly **all CMS-connected datasets** (currently 9: normal 5, caution 4). The result count is **filtered classification equipment groups** (currently 254 before filters), not sensors, API dataset count, or chart total. The charts intentionally do not claim to follow the classification filters. Unknown state is a separate gray, labeled category, never critical or healthy by default.
- Actual selectable reference: `1냉연 / 1CAL / FAN / NO.1 DUST COLLECT FAN`; unfiltered equipment has two sensors, V190/PULLEY SIDE and live V191/IMPELLER SIDE. Its existing `/dashboard2?dataset=...` destination and dataset resolution remain unchanged. Live-only Water Treatment/rolling-mill groups are also added to the rendered tree without mutating demo inputs.
- `data-cms-result-count` announces the controller's actual rendered group count. Native disclosure summaries and real navigation buttons use `aria-current="true"` for the current result/path; `aria-expanded` remains owned by native details rather than a fabricated tree widget. Manual filters, tree choices, list selection, reset and true zero results are synchronized. A zero-result state has no current equipment.
- Loading disables filters and announces lookup state; a genuinely unmatched name produces 0 groups; a dataset API failure shows classification-only notice and a separate failed CMS chart status. No chart is fabricated from history/person allocations. Group/tree display precedence is critical > attention > unknown > normal. Diagnosis/API calculations and Excel/tree input files are unchanged.
- Before: `.cache/cms-ui/task4-reference-initial-{1280x800,1440x900,1920x1080}-zoom100.png` and `task4-reference-initial-1440x900-zoom125.png`. These preserve the pre-redesign rounded/card-heavy screen.
- Accepted default and selection: `.cache/cms-ui/task4-reference-{default,selected}-<width>x<height>-zoom<percent>.png` for 1280x800/100, 1440x900/100, 1920x1080/100, and 1440x900/125. Each is top-aligned and has `.json` geometry plus `.alarm.json` count, typography and selection evidence. Native desktop widths have no root horizontal overflow. 125% means 1152x720 CSS layout at 1.25 raster scale, not native menu zoom. No mobile validation or mobile compliance claim.
- State evidence uses `task4-{loading,empty,error,long-korean}-<width>x<height>-zoom<percent>.png` at the same four conditions. `task4-unknown-intercepted-1440x900-zoom100.png` exercises real-schema V191 summaries changed only in browser interception. Scrollable list/tree viewports remain real scroll regions; full-page captures do not purport to show every row simultaneously.
- Focused browser suite: `tests/ui/test_cms_equipment_status.py`; durable logs and executable manifest audit: `.superpowers/sdd/2026-10-29-cms-design-unification/artifacts/task4-*`. `task4-evidence.json` records 24 accepted state captures, ten clean request audits and a baseline failure-set comparison. Existing lab/legacy overflow debt above remains retained and outside Task 4.
- Current live server is the safe Task 2 launcher on `http://127.0.0.1:8010` (`shell: cms-task2-safe-live-8010`), with dotenv disabled and external Python connections denied. Task 4 changes are static and require reload only; no Python/server restart was needed.

## Task 7 Retained Inventory Disposition

This is the current disposition; the Task 1 failure/overflow observations above remain historical evidence, not current failures. Usage of comparison/experimental entries is still unconfirmed. Every existing URL is retained without deletion or redirect. Unknown usage is not evidence that a page can be removed.

| URL | Retained Owner | Data / Disposition |
| --- | --- | --- |
| `/` | `equipment-status2.html` | Operating reference; live CMS plus retained classification inventory |
| `/equipment-status2` | `equipment-status2.html` | Same operating reference, retained |
| `/dashboard_ui6` | `kpi-dashboard-concept.html` | Live KPI/history; separately labeled demo operating panels |
| `/dashboard` | `index.html` | Real dataset detail alias, retained |
| `/dashboard2` | `index.html` | Real dataset detail reference, retained |
| `/history` | `history.html` | Real history alias, retained |
| `/history2` | `history.html` | Real history reference; not the static history2 owner |
| `/main_ct` | `main-workspace.html` | Real central data grouped by plant, retained |
| `/main_sv` | `main-workspace.html` | Real field data grouped by line, usage unconfirmed, retained |
| `/main_ct1` | `main-control.html` | Real central variant 1, usage unconfirmed, retained |
| `/main_ct2` | `main-control.html` | Real central variant 2, usage unconfirmed, retained |
| `/main_ct3` | `main-control.html` | Real central history-queue variant, usage unconfirmed, retained |
| `/main_sv1` | `main-control.html` | Real field variant 1, usage unconfirmed, retained |
| `/main_sv2` | `main-control.html` | Real field line-grouped variant 2, usage unconfirmed, retained |
| `/main_sv3` | `main-control.html` | Real field history-queue variant, usage unconfirmed, retained |
| `/main` | `main.html` | Real plant overview, usage unconfirmed, retained and unified |
| `/dashboard_ui1` | `dashboard-ui1-kpi.html` | Real KPI plus explicitly labeled demo panels, comparison retained |
| `/dashboard_ui2` | `kpi-dashboard-concept.html` | Real KPI/history plus labeled demo panels, comparison retained |
| `/dashboard_ui3` | `design-lab.html` | Real totals/bars/history; fixed illustrative pie labeled, retained |
| `/dashboard_ui4` | `design-lab.html` | Existing worklist presentation; same real/illustrative boundary, retained |
| `/dashboard_ui5` | `dashboard-ui5.html` | Real report/priority list/history, comparison retained |
| `/dashboard_ui1_canvas` | `dashboard-ui1-canvas.html` | Existing live status proportions rendered as real 2D canvas, retained |
| `/static/history2.html` | `history2.html` | Separate retained history comparison; complete static HTML |
| `/static/dashboard-ui1-fresh.html` | `dashboard-ui1-fresh.html` | Real totals/bars/history with labeled fixed illustrative pie, retained |
| `/static/dashboard-lab.html` | `dashboard-lab.html` | Retained default UI01; invalid pathname mapping repaired, no pageerror suppression |

The additional direct entries `/static/main.html`, `/static/dashboard-ui1-kpi.html`, `/static/dashboard-ui1-canvas.html`, `/static/design-lab.html`, `/static/dashboard-ui5.html`, and `/static/equipment-status.html` are also retained, tested and complete without server slots. Legacy equipment status preserves its demo classification asset paths and real CMS connections. No file in `equipment-status-demo/` was modified.

All 25 inventory routes and these six direct entries use one token/style/icon/module set in order, readable shared roles and the explicit 244/76 sidebar. Retained raw HTML includes four complete `cms-static` regions; server routes convert only those explicit regions into the Task 3 renderer slots. No style-string replacements or extra override stylesheet are used. Original sidebar/hover-width and conflicting typography/control declarations were removed from the page owners.

Final visuals use `.cache/cms-ui/task7-route-*-<width>x<height>-zoom<percent>.png` with geometry and `.roles.json` sidecars, at 1280x800, 1440x900, 1920x1080 and 1440x900/125%. Canvas evidence records backing/display dimensions, actual API-derived segment counts, token font and nonuniform sampled pixels after sidebar resizing. The 125% case remains reduced CSS viewport plus raster scaling, not a native zoom-menu claim. No mobile validation is claimed.

Current commands, final counts, exact known-vs-new debt comparison and capture manifest are recorded in `.superpowers/sdd/2026-10-29-cms-design-unification/task-7-report.md` and `artifacts/task7-evidence.json`. The original three lab TypeErrors have a dedicated 3-pass repair check. The safe server remains `http://127.0.0.1:8010`.