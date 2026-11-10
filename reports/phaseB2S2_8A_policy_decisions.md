# Research Enhancement Track — Phase B2-S2.8A: Research Policy Decision Preparation

**Status: DECISION PREPARATION ONLY. Nothing here is approved, implemented or chosen.** Every "recommendation" is a recommendation
for the project owner to accept, change or reject. The only project file created in this phase is this report. Date: 2026-10-20 (UTC).
Written for: the project owner, who answers the numbered questions in the last section.

**Labels.** **[CODE]** read in the repository (path:line). **[OBSERVED]** a reproducible result of a synthetic probe or an existing test run
in S2.7 or this phase, against unchanged code. **[AUDIT-DATA]** a number from the pre-acquisition audit reports (slot presence from the
master list and header checks; not processed data). **[SAMPLE]** a number from the 192-batch local B2-M sample, which is isolated
batches and therefore a sample-specific figure, never a population estimate. **[ASSUMPTION]** reasoning that rests on a stated assumption.
**[RECOMMENDATION]** advice, not a decision.

---

## 1. Verified baseline

| Item | Result |
| --- | --- |
| Git | HEAD `71b363f`; staged 0; tracked modifications 49 (unchanged); untracked 56 before this report, 57 with it |
| Reports read | S2.7, S2.6, S2.5, S2.4, S3 (all present). The S1, S2.1 and S2.2 reports do not exist as files and were not reconstructed |
| Code unchanged since S2.7 | the S2.7 probes `s27_probe.py` and `s27_probe2.py` (scratchpad) were re-run in this phase and gave the same results |
| Tests run | `pytest tests/backend/data/gdelt/test_sentiment_orchestrator.py tests/backend/data/gdelt/test_sentiment_adapters.py tests/backend/data/gdelt/test_sentiment_scaffold.py -q -p no:cacheprovider -W ignore`: **162 passed**. The full suite was not re-run (no code changed since its S2.7 result of 1,187 passed) |
| Source references | near-empty: `engine.py:35,163-168,188`, `manifest.py:262-264,331-340`, `coverage.py:31-50`; aggregator: `features.py:254-287` (`_assess_day`), `:379-436` (`_theme_row`); orchestrator: `orchestrator.py:240-` (`orchestrate_window`), `:264-273` (window partition), `:310-311`, `:352`, `:391-408`, `:65-75` (`POLICY_STATUS`), `:193`, `:198` (`digest`); adapters: `manifest_adapter.py`, `dayfile_adapter.py`; audit data: B2-H `:492-503` (§5.5), `:507-556` (§6) |

---

## 2. Policy 1 — Near-empty slots and unknown indicators

### Existing behaviour [CODE]

- The indicator is set once, at day commit, by `engine._near_empty` (`engine.py:163-168`): it compares the slot's `rows_english_valid`
  (all English rows of the batch, **not** a theme) with 10% of the median of the same slot of the previous days (`NEAR_EMPTY_RATIO = 0.10`,
  `MIN_BASELINE_OBS = 7`, window 14 days, `manifest.py:331-340`). It stores `near_empty_flag` as **1** (near-empty), **0** (not), or **NULL**
  (fewer than 7 baseline observations). All three constants are labelled PROPOSED (`engine.py:34`).
- Three different things are therefore stored in one column: **explicitly near-empty (1)**, **explicitly not near-empty (0)** and **unknown (NULL)**.
  `SlotAccounting.near_empty` keeps the same three values (`slots.py`), and the manifest adapter passes NULL through unchanged.
- Aggregator: `coverage.interval_count` counts a processed slot as covered only when `near_empty is False`; both `True` **and `None`** are
  uncovered (`coverage.py:39-45`, `unknown_near_empty_is_covered=False`). A quiet day and an unknown indicator therefore lower coverage identically.
- Orchestrator: near-empty is **ignored** for status and for `no_news_basis`; only a count of near-empty slots is exposed.

### Impact of NULL indicators [OBSERVED / ASSUMPTION]

