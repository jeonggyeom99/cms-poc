# CMS Design Acceptance

Date: 2026-10-30. Runtime: <http://127.0.0.1:8010>, safe task
`shell: cms-task2-safe-live-8010`, left running. Validator: GitHub Copilot,
**implementer own verification**, not independent validation.
**Independent status: round1 fixes awaiting reviewer recheck.** Sol's original
REQUEST CHANGES decision is retained below; implementer checks do not approve
independent acceptance. Current round1 own evidence supersedes the original
implementer results only, not the independent decision.

## Scope And Ownership

Tasks 1-7 supply the retained inventory, tokens, shell and page owners. Task 8
locks ownership and integrates acceptance without changing API/data/diagnosis
or deleting unknown-use pages. The explicit renderer owns assembly, tokens
own values, shared operations CSS owns shell/role consumers, and the original
page CSS owns layout. No new override stylesheet is added. Data-driven geometry,
canvas/Plotly output and exported document styles are deliberate exceptions.
The scoped scans found no remaining prohibited route/JS style injections;
the initial Task8 ownership sweep therefore required no product edits.
Round1 fixes the reviewed statistics consumers in their original styles.css
owner and moves the original chat launcher into index.html's header flow;
no API/data/diagnosis or chat-controller change is introduced.

## Requirements To Evidence

| Requirement | Task | Executable checks | Fresh visual/metric evidence | Validator/status |
| --- | --- | --- | --- | --- |
| Keep all routes and unknown-use pages | 1, 7, 8 | `test_primary_routes_render`, `test_retained_variants_share_roles_without_losing_content`, `test_task8_final_route_roles_glyphs_and_geometry` | 100 `task8-final-route-*.png` plus geometry/acceptance JSON; 25 URLs x four cases | Implementer; independent pending |
| One owner, assets once, no route style creation or migrated JS CSS injection | 3, 7, 8 | `test_static_presentation_has_single_owner`, `test_shared_shell_assets_once`, five mutation RED probes | Runtime asset ledgers in each acceptance JSON | Implementer; independent pending |
| Stable explicit 244/76 sidebar; hover and actual Tab do not resize/reflow | 3, 8 | `test_task8_final_route_roles_glyphs_and_geometry`, existing shell/storage tests | Each route's expanded/collapsed shell dimensions | Implementer; independent pending |
| Hierarchical type, actual Korean glyphs and readable values | 2, 4-8 | `test_metadata_uses_role_typography`, semantic/fallback/token tests, final route roles/glyph check; `test_task8_fix1_detail_roles_and_hit_tested_chat`, FFT-stat role/token consumers | Metadata/font sidecars plus16 `task8-fix1-detail-*.occlusion.json`: every stats dt13/20 and dd14/22, live token size/leading/weight propagation | Own regression green; S1/P2 awaiting independent recheck |
| Exact metadata example: `3 전기강판 3DNL` and `56`; wrap long names | 2, 5, 8 | Short/long metadata fixture at all four cases; exact content, top/bottom alignment, ranges and CDP fonts | Eight metadata captures and real glyph font records | Implementer; independent pending |
| No clipping/overlap, stable unequal detail columns | 4-8 | Final route Range/scrollport/overlap checks; scoped unequal-column and stable-track tests; `test_task8_fix1_detail_roles_and_hit_tested_chat` | Four stable-track captures;16 exact/long x expanded/collapsed x four-case occlusion captures;48 hit-tested scroll measurements and ancestor clipping checks | Own regression green; S2/P2 awaiting independent recheck |
| Unambiguous VS Code tasks; preserve live server definition | 8 round1 | `test_vscode_task_labels_resolve_unambiguously`; final-input before-snapshot task comparison | Q1 RED names exactly two duplicate labels; GREEN resolves uniquely; original task definitions preserved | Own regression green; Q1/P3 awaiting independent recheck |
| Preserve datasets and link cutoff/start policies | 4-6, 8 | Navigation tests; `test_historical_detail_keeps_cutoff_and_fft`; `test_related_history_link_keeps_its_date_contract`; `test_ai_representative_fft_keeps_start` | Fresh full-UI `.navigation.json` plus request audits | Implementer; independent pending |
| FFT selection, expanded interactive Plotly and chart roles | 2, 5-8 | Detail actions/FFT tests; chart typography checks; final route SVG glyph/trace checks | Plotly font/label/trace metrics; modal zoom captures from final whole-UI run | Implementer; independent pending |
| Real nonblank canvas with original counts, not source-only presence | 7, 8 | Retained variant API-count/dimension/pixel tests; final route canvas pixel checks | Eight fresh canvas-route captures; backing/visible size, color diversity and font | Implementer; independent pending |
| Preserve AI/PPT/email/clipboard/chat/W/O safely | 1, 5, 8 | `test_detail_actions_and_states`, workflow tests; schema-valid local fixtures and fail-closed barrier | Fresh full-UI action captures, local PPTX, audit ledgers; no paid/send/OS clipboard effects | Implementer; independent pending |
| Whole-suite integration, no hidden skips or business fixes | 8 | Final full non-UI `--node`; final entire `tests/ui` without ESM option; exact failure-ID comparison | `artifacts/task8-evidence.json` and full logs | Non-UI remains non-green; independent pending |

