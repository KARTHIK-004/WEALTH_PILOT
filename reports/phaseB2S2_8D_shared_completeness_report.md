# Research Enhancement Track — Phase B2-S2.8D: Shared Completeness Vocabulary and F2/F2b Corrections

**Status: COMPLETE.** One typed completeness contract is now shared by the orchestrator and the aggregator, and F2 and F2b are corrected.
Offline and synthetic. No scorer, candidate-to-`ArticleRecord` conversion, trusted feature, evaluation or production use was built or
authorised. Date: 2026-10-20 (UTC). Written for: the project owner.

## 1. Policy-status table (resolved before coding)

A recommendation in an earlier assistant response is not owner approval. "Evidence" is the owner's own instruction text (S2.8B, S2.8C,
S2.8D); the original owner-decision message is not visible to me.

| Class | Item | Evidence | Status |
| --- | --- | --- | --- |
| Explicitly selected | F1 policy **C-min**: detect earlier-nominal batches whose verified availability falls inside the window; account for them or mark the receiving interval incomplete; do not extend the window | S2.8C, S2.8D | selected, applied (S2.8C), **unchanged** |
| Explicitly selected | Delayed batches are assigned by verified availability time | S2.8B/C | selected, applied |
| Explicitly selected | Unknown (NULL) near-empty is neither complete evidence nor verified no-news | S2.8B | selected; applied in the shared contract as "not full evidence" (`UNDECIDED_POLICY`); whether it should instead make the interval unusable is **not** decided |
| Explicitly selected | A delayed empty batch is not verified no-news; a missing batch is not a valid empty batch; an explicitly near-empty slot stays distinguishable from a missing one; insufficient or unresolved evidence is never usable | S2.8D | selected, applied (answers question 8) |
| Explicitly selected | One shared typed contract for the orchestrator and the aggregator, with the four distinct concepts | S2.8D | selected, applied; the **exact state names are my design** and need owner confirmation (question 11) |
| Explicitly selected | Coverage denominator is the full nominal-slot grid; repeated content is retained, similarity is not identity; unresolved required policies block downstream use; company counts reconcile; versions consistent within a window; the digest binds content | S2.8B | selected, applied |
| Selected but **provisional** | primary source-coverage threshold 0.75, sensitivity 0.50 and 0.90; near-empty detector parameters (10% of the median, 14 days, at least 7 observations); primary near-empty handling (explicit near-empty is uncovered; sensitivity may treat it as covered with the flag kept); every eligible record as the first counting unit with a repetition sensitivity | S2.8B | provisional; **not** applied as approved rules here |
| **Unconfirmed** (not found in the evidence available) | scoring-coverage threshold; the linking rules for repeated content; the absolute limit on consecutive missing slots; holiday and early-close calendars; theme-specific cutoffs; whether unknown near-empty should make an interval unusable rather than undecided | none | open, for the owner |
| **Undecided, stated explicitly** | the **lookback length**. Neither 7 nor 31 days was adopted. The caller-supplied `earlier_batches_from` contract is unchanged. A future lookback decision must be explicit, and a caller-supplied lookback cannot prove completeness beyond its declared range | S2.8C report, S2.8D | open |
| **Blocked** | sentiment model, licence and dependencies; polarity validation; forecast target and protocol; independent validation of the GDELT filter; full-window acquisition; scoring, trusted features, model evaluation and production integration | all | blocked |

The downstream policy guard was not weakened. A new required policy, `scorer_approval_and_polarity_validation`, was added so that a
scoring result stays unusable until an approved scorer and its validation exist; it is `UNRESOLVED_NOT_APPLIED`. Eight required policies
now block, and `late_batch_strictness` is still `SELECTED_APPLIED_LOOKBACK_UNDECIDED` (blocking).

## 2. The shared state model (`sentiment/completeness.py`)

Four distinct concepts, each an explicit enumeration. No state name is shared between them and none is a boolean.

| Concept | States |
| --- | --- |
| **Source completeness** (are the expected source slots accounted for?) | `complete`, `complete_with_delayed`, `final_gaps`, `incomplete` |
| **Interval usability** (evidence and policy conditions) | `usable` (full evidence), `usable_under_coverage_rule` (short of full evidence, accepted by a rule the caller says is applied), `undecided_policy`, `unusable_below_coverage_rule`, `unusable_incomplete` |
| **Per-theme record evidence** | `has_records`, `verified_zero_records`, `unverified_empty` (with reasons), `not_evaluated` |
| **Result availability** | `available`, `available_test_only`, `unavailable`, `blocked_by_policy`, `scoring_not_performed` |

