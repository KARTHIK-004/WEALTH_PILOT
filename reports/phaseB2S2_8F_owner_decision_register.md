# Research Enhancement Track — Phase B2-S2.8F: Owner Decision Register and Aggregator Coverage Integration Plan

**Status: COMPLETE (documentation and audit only).** No code, test, configuration, sample or approval record was changed. Nothing in this register is an
approval. A "Recommendation" is the assistant's suggestion and becomes policy only when the owner answers in the form given under "Owner response needed".
Date: 2026-10-20 (UTC). Written for: the project owner.

## 0. Basis and caveats

- Sources read: `CLAUDE.md`; `docs/PROJECT_PLAN.md` and `docs/ARCHITECTURE.md` (present; this track is not specified there beyond the general rules); reports S2.8A–S2.8E;
  `sentiment/completeness.py`, `coverage_report.py`, `near_empty.py`, `orchestrator.py`, `features.py` (`_evidence`, `_assess_day`), `policy.py`, `coverage.py`.
- The original owner message of 16 answers is not visible (S2.8B/C said so). Status "SELECTED" below means: stated in the owner's own S2.8B–S2.8E instruction text.
  Anything else is UNCONFIRMED, not "not stated".
- Status vocabulary: **SELECTED** (owner-stated direction), **PROVISIONAL** (owner-stated, explicitly not validated), **UNCONFIRMED** (no evidence either way),
  **BLOCKED** (cannot proceed until a named approval), **IMPLEMENTED** (applied in code as owner-selected). `IMPLEMENTED` is never `APPLIED_APPROVED`: the code's
  policy statuses (`orchestrator.POLICY_STATUS`) still block every downstream step.

Current policy statuses in code (unchanged): `deduplication_and_story_updates`, `source_coverage_threshold`, `near_empty_slot_handling` = `SELECTED_PROVISIONAL_NOT_APPLIED`;
`late_batch_strictness` = `SELECTED_APPLIED_LOOKBACK_UNDECIDED`; `cross_interval_story_uniqueness`, `scoring_coverage_threshold`, `scorer_approval_and_polarity_validation`
= `UNRESOLVED_NOT_APPLIED`; `holiday_and_early_close_calendars` = `CALLER_SUPPLIED_NOT_APPROVED`. All eight required policies block.

## 1. Register

### OD-01 (A) Earlier-batch lookback

