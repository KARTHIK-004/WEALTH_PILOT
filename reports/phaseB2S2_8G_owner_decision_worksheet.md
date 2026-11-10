# Research Enhancement Track — Phase B2-S2.8G: Owner Decision Worksheet and S2 Readiness Audit

**Status: COMPLETE (documentation and read-only audit).** Nothing here is an approval. No code, test, policy status, threshold, parameter, lookback, sample file or
approval record was changed. Date: 2026-10-20 (UTC). Written for: the project owner.

## 0. Verified state (checked this phase, not assumed)

| Check | Result |
| --- | --- |
| Git | HEAD `71b363f`; 0 staged; 49 tracked modifications; 162 untracked files; nothing reset, cleaned, stashed or committed |
| Policy statuses (read from `orchestrator.POLICY_STATUS`, executed) | `deduplication_and_story_updates`, `source_coverage_threshold`, `near_empty_slot_handling` = `SELECTED_PROVISIONAL_NOT_APPLIED`; `late_batch_strictness` = `SELECTED_APPLIED_LOOKBACK_UNDECIDED`; `cross_interval_story_uniqueness`, `scoring_coverage_threshold`, `scorer_approval_and_polarity_validation` = `UNRESOLVED_NOT_APPLIED`; `holiday_and_early_close_calendars` = `CALLER_SUPPLIED_NOT_APPROVED`. Extra entries: `theme_specific_calendars` = `NOT_IMPLEMENTED`, `scoring` = `NOT_PERFORMED` |
| Required policies blocking | **8 of 8** (`PolicyState.unresolved()`); none is `APPLIED_*` |
| E1–E7 | all still BLOCKED, as in S2.8F section 3 (no approval record exists in the repository evidence read) |
| Sentiment tests (this phase) | `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/backend/data/gdelt/test_sentiment_*.py` → **299 passed** in 14 s. The S2.8E full-suite figure (1324) was **not** re-run; no code changed since |
| Sample tree (read-only harness `s25_verify.py`) | 546 files, hash `271939bb1895d1d3` before and after: unchanged |

Statuses below are copied from the S2.8F register and the executed policy table. "Implemented" never means "approved": a code path, a passing test, a report or an
earlier recommendation is not owner approval.

## 1. Worksheet

Format per item: **Q** exact question · **Status** · **Why** · **Options** · **Rec** (recommendation only) · **Answer needed** · **Unlocks** · **Still blocked** · **Evidence before a status change**.

### OD-01 Earlier-batch lookback duration
- **Q:** How far before the requested window must the manifest be examined for earlier nominal batches whose verified availability falls inside the window, and who supplies that range?
- **Status:** UNCONFIRMED (duration). Mechanism C-min: SELECTED and IMPLEMENTED (S2.8C).
- **Why:** it bounds what "complete" can mean; a late batch from before the declared range is invisible. No declared lookback proves completeness outside it.
- **Options:** short (cheap, misses long lateness) · long (more coverage, more data and baseline needed) · measure lateness on a contiguous window first · keep caller-supplied.
- **Rec:** measure first, keep caller-supplied meanwhile.
- **Answer needed:** a fixed duration, or "measure first, decided by X", or "caller-supplied indefinitely".
- **Unlocks:** a default or validated `earlier_batches_from`; sizing of the acquisition window (with E7); `late_batch_strictness` can move beyond `LOOKBACK_UNDECIDED`.
- **Still blocked:** claiming completeness beyond the range; scoring, features, evaluation.
- **Evidence:** measured lateness distribution on contiguous data (none in the repository: only 192 isolated sample batches).

### OD-02 Source-coverage thresholds (0.75 primary; 0.50 / 0.90 sensitivity)
- **Q:** Are the primary and sensitivity levels adopted, changed or dropped?
- **Status:** PROVISIONAL.
- **Why:** decides which intervals are usable; a verdict establishes only a share of valid, on-time, non-near-empty source slots, never valid sentiment, correct polarity or verified no-news.
- **Options:** keep three levels · change levels · replace/combine with a missing-slot cap (OD-06).
- **Rec:** keep as provisional reporting; do not let any select a primary result before checking on contiguous data.
- **Answer needed:** adopt/change/drop for primary and for each sensitivity level, and separately whether `source_coverage_threshold` may become `APPLIED_PROVISIONAL`.
- **Unlocks:** applied threshold routing via `coverage_rule_decision`; usability states other than undecided.
- **Still blocked:** scoring/features (other policies), any claim of validity.
- **Evidence:** behaviour on a contiguous window including delayed and near-empty data (the audit covered neither).