Per-slot evidence keeps apart: `accounted`, `accounted_delayed`, `final_absent`, `missing`, `rejected`, `non_final`, and, separately for an
accounted slot, a near-empty status of `not_near_empty`, `near_empty` or `unknown` (a NULL indicator). Earlier-nominal batches (C-min)
enter as `IntervalEarlier` (unresolved batches, "not examined", reconciled arrivals) and as `EarlierEvidence` for a whole window.

**Transitions (`assess_interval`).** Any `missing`, `rejected` or `non_final` slot, an unresolved earlier batch, or a window whose lookback
was not examined gives `incomplete` and `unusable_incomplete`. Otherwise a `final_absent` slot gives `final_gaps`; otherwise a delayed
slot or a reconciled earlier arrival gives `complete_with_delayed`; otherwise `complete`. `usable` requires `complete` with every
indicator known to be false. Anything else short of full evidence is `undecided_policy`, unless a coverage rule the caller has applied
says it is met or not.

**Invariants (tested exhaustively over 3,000+ combinations, and by mutation):**

- **I1** `verified_zero_records` only for a `complete`, `usable` interval with no near-empty or unknown slot and nothing earlier unresolved.
- **I2** `usable` only for a `complete` source with every indicator known false.
- **I3** an `incomplete` source is always `unusable_incomplete`.
- **I4** a result is `available` / `available_test_only` only when no policy blocks, scoring was performed, the interval is usable and the
  theme has records; `blocked_by_policy` takes precedence over every other reason.
- **I5** missing or incomplete evidence carries no value: no mean, no zero, no neutral figure, and no state or field of the contract holds one.

## 3. How F2 and F2b were corrected

Same synthetic window with no records (S2.7 probes P6 and P6b, re-expressed as tests).

| Fixture | Before (orchestrator / aggregator) | After (both layers) |
| --- | --- | --- |
| one delayed empty batch | `unverified_empty_delayed` / **`no_news = True`** | `complete_with_delayed`; every theme `unverified_empty`; `no_news` is `None` |
| one final-absent batch (95/96, coverage above 0.75) | `unverified_empty_partial` / **`no_news = True`** | `final_gaps`; `unverified_empty` (reason `final_gaps`); `no_news` is `None` |
| 20 explicitly near-empty slots (coverage ok) | `accounted_complete`, verified no records / **`no_news = True`** | `complete`, `undecided_policy`; `unverified_empty` (reason `near_empty_slots`); `no_news` is `None` |
| every indicator NULL (F2b) | `accounted_complete`, **verified no records** / `insufficient_coverage` (0.0) | `complete`, `undecided_policy`; `unverified_empty` (reason `near_empty_unknown`); the aggregator reports 96 unknown, 0 near-empty, and keeps counting unknown as uncovered |
| missing manifest slot | `incomplete_accounting` / `slot_grid_mismatch` | both `incomplete`, `unusable_incomplete` |
| non-final slot | `incomplete_accounting` / `incomplete_source_accounting` | both `incomplete` |
| unresolved earlier batch (C-min) | orchestrator only | both `incomplete`; the aggregator now requires the earlier evidence |
| indicators all known false | verified no records / `no_news = True` | unchanged: `usable`, `verified_zero_records`, `no_news = True` |

What changed in code: the orchestrator's status and its theme labels are now derived from the shared transitions (the old strings remain
as labels, plus `unverified_empty_indicator`); the aggregator builds the same per-slot evidence, calls the same functions, takes a required
`earlier: EarlierEvidence` (`WindowReport.earlier_evidence()` produces it), treats an unreconciled batch landing in another interval as
unresolved inflow, and sets `no_news` from `verified_zero_records` only. The aggregator's provisional coverage threshold still decides
whether features are computed (`coverage_status`), but it can no longer justify verified zero; the threshold was not finalised or changed.
The agreement relation tested on every equivalent fixture: equal source completeness, equal "fully usable", `no_news` true exactly when
the orchestrator says verified zero, never a contradiction in theme evidence, and no value ever invented.

## 4. Files changed