## Capture Matrix

The authoritative per-URL/per-case table, exact screenshot paths, geometry,
state, fingerprint and result IDs are in
`.superpowers/sdd/2026-10-29-cms-design-unification/artifacts/task8-evidence.json`.
All captures are in `.cache/cms-ui/`, not historical Task 1-7 image references.
The 25-entry inventory is [current operation](../current-operation.md#11-unified-design-operations).
Six additional direct documents remain tested by the entire retained UI suite.

Cases: 1280x800, 1440x900, 1920x1080 native; representative 1440x900 at
125% using a 1152x720 CSS layout viewport plus 1.25 raster scale. This is
measured layout zoom, not a claim about a browser menu setting. All 25 routes
are checked at all four cases. Full-page screenshots preserve real content;
intentional FFT/history list scrollports remain scrollable. Glyph probes use
Chromium platform-font data, not a CSS family string alone. Native select/input
glyphs are not directly exposed by that CDP API; text-bearing buttons and
visible role nodes provide control glyph probes and native controls retain
computed size/height/geometry checks.

## Original Commands And Results

This table preserves the pre-review implementer run. Current round1 results
are recorded in the round1 own-verification section below and final manifest.

From the repository root, the isolated verifier is
`.superpowers/sdd/2026-10-29-cms-design-unification/artifacts/task1-verify.py`.
It uses this checkout's `.venv` interpreter, no dotenv/provider access, UTF-8,
and portable Node 20 only for `--node`. See the exact runnable commands in
[current operation](../current-operation.md#11-unified-design-operations).

| Final check | Result | Log under SDD `artifacts/` |
| --- | --- | --- |
| Ownership/chart/report/Node slice | **82 passed, 0 skipped**, exit 0 | `task8-final-ownership.txt` |
| Entire non-UI, Node ESM usable | **414 passed, 16 failed, 509 deselected, 0 skipped**, exit 1 | `task8-final-non-ui.txt` |
| Entire UI, bundled Node option cleared | **509 passed, 0 skipped**, exit 0 | `task8-final-all-ui.txt` |
| Final fresh reopen after documentation | **112 passed, 7 deselected, 0 skipped**, exit 0 | `task8-final-reopen.txt` |
| Fingerprint/freshness/baseline/audit validator | **Passed**, unchanged product/test snapshot;112 fresh captures;16 unchanged failures/0 new | `task8-evidence.json`, `task8-evidence.txt` |

Reopen/evidence output is recorded at
`.superpowers/sdd/2026-10-29-cms-design-unification/artifacts/task8-evidence.json`.
The audit asserts112 fresh PNGs (100 route +8 exact/long metadata +4 stable
tracks),104 clean Task8 route/track request ledgers plus8 metadata ledgers,
all eight rendered glyph roles, and
exact equality of the16 baseline failing IDs. The full UI run also covers
workflow/negative states and all six additional direct documents. All509 UI
tests ran after the final product/test fingerprint, without bundled Node ESM
option leakage. The baseline-ID comparison has zero added or removed IDs.

## Remaining Limitations

- **Non-UI is not green.** Compare all 16 exact parametrized failure IDs with `task7-r1-default-non-ui.txt`; do not infer acceptance from the desired PASS in the brief. Full IDs are retained in the evidence manifest/log, not hidden by skip/xfail/snapshot changes.
- Independent reproduction, document/diff review and acceptance signoff are pending the controller's Sol reviewer. The implementer does not self-certify independence.
- Comparison-page external usage is unconfirmed; routes remain retained. Demo KPIs, illustrative pies, W/O download and existing per-link cutoff policies are not new production capabilities.
- No mobile verification was requested. No exhaustive manual whole-page contrast or browser-native zoom claim. Automated Range checks distinguish reachable scroll content from genuine non-scrollable clipping.
- Paid AI, actual email sending, OS clipboard, LibreOffice/PowerPoint rendering and external integrations are not exercised. PPT validation metadata is synthetic in local fixtures; it does not prove real report rendering.

## Independent Evidence Status

Date: 2026-10-30. Reviewer: **GitHub Copilot (Sol, independent Task8 spec/quality
and actual-workflow review session)**. This reviewer did not implement Task8
or change product/test/task configuration. This section supersedes earlier
historical "independent pending" statements for the review outcome only.

**Outcome: REQUEST CHANGES; independent design acceptance NOT APPROVED.**
Spec findings: **2 P2**; additional quality findings: **1 P3**; no P0/P1 found.
The current FFT statistics inherit12px for both labels and values instead of
13/20 and14/22 roles. At1440x900/125%, the fixed chat button obscures threshold
evidence; long Korean metadata exposes overlap on5.44 mm/s and17.11 mm/s.
Two duplicate Task8 VS Code task labels are the P3 quality finding.
These are not new API/data/diagnosis findings or a claim that Task8 changed CSS.

Independent executable reproduction: **141 unique selected pytest cases passed
(82 non-UI +59 UI),0 skips**, using task1-verify and guarded local browser
fixtures. Exact Korean metadata and long-name cases cover1280x800,1440x900,
1920x1080 and representative125% layout/raster zoom. Reproduced real hover/Tab
geometry,storage denial/persistence,history dataset/until/start and returned
FFT record,FFT change,Plotly expand/drag zoom,AI held/error/recovery,local PPTX,
email preview/in-page copy/permission rejection,chat and demo W/O download.
Eight retained canvas cases verify actual API counts,dimensions and pixels.
Eight additional guarded browser probe states confirmed the two P2 findings
with0 blocked requests/page errors; fixed-overlay collisions were hit-tested,
not inferred from CSS alone. Intentional barrier-denial tests separately prove
unregistered/external requests are blocked and are not an empty-ledger claim.

The Task5 deferred equal-width P3 assertion is genuinely corrected: the scoped
test passes for the unequal owning rule, fails under an independent in-memory
equal-column mutation,then passes again without disk product writes.
The completed existing evidence task revalidated unchanged134 product/owned-test
hashes,112 fresh captures and exact16 baseline failure IDs with0 additions or
removals. The whole509 UI/full non-UI suites were not independently rerun.
Passing selected tests does not clear the demonstrated role/overlay blind spots.

Detailed findings,file/line references,exact commands,logs,probe procedure,
screenshots and limitations:
[task-8-review.md](../../.superpowers/sdd/2026-10-29-cms-design-unification/task-8-review.md).
Independent logs are `artifacts/task8-sol-{ownership,typography,contracts,storage,retained}.txt`;
probe results are `artifacts/task8-sol-probes.json` and `task8-sol-equal-tracks.json`
in that SDD directory. Unique reviewer images/metrics use
`.cache/cms-ui/task8-sol-probe-*`; the pre-run fingerprint/manifest is preserved
in `artifacts/task8-sol-before-evidence.json`. Unconfirmed supplementary
aggregation output is not acceptance evidence.

Limits remain:16 non-UI baseline failures,no mobile/native-menu zoom,real
provider/email,OS clipboard or real report-renderer validation; comparison
route usage remains unconfirmed. No .env access or external side effect was
performed. Safe server **http://127.0.0.1:8010** was reused and left running.
Recheck S1/S2 and refresh affected captures after fixes before independent signoff.

## Round1 Own Verification

Implementer: GitHub Copilot,2026-10-30. **S1/P2,S2/P2,Q1/P3: implemented;
own focused regressions green; independent recheck awaiting reviewer.**
No independent PASS is claimed and the preceding independent review is not
rewritten as approval. Exact commands,RED/GREEN outputs and execution details
are appended to task-8-report.md in the existing SDD workspace.

The before snapshot is `.superpowers/sdd/2026-10-29-cms-design-unification/task-8-fix1-before/`.
Terminal execution was unconfirmed; only the snapshot-runner task was
bootstrapped in task configuration before the verified Git Bash snapshot.
Product,tests and docs were unchanged until the snapshot existed. The final
input audit verifies all original task/server definitions remain equal.
Prior final logs/manifest are preserved in artifacts/task8-fix1-prior-evidence/.

Focused checks after the final product/test/config fingerprint:2 FFT consumer
role/token cases,16 exact/long metadata x both sidebar modes x four viewport
cases,and1 unique-task case passed; ownership slice83passed. The16-state check
measures all stats labels/values and mutates/restores their live tokens. It
also hit-tests text/launcher intersections at top,threshold-center and bottom,
checks clipping/overflow,and executes guarded keyboard chat open/reply/Escape,
focus return and dataset-chooser access. The launcher now scrolls normally
with the header; it is not claimed to remain fixed at the bottom of the page.
Its title/accessible name,chat controller and mobile panel/backdrop rules are
preserved. No mobile acceptance is added.

| Round1 final own check | Actual result | Log / artifact under SDD artifacts/ |
| --- | --- | --- |
| Focused repairs | 2role/token +16state-matrix +1task cases passed | task8-fix1-{roles,chat,tasks}-green.txt; corresponding RED logs retained |
| Ownership | 83passed,exit0 | task8-final-ownership.txt |
| Whole non-UI | 415passed,16failed,527deselected,0skipped,exit1; exact baseline IDs unchanged,0new/0removed | task8-final-non-ui.txt; task8-evidence.json |
| Whole UI repeat | 527passed,0skipped,exit0,694.64s | task8-final-all-ui.txt |
| Final all-route reopen | 128passed,9deselected,0skipped,exit0,180.83s | task8-final-reopen.txt |
| Final fingerprint/capture/audit gate | PASS,unchanged frozen product/test/config hashes | task8-evidence.json and task8-evidence.txt |

Observed final evidence:128fresh PNGs (100route +8metadata +4stable-track
+16role/occlusion),including all25routes at three native widths and
representative125% layout/raster zoom. The gate checks128clean final request
audits,all8glyph roles,16nonuniform canvas instances,48role/occlusion scroll
measurements and preservation of original task/server definitions. The full
manifest supplies each URL,viewport,state,screenshot path and test result.
Input boundary:2026-10-29T18:31:41.970275+00:00 (runtime clock).

One first whole-UI run passed527test bodies but had an existing safe-fixture
teardown error (`Route.fulfill: Route is already handled!`) after a historical
dataset switch. Its complete log is retained as task8-fix1-all-ui-first-error.txt;
both aliases then passed the narrow task8-fix1-history-recheck.txt run without
product/fixture edits,and the repeated whole UI passed. This concern is not
hidden by the final green result. Independent recheck remains pending;
non-UI acceptance remains non-green. No mobile or real paid-side-effect
validation is claimed,and the live8010 server is left running.

## Independent Fix1 Re-Review

Date:2026-10-30. Reviewer:GitHub Copilot,independent scoped re-review.
**S1/P2 CLOSED,S2/P2 CLOSED,Q1/P3 CLOSED.** The independently executed new
regression subset passed19 unique cases (18UI+1non-UI),0skips and0fixture
setup/teardown errors. Statistics labels/values compute13/20 and14/22 with
live token propagation. Exact/long metadata x both sidebar modes x four
desktop/zoom cases pass48 hit-tested scroll measurements and guarded chat
open/reply/Escape/focus-return and dataset-chooser access. Fresh long/expanded
and exact/collapsed125% images were visually inspected. The launcher now
scrolls with the header; persistent bottom-of-page placement is not claimed.

**Overall evidence acceptance remains NOT APPROVED: new Q2/P2.** An independent
run of `shell: cms-task8-evidence` exits1 at task8-evidence.py line89:
`Product/test changed after final validation began; rerun final suites`.
The historical unchanged-fingerprint PASS above is not a current independent
PASS. The exact changed input could not be established with the available
diagnostic execution; no product-regression attribution is asserted. Reconcile
the real frozen/current differences before updating the acceptance boundary;
do not silently reset it. No527-case or full non-UI suite was rerun here.

The before snapshot and guarded fixtures exist and the selected cases execute
without missing-fixture setup errors. Retain the documented bootstrap exception:
only the snapshot-runner task was added before the verified snapshot; this is
not byte-identical pre-bootstrap task configuration. No snapshot was reset.
The16 baseline non-UI failures and historical safe-fixture teardown race remain
disclosed debt. No mobile/native-menu zoom/real paid-side-effect validation.
No product,test,task configuration,.env or git modification. Server8010 remains
running. Existing historical review and own-verification entries are preserved.

Exact commands,results,source lines,limitations and final spec/quality verdict:
[task-8-rereview1.md](../../.superpowers/sdd/2026-10-29-cms-design-unification/task-8-rereview1.md).
Stable independent transcript:
[task8-rereview1-execution.txt](../../.superpowers/sdd/2026-10-29-cms-design-unification/artifacts/task8-rereview1-execution.txt).