### OD-03 Near-empty detector parameters (14 days, ≥ 7 observations, < 10% of median)
- **Q:** Adopt, change or drop?
- **Status:** PROVISIONAL.
- **Why:** a false positive removes legitimate quiet slots from coverage; a false negative lets a degraded batch count as covered. The baseline assumes comparable slots across days (weekend/holiday patterns not modelled).
- **Options:** keep · day-type-specific baselines · other ratio/minimum · allow partial lookbacks (weaker guarantee).
- **Rec:** keep provisional; compare derived and observed flags on contiguous data before approving.
- **Answer needed:** adopt / change (state values) / drop; and whether a partial lookback may ever decide.
- **Unlocks:** `near_empty_slot_handling` → applied; baseline sizing for acquisition.
- **Still blocked:** replacing the observed manifest flag with the derived state (not requested anywhere).
- **Evidence:** contiguous manifest history; agreement statistics between the observed flag and the detector.

### OD-04 Unknown/NULL near-empty flag
- **Q:** Should a complete interval with NULL flags stay "undecided by policy", become unusable, or be usable only under an applied coverage rule?
- **Status:** SELECTED that NULL is neither complete evidence nor verified no-news; mechanism UNCONFIRMED.
- **Why:** NULL is expected for the first ~7 days of a run and ~7 days after a long outage; the choice decides how much data is lost.
- **Options:** undecided (current) · unusable (fail closed, most data lost) · usable only under an applied rule.
- **Rec:** keep undecided until OD-02/03 are answered.
- **Answer needed:** one of the three.
- **Unlocks:** final `IntervalUsability` mapping for NULL slots.
- **Still blocked:** treating NULL as false (never allowed), verified no-news from a NULL-flag interval.
- **Evidence:** share of NULL-flag slots on contiguous data under each option.

### OD-05 Sensitivity handling of explicitly near-empty slots
- **Q:** Confirm: primary treats an explicit near-empty slot as uncovered; a sensitivity run may treat it as covered with the flag kept — and is that variant wanted?
- **Status:** PROVISIONAL (primary semantics only are implemented; the variant is not).
- **Why:** shows how sensitive results are to the near-empty rule.
- **Options:** confirm and implement variant later · confirm primary only · reverse.
- **Rec:** implement the variant only after OD-02/03, reported alongside, never as primary.
- **Answer needed:** confirm primary; yes/no on the variant.
- **Unlocks:** a sensitivity coverage report.
- **Still blocked:** changing primary semantics.
- **Evidence:** OD-02/03 answered; contiguous data.

### OD-06 Consecutive-missing-slot cap
- **Q:** Is there an absolute cap on consecutive slots without valid evidence, independent of the ratio?
- **Status:** UNCONFIRMED (runs are reported, no limit applied).
- **Why:** a ratio can hide a long outage (the audited outage ran 416 h).
- **Options:** no cap · cap in slots/hours that blocks · cap that only flags.
- **Rec:** decide together with OD-02.
- **Answer needed:** none / a number with unit, and block-vs-flag.
- **Unlocks:** a cap rule in the coverage verdict.
- **Still blocked:** any use of the cap without OD-02.
- **Evidence:** run-length distribution on contiguous data.

### OD-07 Scoring-coverage threshold
- **Q:** What share of eligible records must be scored for a theme-day to count?
- **Status:** UNCONFIRMED; blocked behind E1.
- **Why:** source coverage and scoring coverage are separate; only the latter says how much text was actually scored.
- **Options:** a threshold · report only.
- **Rec:** decide only once a scorer exists.
- **Answer needed:** a number or "report only".
- **Unlocks:** `scoring_coverage_threshold` policy decision.
- **Still blocked:** everything needing a real scorer (E1).
- **Evidence:** scoring-failure rates from an approved scorer.

