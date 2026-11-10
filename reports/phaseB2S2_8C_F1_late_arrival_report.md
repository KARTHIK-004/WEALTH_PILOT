# Research Enhancement Track — Phase B2-S2.8C: Reconciled Policy Record and F1 (Earlier Nominal Batches Arriving Inside the Window)

**Status: COMPLETE.** The policy record is reconciled and F1 is fixed under policy C-min. Offline, synthetic. No scoring, features, evaluation
or production use is authorised or built. Date: 2026-10-20 (UTC). Written for: the project owner.

## 1. Reconciled policy-record status

### What changed in the record

The S2.8B record marked question 7 (late and earlier-nominal batches) as "mechanism NOT STATED". The S2.8C instruction states that the
earlier owner-decision message **selected C-min**. That is now recorded:

| Q7 | Decision | Status |
| --- | --- | --- |
| Earlier-nominal batches arriving inside the window | **C-min:** detect batches whose nominal timestamp is before the requested window and whose verified availability falls inside it; mark the affected receiving interval incomplete until the earlier batch is accounted for; do not silently extend the requested window | **SELECTED**, applied in this phase |
| Rationale | It stops a false "verified no records" with the smallest change, keeps the requested range intact, and defers the lookback length and any extension of the range until real lateness is measured on a contiguous window | |
| Attestation | The earlier owner message itself is **not visible** in the conversation available to this phase; the decision rests on the S2.8C instruction text that quotes it. This is a recorded attestation, not a verified quotation | |
| Still open inside Q7 | the **length of the lookback** (it is a caller-supplied parameter, `earlier_batches_from`), and whether earlier files should be read beyond the lookback | open |

### How the other entries are classified now

The S2.8B record used "NOT STATED". Because the earlier message is not visible, that label is too strong for items the message may have
answered. The distinction is now explicit:

| Class | Meaning | Items |
| --- | --- | --- |
| SELECTED (explicit in the evidence available) | stated in the S2.8B or S2.8C instruction | 1 (principle), 2, 4, 5 (denominator), 7 (C-min), 9 (retention), 10, 12, 13, 14, 15, 16 |
| PROVISIONAL (selected, not validated) | thresholds 0.75 / 0.50 / 0.90, near-empty detector parameters, primary near-empty handling, the record-counting unit and its repetition sensitivity | 2, 3, 4, 10 |
| UNCONFIRMED (not found in the evidence available; may have been answered in the earlier message) | the owner should confirm or answer | 6 scoring-coverage threshold; 8 delayed batch with zero rows; 11 shared vocabulary; the mechanism parts of 1; the lookback rule of 3; the absolute missing-slot limit of 5; the linking rules of 9 |
| EXPLICITLY UNANSWERED | an answer was given as "not decided" | none is known |

No provisional parameter was upgraded to a validated conclusion. The S2.8B decision record gets a short supersession note (appended; its
text was not rewritten). The policy status for late-batch handling is now `SELECTED_APPLIED_LOOKBACK_UNDECIDED`: applied, but still
blocking the downstream guard because the lookback length is undecided.

## 2. F1: exact behaviour before and after

**Before (S2.7 reproduction P1).** A processed batch with nominal time 2022-03-01 10:00Z (before the first interval opens at 21:00Z), one
equity record, and verified availability 2022-03-02 05:00Z (inside the interval for 2022-03-02). The orchestrator counted its manifest row as
"outside the window" and ignored it. Result: the 2022-03-02 interval `accounted_complete`, equity basis `verified_complete_no_records`, 0
records, no issue.

**After.**

