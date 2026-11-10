# WealthPilot AI — Current Project Memory

The current, verified state of the project. Not a historical narrative —
that lives in `reports/`. Update this file whenever current architecture
or state changes materially; keep entries short and current, not a log.

## Current Phase
Phase 36 (Household Goals & Emergency-Fund Planning) is the most recently
completed phase — see `reports/phase36_household_goals_report.md` — and Phase 35
(Household Financial Data Persistence & Management) immediately before it
(`reports/phase35_household_financial_persistence_report.md`).

- **Phase 35** found that the four household financial tables, their sixteen
  CRUD routes and the summary's use of them already existed (Phases 33/34). With
  the owner's agreement it added only optional factual metadata — `notes` on all
  four, `description` on assets and liabilities, `interest_rate` on liabilities —
  kept `is_active` as the activity rule, and kept ADR-032's `amount > 0` and
  nullable `monthly_payment` (ADR-034).
- **Phase 36** added `household_goals`: a household's goals as stored facts,
  separate from the individual `financial_goals`, with no goal math (the
  assumptions `core/goals.py` needs do not exist for a household) and the
  emergency-fund requirement still computed only by the Phase 34 summary
  (ADR-035).

Neither phase changed `core/`, `agents/`, any model, the individual goals or
financial inputs, or `POST /api/analysis`. No numbered implementation phase is
in progress and no further numbered phase is authorized.

**Research Enhancement Track (separate from the numbered phases; never Phase
37).** Phase B0 produced `docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md` (design
only). **Phase B1** added optional monthly financial records and a pure
behaviour-feature module (`reports/phaseB1_financial_behaviour_inputs_report.md`,
ADR-042). Nothing reads them yet: not `POST /api/analysis`, the recommendation
engine, the optimizer or compliance. B1 was verified (`reports/phaseB1V_verification_report.md`)
and accepted. **Phase B2** (research only) evaluated historical news sources
(`reports/phaseB2_historical_news_source_evaluation.md`). GDELT 2.0 GKG is
conditionally recommended for a market-level experiment; nothing was acquired,
installed or changed. **Phase B2-F** (research only,
`reports/phaseB2F_gdelt_acquisition_feasibility.md`) costed acquiring it.

- **Route A** (stream the English 15-minute files, filter locally, keep no raw
  archive) is conditionally recommended over BigQuery: ≈0.90 TB download, ≈2–6 GB
  kept.
- It found a GDELT outage (2025-06-14 → 2025-07-02 UTC) inside test window 6.
- It corrected B2's window dates: test returns run 2024-01-16 → 2026-07-21.

Route A was then conditionally approved. **Phase B2-G**
(`reports/phaseB2G_gdelt_pilot_audit.md`) piloted it with one English GKG file and
the master file list, both since deleted.

- **Download size:** exactly 0.860 TB for 160,658 listed files.
- **Gaps:** 1,854 slots (1.14%) are absent from the window, including a March 2023
  disruption. Twelve test-period forecast days have under 90% news coverage.
- **Parsing:** streaming works with about 5 MB of memory.

**Phase B2-H** (`reports/phaseB2H_pre_acquisition_readiness.md`) is the
pre-acquisition gate.

- **Checks:** the 180 unchecked absent slots were header-checked. 178 are absent,
  1 is inconclusive, and 1 exists although the master list omits it.
- **Calendar:** verified official NYSE early closes.
- **Evaluation basis:** fingerprinted (`market_data` SHA-256 `563afd21…`); no
  holdout is defined.
- **Proposals:** a frozen filter specification and a missing-data policy.
- **Recommendation:** the minimal window, or the holdout window only if a holdout
  is designated first.

**Phase B2-I** (`reports/phaseB2I_filter_review_and_acquisition_preparation.md`)
prepared the filter review and the acquisition.

- **Decisions:**
  - the minimal window, so there is no news holdout;
  - the June 2025 outage accepted without further checks;
  - filters approved for labelled review only.
- **Review:** blocked. No title sample is retained, and the only past
  training-period batch was never title-reviewed.
- **Proposals:**
  - a rubric;
  - a pre-registered sample of 192 + 192 training-period batches (≈1.03 GB
    each);
  - a manifest schema and a streaming design.
- **Next step, awaiting approval:** the development sample, before the capture
  rule is frozen.

**Phase B2-J** (`reports/phaseB2J_development_sample_approval_checklist.md`) is the
approval checklist for that sample.

- **Checklist:** 12 items across four gates: implementation, the sample download,
  the first label, and full acquisition.
- **Utility design:** isolated and not yet built, in
  `backend/wealthpilot/data/gdelt/`. It uses the standard library and PyYAML
  only.
- **Test plan:** about 90 offline tests.
- **Guards:** hard resource limits. Sequential by default; the sample is capped
  at 1.50 GB.
- **Sample integrity:** the B2-I lists were re-derived from the report text and
  match their committed hashes.

**Phase B2-K** (`reports/phaseB2K_gdelt_tool_implementation_report.md`) built the
isolated tool in `backend/wealthpilot/data/gdelt/`.

- **Dependencies:** standard library + PyYAML only; nothing in the application
  imports it.
- **Tests:** 146 offline tests pass.
- **Locks:** network, the development sample and the confirmation sample are
  locked off in this build. Full acquisition always refuses.
- **Run it:** `python -m wealthpilot.data.gdelt dry-run`.

**Phase B2-L** (`reports/phaseB2L_gdelt_development_sample_and_filter_review.md`)
is blocked before network access.

- **Blockers:** no approval record, and the data allowance is unconfirmed.
- **Result:** 0 bytes downloaded and no labels.

The completion report is `reports/phaseB2_completion_and_acquisition_readiness.md`.

- **Status:** B2 is complete as research design but blocked on the development
  sample and its labelled review.

**Phase B2-M** (`reports/phaseB2M_development_sample_acquisition_report.md`)
stopped at its authorization check.

- **First pass:** stopped at the authorization check; no confirmations had been given.
- **Then:** you confirmed the allowance (user-confirmed, not verified), approved the
  sample, and chose annotation plan (c) with retention until the review ends.
- **Approval record:** git-ignored, at
  `datasets/raw/gdelt/english_gkg_v1/provenance/run_config.yaml`.
- **Locks:** the development-sample and network locks are lifted; the confirmation
  sample stays locked.
- **Tests:** 148 pass. The preflight is ready.
- **Status:** no download yet; it waits for your explicit `fetch-sample` go-ahead.

**Phase B2-N** (`reports/phaseB2N_sample_verification_and_annotation_report.md`)
checked the local files.

- **Finding:** the acquisition never ran. There is no manifest, review folder or
  archive.
- **Annotation preparation:** blocked.
- **Tests:** 148 still pass.

**The B2-M acquisition then ran** on 2026-10-13 (16:25–16:34 UTC), after your
explicit authorisation.

- **Result:** all 192 development batches were downloaded, validated and
  processed, using 384 requests and 1,000,147,201 B, with no retries and no
  failures.
- **Timestamps:** availability was verified for all 192, including 155 cached
  copies corroborated by their zip times.
- **Counts:** the re-parse reproduces every count. Theme member rows:
  `EQUITY_US` 2,751, `RATES_US` 2,909, `GOLD` 193.
- **Stage C trigger:** not fired.
- **Location:** the data is git-ignored, in
  `datasets/raw/gdelt/english_gkg_v1/review/b2i_review_v1/`; details in the B2-M
  report.
- **Next:** annotation preparation (`build-review`), which needs your
  instruction.

**Phase B2-O** (`reports/phaseB2O_annotation_dataset_build_report.md`) built the
annotation files offline.

- **Output:** 1,493 items, of which 193 are in the gold cell, plus a 312-item
  second-annotator subset.
- **Checks:** every item maps to its source record. A rebuild is byte-identical,
  and the sealed key was never opened.
- **Schema:** `b2o_annotation_v1`; the provenance and annotator fields are added.
- **Next:** your labelling under plan (c). No labels exist yet.

**Phase B2-P** (`reports/phaseB2P_annotation_evaluation_report.md`) stopped
before the sealed key.

- **Finding:** both annotation files are unchanged from the build, with 0 of
  1,493 rows labelled.
- **Result:** the sealed key was not accessed and there is no evaluation.
- **Next:** your labelling.

**Phase B2-Q** (`reports/phaseB2Q_annotation_workflow_report.md`,
`reports/phaseB2Q_annotation_quick_reference.md`) prepared the offline labelling
workflow.

- **Helper:** `python -m wealthpilot.data.gdelt annotate` with `init`,
  `export-batch`, `merge`, `validate` and `status`. It never reads the sealed key.
- **Files:** a backup and a working copy were created; still 0 labels.
- **Tests:** 175 pass.
- **Open:** six rubric points are listed for your decision.
- **Next:** you label the 312 overlap rows, without AI suggestions.

**Phase B2-R** (`reports/phaseB2R_annotation_rubric_addendum.md`) assessed the six
rubric gaps. The addendum is PROPOSED and not adopted.

- **Compatible:** four points (timestamps, `company_notice` U with R, the working
  copy as the authoritative file, the empty title).
- **Your decision needed:**
  - **Ambiguity codes:** prefixed codes are not supported yet.
  - **Earlier-duplicate tie-breaker:** item ID conflicts with B2-H's record
    sequence.
- **Code:** unchanged. 10 characterisation tests were added; 185 pass.
- **Labels:** none.

**Phase B2-S** recorded your decisions: ambiguity option (b), and duplicate order
by `available_at_utc` then record sequence.

- **Exported:** the first overlap batch,
  `review_files/working/batches/batch_001_overlap.csv` (50 rows, all overlap).
- **Labels:** none yet.

**Interactive labeller (2026-10-13):** `annotate label` lets you label the 312 overlap
items at a prompt.

- **What it fills itself:** only session facts (initials, `human`, `own`, UTC time),
  saved one item at a time.
- **What it never shows:** AI suggestions or key data.
- **Tests:** 199 pass.
- **Labels:** still none.

**Phase B2-U** (`reports/phaseB2U_labeller_usability_and_ai_assistance_design.md`)
fixed the labeller.

- **Cause:** the rubric rule (company notice Y excludes R) was applied only at
  save, and a refusal discarded all answers.
- **Fix:** answers are kept per item, there is a review screen, `<` goes back, and
  the company-notice rule is explained as soon as it applies. The validator is
  unchanged.
- **Tests:** 212 pass.
- **AI suggestions:** designed but not built; they wait for the 312 overlap labels
  and your approval. One open decision: blind AI labels on the overlap items for
  the agreement figure.
- **Labels:** none; D0001 is not saved.

**Phase B2-T proposal** (`reports/phaseB2T_ai_assisted_annotation_methodology_proposal.md`)
is a PROPOSAL; none of it is approved.

- **Question:** whether to use AI assistance for all 1,493 items, including the
  312 human-only overlap items.
- **Recommendation:** a separately versioned dataset with a pre-registered blind
  subset (150 proposed), so some independent human-versus-AI comparison remains.
- **Pending approvals:** methodology, experimental design, model and provider,
  data handling, and execution. Each one is separate.
- **State:** nothing was run, no suggestion exists and 0 items are labelled.

**Phase B2-U3** (`reports/phaseB2U3_ai_assisted_annotation_implementation_report.md`,
2026-10-19): the AI-assisted annotation pipeline is **built but disabled**. The
AI direction is still **pending approval**; it has not been executed.

- **Built:** `backend/wealthpilot/data/gdelt/ai/` and an `ai` command group. It
  snapshots the original experiment into a new versioned folder, keeps the original
  overlap list as history, records every attempt with provenance, and queues every
  item for human review.
- **Locked:** build constant `AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD = False`, no
  provider adapter, four separate approval gates (A methodology, B provider and
  model, C data handling, D execution), and `--confirm-ai-run`. `ai run` always
  refuses in this build.
- **Original experiment:** untouched. AI-seen labels are flagged and are never
  independent human labels; the original human-only design is changed by AI
  assistance on the 312 overlap items.
- **Tests:** 430 pass in `tests/backend/data/gdelt/` (165 new, all offline).
- **State:** 0 of 1,493 items labelled; 0 AI suggestions; no model called; no data
  sent; sealed key not opened; GDELT switches unchanged.
- **Still to decide:** gates A to D, the blind-subset size, provider and model,
  cost caps, data handling and retention, and who runs it.

**Phase B2-U4** (`reports/phaseB2U4_ai_annotation_approval_package.md`,
2026-10-19) is an approval package. **Nothing is approved, enabled or executed.**

- **Contents:** methodology options, provider and pricing comparison (no provider
  selected), the exact fields that would leave the machine, proposed limits, the four
  gates with their hash components, and a check that `ai dry-run` writes nothing and
  `ai run` stays blocked.
- **Found, not fixed:** the AI review path drops the reviewer's `near_dup_of`; B2-T
  proposed no polarity but the validator and rubric require it for `R`; temperature
  is not configurable or recorded; `retention_days` is recorded but enforces no
  deletion; no evaluation code exists for the new dataset.
- **Tests:** 430 pass; no code changed.
- **State:** 0 of 1,493 items labelled; 0 AI suggestions; no model called; no data
  sent; sealed key not opened; build lock `False`; no adapter.
- **Yours to decide:** methodology (including the blind subset), provider and model,
  data handling, execution, and the duplicate and polarity questions.

**Phase B2-U5** (`reports/phaseB2U5_annotation_workflow_repairs.md`, 2026-10-19):
offline repairs to the AI-assisted workflow. **Nothing was enabled or run.**

- **Fixed:** the dropped `near_dup_of` answer; temperature is required, validated and
  hashed into Gate B, with a run manifest; the polarity decision must be recorded
  (hashed into Gate A); a blind label no longer cites a suggestion; unknown
  `provider`/`protocol` config keys are refused.
- **Added:** `ai retention` (dry run by default) and `ai evaluate` (integrity checks and
  methodology-neutral counts; a blind comparison only with validated provenance).
- **Still open, yours to decide:** the polarity option (only P1 exists in code);
  whether raw provider responses must be expirable (they are not, in the current
  layout); the evaluation methodology (ambiguous labels, kappa and AC1, clustered
  intervals, use for the section 4.7 filter decision).
- **Tests:** 577 pass in `tests/backend/data/gdelt/`. The full project suite was not run.
- **State:** 0 of 1,493 labelled; 0 AI suggestions; no model called; no data sent;
  sealed key not opened; build lock `False`; adapter registry empty; `ai run` blocked.

**B2 completion drive, Stage 1 done** (`reports/phaseB2_completion_decision_document.md`,
2026-10-19). Stages 2 to 4 are blocked on your decisions; nothing was run. B2 is still not complete.

- **Found, not fixed:** the pre-registered "pooled capture recall at least 0.90" is ambiguous. The
  code gates on pooled recall (attainable). Capture recall with the rule-of-three bound cannot reach
  0.90 at these sample sizes. The built AI pipeline still transmits every blind item, so "overlap items
  never sent" is not supported (this corrects the B2-U4 table). The freeze and evaluation do not read
  the AI dataset or stratify by label origin. `annotate label` covers only the overlap items.
- **Proposed, not approved:** protect the 312 overlap items (human-only, never sent). M1 is all-human
  (no provider needed); M2 is AI-assisted for the other 1,181 only. The B2-I section 4.7 numbers are
  reused unchanged. Thirteen decisions are listed in the report.

