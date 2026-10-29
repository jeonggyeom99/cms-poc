# Linked FFT Evidence Implementation Plan

**Goal:** Implement the user's five-point proposal without changing the Agent topology or reintroducing value validation/repair calls.

**Architecture:** Keep scalar evidence IDs and server hydration. Offer complete measurement bundles alongside the source table, preserve their dependencies when limiting the catalog, and separate weekly peak provenance from latest occurrence and mode counts. Use a dedicated FFT draft contract with a 1,200-character summary; Trend stays at 500.

**Tech Stack:** Existing Python/FastAPI/Pydantic/OpenAI gateway and pytest.

**Spec:** The user's five-point implementation request in this chat is the approved scope. All work stays in this worktree; no commit, merge, or push.

## Review Focus

- Catalog selection must retain the frequency paired with each selected amplitude, including tool evidence and synthesis citations.
- Peak measurement date and latest occurrence must remain distinct when the latest sample is lower.
- Weekly ALL and ENV counts are parts of the total, with existing ranking and grades unchanged.
- FFT summaries from 501–1,200 characters must survive both schema parsing and final assembly; 1,201 must fail without repair.
- Missing History and failed provider calls must produce different server messages.

## Tasks

- [x] Add failing tests in `tests/test_linked_fft_evidence.py` for measurement bundles, date provenance, ALL/ENV scope, FFT summary limits, and History messages.
- [x] Update `app/services/fft_status.py` with per-mode counts and distinct peak/latest explanation facts; preserve grade calculation.
- [x] Update `app/agents/handoff.py` to retain paired evidence, transmit source-linked measurement bundles, fix weekly peak provenance, and distinguish History states.
- [x] Update `app/agents/orchestrator.py` with FFT-specific schema, output budgets, focused observation → interpretation → inspection instructions, and cache version changes.
- [x] Run focused and complete pytest suites. Recheck CSV datasets 2/7 (June 18 record 51), 9 (shifted date), and a dataset with mixed ALL/ENV BPFI.
- [x] Run configured live analysis on the same CSV cases, inspect full text, paragraphs, references, truncation/finish reason, usage, and latency. Save measurements and quality findings under `docs/multi-agent/` with raw outputs in `.cache/`.

## Execution Record

- Branch verified: `codex/agent`; pre-existing changes retained.
- Root causes: scalar-only prompt table, incomplete sibling selection, weekly aggregate inherited `latestAt`, common 500-character internal summary, common 2,200-token specialist and 1,600-token synthesis budgets.
- Initial 9 regression failures confirmed; source-linked maximum forwarding separately RED→GREEN. Final 12 regressions pass in full suite (367 passed, 1 unchanged Windows killpg failure).
- Live runs approved by the user: datasets 2/5 once each, then one approved rerun each after summary prompt refinement. Final 16.29s/17.45s; no repairs or truncation. FFT summaries pass reviewed peak/date/count cases and two-paragraph structure. Dataset 5 synthesis still mislabels overall BPFI count as ENV; recorded as a failed prose quality case, not a passing run.
- Read-only independent review found no further code issues. Reviewer left live quality to the executor (reviewed and reported explicitly) and unrelated pre-existing edits/Windows failure outside this change (left intact).
- No commit, merge or push. Existing changes and prior caches preserved.