| Situation | Result |
| --- | --- |
| The same batch, read, validated and reconciled | its record is placed in the 2022-03-02 interval; state `late_arrival_reconciled` with nominal time, verified availability and receiving interval kept; the interval is `accounted_with_delayed`; themes with no record are `unverified_empty_delayed`, never verified no-records |
| The same batch, counts do not reconcile (or day file missing/invalid, duplicate id, version conflict) | the receiving interval is `incomplete_accounting`; an `earlier_batch_unresolved` issue names the batch, its nominal time, its verified availability and the receiving interval; its records are held back and counted, not dropped |
| No manifest row for a batch in the lookback | cannot be placed: **every** interval is incomplete (`earlier_batch_unresolved`, `missing_manifest_row`) |
| Non-final earlier batch (availability unknown) | every interval incomplete |
| Earlier row with invalid or unverifiable availability (unverified status, garbage timestamp, wrong status) | every interval incomplete |
| Rejected earlier row whose manifest-**verified** availability is usable | only the receiving interval if that availability is inside the window; ignored (counted) if it is outside |
| Final-absent/failed/invalid earlier batch | can never become available: counted, no effect |
| Processed earlier batch available outside the window (including exactly at the first cutoff) | counted, no effect |
| Lookback not declared (`earlier_batches_from = None`) | nothing was examined: every interval incomplete, issue `earlier_batches_not_examined` |
| On-time window | unchanged |

Boundary: a verified availability exactly at the first cutoff is outside (the existing inclusive-cutoff rule); one second later it lands
in the next interval.

## 3. How earlier batches are discovered, and the evidence required

- **New input:** `WindowInputs.earlier_batches_from`, the first nominal batch stamp from which the caller guarantees that `slot_rows`
  holds **every** manifest row up to the window start. The orchestrator builds the lookback grid from there to the slot before the window
  (`timeutil.slot_grid`), requires a manifest row for each stamp (a missing one is a rejection), and adapts them with the existing manifest
  adapter. The stamp is validated (canonical, on the grid, strictly before the first slot) or the call raises.
- **Availability** comes only from the verified field: the adapted `SlotAccounting.available_at_utc` (existing availability rule), or, for a
  rejected row, the manifest's own `availability_status = verified` with a strictly formatted timestamp. The receiving interval is found with
  the existing `interval_locator` / `origin_for`. No page publication time is read (a test and a source scan check this).
- **Accounting** of a late batch reuses the window machinery: its UTC day file is read through the same `day_source`, validated by the same
  day-file adapter against the batch's slot, and reconciled with the same `reconcile_slot` (counts, themes, company items, availability),
  version consistency included.
- **No filesystem scanner, database reader or production integration was invented.** Discovery is limited to the rows the caller supplies.
  This is the missing input: without `earlier_batches_from` the contract cannot discover earlier batches, so the result fails closed
  rather than pretending completeness.
- **No window extension:** no interval, slot view or row is produced for the lookback; `trading_days`, the 192 window slots and the two
  intervals are unchanged (tested). The lookback is reported separately (`earlier_batches_from`, `n_lookback_rows`, `earlier_arrivals`).

## 4. Fail-closed summary

| Missing or bad evidence | Effect |
| --- | --- |
| lookback not declared | every interval `incomplete_accounting` |
| row missing in the declared lookback | every interval incomplete |
| availability not verified / unparseable / non-final | every interval incomplete |
| receiving interval known, batch not reconciled | that interval incomplete |
| everything reconciled | records placed, interval `accounted_with_delayed` |

## 5. Files changed

| File | Change |
| --- | --- |
| `backend/wealthpilot/data/gdelt/sentiment/orchestrator.py` | `earlier_batches_from` input; lookback partition and examination; `EarlierArrival`; shared `processed_state`; receiving-interval placement and incomplete marking; new report fields (`earlier_batches_from`, `earlier_arrivals`, `n_lookback_rows`, `n_earlier_final_unavailable`, `n_earlier_outside_window`, per-interval `n_earlier_arrivals`); digest binds them; `late_batch_strictness` status; docstring |
| `backend/wealthpilot/data/gdelt/sentiment/policy.py` | docstring lists the new status (still blocking) |
| `tests/backend/data/gdelt/test_sentiment_orchestrator.py` | the synthetic world now includes a 24-hour manifest lookback and declares it; 18 new tests |
| `tests/backend/data/gdelt/test_sentiment_policy.py` | the new status is added to the blocking cases |
| `docs/MEMORY.md` | one concise S2.8C entry |
| `reports/phaseB2S2_8B_policy_decision_record.md` | a supersession note appended (text not rewritten) |
| `reports/phaseB2S2_8C_F1_late_arrival_report.md` | this report |