### OD-08 Delayed batch with zero rows
- **Status:** IMPLEMENTED (S2.8D); not reopened. A delayed empty batch is not verified no-news. No answer needed unless the owner asks to reverse it.

### OD-09 Shared completeness vocabulary
- **Q:** Confirm the names and values in `completeness.py` and the `CoverageBlock` exclusion reasons.
- **Status:** PROVISIONAL (names are the assistant's design).
- **Why:** names enter digests and stored results; renaming later changes them.
- **Options:** confirm · list renames.
- **Rec:** confirm before more code depends on them.
- **Answer needed:** "confirmed" or a rename list.
- **Unlocks:** freezing the vocabulary and digest semantics.
- **Still blocked:** freezing before an answer.
- **Evidence:** owner review of the enumerations (listed in the S2.8D and S2.8E reports).

### OD-10 Aggregator coverage integration and unreconciled-slot treatment
- **Q:** (1) May the aggregator carry the shared `CoverageBlock` as a report-only field? (2) Does a processed slot with a reconciliation problem count as covered (aggregator today) or excluded as `rejected` (shared block)?
- **Status:** UNCONFIRMED; not authorised by the current policy contract.
- **Why:** replacing the numerator changes `n_slots_covered`, `coverage` and possibly status on mismatch days.
- **Options:** (1) yes/no; (2) excluded · covered (then add a distinct reason to the shared block so both agree).
- **Rec:** (1) yes, report-only; (2) excluded, but it is the owner's call.
- **Answer needed:** two separate answers.
- **Unlocks:** step 1 of section 3 on (1); numerator replacement on (2).
- **Still blocked:** policy-status routing becoming the only path to a verdict until applied; scoring/features.
- **Evidence:** the cross-check tests of section 3 passing.

### OD-11 Repeated content and cross-interval story counting
- **Q:** Which relations may be linked and at what evidence level; may a story be counted in more than one interval; what is the counting unit?
- **Status:** retention and "similarity is not identity": SELECTED; counting unit "every eligible record + repetition sensitivity": PROVISIONAL; linking rules and cross-interval uniqueness: UNCONFIRMED.
- **Why:** it defines what a sentiment observation is and prevents double counting.
- **Options:** counting-only (current) · link by canonical URL · link by title hash · similarity linking · allow/forbid cross-interval counting.
- **Rec:** stay counting-only until the unit is chosen.
- **Answer needed:** a linking rule (or "none") and a cross-interval rule.
- **Unlocks:** story-level unit, `story_id` design (still needs E3).
- **Still blocked:** story IDs and story-level features before an answer.
- **Evidence:** repeat statistics (sample: 133 repeated URLs, 2071 repeated title hashes) are descriptive only, not validation.

### OD-12 Authoritative calendars and theme-specific cutoffs
- **Q:** Which holiday/early-close calendar source is authoritative, and do themes have their own cutoffs?
- **Status:** UNCONFIRMED (calendars caller-supplied and unapproved; theme cutoffs not implemented).
- **Why:** every interval boundary depends on it.
- **Options:** name one source · keep caller-supplied · add theme cutoffs now/later.
- **Rec:** name one source; keep a single US-equity cutoff until themes are in scope.
- **Answer needed:** a source and yes/no on theme cutoffs.
- **Unlocks:** production-like interval boundaries.
- **Still blocked:** production-like boundaries before an answer.
- **Evidence:** the named calendar and a check of the window against it.

### E1 Scorer/model, licence and dependency approval — BLOCKED
- **Q:** Which model, under which licence, with which dependencies, may be used?
- **Why:** no scorer exists; `scorer_approval_and_polarity_validation` is unresolved; the fake scorer is test-only.
- **Options:** a named local model · an external provider · none yet.
- **Rec:** none; owner choice.
- **Answer needed:** model, licence check, dependency list, separate authorisation to install; separate authorisation for any external provider and any data transmission.
- **Unlocks:** scorer integration design. **Still blocked:** polarity validity (E2), conversion (E3), features, evaluation.
- **Evidence:** licence review, dependency review, a pinned version.

### E2 Polarity ground truth and validation plan — BLOCKED
- **Q:** What independent polarity labels and acceptance criterion validate the scorer?
- **Why:** AI labels are never independent; manual/fake labels are forbidden.
- **Options:** independent human labelling · an external labelled benchmark · none.
- **Rec:** none; owner choice.
- **Answer needed:** label source, protocol and criterion, with authorisation for any labelling activity.
- **Unlocks:** validated-polarity claims after the work is done. **Still blocked:** any claim of validated polarity.
- **Evidence:** completed independent labels and a result against the criterion.

### E3 Article eligibility and candidate-to-scored-record contract — BLOCKED
- **Q:** Which candidates are eligible and how does a candidate become a scored record?
- **Why:** candidates are unscored `CandidateRecord`s; no `ArticleRecord` conversion exists; depends on OD-11 and E1.
- **Options:** eligibility by text length/language/validity (current candidate rules) plus an explicit conversion contract.
- **Rec:** none.
- **Answer needed:** eligibility rules, counting unit, `story_id` rule.
- **Unlocks:** conversion design. **Still blocked:** conversion code until E1 and OD-11.
- **Evidence:** the written contract and its tests.

### E4 Sentiment feature generation — BLOCKED
- **Q:** When may features be generated?
- **Why:** `aggregate_daily` refuses while any required policy is unapplied.
- **Answer needed:** explicit go-ahead after E1–E3 and every required policy being applied.
- **Unlocks:** feature generation. **Still blocked:** evaluation without E5.
- **Evidence:** all eight required policies `APPLIED_*`.

### E5 Forecast target and evaluation design — BLOCKED
- **Q:** What is forecast, over which horizon, with which split/embargo and metrics?
- **Why:** approved evaluation criteria (D8) are not reopened here.
- **Answer needed:** target, horizon, protocol, metrics, with separate authorisation to run an evaluation.
- **Unlocks:** evaluation design. **Still blocked:** evaluation without E4.
- **Evidence:** a written protocol.

### E6 GDELT filter validation and independent reference labels — BLOCKED
- **Q:** How will the filter be validated against independent labels, and who may unseal anything?
- **Why:** the B2 evaluation lacks independent labels; the sealed key stays sealed; D12/D12.1 and D13 untouched.
- **Answer needed:** an independent labelling plan and a separate authorisation for any unsealing.
- **Unlocks:** validation work. **Still blocked:** any claim of filter validation.
- **Evidence:** independent labels and results.

### E7 Full-window data acquisition — BLOCKED
- **Q:** Which window, lookback, storage and network use are authorised?
- **Why:** needs OD-01 (lookback) and OD-03 (baseline length) first.
- **Answer needed:** window, lookback, storage, plus separate authorisation for network access and downloads.
- **Unlocks:** acquisition planning. **Still blocked:** acquisition itself until authorised.
- **Evidence:** OD-01 and OD-03 answered.

## 2. Dependency and execution map (constraints on order, not authorisations)

```text
OD-01 ──► (late-arrival completeness claim) ──┐
OD-01 + OD-03 ──► E7 (acquisition window)     │
OD-02 + OD-03 + OD-04 + OD-05 + OD-06 ──► final source-coverage behaviour ─┐
OD-09 ──► freeze vocabulary and digest semantics                          │
OD-10 ──► replace aggregator numerator                                    ├─► all required policies applied ─► E4 features ─► (E5) evaluation
OD-11 ──► story-level unit / story IDs ──► E3                             │
OD-12 ──► production-like interval boundaries                             │
E1 ──► scorer integration, dependency install ──► E2 validated polarity ──► E3 conversion
E6 ──► filter-validation claim (independent of the chain above)
```

- OD-07 is needed for `scoring_coverage_threshold` and needs E1.
- E4 needs E1–E3 and all eight required policies applied; E5 needs E4 before any forecast evaluation can run.
- A decision unlocks only the tasks listed under its item; no answer authorises an adjacent item.

## 3. Next implementation plan — prepared, NOT applied (needs the OD-10 answers)

1. Report the shared `CoverageBlock` next to the aggregator's existing coverage as a report-only field; `coverage_status`, `n_slots_*`, `coverage` and `no_news` keep their values.
2. Test numerator equality on clean reconciled intervals; assert and document the known divergence on unreconciled slots (aggregator counts them covered; the block excludes them as `rejected`).
3. Wait for explicit OD-10(2) before changing numerator semantics.
4. Route any threshold verdict through `coverage_rule_decision(block, thresholds, policy status)` so only an applied status can act.
5. Keep `no_news` derived from verified theme evidence, never from a ratio.
6. Keep the full expected-slot denominator, and keep source coverage separate from scoring coverage.

OD-10 behaviour stays unresolved: today `_assess_day` counts a processed-but-unreconciled slot as covered; the shared block does not. Neither is declared correct.

## 4. Owner response template

Rules: **a blank answer is unresolved.** An answer applies to its own line only. Nothing is preselected. Authorisations for models, licences, dependency installation, network access, data transmission and acquisition are separate lines and are never implied by any other line. Fill in only what you decide.

```text
OD-01 lookback duration:                     [ ] fixed: ____   [ ] measure first, decided by: ____   [ ] caller-supplied indefinitely
OD-02 primary threshold:                     [ ] adopt 0.75    [ ] change to ____   [ ] drop
OD-02 sensitivity thresholds (each):         0.50 [ ] adopt [ ] change ____ [ ] drop   0.90 [ ] adopt [ ] change ____ [ ] drop
OD-02 may source_coverage_threshold become APPLIED_PROVISIONAL?   [ ] yes   [ ] no
OD-03 near-empty parameters:                 [ ] adopt 14 / 7 / 10%   [ ] change to ____   [ ] drop      partial lookback may decide? [ ] yes [ ] no
OD-04 NULL near-empty:                       [ ] undecided   [ ] unusable   [ ] usable only under an applied rule
OD-05 explicit near-empty:                   primary uncovered [ ] confirm [ ] change ____    sensitivity variant wanted [ ] yes [ ] no
OD-06 missing-slot cap:                      [ ] none   [ ] ____ slots/hours   [ ] blocks   [ ] flags only
OD-07 scoring-coverage threshold:            [ ] ____   [ ] report only
OD-08 delayed zero-row batch:                [ ] keep as implemented   [ ] reverse (explicit request)
OD-09 vocabulary:                            [ ] confirmed as written   [ ] renames: ____
OD-10 (1) report-only block in the aggregator:   [ ] yes   [ ] no
OD-10 (2) unreconciled slot counts as:       [ ] excluded (rejected)   [ ] covered (add a distinct reason)
OD-11 linking rule:                          [ ] none   [ ] ____        cross-interval counting: [ ] allowed [ ] forbidden
OD-11 counting unit:                         [ ] every eligible record + repetition sensitivity   [ ] other: ____
OD-12 calendar source:                       [ ] ____   [ ] caller-supplied is fine         theme cutoffs: [ ] yes [ ] no
E1 model/licence (named): ____    dependency list: ____
E1 authorise: dependency installation [ ] yes [ ] no   external provider [ ] yes [ ] no   data transmission [ ] yes [ ] no   network access [ ] yes [ ] no
E2 label source/protocol/criterion: ____     authorise labelling activity [ ] yes [ ] no
E3 eligibility rules / unit / story_id rule: ____
E4 feature generation:                       [ ] authorised after E1–E3 and all policies applied   [ ] not authorised
E5 target / horizon / protocol / metrics: ____     authorise running an evaluation [ ] yes [ ] no
E6 independent labelling plan: ____          authorise any unsealing [ ] yes [ ] no
E7 window / lookback / storage: ____         authorise network [ ] yes [ ] no   authorise download/full-window acquisition [ ] yes [ ] no
```

## 5. What this phase did not do

No source, test, policy, threshold, parameter or lookback change; no sample, manifest, registry, build-lock, compliance or approval-record change; no network, install, key/label
access, scoring, feature generation, evaluation, S2.9 or S4.