- **Existing sample [SAMPLE]:** `near_empty_flag` is NULL for 192 of 192 batches (isolated batches have no same-slot neighbours). Anything
  built from the sample has no usable near-empty information.
- **A contiguous window:** the first 7 days of the *processed* run are NULL for every slot-of-day, because each needs 7 earlier same-slot
  observations. A lookback of at least 14 days (the audit planned 2,964 slots, about 31 days) removes this for the scored days **only if
  the lookback is processed and committed first, in date order**, because the flag is written once at commit and a committed slot is never
  reset (`manifest.py:288-304`). **[ASSUMPTION: every earlier day present.]**
- **After a long outage:** each slot-of-day needs 7 present earlier days among the previous 14. After the 416-hour outage of
  2025-06-14 to 07-02 **[AUDIT-DATA]**, the first recovered day has 0 observations and the flag stays NULL for about **7 days** (days
  r to r+6), then recovers. The 32-hour gap of 2023-03-22/23 leaves at least 12 observations, so it does not create NULLs.
- **Effect on the aggregator [OBSERVED, F2b]:** with every flag NULL and every slot processed, the aggregator reports
  `insufficient_coverage` and `no_news = None` for the whole interval (coverage 0.0); with every flag 0 it reports `ok`, `no_news = True`.
- **Scale of true near-empty [AUDIT-DATA]:** under the audit's own (different, centred, size-based) rule only 86 of 162,512 slots (0.05%) were
  near-empty, in 4 runs. The causal 10%-of-median rule used by the engine has **not** been measured on any contiguous data.

### Options and consequences

| Option | Meaning | Consequence |
| --- | --- | --- |
| A. Unknown = not usable (current aggregator) | NULL counts as uncovered | safe; but a window start or post-outage period is unusable, and the sample is unusable |
| B. Unknown = covered | NULL counts as covered | makes unknown look complete; contradicts "unknown is not complete" and the project's missing-data rule |
| C. Unknown excluded from the denominator | coverage over slots with a known flag | coverage can rest on few slots; needs a minimum of known slots |
| D. Require a baseline | fail the interval, or the window, if any indicator in it is NULL | forces the lookback; no silent policy |
| E. Explicit near-empty (flag 1): uncovered (current) / covered (quiet but processed) / excluded | separate decision from unknown | "uncovered" removes quiet days non-randomly (informative missingness); "covered" keeps them but may admit failed-but-nonempty files |

**[RECOMMENDATION]** Treat unknown as **neither complete nor empty**: option D for scored intervals (a NULL indicator makes the interval
`UNDECIDED`, with the reason "no causal baseline"), keep the three values distinct everywhere, and decide explicit near-empty (E)
separately, reporting the primary result under one choice and a sensitivity run under the other.

### Required tests (later, synthetic)
NULL, 0 and 1 produce three distinct outcomes in both layers; a NULL never equals 0 or 1; the orchestrator exposes the count of unknown
indicators and does not call an interval usable when any is unknown; the baseline-order dependence (a day committed before its
predecessors) is detected or documented.

**Approval:** project owner (Q1-Q3).

---

## 3. Policy 2 — Coverage

### The exact quantities supported by the current code [CODE]

| Quantity | Numerator | Denominator | Where |
| --- | --- | --- | --- |
| **Source-slot coverage** (aggregator) | slots that are `processed`, **available at or before the interval's cutoff**, have `rows_captured` not null, and `near_empty is False` | the number of expected **nominal** 15-minute slots of the interval (96 on an ordinary day; validated against the grid) | `features._assess_day` (`:266-270`), `coverage.interval_count` (`:46-50`) |
| **Record availability** | not a ratio: each record's verified availability must equal its slot's, and decides the interval it enters | n/a | `slots.reconcile_slot`, `features.interval_locator` |
| **Sentiment-scoring coverage** | `n_scored` | `n_eligible` (eligible records after text and duplicate rules), per theme and interval | `features._theme_row` (`scoring_coverage`) |
| Orchestrator | **no ratio at all**: counts of slots per state, counts of records | n/a | `orchestrator.IntervalAccounting` |

Effect of each situation on the source-slot calculation:

| Situation | Numerator | Denominator | Status |
| --- | --- | --- | --- |
| missing manifest slot, extra, duplicate, wrong grid | not computed | 96 expected | `slot_grid_mismatch` |
| non-final batch (in progress, unverified, parsed-not-committed) | not computed | 96 | `incomplete_source_accounting` (aggregator); `incomplete_accounting` (orchestrator) |
| final absent/failed/invalid batch | not counted | 96 | counts toward threshold; orchestrator: `partial_source_accounting` |
| processed, available after the cutoff (delayed) | not counted | 96 | counts toward threshold; orchestrator: `accounted_with_delayed` |
| processed, `near_empty` true | not counted | 96 | counts toward threshold; orchestrator ignores |
| processed, `near_empty` null | not counted | 96 | counts toward threshold; orchestrator ignores |
| processed, zero captured rows, `near_empty` false | counted | 96 | real quiet slot |

Coverage is **interval-level**, not theme-level. The three series have very different density (about 14, 15 and 1 member rows per batch
in the sample **[SAMPLE]**), so a covered slot says nothing about whether gold content exists.

### The proposed 0.75 threshold (not approved)

- **Absolute tolerance depends on interval length [CODE arithmetic]:** minimum covered slots at 0.75 are 72 of 96 (24 may be missing), 63 of 84
  (an early-close day), 135 of 180, 213 of 284 and 216 of 288 (72 may be missing, 18 hours of a weekend interval).
- **Sensitivity on real data [AUDIT-DATA, B2-H §6.2]:** over 1,171 forecast origins, 15 days fall below 75% (3 in training, 12 in test) and
  **the same 15 fall below 90%**; 14 fall below 50%. So on slot presence alone, thresholds from 0.75 to 0.90 give an identical set of null
  days, and 0.50 differs by one day (2025-07-02, 74.0%). Almost all of the affected days are the 2025 outage.
- **What that evidence does not cover:** delayed arrivals, the causal near-empty rule, per-theme density and processed (not merely listed) slots.
  Near-empty and delays could move many more days across a threshold than the 15 outage days.
- **Trade-off:** a threshold removes whole days to protect against partial information; a low one admits intervals whose "no news" is weakly
  supported. A fractional threshold treats a 288-slot weekend interval and a 96-slot day alike.

**[RECOMMENDATION]** Keep the three quantities as separate, always-reported numbers; make coverage a reported ratio with its numerator and
denominator rather than a hidden gate; choose the primary threshold only after the near-empty decision, and run 0.50, 0.75 and 0.90 as
pre-registered sensitivity runs. Consider also an absolute cap on consecutive missing slots. Decide the scoring-coverage rule separately
and keep it report-only until then.

### Required tests
Boundary cases at exactly the threshold (71/96 versus 72/96 exists); each situation in the table; weekend, early-close and DST
denominators; delayed counted uncovered but later accounted; scoring coverage never merged with source coverage.

**Approval:** project owner (Q4-Q6).

---

## 4. Policy 3 — Late batches and point-in-time assignment

### The F1 failure [CODE / OBSERVED]

`orchestrate_window` partitions the manifest rows into those whose batch is in the window's nominal grid and the rest
(`orchestrator.py:264-273`); the rest are only **counted** (`n_manifest_rows_outside_window`). A batch whose nominal slot precedes the first
interval can still have a **verified availability inside the window** (it arrived late). Its manifest row is ignored and its day file is not
read, so its records never appear.