Not changed: both adapters, `slots.py`, `features.py`, `schema.py`, `fake_scorer.py`, the parser, engine, manifest, availability, calendar,
filter and dedup code, any dataset, manifest or day file, D8 criteria, the D12/D12.1 guard, the D13 lock, provider gates, compliance
rules, the build lock and the adapter registry. F2/F2b, the shared vocabulary, coverage plumbing, near-empty detection and repeated-content
linking were not touched.

## 6. Regression coverage (18 new tests, `test_sentiment_orchestrator.py`)

late earlier batch accounted for (both times kept, record placed by verified availability, no silent expansion); the S2.7 reproduction with
unreconciled counts (receiving interval incomplete, record held back, issue text carries nominal time, availability and interval); missing
earlier batch; four unverifiable-availability variants; non-final earlier batch; final-absent earlier batch; rejected row inside versus
outside the window; missing earlier day file (only the receiving interval); an earlier late batch with no records is not evidence of
absence (and the existing window-nominal delayed rule is unchanged); no lookback declared; lookback declaration validated and bounding what
is examined; first-cutoff boundary (exactly at, one second after); no window expansion and unchanged on-time behaviour; availability only
from verified timestamps (a page publication time is ignored); digest binds the lookback and the arrivals. The 56 earlier orchestrator and
policy tests pass unchanged against a world that now declares a lookback.

## 7. Test results (actually run)

| Command | Result |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest tests/backend/data/gdelt/test_sentiment_orchestrator.py tests/backend/data/gdelt/test_sentiment_policy.py -q -p no:cacheprovider -W ignore` | **75 passed** |
| `.venv/Scripts/python.exe -m pytest tests/backend/data/gdelt/test_sentiment_adapters.py tests/backend/data/gdelt/test_sentiment_scaffold.py -q -p no:cacheprovider -W ignore` | **145 passed** |
| all four sentiment test files together | **220 passed** |
| `.venv/Scripts/python.exe -m pytest tests/backend/data/gdelt -q -p no:cacheprovider -W ignore` | **1245 passed, 0 failed** (was 1226) |
| mutation check, 11 F1 guards broken one at a time (file restored byte-for-byte) | **11 of 11 caught** |
| build lock and adapter registry | `AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD = False`, registry `{}` (unchanged) |

Not run: frontend, hosted-database and full-project suites.

## 8. Git and sample integrity

HEAD `71b363f`; nothing staged; 49 tracked modifications (the same files; `docs/MEMORY.md` was already among them); untracked 59 before this
report, 60 with it. No commit, stage, reset or push; no unrelated file touched. The development sample (546 files) has the same
(path, size, modification time) hash before and after, `271939bb1895d1d3`, re-checked with the read-only harness; no manifest or day file
was written.

## 9. Remaining limitations and next bounded step

1. **Lookback length (undecided).** Arrivals from before `earlier_batches_from` are not examined, and lateness has no upper bound in the
   availability rule. The owner should choose a length (the audit's lookback of about 31 days is a candidate), or ask for a different
   mechanism; the length is currently the caller's responsibility.
2. **Discovery depends on the caller's rows.** The orchestrator cannot prove that `slot_rows` is complete for the lookback beyond requiring a
   row for every stamp; a file-backed or database-backed reader that supplies them is not built.
3. **Conservative choice to confirm:** an interval that receives an accounted earlier arrival is `accounted_with_delayed`, so empty themes
   there are unverified rather than verified no-records. Revisit with the shared vocabulary (F2).
4. **Still open:** F2/F2b (the aggregator's different empty-interval rule and NULL near-empty handling), the shared completeness
   vocabulary, coverage and near-empty plumbing, repeated-content labelling, the UNCONFIRMED items in section 1, and everything that blocks
   scoring, features, evaluation and production (model, polarity validation, target, filter validation, acquisition).
5. The aggregator does not use these results; there is still no candidate-to-`ArticleRecord` conversion. Every required policy still blocks
   feature generation.

**Next bounded step:** answer the UNCONFIRMED items (especially 1, 3, 8 and 11) and choose the lookback length; then one phase for the shared
completeness vocabulary that settles F2/F2b. Stopped here; S2.9 and S4 were not started.
