# Research Enhancement Track — Phase B2-S2.6: Window Orchestrator Design and Synthetic Integration Tests

**Status: COMPLETE (offline, synthetic, no scoring).** An isolated orchestrator now connects the manifest adapter, the day-file adapter
and the interval rules across a window and returns accounting and unscored candidate records. It produces no sentiment, no
`ArticleRecord`, no feature and no `no_news` flag, and is connected to nothing in production. Date: 2026-10-20 (UTC). Written for:
the project owner.

Labels: **[EXISTING]** an interface that was already in the repository. **[NEW]** added in this phase. **[PROPOSED]** designed but not
built. **[BLOCKED]** needs a decision or a missing contract. **[VERIFIED]** shown by a test or a read-only check in this phase.

---

## 1. Verified starting state

- HEAD `71b363f`; nothing staged; 49 tracked modifications; 54 untracked entries [VERIFIED before editing]. All were preserved.
- Present: the S3 report, the S2.3, S2.4 and S2.5 reports, `docs/PROJECT_PLAN.md`, `docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md`. The S1,
  S2.1 and S2.2 reports do not exist as files and were not reconstructed.
- Before any edit the sentiment tests passed; after the one refactor in `features.py` (section 5) they still passed (137).

## 2. Existing and proposed interfaces

### Existing [EXISTING]

| Interface | Role used here |
| --- | --- |
| `manifest_adapter.adapt_manifest(slot_rows, series_rows, *, filter_version, expected_batches)` | manifest rows to `SlotAccounting` plus rejections |
| `dayfile_adapter.adapt_day_file(data, *, utc_day, slots, min_chars, source_name, day_commit)` | day-file bytes to unscored `CandidateRecord`s plus rejections |
| `slots.reconcile_slot(slot, records)` | per-batch and per-theme count and availability reconciliation |
| `session_calendar.cutoff_utc`, `origin_for`; `timeutil.slot_grid`, `format_batch_stamp` | cutoffs, interval of an availability time, the nominal batch grid |
| `output.Layout.day_path(day)` | the established day-file path convention (`filtered/<filter_version>/YYYY/YYYY-MM-DD.tsv.gz`); **not** used by the orchestrator, which takes a source callable |

### New [NEW]

`backend/wealthpilot/data/gdelt/sentiment/orchestrator.py`

```text
orchestrate_window(WindowInputs) -> WindowReport

WindowInputs(trading_days, early_closes, market_holidays, filter_version, min_chars, slot_rows, series_rows, day_source)
    day_source: Callable[[str utc_day], DayFileData | None]
    DayFileData(data: bytes, source_name: str, day_commit: Mapping | None)

WindowReport(trading_days, filter_version, intervals, slots, day_files, issues, repeated_content,
             n_manifest_rows_outside_window, n_out_of_window_records, n_records_beyond_window, n_records_held_back, policy_status)
    .interval(d) -> IntervalAccounting       .digest() -> str
```

- The window is an explicit calendar (`trading_days`, validated by the same rules as the aggregator; the first day is only a lower
  bound). Manifest rows may be the whole manifest: rows of batches outside the window's nominal grid are counted, not adapted.
- Inputs are rows and bytes; the module does no file, database or network access. How a file-backed `day_source` finds and reads a
  day file is a thin wrapper around `Layout.day_path` and the `day_commit` row **[PROPOSED, not built]**; no path convention was
  invented.
- Small public helpers were added to `features.py` so nothing is implemented twice **[NEW]**: `check_calendar_inputs`,
  `check_calendar`, `interval_cutoffs`, `nominal_grids`, `interval_locator`. The aggregator now calls them; behaviour is unchanged.
- **Output is accounting, not sentiment.** `IntervalAccounting` holds status, slot-state counts, the placed `CandidateRecord`s,
  per-theme record counts, delayed and carried-in counts, unresolved inflow, and `no_news_basis`. The test suite asserts that the
  report has no `mean_*`, `no_news`, prediction, score or `story_id` field.

### Proposed, not built **[PROPOSED / BLOCKED]**

