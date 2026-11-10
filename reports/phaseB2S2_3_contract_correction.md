# Research Enhancement Track — Phase B2-S2.3: Offline Sentiment Contract Correction

**Status: COMPLETE for the independently verifiable part. Offline and synthetic only. No model, network, key, label,
acquisition or approval was used or given.** Date: 2026-10-20 (UTC). Written for: the project owner.

Labels: **[VERIFIED]** checked in code, a test, or a read-only run in this phase. **[PROPOSED]** not approved.
**[BLOCKED]** needs a decision. **[UNVERIFIED]** not checked.

---

## 1. Verified root causes

Starting state [VERIFIED]: HEAD `71b363f`, nothing staged, 49 tracked modifications (pre-existing demo work plus `docs/MEMORY.md`),
51 untracked entries. The S3 report exists (`reports/phaseB2S3_sentiment_design_feasibility.md`); the B2-F, B2-G, B2-H and B2-M
reports and the local B2-M sample exist. The S1, S2.1 and S2.2 reports do not exist as files and were not reconstructed.

### Defect 1 — wrong reconciliation contract

S2.2 (`features.py`, `_reconciles`) required the `series_rows` of a slot to equal the number of article records supplied for the
batch, across all themes. In the real pipeline `series_rows` is the member count of **one series**
(`engine.py:97-100`, stored by `manifest.py:258-260` in `slot_series_count`), counted before dedup, and one row can belong to
several series. It is a different quantity from the batch's captured rows (`engine.py:127`, `manifest.py:252`), and `SlotSummary`
could carry only one number for three themes.

Re-verified in this phase by a test that reads the local sample read-only (counts and flags, no titles): the corrected contract
reconciles **192 of 192** real batches; the S2.2 reading holds in **0 of 192**.

### Defect 2 — two clocks for one batch

S2.2 placed a batch's *slot* (coverage, reconciliation) by its **nominal** time, but placed its *articles* by **verified
availability**. For a batch written late the slot stayed in the earlier interval, which counted it as covered at a cutoff when it
did not yet exist, while its articles moved to the next interval, which had no slot accounting for them. The earlier day then read
"covered, no articles, `no_news = True`" and the later day held unaccounted-for articles. The synthetic case from S3 (nominal
20:45Z, available 21:45Z) now behaves as in section 4.

### Contributing gaps closed [VERIFIED]

- No manifest-to-slot adapter existed, so the input shape was undefined (`SlotSummary` was used only by `coverage.py`).
- S2's article-level "unverified availability" had no real source: an unverified batch is rejected whole and produces no records
  (`engine.py:77-78,356-360`).
- Slot states were collapsed into a boolean `processed`, losing absent versus failed versus not-yet-final.

## 2. Before and after: the contract

| Aspect | Before (S2.2) | After (S2.3) |
| --- | --- | --- |
| Slot input | `IntervalSlot(batch_ts, SlotSummary(processed, near_empty, series_rows))` | `SlotAccounting(batch_ts, state, available_at_utc, rows_captured, theme_rows, near_empty, filter_version, parser_version)` |
| Counts compared | one `series_rows` vs total supplied records | per batch `rows_captured == len(records)`; per batch and theme `theme_rows[t] == count(records flagged t)`; every record's availability equals the batch's |
| Different-stage counts | could be mixed | `rows_english_valid`, `rows_physical`, rejected counts are never read; only same-stage counts are compared |
| Non-processed slot | boolean false | its real state (absent, failed, invalid, or not final); records for it are a mismatch |
| Non-final slot (`unverified`, `verified_available`, `in_progress`, `parsed_validated`) | counted as unprocessed | `incomplete_source_accounting`: the interval is unavailable, never guessed |
| Mismatch | one generic message | batch stamp and both numbers per difference, first three shown |
| Missing mapping | not applicable | the adapter raises; no default is invented |
| Article availability | independent of its slot | must equal its batch's availability; an unverified record in a processed slot is a mismatch |
| Mixed filter/parser versions | not checked | refused |
| `n_unavailable` feature | counted unverified articles | removed (it would always be zero and so hide missingness); `DailyFeatures` is `s2_daily_v3` |

## 3. Real count semantics and source paths [VERIFIED]