**B2-U12** (`reports/phaseB2U12_m2_selection_and_plan.md`, 2026-10-19): the project owner selected **M2** as the
preferred methodology (decision D1 only) and decided D2: exclusion mode `overlap_and_blind`, `blind_item_ids` empty
(exclusion setting only; no gate record created). D12 decided: option (c) (all labels decide, gated by
a pre-registered precision-only consistency guard on the 312 human-only items, tolerance 0.10, a failed guard gives
INSUFFICIENT_EVIDENCE). Approved and implemented offline (852 GDELT tests pass): F1-F3 bridge integrity, D3 realised-cell
reweighting with F4b (min 30 human-only members per series, refusal otherwise), the D12(c) combination, and the D13
overlap-first lock (`annotate lock-overlap`, `protocol.overlap_labels_sha256` bound into Gate D, revalidated at freeze).
F4a held. D8 approved: the B2-I criteria (precision 0.70, bootstrap lower bound 0.60, pooled recall 0.90, floor 100)
are frozen in `decision.py` (status APPROVED, reference, and a hash of criteria+guard+recall gate that removes the
authority if any threshold changes; 863 GDELT tests pass). No experiment freeze, gate record, provider access or
execution; outcomes authorize nothing. B2 is not complete.
D9: an UNAPPROVED draft config for `claude-haiku-5-5` exists at `config/gdelt/b2t_haiku55_DRAFT_UNAPPROVED.yaml` (all approvals
null, terms attestation false, retention/region/data transmission unresolved); the non-writing dry run shows 12 unmet
prerequisites. The owner then authorised writing and fake-transport testing only of a stdlib HTTPS adapter: written at
`ai/adapters/anthropic.py` (not registered; `ADAPTERS` empty; one call per `suggest`; temperature 1, thinking disabled;
94 offline tests; 957 GDELT tests pass). No real request, no key read, no gate record; build lock `False`. B2 incomplete.
B2-U18 (offline): rule-based annotation validation (`annotation_rules.py`), a separate non-independent AI-only suggestion
schema/store (`ai_only.py`, outside any review folder, imported by no evaluation module), and a read-only `annotate
metric-status` report; with no independent human labels every accuracy metric is unavailable and the decision is
INSUFFICIENT_EVIDENCE. `provenance.verify` now blocks non-human/`ai_only` labels in the working copy. 68 new tests; 1,025
GDELT tests pass. No threshold, guard, lock, gate, key, provider or data change.
S2 (offline sentiment scaffold, `gdelt/sentiment/`): article schema (`s2_article_v1`), a deterministic TEST-ONLY fake scorer
(not exported; refuses non-synthetic input; records rejected unless `allow_test_only`), and daily per-theme aggregation using
the existing availability and session-calendar rules. Missing batches, low coverage, no-news, invalid text and scored-neutral
are distinct (None, never neutral or zero). Dedup policy, coverage threshold (0.75) and early-close list are PROPOSED inputs,
every row says `PROPOSED_NOT_APPROVED`; NOT production-ready. No model, weights, dependency, network, key or label; connected
to no forecaster, optimizer or recommendation. 66 new tests. It approves no provider, transmission, execution, retention change, gate
record, criteria freeze, bridge fix or acquisition; build lock `False`, adapter list empty. Found: under M2 the
current evaluation can only return INSUFFICIENT_EVIDENCE (it decides on the human-only reference scope, about 40
members per series), so a decision on how AI-assisted and independent evidence combine (D12, the B8 amendment) must
precede the first label; the overlap-first rule is procedure only, not enforced in code (D13). A dependency-ordered
plan is in the report. B2 is not complete.
S2.2 (corrective revision after the S2.1 review): schema `s2_article_v2` (whole-second timestamps, `unavailable_reason`, scored
at or after available), features `s2_daily_v2`. `aggregate_daily` now refuses generators/sets, validates the trading calendar
(weekdays, plain dates, no missing day; holidays are an explicit unapproved input) and each interval's exact 15-minute slot grid,
reconciles `series_rows` with the supplied articles (mismatch is unavailable, never "no news"), separates source coverage from
scoring coverage, flags unresolved duplicate/story handling instead of choosing a policy, rejects mixed model_id/revision/code
hash, and the fake scorer refuses to run outside pytest. Still PROPOSED/unapproved and blocked: dedup and story-update policy,
the 0.75 threshold, early-close and holiday calendars, theme-specific calendars (need a forecast target), any scoring-coverage
threshold. 90 sentiment tests. Not production-ready; no model, network, key, label or provider.
S2.3 (contract correction after the S3 trace): slots are now `SlotAccounting` (`gdelt/sentiment/slots.py`) built from the real
manifest counts. Reconciliation is per batch (`rows_captured`) and per theme (series member rows), same-stage counts only; it held
for 192/192 real sample batches where the S2.2 rule held for 0/192. Coverage is as of the cutoff: a batch available after its
interval's cutoff is "delayed" (not covered, counted), its articles enter the interval of their availability, every entering
article needs a reconciled source slot, and delayed theme rows make `no_news` unknown, never true. Non-final slots give
`incomplete_source_accounting`. Features `s2_daily_v3`; 110 sentiment tests, 1135 GDELT tests pass. Late-batch strictness, the
0.75 threshold, dedup, calendars, target, model and acquisition remain unapproved; no producer reads the manifest end to end yet.
S2.5 (read-only adapters, no scoring): `gdelt/sentiment/manifest_adapter.py` (`adapt_manifest`: manifest slot and series rows to
`SlotAccounting`, series chosen by an explicit filter_version, every problem a `Rejection`, stage counts never compared as equal)
and `dayfile_adapter.py` (`adapt_day_file`: committed day file bytes to unscored `CandidateRecord`s, header/hash/availability/versions
checked against the manifest, raw title hash kept apart from the filter hash, no story id or cross-batch status). Both are pure, used
only by tests; nothing is scored and no feature is produced. On the local B2-M sample (read-only): 192/192 slots, 170/170 day files,
26,854 records, 0 rejections, 192/192 reconcile, deterministic, sample tree unchanged. 137 sentiment tests, 1162 GDELT tests pass.
Open: a pre-score-to-`ArticleRecord` step, the cross-batch story pass, a window orchestrator, and all policy decisions (dedup,
calendars, thresholds, late-batch strictness, model); the sample has no complete interval and no late batch.
S2.6 (window orchestrator, no scoring): `gdelt/sentiment/orchestrator.py` (`orchestrate_window`) joins the two adapters, `reconcile_slot`
and the existing cutoff/`origin_for` rules across a window and returns a `WindowReport`: per-batch states (reconciled, delayed,
source_batch_absent, missing/rejected/non-final slot, day file missing/invalid, count mismatch, duplicate id), per-interval accounting
status with the unscored candidate records placed by availability, per-theme `no_news_basis` (verified-empty only when every slot is
reconciled and none delayed), issues, and a preserved-and-counted `RepeatedContent` (no dedup). `features.py` gained small public
helpers (calendar checks, cutoffs, nominal grids, interval locator) reused by both. No scorer, no features, no `ArticleRecord`, no
production wiring. 25 synthetic integration tests; 1187 GDELT tests pass. Dedup, thresholds, near-empty, calendars, late-batch
strictness, the pre-score-to-`ArticleRecord` step and a file-backed day source remain open.
S2.8B (policy record + first corrective phase): `reports/phaseB2S2_8B_policy_decision_record.md` records the owner's 16 decisions
(0.75 primary and 0.50/0.90 sensitivity coverage, near-empty unknown is neither complete nor no-news and explicit near-empty is uncovered
in the primary run, full nominal grid as denominator, retain repeated records with every eligible record as the provisional counting
unit); thresholds, detector parameters and counting choices are PROVISIONAL, and nothing is "applied". Fixed and tested: F5 (invalid
`batch_ts` is its own issue, never out of window), F7 (content-bound canonical digest), F6 (`gdelt/sentiment/policy.py`: immutable
`PolicyState`; `aggregate_daily` refuses while any required policy is unapplied; `SentimentConfig.policy` is now required), F3
(`rows_company_item` reconciled with record flags), F4 (mixed parser versions fail the window). Not done: F1, F2/F2b, coverage and
near-empty plumbing, repeated-content labelling. 1226 GDELT tests pass. Model, polarity validation, target, filter validation,
acquisition, scoring, features and production remain blocked.
S2.8C (F1, owner policy C-min): `WindowInputs.earlier_batches_from` declares the lookback of nominal batches before the window; each is
examined by verified availability; one that becomes available inside the window must be read, validated and reconciled (records then
enter the receiving interval, which is `accounted_with_delayed`; empty themes stay `unverified_empty_delayed`), otherwise the receiving
interval (or every interval when availability cannot be verified, a row is missing, or nothing was declared) is `incomplete_accounting`
with an `earlier_batch_unresolved` issue. The window is never extended. `late_batch_strictness` is `SELECTED_APPLIED_LOOKBACK_UNDECIDED`
(lookback length undecided, caller-supplied). Items not found in the visible evidence are "UNCONFIRMED", not "NOT STATED". 1245 GDELT
tests pass. F2/F2b, vocabulary, coverage/near-empty plumbing and repeated-content labelling remain open.
S2.8D (shared completeness vocabulary, F2/F2b): `gdelt/sentiment/completeness.py` defines four distinct states used by BOTH the orchestrator
and the aggregator through the same transitions: source completeness (complete / complete_with_delayed / final_gaps / incomplete),
interval usability (usable / usable_under_coverage_rule / undecided_policy / unusable_*), per-theme evidence (has_records /
verified_zero_records / unverified_empty / not_evaluated) and result availability (available / available_test_only / unavailable /
blocked_by_policy / scoring_not_performed), plus per-slot evidence with explicit near-empty vs unknown (NULL) vs missing. `no_news` is
true only for verified_zero_records (complete source, every indicator known false, nothing earlier unresolved); a delayed, missing,
absent, near-empty or unknown-indicator case can never give it. `aggregate_daily` now requires `earlier=` (C-min evidence); a
`scorer_approval_and_polarity_validation` policy was added to the required set. C-min unchanged; the lookback length stays undecided
(caller-supplied; no completeness proof beyond it). 1290 GDELT tests pass. Coverage/near-empty plumbing, the unknown-indicator mechanism,
vocabulary names (question 11), scoring, features, evaluation and production remain open or blocked.
S2.8E (coverage and near-empty plumbing, `reports/phaseB2S2_8E_coverage_near_empty_report.md`): `sentiment/coverage_report.py` reports per interval
the full-grid denominator, numerator, ratio, exclusions by one reason each (missing / rejected / non_final / final_absent / delayed_after_cutoff /
near_empty / near_empty_unknown) and the longest missing and uncovered runs, with 0.75 / 0.50 / 0.90 as explicit PROVISIONAL, non-approving
configuration; a verdict reaches usability only via an APPLIED policy status (none is). `sentiment/near_empty.py` is a pure detector (14 days, >= 7
committed same-slot observations, < 10% of the median; provisional) over strictly prior committed observations, `UNKNOWN` without caller-declared
baseline evidence (`baseline_batches_from`), kept apart from the observed manifest flag (`compare_flags`). The repository has no contiguous
baseline, so it is tested with synthetic baselines only. Orchestrator digest is v3. 1324 GDELT tests pass; lookback length, parameter approval and
the aggregator's `_assess_day` rewiring remain open. Next steps, S2.9 and S4 not started.
S2.8F (owner decision register, documentation only, `reports/phaseB2S2_8F_owner_decision_register.md`): 12 decisions (OD-01..12) with status,
options and a labelled recommendation; nothing approved. Open for the owner: lookback length, the 0.75/0.50/0.90 thresholds, the near-empty
parameters, unknown-near-empty mechanism, missing-slot cap, scoring-coverage threshold, vocabulary names, aggregator integration, linking rules,
calendars; research approvals E1-E7 stay blocked. Aggregator finding (from reading, not execution): `_assess_day` counts a processed slot with a
reconciliation problem as covered whereas the shared block excludes it as `rejected`, so only a report-only supplement is safe now; replacing the
numerator needs OD-10. No code changed; 299 sentiment tests re-run and pass; sample tree hash unchanged.
S2.8G (`reports/phaseB2S2_8G_owner_decision_worksheet.md`, documentation only): per-item worksheet for OD-01..12 and E1-E7 (question, status, options,
labelled recommendation, answer needed, what it unlocks and what stays blocked), a dependency map, the prepared-not-applied aggregator coverage plan and a
blank owner response template (blank = unresolved; model/licence/install/network/transmission/acquisition authorised on separate lines). Re-verified this
phase: 8 of 8 required policies still block, 299 sentiment tests pass, sample tree hash unchanged. Nothing approved, no code changed.
S2.8I/S2.8J (OD-10, owner-authorised): `DailyFeatures.coverage_report` carries the shared `CoverageBlock` (report-only, never read by a gate). Per the
owner's OD-10 part 2 decision a processed slot that fails reconciliation is excluded from the aggregator's `n_slots_covered`/`coverage` numerator
(denominator unchanged; a slot with no verdict fails closed); the block and the aggregator now agree on it. No policy applied, no threshold or
parameter changed, 8 of 8 required policies still block. 1346 GDELT tests pass. Report: `reports/phaseB2S2_8J_OD10_part2_unreconciled_slot_coverage.md`.
OD-13 and E3/OD-11 (owner-confirmed, `reports/phaseB2S2_OWNER_APPROVAL_WORKSHEET.md`): `n_slots_near_empty` now excludes unreconciled slots; new
`sentiment/scorer_port.py` (local-scorer interface, fail-closed while the scorer policy is unapplied), `polarity_validation.py` (descriptive stats, no
verdict), `scored_records.py` (candidate -> `ArticleRecord`: theme-flagged text-ok candidates scored, `story_id` = `UNLINKED:<id>`, same-batch
`dup_status` only), `pipeline.py` (blocked-state entry point), and the primary counting unit (every eligible record) with the proposed dedup policy as
a reported sensitivity. No real scorer, labels, features or evaluation exist; 8 of 8 required policies still block. 1392 GDELT tests pass.
Tone baseline (owner-directed): `sentiment/tone_baseline.py` validates GDELT's own document-level tone columns (carried raw on `CandidateRecord.tone_raw`,
bound into the record fingerprint) as valid / missing / invalid with per-theme counts, wired into `pipeline.py` as `tone_baseline`; the derived mean tone
(`tone_derived`, mapping `gdelt_tone_mean_v0`) is owner-approved ONLY as a labelled descriptive document-tone baseline (reported with `n_valid`, `n_records`,
`n_valid_all_zero` and an all-zero-excluded sensitivity) and stays BLOCKED by the 8 unapplied policy gates (`derive_interval_tone` also needs a usable interval).
Owner-approved metadata read (3 anonymous GETs per model, huggingface.co only) done for ProsusAI/finbert (rev 0bc2ac10, card licence CC BY-NC-SA 4.0 claim) and
mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis (rev ae0eab9a, card Apache-2.0 claim); card claims only, no scorer chosen or registered.
Annotation milestone (owner, 2026-10-20): see completion report 11.4 (seed-42 sample drawn, exports in `datasets/derived/sentiment_validation_v1/`; no human labels yet). 1492 GDELT tests pass.
Financial behaviour & user-text sentiment (ADR-043, owner request 2026-10-20): `core/behaviour_findings.py` (observed-fact findings over the ADR-042 features; no new formula, no thresholds, debt/goals `not_included`),
`core/user_text_sentiment.py` (deterministic UNVALIDATED rules baseline; taxonomy sentiment/emotional_tone/topics/preferences; confidence always null; no text -> unavailable), `core/personalized_insight.py` (display-only
composition; the stored risk assessment wins and conflicts are reported), `api/services/personalized_insight_service.py`, `POST /api/profiles/{id}/personalized-insights` (no DB write, no migration, text never stored or logged),
frontend card "Financial behaviour & sentiment" on Financial Health. Blocked: preference confirmation/persistence (needs a migration), a multi-line input (shadcn CLI), any trained model, a user-text validation set. Core/API tests
ran offline (37); the DB-backed backend suite was not run (it needs the hosted test database).
Both transformer candidates deferred by the owner (no download/install; local-only, transmission denied). Added `polarity_validation.draw_validation_sample` /
`annotation_rows` / `validate_polarity_by_theme` (deterministic, overlap-excluding, title-only export; no labels created) and `pipeline.blocking_gates`
(per-stage blockers from the live policy table). 1447 GDELT tests pass; 8 of 8 policies still block. Sample facts: all 26,854 rows numeric, relations hold to ~1e-13, ~1/3 exactly zero
(not evidence of neutrality). It is document-level, not title sentiment or market direction. No model chosen: no torch/transformers, weights or cache exist
locally, and licence/revision metadata needs a network permission not yet given. 1421 GDELT tests pass.

**B2-U11** (`reports/phaseB2U11_methodology_decision_sheet.md`, with `_bridge_hardening_plan`,
`_statistical_reconciliation`, `_execution_report`, 2026-10-19): documentation and verification only; no code or data
changed (794 GDELT tests pass). The U10 capture-recall figures were reproduced independently from public numbers
(full best case 0.9328; independent subset 0.7351 reweighted, 0.3569 under parent weights, the latter a weight-basis
artefact). Withdrawn: the U10 content-derived label-basis recommendation. Unresolved: what "pooled capture recall"
and "bootstrap polarity" mean. F1-F4 bridge fixes are planned, not made. Eleven decisions are on the sheet; none was
made. B2 is not complete.

**B2-U10** (`reports/phaseB2U10_readiness_report.md`, with `_retention_design`, `_gate_audit`, `_completion_plan`,
2026-10-19): documentation and verification only; no code or data changed. Baseline re-verified (HEAD `71b363f`,
794 GDELT tests pass, lock `False`, no adapter, key unopened). Audit found three bridge verification gaps (review
chain not read, manifest chain heads not compared, silent legacy fallback) and an inconsistent capture-recall
number in the U8 independent-reference scope; neither fixed (needs authorisation). Corrects U9: capture recall 0.90
is reachable in the full sample only in a demanding best case (0.933), not impossible. Retention payload-file design
proposed, not built. Gates A to D: all missing records (no failed checks). Fourteen decisions listed; none made.
B2 is not complete.

**B2-U9** (`reports/phaseB2U9_label_bridge_and_methodology_readiness.md`, 2026-10-19): the U8 "incompatible
formats" blocker is resolved offline (794 GDELT tests pass). The B2-T and legacy suggestion formats are
column-compatible; `ai_bridge.py` supplies a hash-chain-verified B2-T suggestion set to the unchanged legacy
validator (optional argument; both sources present is refused) and turns verified reviews into merge labels,
refusing `human_uncertain` / `human_insufficient_evidence` (basis mapping is a decision). Audit: overlap
membership is a pre-registered 20% hash rule that reproduces exactly (312/312); realised per-cell counts need the
sealed key (unopened); the independent subset has about 40 members per series, below the 100 floor; capture
recall at 0.90 is arithmetically unmeetable. Raw responses stay non-expirable; a payload-file design is proposed,
not built. Nothing was run, enabled or approved; B2 is not complete.

**B2-U8** (`reports/phaseB2U8_end_to_end_evaluation_wiring_report.md`, 2026-10-19): offline wiring
implemented and tested (765 GDELT tests pass). `ai_origin.py` verifies the AI-origin export against the provenance
bridge; freeze and evaluation refuse unverifiable or incomplete AI origin before the sealed key, and the export's
hashes are in the evaluation fingerprint. Results have an exploratory scope (all labels, no decision) and a
`human_only` reference scope (the only one with a decision; BLOCKED below the 100-member floor; never
authoritative, authorizes nothing). `protocol_partition` describes the proposed M2 groups (real data: 312
reference, 0 blind, 1,181 eligible) without choosing it. **Blocked:** no approved path carries B2-T review labels
into the working copy (the validator wants a legacy `ai_suggestions_A.csv`), so AI-assisted labels cannot be
frozen end to end. Nothing was run, enabled or approved; B2 is not complete.

**B2-U7** (`reports/phaseB2U7_offline_safeguards_report.md`, 2026-10-19): offline safeguards implemented
and tested (690 tests pass). A fail-closed `protocol.provider_exclusion` (unset blocks; hashed into Gates A and
D) keeps overlap and blind items from any provider; `provenance.py` verifies the working copy, overlap manifest
and merge history; `decision.py` gives PASS, FAIL, INSUFFICIENT_EVIDENCE or INVALID_EVALUATION against the
still-PROPOSED criteria (never authoritative); a freeze is bound to an evaluation fingerprint and a stale one
is refused. The bootstrap stays `random.Random(42)`. Nothing was run, enabled or approved; B2 is not complete.

**B2-U6** (addendum to `reports/phaseB2_completion_decision_document.md`): five decisions recorded as
recommendations, **none approved**. Audit findings: the AI pipeline cannot guarantee overlap items are
never sent; evaluation lacks per-cell Wilson, unique-story precision and enforcement of the 100-member
floor; the bootstrap uses `random.Random(42)`, not numpy `default_rng(42)` as B2-I says. No code changed.

**B2 is paused (deferred), not complete** (`reports/phaseB2_pause_and_research_handoff.md`,
2026-10-19). Unmet: the labelled review (0 of 1,493), freeze and evaluation, the filter
decision, the window-wide driver, full-window ingestion and the B2 ADR.

- **Next phase in plan order:** B3 (sentiment classifier). It is blocked and is not started.
  Unvalidated GDELT sentiment is not a model input.
- **Market-only B4 stage:** specified, not approved and not run. The plan makes B4 depend on
  B3, so running it first needs your approval to re-sequence. It also needs a data route (the
  market data is only in the hosted table), a target and holdout decision, and a script.
- **Behaviour features:** no historical coverage, so no feature-addition experiment can run.
- **Kept while paused:** the sample, labels, backups and approval records. The GDELT network
  and development-sample switches are still on (locking them is your decision).

**B2 master completion run** (`reports/phaseB2_remaining_work_and_completion_report.md`,
2026-10-16): B2 is **partially complete**; it is not closed.

- **Fixed:** a validator gap. An AI-based label now needs a valid suggestion for
  its own item, not just an existing file.
- **Built:** `annotate freeze` and `annotate evaluate` (the sealed key opens only
  after a label freeze), plus pure estimators. Tested on synthetic data only.
- **Tests:** 262 pass in `tests/backend/data/gdelt/`.
- **State:** 0 of 1,493 items labelled; no AI suggestion; the sealed key was not
  opened; the GDELT switches are still on (unchanged, awaiting your approval to
  lock them).
- **Blocked on you:** labelling the 312 overlap items, and the B2-T decisions
  (methodology, provider, data handling, execution). Full acquisition and its
  driver are not approved.
- **Not started:** B3 and the ADR.

**Full acquisition is not approved.** B3 onward need explicit approval. No real
blockchain integration is approved: the only ledger is the local hash-chain
prototype of ADR-047, which is not a blockchain.

## Overall Project Status

All planned phases through Phase 36 are implemented, tested, and
documented. The full backend regression suite passes in isolation (see
"Current Test Status"). The frontend type-checks, builds, and lints
cleanly. The system reaches all four terminal analysis states (approved,
approved/savings-first, rejected, pending_information) through real,
unmodified pipeline execution, verified live against real demo customers.
Verified at source level only (no browser tool exists here): the frontend
journeys.

