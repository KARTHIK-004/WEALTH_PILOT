# Research Enhancement Track — Phase B2-S2.5: Read-Only GDELT Sentiment Adapters

**Status: COMPLETE. Two deterministic, pure adapters were implemented and tested. No scoring, no features, no production wiring.**
Date: 2026-10-20 (UTC). Written for: the project owner.

Labels: **[VERIFIED]** checked by a test or a read-only run in this phase. **[CODE]** read in the repository. **[BLOCKED]** needs an
owner decision or a missing interface.

---

## 1. Verified starting state

- HEAD `71b363f`; nothing staged; 49 tracked modifications; 53 untracked entries [VERIFIED before editing]. All pre-existing
  modifications were preserved; the only tracked file edited is `docs/MEMORY.md` (already modified before this phase).
- Present: `reports/phaseB2S3_sentiment_design_feasibility.md`, `phaseB2S2_3_contract_correction.md`, `phaseB2S2_4_integration_audit.md`,
  `docs/PROJECT_PLAN.md`, `docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md`. The S1, S2.1 and S2.2 reports do not exist as files and were not
  reconstructed.

## 2. Source schemas and interfaces implemented

### Source schemas used [CODE]

| Source | Schema |
| --- | --- |
| Manifest `slot` | `manifest_schema.sql:49-127`: `batch_ts` primary key; state columns `existence`, `fetch_status`, `parse_status`, `commit_status`; `availability_status`, `available_at_utc`, `near_empty_flag`, `filter_version`, `parser_version`; ten stage counts (`rows_physical` ... `rows_audit_sample`) |
| Manifest `slot_series_count` | `:159-167`: primary key `(batch_ts, filter_version, series)`; `rows`, `rows_us_relevant`, `new_stories` (never populated) |
| Manifest `day_commit` | `:169-188`: `(utc_day, filter_version, parser_version)`, `status`, `rows_kept`, `file_sha256` |
| Day file | `output.py:21-28` (`COLUMNS`, 39 columns), gzip TSV, header then `captured` rows, one UTC day of nominal stamps (`output.py:135-147`) |

### Adapter A — `backend/wealthpilot/data/gdelt/sentiment/manifest_adapter.py`

`adapt_manifest(slot_rows, series_rows, *, filter_version, expected_batches=None) -> ManifestAdaptation(slots, sources, rejections)`.

- Input is plain mappings (`dict(sqlite_row)`); the module does no I/O. `filter_version` is explicit and required.
- Identifier: the canonical `batch_ts` (validated with the existing `parse_batch_stamp`). A duplicate `batch_ts` rejects every copy.
- State: the manifest's own `slot_state`. `processed` needs `existence = present_verified` and `parse_status = parsed_validated`.
  Non-final and failed states become non-final `SlotAccounting`s (no counts), never `processed`.
- Series counts are selected by `(batch_ts, filter_version, series)`; a processed slot must carry the requested version and exactly one
  row for each of `EQUITY_US`, `RATES_US`, `GOLD`. Other versions are never mixed in (they are only named in the rejection).
- Stage counts are validated as non-negative integers and kept as provenance (`SlotSource.stage_counts`). Only relations that hold by
  construction are checked, as inequalities between nested sets: `captured <= english_valid`, `company_item <= captured`,
  `audit_sample + captured <= english_valid`, `dup_same_batch <= english_valid`, disjoint line classes `<= physical`, and
  `us_relevant <= rows` within a series. Equality between `english_valid`, `captured`, duplicate counts and series rows is never required.
- `SlotAccounting` is built by the existing `slots.slot_from_manifest` (no parallel timestamp or state system).
- Every problem is a `Rejection(batch_ts, code, detail)`; a rejected batch yields no slot. Output and rejections are sorted, so the
  result does not depend on input order. `expected_batches` adds `missing_manifest_row` / `unexpected_batch`. `require_ok()` raises.

### Adapter B — `backend/wealthpilot/data/gdelt/sentiment/dayfile_adapter.py`

`adapt_day_file(data, *, utc_day, slots, min_chars, source_name, day_commit=None) -> DayFileResult(records, rejections, file_sha256, rows_read, integrity_checked)`.

- Takes the file's bytes (the caller reads the file) and the slots from Adapter A. The header must equal `output.COLUMNS` before any row
  is read. With `day_commit`, it checks committed status, day, versions, `rows_kept` and the SHA-256 of the bytes; an untrusted file
  yields no records.
