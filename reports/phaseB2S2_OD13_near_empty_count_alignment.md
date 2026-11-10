# OD-13 — `n_slots_near_empty` aligned with the shared coverage report

Owner decision: **OD-13 OWNER-CONFIRMED — ALIGN.** This records and implements that one decision; it applies no policy gate. Date: 2026-10-20 (UTC).

**Change** (`sentiment/features.py::_assess_day`, one line): `n_slots_near_empty` now counts slots that are on time **and reconciled** (`covered_asof`) and flagged near-empty (`True`).
The reconciliation result is the existing verdict used for OD-10 part 2; a slot with no verdict is treated as unreconciled.

| | Before | After |
| --- | --- | --- |
| A reconciled, on-time, near-empty slot | counted | counted |
| A processed slot that fails reconciliation (or has no verdict) and is flagged near-empty | counted | **not counted** (the shared block reports it as `rejected`) |
| Unknown (NULL) flag, delayed, absent, missing slots | not counted | not counted (unchanged; unknown stays in `n_slots_near_empty_unknown`) |
| `n_slots_expected`, `n_slots_covered`, coverage, status, reasons, `no_news`, thresholds, policy statuses | — | unchanged |

Evidence: the 13-scenario / 78-row snapshot used since S2.8I is byte-identical to the S2.8J result (no scenario contained an unreconciled near-empty slot). New file
`tests/backend/data/gdelt/test_sentiment_near_empty_count_alignment.py` (7 tests: reconciled counts; unreconciled does not and equals the block's `near_empty`; no verdict does not; denominator/covered/ratio/status/`no_news`
unchanged; unknown stays unknown and never false or no-news; delayed/absent unaffected; other interval and themes unaffected). Mutation check: restoring the old line fails 4 of the 7 tests.

Tests (repo root, `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`): new file 7 passed; `test_sentiment_*.py` 356 passed; `tests/backend/data/gdelt` 1381 passed (these counts include the scorer-port, polarity-validation and pipeline tests added in the same run).
Git: HEAD `71b363f`, 0 staged, 49 tracked modifications (unchanged), 176 untracked (170 before). Policy table unchanged: 8 of 8 required policies block. Sample tree `271939bb1895d1d3` unchanged.