| Quantity | Meaning | Source |
| --- | --- | --- |
| `rows_physical` | every line read | `parser.py` counters; `manifest.py:249` |
| `rows_english_valid` | lines that passed row validity (includes duplicates, uncaptured rows) | `parser.py:145`; `manifest.py:251` |
| rejected (`malformed`, `date_mismatch`, `translated`, `non_web`) | counted by reason | `parser.py`; `manifest.py:249-251` |
| `rows_captured` | rows kept in the shard (duplicates and company items included) | `engine.py:127`; `manifest.py:252` |
| `slot_series_count.rows` | rows that are members of one series, pre-dedup; may overlap across series | `engine.py:97-100`; `manifest.py:258-260` |
| `near_empty_flag` | all-English-rows baseline test; null without a baseline | `engine.py:163-168,188`; `manifest.py:262-264` |
| `available_at_utc` | `max(nominal, verified Last-Modified) + 15 min`; absent if unverified | `availability.py:121-128`; `engine.py:74-78` |
| slot state | `slot_state(row)` | `manifest.py:38-56` |

Mapping to the aggregator (`sentiment/slots.py`): series `EQUITY_US`, `RATES_US`, `GOLD` map to themes `equity_us`, `rates_us`,
`gold` (`filters.SERIES` lower-cased; a test fixes this). `slot_from_manifest(row, series_rows)` takes a manifest row and a
series-to-rows mapping, uses the manifest's own `slot_state`, and raises on a missing, extra, negative or non-integer count, a
non-verified processed slot, a malformed timestamp, or a bad near-empty flag.

## 4. Batch slot to feature interval [VERIFIED by tests]

- **Source accounting** is by the **nominal** slot: the 15-minute grid of `(cutoff(previous), cutoff(d)]`
  (`[cutoff(prev), cutoff(d) - 15 min]` as nominal stamps), validated for missing, duplicate and unexpected slots.
- **Feature placement** is by **verified availability**, using the existing `session_calendar.origin_for` for slots and
  articles alike (`features.py`, `interval_of`). Exactly at a cutoff is inside; one second later is the next interval; a weekend
  time goes to the next trading day; the first calendar day is only a lower bound.
- A slot is **covered** for its nominal interval only if `available_at <= cutoff` of that interval. Otherwise it is **delayed**:
  not covered (it did not exist at the cutoff), counted in `n_slots_delayed`, its series rows counted per theme in
  `n_delayed_theme_rows`.
- Its articles enter the interval that contains their availability time, reported in `n_late_carried_in`. They are counted
  exactly once.
- Every article that enters any interval must belong to a reconciled batch. Otherwise the receiving interval is
  `slot_article_mismatch` ("without a reconciled source slot"): a late article is never silently dropped or used unaccounted-for.
  A batch whose availability is after the last cutoff has no interval in the window and is reported only through the delayed
  counts of its nominal interval.

| Case (nominal 20:45Z slot of D2, cutoff 21:00Z) | D2 | D3 |
| --- | --- | --- |
| Available 20:45Z or 21:00:00Z | counted; not delayed | nothing |
| Available 21:00:01Z | not covered (95/96); `n_slots_delayed = 1` | 1 record, `n_late_carried_in = 1` |
| Available 21:45Z, theme has rows | `no_news = None`, reason `delayed_availability` | 1 record, carried in |
| Same, for a theme the batch does not carry | `no_news = True` (genuinely verified) | nothing |
| Source slots for D2 absent | `no_expected_slots` | `slot_article_mismatch`, no features |
| Any D2 slot not final | `incomplete_source_accounting` | unaffected |

The status vocabulary now separates: verified no-news (`ok`, `no_news = True`), delayed availability (`no_news = None`, delayed
counts), incomplete accounting (`incomplete_source_accounting`, `slot_article_mismatch`, `slot_grid_mismatch`), and unavailable
features (every status other than `ok`, all values `None` with a reason).

## 5. Changes made