- Each row must be a `captured` row with a well-formed record id whose prefix equals `batch_ts`, a batch on the file's UTC day, a
  processed manifest slot, availability equal to the slot's verified availability, and filter/parser versions equal to the slot's.
  Flags must be 0/1, `mech_dup` one of the three same-batch statuses the engine can write, the filter title hash empty or a SHA-256,
  and the required provenance fields non-empty. Duplicate record ids reject every copy. A rejected row carries its line and record id;
  the other rows are returned but `ok` is false.
- `CandidateRecord` is **not** an `ArticleRecord`. It keeps `article_id`, `batch_ts`, `available_at_utc`, `source_domain`, the title
  (not shown in `repr`), `text_status` (`ok`, `empty`, `short`, `malformed`, using the explicit `min_chars`), `title_sha256_raw` (the
  hash of the stored title) kept apart from `filter_title_hash` (the filter's normalised hash, copied unchanged), `url_canonical` and
  `word_count` (only the inputs a future story pass would need), theme flags, `company_item`, `same_batch_status`, versions and the
  source file and line. It has no `story_id`, no cross-batch status, no model, probability, label or score, and no page publication time.
- Sorted by `(batch_ts, numeric sequence)`; `find_duplicate_record_ids` reports ids repeated across files.

## 3. Changed files

| File | Change |
| --- | --- |
| `backend/wealthpilot/data/gdelt/sentiment/manifest_adapter.py` | **Created** (Adapter A) |
| `backend/wealthpilot/data/gdelt/sentiment/dayfile_adapter.py` | **Created** (Adapter B) |
| `tests/backend/data/gdelt/test_sentiment_adapters.py` | **Created**: 27 tests (synthetic) plus the read-only sample test |
| `tests/backend/data/gdelt/test_sentiment_scaffold.py` | **One-line edit** to the isolation scan so it skips the scaffold's own `test_sentiment_*.py` files (otherwise the new test file, which must import the package, tripped the "nothing else imports the scaffold" check) |
| `docs/MEMORY.md` | Concise S2.5 entry appended |
| `reports/phaseB2S2_5_adapter_implementation.md` | **Created** (this report) |

Not changed: `slots.py`, `schema.py`, `features.py`, `fake_scorer.py`, the parser, engine, filter, manifest, availability, dedup code, any
dataset or other report.

A real defect was found by the sample test during development and fixed: the duplicate-id check initially keyed on column 0
(`row_kind`) instead of `gkg_record_id`, which rejected whole files. The synthetic tests did not catch it; the real files did.

## 4. Tests

| Command | Result |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest tests/backend/data/gdelt/test_sentiment_adapters.py tests/backend/data/gdelt/test_sentiment_scaffold.py -q -p no:cacheprovider -W ignore` | **137 passed, 0 failed** (27 new; the sample test ran, not skipped) |
| `.venv/Scripts/python.exe -m pytest tests/backend/data/gdelt -q -p no:cacheprovider -W ignore` | **1162 passed, 0 failed** (was 1135) |
| Mutation check on the adapters (15 guards broken one at a time, files restored byte-for-byte) | **15 of 15 caught** (1 to 3 failing tests each) |

Not run: hosted-database, frontend and full-project suites.

Manifest tests: valid final slot; each non-final state; missing field and null value; duplicate `batch_ts`; invalid timestamp and
inconsistent state; missing, wrong-version, mixed-version, duplicate, unknown and malformed series rows; inconsistent captured, theme and
stage counts; different stages not required to match; expected/orphan batches; wrong argument types; determinism under shuffling.
Day-file tests: multi-theme record; unscored/no story identity; raw versus filter hash; empty, short and malformed titles kept;
malformed rows with line and id; missing provenance; availability, version, batch and slot-state mismatches; duplicate ids;
several batches per file; repeats across batches kept without dedup; ordering and determinism; header and file-level failures;
day-commit checks; wrong calls; reconciliation through the existing `reconcile_slot`; no scoring/production wiring.

## 5. Sample verification (local B2-M sample, read-only)

Harness: `s25_verify.py` in the session scratchpad and the pytest sample test. Manifest opened `mode=ro&immutable=1`; counts and hashes only.

| Check | Result [VERIFIED] |
| --- | --- |
| Integrity of the sample tree | 546 files, (path, size, mtime) hash `271939bb1895d1d3` before and after: **unchanged** (also identical to the S2.4 value, so unchanged since then) |
| Adapter A | 192 slot rows and 576 series rows give **192 accepted processed slots, 0 rejections**; reversed input gives an identical result |
| Adapter B | 170 day files, all integrity-checked (hash, status, day, versions, `rows_kept`): **170 ok, 26,854 records, 0 rejections**; 0 duplicate ids across files |
| Traceability | records exist for 192 batches; 0 batches unmatched in either direction; 0 slots fail `reconcile_slot`; every record's availability equals its slot's |
| Theme counts | records flagged: equity 2,751, rates 2,909, gold 193; manifest series rows: identical |
| Text states | ok 26,599; short 206; empty 37; malformed 12 (all kept) |
| Same-batch status | ORIGINAL 22,038; SYNDICATED_SAME_BATCH 4,555; DUP_SAME_BATCH 261 |
| Hashes kept apart | filter title hash empty in 255 records; raw hash equals the filter hash in 45 records |
| Repeats retained, not deduplicated | 133 canonical URLs and 2,071 filter title hashes occur in more than one record (within or across batches) |
| Determinism | a second full run is equal; content digest `490edbc0c184a7b9` |
| Negative controls (in memory only) | one slot's availability moved +15 minutes: 1 day file rejected (148 `availability_differs_from_manifest`); one slot removed: 148 `batch_not_in_manifest`; wrong `filter_version` requested: 0 accepted (192 `filter_version_differs`, 192 `missing_series`) |

## 6. Unmatched and rejected records

On the real sample there are **none**: 0 rejected slots, 0 rejected files, 0 rejected rows, 0 unmatched batches, 0 duplicate ids. The
only rejections occur in the negative controls above and in the synthetic tests, which exercise every rejection code.

## 7. Limitations and blockers

- **Not validated:** the full interval pipeline and real late-batch handling. The sample has no complete 96-slot day and no late batch
  (`late_flag` 0 in 192); the adapters were validated per batch and per file only.
- **Pre-score to `ArticleRecord` [BLOCKED]:** `ArticleRecord` requires a model identity, a label or an explicit `unavailable` reason,
  and `story_id`. Converting a `CandidateRecord` needs a scorer (blocked) and a `story_id` policy (blocked). The missing interface is a
  decision on how an unscored, story-less record enters `aggregate_daily`; nothing in the schema was changed.
- **Cross-batch story identity [BLOCKED]:** no `story_id` or cross-batch status is produced; 133 URLs and 2,071 title hashes repeat in
  the sample and are retained untouched. `url_canonical` and `word_count` are kept only as future inputs.
- **No window orchestrator:** nothing yet combines trading days, the nominal grid, the two adapters and the aggregator; the adapters
  take already-read rows and bytes.
- **`min_chars`** is passed explicitly (the sample test reads the filter specification's `title_hash_min_chars`); `text_status`'s
  "short" rule is the schema's, not the filter's normalised-length rule, so the two can differ per row.
- **Empty and CRLF line counts** are not in the manifest, so the physical-line identity is checked only as an inequality.
- **Unapproved and unchanged:** dedup and story-update policy, coverage and scoring thresholds, near-empty handling, holiday and
  early-close calendars, theme-specific cutoffs, late-batch strictness beyond the existing rule, target, model, licence, dependency,
  full-window acquisition. Adapter correctness says nothing about sentiment-model validity.

## 8. Confirmation: no scoring, no production integration

No sentiment was scored: the fake scorer is not imported by either adapter (a test asserts it), no `ArticleRecord` or neutral
prediction is created from a candidate, and `aggregate_daily` was not run on any real data, so no trusted feature was produced. The
adapters are called only from tests and the scratchpad harness; no API, optimizer, recommendation or request path imports them (the
isolation scan passes). No network, download, installation, model, provider call, sealed key, annotation label, AI-only data, `.env`
or secret was used; no title or URL was printed. D8, the D12/D12.1 guard, the D13 lock, provider gates, build lock, adapter registry
and compliance rules are untouched (the existing tests still assert them).

## 9. Final Git status

HEAD `71b363f`; nothing staged; **49 tracked modifications** (the same files as at the start; `docs/MEMORY.md` now also carries the S2.5
entry); untracked entries 53 before this report and 54 with it (the sentiment package and test directory are already counted as
directories). No commit, stage or push. No pre-existing file was reverted, reformatted or cleaned. Stopped after S2.5; S2.6, the S3
follow-up and S4 were not started.
