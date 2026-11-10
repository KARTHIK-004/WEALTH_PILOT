# Research Enhancement Track — Phase B2-S2.8B, Part B: First Corrective Implementation

**Status: COMPLETE for F5, F7, F6, F3 and F4.** Offline, synthetic. No scoring, no features, no production wiring. Date: 2026-10-20 (UTC).
Written for: the project owner. Decisions are recorded in `reports/phaseB2S2_8B_policy_decision_record.md`.

## 1. Decision-record status and unresolved approvals

- All 16 decisions are recorded with a status. The 16 individual answers were not present as a separate message in the conversation
  available to this phase, so they were taken from the S2.8B instruction text; anything that text does not address is recorded as
  **NOT STATED** and left open (questions 6, 8 and 11; the mechanism parts of 1 and 7; the lookback rule of 3; the absolute missing-slot
  limit of 5; the linking rules of 9). If the original answers differ, the record should be corrected.
- Provisional (not validated conclusions): coverage thresholds (0.75 primary, 0.50 and 0.90 sensitivity), near-empty detector parameters,
  primary near-empty handling, and the record-counting unit with its repetition sensitivity.
- Still unresolved and blocked: sentiment model and licence/dependencies, polarity validation, forecast target and protocol, independent
  validation of the GDELT filter, full-window acquisition, scoring, trusted features, model evaluation, production integration.
- Nothing is "applied": every required policy still blocks conversion and feature generation by design.

## 2. Git state

| | Start | End |
| --- | --- | --- |
| HEAD | `71b363f` | `71b363f` |
| Staged | 0 | 0 |
| Tracked modifications | 49 | 49 (same files; `docs/MEMORY.md` was already among them and gained one entry) |
| Untracked entries | 57 | 58 before this report is counted, 59 with it (the new test file, `policy.py` and the decision record are inside already-counted directories or are new files) |
| Sample tree | 546 files, hash `271939bb1895d1d3` | 546 files, hash `271939bb1895d1d3` (re-checked with the read-only harness) |

No pre-existing change was reverted, reformatted or cleaned. Nothing was staged, committed or pushed.

## 3. Files

| File | Change |
| --- | --- |
| `backend/wealthpilot/data/gdelt/sentiment/policy.py` | **Created.** Immutable `PolicyState`, `REQUIRED_POLICIES`, `require_policies_applied`, `PolicyBlockedError` |
| `backend/wealthpilot/data/gdelt/sentiment/slots.py` | **Edited.** `SlotAccounting.rows_company_item` (optional, validated); `slot_from_manifest` carries it; `reconcile_slot(..., company_evidence=False)` |
| `backend/wealthpilot/data/gdelt/sentiment/dayfile_adapter.py` | **Edited (F5).** An invalid `batch_ts` is flagged, never looked up in the manifest, and carries no batch id |
| `backend/wealthpilot/data/gdelt/sentiment/orchestrator.py` | **Edited (F5, F3, F4, F6, F7).** New counters/fields, version check, company reconciliation, immutable policy status, content-bound digest |
| `backend/wealthpilot/data/gdelt/sentiment/features.py` | **Edited (F6).** `SentimentConfig.policy` (required); `aggregate_daily` refuses while a required policy is unapplied |
| `tests/backend/data/gdelt/test_sentiment_policy.py` | **Created** (16 tests) |
| `tests/backend/data/gdelt/test_sentiment_orchestrator.py` | **Edited:** 15 new tests, builder computes `rows_company_item`, two status assertions updated to the recorded decisions |
| `tests/backend/data/gdelt/test_sentiment_adapters.py` | **Edited:** 9 new tests (F5 adapter level, F3 slot level) plus company reconciliation over the real sample |
| `tests/backend/data/gdelt/test_sentiment_scaffold.py` | **Edited:** the config fixture supplies a test-only applied policy state |
| `docs/MEMORY.md` | One concise S2.8B entry |
| `reports/phaseB2S2_8B_policy_decision_record.md`, `reports/phaseB2S2_8B_corrective_report.md` | **Created** |

Not changed: `schema.py`, `fake_scorer.py`, `manifest_adapter.py`, parser, engine, manifest, filter, availability, calendar and dedup code,
any dataset, manifest or day file, D8 criteria, the D12/D12.1 guard, the D13 lock, provider gates, compliance rules, the build lock and the
adapter registry (the existing tests still assert the lock is off and the registry empty).

## 4. Fixes and regression tests