| Interface | Why it is not built |
| --- | --- |
| Candidate record to `ArticleRecord` | needs a scorer and a `story_id` policy; the schema was not changed |
| Orchestrator report to `aggregate_daily` inputs | depends on the previous row |
| File-backed `day_source` | I/O wrapper over `Layout.day_path`; deliberately kept out of the pure module |
| Reading the manifest database | I/O; done only in tests/harnesses so far |

## 3. State model and transition rules

### Per-batch state (`SlotView.state`), decided in this order for each nominal batch of the window

| Order | Condition | State |
| --- | --- | --- |
| 1 | no manifest row for an expected batch | `missing_manifest_slot` |
| 2 | the manifest adapter rejected the row (wrong filter version, missing or duplicate series, inconsistent counts, duplicate `batch_ts`, invalid state fields) | `slot_rejected` |
| 3 | manifest state `unverified`, `verified_available`, `in_progress`, `parsed_validated` | `non_final_slot` |
| 4 | manifest state absent, failed, inaccessible or invalid | `source_batch_absent` (final; no records allowed) |
| 5 | processed, but its UTC day has no file | `day_file_missing` |
| 6 | processed, but the day file is untrusted (no `day_commit`, hash, status, day, row count, header or readability problem) | `day_file_invalid` |
| 7 | a record id of the batch is ambiguous | `duplicate_record_id` |
| 8 | per-batch or per-theme counts, or availability, do not reconcile (including a rejected record that left a gap) | `count_mismatch` |
| 9 | reconciled, available after the cutoff of its nominal interval | `delayed` (records enter the interval of their availability) |
| 10 | reconciled and on time | `reconciled` |

Records of a batch that is not `reconciled` or `delayed` are never placed in an interval (they are counted as held back). A
record whose batch has no matching processed slot (no manifest row, rejected row, or a non-processed slot) is a record-scope issue
and is never placed. A record of a batch outside the window is counted as out of window, not an error.

### Interval status (`IntervalAccounting.status`)

| Status | Rule |
| --- | --- |
| `incomplete_accounting` | any slot in states 1-3 or 5-8, or an unreconciled processed batch whose known availability falls in this interval (`unresolved_inflow`) |
| `partial_source_accounting` | otherwise, some `source_batch_absent`. Whether that is enough is the unapproved coverage-threshold decision, so no verdict is given |
| `accounted_with_delayed` | otherwise, some `delayed` |
| `accounted_complete` | every nominal slot `reconciled` |

### Empty intervals (`no_news_basis`, per theme)

`has_records` if the interval holds a record of the theme. Otherwise `verified_complete_no_records` **only** for
`accounted_complete`; else `unverified_empty_incomplete`, `unverified_empty_partial` or `unverified_empty_delayed`. A delayed batch is
never evidence of absence, even when it carries no rows: at the cutoff it did not exist yet, so absence cannot be verified
point-in-time. (This is stricter than the aggregator, which downgrades only when the delayed batch carries rows of the theme.)

### Repeated content

Repeated canonical URLs and filter title hashes are preserved and only counted, window-wide and across batches
(`RepeatedContent`, policy `UNRESOLVED_NOT_APPLIED`). No story identity is inferred and nothing is removed.

## 4. Synthetic test coverage and results

`tests/backend/data/gdelt/test_sentiment_orchestrator.py` builds a synthetic window (manifest rows, series rows, gzip day files and
`day_commit` hashes that agree) and breaks one thing at a time. 25 tests:

reconciled on-time batch; several batches and ordering; empty window with complete accounting; missing manifest slot; missing day
file; untrusted day file (hash, missing and superseded commit); non-final slot; absent source batch (partial accounting); incorrect
filter version (slot, series, requested version); per-batch and per-theme count mismatch; record with no matching slot (no row,
non-processed slot); records outside the window; availability mismatch; duplicate record ids; batch available exactly at the cutoff;
one second after the cutoff; late batch entering a later interval (never used earlier, never dropped, beyond-window case);
unreconciled late batch (unresolved inflow); delayed empty batch not treated as absence; weekend window; repeated URLs and title hashes
across batches (preserved, counted, no story fields); determinism across runs and input order (digest); wrong calls and bad calendars;
early-close and holiday inputs; no scoring or feature fields and no scorer imports.