| File | Change |
| --- | --- |
| `backend/wealthpilot/data/gdelt/sentiment/completeness.py` | **Created.** The shared contract, transitions, invariants |
| `backend/wealthpilot/data/gdelt/sentiment/orchestrator.py` | uses the shared transitions; `ThemeEvidenceRecord`, `IntervalAccounting.assessment/theme_evidence`, `WindowReport.earlier_evidence()`; digest binds the new states; new required-policy status |
| `backend/wealthpilot/data/gdelt/sentiment/features.py` | shared per-slot evidence and transitions; required `earlier`; seven new `DailyFeatures` fields; `s2_daily_v4`; `no_news` only for verified zero; inflow of unreconciled late batches |
| `backend/wealthpilot/data/gdelt/sentiment/policy.py` | `scorer_approval_and_polarity_validation` added to the required policies |
| `tests/backend/data/gdelt/test_sentiment_completeness.py` | **Created** (22 tests) |
| `tests/backend/data/gdelt/test_sentiment_orchestrator.py` | the world now supplies known-false near-empty flags by default; 18 new agreement and F2/F2b tests |
| `tests/backend/data/gdelt/test_sentiment_scaffold.py` | calls pass explicit earlier evidence; two assertions updated to the corrected F2 behaviour; 5 new tests |
| `tests/backend/data/gdelt/test_sentiment_policy.py` | explicit earlier evidence; eight required policies |
| `docs/MEMORY.md`, `reports/phaseB2S2_8D_shared_completeness_report.md` | one concise entry; this report |

Intentional interface changes: `aggregate_daily` needs `earlier=`; `DailyFeatures` has seven new fields; `IntervalAccounting` has two new
fields. Not changed: both adapters, `slots.py`, `schema.py`, `fake_scorer.py`, the parser, engine, manifest, availability, calendar, filter and
dedup code, any dataset, manifest or day file, D8 criteria, the D12/D12.1 guard, the D13 lock, provider gates, compliance rules, the build
lock and the adapter registry (still `False` and `{}`).

One of my own slips was caught by the tests: an invalid-text-only theme was first reported as an available (test-only) result with no
value; that is fixed (`scoring_not_performed`) and pinned. A shell re-save also briefly mangled a zero-width character in a test and added a
byte-order mark; both were repaired and the suite re-run.

## 5. Test results (actually run)

| Command | Result |
| --- | --- |
| `pytest tests/backend/data/gdelt/test_sentiment_completeness.py tests/backend/data/gdelt/test_sentiment_orchestrator.py tests/backend/data/gdelt/test_sentiment_policy.py -q -p no:cacheprovider -W ignore` | **115 passed** |
| `pytest tests/backend/data/gdelt/test_sentiment_adapters.py tests/backend/data/gdelt/test_sentiment_scaffold.py ...` | **150 passed** |
| all five sentiment test files | **265 passed** |
| `pytest tests/backend/data/gdelt -q -p no:cacheprovider -W ignore` | **1290 passed, 0 failed** (was 1245) |
| mutation check, 15 guards (shared transitions, aggregator, orchestrator, result states), files restored byte-for-byte | **15 of 15 caught** |

Not run: frontend, hosted-database and full-project suites.

## 6. Git state and sample integrity

HEAD `71b363f`; nothing staged; 49 tracked modifications (the same files; `docs/MEMORY.md` was already among them); untracked 60 before this
report, 61 with it. No commit, stage, reset or push. The development sample's 546 files have the same (path, size, mtime) hash before and
after (`271939bb1895d1d3`), re-checked with the read-only harness, which also still accepts 192/192 slots and 170/170 day files; no
manifest or day file was written.

## 7. Remaining blockers and next bounded step

1. **Unknown near-empty:** implemented as "not full evidence" (`undecided_policy`). The owner should decide whether it should instead
   make an interval unusable, and how a baseline is guaranteed.
2. **Coverage and near-empty plumbing** (rules, sensitivity runs, primary/sensitivity switch) remain unbuilt; the aggregator's provisional
   threshold is still only a gate for computing features.
3. **Lookback length** is undecided and caller-supplied; nothing proves completeness beyond the declared range.
4. **Earlier arrivals in the aggregator:** the aggregator accepts earlier-batch evidence but not their records (they have no slot in the
   grid); there is still no candidate-to-`ArticleRecord` conversion, scorer or story policy.
5. **Vocabulary names** (question 11) need owner confirmation; scoring-coverage threshold, linking rules, missing-slot limit, calendars and
   theme cutoffs remain unconfirmed.
6. Everything in the blocked row of section 1 stays blocked; every required policy still blocks features.

**Next bounded step:** confirm or rename the vocabulary, decide the lookback length and the unknown-indicator mechanism, then one phase for
coverage and near-empty plumbing that applies the recorded primary and sensitivity settings through this contract. Stopped here; S2.9 and
S4 were not started.