Concrete example [OBSERVED, probe P1]: a processed batch with nominal time 2022-03-01 10:00Z (before the first interval's cutoff of 21:00Z),
one equity record, verified availability 2022-03-02 05:00Z (inside the interval for 2022-03-02). Result: the 2022-03-02 interval is
`accounted_complete`, its equity basis is `verified_complete_no_records`, records 0, `n_manifest_rows_outside_window` 1, **no issue**. At the
cutoff that record already existed, so the "verified no records" claim is false. The aggregator would catch it only if the record were supplied
as an article (its source slot would be missing), but the orchestrator removes it first.

How likely: 0 of 192 sample batches were late **[SAMPLE]**; the historical files show no sign of rewriting in the audit checks (B2-F); a late
file is expected mainly around outages **[ASSUMPTION]**. There is no upper bound on lateness in the availability rule (a rewrite is merely
flagged after 24 hours, `availability.py`).

### Options

| Option | What it does | Consequences |
| --- | --- | --- |
| A. Exclude earlier nominal slots (current) | late pre-window batches are ignored | silent false "no records" near the window start; only a documented caveat |
| B. Expand the source window | caller adds L earlier trading days to the accounting range; rows are emitted only for the requested range | needs a rule for L (lateness has no bound); the requested range is not changed, but more data is read and the first L days' own intervals need a lookback of their own |
| C. Account for prior-slot batches that arrive in the requested interval | scan **all** manifest rows with verified availability inside the window, whatever their nominal slot; reconcile them (read their day files) or mark the receiving interval incomplete | exact, no guess of L; needs the earlier day files; fails closed when they are absent |
| C-minimum (fail closed only) | detect such rows and mark the receiving interval `incomplete` with their batch ids, without reading earlier files | smallest change; loses intervals only where a late batch actually exists |

**[RECOMMENDATION]** C-minimum first (detect and fail closed), with C or B as a later refinement once the real late frequency is measured
on a contiguous window. Never change the requested date range silently; report the accounting range separately.

**Provenance required for any option:** nominal `batch_ts`; verified `available_at_utc` and the availability flags (`late`,
`written_after_nominal`, `rewrite_suspect`) of the source slot; the slot state and counts; the day file name and hash for the batch's own UTC
day; the interval of the nominal slot and the interval that receives it; whether its records reconciled.

**Delayed batches inside the window** are already accounted (nominal interval counts them as delayed, the later interval receives the
records). The remaining question is only whether a **delayed batch with zero rows** is evidence of absence: the orchestrator says no
(strict), the aggregator says yes unless the batch carries rows of that theme (Q8).

### Required tests
The P1 case (must become incomplete or accounted); a pre-window batch available before the first cutoff (no effect); at the first cutoff
exactly; after the last cutoff; a pre-window batch with unreconciled counts; the report distinguishes requested from accounting range.

**Approval:** project owner (Q7-Q8).

---

## 5. Policy 4 — Repeated content and deduplication

### Distinctions [CODE]

| Case | What the data can establish | Existing label |
| --- | --- | --- |
| Identical record id (`<batch>-<seq>` twice) | an integrity error: one row cannot have two identities | rejected, whole batch `duplicate_record_id` |
| Repeated URL in one batch | strong: the same page twice | `DUP_SAME_BATCH` (written by the engine) |
| Same normalised title, different URL, same batch | weak: syndication, or a generic title | `SYNDICATED_SAME_BATCH` (written by the engine) |
| Repeated URL in a later batch, same title hash and word count | re-observation of the same page | `REOBSERVATION` (**never produced**: `dedup.StoryTracker` is not called) |
| Repeated URL in a later batch, changed content | an update of the same page | `UPDATE` (never produced) |
| New URL, same title hash within 72 hours | syndicated copy | `SYNDICATED` (never produced) |
| Same title text by chance | a **separate** story (recurring headlines such as market summaries) | not distinguishable by hash; the 20-character minimum is the only guard |

Observations **[SAMPLE, not a population estimate]**: 18.0% of English rows are same-batch duplicates; in the 26,854 kept rows 4,816 carry a
same-batch status (4,555 syndicated, 261 same URL); 22,038 are `ORIGINAL`. Among those `ORIGINAL` rows, **261 (1.2%) repeat an earlier batch's
URL (68) or title hash (215)**. Because the 192 batches are isolated (131 pairs within 72 hours), this is a **lower bound for this sample
only**; a contiguous window would show more, and the rate for the full window is unknown.

### Options

| Option | Description | Consequences |
| --- | --- | --- |
| P-A. Preserve all records, no links (current) | every record counts | cross-batch repeats count as separate stories (1.2% in the sample, lower bound); same-batch handling relies on the proposed aggregator rule |
| P-B. Link verified duplicates, drop nothing | a producer adds `relation` (type, evidence strength) and `first_record_id` as fields; consumers choose | no information lost; needs the causal story pass (availability order, 72-hour warm-up, unbounded URL state) and a policy at aggregation |
| P-C. Link updates as separate versions | an updated page is a new version at its own availability, linked to the first | matches the B2-H wording for updates only in the sensitivity variants; the S2 proposal keeps them in the primary count |
| P-D. Drop duplicates | remove linked records | irreversible without the source; strong policy; not recommended before measuring |

**[RECOMMENDATION]** P-B in the form of *labelling only*: relation type and evidence strength recorded as separate fields (URL-equal strong;
title-hash-equal weak), nothing dropped, no `story_id` asserted, and the counting unit (record, first-occurrence story, or story with
versions) decided at aggregation. Do not use a record id, URL or hash as a placeholder `story_id`.

### Required tests
Same id twice; same URL in and across batches; same title hash with different URLs; update chain; coincidental identical titles; warm-up
at the window start; order independence of the labelling; no record is ever removed by the producer.

**Approval:** project owner (Q9-Q10).

---

## 6. Policy 5 — Cross-layer completeness semantics

### Why the layers disagree [OBSERVED]

Three layers answer different questions with different vocabularies:

| Layer | Question it answers | Vocabulary today |
| --- | --- | --- |
| Orchestrator | "What do we know about the sources of this interval?" (facts, no thresholds) | `accounted_complete`, `accounted_with_delayed`, `partial_source_accounting`, `incomplete_accounting`; bases `verified_complete_no_records`, `unverified_empty_*` |
| Aggregator | "Can a feature be computed under the supplied rules?" (applies threshold and near-empty) | `ok`, `insufficient_coverage`, `missing_source_batches`, `incomplete_source_accounting`, `slot_grid_mismatch`, `slot_article_mismatch`, `no_expected_slots`; `no_news` True/False/None |
| Policy | "Is the result admissible?" | informational `policy_status` only |

Concrete examples (same synthetic window, no records; probes `s27_probe.py`, `s27_probe2.py`, re-run in this phase):

| Case | Orchestrator | Aggregator |
| --- | --- | --- |
| **F2** one delayed empty batch (flags 0) | `accounted_with_delayed`, `unverified_empty_delayed` | `ok`, `no_news = True` |
| **F2** one absent batch, 95/96 covered (flags 0) | `partial_source_accounting`, `unverified_empty_partial` | `ok`, `no_news = True` (0.99 is above 0.75) |
| **F2** quarter of the day near-empty (flags 1 on 30 slots) | `accounted_complete`, `verified_complete_no_records` | `insufficient_coverage` (0.688 below 0.75), `no_news = None` |
| **F2b** every slot processed, **flag NULL** | `accounted_complete`, `verified_complete_no_records` | `insufficient_coverage` (coverage 0.0), `no_news = None` |
| non-final batch | `incomplete_accounting` | `incomplete_source_accounting` |
| missing manifest slot | `incomplete_accounting` | `slot_grid_mismatch` |

Reading: the first two are not bugs in either layer: the aggregator applies a supplied threshold, the orchestrator withholds a verdict. They
become defects only because both use the words "no news" / "verified" for different standards, and because nothing prevents a consumer from
using the aggregator's `no_news = True`. F2b is a plain contradiction: the same unknown indicator is "complete" in one layer and "0% covered" in the other.

### Proposed common vocabulary [RECOMMENDATION, not implemented]

**Level 1 — Source completeness (facts; the orchestrator owns it; no thresholds)**

| Term | Meaning |
| --- | --- |
| `COMPLETE` | every nominal slot reconciled and available by the cutoff |
| `COMPLETE_WITH_DELAYED` | all accounted; some batches became available only after the cutoff |
| `FINAL_GAPS` | all processed batches reconcile; some batches are final but absent/failed |
| `INCOMPLETE` | any non-final, missing, rejected, unreconciled or unresolved-inflow batch (reasons listed) |
| `INDICATOR_UNKNOWN` (flag, orthogonal) | some processed slot has a NULL near-empty indicator |

**Level 2 — Interval usability (policy applied; the aggregator or a policy layer owns it)**

| Term | Meaning |
| --- | --- |
| `USABLE` | completeness and coverage meet the approved rules |
| `USABLE_WITH_FLAGS` | usable, with delayed rows, near-empty slots or partial scoring exposed |
| `UNUSABLE_BELOW_POLICY` | below the approved coverage rule |
| `UNUSABLE_INCOMPLETE` | Level 1 is `INCOMPLETE` |
| `UNDECIDED_POLICY` | a required policy value is not approved or an indicator is unknown |

**Level 3 — Record evidence (per theme)**

| Term | Meaning |
| --- | --- |
| `HAS_RECORDS` | records exist |
| `VERIFIED_NO_RECORDS` | Level 1 `COMPLETE` and no record |
| `UNVERIFIED_EMPTY(reason)` | no record, but completeness is not `COMPLETE` (reason: incomplete, final gaps, delayed, indicator unknown) |
| `DELAYED_EVIDENCE` | records exist in batches that became available only after the cutoff |

**Level 4 — Result availability.** `AVAILABLE`, or `UNAVAILABLE(reason)`: the reason is always one of the Level 1-3 terms. "No news" in a
feature may be asserted only for `USABLE` + `VERIFIED_NO_RECORDS`. A neutral or zero value is never a stand-in for any other term.

Mapping of today's names: orchestrator `accounted_complete` to `COMPLETE`; `accounted_with_delayed` to `COMPLETE_WITH_DELAYED`;
`partial_source_accounting` to `FINAL_GAPS`; `incomplete_accounting` to `INCOMPLETE`; aggregator `ok` to `USABLE` only when its inputs
were `COMPLETE` or an approved rule admits the gaps.

**Approval:** project owner (Q11). Not implemented.

---

## 7. Policy 6 — Secondary defects (invariants and tests; nothing implemented)

| ID | Observation [OBSERVED in S2.7] | Proposed invariant | Proposed test | Owner decision? |
| --- | --- | --- | --- | --- |
| F3 | `rows_company_item` (a same-stage count; equal to the flagged kept rows in 192 of 192 sample batches) is kept in `SlotSource` but never reconciled; a mismatched slot stays `reconciled` | for a processed batch, `count(records with company_item) == rows_company_item`; the count becomes part of reconciliation | slot says 1 company item, 0 flagged records: state `count_mismatch` | **Yes, small:** it adds a field to `SlotAccounting` (a contract type) (Q12) |
| F4 | the orchestrator pins the filter version but not the parser version; a window with `gkg_parser_v2` on one day is reported complete while `aggregate_daily` raises | all processed slots of a window share one (filter, parser) pair equal to the commits' | two days with different parser versions: a window-level issue, intervals not complete | **Yes:** may a window span a parser upgrade? Recommendation: no (Q13) |
| F5 | a record with an invalid `batch_ts` is also counted as out of window | the out-of-window counter counts only records with a valid batch outside the grid; invalid records go to a separate counter | invalid stamp: issue present, out-of-window 0, invalid-record count 1 | No |
| F6 | `policy_status` is a mutable dict; nothing reads it | the status is immutable and any conversion or feature step must refuse while a required item is unresolved unless an approved policy record is supplied | assignment raises; a conversion call with an unresolved item raises | **Yes:** should unresolved policy block (raise) or only warn? Recommendation: block (Q14) |
| F7 | `WindowReport.digest()` identifies states and ids, not record content, inputs or policy | the digest covers record content hashes (raw and filter title hash, flags, availability, source file/line), the policy status, and fingerprints of the manifest rows and day commits | change a title: the digest changes; reorder inputs: it does not | Which fields count (Q15); no policy |

---

## 8. Unresolved choices not analysed in this document

Holiday and early-close calendars (the proposed early-close list ends in 2025); theme-specific calendars and cutoffs; the story-update
primary counting unit beyond section 5; the sentiment model, licence and dependency route; polarity validation; the forecast target;
full-window acquisition; whether the sentiment work may proceed while the filter evaluation still lacks independent labels. They remain as
recorded in the S2.7 register (rows 6, 7, 9-13). None is decided here.

## 9. Proposed order of the later corrective implementation [RECOMMENDATION]

1. **Decision-free hardening** (no owner choice needed): F5, F6 immutability (without the blocking rule), F7, plus the failing tests from the
   S2.7 reproductions.
2. **Small contract changes after Q12-Q13:** F3 and F4.
3. **Vocabulary and layering** after Q4-Q8 and Q11: one completeness vocabulary; the aggregator consumes the orchestrator's level-1 facts
   instead of re-deriving them; the F2 examples become tests; the unknown indicator is handled as decided in Q1-Q3 (F2b).
4. **Late-batch handling** (F1) after Q7: C-minimum first.
5. **Near-empty and coverage plumbing:** report numerators, denominators and unknown counts; apply the approved rules; run the sensitivity set.
6. **Repeated-content labelling** as a separate producer phase after Q9-Q10, labelling only.
7. Only then: pre-score record state, scorer, features. Not before.

Each step is independently testable with synthetic fixtures and none needs a model, network or acquisition.

---

## 10. Owner decisions required

Please answer by number. Every "recommendation" below is advice; selecting nothing leaves the behaviour unchanged.

**Near-empty and unknown**
1. A NULL (unknown) near-empty indicator: (a) interval unusable, (b) counts as covered, (c) excluded from the denominator, (d) fail the window unless a baseline exists. *Recommendation: (d) with (a) inside an interval.*
2. An explicit near-empty slot (flag 1): (a) uncovered, (b) covered, (c) excluded. Which is the primary run and which the sensitivity run? *Recommendation: report both; you choose the primary.*
3. Keep the proposed near-empty rule (10% of the median, previous 14 days, at least 7 observations) or change it? Must the lookback of at least 14 days be processed before the first scored day?

**Coverage**
4. Primary source-coverage threshold: 0.50, 0.75, 0.90 or none (report only)? Which are sensitivity runs? *Recommendation: pre-register 0.50/0.75/0.90 as sensitivity; you pick the primary.*
5. Confirm that coverage means "covered slots available by the cutoff, divided by expected nominal slots" (current), with delayed slots uncovered. Add an absolute limit on consecutive missing slots?
6. Scoring coverage: report only, or a threshold (give the value)?

**Late batches**
7. Pre-window late batches (F1): (A) keep ignoring, (B) expand the accounting range by L trading days (give L), (C) read their files, (C-min) detect and mark the receiving interval incomplete. *Recommendation: C-min now.*
8. Is a delayed batch with zero rows of a theme evidence that the theme had no records? (a) no (orchestrator), (b) yes unless it carries rows of that theme (aggregator).

**Repeated content**
9. Which repeats may be linked (record only, never dropped): same URL, same title hash, updates? Which evidence level counts as "verified"?
10. Primary counting unit: every record, first-occurrence story, or story with versions? (Only needed before feature generation.)

**Vocabulary and secondary defects**
11. Adopt the four-level vocabulary of section 6 (completeness, usability, record evidence, availability), with the orchestrator owning level 1?
12. F3: add the company-item count to `SlotAccounting` and reconciliation?
13. F4: must all slots in a window share one parser version (window fails otherwise)?
14. F6: should an unresolved policy block conversion and feature steps (raise), or only warn?
15. F7: confirm the fields the digest must cover (record content hashes, policy status, input fingerprints).
16. Approve the implementation order of section 9, or give a different order?

---

## 11. Confirmation

Read-only apart from this report. No application code, test, manifest, day file, dataset, approved criterion, compliance rule, provider gate
or build lock was modified. No network access, installation, inference or acquisition. No sealed key or annotation label was accessed. The
probes were in-memory runs against synthetic data and the local sample opened read-only. No corrective implementation, scoring, S2.9 or S4
was started. No staging, commit or push. Final Git: HEAD `71b363f`, staged 0, tracked modifications 49 (unchanged), untracked 57 including this report.