| Command | Result |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest tests/backend/data/gdelt/test_sentiment_orchestrator.py tests/backend/data/gdelt/test_sentiment_adapters.py tests/backend/data/gdelt/test_sentiment_scaffold.py -q -p no:cacheprovider -W ignore` | **162 passed, 0 failed** (25 new) |
| `.venv/Scripts/python.exe -m pytest tests/backend/data/gdelt -q -p no:cacheprovider -W ignore` | **1187 passed, 0 failed** (was 1162) |
| Mutation check (13 guards in the orchestrator broken one at a time, file restored byte-for-byte) | **13 of 13 caught** (1 to 9 failing tests each) |

Not run: frontend, hosted-database and full-project suites. A test fixture bug was caught by the adapter itself: a synthetic row with
`rows_physical` below its other line classes was rejected as inconsistent, which is the intended behaviour.

## 5. Changes

| File | Change |
| --- | --- |
| `backend/wealthpilot/data/gdelt/sentiment/orchestrator.py` | **Created** |
| `tests/backend/data/gdelt/test_sentiment_orchestrator.py` | **Created** (25 tests) |
| `backend/wealthpilot/data/gdelt/sentiment/features.py` | **Edited (behaviour-preserving refactor):** extracted `check_calendar_inputs`, `check_calendar`, `interval_cutoffs`, `nominal_grids`, `interval_locator` so the orchestrator reuses them; `SentimentConfig` and `aggregate_daily` call them. Messages unchanged; the existing 137 sentiment tests pass unchanged |
| `docs/MEMORY.md` | Concise S2.6 entry appended |
| `reports/phaseB2S2_6_orchestrator_design.md` | **Created** (this report) |

Not changed: `slots.py`, `schema.py`, `fake_scorer.py`, both adapters, the test files for them, the parser, engine, manifest, availability,
filter and dedup code, any dataset or any other report. The sample was not touched in this phase (its tree still has 546 files).

## 6. Research decisions deliberately left unresolved

Cross-batch deduplication and story-update policy; cross-interval story uniqueness; the source coverage threshold (0.75) and any
scoring-coverage threshold; near-empty-slot handling (the count is exposed only for `reconciled` and `delayed` batches); holiday and
early-close calendars (caller-supplied, labelled `CALLER_SUPPLIED_NOT_APPROVED`); theme-specific calendars and cutoffs
(`NOT_IMPLEMENTED`); late-batch strictness beyond the minimum point-in-time rule; forecast target; sentiment model, licence and
dependency route; polarity validation; full-window acquisition. Each is carried in `WindowReport.policy_status` so a downstream user
cannot mistake the report for an approved result.

## 7. Blocked implementation

1. **Candidate to `ArticleRecord`:** requires a scorer and a `story_id` policy; `ArticleRecord` has no unscored state.
2. **Feeding `aggregate_daily`:** depends on 1.
3. **Cross-batch story pass:** a policy decision (and its warm-up) comes first.
4. **File-backed day source and manifest reader:** straightforward I/O wrappers over existing conventions, not built.
5. **Real late-batch behaviour and complete real intervals:** not testable; the only real data has none. Everything here is synthetic.
6. **Late batches from before the first interval** cannot be accounted for; include an earlier trading day to cover them.
7. **Coverage verdict for `partial_source_accounting`:** blocked on the threshold decision.

## 8. Confirmation

No scorer was called or imported by the orchestrator (a test asserts the source); no `ArticleRecord` or prediction is created; no daily
feature is produced; nothing is wired into production, API routes, the optimizer or recommendations. No network, installation, model
download, inference, provider call, sealed key, annotation label, AI-only data or `.env` was used. D8 criteria, the D12/D12.1 guard,
the D13 lock, provider gates, compliance rules, build lock and adapter registry are untouched (existing tests still assert them). No
sample data, manifest or committed day file was modified.

## 9. Final Git status

HEAD `71b363f`; nothing staged; **49 tracked modifications** (the same files as at the start; `docs/MEMORY.md` now also carries the S2.6
entry); untracked entries 54 before this report and 55 with it. Changed or created this phase: `orchestrator.py`,
`test_sentiment_orchestrator.py`, `features.py` (refactor), `docs/MEMORY.md`, this report. No commit, stage or push. Stopped after S2.6;
S2.7 and S4 were not started.