## Completed Phases

Phase 0 (foundation) through Phase 25 (final UX/viva polish), each with
its own numbered report in `reports/`, plus four additional,
non-numbered-in-filename phases completed after Phase 25 and before
Phase 28: the Demo Data phase (`reports/demo_data_completion_report.md`),
the Live Analysis Flow phase (`reports/live_analysis_flow_fix_report.md`),
the Post-Login Profile Flow fix
(`reports/post_login_profile_flow_report.md`), Phase 28 itself
(`reports/phase28_financial_input_savings_first_report.md`), Phase 29
(`reports/phase29_final_integration_report.md`), Phase 30
(`reports/phase30_analytics_visualization_report.md`), and Phase 31
(`reports/phase31_final_demo_readiness_report.md`), Phase 32
(`reports/phase32_household_foundation_report.md`), Phase 33
(`reports/phase33_household_financial_data_report.md`), Phase 34
(`reports/phase34_household_financial_aggregation_report.md`), Phase 35
(`reports/phase35_household_financial_persistence_report.md`), and Phase 36
(`reports/phase36_household_goals_report.md`). See `TASKS.md` for the itemized
checklist.

## Current Architecture

Matches `docs/ARCHITECTURE.md` in full as of this writing — no known
drift between that document and source at the time this memory entry was
written.

## Current Backend State

FastAPI app (`backend/wealthpilot/api/main.py`) with routers for
profiles (including Phase 28's financial-inputs endpoints and the
Live-Analysis-Flow-phase name-lookup endpoint), analysis, scenarios, qa,
health. `analysis_service.py::_build_graph_dependencies` (Phase 28) wires
real financial inputs into every analysis run. `core/compliance.py` has
the Phase 28 savings-first weight exemption. `agents/nodes.py`'s
`savings_first_node` has the Phase 28 `sufficient is None` fix, and
`load_portfolio_returns` is public (renamed from `_load_portfolio_returns`).
Phase 29 corrections in `analysis_service.py`: the goal Monte Carlo's
historical-return series is compounded to the goal's contribution period
frequency (`_compound_to_period_returns` — before this, daily returns were
applied once per month and every goal showed 0.0%; ADR-027);
`ANALYSIS_PIPELINE_VERSION` ("2") is part of the analysis cache key so a
computation fix invalidates stale cached results; the `savings_first` SSE
summary says "insufficient" only when sufficiency is known to be false and
"could not be confirmed" when it is unknown.

Phase 32 backend (household foundation): models `Household`/`HouseholdMember`
(`db/models.py`), schemas (`api/schemas.py` — request models forbid unknown
fields so nothing financial can be sent), `api/routers/households.py`,
`api/services/household_service.py` (all rules and authorization),
`api/dependencies.py::get_acting_customer_id`, and new RFC 7807 errors
(401 identity required, 403 access denied, 404 household / member not found,
409 conflict). Only the household's primary member can add or remove members;
a member can view; the primary cannot be removed; nothing in the household code
reads or writes any financial table, and `POST /api/analysis` is untouched.

Phase 33 backend (household financial data): models `HouseholdIncome`/
`HouseholdExpense`/`HouseholdAsset`/`HouseholdLiability` (`db/models.py`), 12
new schemas (`api/schemas.py`, every request model `extra="forbid"`),
`api/routers/household_finances.py` (16 routes),
`api/services/household_finance_service.py` (one table-driven core plus
explicit per-resource functions), and one new error
(`HouseholdRecordNotFoundError`, 404).

Phase 34 backend (household aggregation): `core/household_finance.py` — a pure,
DB-free, `Decimal` engine holding ALL household arithmetic (monthly
normalization, one-time separation, active-only aggregation, cash flow, net
position and an emergency fund reusing `core/goals.py`'s 6-month constant and
comparison) — plus `api/services/household_summary_service.py` (loads four
scoped queries, maps engine output to the schema, no arithmetic of its own),
`api/routers/household_summary.py` (one read-only GET) and nine new response
schemas. Nothing derived is persisted; a summary is recomputed per request. No
migration, table or column was added, and `analysis_service.py`, `core/goals.py`
and every model remain untouched. `household_service.py` gained
`require_member`/`require_primary_member` helpers, reusing the Phase 32
membership checks unchanged. **The service layer contains no arithmetic**: it
lists, creates, merges partial updates and deletes records, and returns them as
stored. Nothing in `core/`, `agents/`, `analysis_service.py` or any ML code was
touched.

## Current Frontend State

Public-page colors (2026-10-02): Home, About and their shared navbar/footer use
exactly the dashboard's semantic tokens (neutral `primary`); the former
`--brand` token and the public-only `.public-theme` override were both removed,
so the app has one color system (`docs/DESIGN.md` section 32). New public pages
use the same tokens with no override.

About This Project page (2026-10-02): public `/about` (`pages/about-page.tsx`,
`components/about/`, `docs/DESIGN.md` section 31) — static project explanation
built only from documented results (metrics.json, phase reports); linked from the
Home navbar/footer and a "Project" group in the app sidebar.

Plain-language dashboard (2026-10-01, frontend presentation only):
`lib/terminology.ts` maps raw API values to plain labels (tickers, strategies,
capacity bands, metrics, statuses, compliance rules, analysis steps); raw
values, method names, versions and artifact paths are kept in collapsed
`TechnicalDetails` sections, with `HelpTip` tooltips for terms (`docs/DESIGN.md`
section 30). API values and numbers are unchanged. Also fixed: Base UI
`SelectValue` showed raw values (`default`/`mvo`, `unspecified`) — the
Scenario Simulator and Create Profile selects now pass `items`; the create-user
capacity labels now come from the shared mapping (€, was `$`); and a
pre-existing 768px horizontal overflow (the header's page title could not
shrink, widening the content column) is fixed with `min-w-0` on `SidebarInset`
and the header title; the household section's tab row now scrolls sideways at
phone width instead of clipping its last tabs.