| Field | Entry |
| --- | --- |
| Question | How far before the requested window must the manifest be examined for earlier nominal batches whose **verified availability** falls inside the window, and who is responsible for supplying that range? |
| Status | **UNCONFIRMED** (length); mechanism C-min is **SELECTED / IMPLEMENTED** (S2.8C) |
| Current behaviour | `WindowInputs.earlier_batches_from` is caller-supplied; `None` = not examined, every interval incomplete. Examined batches are placed by verified availability; an unresolved one makes its receiving interval incomplete (an unverifiable one, every interval). The window is never extended. No duration is encoded anywhere (the synthetic tests use 24 h only as fixture data). |
| Options | **Short (e.g. hours–days):** cheap, little extra data to acquire; a batch arriving later than the lookback is *invisible*, so an interval can read "complete" while a late batch is still to come. **Long (e.g. a week or more):** catches more late arrivals; needs more manifest rows and baseline-style completeness for that range, and makes every window depend on earlier data. **Measured:** choose after measuring real lateness on a contiguous window (S2.8C's stated reason for deferring). |
| Limit that holds for any choice | A declared lookback proves nothing outside its range. "Complete" always means "complete as far as the declared range shows". |
| Recommendation (not an approval) | Keep it caller-supplied until lateness is measured on contiguous data; then choose a length with margin over the observed maximum and record the residual limit in every report. |
| Owner response needed | One of: (a) a fixed duration (state it), (b) "measure first, then decide" plus who decides, (c) keep caller-supplied indefinitely. |
| Affected | `orchestrator.orchestrate_window`, `WindowReport.earlier_evidence`, `features.aggregate_daily(earlier=)`, `late_batch_strictness` policy, full-window acquisition design |

### OD-02 (B) Source-coverage thresholds

| Field | Entry |
| --- | --- |
| Question | Are primary 0.75 and sensitivity 0.50 / 0.90 (ratio of covered to expected nominal slots) adopted, changed or dropped? |
| Status | **PROVISIONAL** |
| Current behaviour | `CoverageThresholds` (explicit, `PROVISIONAL_NOT_APPROVED`) is reported per interval by the orchestrator; it authorises nothing. In the aggregator, `SentimentConfig.coverage_threshold` (caller-supplied, tests use 0.75) gates `coverage_status = ok / insufficient_coverage`, reachable only after the policy guard passes. |
| What a verdict **can** establish | Only that a stated share of expected source slots were processed, valid, on time and not flagged near-empty. It is a statement about *source slots*. |
| What it **cannot** establish | That the sentiment is valid, that polarity is correct, that the filter's themes are right, that records in covered slots are representative, that a missing theme has no news (a ratio never creates verified `no_news`; only a complete source with every indicator known false does), or that scoring coverage is adequate (separate, unresolved). |
| Options | Keep three levels (primary + sensitivity); change levels; replace with an absolute missing-slot rule (see OD-06) or combine both. The audit data showed 15 / 15 / 14 days below 0.75 / 0.90 / 0.50 in the forecast set, so the levels differ little there; this says nothing about delayed or late data. |
| Recommendation (not an approval) | Keep the three as provisional and report all three; do not let any of them select a primary result until the threshold is checked on contiguous data. |
| Owner response needed | "Adopt / change to X / drop" for the primary, and whether the sensitivity levels stay; then (separately) when the policy may move to `APPLIED_PROVISIONAL`. |
| Affected | `coverage_report.CoverageThresholds`, `orchestrator`, `features.SentimentConfig`, `source_coverage_threshold` policy |

### OD-03 (C) Near-empty detector parameters

| Field | Entry |
| --- | --- |
| Question | Are previous 14 calendar days, at least 7 valid same-slot observations and "below 10% of the baseline median" adopted, changed or dropped? |
| Status | **PROVISIONAL** |
| Current behaviour | `near_empty.NearEmptyParams` (provisional), pure detector, strictly prior committed same-slot observations only; `UNKNOWN` without caller-declared baseline evidence covering the whole lookback, with too few usable observations, or with an invalid observed count. Reported separately from the observed manifest flag; never changes coverage. |
| Assumptions | The same slot of day is comparable across days (weekday/weekend and holiday patterns are **not** modelled, so a quiet Sunday can be compared with weekdays); 14 days is long enough to be stable but short enough to follow level changes; the median is robust to a few outliers; `rows_english_valid` measures source volume, not news content; a long outage leaves no usable baseline for about 7 days afterwards (so the slot is unknown, which is the safe direction). |
| Risks of classifying near-empty | A false positive (a legitimately quiet slot, a weekend, a holiday, a real lull) removes a slot from coverage and may lower an interval below a threshold; a false negative lets a degraded batch count as covered. A low count is **not** proof of missing data and is never treated as missing. A baseline containing earlier degraded slots drags the median down and hides further degradation. |
| Insufficient-baseline behaviour | Explicit `UNKNOWN` (reasons `no_baseline_evidence_declared`, `baseline_lookback_not_available`, `insufficient_valid_baseline`, `baseline_not_committed`); `UNKNOWN` is never false and never evidence of completeness. |
| Options | Keep as is; day-type-specific baselines (weekday vs weekend, needs more history); a different ratio or minimum count; relax the "whole lookback declared" requirement (would use partial baselines: more decisions, weaker guarantee). |
| Recommendation (not an approval) | Keep as is, provisional, and evaluate flag/derived agreement on a contiguous window before approving; do not use the derived state to override the observed flag. |
| Owner response needed | Adopt / change (state values) / drop; and whether a partial lookback may ever decide. |
| Affected | `near_empty.py`, orchestrator derived fields, `near_empty_slot_handling` policy, the collector's `near_empty_flag` (unchanged, observed) |

### OD-04 Unknown (NULL) near-empty: undecided or unusable

| Field | Entry |
| --- | --- |
| Question | When an otherwise complete interval has slots with a NULL near-empty flag, should it stay "undecided by policy" or become "unusable"? |
| Status | **SELECTED** (a NULL flag is neither complete evidence nor verified no-news); mechanism **UNCONFIRMED** |
| Current behaviour | The interval is `UNDECIDED_POLICY`; coverage excludes the slot as `near_empty_unknown`; no theme can be `VERIFIED_ZERO_RECORDS`. |
| Options | Keep undecided (current); unusable (fail closed, more intervals lost: first 7 days of any run and about 7 days after a long outage have NULL flags); usable under a coverage rule only. |
| Recommendation (not an approval) | Keep undecided until OD-02/OD-03 are settled, then let the applied coverage rule decide. |
| Owner response needed | One of the three options. |
| Affected | `completeness.assess_interval`, orchestrator, aggregator |

### OD-05 Explicit near-empty handling in the primary and sensitivity runs

| Field | Entry |
| --- | --- |
| Question | Confirm: primary run treats an explicit near-empty slot as uncovered; a sensitivity run may treat it as covered with the flag kept. |
| Status | **PROVISIONAL** (S2.8B) |
| Current behaviour | Primary semantics only (uncovered). The sensitivity variant is **not implemented**. |
| Recommendation (not an approval) | Implement the sensitivity variant only after OD-02/03 are answered, as a reported alternative, never as the primary. |
| Owner response needed | Confirm, and say whether the sensitivity variant is wanted. |
| Affected | `coverage_report`, `coverage.interval_count` (`unknown_near_empty_is_covered` exists but is unused), aggregator |

### OD-06 Limit on consecutive missing slots

| Field | Entry |
| --- | --- |
| Question | Is there an absolute cap on consecutive slots without valid evidence, independent of the ratio? |
| Status | **UNCONFIRMED** |
| Current behaviour | The longest runs are **reported** (`max_consecutive_missing_run`, `max_consecutive_uncovered_run`); no limit is applied. A ratio alone can hide a long outage (the audited outage ran 416 h). |
| Options | No cap; a cap in slots/hours; a cap that applies to the primary only. |
| Recommendation (not an approval) | Decide a cap together with OD-02, because a ratio and a cap answer different questions. |
| Owner response needed | None / a number with its unit and whether it blocks or only flags. |
| Affected | `coverage_report`, `source_coverage_threshold` policy |

### OD-07 Scoring-coverage threshold

| Field | Entry |
| --- | --- |
| Question | What share of eligible records must be scored for a theme-day to count? |
| Status | **UNCONFIRMED**; blocked behind OD-E1 |
| Current behaviour | `scoring_coverage` is reported by the aggregator, no threshold; policy `UNRESOLVED_NOT_APPLIED`. Source coverage and scoring coverage are separate by construction. |
| Recommendation (not an approval) | Decide only once a scorer exists (E1). |
| Owner response needed | A threshold or "none, report only". |
| Affected | `features._theme_row`, `scoring_coverage_threshold` policy |

### OD-08 Delayed batch with zero rows — **IMPLEMENTED** (S2.8D)

A delayed, empty batch is not verified no-news (at the cutoff it did not exist yet). Applied in the shared contract, orchestrator and aggregator. Listed for completeness; no answer needed unless the owner wants it reversed.

### OD-09 Shared vocabulary names

| Field | Entry |
| --- | --- |
| Question | Confirm the names `SourceCompleteness`, `IntervalUsability`, `ThemeEvidence`, `ResultAvailability`, `SlotAccount`, `NearEmpty` and their values, and the S2.8E `CoverageBlock` exclusion-reason names. |
| Status | **PROVISIONAL** (the names are the assistant's design) |
| Recommendation (not an approval) | Confirm before more code depends on them; renaming later changes digests. |
| Owner response needed | Confirm, or list renames. |
| Affected | `completeness.py`, `coverage_report.py`, orchestrator, aggregator, digests |

### OD-10 (D) Aggregator integration with the shared coverage contract

| Field | Entry |
| --- | --- |
| Question | May `aggregate_daily` use `coverage_report.coverage_block` (supplement or replace its own computation), and if it replaces it, how should a processed-but-unreconciled slot count? |
| Status | **UNCONFIRMED**; **not authorised** by the current policy contract (`source_coverage_threshold` is `SELECTED_PROVISIONAL_NOT_APPLIED`; S2.8E explicitly left `_assess_day` unwired) |
| Current behaviour | See section 2. |
| Recommendation (not an approval) | Supplement first (report-only block, no behaviour change); replace the numerator only after the owner answers the unreconciled-slot question. |
| Owner response needed | (1) Supplement now: yes/no. (2) For replacement: does a processed slot with a reconciliation problem count as covered (current aggregator) or excluded as `rejected` (shared block)? |
| Affected | `features._assess_day`, `DailyFeatures`, `test_sentiment_scaffold.py`, digests of any stored result |

### OD-11 Repeated content and cross-interval story uniqueness

| Field | Entry |
| --- | --- |
| Question | Which relations (same canonical URL, same title hash, similar title) may be linked, at what evidence level, and may a story be counted in more than one interval? |
| Status | Retention and "similarity is not identity" **SELECTED**; counting unit "every eligible record + repetition sensitivity" **PROVISIONAL**; linking rules and cross-interval uniqueness **UNCONFIRMED** |
| Current behaviour | Records retained; repeats counted only (`RepeatedContent`); no story identity inferred; policies `SELECTED_PROVISIONAL_NOT_APPLIED` / `UNRESOLVED_NOT_APPLIED`. |
| Recommendation (not an approval) | Keep counting-only until the sentiment unit is chosen. |
| Owner response needed | The linking rule (or "none"), the cross-interval rule. |
| Affected | `dayfile_adapter`, `orchestrator.RepeatedContent`, a future feature step |

### OD-12 Calendars and theme cutoffs

| Field | Entry |
| --- | --- |
| Question | Which holiday and early-close calendars are authoritative, and do themes (rates, gold) have their own cutoffs? |
| Status | **UNCONFIRMED**; calendars are caller-supplied and unapproved; theme cutoffs `NOT_IMPLEMENTED` |
| Recommendation (not an approval) | Name one calendar source and keep a single US-equity cutoff until themes are in scope. |
| Owner response needed | A calendar source (or "caller-supplied is fine") and yes/no on theme cutoffs. |
| Affected | `features.interval_cutoffs`, `session_calendar`, every interval boundary |

## 2. Part D — what the aggregator does today, and an integration plan

**Current computation (`features._assess_day`)**, read from the source (not executed in this phase):

1. Per slot it builds `SlotEvidence` (`_evidence`) for the shared assessment, and **separately** a `SlotSummary(processed_as_of_cutoff, near_empty, rows_captured)` for `coverage.interval_count`.
2. `interval_count` counts a slot as covered iff processed by the cutoff, `series_rows` present, and `near_empty is False`; `coverage = covered / len(summaries)`; below the single threshold the observation value is `None` (`insufficient_coverage`).
3. `n_slots_covered = round(coverage × n)`; `n_slots_near_empty` counts only processed true flags; delayed slots are uncovered.
4. `assess_interval(..., coverage_rule_met = (obs.value is not None))` — the threshold verdict reaches usability **without consulting a policy status**; the only protection is that `aggregate_daily` calls `require_policies_applied(config.policy)` first.
5. `no_news` is derived from the shared theme evidence, not from coverage.

**Differences from the shared `coverage_report`:**

| # | Aggregator | Shared block | Consequence of replacing |
| --- | --- | --- | --- |
| 1 | The summaries ignore the reconciliation verdict, so a processed slot with a count/availability problem **counts as covered** (the day then reports `slot_article_mismatch`) | Such a slot is `REJECTED`, excluded | `n_slots_covered` and `coverage` change for mismatch days; status precedence (`insufficient_coverage` vs `slot_article_mismatch`) can change |
| 2 | One threshold; no sensitivity | Primary + sensitivity results | None unless sensitivity is surfaced |
| 3 | `coverage_rule_met` set from the threshold, status not consulted | Verdict only through an applied policy status | Same outcome today (the guard forces applied), different failure mode if the guard is ever relaxed |
| 4 | Count derived by `round(ratio × n)` | Exact integer numerator | Equal in practice; the integer is safer |
| 5 | Exclusion reasons are not itemised | Seven reasons + two runs | Pure addition |
| 6 | Status gate `missing_source_batches` when nothing was available by the cutoff | No such gate (reports ratio 0) | Must be kept in the aggregator |

**Can it replace or supplement without changing the meaning of unresolved policies, `no_news` and fail-closed behaviour?**
- **Supplement: yes**, safely. Compute `coverage_block(evidence, …)` inside `_assess_day`, carry it on `_Day`, and add it to `DailyFeatures` as a report-only field. `coverage_status`, `n_slots_*`, `no_news` and all gates stay computed exactly as now.
- **Replace the numerator: only after OD-10(2)**, because of difference 1. It would be a behaviour change, not a refactor.
- Neither changes `no_news` (it comes from theme evidence) or policy blocking (`require_policies_applied` stays first).

**Integration plan (not executed; needs owner go-ahead for step 2 and beyond):**
1. *Supplement (report-only).* Add the block to `_Day`/`DailyFeatures`; no gate reads it. Digest/stored-result consumers: none exist yet.
2. *Cross-check test.* For every aggregator scenario, assert `block.n_covered == n_slots_covered` where no reconciliation problem exists; assert the known difference where one does (documents difference 1).
3. *Decide OD-10(2).* If "excluded", switch the numerator to the block and update the affected scaffold tests deliberately; if "covered", change the shared block instead (add a `processed_unreconciled` reason) so both agree.
4. *Policy-status routing.* Replace `coverage_rule_met=obs.value is not None` with `coverage_rule_decision(block, thresholds, config.policy.status("source_coverage_threshold"))`, so the verdict can never act on an unapplied policy even if the guard changes.
5. *Retire `interval_count` use* in the aggregator only after steps 2–4 pass; keep the module (still used by tests/audit code).

**Required tests:** numerator equality on clean days; documented divergence on unreconciled days; delayed / absent / near-empty / unknown / non-final each distinct and unchanged in `DailyFeatures`; `no_news` identical across thresholds (0.10–1.0) and across a high ratio with an unverified empty theme; all eight scaffold coverage tests and the C-min tests unchanged; unapplied-policy aggregation still raises `PolicyBlockedError`; denominator equals the full grid with a missing slot; mutation check that a status-ignoring `coverage_rule_decision` is caught.

**Risks:** silent change of `n_slots_covered` on mismatch days (difference 1); two coverage definitions drifting if only one is changed; reading a high ratio as validity (the register's OD-02 caveat); breaking existing scaffold expectations (`test_sentiment_scaffold.py` lines 359–377, 684–701); digest changes if the block is added to any stored result.

## 3. Part E — outstanding research approvals (all BLOCKED; S2.8E completion authorises none)

| ID | Item | Why blocked | Needed from the owner |
| --- | --- | --- | --- |
| E1 | Scorer / model, licence and dependency approval | No model is approved; no dependency may be installed; `scorer_approval_and_polarity_validation` is `UNRESOLVED_NOT_APPLIED`; the fake scorer is test-only | Model, licence check, dependency list, and a statement that installation may occur |
| E2 | Polarity ground truth and validation plan | No independent polarity labels; AI labels are never independent; manual/fake labels are forbidden | A labelling source and protocol, and the acceptance criterion |
| E3 | Article eligibility and the candidate-to-scored-record contract | Candidates are unscored `CandidateRecord`s; no conversion to `ArticleRecord` exists; story identity/`story_id` policy and the counting unit are open (OD-11) | Eligibility rules, counting unit, `story_id` rule |
| E4 | Sentiment feature generation | Blocked by E1–E3 and every unresolved required policy; `aggregate_daily` refuses while any is unapplied | Explicit go-ahead after E1–E3 |
| E5 | Forecast target and evaluation design | No target or protocol approved; the D8 criteria are unchanged and are not reopened here | Target definition, horizon, split/embargo protocol, metrics |
| E6 | GDELT filter validation and independent reference labels | The B2 evaluation still lacks independent labels; the sealed key stays sealed; D12/D12.1 guard and D13 lock untouched | An independent labelling plan, and who may unseal when |
| E7 | Full-window data acquisition | No acquisition approved; lookback (OD-01) and baseline completeness (OD-03) must be settled first so the acquired range is sufficient | Window, lookback, storage, network permission |

## 4. What this phase did not change

No code, test, policy status, threshold, detector parameter, lookback, sample file, model registry, build lock, compliance rule or approval record was changed. No scoring,
feature generation, candidate-to-`ArticleRecord` conversion, evaluation, S2.9 or S4 work was done.
