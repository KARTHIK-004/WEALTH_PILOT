# Research Enhancement Track — Phase B2-S2.8E: Coverage and Near-Empty Plumbing

**Status: COMPLETE.** Source-slot coverage accounting and near-empty detector plumbing were added on the shared completeness contract.
Offline and synthetic. No scorer, candidate-to-`ArticleRecord` conversion, feature, evaluation or production use was built or
authorised. No threshold, detector parameter or lookback length was approved or chosen. Date: 2026-10-20 (UTC). Written for: the project owner.

## 1. Part A — policy and contract audit (done before coding)

Owner approval is taken only from the owner's own instruction text (S2.8B/C/D/E). A recommendation in an earlier assistant response is not
approval. The original owner-decision message is not visible to me.

| Class | Item | Status after S2.8E |
| --- | --- | --- |
| Explicitly selected | Denominator is the full expected nominal grid; unknown near-empty is neither complete evidence nor verified no-news; explicit near-empty stays distinct from missing; a missing batch is not a valid empty batch; a delayed empty batch is not verified no-news; unresolved policies block downstream use | applied in the shared contract (S2.8B/D), unchanged |
| Explicitly selected | F1 C-min with the caller-supplied `earlier_batches_from` | applied (S2.8C), **unchanged**; no lookback length chosen |
| Selected, **provisional** | Coverage 0.75 primary, 0.50 / 0.90 sensitivity; detector: previous 14 calendar days, ≥ 7 valid same-slot observations, near-empty when below 10% of the median; primary handling "explicit near-empty is uncovered" | now **explicit configuration** (`CoverageThresholds`, `NearEmptyParams`, both carrying `status = PROVISIONAL_NOT_APPROVED`) and reported. Policy statuses stay `SELECTED_PROVISIONAL_NOT_APPLIED`, so they still block scoring and features |
| Unresolved owner decisions | scoring-coverage threshold; cross-interval story uniqueness and linking rules; the absolute limit on consecutive missing slots (the run is now *reported*, no limit is applied); calendars and theme cutoffs; whether unknown near-empty should make an interval unusable instead of undecided; **the lookback length** (both for late arrivals and for the baseline); exact state names | open |
| Blocked | model, licence, dependencies, polarity validation, forecast target, filter validation, acquisition, scoring, features, evaluation, production | blocked |

**What could be implemented without resolving them:** reporting (numerator, denominator, ratio, exclusions, runs), threshold *configuration* with
no decision power, the detector as a pure function with its parameters as inputs, and a baseline-evidence *contract* (caller-declared start).
Nothing needed an owner decision to be made on the owner's behalf.

## 2. Part B — coverage definitions (`sentiment/coverage_report.py`)

- **Denominator** = the expected nominal source slots of the interval (the full grid). It is never shrunk: `coverage_block(..., expected_n=)`
  refuses a different count, duplicates are refused, and an earlier-nominal batch that arrives late adds nothing to the denominator or the numerator.
- **Covered** = accounted (processed, reconciled, valid) **and** available by the applicable cutoff **and** observed near-empty flag known false.
- **Excluded, one reason per slot** (all keys always reported, zeros included): `missing`, `rejected`, `non_final`, `final_absent`,
  `delayed_after_cutoff`, `near_empty` (explicit), `near_empty_unknown` (NULL). `covered + excluded == expected` always.
- **Delayed** batches are judged by verified availability and the existing cutoff rules upstream: availability exactly at the cutoff is on time; one second later is
  `delayed_after_cutoff`.
- **Runs:** `max_consecutive_missing_run` = longest grid-order run of slots with no valid accounted evidence (missing, rejected, non-final, final-absent);
  `max_consecutive_uncovered_run` also counts delayed and near-empty slots. No limit is applied to either.
- **Thresholds:** `ThresholdResult(threshold, label, meets)` for the primary and each sensitivity threshold (`ratio >= threshold`). It is a report; it carries
  `status = PROVISIONAL_NOT_APPROVED` and authorises nothing.
- **Kept separate:** the block is typed `source_slot_coverage` and contains no scoring or record-availability field. Per-theme evidence ignores coverage entirely, so a
  ratio can never create verified no-news (tested with ratios from 0.10 to 1.0 thresholds, and with a ratio of 0.99 that still gives `unverified_empty`).

## 3. Part C — near-empty plumbing (`sentiment/near_empty.py`)

| Behaviour | Result |
| --- | --- |
| Parameters | `NearEmptyParams(14, 7, 0.10)`, `PROVISIONAL_NOT_APPROVED`, validated |
| Baseline | the same slot of day, 1…14 days **strictly before** the assessed batch; the batch itself, later days and other slots of the day are never read |
| Usable observation | committed **and** valid, integer ≥ 0, exactly one row per stamp. Uncommitted, invalid, duplicate (ambiguous) and absent observations are counted, never used; another filter version is never mixed in |
| Lookback evidence | the caller declares `baseline_batches_from` (the first stamp from which `slot_rows` is complete). Without it, or if the 14-day lookback starts before it, the state is `UNKNOWN` (`no_baseline_evidence_declared` / `baseline_lookback_not_available`) |
| Insufficient | fewer than 7 usable → `UNKNOWN` (`insufficient_valid_baseline`, or `baseline_not_committed` when the uncommitted observations would have sufficed) |
| Decision | median of the usable values; near-empty iff `rows_english_valid < 0.10 × median` (equal is not near-empty; a zero median cannot be undercut) |
| Observed vs derived | the manifest flag stays the observed flag used by coverage; the detector's result is a separate derived state. `compare_flags` reports `agree`, `disagree`, `observed_only`, `derived_only`, `both_unknown`. A derived state never repairs a NULL flag for coverage |
| Unknown | `UNKNOWN` is never `NOT_NEAR_EMPTY`, never counted as covered, never evidence of completeness. A low count is reported as near-empty, never as missing |

