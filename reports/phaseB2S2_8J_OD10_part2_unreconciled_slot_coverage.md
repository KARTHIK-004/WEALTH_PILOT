# Research Enhancement Track — Phase B2-S2.8J: OD-10 Part 2, Exclude Unreconciled Slots from Coverage

**Status: COMPLETE.** The owner's OD-10 part 2 decision is implemented: a processed slot that fails reconciliation no longer counts in the aggregator's coverage numerator.
The denominator, grid, shared-block vocabulary, thresholds, policies and `no_news` semantics are unchanged. Offline and synthetic. Date: 2026-10-20 (UTC). Written for: the project owner.

**Prompt note.** The S2.8J prompt was cut off in section 4 ("For an interval with eight processed"). The objective, authorisation boundary and the invariant in sections 1–3 were complete, so I implemented those and
treated section 4 as "keep `DailyFeatures.coverage_report` present, serialisable, deterministic and additive". If the missing text added a requirement, please resend it.

## 1. Pre-change state (verified live)

HEAD `71b363f`, branch `master`; 0 staged; 49 tracked modifications; 166 untracked. Reports 8D, 8E, 8G, 8H, 8I all present. Policy table unchanged: 8 of 8 required policies block;
`source_coverage_threshold` = `SELECTED_PROVISIONAL_NOT_APPLIED`. Baseline: 312 sentiment tests passed; S2.8I's golden snapshot available. `features.py` is untracked (new in this track), so
"existing modifications" to it are the whole file.

## 2. The change (`sentiment/features.py::_assess_day`, one block)

- `unreconciled[i] = slot not in verdict or bool(verdict[slot])` — the existing reconciliation verdict (`reconcile_slot`) is the only evidence. A processed slot with **no** verdict fails closed (not covered).
- `covered_asof = on_time and not unreconciled` feeds the existing `SlotSummary` / `interval_count` (same formula, same threshold argument, same `n_cov = round(ratio × n)`).
- Unchanged on purpose: `asof` still drives `delayed` and the `missing_source_batches` test (so an all-unreconciled interval is not mislabelled "missing"); `near` keeps its meaning (processed, on time, flagged near-empty);
  the denominator is still `len(slots)` (the full grid).
- Reason text: when `insufficient_coverage` and unreconciled slots exist, the message adds "N processed slot(s) failed reconciliation and are not counted as covered".
- Comments on `DailyFeatures.coverage_report` updated: the block and the numerator now agree on this case.

## 3. What changed and what did not (evidence)

Snapshot comparison (scratch script, 13 scenarios, 78 rows, every field except `coverage_report`), before S2.8J vs after:

| Scenario | Result |
| --- | --- |
| clean, clean empty, absent ×24/60/96, near-empty some/unknown, delayed, no slot information, earlier unresolved, earlier not examined | **identical** |
| unreconciled (8 wrong slots), count mismatch (1 wrong slot) | **only `coverage` and `n_slots_covered` changed** (96→88, 96→95); `coverage_status`, `reason`, `no_news`, usability, completeness, `n_slots_expected` identical |

Consequences that follow from the numerator, by design: with ≥ 25 of 96 slots unreconciled the ratio falls below the configured 0.75, so the status becomes `insufficient_coverage` (before: `slot_article_mismatch`);
all 96 unreconciled → `insufficient_coverage` with coverage 0.0. At or above the threshold the status stays `slot_article_mismatch`, so a problem day is never `ok`. `no_news` stays `None` in all of them (it was `None` for both statuses).

## 4. Tests

| Command (repo root, `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`) | Result |
| --- | --- |
| `test_sentiment_aggregator_unreconciled_coverage.py` (new, 9 tests) + `test_sentiment_aggregator_coverage_report.py` | 22 passed |
| `tests/backend/data/gdelt/test_sentiment_*.py` | **321 passed** |
| `tests/backend/data/gdelt` (full GDELT suite, run this phase) | **1346 passed** in 68 s |

New tests: numerator drops by exactly the unreconciled count with the denominator fixed at 96 (1, 8, 24 slots); aggregator and shared block numerators equal (and `rejected` count equal); status stays mismatch at the exact
0.75 boundary and becomes insufficient at 71/96 with the new reason; all-unreconciled; other states (absent, near-empty, unknown, delayed) keep their separate meanings in a mixed interval; numerator equality across seven scenarios;
a processed slot with no verdict fails closed (called directly on `_assess_day`); a 99% ratio does not make a slot reconciled; policies, thresholds and `EXCLUSION_REASONS` unchanged; clean days unchanged.
Two S2.8I tests that encoded the divergence were updated to the new decision (the divergence test now asserts agreement; the "neither authoritative" text test now checks the decision is recorded). No other existing test was edited, and all
other existing tests passed unchanged.

## 5. Limits

- The aggregator's `n_slots_near_empty` still counts an unreconciled near-empty slot, while the block reports it as `rejected` (not near-empty). Not changed: the decision covered the covered-count only. Flagged for the owner if they want the two aligned.
- `coverage_status` for a heavily unreconciled interval changed from `slot_article_mismatch` to `insufficient_coverage`; this is the direct consequence of the authorised numerator, not an independent decision.
- Source coverage is still not evidence of valid sentiment, polarity or verified no-news; the threshold policy is still not applied.

## 6. Post-change state and confirmations

HEAD `71b363f`; 0 staged; 49 tracked modifications (unchanged); 167 untracked (166 + the new test file; this report makes 168). Source edited: `features.py` only. Test files: one new, one updated (S2.8I). Sample tree: 546 files, `271939bb1895d1d3` before and after.
Policy table unchanged (8 of 8 block). No network, download, install, key or annotation-key access, scoring, features, evaluation, acquisition, S2.9 or S4. Nothing staged or committed; no unrelated work overwritten.