| File | Change |
| --- | --- |
| `backend/wealthpilot/data/gdelt/sentiment/slots.py` | **Created.** `SlotAccounting`, state vocabulary, `slot_from_manifest`, `reconcile_slot`; documents every count |
| `backend/wealthpilot/data/gdelt/sentiment/features.py` | **Edited.** `IntervalSlot` replaced by `SlotAccounting`; as-of-cutoff coverage; delayed and carried-in accounting; unaccounted-article check; `incomplete_source_accounting`; version check; `n_unavailable` removed; new fields `n_late_carried_in`, `n_slots_delayed`, `n_delayed_theme_rows`; `s2_daily_v3` |
| `tests/backend/data/gdelt/test_sentiment_scaffold.py` | **Edited.** 90 to 110 tests: slot helpers rebuilt for the new input, new S2.3 sections added, S2.2 tests kept |
| `docs/MEMORY.md` | **Edited.** One concise S2.3 entry appended (pre-existing modification of this file preserved) |
| `reports/phaseB2S2_3_contract_correction.md` | **Created** (this report) |

Not changed: `schema.py`, `fake_scorer.py`, `__init__.py`, any acquisition, parser, manifest, availability, calendar, filter or
dedup code, or any other file.

## 6. Tests executed

| Command | Result |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest tests/backend/data/gdelt/test_sentiment_scaffold.py -q -p no:cacheprovider -W ignore` | **110 passed, 0 failed** (includes the read-only real-sample test, not skipped) |
| `.venv/Scripts/python.exe -m pytest tests/backend/data/gdelt -q -p no:cacheprovider -W ignore` | **1135 passed, 0 failed** (was 1115) |
| Mutation check (12 guards broken one at a time, files restored byte-for-byte) | 11 caught (2 to 7 failures each); 1 survivor, "first day used as a row", is an equivalent mutant: that day has no output row, so the guard is redundant |

Covered: batch/theme reconciliation; counts from different stages (1121-style English-row count, all-themes-equal-captured
reading); missing, extra, negative and malformed adapter inputs; before, exactly at, one second after a cutoff; a delayed batch
from an earlier interval; a weekend delay; a batch delayed past the last cutoff; incomplete accounting for each non-final state;
late article never `no_news`; no use before availability; missing or broken source slot; availability mismatch; mixed versions;
determinism across runs, article order and slot order; all earlier S2.2 behaviour. Not run: hosted-database, frontend and
full-project suites.

## 7. Remaining blockers and decisions [BLOCKED]

1. **Late-batch policy choice.** The implemented rule is the minimum point-in-time requirement: a slot not available at the cutoff
   is not covered. A stricter alternative (make the whole interval unavailable if any slot is late) is a policy choice and was not
   made. The 0.75 threshold that decides whether a day with delayed slots is still `ok` remains unapproved.
2. **Real late-file frequency** is unmeasured (0 of 192 in the sample). Behaviour on real late data is tested only synthetically.
3. **Cross-batch dedup and `story_id`** still have no producer; the dedup and update policy, near-empty treatment, calendars,
   scoring threshold, theme-specific coverage, model, target and acquisition are unchanged and unapproved.
4. **No end-to-end producer** reads the manifest and day files into the aggregator; only the pure adapter and a read-only test
   exist. The series counts passed to the adapter are not themselves checked against the series table's `filter_version`.
5. **Pre-window late batches** need slot accounting for the interval before the first calendar day; until a caller supplies it,
   such an article makes the receiving interval a `slot_article_mismatch`.
6. **Performance** was deliberately not addressed: `origin_for` rebuilds the cutoff list per distinct availability time.
7. `reconcile_slot` is duck-typed so the real-data test could avoid constructing full records.

## 8. Actions deliberately not taken

No dedup or story policy, threshold, near-empty, calendar, theme-specific calendar, target, model, licence, dependency,
annotation or acquisition decision. No network, download, package installation, provider call, inference or scoring with a real
model. No read of the sealed key, annotation labels, AI-only data, `.env` or API keys. No edit to the manifest or any dataset (the
sample was opened `mode=ro&immutable=1`). No change to D8 criteria, the D12/D12.1 guard, the D13 lock, provider gates, build lock
or adapter registry (the tests still assert them). No production, API, optimizer or recommendation integration. No efficiency
refactor. No staging, commit or push. No S3 follow-up, S4 or other phase.

## 9. Final Git status

HEAD `71b363f`; nothing staged; 49 tracked modifications, the same count and files as at the start (`docs/MEMORY.md` was already
among them and now also carries the S2.3 entry); 51 untracked entries before this report is counted (this report and `slots.py`
are untracked additions). No pre-existing file was reverted, reformatted or cleaned up.