**Evidence limit (documented, not fabricated).** The repository holds the 192 isolated development-sample batches, all with `near_empty_flag` NULL, and no
contiguous 14-day baseline. The detector is therefore implemented and tested against synthetic baselines only, and on the real sample every derived state
would be `UNKNOWN` (no baseline declared). The earlier audit expects NULL flags for about 7 days after any long outage and for the first 7 days of a run.

## 4. Part D — shared-contract integration (`sentiment/orchestrator.py`)

- `WindowInputs` gained `baseline_batches_from` (default `None`), `coverage_thresholds` and `near_empty_params` (provisional defaults). The window is never extended and no lookback length is chosen.
- `SlotView` gained `derived_near_empty`, `derived_reason`, `flag_comparison`; `IntervalAccounting` gained `coverage` (the block) and `derived_near_empty` (counts). `WindowReport` carries the configuration and `n_baseline_rows`.
- The digest was bumped to `wp-window-digest-v3` and binds the coverage block, the derived states, the thresholds, the detector parameters and the baseline declaration/observations.
- **Usability:** `coverage_rule_decision` returns a verdict for `assess_interval(coverage_rule_met=)` **only** while the policy status is `APPLIED_*`. The status is `SELECTED_PROVISIONAL_NOT_APPLIED`, so a below-threshold interval is `UNDECIDED_POLICY`, not `UNUSABLE_BELOW_COVERAGE_RULE`, and a meeting interval is not `USABLE_UNDER_COVERAGE_RULE`. Source completeness, interval usability, per-theme evidence and result availability remain four separate states.
- A `USABLE` interval is still `blocked_by_policy` for every theme (the unresolved model, polarity, filter-validation and other policies keep blocking scoring and features).
- **Not changed:** `features._assess_day` still uses the existing `coverage.interval_count` with the provisional threshold; it runs only after `require_policies_applied`, so it cannot be reached with an unapplied policy. I did not rewire it (out of scope; its numerator definition is the same). Recorded as a follow-up, not silently fixed.

## 5. Part E — tests actually run

New file `tests/backend/data/gdelt/test_sentiment_coverage_near_empty.py` (34 tests): full-grid denominator; missing/rejected/non-final/absent as separate reasons; delayed arrival by verified availability and the cutoff; a late earlier batch not changing the denominator; explicit vs unknown near-empty; insufficient, uncommitted, invalid and missing baselines; no future-data leakage; same-slot-only baseline; threshold sensitivity not altering verified no-news; unknown never false; source vs scoring coverage separate; usable-but-not-scoreable; digest binding; C-min intact.

| Command (from repo root, `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`) | Result |
| --- | --- |
| `tests/backend/data/gdelt/test_sentiment_coverage_near_empty.py` | 34 passed |
| focused: coverage_near_empty + completeness + orchestrator + policy | 149 passed |
| `tests/backend/data/gdelt/test_sentiment_*.py` (all sentiment files) | 299 passed |
| `tests/backend/data/gdelt` (full GDELT suite) | **1324 passed** in 71 s |

Mutation check (scratchpad script, source restored after each): 9 of 9 mutants caught — unknown counted as covered, policy status ignored, denominator shrink allowed,
future observations read, uncommitted observations used, unknown turned into false, insufficient history deciding, lookback requirement removed, coverage deciding
usability while unapplied.

Two test expectations were wrong when first written (not code defects) and were corrected: 40 near-empty slots leave a 0.58 ratio (60 used), and an all-uncommitted baseline reports `baseline_not_committed`. One real defect was found and fixed: the detector classified an uncommitted observation (no count yet) as *invalid*; it is now *uncommitted*, checked before the count.

No frontend, database or unrelated tests were run. Tests are not a package, so the new file loads the shared `World` builder by path.

## 6. Git state and sample integrity

HEAD `71b363f`; 0 staged; 110 status entries (tracked modifications plus untracked, all preserved). Nothing was staged, committed, pushed or reset. New files: `sentiment/near_empty.py`, `sentiment/coverage_report.py`, the new test file and this report; edited: `sentiment/orchestrator.py`, `docs/MEMORY.md`.
Read-only harness `s25_verify.py`: 546-file sample tree hash `271939bb1895d1d3` before and after, unchanged. No network, download, install, provider call, inference, sealed-key or label access.

## 7. Remaining blockers and next bounded step

Blockers (all owner decisions, none taken here): the lookback length (late arrivals and baseline), approval of the thresholds and detector parameters, scoring-coverage threshold, missing-slot limit, whether unknown near-empty makes an interval unusable, calendars and theme cutoffs, cross-interval story uniqueness, model/licence/dependencies, polarity validation, target, filter validation.

Next bounded step (for the owner to choose, not started): decide the lookback length and whether the provisional coverage/near-empty parameters are approved, then, if wished, wire the aggregator's `_assess_day` to `coverage_report` so one coverage definition is used end to end. S2.9 and S4 were not started.