Demo completeness audit (2026-10-01, `docs/demo_runbook.md` "Demo Completeness
Audit"): Financial Health now also shows the profile's own stored income,
essential expenses and liquid savings (display only), states that individual
debts/cash flow/net position are not recorded, and points household members to
the separate household summary. The spending pattern stays unavailable for all
demo personas (ADR-010; no Kaggle/FAR-Trans linkage). Resolved by the
2026-10-04 demo reset (ADR-040): the out-of-seed "TEST" household and the
duplicate customer were removed; see the demo-data section below for current
ids.

Public Home page (2026-10-01): `/` is a public, static landing page
(`pages/home-page.tsx`, `components/home/`, `docs/DESIGN.md` section 29) —
outside `ProtectedRoute` and `AppShell`, no API call. The Dashboard moved from
`/` to `/dashboard` (sidebar item, sidebar logo, 404 link, onboarding
"Continue to Dashboard", error-boundary reload, and the login default redirect
all updated). Home's demo buttons open `/login?demo=individual|family`, which
only focuses the matching existing demo button; authentication is unchanged.
(The accent token `--brand` added then was later removed; public pages now use the dashboard's neutral tokens.)

Ten protected pages plus Login/Create-User/two onboarding pages, all
reading a single `profileId` source of truth. The Customer Profile page
now includes a Financial Inputs card (Phase 28) alongside the existing
profile-field and goals display. No customer-switching UI exists
anywhere (removed in the post-login-flow fix). Phase 29: the
Recommendation page renders the API's per-rule compliance results via
`components/shell/compliance-breakdown.tsx` (a rejected analysis now shows
which rule triggered and the engine's own reason, not only a generic
"blocked" sentence); Why This Recommendation states why no explanation
exists for a rejected/pending result; the Dashboard's "Next step" text for
a savings-first result says a savings-first recommendation is ready and no
investment allocation is active.

Phase 30 visualization layer: `components/charts/` (Recharts, display-only —
`docs/DESIGN.md` section 16, ADR-029) holds `RiskProbabilityChart`
(Risk Assessment), `EmergencyFundChart` (Financial Health; Portfolio and
Dashboard on a savings-first result), `GoalTargetChart` (Goals),
`PortfolioAllocationChart` (Portfolio, Recommendation, Dashboard — approved
only; replaced the old `components/portfolio/allocation-chart.tsx`),
`ScenarioComparisonChart` (Scenario Simulator) and `AgentPipeline` (Agent
Activity; draws only received SSE events). Every chart plots an API value
unchanged, shows an unavailable state for `null` (never zero), and sits
beside a table/text with the same values. The Goals page shows Monte Carlo
probabilities to one decimal and a "Contribution exceeds the calculated
requirement." note when the backend's `contribution_gap` is negative. The
Portfolio page shows the Phase 29 compliance breakdown for a rejected
analysis. Not built: a portfolio risk/return or efficient-frontier chart
(the API exposes no frontier data).

Phase 31 frontend polish (targeted, no redesign): the Why This Recommendation
page separates "Explanation (wording only)" — labelled either AI-written
wording checked against the computed numbers, or a template restatement (its
fallback alert now correctly names an unavailable/out-of-quota service, not
only failed validation) — from "Deterministic factors" computed by the
backend; the Customer Profile page has a Questionnaire card linking to
`/onboarding/questionnaire` (the questionnaire's Back returns to the page
that linked to it), and every empty Financial Inputs field shows "Not
provided" (never 0); the Dashboard says "N goal(s) recorded — not yet
evaluated" instead of "No goals recorded" when analysis has not reached goals;
login/create-user/onboarding text uses em dashes; the scenario chart's
sub-titles are `<h2>` (no skipped heading level); the obsolete unused
`components/shell/page-placeholder.tsx` was removed and `App.tsx`'s stale
"Phase 16 placeholders" docstring corrected.

Phase 32 frontend: a Household card on the Customer Profile page
(`components/profile/household-card.tsx`, `hooks/use-household.ts`, household
methods in `lib/api-client.ts`) — "No household created yet." with a create
form, or the household name / your role / relationship / member count, and
behind "View Household" a member table (with a "You" badge) and, for the primary
member only, a labelled prototype add-member form (existing profile ID +
relationship + role) and two-step Remove. No arithmetic, no implicit creation,
and no customer switching.

Phase 33 frontend: "View Household" now opens a `Tabs` control whose first tab
is the Phase 32 Members table, followed by Income, Expenses, Assets and
Liabilities — all four rendered by the config-driven
`components/profile/household-finance-section.tsx` over
`hooks/use-household-finances.ts` and 16 new `lib/api-client.ts` methods. Each
tab lists the household's stored records exactly as returned, with add/edit
dialogs and two-step delete for the primary member and read-only tables for
everyone else. **There is no arithmetic in it at all** — no total, net worth,
savings, ratio or coverage figure, and each tab states in muted text what is
not being calculated; a `null` renders as "Not provided" (a liability's absent
monthly payment) while a stored `0` renders as a formatted zero. Validation is
form-shape only (required / numeric / sign), mirroring the API's own rules.

Phase 34 frontend: the expanded household card now renders
`components/profile/household-financial-summary.tsx` above those tabs, over
`hooks/use-household-summary.ts` — the recurring monthly view, one-time records,
an assets/liabilities table with net position, the emergency-fund position, and
neutral Available/Unavailable badges per area. It is display-only and contains
**no arithmetic at all**; `null` renders as "Not provided" and a stored `0` as a
formatted zero. The Phase 33 record mutations also invalidate the summary query
so an edited record yields a freshly recomputed summary from the server.

Plain-language explanations (ADR-037, not a phase): Why This Recommendation
opens on a **Simple** view (`components/explanation/plain-language-explanation.tsx`)
built only from the deterministic analysis fields, so it works for every
analysis including cached ones. The existing AI/fallback wording and
deterministic-factors card are the **Detailed** view.

**Backend part NOT applied (as of 2026-09-30).** The Gemini prompt wording,
the stricter validator (ticker attribution, derived counts, grouped amounts
such as "30,000") and the plainer fallback are prepared outside the repository.
None of them is in `agents/explanation.py`, and
`tests/backend/agents/test_explanation_readability.py` does not exist yet.

The required pre-patch full-suite run was interrupted on 2026-09-27 at 51%,
with no exit code recorded. The only failure it had printed,
`test_setup_family_is_idempotent`, had no traceback, so it is unclassified; it
passed in isolation on 2026-09-30.

Applying and validating the backend part is pending an explicit instruction.
Its known gap is real: the current validator reads "30,000" as 0.

## Current ML State

Risk (`models/risk/`), behaviour (`models/behaviour/`), expense
(`models/expense/`), market (`models/market/`) artifacts are all trained
and loaded at startup. No model was retrained, modified, or re-saved
since Phase 19's final evaluation — confirmed by `find models -newer
<baseline>` returning empty at the end of every subsequent phase,
including Phase 28.

## Current Database State

Alembic head: `f7a2d4b6c810` (`add protected records and audit ledger`, ADR-047; applied to the
isolated test database `neondb_test` only -- `neondb` still needs `alembic upgrade head` from the
owner), revising `e5b1c7d93a20` (`add monthly financial records`, Research
Enhancement Track B1), revising `c3e8f2a9d154` (`add household goals`, Phase 36),
revising
`a7c41e9b6f30` (Phase 35's `add household financial metadata columns`), revising
`d2be70d8b07f` (`add household financial data tables`, Phase 33),
revising `f59ab6395383` (Phase 32's `add households and household_members`),
which revises `8ef3f9affbe5` (Phase 28's `add financial_inputs`). Tables:
`customers`, `customer_risk_snapshots`, `financial_goals`,
`questionnaire_answers`, `financial_inputs`, `transactions`, `portfolios`,
`market_data`, `recommendations`, `agent_logs`, `risk_assessments`,
`analysis_runs`, `households`, `household_members`, `household_incomes`,
`household_expenses`, `household_assets`, `household_liabilities`,
`household_goals`, `monthly_financial_records` (B1: one row per customer per
calendar month, every amount nullable, unique `(customer_id, period_month)`,
CHECK constraints for sign, first-of-month, basis and at-least-one-amount).
Applied to both
`DATABASE_URL` and `TEST_DATABASE_URL`. `household_members` enforces, in the
database, one household per customer (`UNIQUE(customer_id)`), one primary per
household (partial unique index), primary implies `self`, `self` never a
dependent, `is_dependent` = (`role` = 'dependent'), and the controlled
relationship/role vocabularies; both foreign keys cascade. The four Phase 33
financial tables each hang off `household_id` (indexed, cascading) and carry
**no `customer_id`**; CHECK constraints enforce the controlled vocabularies and
the sign rules (income/expense `amount > 0`; `current_value >= 0`;
`outstanding_amount >= 0`; `monthly_payment IS NULL OR monthly_payment >= 0`),
with `monthly_payment` nullable and `is_essential` defaultless on purpose. No
column, view or query aggregates any of it — Phase 34's summary is derived in
Python, per request, and stored nowhere, so **Phase 34 added no migration**.
Phase 35 added seven optional metadata columns to those four tables (all
nullable, no default; `interest_rate` `Numeric(6, 4)` with a non-negative
CHECK). Phase 36 added `household_goals` (facts only, no `customer_id`,
`target_amount > 0`, nullable `current_savings`, controlled `goal_type`).
`alembic check` reports no drift on either database. The dev database holds no
household rows of any kind: every live check ran inside a transaction that was
rolled back, and row counts were confirmed unchanged afterwards.

## Current API State

`GET /api/questionnaire`, `POST /api/profiles`,
`GET /api/profiles/{id}`, `GET /api/profiles/lookup`,
`POST`/`GET /api/profiles/{id}/questionnaire`,
`POST /api/profiles/{id}/goals`,
`GET`/`PUT /api/profiles/{id}/financial-inputs`,
`GET /api/profiles/{id}/monthly-financial-records`,
`GET`/`PUT`/`DELETE /api/profiles/{id}/monthly-financial-records/{YYYY-MM}`,
`GET /api/profiles/{id}/behaviour-features` (Research Enhancement Track B1),
`POST /api/analysis`, `GET /api/analysis/{id}`,
`GET /api/analysis/stream`, `POST /api/scenarios/compare`,
`POST /api/qa`, `GET /api/health`, and (Phase 32, all requiring an
`X-Customer-Id` header, none touching finances) `POST /api/households`,
`GET /api/households/{id}`, `GET`/`POST /api/households/{id}/members`,
`DELETE /api/households/{id}/members/{member_id}`,
`GET /api/profiles/{id}/household`, and (Phase 33, same header and
authorization) `GET`/`POST /api/households/{id}/income|expenses|assets|
liabilities` plus `PUT`/`DELETE` on each `/{record_id}`, and (Phase 34)
`GET /api/households/{id}/financial-summary`, and (Phase 36)
`GET`/`POST /api/households/{id}/goals` plus `GET`/`PUT`/`DELETE` on
`/goals/{goal_id}` — 29 paths in all. There is no
household deletion route, no mutation route for calculations, and deliberately
no totals, net-worth, savings or debt-ratio route; tests pin the household route
inventory exactly and assert that `financial-summary` is the ONLY aggregate
path. `frontend/src/types/api.ts` was regenerated in Phase 36 (+313 lines, -0)
directly from `app.openapi()`, and a second generation is byte-identical.

## Current Agent State

LangGraph topology unchanged in shape since Phase 11; two Phase 28
corrections to node/rule *behavior* (not topology) are documented in
`docs/DECISIONS.md` ADR-018. AutoGen debate and Gemini explanation are
both unchanged in mechanism; Gemini explanation is now genuinely
exercised live (previously never reached for any customer pre-Phase-28).

## Current AI/LLM State

`GEMINI_MODEL`/`GEMINI_API_KEY`/`GEMINI_PROJECT_NUMBER` configured via
`.env`. Live Gemini calls have been observed falling back to the
templated, non-generative explanation under quota pressure during
Phase 28's own live verification — the pre-existing, correct fallback
behavior, not a defect.

## Current Authentication State

Prototype auth unchanged in mechanism since the post-login-flow fix: one
supported demo credential, automatic customer resolution on every
successful login (regular or demo), no manual profile-id entry anywhere.

## Current Demo State

Canonical personas (this environment's ids — regenerate via
`python backend/scripts/seed_demo_data.py verify` for a fresh
environment's actual ids):

**Reset 2026-10-06 (ADR-041):** the demo data was replaced by one meaningful
canonical dataset in rupees. The four old demo customers and the old family
household (and every row that belonged to them, exact counts verified) were
deleted, and the four personas and the family were re-created through the real
public API under new ids. Everything below is the freshly computed result, not
illustrative. Earlier resets (ADR-040) and their ids are history only.

| Persona | id (this env) | Inputs (annual income; essential spending; savings) | Actual status (analysis id) |
|---|---|---|---|
| WealthPilot Demo — Complete | 29110 | ₹14,40,000; ₹45,000/mo; ₹3,60,000 | `approved`, Aggressive, MVO portfolio QQQ 55%/GLD 45%, PASS; emergency target ₹2,70,000 met; goals: Home Down Payment Feasible, Child Higher Education Feasible, Retirement Corpus At Risk (214) |
| WealthPilot Demo — Savings | 29111 | ₹8,40,000; ₹38,000/mo; ₹90,000 | `approved` with `recommendation.status = savings_first`, Balanced, no weights, PASS; target ₹2,28,000, short ₹1,38,000; goals: Emergency Fund Feasible, Home Down Payment At Risk (215) |
| WealthPilot Demo — Compliance | 29112 | ₹13,20,000; spending and savings not provided | `rejected`, Conservative, one triggered rule `emergency_fund_savings_first` (fail-closed: unknown is never sufficient); goals still computed (216) |
| WealthPilot Demo Customer | 29113 | ₹9,60,000; ₹35,000/mo; ₹2,40,000 | `pending_information`: no trading history, so no risk label; questionnaire answered for questions 1–15 only (217) |

**Why Compliance is built this way:** of the five existing compliance rules,
only `emergency_fund_savings_first` can be triggered by a customer input
(the other four check the optimizer's own weights). It rejects only when the
emergency-fund position is unknown, so persona C omits its essential spending
and easy-access savings. No rule was changed.

**Family demo (ADR-036):** household **"WealthPilot Demo Family"** (id 9 in
this environment), seeded by `seed_demo_data.py setup-family` through the
public household API — primary "WealthPilot Demo — Savings" (29111,
self/primary), spouse "WealthPilot Demo — Compliance" (29112, spouse/member),
5 income, 10 expense, 6 asset, 2 liability and 5 goal records. Summary:
recurring income ₹1,60,000, recurring expenses ₹99,200, cash flow ₹60,800,
net position ₹18,20,000, emergency fund required ₹5,16,000, status
insufficient. The individual data of the personas is unchanged by it. Details:
`reports/family_demo_report.md` (historical).

"Use Individual Demo" (formerly "Use Demo Account") and a regular Sign In
resolve to "WealthPilot Demo — Complete" whenever it is seeded, in every browser — Phase 31 (ADR-030)
reordered `resolveDemoCustomer` so the seeded persona wins over a remembered
blank fallback id (before this, a browser that had once landed on the blank
"WealthPilot Demo Customer" stayed there). Only when "Complete" is not seeded
does it fall back to a remembered demo id or the from-scratch canonical
customer. "Use Family Demo" resolves the family's primary, 29111, and opens
its Household section (ADR-036) — so 29111's own pages are now reachable
in-app; 29112 and 29113 still are not (no switcher, by design) and their
individual results are shown via `/docs` — see `docs/final_demo_script.md`
sections 15–17.

**Demo dataset (ADR-038, not a phase):** `demo_data/` is the single source
of the demo population, validated by
`python backend/scripts/validate_demo_data.py`.

- **Contents:** personas A–D (29110, 29111, 29112, 29113 here), family
  `WPDEMO-FAM` (household 9), five strategy scenarios, and expected
  contract-level states. Version 1.0.0; the manifest records counts, hashes
  and the raw-data guard. Persona A has 3 goals, B/C/D have 2, and the family
  has 5 (ADR-041); the manifest was regenerated accordingly. The validator now
  also checks input plausibility (see `demo_data/README.md` section 8).
- **Seeding:** `seed_demo_data.py` loads it. `setup` now also seeds persona D
  (find-or-create; `reset` never deletes it). Every mode takes `--in-process`.
  `verify` compares all stored values and the expected states.
- **No duplicate present.** The ADR-030 duplicate (old id 29101) and the
  stray "TEST" household were removed in the 2026-10-04 reset (ADR-040), and every demo row was replaced in the 2026-10-06 reset (ADR-041); a
  direct `GROUP BY name HAVING count(*) > 1` check over demo-named customers
  confirms none has been recreated, and re-running `setup`/`setup-family`
  a second time creates zero rows.
- Details: `demo_data/README.md`, `reports/demo_dataset_catalog.md` §10.

Final demo material: `docs/final_demo_script.md` (click-by-click, verified
numbers), `docs/final_viva_talking_points.md` (40 answers),
`docs/demo_runbook.md` (longer narrative). `reports/final_viva_facts.md` is a
Phase 19 snapshot with a superseded note — do not quote its "no customer has
reached approved" or "goal engine not wired" claims.

## Current Customer Association

`CustomerProvider`'s `profileId` (`wealthpilot-profile-id` in
`localStorage`) is the single source every protected page reads, set only
by `login-form.tsx::completeLogin`, `create-user-page.tsx::handleContinue`,
and cleared by `header.tsx`'s sign-out. Household membership (Phase 32) does
not change this: the authenticated customer stays the active user, and a
household route reads that same `profileId`, sent as `X-Customer-Id`. The
header is an asserted identity (no server session), so household authorization
stops accidental/URL-edited cross-household access, not a malicious client.

## Current Dataset State

`datasets/raw/FAR-Trans/` and `datasets/raw/kaggle/` unchanged since
ingestion; immutable per `docs/DECISIONS.md` ADR-023. Their SHA-256 hashes are
recorded in `demo_data/manifest.json` (`training_data_guard`), which
`validate_demo_data.py` checks. The synthetic demo dataset lives separately in
`demo_data/` and is never training data (ADR-038).

**Synthetic ML training dataset (ADR-039, not a phase)** in `datasets/generated/`.
The CSVs are git-ignored and regenerate byte-identically with
`python scripts/generate_wealthpilot_synthetic_dataset.py` (seed 42).

- **Size:** 100,000 customers × 76 columns, 2,642,361 transactions and 325,290
  goals.
- **Format copies:** the same population is also written in the FAR-Trans and
  Kaggle formats, which the existing loaders read unchanged.
- **Targets:**
  - `risk_label` from hidden variables;
  - `expense_segment` and `behavior_anomaly` as planted ground truth;
  - `goal_feasibility` from the production goal engine at 500 paths.
- **Validation:** `scripts/validate_synthetic_training_dataset.py`.
- **Not wired into any training script.** Using it to train a production model
  is a separate decision.
- Details: `datasets/generated/README.md`.

## Current Model Artifacts

Unchanged since Phase 19 (risk/behaviour/expense) and their respective
training phases (market/portfolio) — see "Current ML State" above.

## Sentiment approval gate checked (2026-10-26): CLOSED

`reports/sentiment_model_approval_record.md` holds the decision matrix R1-R14 (dependency pins, compatibility test, FinBERT licence and revision, RoBERTa candidate, Financial PhraseBank, annotation protocol, 300-statement target, metric targets, coverage, calibration policy, activation criteria): **all UNRESOLVED** (intensity regression stays deferred, APPROVED). The brief to start the isolated compatibility phase supplied no decisions, so the stop rule applied: nothing installed, no environment created, no download, no code or configuration change; the rules baseline stays active with `SENTIMENT_MODEL_ENABLED=false`. Next approval required: R1-R5 before any install; R6 / R7 with exact commit hashes before any weights.

## Sentiment research phase: approval package prepared (2026-10-27)

Documentation only. The approval package is the addendum of `reports/sentiment_transformer_dependency_request.md` (dependency pins with evidence labels, security requirements and their enforcement status, candidate and dataset registers, evaluation plan, a 16-item checklist: all UNRESOLVED
except "intensity regression stays deferred") (section G: the proposed independent 300-statement held-out set with its numbers) plus the addendum of `docs/USER_TEXT_VALIDATION_DECISION_SHEET.md` (the annotation protocol without numbers: that packet's guard forbids numeric thresholds). Nothing was installed, downloaded, collected, trained or changed in code; the rules baseline `user_text_rules_v1` is active
and `SENTIMENT_MODEL_ENABLED=false`. Known gaps recorded for after approval: the exact model revision is not yet enforced in the metadata or the training script; the rubric file was deliberately not edited (its hash is in the pilot pack's manifest).

## Trained sentiment model seam (ADR-052, 2026-10-26)

**No Transformer model exists, is installed or is validated.** `torch`, `transformers`, `tokenizers`, `safetensors` are outside the approved stack and not installed; no weights, no approved labelled dataset. Built and tested without them: `core/sentiment_model.py` (verified-artifact loader, calibration, fixed reason codes, CPU / time / token limits, validated-only primary), the model policy in `analyse_user_text`
(own-clauses input, safeguard precedence, disagreement exposed, visible rules fallback), extended API (`class_probabilities`, `confidence_calibration_status`, `sentiment_intensity`, `rules_baseline`, `disagreement`, `fallback_reason`; `GET /api/sentiment-model/status`), the page states, and `training/sentiment/`
(manifest gate, deterministic leak-free split, calibration, evaluation, artifact writer). Config `SENTIMENT_MODEL_*` defaults to off; the rules baseline stays the method. Regression / intensity stays disabled (null). Waiting on the owner: `reports/sentiment_transformer_dependency_request.md`.

## Full-pipeline household, honest debt and spending states (ADR-051, 2026-10-24)

`setup` now also builds "WealthPilot Demo — Full Pipeline Household" (`WPDEMO-HHE`): E primary, the new light partner persona `WPDEMO-F` (pending information, like D) as spouse, with income, expenses (EMIs as `debt_payment`),
assets, liabilities (car and education loan with EMIs, a credit card at a stated 0) and goals; the application computes recurring income 155,000, spending 96,000, cash flow 59,000, net position 1,720,000, emergency fund sufficient.
Manifest: 6 personas, 2 households, 49 files. Seed: `--household family|pipeline` on the `*-family` modes; `verify` / `reset` cover both. Financial Health: "Debt & Commitments" says an individual has no recorded loans
(unsupported by design, ADR-033) and points a household member to the household; "Spending and expenses" shows the backend's spending findings from the reported months (the expense-persona model stays unavailable for FAR-Trans
customers, ADR-010). A saved month now also refreshes the `personalized-insight` query. The local SQLite launcher keeps the partial index (`uq_household_members_one_primary`), so two-member households work locally.
Only "Use Full Pipeline Demo" opens E; "Sign In" / "Use Individual Demo" open persona A (no months, no household, by design).

## Sentiment interpretation pipeline (ADR-050, 2026-10-23)

`core/user_text_sentiment.py` is now a multi-stage, deterministic RULES BASELINE `user_text_rules_v1` (still `UNVALIDATED_BASELINE`, `confidence` null, no trained model, no LLM, no new dependency): validation ->
language / quality -> financial relevance -> clause analysis (quotes, other people, past feelings, negation) -> sentiment + emotional tone -> topics -> explicit preferences -> abstention
(`insufficient_evidence`, `abstain_reason`, `interpretation_state` valid / weak / abstained / unavailable). Emotional tone is not risk tolerance; every preference is `unconfirmed`; the stored risk assessment
stays authoritative (`risk_profile.remains_authoritative`) and a disagreement is a structured conflict. Optional model seam `SentimentModel` / `get_sentiment_model()` (returns None; failure -> rules,
`fallback_used`). Same route and nested object, fields added, `method` is now `rules_baseline | trained_model | hybrid | unavailable`, composer `personalized_insight_v2`. Frontend page updated (no new
dependency; types regenerated). Open owner decisions are listed in ADR-050. The annotation rubric / pilot pack were deliberately not edited (production taxonomy is a pinned superset).

## Full-pipeline demo persona (ADR-049, 2026-10-23)

`WPDEMO-E` "WealthPilot Demo — Full Pipeline": FAR-Trans customer `F7D82BE85FF183D757BA` (genuine `Balanced`, 52 months), twelve reported months in `demo_data/monthly_records/`,
three goals, sufficient emergency fund. Seeded by `seed_demo_data.py setup`; sign in with "Use Full Pipeline Demo". Real result on a local database with market data loaded:
Balanced (0.663), equal-weight recommendation approved, compliance PASS (5 rules), goals Feasible / Feasible / At Risk. `scripts/load_local_market_data.py` fills `market_data` locally
(without it even persona A is rejected: compliance fails closed on missing weights). Also fixed: the Behaviour & Sentiment "stored risk assessment" now falls back to the latest analysis
run (the pipeline never writes `risk_assessments`). Manifest: 5 personas, 36 files. The aggregate CSV still covers A-D. The written Gemini explanation needs a configured key.

## Integration and requirements audit (2026-10-23)

`reports/integration_requirements_audit_2026-10-22.md` records the contract checks, the defects fixed (the protected-note and status routes now answer a plain 503 when migration `f7a2d4b6c810` is not applied, and the Data Protection page shows that sentence), the audit against `docs/PROJECT_PLAN.md` (completed / deviations / incomplete / blocked / untested) and the exact commands. The Risk and Goals pages show "not available / not reviewed yet" for any profile without a FAR-Trans link by design (information-request route ends the graph before the goal analyst); changing that is an owner decision. Human sentiment evaluation has not been done and is blocked on independent annotators.

## Financial Behaviour & Sentiment Page Redesign (ADR-048, 2026-10-22)

Frontend only. `pages/financial-behaviour-page.tsx` renders `BehaviourSentimentCard` -> `BehaviourSentimentView`, now composed of `behaviour-insights-panel.tsx`, `risk-assessment-panel.tsx`, `sentiment-input-panel.tsx` (shadcn Textarea, added with the CLI) and `sentiment-results-panel.tsx`, with pure helpers `lib/behaviour-insights.ts` and (additions) `isSubmitShortcut` / `inconclusive` in `lib/user-text-input.ts`. Endpoint, hook, schemas, generated types and `user_text_rules_v0` are unchanged; the text is still never stored anywhere. The 2026-10-20 "single-line input stays" note is superseded for the input only. `frontend` verification: `tsc -b` 0, `typecheck:tests` 0, `oxlint` 0 errors / 8 pre-existing warnings, build OK, `npm test` 133 passed, mutations 110 of 110 with a new pre-flight that fails on a stale mutation (see ADR-048); real-browser check on the offline SQLite launcher at 1366, 820 and 390 px, including submit, Ctrl+Enter, Clear, a conflict, no text in storage or the URL, and a profile switch.

## Sensitive-Data Protection Prototype (ADR-047, 2026-10-21)

An academic security extension, documented in `docs/THREAT_MODEL.md` (read it before describing it). What exists:
`backend/wealthpilot/security/` (`keys.py` KeyProvider + development `EnvironmentKeyProvider`; `crypto.py` AES-256-GCM
`EncryptionService` with versioned envelopes and context-bound associated data; `ledger.py` `AuditLedger` +
`LocalHashChainLedger`; `anchor.py` `LedgerAnchor` contract + `UnconfiguredAnchor`), tables `protected_records` and
`audit_ledger_events` (migration `f7a2d4b6c810`), routes `POST|GET /api/profiles/{id}/protected-notes`,
`GET|PUT|DELETE .../protected-notes/{record_id}` and `GET /api/profiles/{id}/security-status`, and the frontend page
`/security` ("Data Protection", display only). Config: `PROTECTED_DATA_KEYS` / `PROTECTED_DATA_ACTIVE_KEY_ID` (empty by default =>
protected notes fail closed with 503 and the page says "not configured"). `cryptography==50.0.1` is pinned in `pyproject.toml` (it was
already installed through `google-auth`); no other dependency was added.

State that must not be misdescribed: **only `protected_records` is encrypted -- every other table is plaintext.** The audit ledger is a
**local hash chain, not a blockchain** (same database, no consensus, not immutable; a privileged rewrite passes local verification).
Authorization is the project's asserted `X-Customer-Id` (ADR-020/031), so an API caller who asserts the owner's id is not stopped;
confidentiality holds against database/backup readers without the key. The development key provider is not a KMS; no re-encryption tool,
no escrow, no recovery from key loss. `core/`, `agents/`, `data/` and `training/` never import the security package (tested).
Unchanged: the advisory pipeline, risk/compliance/recommendation logic, sentiment feature, existing endpoint contracts.

Verification (2026-10-22): `tests/backend/security` 143 passed; DB-free group 926 passed / 1 skipped; GDELT 1492 passed; isolated Neon-test
regression run per file: 665 passed + 1 transient connection drop that passed on isolated re-run (not one uninterrupted run; see
`docs/TEST_PLAN.md` section 25); frontend `tsc -b` 0, `oxlint` 0 errors (8 pre-existing warnings), build OK, `npm test` 106 passed, mutations 88/88;
real-browser check of `/security` on the offline SQLite launcher (operational, tampered-chain, 390/1366 px).

Pending for the owner: apply the migration to `DATABASE_URL` (`alembic upgrade head`), set the two key variables if protected notes are
wanted, and decide on the production-hardening items in `docs/THREAT_MODEL.md` section 14 (real authentication first). Tests: see
`docs/TEST_PLAN.md` section 25. `CLAUDE.md` and `.claude/rules/*.md` were not edited; their layout lists do not yet mention `security/`.

## Current Test Status
Latest full run, after the demo dataset package (ADR-038), 2026-09-30 21:03:45–23:12:42, detached and in
isolation: **`1326 passed, 1 skipped, 158 warnings in 7732.26s (2:08:52)`, 0 failed, 0 errors, exit code 0.**
The earlier Phase 36 run below remains as history.

Full `pytest tests/ -v`, run detached and in isolation at the end of Phase 36:
**`1260 passed, 3 skipped, 152 warnings in 5977.95s (1:39:37)` — 0 failed,
0 errors, pytest exit code 0.** This is one clean, fully isolated, detached run of
`pytest tests/ -v` (1263 tests collected), started 2026-09-26 20:10:52 and exited
21:50:35. The 3 skips are the documented live-Gemini tests
(`test_debate_gemini_client.py` x2, `test_explanation_gemini_client.py` x1),
which skip when Gemini is unavailable or out of quota (CLAUDE.md section 19).

How it was reached, per `docs/TEST_PLAN.md` section 22: an earlier full run the
same day ended `1249 passed, 2 skipped, 12 errors in 21318.72s (5:55:18)`,
exit code 1. All 12 errors were in `tests/backend/api/test_household_goals.py`,
all at **test setup** (no test body ran), all at
`tests/backend/api/conftest.py:56` (`engine.connect()` in the `db_connection`
fixture): the first raised `server closed the connection unexpectedly` / `the
connection is lost`, the other eleven `[Errno 11001] getaddrinfo failed`. No
product frame appeared in any traceback, so all 12 were classified
DATABASE/NETWORK. After a DB-free probe confirmed the database reachable, exactly
those 12 were re-run in isolation, unmodified: **12 passed, 0 failed** (164.96s,
exit code 0). The clean run above was then taken fresh; the earlier run is not
used as the result. (A development server started outside this work was also
running during the clean run; the run still completed with no failure or
error.)

Before that, the most recent completed full run was Phase 32's (**838 passed,
2 skipped, 0 failed**, 37:03). Phases 33 and 34 never completed one: Phase 33's
attempts were killed by session teardowns (which is how a stale Phase 32 route
inventory went unnoticed until Phase 34), and Phase 34's was blocked when
port 5432 to the hosted database became unreachable.

Phase 35/36 targeted run (every never-before-executed Phase 35 and 36 test
file, detached, in isolation): **236 passed, 0 failed** in 30:19 — engine 61,
migration history 11, goal models 30, metadata models 11, goals API 85,
metadata API 39. One earlier Phase 35 failure was a defect in the test itself
(it deleted a household through the ORM instead of exercising the database
cascade) and was corrected before this run.

Live check against the real dev database (rolled back): **34/34** — the four
personas' full analysis responses byte-identical, their individual goals and
financial inputs unchanged, the summary reading persisted records with the
specified reference values, goals never changing the summary, and all 11
tables' row counts restored.

Frontend, at the current state of the code: `npx tsc -b` 0 errors; `npx oxlint`
0 errors, 8 baseline warnings; `npm run build` succeeds. Source-level render
checks of the Customer Profile page against real API payloads pass 20/20
(Phase 36), 17/17 (Phase 35) and 39/39 (Phase 34). No browser-based test has
been run.

## Current Build Status

Frontend production build succeeds; 1,094.83 kB (gzip 327.13 kB) single JS
chunk plus 97.80 kB CSS (a known, accepted characteristic — not code-split;
see `docs/TEST_PLAN.md` §18). By original source size the bundle is roughly
24% Recharts, 18% `@base-ui/react` (shadcn v4 primitives), 17% react-dom, 10%
react-router, 8% application code; the only duplicated bundled package is a
small nested `reselect` under recharts. Recharts arrived in Phase 30 (+84 kB).

## Current Known Limitations

See `docs/ARCHITECTURE.md` §23 and `docs/PRD.md` §39 for the full list;
summary: `expense_persona` permanently unavailable for FAR-Trans
customers (structural); prototype auth has no server session
(disclosed); no customer-switching UI (by design); no browser-based
visual testing performed to date (disclosed each time it applies) — in
particular the Phase 30 charts' drawing, label room at narrow widths and
dark-mode contrast are unverified; only their data binding was checked.
Environment-specific: the Gemini account's quota is exhausted (HTTP 429
`RESOURCE_EXHAUSTED`), so every approved analysis currently shows the
designed templated explanation (`validation_passed: false`) rather than a
validated live Gemini one — though as of Phase 32 the quota has partially
recovered: one of the three live-Gemini tests now runs and passes, while the
other two still skip; `customers.name` is not unique at the schema level (so
`GET /api/profiles/lookup` deterministically returns the lowest id when
names repeat), though the 2026-10-04 reset (ADR-040) removed the one
duplicate that had actually accumulated (old id 29101); a Python virtualenv
exists at
`frontend/.venv/` (created outside any phase's work on 2026-09-20 12:53,
gitignored, untouched); backend-authored `unavailable_reason` strings are
shown verbatim and contain developer-style wording (ASCII " -- ", one names
an internal function) — changing them is a backend text change, deferred;
the databases
are hosted, so network drops can cause bursts of test failures unrelated
to the code. **Known defects (found in Phase 36, not fixed — outside its
scope):** the Phase 33 household record endpoints return a 500 rather than a
422 for an explicit `null` on a required field in a `PUT`, and for a
non-finite (`"1e400"`) or out-of-range amount; the Phase 28
`FinancialInputsUpdate` schema also accepts non-finite values (its HTTP
behaviour was not probed). The Phase 35 `interest_rate` field and the Phase 36
goal schemas are hardened against both.

**Pre-existing finding from the final git audit (documented, not changed):** the
root `.gitignore` (last modified 2026-09-24 23:24, before Phases 35 and 36) has
no rule for `datasets/`, so `git status` now lists the ten raw files under
`datasets/raw/` as untracked, contrary to CLAUDE.md's "datasets/raw/ ...
gitignored". Neither phase touched `.gitignore` or `datasets/`: every raw file
still matches its recorded Phase 5 SHA-256 hash, and the `datasets/`
directories were last modified 2026-09-13. `.env` and both virtualenvs are
still ignored. Restoring the rule (for example `datasets/raw/*` with a tracked
`.gitkeep`) is left to the project owner, and should be done before any first
commit so the raw datasets are not committed.

## Current Blockers
None. The port-5432 block recorded during Phase 34 cleared on its own; the
database has been reachable throughout the Phase 35/36 validation.

## Pending Work

- The backend part of the plain-language explanation enhancement (ADR-037) is
  prepared but not applied or validated; see Current Frontend State above.
  Nothing else is scheduled. See `docs/PRD.md` §40 (Future Scope) for possible,
unscheduled future direction.

## Important Implementation Notes

Scenario Simulator: for the Aggressive default persona the risk-conditioned
default is already MVO; comparing it with HRP or 1/N shows both **REJECTed by
compliance** (QQQ below the Aggressive band) — real, verified behaviour, useful
in a demo. `PYTHONPATH` must include the repo root (not just `backend/`) for
`training.*` imports to resolve outside pytest's own `pythonpath = .` —
relevant when running any one-off script that imports from
`agents/nodes.py` (which imports `training.behaviour.common`). Do not run
a long-lived server (e.g. `uvicorn`) to generate the OpenAPI schema for
type regeneration — call `app.openapi()` directly in a short-lived Python
process instead (`json.dump(FastAPI_app.openapi(), f)`), then
`npx openapi-typescript <file> -o frontend/src/types/api.ts`. When
running the full backend test suite in the background for a long
duration, do not pipe through `tail` — it buffers all output until the
process exits, hiding real progress; prefer direct/unbuffered output to a
file you can `Read` incrementally. The databases are hosted (Neon), so a
network drop mid-run produces bursts of DB failures (`getaddrinfo failed`,
`Network is unreachable`, `server closed the connection unexpectedly`);
see `docs/TEST_PLAN.md` §22 for how to classify them. When a cached
analysis must be recomputed after a change to what the pipeline computes,
bump `ANALYSIS_PIPELINE_VERSION` in `analysis_service.py` rather than
deleting rows. `run_goal_monte_carlo` needs per-period returns matching
`GoalAssumptions.contribution_periods_per_year`; never pass it the raw
daily series. Recharts 3 draws no `<svg>` in a server render (its surface
mounts after a client-side size measurement), so chart *drawing* cannot be
verified without a browser; chart *data binding* was verified in Phase 30
by SSR-rendering the real page components against real API responses with
the Recharts primitives replaced by data-capturing stubs (scratch harness,
not committed; Phase 31 extended it to the whole routed app with the four
personas — 71 checks — plus a rollback-safe live API regression of every route,
56 checks). After changing any backend docstring that appears in the
OpenAPI schema, regenerate `types/api.ts` (dump `app.openapi()` to JSON,
then `npx openapi-typescript`) — Phase 29's lookup-docstring edit left it
stale by one comment until Phase 30.

## Last Verified State

This file was last verified against source and the live system at the
completion of Phase 32. If a later change is made without updating this file, treat
this section's claims as potentially stale and re-verify against source
per `docs/RULES.md` Rule 29.

User-text annotation (owner decisions 2026-10-20): the single-line input stays; preference confirmation/persistence and migrations are deferred (preferences stay unconfirmed and non-persistent).
`docs/USER_TEXT_ANNOTATION_RUBRIC.md` is a PROPOSED rubric and validation-protocol draft; `datasets/rubric_examples/` holds 21 SYNTHETIC rubric walkthrough examples (illustrative labels, never validation
data). No real user text collected, no accuracy measured: `user_text_rules_v0` remains UNVALIDATED_BASELINE. DB-backed tests are not run here (only hosted Neon URLs configured; see `docs/TEST_PLAN.md`).

Proposed owner decisions (2026-10-20, ADR-044, NOT accepted/implemented): O5 code-mixed/unsupported-language text is `uncertain` + flagged, no translation, reported separately; O6 multiple `emotional_tone` labels,
`concerned`/`hopeful` list, `ambiguous_tone` flag. Production taxonomy and `user_text_rules_v0` (UNVALIDATED_BASELINE) unchanged. `docs/USER_TEXT_VALIDATION_DECISION_SHEET.md` lists O1-O4/O7 options (all blank).
No local PostgreSQL (setup steps in `docs/TEST_PLAN.md`); instead `tests/backend/api/test_monthly_records.py` was run against the Neon test DB `neondb_test` after a read-only safety check (empty, at head `e5b1c7d93a20`): 53 passed, migration a no-op. `datasets/rubric_examples/pilot_pack_v0/` is a 30-text FICTIONAL pilot pack: `annotator/` (unlabelled texts, blank template, instructions) is separate from `author_only/` (challenge map); `scripts/pilot_disagreements.py` lists differences and unclear flags with no scoring. Rubric preparation only, not validation. `scripts/local_test_db.ps1` (guarded local test-DB setup) is prepared but unexecuted: PostgreSQL is not installed (needs UAC).

Isolated Neon test runner (2026-10-20): `scripts/run_isolated_db_tests.py` + `scripts/isolated_db/` (guard, pytest plugin with keepalives) with 46 offline guard tests; accepts only `neondb_test` on the expected Neon host, deselects `real_*` tests, never migrates on its own. 622 isolated DB tests passed earlier; the 93 development-database tests are excluded. The decision sheet now has an owner summary and the verified O5 issue (baseline labels code-mixed text that contains one English cue word; a characterisation test pins it; fail-closed option B recommended for owner review, not implemented).

User-text validation decision packet (2026-10-20): `docs/USER_TEXT_VALIDATION_DECISION_SHEET.md` now covers O1-O7 with stable ids, status, recommended default, rationale, consequences and prerequisites; every owner row is blank, O5/O6 stay PROPOSED, no threshold is invented. Contradictions C1-C6 listed (C1/C2/C4/C5 fixed in the rubric/instructions; C3 withdrawal-vs-no-link is an open owner decision). Rubric is `v0-draft` (unfrozen; freeze manifest tool NOT STARTED). Baseline unchanged, UNVALIDATED_BASELINE.

Fictional rubric dry run (owner limited approvals 2026-10-20): O1 accepted for fictional notes only; O4 accepted for the dry run (two annotators + one adjudicator, all independent of the rubric author); O5 Option A is the proposed annotation policy; O6 stays proposed; O2/O3/O7 undecided; withdrawal-vs-unlinkability (C3) recorded as a blocker for future real-text collection. Built: verified annotator package (`datasets/rubric_examples/pilot_pack_v0/package/`, only the rubric parts between its `annotator-excerpt` markers, sections 1-3 plus the flag definitions), DRAFT unfrozen manifest, participant-register independence gate, blind adjudication worklist (`pilot_disagreements.py --blind`), `scripts/build_dry_run_package.py`. Rubric `v0-draft` (rule 9 aligned with O5 Option A). ANNOTATION NOT STARTED: no independent human reviewers identified; the AI author did not annotate and AI labels are not accepted as independent. Baseline not run on the pilot; UNVALIDATED_BASELINE unchanged.

Demo-manifest guard fixed (2026-10-20, ADR-045): the training-data guard covers every `datasets/raw/` source except the explicitly excluded `gdelt` research acquisition area (`GUARD_EXCLUDED_RAW_SOURCES`); both previously failing tests pass, manifest.json unchanged. The 11 pre-annotation ambiguities now have PROPOSED clarifications (`pilot_pack_v0/author_only/pre_annotation_ambiguities.md`), none applied, none changing the taxonomy; dry run still blocked on independent human reviewers.

Rubric ambiguity review (2026-10-20): A1-A11 each classified C (testable, no taxonomy change) / P (owner policy: A5, A6, A10) / T (taxonomy: A7, and A1 if the tone list is extended) / H (needs human annotation), with current rule, proposed wording, likely disagreement and downstream implications in `pilot_pack_v0/author_only/pre_annotation_ambiguities.md`; all PROPOSED, none applied, none with human agreement. Fixed two contradictions (rubric section 8 status table; rule 2 vs rule 9) and rebuilt the DRAFT package. The decision sheet ends with a five-step next-decision sequence; recommended: name independent reviewers, then run `v0-draft` unchanged. O2, O3, O7, C3 open; O5, O6 PROPOSED; baseline UNVALIDATED_BASELINE.

Consistency and safety audit (2026-10-20): found and fixed (1) the annotator excerpt still leaked provenance/consent/O2 wording and a remark about a pilot example (now only the rubric parts between `annotator-excerpt` markers, sections 1-3 plus the flag definitions, are distributed; `verify` flags leaked wording, a stale package copy and a stale excerpt); (2) backspace characters (0x08) written where regex word boundaries were meant, which made the O1-O4/O7 leak pattern, the no-numeric-threshold test and a GDELT adapter `.env` assertion inert (all repaired; a repo-wide test now forbids stray control characters in Python sources); (3) the rubric cited an ADR inside the annotator text; (4) the shipped `limitations` list now says there is no language detection (additive string, no schema or behaviour change). Statuses (O1/O4 limited approval, O2/O3/O7 open, O5/O6 PROPOSED, C3 open, A1-A11 unapplied, annotation NOT STARTED, rubric not frozen) are pinned across the documents by tests. Rebuild is byte-deterministic.

Adversarial audit of the dry-run package builder (2026-10-20): `build_dry_run_package.py` now refuses (exit 2, nothing written) on bad/duplicate/misspelled excerpt markers, leaking or malformed sources, label-carrying texts/template, symlink sources and unexpected package entries (never deletes); `verify` also checks symlinks, manifest counts/hashes/keys, CRLF-normalised sources, malformed manifests; register gate requires an ISO attestation date, tolerates a BOM, is case/space-insensitive on codes and cannot verify independence (owner attestation). 80 new tests (58 adversarial, 22 mutation checks proving the regression tests fail on bad fixtures). Rubric still v0-draft, proposals unapplied, manifest DRAFT/unfrozen, annotation NOT STARTED, package not distributed.

Sentiment feature completion (2026-10-21): the "Financial behaviour & sentiment" card is split into a pure input-rules module (`frontend/src/lib/user-text-input.ts`, limit and control characters mirror and are cross-checked against the backend, never looser), a presentational view and a thin container; it renders backend `statements` (observed facts with their source fields, once each), the stored assessment, the reading (label + icon + explanation, never uncertain->neutral, confidence "not provided" when null, backend limitations incl. "no language detection"), conflicts, caveats and technical details; character counter, validation, Clear, duplicate-submit guard, stale-results notice, failed request shows no results. Fixed: validation 422 echoed wrongly typed text (route-scoped fix in `api/errors.py`); Clear was enabled with nothing to clear. Frontend tests need no new dependency (`npm test` 46, `npm run test:mutations` 43/43; fixtures are real backend responses). Backend +98 tests. Not covered: real-browser interaction and visual layout. Baseline still UNVALIDATED_BASELINE; no change to taxonomy, schema, migrations or A1-A11/O5/O6.

Dedicated page (2026-10-21, ADR-046): `/financial-behaviour` ("Financial Behaviour & Sentiment", sidebar "Behaviour & Sentiment") holds the detailed card (key by profile, `showHeader={false}`); Financial Health keeps a compact `BehaviourSummaryCard` (records-only call, 3 facts + assessment sentence + a real link styled with `buttonVariants`). Browser-verified (real Chrome via agent-browser against a local SQLite synthetic backend; Neon never contacted): navigation, API match (21/21 values), validation, loading/error/empty states, profile switching, privacy (no storage/URL/console leak), desktop/tablet/phone. Defects found and fixed in that pass: status badge cut off on phones, Button-as-Link console errors (10 sites) and button role, onboarding/login/create-user had no main landmark, Create User sent empty/invalid values to the API (now field-level validation, `lib/profile-form.ts`), phone sidebar sheet stayed open after navigation. Known remaining: the 10 Button-as-Link sites still announce as buttons; populated pages other than the sentiment ones were only structurally swept.

## Sentiment isolated compatibility phase (2026-10-26): stopped on advisory blocker

The owner approved R1 to R4 (`torch==2.6.0` CPU, `transformers==4.57.1`, `tokenizers==0.22.1`, `safetensors==0.6.2`) and R5 for isolated verification only; R6 to R14 are still UNRESOLVED. In a disposable venv outside the repo the four pins resolved without conflict on Python 3.11.9 / Windows amd64 (with numpy 1.26.4; unconstrained pip would pick numpy 2.4.6), all 24 wheel hashes matched PyPI, but OSV lists 24 records against `torch==2.6.0` and 12 against `transformers==4.57.1`, mostly fixed only in later releases. The owner's stop rule applied: nothing was installed, no version substituted, the venv and scratch cache were deleted. A1 was then REJECTED by the owner (see the next entry). The model is still disabled, `user_text_rules_v1` is still active, no weights or datasets were touched. Details: `reports/sentiment_model_approval_record.md`, section I of `reports/sentiment_transformer_dependency_request.md`.

## Sentiment security remediation (2026-10-26): A1 REJECTED, installation BLOCKED, replacement versions are candidates only

The owner rejected A1 for `torch==2.6.0` and `transformers==4.57.1` (36 OSV records / 29 CVEs by OSV's per-version query, later corrected to at least 31 CVEs; including the `transformers` config.json code-execution advisory CVE-2026-4372, which the advisory says bypasses `trust_remote_code`). In this read-only phase nothing was installed or downloaded and no weights, datasets, model revisions or runtime code were touched; R6 to R14 are still UNRESOLVED and the Transformer is still disabled. Findings: `torch` has no OSV record from 2.13.0; the whole `transformers` 4.x line still has records, so every clean candidate is a 5.x release (zero records from 5.10.1; 5.10.0 is yanked); `transformers` 5.10.1 to 5.12.1 accept the approved `tokenizers==0.22.1` and `safetensors==0.6.2`; the only existing package a candidate forces to change is `setuptools` (to at least 77.0.3). Candidates S1 to S4 (S1: torch 2.13.0, transformers 5.12.1) need explicit owner approval as new item A2 (UNRESOLVED); none is selected. The training loader (`training/sentiment/train_sentiment_transformer.py`) has no `use_safetensors=True` or pinned revision (not changed). Unrelated, pre-existing: the project's `certifi 2026.7.22` has two advisories (fixed in 2026.10.18), not fixed here. Details: `reports/sentiment_model_approval_record.md` and section J of `reports/sentiment_transformer_dependency_request.md`.

## Sentiment candidate-set review (2026-10-26): S1 to S4 reviewed read-only; A2 still UNRESOLVED, installation still BLOCKED

The owner did not approve A2 and asked for a read-only review of the candidate sets S1 to S4 (torch 2.13.0 / 2.14.1, transformers 5.10.1 / 5.12.1 / 5.20.2, tokenizers 0.22.1 / 0.23.3, safetensors 0.6.2 / 0.8.0). Unchanged: A1 REJECTED for the original pins, A2 UNRESOLVED, R6 to R14 UNRESOLVED, `user_text_rules_v1` active, `SENTIMENT_MODEL_ENABLED=false`, intensity regression deferred; nothing installed, downloaded or run; no code, manifest or configuration changed. Findings: no OSV, PyPI or upstream advisory lists any candidate version; all licences are permissive (torch's wider SPDX expression comes from PyTorch adopting PEP 639 `license-files`; its own licence is still BSD-3-Clause), no licensing concern identified (preliminary, not legal advice); the original `torch==2.6.0` pin has 24 CVEs, not 22 (OSV missed records with non-standard version strings; `transformers` 7), at least 31 with `transformers`, plus one advisory OSV lacks; `trust_remote_code=False` does not mitigate CVE-2026-4372 and `local_files_only=True` is not established as a mitigation; the transformers 5.x migration guide removes `safe_serialization` from `save_pretrained`, so `training/sentiment/train_sentiment_transformer.py:155` would need a code change (not made); `setuptools` 82+ removes `pkg_resources`, which `tensorboard` (required by TensorFlow 2.17) imports, so any torch environment should constrain `setuptools>=77.0.3,<82`; the project's `certifi 2026.7.22` (and `pip` 26.2.1's vendored copy) are affected by the Critical GHSA-6q48-6c7w-9gw2 (use 2026.10.19 or later; unrelated to the candidates, not fixed here, needs its own task before any Hub download). Ranking: S1 is the most defensible candidate for isolated verification (conditionally), S4 should be excluded for now; PyTorch does not backport fixes, so advisories must be re-checked on every install. The exact owner decision text, the maturity-rule values to choose and the unresolved questions are in `reports/sentiment_model_approval_record.md` (fourth-brief section) and section K of `reports/sentiment_transformer_dependency_request.md`.

## Sentiment isolated compatibility validation, set S1 (2026-10-27): completed; setuptools advisory flagged

The owner recorded A2 APPROVED for isolated verification only, set S1 (`torch==2.13.0`, `transformers==5.12.1`, `tokenizers==0.22.1`, `safetensors==0.6.2`; R3 / R4 unchanged; R1 / R2 only as replaced; R5 for isolated verification; A1 still REJECTED for the original pins; R6 to R14 UNRESOLVED) before anything was created. In a disposable venv outside the repo (since deleted): 35 hash-pinned wheels (170.3 MB, 852.8 MB installed) resolved by pip with no conflict, every hash equal to PyPI's, installed with `--require-hashes`, `pip check` clean; Python 3.11.9 / Windows CPU wheel confirmed, `torch 2.13.0+cpu` with no CUDA (declared `cuda-*` / `nvidia-*` / `triton` requirements are Linux-only), imports, an in-memory tokenizer and a safetensors round trip work offline, the torch-numpy bridge works with numpy 1.26.4, and TensorFlow 2.17.0 + PyTorch coexist in one process in both import orders from both interpreters (4 of 4 passed). All 107 declared `torch` licence files ship in the wheel; licences are permissive. No advisory lists any of the four S1 packages or 30 of the 31 transitive packages; the one finding is `setuptools` (every release in the approved `>=77.0.3,<82` range is listed for GHSA-h35f-9h28-mq5c, macOS sdist exclusion bypass, and GHSA-xmj3-9gf7-h52w, Windows legacy egg wheel install, published 2026-10-23); installed 81.0.0 under the literal condition, assessed as inapplicable, owner decision needed (accept, or amend the bound to e.g. `>=84.1.0` for disposable environments). Static findings on transformers 5.12.1: `use_safetensors=True` still refuses a pickle-only directory; `save_pretrained(safe_serialization=True)` is silently ignored (dead argument); the hub branch can request a background Hub conversion for pickle checkpoints. Not run, by the terms of A2: any model, stand-in model, forward pass, weight, tokenizer download or dataset. Nothing in the project environment, repository code or manifests changed; the Transformer stays disabled and `user_text_rules_v1` active. Next approvals: the setuptools decision; optionally a stand-in model test; separate code and project-environment tasks; R6 to R14 before any weight or dataset step. Details: `reports/sentiment_model_approval_record.md` and section L of `reports/sentiment_transformer_dependency_request.md`.

## Sentiment stand-in compatibility test, set S1 (2026-10-27): 19 of 19 checks passed; code changes recommended, not applied

The owner accepted `setuptools==81.0.0` and GHSA-h35f-9h28-mq5c / GHSA-xmj3-9gf7-h52w as residual risks for the isolated Windows pip-only environment only (not fixed, not irrelevant elsewhere) and authorised one stand-in test; A1 still REJECTED, A2 APPROVED only for S1 isolated verification, R6 to R14 UNRESOLVED, `user_text_rules_v1` active, `SENTIMENT_MODEL_ENABLED=false`. In a new disposable venv (identical 35-wheel hash-pinned set, since deleted) a random-initialised tiny BERT classifier with fixed synthetic ids passed 19 of 19 checks, with the repository only read: the runtime loader (`sentiment_model.py:258-259`) and the real training function (`fine_tune_with_torch`, called with `epochs=0`, no optimiser step) work unchanged under transformers 5.12.1; `use_safetensors=True` refuses pickle / `.bin` / `.pt` / `.pt2` weights, `trust_remote_code=False` never runs local custom code (a control in its own process shows `True` does and writes into the HF modules cache), `local_files_only=True` reaches the hub layer as cache-only, `load_model` refuses the unvalidated stand-in as `not_validated`; 0 network attempts, 0 hub-level calls, 0 `torch.load` calls, empty scratch HF cache, no pickle artifact created; no weights, datasets, Hub or user text touched. Findings (code NOT changed; separate approval): `save_pretrained(..., safe_serialization=True)` at `training/sentiment/train_sentiment_transformer.py:155` is a silently ignored dead argument in 5.x (byte-identical output with or without it); in 5.x `BertTokenizer(vocab_file=...)` silently builds a 5-token tokenizer and `verify_artifact` would still accept an artifact with such a tokenizer (it compares two numbers that both come from `config.json`), so the smallest fix is to record `len(tokenizer)` at training and compare it with the loaded tokenizer in `TransformersBackend.__init__`; training-loader hardening (`use_safetensors=True`, pinned revision, no Hub conversion thread) belongs with R6 / R7; the README still calls v4 the LTS line. Not covered: a real base model, a real download, a real head-size mismatch, a real training loop. Details: section M of `reports/sentiment_transformer_dependency_request.md` and `reports/sentiment_model_approval_record.md`.

## Sentiment integration hardening (2026-10-27): approved code changes applied and tested; nothing activated

Under a separate owner approval (recorded before editing) the Transformer seam was hardened: `fine_tune_with_torch` no longer passes the obsolete `safe_serialization` argument; artifacts record `tokenizer.length` (`len(tokenizer)`) and `TransformersBackend` (new required `tokenizer_length`) refuses a different loaded length, and `verify_artifact` refuses a missing or malformed length, with the existing code `artifact_incompatible` (a new reason code would change the public API schema, generated TypeScript types and frontend message map, so it was not added); the length is not compared with `config.vocab_size` (padded embeddings are valid); the trainer requires a caller-supplied immutable `revision` (40-character commit hash, checked before any import; none is defaulted anywhere), loads with `use_safetensors=True`, `trust_remote_code=False` and offline unless `--allow-hub-download` is given. Hub-conversion protection stays a documented blocker (`DISABLE_SAFETENSORS_CONVERSION` is undocumented, so unused; documented parameters plus pinned revision are the protection and a test pins the installed 5.12.1 behaviour). Tests: 113 new (41 tokenizer integrity, 40 training seam, 32 stand-in); project environment run 359 passed, 3 skipped (stand-in module skips without torch); with the disposable S1 packages 391 passed, 2 skipped; six deliberate defects all detected; 0 network attempts, hub-level calls, `torch.load`/pickle calls or Hugging Face cache writes. Unchanged: `user_text_rules_v1` active, `SENTIMENT_MODEL_ENABLED=false`, R6 to R14 UNRESOLVED, no model/revision/licence/dataset approved, no manifest or configuration change, intensity regression deferred. Open decisions: record the revision in the artifact metadata (schema), a more specific reason code (API), a tokenizer-longer-than-vocab check. Next approval before any real checkpoint or dataset: R6/R7 with commit hashes, network approval for `--allow-hub-download`, approval to install S1 where training runs, the project `certifi`/`pip` task; datasets need R8 to R10. Details: `reports/sentiment_model_approval_record.md`, `training/sentiment/README.md`, ADR-052 addendum.

## Sentiment owner decision record (2026-10-28): D7 approved, D8/D9 unresolved, D10 to D13 blocked; no code changed

A read-only review prepared the owner decision record in `reports/sentiment_model_approval_record.md` ("Owner decision record (eighth brief)"). **D7 APPROVED:** the existing code `artifact_incompatible` is retained for tokenizer-length mismatches (no new public API code; API, generated types and frontend untouched). **D8 UNRESOLVED:** whether every artifact must record the exact 40-character base-model revision, tokenizer source, extended library versions, a manifest hash and a `metadata_schema_version` (engineering recommendation: approve, before any real training run; proposed policy: supported versions `{1}`, unknown or missing refused, no migration, artifacts immutable; decision text prepared). **D9 UNRESOLVED:** whether to reject `len(tokenizer) > config.vocab_size` (recommendation: approve; equality still not required). **D10 BLOCKED:** Hub conversion is an observed 5.12.1 property, no undocumented switch is added, and one of a documented mechanism, a local conversion-free workflow (needs a trainer API decision for a local base directory) or a separate security approval is needed first. **D11 BLOCKED:** the eight-item network approval (repository, 40-character revision, exact files, destination, `--allow-hub-download`, account/network boundary, hash verification, cleanup/rollback) is unsupplied; note `--allow-hub-download` is not a file allow-list. **D12 BLOCKED:** a real training environment needs a separate approval to install the S1 set; `backend/pyproject.toml` untouched until production activation. **D13 BLOCKED:** separate task TASK-CERT-1 for the project `certifi`/`pip` advisory, not started; no Hugging Face download before it is done or risk-accepted. R6 to R14 UNRESOLVED; the brief's reading-list path `backend/wealthpilot/core/artifacts.py` does not exist (the writer is `training/sentiment/artifacts.py`). First missing approval before any real checkpoint: R6 (or R7) with the exact revision supplied by the owner. Production remains on `user_text_rules_v1`; `SENTIMENT_MODEL_ENABLED=false`.

## Sentiment D8 and D9 implemented (2026-10-28): artifact provenance schema 1 and the tokenizer/embedding invariant; nothing activated

The owner approved D8 and D9 and they are enforced. Every trained artifact now records `metadata_schema_version: 1` (only version accepted; missing/unknown refused; no migration; never edited in place), `base_model` and `base_model_revision` (40-character lowercase hash), `tokenizer.identifier`/`tokenizer.revision`/`tokenizer.length`, `library_versions` with torch/transformers/tokenizers/safetensors (provenance only) and `manifest_sha256` (SHA-256 of the canonical JSON of the `files` map; malformed = `artifact_incompatible`, wrong = `artifact_corrupt`). The trainer reports what it actually loaded; the revision rule has one definition (`is_commit_hash` in `sentiment_model.py`). Old-format artifacts fail closed as `artifact_incompatible`. D9: `len(tokenizer) > config.vocab_size` is refused (`artifact_incompatible`) at artifact verification and in the `TransformersBackend` constructor before any text is processed; equal and shorter (padded) are accepted. No new public API code. Tests: 608 passed, 3 skipped in the project environment (184 new provenance/D9 tests, 60 integrity, 62 seam); eight deliberate defects all detected. **Limit:** `tests/training/sentiment/test_transformer_standin.py` was updated for the new schema (and two tests added) but NOT re-run, because no package may be installed in this phase; re-run it in the disposable S1 environment before any real training. D10 to D13 BLOCKED; R6 to R14 UNRESOLVED; no real checkpoint, dataset or Hugging Face asset accessed; `user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`. Details: `reports/sentiment_model_approval_record.md` ("D8 and D9 implementation results"), `training/sentiment/README.md`, ADR-052 addendum.

## Sentiment disposable S1 regression check (2026-10-28): passed; nothing activated

Under the owner's tenth-brief authorisation the disposable S1 environment was recreated from the unchanged 35-package hash-pinned list (wheels fetched once with `--require-hashes`, all 35 re-hashed, installed offline, `pip check` clean) and the updated library-dependent stand-in tests ran offline with the related seam, provenance, tokenizer-integrity and loader-guard tests: **381 passed, 1 skipped (the earlier symlink skip), 0 failed** (stand-in 34, seam 62, provenance 184, integrity 60, loader guards 41). Against real libraries and randomly initialised local models: schema version 1 provenance and manifest hash work, equal / shorter / padded tokenizer lengths are accepted, longer is refused by the writer and the backend, output is safetensors-only, pickle / `.bin` / `.pt` / `.pt2` are refused, `trust_remote_code=False` and `local_files_only=True` are preserved, and 0 sockets, Hub calls, `torch.load` or pickle calls, no Hugging Face cache writes. The environment (903 MB), wheels (163 MB) and caches were deleted; repository and project environment unchanged. Open housekeeping: two README statements still say the stand-in tests were not re-run (needs a one-line approval to fix). Ready to enter the separate R6/R7 licence-and-revision approval phase; not ready for any download (D10 to D13 BLOCKED, R6 to R14 UNRESOLVED). `user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`. Details: `reports/sentiment_model_approval_record.md`.

## Sentiment R6/R7 approval preparation (2026-10-28): matrix and owner decision fields prepared; nothing decided

The README now records the passed disposable-environment check (381 passed, 1 skipped, 0 failed). A decision matrix for FinBERT (R6) and `FacebookAI/roberta-base` as the R7 candidate (no sentiment head; the owner must name the candidate) and owner decision fields P1 to P11 are in `reports/sentiment_model_approval_record.md`. Built only from evidence recorded on 2026-10-20 (licence claims: FinBERT CC BY-NC-SA 4.0, trained on Financial PhraseBank CC BY-NC-SA 3.0 and Reuters TRC2; recorded FinBERT revision `0bc2ac10...f031`, NOT approved). Financial PhraseBank is not sufficient validation for personal-finance narratives. No Hugging Face query, download, dataset or package. R6/R7 UNRESOLVED; D10 to D13 BLOCKED; R8 to R14 UNRESOLVED; `user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`.

## Sentiment R6/R7 selection phase (2026-10-28): no selection supplied; R6 and R7 UNRESOLVED

The twelfth brief listed the R6 and R7 choices but gave no selection or accept / reject values, so nothing was decided: R6 (FinBERT) UNRESOLVED, R7 (`roberta-base` / `cardiffnlp/twitter-roberta-base-sentiment-latest` / `mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis`) UNRESOLVED, no candidate selected or rejected. The complete decision form (R6-0 to R6-9, R7 matrix, F1 to F14, approvals required before a metadata query and before a download, a one-reply format) is in `reports/sentiment_model_approval_record.md`. A metadata query needs its own approval; D10 to D13 must be resolved before any checkpoint access. Recorded revisions stay proposals (`0bc2ac10...f031` FinBERT, `ae0eab9a...e91` mrm8488); nothing invented (no licence, tokenizer licence, data permission, file list, host). No external access, no package, no code change. `user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`.

## Sentiment R6/R7 decision form (2026-10-28): recorded conservatively; nothing approved

Per the owner's thirteenth brief: R6-0 to R6-9 KEEP UNRESOLVED; R7 KEEP UNRESOLVED; R7-A (`roberta-base`), R7-B (`cardiffnlp/twitter-roberta-base-sentiment-latest`), R7-C (`mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis`) NOT SELECTED (not rejected); F1 to F14 KEEP UNRESOLVED for every candidate; R8 to R14 KEEP UNRESOLVED; D10 to D13 BLOCKED; D7 to D9 approved. Reason: the evidence cannot support accepting any licence, data terms, tokenizer licence, commercial-use position, revision, file list or download boundary. No metadata-only query is authorised; to reopen, the owner supplies the seven inputs listed in `reports/sentiment_model_approval_record.md`. No external access, package, code or manifest change. `user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`.

## Sentiment phase completion (2026-10-28, fourteenth brief): one rules-baseline gap fixed; nothing activated

The end-to-end re-verification found one defect: hypothetical and conditional statements ("If the market crashes I would be very worried", "If I had more money I would want higher returns") were read as a current feeling or preference. Fixed in `core/user_text_sentiment.py` (ADR-050 addendum): such clauses give no cue, tone, evidence or preference, the text is `uncertain` / `weak` with a note in `limitations`, a model is never shown them; no API or type change. Also added a database-free ledger-boundary test (nothing sentiment-related reaches `wealthpilot.security`; the ledger shape cannot carry text or personal data). Re-verified: privacy audit (no logging, persistence, caching, ledger call; the frontend keeps text in memory only and clears it on profile switch), seam and artifact guards, undocumented env controls (none), generated types identical, frontend 174 tests and 150 of 150 mutations. Open owner items: add a hypothetical / conditional category to the annotation rubric and coverage list before the rubric is frozen; the CI, agreement and breakdown statistics are not implemented in `metrics.py`. Gates unchanged: `user_text_rules_v1` active, `SENTIMENT_MODEL_ENABLED=false`, D7 to D9 approved, D10 to D13 BLOCKED, R6 to R14 UNRESOLVED, no model, dataset or user text accessed, intensity regression disabled, no blockchain payload with sentiment. Record: `reports/sentiment_model_approval_record.md`, "Sentiment phase completion (fourteenth brief)".

## Sentiment rubric update and evaluation statistics (2026-10-29): prepared offline; nothing activated

Owner-approved (recorded first): `docs/USER_TEXT_ANNOTATION_RUBRIC.md` gained rule 11 (hypothetical / conditional / wish / counterfactual statements are not a current view) and rule 12 (labelling rule with six illustrative examples; "I feel safe even if prices fall" keeps its current clause). Still `v0-draft` (not frozen, not validated, no annotator has it); the pilot-pack manifest was rebuilt with the repository's builder: rubric SHA-256 `c77179950111c4ffaedf1564e5ee6466f6f38c753d012e1930672c1b77808fd3`, excerpt `a7bc2d328c55e9bddece4023ebd609c2713b6a1e3df679ba0ddd83f6bac9cd9b`. The rubric has no rules for plain quotations, other people's statements or past feelings (open item), and the baseline deliberately disagrees on "even if" clauses (documented, baseline unchanged). `training/sentiment/metrics.py` now has offline evaluation statistics (Wilson / stratified bootstrap intervals, Cohen's kappa and Krippendorff's alpha, per-class and per-group breakdowns with explicit undersized-group handling, coverage / abstention, calibration bins and ECE, paired rules-baseline comparison) behind a required `StatisticsPlan` (proposed values, not approved) and `EvidenceBasis` (synthetic / unapproved data is `not_validation_evidence`; never "validated"; no targets or pass / fail; not connected to activation or to `evaluate_sentiment_model.py`). Tests: 20 + 2 rubric guards, 39 statistics tests, 22 of 22 mutations detected. Remaining owner approvals: interval methods and values, class-support threshold, agreement statistic and multi-label fields, calibration / selection criteria, significance testing, label set, wiring; plus a dataset (R8 to R13). Gates unchanged: `user_text_rules_v1` active, `SENTIMENT_MODEL_ENABLED=false`, D10 to D13 BLOCKED, R6 to R14 UNRESOLVED, no model / dataset / user text access, intensity regression deferred. Record: `reports/sentiment_model_approval_record.md`, "Rubric update and evaluation-statistics support (fifteenth brief)".

## Sentiment evaluation-policy preparation (2026-10-29): alignment and statistical values left UNRESOLVED

The owner's brief named three outcomes for the rubric / baseline "even if" disagreement but chose none, so it is unresolved and neither the rubric's rule 12 nor `core/user_text_sentiment.py` changed. Added: rubric rule 13 (quotations, other people's statements, past feelings give no current view; unsettled cases go to `rubric_unclear`; no label, no example); pilot-pack hashes rebuilt only by `scripts/build_dry_run_package.py` (rubric `5a5be11cbe06f0685c91d17670c814c42b1373202d852a70e8d905ed1fbc48a2`, excerpt `cc465ffdaad2f4452987df62955146c5664bd929817878d6c5018ba999f93f22`; still `v0-draft`, DRAFT, not frozen, not distributed). Verification found more rubric / baseline differences, all documented and pinned by tests: a current clause joined to a conditional one without a comma is lost; past-only text is read as neutral while quotation-only and other-person-only text is declined; the baseline tags no topic from quotations or other people and has no `hedged` flag. Nine open annotation-policy items AP1 to AP9 are in the validation decision sheet (owner entries blank). A 34-row statistical-policy matrix is in the approval record: no value is approved (95%, 2,000, 42, 20, 0.80, 0.85 are candidates only); `metrics.py` is unchanged and encodes no target; the evaluation-script integration is a design with seven steps and stated blockers (frozen-manifest schema, an approved dataset, the label set, group tags, near-duplicate removal, D12). Guard tests: 6 policy-record tests plus 13 new rubric / baseline tests. Gates unchanged: `user_text_rules_v1` active, `SENTIMENT_MODEL_ENABLED=false`, D10 to D13 BLOCKED, R6 to R14 UNRESOLVED, no model / dataset / user text access, intensity regression deferred.

## Sentiment evaluation policy decided and enforced offline (2026-10-29): gates, not activation

The owner approved every stated value and adopted the assistant's proposal for the rest (two explicit answers, recorded in `reports/sentiment_model_approval_record.md`). Annotation: AP1 to AP3 and AP7 `NO_CURRENT_VIEW`, AP4 `KEEP_DOCUMENTED_DIFFERENCE`, AP5 `UNCERTAIN_WEAK`, AP6 `LABEL_CURRENT_ONLY`, AP8 `HEDGED_CURRENT_CONDITIONAL_NOT_CURRENT`, AP9 `TAG_TOPIC_ONLY`, comma-less "and" `RETAIN_DOCUMENTED_BASELINE_BEHAVIOR`; the production baseline is unchanged; the draft rubric (still `v0-draft`, not frozen, rubric `bcd6b56da929e984faabba825b3377a78a610862d7b0b19e5a6b43e19738b7c0`, excerpt `a7032ef0b3c6bd747d312a74ab433826bb0025468fba4eb1d717877933e38c6e`) was aligned and the pack rebuilt by the official builder. Statistics: 0.95 / 2,000 / 42, supports 75 / 20 / 300, positive-negative-neutral, Cohen's kappa (no floor), 10 bins, report-only ECE, coverage 0.70 / abstention 0.30, macro-F1 0.80, precision 0.85, no recall floor, no significance test. `metrics.py` evaluates them as gates (`assess_against_policy`), never as activation; wording `validated` / `not_validation_evidence` / `descriptive_only` / `insufficient_support`; activation (R14) also needs an unapproved lower-bound rule. New `frozen_evaluation.py` (offline frozen-set verification; its manifest schema is a proposal awaiting confirmation) is not connected to the evaluation script. Tests: 31 policy-gate, 29 frozen-evaluation, 6 record guards; 61 of 61 mutations detected. Open: confirm the implementation readings and documented differences, lower-bound rule, multi-label agreement, the AP8 polite-form boundary, schema confirmation and wiring, then R8 to R13 (dataset, annotation, frozen rubric), R6 / R7, D10 to D13, R14. `user_text_rules_v1` active, `SENTIMENT_MODEL_ENABLED=false`, no model / dataset / user text access.

## Sentiment: remaining evaluation-policy decisions recorded, schema wired to local fixtures (2026-10-29)

The owner confirmed the recorded readings (no current view is `uncertain`; AP4 `KEEP_DOCUMENTED_DIFFERENCE`; comma-less "and" retained; coverage and abstention are gates, not activation rules; the strict view decides the macro-F1 gate; gates only on `positive_negative_neutral`; `validated` needs every condition; the baseline / rubric differences are comparability limitations) and approved five choices: `NO_LOWER_BOUND_ACTIVATION_RULE` (a report alone never recommends activation), `DEFER_MULTI_LABEL_AGREEMENT`, `NON_STRATIFIED_ITEM_BOOTSTRAP`, `APPROVE_SCHEMA_AND_WIRE_OFFLINE` and AP8 `CONTEXT_DEPENDENT`. Changes: the baseline now withholds a polite form ("would like" / "would prefer") followed by a bare trailing condition (the only production change; method label unchanged); rubric rule 12 aligned (still `v0-draft`, rubric `346c5dce27bd37f493decc4d55876adc6dbdf6008e48f10c318f74e217896e8e`, excerpt `d98ece044dde43c36b1337d8e4df7cc7015f2b84d1c36402447f2601f180e778`); `EvaluationPolicy` has the four decided options; `frozen_evaluation.py` implements the confirmed schema (immutable manifest hash, recomputed record hashes, personal-data markers refused, declared evidence status checked); `evaluate_sentiment_model.py` has a frozen-set mode through that interface only (no model artifact, evidence from the manifest alone, no record text or id, exit status independent of targets). No real manifest or dataset exists. New difference (f) awaits confirmation. A labels-only predictions file keeps a candidate `descriptive_only` (no confidences). Open: near-duplicate method and threshold, group-dimension names, a predictions format with probabilities, a real dataset with annotation and a frozen approved rubric (R8 to R13), R6 / R7, D10 to D13, R14. `user_text_rules_v1` active, `SENTIMENT_MODEL_ENABLED=false`, no model / dataset / user text access.

## Sentiment: consolidated approval form issued (2026-10-29)

All remaining phases (metadata query, environment, checkpoint download, dataset and annotation, evaluation, activation) are behind hard gates that are still closed, so none started. Issued `reports/sentiment_consolidated_approval_form.md` (sections A model selection and per-model licence / revision / files / hosts / destination / hashes / cleanup / use, B metadata-only query, C D10 to D13 and cache location, D dataset and annotation R8 to R13 incl. whether fictional text counts as non-synthetic, E code and format approvals, F activation) with every entry blank; answering it in one reply resolves everything, and unanswered IDs stay unresolved. Code findings: the download is implicit inside training (no file allow-list, per-file hash record, host / redirect enforcement or destination parameter), so a verified fetch step is needed before the download phase; no metadata-query tool exists; a labels-only predictions file cannot be calibrated. Added `docs/THREAT_MODEL.md` section 18 (pre-approval analysis, controls that exist versus planned). `user_text_rules_v1` active, `SENTIMENT_MODEL_ENABLED=false`, no model / dataset / user text access, no package installed, no network call.

## Sentiment: consolidated approval form answered in part (2026-10-29)

Of the form's 55 IDs, the owner gave explicit values for three: **E1 approved** (a verified download / fetch step with file allow-list, per-file SHA-256 verification, host and redirect checks, explicit destination and rollback; fetch step only, built later with fakes, no network use, nothing built yet), **E2 approved** (calibration requires probability-bearing predictions; labels-only predictions stay descriptive-only and never `validated`), **F1 / R14 left unresolved**. No value was given for models, per-model items, the metadata query, D10 to D13 (still BLOCKED), R8 to R13 or the other code approvals, so 49 IDs stay `KEEP UNRESOLVED`; no recommendation was taken as an answer. All phases 2 to 7 are locked; a guard test (46 tests) holds the form to this state and to the dependency rules. Still needed in one list: A1 or A2 plus the 13 A3 items, B1 to B10, C1 to C5, D1 to D20, E3, E4, the E1 mechanism and the B9 tool. `user_text_rules_v1` active, `SENTIMENT_MODEL_ENABLED=false`, no model / dataset / user text access, no package installed, no code modified.

## Sentiment: Phase 2 gate presented again, nothing chosen (2026-10-29)

The owner restated the Phase 2 outcomes (A1, A2, 14 A3 items, B1 to B10) without choosing any, so all stay `KEEP UNRESOLVED` and Phase 2 is locked; nothing was inferred from recommendations, earlier proposals, model-card labels or silence. Recorded owner statements: the metadata query is read-only and downloads no weights, tokenizer files, **model configuration files**, datasets or training artifacts (the form's B3 candidate no longer lists `config`; a label order is read only after an approved download); an approved candidate with any unresolved A3 item never unlocks Phase 2; B2 to B10 follow B1. Open dependency question: Phase 2 exists to read the revision, file list and licences yet the gate needs them approved first, so the owner either supplies them from their own reading (Phase 2 then verifies) or approves an explicit rule making A3.1 to A3.8 provisional. The form now has a minimum-reply template. Guard tests: 95. E1 and E2 stay approved only as future build authorisations; C1 to C4 BLOCKED; C5, D1 to D20, E3, E4, F1 unresolved. `user_text_rules_v1` active, `SENTIMENT_MODEL_ENABLED=false`, no query, download, installation, dataset access or code change.

## Sentiment: Phase 2 circularity resolved (Option 2), metadata query approved with restrictions, still locked (2026-10-29)

Owner decisions: A3.1 to A3.8 (licences, data terms, commercial use, attribution / share-alike, suitability, exact immutable revision, permitted files) are provisional until Phase 2 verification; they authorise no download, tokenizer or config access, dataset access, training or inference and must be confirmed before Phase 4; A3.9 to A3.13 must be approved before Phase 2 unlocks. B1 and B3 to B10 approved as a read-only, anonymous, metadata-only query of the one selected model (API metadata, model-card text, licence metadata, file listing, revision metadata, redirect metadata; no weights, tokenizer files, `config.json`, datasets, training artifacts), max 10 requests, `huggingface.co` only, no redirect to a file host, sanitized metadata stored only in the approval report, seven stop conditions. B2 unresolved: no candidate selected. Phase 2 stays locked (no candidate, no B2, no A3.9 to A3.13) and the query tool is not built (E1 covers fetch only), so nothing was queried: 0 requests, no host, no field. Open points: name any redirect endpoint; two candidates have no recorded proposed revision to compare; building the query tool needs authorisation. Guard test: 52. E1 / E2 unchanged; C1 to C4 BLOCKED; C5, D, E3, E4, F1 unresolved. `user_text_rules_v1` active, `SENTIMENT_MODEL_ENABLED=false`.

## Sentiment: E1 / E2 / B9 built offline, still nothing executed (2026-10-29)

`training/sentiment/hub_fetch.py` (verified fetch step + restricted metadata query; standard library; its metadata query has since run once, see the next section; the download path has never run against a real host), probability-bearing predictions in `evaluate_sentiment_model.py` (E2) and `tests/backend/core/test_user_text_robustness.py` were added with tests (`test_hub_fetch.py` 97, `test_evaluate_frozen_mode.py` 29, robustness 12). No query, download, install, dataset or activation occurred. Consolidated form unchanged in status (11 APPROVE, 4 BLOCKED, 40 KEEP UNRESOLVED); every phase still locked; `user_text_rules_v1` is the production method, `SENTIMENT_MODEL_ENABLED=false`.

## Sentiment: Phase 2 unlocked for ProsusAI/finbert and run once; stopped (2026-10-29)

The owner's second reply selected A1 `ProsusAI/finbert` (A2 unresolved), B2, A3.9 to A3.13 (host `huggingface.co` only, destination outside the repository, SHA-256, cleanup, `OFFLINE_EVALUATION_ONLY`) and E5, and gave provisional A3.1 to A3.8 values (A3.5 share-alike and A3.6 suitability left unresolved). Phase 2 ran once: 2 anonymous requests to `huggingface.co`, no redirect, revision `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031` equal to the proposal, licence tag `cc-by-nc-sa-4.0`; the tool stopped (`malformed_response`) at the file listing (probable cause: the dot-file `.gitattributes`; fixed offline). No provisional field is confirmed; no file, tokenizer, config, weight or dataset was requested; the model card was not read. A re-run needs the owner's confirmation (B1 approved one query). Form: 19 APPROVE, 4 BLOCKED, 33 KEEP UNRESOLVED over 56 IDs; Phases 3 to 8 locked; `user_text_rules_v1` active, `SENTIMENT_MODEL_ENABLED=false`.

## Sentiment: Phase 2 metadata verification completed for ProsusAI/finbert (2026-10-29)

The owner-approved re-run made 3 requests (5 of 10 in total), `huggingface.co` only, no redirect, no stop. Revision `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031` confirmed; licence CC BY-NC-SA 4.0 confirmed from the tag, front matter and the card's licence section; listing of 10 files obtained (only `model.safetensors` has an API hash; three pickle-capable files exist and must never be fetched). Results: model licence, commercial restriction, attribution, revision CONFIRMED; tokenizer licence, training-data terms, personal-finance suitability INSUFFICIENT EVIDENCE; share-alike scope and the permitted file list UNRESOLVED; none REJECTED. These are not owner approvals: the form still has 19 APPROVE, 4 BLOCKED, 33 KEEP UNRESOLVED over 56 IDs and Phases 3 to 8 stay locked. Nothing downloaded or installed; `user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`.

## Sentiment: FinBERT A3.1 to A3.8 awaiting explicit choices (2026-10-29)

The owner's latest brief listed accept / reject / keep-unresolved options for each field and chose none, so nothing was approved. Recorded (not approved): the proposed five-file allow-list and the never-download list; recorded (clarification of approved A3.11): the four files without an API hash are hashed independently at the first approved download. Phase 3 and 4 stay locked.

## Sentiment: owner statements A3.1 / A3.4 / A3.5a / A3.7 / A3.8 recorded; first-download controls still closed (2026-10-29)

Approved from the owner's statement: A3.1 and A3.4 (non-commercial offline evaluation only, not legal clearance), A3.7 (revision confirmed), A3.8 (five-file allow-list; a list only). Still unresolved: A3.2, A3.3, A3.5b, A3.6, A2, C1 to C4 (blocked), C5, D1 to D20, E3, E4, F1. Form: 23 APPROVE, 4 BLOCKED, 29 KEEP UNRESOLVED over 56 IDs. Nothing downloaded; Phases 3 to 8 locked.

## Sentiment: Phase 3 brief received; blocked by C4 (TASK-CERT-1), nothing created (2026-10-29)

Recorded from the owner: A3.5b rejected until the legal scope is verified (A3.5 = REJECT), A3.6 approved as an offline research candidate only, C1 Path B, C2, C3, C5 approved (paths under `C:\Users\Administrator\.copilot\`), C4 decided as "complete TASK-CERT-1 first". TASK-CERT-1 is not done (project env `certifi` 2026.7.22, `pip` 26.2.1) and no approved wheels exist, so no environment was created and nothing installed. Form: 28 APPROVE, 1 REJECT, 1 BLOCKED, 26 KEEP UNRESOLVED. Phases 3 to 8 locked. The Path B trainer change is documented, not applied.

## Sentiment: Phase 3 offline preparation done; waiting on one consolidated decision (2026-10-29)

Prepared offline: `training/sentiment/local_model_dir.py` (Path B loader, unwired, 56 synthetic tests, 22/22 mutations), the S1 pin-list guard (executed 35-wheel list with `setuptools==81.0.0` is authoritative; early 84.2.1 table superseded), TASK-CERT-1 facts (not completable offline). Waiting on the owner's one decision request in the consolidated form (C4, PyPI retrieval, S1 set, Path B wiring, A3.2/A3.3/A3.5b, C5 retention, D/E items). Form unchanged: 28 APPROVE, 1 REJECT, 1 BLOCKED, 26 KEEP UNRESOLVED. Phases 3 to 8 locked.

## Sentiment: S1 validated in a disposable environment; Path B wired offline; TASK-CERT-1 stopped (2026-10-29)

The 35-wheel S1 list was retrieved from PyPI (hosts `pypi.org`, `files.pythonhosted.org`), verified 35 of 35, installed with `--require-hashes` in `...\wealthpilot-finbert-eval-venv`, validated (CPU-only torch 2.13.0+cpu, `pip check` clean, TensorFlow/PyTorch coexistence, 1124 tests passed, 2 skipped) and deleted. TASK-CERT-1 stopped before any change (no `pip` wheel in the lock; missing approval: a named `pip` version and hash); project `certifi` 2026.7.22 and `pip` 26.2.1 unchanged. Path B is wired offline into the trainer (`--local-model-dir`) and the evaluation script (`--local-model`); nothing downloaded; production unchanged. Hash table: dependency report, section S.

## Sentiment: TASK-CERT-1 metadata phase (2026-10-29)

PyPI metadata (2 requests): the only `pip` release after 26.2.1 is 26.2.2 (`pip-26.2.2-py3-none-any.whl`, SHA-256 `fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70`, not yanked), but its vendored `certifi` cannot be verified from PyPI metadata, so the version stays unresolved and TASK-CERT-1 stays BLOCKED. Policy: `certifi` 2026.10.23 only together with the approved `pip`, never alone; project `setuptools`, TensorFlow, Keras, NumPy unchanged; S1 environment separate. Nothing installed.

## Sentiment: TASK-CERT-1 completed (2026-10-29)

Project environment: `pip` 26.2.1 to 26.2.2 and `certifi` 2026.7.22 to 2026.10.23 (hash-pinned, nothing else changed; `setuptools` 65.5.0, TensorFlow 2.17.0, Keras 3.15.1, NumPy 1.26.4 unchanged); pip's vendored `certifi` is 2026.10.19 (verified from the hash-checked wheel); `pip check` clean; 1301 tests passed. C4 is APPROVE (completed). Rollback backup at `...\.copilot\wealthpilot-taskcert-rollback`. Phase 4 (any download) is still locked: A3.2, A3.3 unresolved, A3.5b rejected, plus D1 to D20, E3, E4, R14.

## Sentiment: end-to-end brief received; one legal form and one dataset form issued, nothing approved (2026-10-29)

The consolidated form now holds the single request for A3.2, A3.3, A3.5b and the dataset gate (D1 to D20, mapped from the brief's 20 items). No value was supplied, so FinBERT stays undownloaded, no dataset exists, no evaluation ran, R14 untouched. Form unchanged: 29 APPROVE, 1 REJECT (A3.5), 0 BLOCKED, 26 KEEP UNRESOLVED. Rollback backup retained.

## Sentiment: owner reply recorded - four direct dataset approvals, all legal and value items unresolved (2026-10-29)

Approved: D6 (two annotators, one adjudicator), D7 (blinding), D9 (300 held-out, 75 per class), D15 (coverage 0.70, abstention 0.30). Unchanged: A3.2, A3.3 unresolved, A3.5b rejected, D1 to D5, D8, D10 to D14, D16 to D20, E3, E4, F1 unresolved. Form: 33 APPROVE, 1 REJECT, 0 BLOCKED, 22 KEEP UNRESOLVED. FinBERT still undownloaded, no dataset, no evaluation, R14 untouched. Production: `user_text_rules_v1`, `SENTIMENT_MODEL_ENABLED=false`.

## Sentiment: third owner reply recorded - D4 and D8 approved, all legal and value items unresolved (2026-10-29)

Newly approved: D4 (privacy and de-identification; verifier still to be named) and D8 (agreement and adjudication). Unresolved: A3.2, A3.3, D1 to D3, D5, D10 to D14, D16 to D20, E3, E4, F1; A3.5b rejected. Form: 35 APPROVE, 1 REJECT, 0 BLOCKED, 20 KEEP UNRESOLVED. FinBERT undownloaded, no dataset, no evaluation, R14 untouched. Production: `user_text_rules_v1`, `SENTIMENT_MODEL_ENABLED=false`.

## Sentiment: fourth owner brief recorded - A3.2 accepted, nine dataset / alignment decisions, D11 method implemented (2026-10-29)

Approved: A3.2 (non-commercial offline evaluation only; not legal clearance), D3 (fictional text stays synthetic; never `validated`), D10 (600 / 100 / 300), D11 (normalized-text hash; character 5-gram Jaccard at or above 0.90), D12, D13, D17, D18, E4 (keep all six differences). Still open: A3.3, A3.5b rejected, D1, D2, D5 (kept `v0-draft`), D14, D16 (no storage location), D19, D20, E3, R14. Form: 44 APPROVE, 1 REJECT, 0 BLOCKED, 11 KEEP UNRESOLVED. `frozen_evaluation.py` now uses the approved duplicate method. To do before any real data: name the storage location, add the register fields, wire D13 for the frozen path. FinBERT undownloaded, no dataset, no evaluation. Production: `user_text_rules_v1`, `SENTIMENT_MODEL_ENABLED=false`.

## Sentiment: participant-register validator and D13 calibration implemented offline (2026-10-30)

Added `training/sentiment/participant_register.py` (offline validator, sanitized errors), D13 temperature calibration in `metrics.py` (calibration split only; log-probabilities, no invented logits), and frozen-manifest schema 2 (register / verifier / consent / calibration-split hashes, temperature-policy version, data status; the register is a sixth input; CLI flag `--participant-register`; candidates may answer the calibration split). No decision changed: 44 APPROVE, 1 REJECT, 0 BLOCKED, 11 KEEP UNRESOLVED; A3.3, D1, D2, D5, D14, D16, D19, D20, E3, R14 unresolved, A3.5b rejected; no real data, register or manifest; FinBERT undownloaded. Production: `user_text_rules_v1`, `SENTIMENT_MODEL_ENABLED=false`.

## Sentiment: fifth owner brief recorded; deletion policy enforced; one consolidated approval table issued (2026-10-30)

No status changed (44 APPROVE, 1 REJECT, 0 BLOCKED, 11 KEEP UNRESOLVED). The owner's "D14" and "D19" are the form's D8 and D17 (already approved, now specified); E3 is approved for schema-2 offline implementation only. The participant-register validator enforces the deletion policy (project-owner authorization, retention only until evaluation, audit and R14, only hashes, aggregates and decision records kept, rollback never restores raw text). New guards: no fixture can pass as real evidence, no real FROZEN manifest or register exists. The single approval table the end-to-end brief asks for is in the consolidated form. FinBERT undownloaded, no dataset, no evaluation. Production: `user_text_rules_v1`, `SENTIMENT_MODEL_ENABLED=false`.

## Sentiment: phase closed as an offline rules-baseline phase (2026-10-30)

> The offline rules-based sentiment phase is complete. Transformer evaluation, real dataset creation and production activation are deferred because the required legal, dataset, storage and activation approvals are unresolved.

Owner values: A3.3, D1, D2, D16, R14 unresolved; A3.5b rejected; D5 kept `v0-draft`; D20 REJECTED (no real data creation, collection, labeling, storage or manifest this phase); E3 schema-2 offline only; E4 keep all six differences documented. Form: 44 APPROVE, 2 REJECT, 0 BLOCKED, 10 KEEP UNRESOLVED. The requests are closed, not to be repeated; a new phase needs a new approval request. Production method `user_text_rules_v1`; `SENTIMENT_MODEL_ENABLED=false`; real model downloaded: no; real dataset created: no; real evaluation run: no; production activation: no; intensity regression: disabled; blockchain / ledger sentiment payload: none. A3.2 stays approved only for non-commercial offline evaluation; D3: fictional text is synthetic and never `validated`.

## Sentiment: final-state verification (2026-10-30)

Verified at runtime and by `tests/backend/core/test_sentiment_final_state.py` (12 tests), with 1,652 offline tests passing and 0 external connection attempts. Production method `user_text_rules_v1`; `SENTIMENT_MODEL_ENABLED=false`; real model not downloaded; real dataset not created; real evaluation not run; production activation not performed; intensity regression disabled; ledger / blockchain sentiment payload none. The offline rules-based phase is complete; real model, dataset, evaluation and activation work remain deferred.

## Financial Behaviour & Sentiment demonstration mode (2026-10-31)

Added `POST /api/demo/financial-behaviour` (`api/routers/demo.py`, `api/services/demo_behaviour_service.py`; off unless `DEMO_MODE_ENABLED=true`, default false, no database session, no logging, no ledger) and the frontend `?demo=true` view (`components/financial-health/demo-financial-behaviour*.tsx`, `lib/demo-mode.ts`, `lib/demo-build.ts`; honoured only by a dev server or `VITE_DEMO_MODE=true`). Six fictional months; every ratio and change comes from `compute_behaviour_features`; the sentence goes through `analyse_user_text` (`user_text_rules_v1`). `build_insight` was split so the customer route and the demo share `build_insight_from_features` (behaviour unchanged). The sign-in redirect now keeps the requested page's query. Production state unchanged: `user_text_rules_v1`, `SENTIMENT_MODEL_ENABLED=false`, intensity null, no ledger payload. Tests: `tests/backend/api/test_demo_financial_behaviour.py`, frontend `tests/demo-mode.test.ts` and `tests/demo-financial-behaviour-view.cases.tsx` (fixtures from `scripts/export_demo_fixtures.py`), mutations DM1 to DM12.

## Financial Behaviour page: real records, family demo, simple-English sentiment (2026-11-02)

The real page now has the overview, the profile's months (chart and table), investment behaviour, the spending-pattern state, the individual loan / EMI wording and the optional note in simple English (technical reading in an optional disclosure); `?demo=family` shows a fictional family (`POST /api/demo/family-financial-behaviour`, same `DEMO_MODE_ENABLED` guard, no database). The existing behaviour calculation gained an **income month-over-month change** (`income_change`, the same `_change` helper) and an `income_trend` finding; `household_summary_service.build_summary_response` was extracted so the demo's household totals are the real engine's output. New files: `lib/plain-sentiment.ts`, `investment-behaviour.ts`, `spending-pattern.ts`, `behaviour-overview.ts`, `components/financial-health/behaviour-sections.tsx`, `financial-behaviour-real.tsx`, `demo-family-behaviour*.tsx`. Production state unchanged: `user_text_rules_v1`, `SENTIMENT_MODEL_ENABLED=false`, intensity null, no ledger payload.

## Reaching the Financial Behaviour demonstration (diagnosed and fixed 2026-11-03)

Root cause: not missing data. The demo route and page worked, but the demo flag was lost on the way in (the Use Family Demo sign-in discarded the requested address; the sidebar link drops the query), a build or value that did not honour the flag silently showed the normal empty page, and a 404 from the demo route read as "not created yet". Fixed: `destinationAfterLogin` (every sign-in returns to the requested address), `behaviourLinkTarget` (the sidebar keeps a demonstration), `demoRequest` plus `DemoRequestNotice` ("Demonstration mode is not active"), a 404 explained as the flag or an older backend, and a development-only `DevDemoHint` on the real empty page. Verified in headless Chrome against a running dev server, a production-style build and a backend with the flag off. Production state unchanged: `user_text_rules_v1`, `SENTIMENT_MODEL_ENABLED=false`, intensity null, no ledger payload.

## Transformer enablement requested; pre-flight blocked (2026-11-03)

`scripts/sentiment_preflight.py` (read-only, no network, no model, no text; `--json` available) reports which gate blocks enabling the Transformer: legal (A3.3, A3.5b), dependencies (four packages not installed), dataset (D1, D2, D5, D14, D16, D19 unresolved, D20 rejected, no frozen manifest), evaluation (E3, no calibration), artifact (no `model.safetensors`) and activation (R14). Exit status 1 until all pass; a pass would still not enable anything. No code path was changed; production stays `user_text_rules_v1`, `SENTIMENT_MODEL_ENABLED=false`.

## Pretrained FinBERT + RoBERTa research comparison (ADR-053, 2026-11-03)

Implemented the research-only, display-only comparison in `backend/wealthpilot/core/sentiment/` (registry, normalization, adapter, comparison, inference_service), the optional `transformer_research`
object on `POST /api/profiles/{id}/personalized-insights`, additive fields on `GET /api/sentiment-model/status`, the panel in `behaviour-sentiment-view.tsx`, `scripts/write_pretrained_manifest.py` and
`docs/sentiment/*`. Exact revisions read 2026-11-03: FinBERT `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031` (cc-by-nc-sa-4.0 -> `blocked_by_licence`), Twitter-RoBERTa `3216a57f2a0d9c45a2e6c20157c20c49fb4bf9c7`
(cc-by-4.0, but no `model.safetensors` published -> `no_safetensors_published`, and no approval recorded). Neither can run. No package installed, no weights downloaded, no dataset, no training, no
evaluation. Tested with stand-in backends only. Production: `user_text_rules_v1`, `SENTIMENT_MODEL_ENABLED=false`, `SENTIMENT_TRANSFORMERS_ENABLED=false`, confidence unavailable, intensity null.

## Replacement candidates reviewed; both blocked (ADR-054, 2026-11-03)

Reviewed `tooshlegacy/distilbert-financial-tweet-sentiment` (`ba66b6a858cc775dc9e78d773c437b7e984fd5fc`) -> `blocked_by_provenance` (no licence file or author; tweets via the Twitter API with undocumented annotation) and `Horizon-Labs/multilingual-sentiment-small`
(`e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac`) -> `blocked_by_approval` (web-crawl + LLM-synthetic training text, LLM labels, transformers-5 config). Neither downloaded or installed. The active registry is unchanged (FinBERT / Twitter-RoBERTa, both gated off); reviews are code constants in
`core/sentiment/reviews.py`, exposed as `reviewed_candidates` on the status endpoint. The normaliser now maps Bullish/Bearish. Production: `user_text_rules_v1`, both flags false, confidence unavailable, intensity null.

## Horizon approved for research inference only; compatibility investigated (ADR-054 addendum, 2026-11-04)

The owner approved `Horizon-Labs/multilingual-sentiment-small` @ `e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac` for research inference only (disclosed web-crawl + LLM-generated training data and no human-validated labels accepted). Review verdict `approved_for_research_inference`; the financial `tooshlegacy` model stays `blocked_by_provenance`, the financial slot is empty, A3.3 / A3.5 / D20 / F1 unchanged.
Findings: `transformers` 4.57.1 is not compatible (silent rope-theta error); `transformers` 5.17.0 required; ONNX Runtime plausible but unverifiable and needs a policy extension; installed TensorFlow 2.17 / Keras 3.15.1 / numpy 1.26.4 / protobuf 4.25.9 unaffected so far (no dry-run done). Nothing installed, downloaded or run; registry unchanged; production `user_text_rules_v1`, `SENTIMENT_TRANSFORMERS_ENABLED=false`. Plan: `docs/sentiment/horizon_runtime_plan.md`.

## Stage A executed: Horizon real CPU inference verified in an isolated environment (2026-11-04)

Isolated venv `C:\Users\Administrator\.copilot\wealthpilot-stageA\venv` (outside the repo; hash-pinned lock in `docs/sentiment/stage_a/`), model files in `C:\Users\Administrator\.copilot\wealthpilot-approved-models\horizon-multilingual-sentiment-small` (checksum-verified against the repository SHA256SUMS). Real inference ran on fictional sentences: INFERENCE_VERIFIED for the reference stack only; no accuracy claim. Application `.venv`, TensorFlow, registry, settings and production untouched. Test work: the ADR-053 `transformer_research` field had broken two API tests and the saved insight fixtures (fixed: fixtures regenerated, key-set assertion made additive); a preflight test and a frontend test were updated for state the approved download changed; database setup errors seen in the hosted test database were transient connection drops. Stage B unauthorised. Report: `reports/sentiment_transformer_stage_a_report.md`.

## Stage A finalised; database-boundary incident recorded (2026-11-04)

Final Stage A record: `docs/sentiment/stage_a/STAGE_A_COMPLETION_REPORT.md`. Nine directory runs: 4,294 passed, 1 failed (the unrelated GDELT scaffold false positive), 9 skipped, 0 errors; about 546 API tests before `test_profiles.py` were not re-run in the final chain. **Incident:** the `agents` directory was run with plain `pytest`, which opened sessions on the development database `neondb` (access confirmed; read-only by test design; application-level writes not fully verified; state not verified; modification UNKNOWN) and made three rate-limited live Gemini calls; the project's `scripts/run_isolated_db_tests.py` was not used. Do not re-run `agents`; use the isolated runner for database-backed suites. Horizon real inference remains verified only in the isolated environment; production, registry and `.venv` unchanged; Stage B not started.

## Stage B1 runtime readiness report written (2026-11-04)

`docs/sentiment/stage_b/STAGE_B1_RUNTIME_READINESS_REPORT.md`: recommends transformers 5.17.0 + CPU torch + safetensors (conditional on a TensorFlow/torch coexistence test); resolver dry-run against the project `.venv` (nothing installed) would add 16 packages and change `setuptools` 65.5.0 -> 84.2.1; the ADR-053 two-slot comparison cannot use a single approved model; fault injection found unguarded load-time exceptions, a model load on `GET /status` and a load inside the global lock. Investigation only: nothing installed, registry, flags, `.venv` and schemas unchanged; B2 not started and needs the owner's decisions (report section 14).

## Stage B2.1: runtime installed in the project .venv, then STOPPED on a setuptools constraint (2026-11-04)

`docs/sentiment/stage_b/STAGE_B2_1_RUNTIME_COEXISTENCE_REPORT.md` and `docs/sentiment/stage_b/evidence/` (incl. `RECOVERY_RECORD.md`). Installed 15 packages plus a `setuptools` 65.5.0 -> 84.2.1 upgrade into the project `.venv` (transformers 5.17.0, torch 2.15.0+cpu, tokenizers 0.23.3, safetensors 0.8.0, huggingface-hub 1.33.0 and dependencies; hash-pinned); `pip check` clean; TensorFlow 2.17.0, Keras 3.15.1, NumPy 1.26.4, protobuf 4.25.9 unchanged. `setuptools` 84.2.1 removed `pkg_resources`, which breaks `tensorboard.default` / `tensorboard.program` / `tensorboard.data.server_ingester` (unused by the project); the project had already recorded "must stay below 82" (approved pin 81.0.0) and B1 missed it. Coexistence tests, market-model and Horizon-load tests NOT RUN; awaiting the owner's choice (A: `setuptools==81.0.0`, B: accept, C: roll back). Production, registry, flags, lifespan, schemas and database untouched; B2.2 not started.

## Setuptools recovery, coexistence verified, role-slot research architecture (ADR-055, 2026-11-05)

`docs/sentiment/SENTIMENT_*.md` (architecture, implementation, privacy/security, model card, evaluation, API reference, governance, test report, decision log) and `docs/sentiment/SENTIMENT_FINAL_COMPLETION_REPORT.md`. The owner-approved `setuptools==81.0.0` was installed (hash-pinned; TensorBoard `pkg_resources` modules import again; `pip check` clean; TF 2.17.0 / Keras 3.15.1 / NumPy 1.26.4 / protobuf 4.25.9 unchanged). TensorFlow and PyTorch coexist in the project `.venv` in both import orders (peak RSS 1.3-1.6 GB; Horizon load about 3.5 s; Horizon logits identical to Stage A; the backend itself never imports TensorFlow). The research comparison now has role slots `financial` / `general`; **Horizon stays `pending_owner_approval` (not registered), so both slots are empty, the flag stays off, `user_text_rules_v1` remains the production method**. Lifecycle guards: non-loading status, per-candidate non-blocking load lock (`loading`), 30 s timeout breaker, fixed reason codes, a never-raise service boundary, optional `SENTIMENT_TRANSFORMERS_THREADS`. Rules baseline got a 42-test characterization suite. The `transformer_research` JSON shape changed (never enabled). `INFERENCE_VERIFIED` through the adapter is NOT claimed: the opt-in real-weights smoke test is skipped until the owner approves placing the verified files. **Open item (unrelated to sentiment code, unexplained):** an intermittent native `access violation` appears in `tests/training` (TensorFlow/xgboost/joblib processes; torch not imported in the crashing process; each sub-directory passes on re-run; one clean sample before the install). `tests/backend/core/test_task_cert_1_state.py` now accepts setuptools 65.5.0 or the approved 81.0.0. No accuracy, calibration or human-validation claim exists; D20 rejected, A3.3 / A3.5 / E3 / F1 unchanged; Stage B2.2 not started.

## R1 / R2 / R3 executed on the owner's instruction (ADR-056, 2026-11-07 to 2026-11-09)

`docs/sentiment/R1_*.md`, `R2_*.md`, `R3_*.md`. **Horizon is now REGISTERED as the `general` research candidate** (still research only: flags off, `user_text_rules_v1` is production, financial slot empty, `production_activation: not_activated`). The eight approved files sit in the git-ignored `models/sentiment_pretrained/horizon/` with a manifest (`.gitignore` now ignores that whole directory); the opt-in `WEALTHPILOT_REAL_WEIGHTS_SMOKE=1` test passed (9 tests): adapter logits equal the Stage A logits, one softmax, first call including hashing about 10 s, warm median about 25 ms, peak working set about 1.3 GB (this machine). Unit tests are made hermetic by a fixture that points the default model directory at an empty folder. **The `tests/training` native crash is explained**: the CUDA-enabled XGBoost wheel probes the NVIDIA driver (hybrid-graphics laptop, driver 32.0.15.5597); `nvdxgdmal64.dll` is loaded then unloaded 21 ms later and a late callback executes it, killing the process with `0xC0000005` (14 of 16 unprotected runs; 0 of 8 with the DLL held mapped). It is independent of the Transformer packages. Whole-directory `tests/training` runs are unreliable on this machine; run sub-directories. No mitigation applied (options in the R3 report). Comparison environments remain in `C:/Users/Administrator/.copilot/wealthpilot-r3/`.

## R4 test-only NVIDIA DLL guard and open item U1 (2026-11-09 / 2026-11-10)

Supersedes "No mitigation applied" in the R1 / R2 / R3 entry above. `tests/training/nvidia_dll_guard.py` + `tests/training/conftest.py` (+ `test_nvidia_dll_guard.py`) hold one reference to the validated driver DLL for the pytest process (owner option 4; test-only; off with `WEALTHPILOT_NVIDIA_DLL_GUARD=0`). Whole `tests/training`, project `.venv`: guard off 4 of 5 runs crashed (`0xC0000005`), guard on 0 of 5 (796 passed / 2 skipped each). It is a machine-specific mitigation, not proof the driver defect is fixed; it protects only runs that collect `tests/training/`; no dependency, XGBoost, driver, GPU-preference or production change. **Open item U1 (unresolved): backend XGBoost exposure.** The served risk model is the random forest and no backend module imports `xgboost` (static check only); dynamic confirmation and transitive imports are unchecked. Details: `docs/sentiment/R3_TRAINING_NATIVE_CRASH_INVESTIGATION.md` sections 10-11.

**U1 update (2026-11-10):** the backend-exposure item was investigated read-only (`docs/sentiment/r_series/U1_BACKEND_XGBOOST_RUNTIME_EXPOSURE_REPORT.md`): 37 import runs, none imports `xgboost` from the served closure and none maps an NVIDIA module; latent path `autogen` -> `flaml` -> `xgboost` exists but only via `run_strategy_debate`, which nothing calls. Classification: no exposure observed in tested imports (not "safe"; XGBoost use, served requests and `warm_model_caches` NOT RUN).
