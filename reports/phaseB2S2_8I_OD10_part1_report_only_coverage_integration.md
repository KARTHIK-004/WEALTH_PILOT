# Research Enhancement Track — Phase B2-S2.8I: OD-10 Part 1, Report-Only Coverage Integration

**Status: COMPLETE.** The aggregator now carries the shared `CoverageBlock` as an additional report-only field. Every existing value, status and verdict is unchanged
(proved by a before/after snapshot, section 5). Offline and synthetic. Date: 2026-10-20 (UTC). Written for: the project owner.

## 1. Scope and authorisation boundary

Authorised by the owner's S2.8I prompt: **OD-10 part 1 only** — report the shared block alongside the existing aggregator coverage. Not done, by design: numerator or denominator changes;
any change to `coverage`, `n_slots_*`, `coverage_status`, `no_news`, usability, completeness or result-availability states; threshold or detector-parameter changes; applying any policy;
resolving **OD-10 part 2** (unreconciled-slot treatment); calendars, lookback, late-arrival, dedup or story logic; scoring, features, evaluation, S2.9, S4, acquisition.
No policy status changed, `coverage_rule_decision` is not called by the aggregator, and no block value is read by any gate.

## 2. Pre-change state (verified live)

HEAD `71b363f`, branch `master`; 0 staged; 49 tracked modifications; 164 untracked (the sentiment package and its tests are entirely untracked, so `features.py` had no diff baseline;
its pre-change behaviour was captured by the snapshot below). Policy table read from the code: unchanged from S2.8G, **8 of 8 required policies block**; `source_coverage_threshold` and
`near_empty_slot_handling` = `SELECTED_PROVISIONAL_NOT_APPLIED`. Baseline: scaffold + completeness tests 137 passed; all sentiment files 299 passed. The reports named in the prompt
(8D, 8E, 8G, 8H) all exist; `docs/MEMORY.md` was not changed (see section 8).

## 3. Change

| File | Change | Why |
| --- | --- | --- |
| `backend/wealthpilot/data/gdelt/sentiment/features.py` | imports `CoverageBlock`, `coverage_block`; new last field **`DailyFeatures.coverage_report: CoverageBlock \| None = None`**; `_Day.coverage_block`; `_assess_day` computes `coverage_block(evidence, expected_n=n_exp)` from the same per-slot evidence it already builds and attaches it to the three `_Day` results that follow; `_row` copies it | the narrowest carrier: the existing shared type, no second coverage model, no recalculation elsewhere |
| `tests/backend/data/gdelt/test_sentiment_aggregator_coverage_report.py` (new) | 13 focused tests | section 4 |
| `reports/phaseB2S2_8I_...md` (new) | this report | requested |

Semantics, documented on the field: report-only; uses the shared **provisional default** thresholds (not the aggregator's `coverage_threshold`), so its threshold results can differ from the
aggregator's gate; `None` when an interval's slots cannot be listed (`no_expected_slots`, `slot_grid_mismatch`) rather than an invented block; one identical block per interval, shared by the three
themes. No schema/migration change; the field has a default, so existing constructors and consumers that ignore it keep working.

## 4. Tests

| Required case | Test result |
| --- | --- |
| Clean reconciled interval | block present (96/96, ratio 1.0), `json.dumps(asdict(block))` works; existing `coverage` 1.0, status `ok`, `n_slots_*` unchanged; verified empty day still `no_news = True` |
| Processed but unreconciled | **existing:** 8 wrong slots counted covered (`coverage` 1.0, `n_slots_covered` 96, status `slot_article_mismatch`); **report-only block:** `n_covered` 88, 8 excluded as `rejected`, missing run 8. Divergence visible; existing values unmoved; neither declared authoritative |
| Missing / incomplete evidence | 60 absent slots → block `final_absent` 60, 36 covered, equal to the existing 0.375; delayed → `delayed_after_cutoff`; all-NULL flags → `near_empty_unknown` 96; no-slot and grid-mismatch intervals → no block; lookback not examined or unresolved with a perfect 1.0 ratio → `no_news` stays `None`, status `incomplete_source_accounting`, theme evidence `not_evaluated` (existing behaviour) |
| Unresolved policies | an unapplied `PolicyState` still raises `PolicyBlockedError` (clean and unreconciled inputs); 8 unresolved |
| Backward compatibility | the new field is the only addition and is last with a default; stripping it leaves every other field identical on representative fixtures |
| Determinism | equal inputs give equal blocks; reason order is the contract's fixed order; one block per interval |
| Independence | replacing the block with an arbitrary bogus one (monkeypatch) changes no existing field; the source contains no call to `coverage_rule_decision` |

One initial expectation was wrong (I assumed `unverified_empty` for an unexamined-lookback interval; the existing behaviour is `not_evaluated`); the test was corrected to the existing behaviour, the code was not changed.

Commands (repo root, `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`):

| Scope | Result |
| --- | --- |
| `tests/backend/data/gdelt/test_sentiment_aggregator_coverage_report.py` | 13 passed |
| `tests/backend/data/gdelt/test_sentiment_*.py` (all sentiment files) | **312 passed** |
| `tests/backend/data/gdelt` (full GDELT suite, run this phase) | **1337 passed** in 68 s |

## 5. Evidence that existing values are unchanged

Before editing, a scratch script serialised **every field except the new one** of every row for 13 scenarios (78 rows): clean, empty, unreconciled, count mismatch, 60/24/96 absent,
all-NULL near-empty, some near-empty, no slot information, delayed slot, unresolved earlier batch, earlier batches not examined. After the edit the same script produced a byte-identical snapshot
(`identical existing fields: True`, 78 rows). The existing 137 scaffold/completeness tests also passed unchanged, and no existing test was edited.

## 6. OD-10 part 2 — still unresolved

The aggregator still counts a processed-but-unreconciled slot as covered; the block excludes it as `rejected`. Both are exposed; no numerator was changed and neither is approved.
Smallest decision needed: the owner's answer to OD-10 part 2 (excluded or covered).

## 7. Limitations

- The block's threshold results use shared provisional defaults and may disagree with `coverage_status` (which uses the configured threshold). Intentional for a report-only field.
- A consumer that serialises `DailyFeatures` wholesale will now see the additional field; none exists in the repository.
- `CoverageBlock` holds a plain `dict`, so a `DailyFeatures` instance is not hashable; it was not hashable-relied-upon before (no hashing found).

## 8. Post-change state and confirmations

HEAD `71b363f`; 0 staged; 49 tracked modifications (unchanged); **166 untracked** (the 164 recorded before editing plus the new test file and this report). Edited existing
file: `features.py` only (untracked, new in this track). No unrelated user work was overwritten, nothing was staged, committed, reset, cleaned or stashed. Sample tree: 546 files,
hash `271939bb1895d1d3` before and after. Policy table: unchanged (8 of 8 block). Code touched: `features.py`; no change to `completeness.py`, `coverage_report.py`, `near_empty.py`, `orchestrator.py`, `policy.py`, registries, build lock, compliance rules or evaluation criteria.
`docs/MEMORY.md` was not edited: no policy or project decision state changed (an additive report field); add a one-line entry on request.
No network, download, install, key or annotation-key access, scoring, features, evaluation, acquisition, S2.9 or S4.