| Fix | Behaviour now | Key tests |
| --- | --- | --- |
| **F5** invalid `batch_ts` | The day-file adapter reports `invalid_batch_ts` and does no manifest lookup for that row; the rejection carries no batch id. The orchestrator counts such records in `n_records_invalid_batch_ts`, never in `n_out_of_window_records`; the affected batch becomes `count_mismatch` | five invalid stamps (`2022-03-02`, off-grid, empty, non-digits, impossible date) at adapter and orchestrator level; a valid out-of-window stamp is still only counted |
| **F7** digest | `digest()` is a SHA-256 of canonical JSON binding: trading days, filter version, early closes, holidays, `min_chars`, observed (filter, parser) versions, the policy status, a fingerprint of the in-window manifest rows, a fingerprint of every accepted record (id, batch, availability, domain, raw title hash, filter title hash, URL hash, word count, text status, flags, company flag, same-batch status, versions, source file and line), the day-file entries, and all derived states. Order-free parts are sorted | six record-content changes alter the record fingerprint and digest while the input fingerprint is unchanged; manifest-only changes, file renaming, configuration, window, versions and policy each change it; shuffled and key-reordered inputs do not; the digest payload holds hashes, not titles or URLs |
| **F6** policy | `POLICY_STATUS` and `WindowReport.policy_status` are immutable; `policy_state()` returns a frozen `PolicyState` snapshot; `require_policies_applied` refuses any status that is not `APPLIED_APPROVED` / `APPLIED_PROVISIONAL` and refuses a plain mapping; `aggregate_daily`, the existing feature boundary, calls it before reading anything | mutating the source mapping after the snapshot (either direction) cannot bypass it; every unresolved status blocks; a missing policy blocks; assignment to the report's mapping raises; the aggregator raises with the report's real status and runs with a test-only applied state |
| **F3** company items | `rows_company_item` is validated on the slot and reconciled with the candidates' company flags; a mismatch, a missing count, or records without the flag make the batch `count_mismatch` (never reconciled). On the real sample it reconciles 192/192 (1,560 company items) | matching and three mismatching counts, the S2.7 reproduction, a row with no count (rejected), explicit problems for missing evidence, default behaviour unchanged |
| **F4** versions | If processed batches come from more than one (filter, parser) pair, the window fails closed: every processed batch is `version_mismatch`, no day file is read, every interval is `incomplete_accounting`, and one window-scope issue lists the versions. A window with a single version, even a new one, is unchanged. Other filter versions are still rejected per batch | mixed parser versions (the S2.7 reproduction), a clean all-v2 window, a mixed filter version |

Status labels changed to follow the recorded decisions: coverage threshold, near-empty handling and dedup/story retention are
`SELECTED_PROVISIONAL_NOT_APPLIED`; late-batch strictness is `SELECTED_NOT_APPLIED`; the others are unchanged. Two earlier assertions were
updated accordingly; no other existing test needed a behavioural change.

Intentional interface changes: `SentimentConfig` now requires a `policy`; `SlotAccounting` has an optional `rows_company_item`;
`reconcile_slot` has a keyword `company_evidence`; `WindowReport` has new fields; a new slot state `version_mismatch`.

## 5. Test results (actually run)

| Command | Result |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest tests/backend/data/gdelt/test_sentiment_orchestrator.py tests/backend/data/gdelt/test_sentiment_policy.py -q -p no:cacheprovider -W ignore` | **56 passed** |
| `.venv/Scripts/python.exe -m pytest tests/backend/data/gdelt/test_sentiment_adapters.py tests/backend/data/gdelt/test_sentiment_scaffold.py -q -p no:cacheprovider -W ignore` | **145 passed** |
| all four sentiment test files together | **201 passed** |
| `.venv/Scripts/python.exe -m pytest tests/backend/data/gdelt -q -p no:cacheprovider -W ignore` | **1226 passed, 0 failed** (was 1187) |
| mutation check (15 guards broken one at a time, files restored byte-for-byte) | 13 caught; 2 survivors, both equivalent (below) |
| read-only sample harness (`s25_verify.py`, scratchpad) | 192/192 slots, 170/170 day files, 26,854 records, 0 rejections, tree hash unchanged |

Two surviving mutants are equivalent, not gaps: removing the manifest lookup for an invalid stamp changes nothing because the branch order
already skips the lookup; and un-sorting the record fingerprint changes nothing because record order and `source_line` already move together.

A first draft of the new orchestrator tests was lost to a shell quoting error and rewritten; the 56/145/201/1,226 figures above come from
the final files. Not run: frontend, hosted-database and full-project suites.

## 6. Datasets, manifests and day files

Unchanged. The sample was opened only read-only (`mode=ro&immutable=1`); its 546-file (path, size, mtime) hash is identical before and
after (`271939bb1895d1d3`), the test that reads it checks the same, and no committed day file or manifest was written.

## 7. Remaining blockers and limitations

1. **F1** (earlier nominal batches arriving inside the window) is still open: an interval can still be reported complete when a pre-window
   batch is available inside it. Selected direction: detect it; the mechanism and any lookback length need a decision.
2. **F2/F2b** are open: the orchestrator and the aggregator still use different empty-interval rules, and a NULL near-empty flag still makes
   every aggregator interval `insufficient_coverage`.
3. **Coverage and near-empty plumbing, the sensitivity runs, and repeated-content labelling** are not built.
4. The guard stops accidental use; it cannot prove an `APPLIED_*` status is genuine (whoever builds the state attests to it). Production
   code builds no applied state; only tests do, and the fixture says so.
5. The aggregator cannot verify company counts (`ArticleRecord` has no company flag); it relies on records that the orchestrator already
   reconciled, and no candidate-to-`ArticleRecord` conversion exists.
6. The digest does not bind the tool's code version, the filter-specification hash, or the manifest database and day-file paths, because the
   existing schema does not provide them (`source_name` is the caller's label).
7. Everything in section 3 of the decision record (model, polarity validation, target, filter validation, acquisition, scoring, features,
   evaluation, production) remains blocked.

## 8. Recommended next step

A separately bounded follow-up in this order, each with synthetic tests first: (1) F1 with the owner's chosen mechanism (detect and fail
closed is the smallest); (2) one completeness vocabulary shared by the orchestrator and the aggregator, which settles F2 and F2b and needs
decisions 1, 8 and 11; (3) coverage and near-empty plumbing with the recorded primary and sensitivity settings. Please first answer the
NOT STATED items in the decision record. Stopped here: S2.9 and S4 were not started.
