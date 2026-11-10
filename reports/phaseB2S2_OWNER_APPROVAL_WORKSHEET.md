# WealthPilot AI — Sentiment Pipeline: Owner Approval Worksheet

Written for: the project owner. Source of truth: `reports/phaseB2S2_SENTIMENT_COMPLETION_REPORT.md` (section 9), with `phaseB2S2_8F_owner_decision_register.md`, `phaseB2S2_8G_owner_decision_worksheet.md`,
`phaseB2S2_8H_owner_decision_intake.md`, `phaseB2S3_sentiment_design_feasibility.md` and the live policy table (read, not modified). Date: 2026-10-20 (UTC).

**How to use.** Fill only the lines you decide. **A blank answer is unresolved. `DEFER` is not approval. Approving one line approves nothing else.** Items marked `RECOMMENDATION — NOT APPROVAL` are suggestions only.
Existing IDs are kept; sub-IDs (E1a…) split permissions that must not be bundled.

**State when written:** branch `master`, HEAD `71b363f`, 0 staged, 49 tracked modifications, 170 untracked (169 before this worksheet). Policy table: 8 of 8 required policies block, none applied. The offline accounting layer is implemented and verified; scoring, polarity validation, production features and evaluation are blocked.
Engineering completion (code that works and is tested) is **not** scientific validation (independent evidence that the scores mean something and forecast something); this worksheet covers both.

## Already resolved (not asked again)

| Item | Resolution | Record |
| --- | --- | --- |
| Source availability rule | Availability = `max(nominal, verified Last-Modified) + 15 min`; a page publication time is never proof of availability | implemented in the adapters/availability code; `features.py` docstring; completion report §5 |
| Delayed empty batch (OD-08) | A delayed empty batch is not verified no-news | S2.8D, implemented; not reopened |
| Coverage denominator and unreconciled slots (OD-10) | Denominator is the full expected grid; a processed slot failing reconciliation, or lacking a result, is not covered; report-only coverage block carried by the aggregator | owner decisions of S2.8I/S2.8J; `phaseB2S2_8J_...md` |
| Late-arrival *mechanism* (C-min) | Detect earlier-nominal batches by verified availability; incomplete if unresolved; window never extended | S2.8C. Only the **duration** is open (OD-01) |
| Unknown near-empty is neither complete nor no-news; explicit near-empty distinct from missing | selected principle | S2.8B/D records. The **mapping** is open (OD-04) |
| Repeats retained; similarity is not identity | selected principle | S2.8B record. The **rules** are open (OD-11) |

## A. Source accounting and coverage

| ID | Question (plain English) | Status | Evidence | Why it matters / blocks | Options documented | Blank = |
| --- | --- | --- | --- | --- | --- | --- |
| OD-01 | How many days/hours before the analysed window must we look for batches that arrive late into it, or should we measure lateness first? | UNRESOLVED (caller-supplied; no duration anywhere) | 8C, 8F | No completeness claim beyond the declared range; sizes the acquisition (E7) | fixed duration · measure first on contiguous data · caller-supplied indefinitely. RECOMMENDATION — NOT APPROVAL: measure first | late arrivals older than the declared range stay invisible |
| OD-03 | Keep the near-empty detector at 14 days / at least 7 observations / below 10% of the median? May a partial lookback decide? | PROVISIONAL | 8B, 8E; `near_empty.py` | False positives lose quiet slots; false negatives hide degraded batches | adopt · change values · drop · day-type baselines. RECOMMENDATION — NOT APPROVAL: keep provisional, compare with the observed flag on contiguous data | detector stays informational |
| OD-04 | When a complete interval has NULL near-empty flags: stay undecided, become unusable, or be usable only under an applied rule? | UNRESOLVED (principle selected, mapping not) | 8B, 8F | decides how much data is lost (first ~7 days of a run and ~7 days after a long outage) | the three listed. RECOMMENDATION — NOT APPROVAL: stay undecided until OD-02/03 | stays undecided; NULL is never false |
| OD-05 | Confirm: explicit near-empty is uncovered in the primary run. Do you want a sensitivity variant that treats it as covered? | PROVISIONAL (primary only implemented) | 8B, 8F | sensitivity reporting | confirm/change primary · variant yes/no | primary stays; no variant |
| OD-02 | Are 0.75 (primary) and 0.50 / 0.90 (sensitivity) adopted, changed or dropped? May `source_coverage_threshold` be applied? A ratio never proves valid sentiment, polarity or no-news. | PROVISIONAL | 8B, 8F | usability states other than "undecided"; one of the 8 blocking policies | adopt/change/drop each value; apply yes/no | thresholds informational; gate keeps blocking |
| OD-06 | Is there a cap on consecutive slots without valid evidence (a ratio can hide a long outage)? | UNRESOLVED | 8F | outage handling | none · number with unit, blocks · number, flags only. RECOMMENDATION — NOT APPROVAL: decide together with OD-02 | longest runs reported, no limit |
| OD-07 | What share of eligible records must be scored for a theme-day to count, or report only? | UNRESOLVED; needs E1 | 8F; policy `UNRESOLVED_NOT_APPLIED` | scoring coverage is separate from source coverage | threshold · report only | blocks features |
| OD-09 | Confirm the shared state names (`SourceCompleteness`, `IntervalUsability`, `ThemeEvidence`, `ResultAvailability`, `SlotAccount`, `NearEmpty`, exclusion reasons) or list renames | PROVISIONAL (assistant design) | 8D, 8E | renaming later changes digests | confirm · rename list | names cannot be frozen |
| OD-13 | Should `n_slots_near_empty` exclude processed-but-unreconciled near-empty slots, as the shared coverage block does? | UNRESOLVED (found in the completion report; no decision covers it) | completion report §5/§9 | two counts disagree in that edge case | yes (align) · no (leave). RECOMMENDATION — NOT APPROVAL: align | unchanged; discrepancy documented |

### A — Owner entries (status per row)

Entered 2026-10-20 from the owner's instruction; statuses updated the same day on the owner's instruction. The table above is the original record and is **not edited**; this subsection carries the current status of each Section A entry.
**Status meanings.** `OWNER-CONFIRMED` = the owner confirmed that exact decision (OD-01, OD-04, OD-05, OD-06, OD-07). `PROVISIONAL — INFORMATIONAL, NOT APPLIED` = the numerical values are kept as provisional reporting values, and neither the policy nor the detector is an authoritative rule (OD-02, OD-03).
`DEFERRED` = not decided, not frozen (OD-09). `OWNER-CONFIRMED — ALIGN` (OD-13) = the owner confirmed and the aligned count is implemented; it applies no policy gate. No Section A entry remains a pending proposal. **Confirmation records a decision; it does not apply a policy.** No policy status in the registry changed, nothing here was implemented, and all 8 required policy gates still block.
Nothing here covers Sections B–F.

| ID | Proposed entry | Marker | Effect on the implementation today | Needs before it can be applied |
| --- | --- | --- | --- | --- |
| OD-01 | **MEASURE FIRST.** No fixed late-arrival lookback duration is chosen. | OWNER-CONFIRMED | none; `earlier_batches_from` stays caller-supplied | contiguous data to measure lateness (acquisition is a separate, unapproved decision, E7) |
| OD-02 | Keep **0.75** as the proposed primary source-coverage threshold and **0.50 / 0.90** as sensitivity values. All **informational**; the policy is **not** applied. | PROVISIONAL — INFORMATIONAL, NOT APPLIED | none; values already exist as provisional reporting configuration | a separate decision to apply `source_coverage_threshold` |
| OD-03 | Keep the detector at **14 calendar days, at least 7 valid observations, below 10% of the median**, all **provisional**. Compare against observed near-empty flags when suitable contiguous data exists. Not an authoritative decision rule. | PROVISIONAL — INFORMATIONAL, NOT APPLIED | none | contiguous history for the comparison |
| OD-04 | Keep **NULL** near-empty evidence **undecided**. NULL is never false and never verified no-news. | OWNER-CONFIRMED | none; matches current behaviour | — |
| OD-05 | Explicitly near-empty slots stay **uncovered** in the primary calculation. **No sensitivity variant yet.** | OWNER-CONFIRMED | none; matches current primary behaviour | — |
| OD-06 | **Report** consecutive missing/uncovered runs only. **No blocking cap yet.** | OWNER-CONFIRMED | none; runs are already reported | — |
| OD-07 | **Report** scoring coverage only. **No threshold chosen or applied.** | OWNER-CONFIRMED | none; the aggregator already reports `scoring_coverage` with no threshold | an approved scorer (E1) before any scoring coverage exists |
| OD-09 | **Defer** freezing the shared state vocabulary. | DEFERRED — vocabulary not frozen | none; names stay provisional | — |
| OD-13 | **Align** `n_slots_near_empty` with the shared coverage report so processed-but-unreconciled slots are handled consistently. | **OWNER-CONFIRMED — ALIGN** (records the decision; **does not apply any policy gate**) | implemented in `features.py::_assess_day`: a processed slot that fails reconciliation, or has no reconciliation result, no longer counts in `n_slots_near_empty`; see `reports/phaseB2S2_OD13_near_empty_count_alignment.md` | — |

**Source-record check.** No existing record contradicts any entry above. Three points for the owner's awareness, none a conflict:
(1) the aggregator's configured `coverage_threshold` (test config 0.75) already gates `coverage_status` (`ok` / `insufficient_coverage`), reachable only after the policy guard passes — this is existing provisional behaviour, and "informational" in OD-02 refers to the shared coverage report and the
policy, not to that gate; (2) OD-13 is the only entry that, once confirmed, changes behaviour (only `n_slots_near_empty` in the edge case of an unreconciled near-empty slot); (3) the entries for OD-01 and OD-03 depend on contiguous data that does not exist locally.

## B. Article eligibility and story counting

| ID | Question | Status | Evidence | Blocks | Options documented | Blank = |
| --- | --- | --- | --- | --- | --- | --- |
| E3 | Which candidate records are eligible for scoring (text status, language, duplicates, company items), and what exactly turns a candidate into a scored record? | BLOCKED | completion report §3 row 6 | candidate → `ArticleRecord` conversion, features | none documented beyond the existing candidate fields | no conversion |
| OD-11a | May repeated URLs / title hashes / similar titles be linked into a story, and at what evidence level? | UNRESOLVED | 8B, 8F | story IDs, unique-story metrics | none · link by canonical URL · by title hash · similarity. RECOMMENDATION — NOT APPROVAL: none until the unit is chosen | counting only; no story identity |
| OD-11b | May a story be counted in more than one interval? | UNRESOLVED | 8F | cross-interval uniqueness policy (blocking) | allowed · forbidden | blocks |
| OD-11c | Primary counting unit | PROVISIONAL ("every eligible record + repetition sensitivity") | 8B | feature meaning | confirm · other | features cannot be authoritative |

### B — Owner entries (status per row)

Entered 2026-10-20 on the owner's instruction. The table above is the original record and is not edited. **Each row records a decision and its implementation; none applies a policy gate** (`deduplication_and_story_updates` stays `SELECTED_PROVISIONAL_NOT_APPLIED`, and all 8 required gates still block).

| ID | Owner decision | Status | Implemented in |
| --- | --- | --- | --- |
| E3a | Score a candidate only when `text_status == ok` and at least one theme flag is set; same-batch duplicates included | OWNER-CONFIRMED | `scored_records.scoring_inputs` |
| E3b | Non-theme candidates stay candidates with the reported reason `not_theme_relevant` (not converted); text-invalid theme candidates stay `unavailable` with their existing `text_*` reason | OWNER-CONFIRMED | `scored_records.convert` |
| E3c | `dup_status` = same-batch status only (no `dedup.py` pass); `story_id` = `UNLINKED:<article_id>`, documented as "unlinked record; not a story-identity claim" | OWNER-CONFIRMED | `scored_records.convert` |
| OD-11a | No linking of records into stories; exact URL and title-hash repetition stay diagnostics only | OWNER-CONFIRMED — NONE | `RepeatedContent` (unchanged); no linking code |
| OD-11b | ALLOWED: each eligible record counts in the interval of its verified availability; no story-level uniqueness claim | OWNER-CONFIRMED | aggregator (unchanged rule) |
| OD-11c | Primary unit = every eligible record, with the current dedup policy kept as a separately reported sensitivity | OWNER-CONFIRMED (the policy itself remains provisional and unapplied) | `features.PRIMARY_DEDUP_POLICY`, `aggregate_daily_with_sensitivity` |
| Scoring input | Title only, the existing validated title field; no article bodies, no network | OWNER-CONFIRMED | `scorer_port.score_candidates` |

Scope: these decisions authorise the conversion contract and the primary-versus-sensitivity counting only. They do not authorise model selection, downloads, installation, network, external transmission, credentials, scoring execution or removal of any policy gate.

## C. Calendar and availability

| ID | Question | Status | Evidence | Blocks | Options documented | Blank = |
| --- | --- | --- | --- | --- | --- | --- |
| OD-12a | Which source defines holidays and early closes? | UNRESOLVED (caller-supplied, unapproved) | policy `CALLER_SUPPLIED_NOT_APPROVED` | production-like interval boundaries | name a source · caller-supplied is fine | boundaries unapproved |
| OD-12b | Do themes (rates, gold) need their own cutoffs? | UNRESOLVED (not implemented) | policy `NOT_IMPLEMENTED` | multi-theme boundaries | yes · no. RECOMMENDATION — NOT APPROVAL: no, until themes are in scope | single cutoff only |

## D. Scorer approval (separate permissions; none implies another)

| ID | Question | Status | Evidence | Blocks | Blank = |
| --- | --- | --- | --- | --- | --- |
| E1a | Exact model identifier, version/revision | BLOCKED (only "FinBERT-class", no checkpoint) | S3 report | everything below in D, features | no scorer |
| E1b | Licence and data-rights review of that model | BLOCKED (unverified; no metadata check authorised) | S3 report | use of the model | not usable |
| E1c | Permission for a **metadata-only** check (model card, licence, label map) | BLOCKED (not authorised) | S3 report | E1a/E1b | no check |
| E1d | Local weights and provenance: source, revision, weights hash | BLOCKED | S3 report | reproducible scoring | no weights |
| E1e | Dependency installation (name each package/version) | BLOCKED (`torch`/`transformers` absent) | completion report §3 | running any model | nothing installed |
| E1f | Network access for a download or provider call (state which) | BLOCKED | — | E1d, provider use | none |
| E1g | Provider/execution authorisation (local run vs external provider) | BLOCKED | — | scoring | no scoring |
| E1h | External data transmission: approved fields only (e.g. title text), retention, processing region and any other handling conditions — applies only if an external provider is chosen; the handling conditions are raised by this worksheet and have no earlier record | BLOCKED | — | provider use | nothing transmitted |

## E. Independent validation

| ID | Question | Status | Evidence | Blocks | Blank = |
| --- | --- | --- | --- | --- | --- |
| E2a | Polarity-label source and human-review procedure (who labels, how many, disagreement handling) | BLOCKED | completion report §7 | any polarity-quality claim | none |
| E2b | Independence rules: AI suggestions never count as ground truth; overlap exclusions and the build lock stay intact | selected principle; procedure UNRESOLVED | prior B2 records | validity of labels | principle holds; no labels |
| E2c | Sealed-key safeguards: who may unseal, when, for what | BLOCKED (nothing authorised) | prior B2 records | filter validation (E6) | sealed |
| E2d | Metric definitions and acceptance criteria for polarity, fixed before scoring, with uncertainty method | BLOCKED | completion report §7 | "validated" claim | no criterion |
| E2e | Minimum evidence: labels frozen before the scorer runs; seeded sample from records outside overlap-excluded sets; intervals reported (proposed in the completion report) | PROPOSED (not approved) | completion report §7 | validity | not adopted |

## F. Daily features, evaluation, filter validation, acquisition

| ID | Question | Status | Evidence | Blocks | Blank = |
| --- | --- | --- | --- | --- | --- |
| E4 | Authorise daily feature generation (only after E1–E3 and all 8 policies applied) | BLOCKED | completion report | features | none |
| E5a | Forecast target. Candidates documented: T3 five-day realised-volatility category (proposed), T5 20-day realised volatility (existing definition); no target is approved | BLOCKED | S3 §3.6.2 | evaluation | none |
| E5b | Instruments and research window (existing market model: `^IXIC`, `^NDX`, QQQ, AGG, GLD; horizon is part of E5a) | BLOCKED | S3 §3.6 | evaluation | none |
| E5c | Evaluation calendar, temporal split and embargo | BLOCKED | — | leakage-safe evaluation | none |
| E5d | Arms and baselines (proposal: market-only, sentiment-only, hybrid, time-shuffled control), metrics, uncertainty, acceptance criteria | BLOCKED (proposal only) | S3 | evaluation | none |
| E5e | Authorisation to run an evaluation | BLOCKED | — | any result | nothing runs |
| E6a | Independent relevance/theme reference-label plan for the GDELT filter | BLOCKED | prior B2 records | filter-validation claim | none |
| E7a | Acquisition window, lookback (OD-01) and baseline length (OD-03), storage and resource limits | BLOCKED | completion report | acquisition | none |
| E7b | Authorise network use for acquisition | BLOCKED | — | download | none |
| E7c | Authorise the full-window download itself | BLOCKED | — | download | none |

## Dependency order (from the repository, not a rule that everything is strictly sequential)

1. **Parallel upstream:** OD-01/03/04/05/02/06/09/13 (accounting), E3 + OD-11a/b/c (eligibility, counting), OD-12a/b (calendar). These need no model and can be answered now.
2. **Model:** E1a → E1c (metadata check) → E1b (licence) → E1d. Selection (E1a) authorises nothing else.
3. **Permissions, each separate:** E1e install, E1f network, E1g execution, E1h transmission. Only those the chosen route needs.
4. **Validation evidence:** E2a–E2e can start in parallel with step 3 (labels must be independent of the scorer and frozen before scoring); needs no scorer to *design*.
5. **Integration:** E3 contract + approved scorer → candidate-to-scored conversion (engineering).
6. **Features (E4):** only when E1–E3, OD-07 and all 8 policies are applied. Engineering-complete here; **scientifically valid only after step 4's acceptance criteria are met.**
7. **Evaluation:** E5a–E5e after features; needs a window of data.
8. **Acquisition (E7):** needs OD-01, OD-03 and E7a first; it can be approved earlier than step 7 if you want data to measure lateness (OD-01 recommends measuring), because that measurement depends on no scorer. That is a sequencing option, not a requirement.
9. **Filter validation (E6a/E2c)** is independent of the chain above.

## Owner response template (copy, fill, return; blank = unresolved)

```text
OD-01 lookback:                 [ ] fixed: ____   [ ] MEASURE FIRST   [ ] CALLER-SUPPLIED   [ ] DEFER
OD-02 primary 0.75:             APPROVE / CHANGE ____ / DROP / DEFER     0.50: ____     0.90: ____     APPLY POLICY: yes / no / defer
OD-03 14 / 7 / 10%:             APPROVE / CHANGE ____ / DROP / DEFER     partial lookback may decide: yes / no
OD-04 NULL flag:               UNDECIDED / UNUSABLE / USABLE-UNDER-RULE / DEFER
OD-05 explicit near-empty:      CONFIRM primary / CHANGE ____ ;  sensitivity variant: yes / no
OD-06 missing-slot cap:         NONE / ____ slots or hours, BLOCKS / FLAGS-ONLY / DEFER
OD-07 scoring-coverage:         THRESHOLD ____ / REPORT-ONLY / DEFER
OD-09 vocabulary:               CONFIRMED / RENAMES ____ / DEFER
OD-13 n_slots_near_empty:       ALIGN to the block / LEAVE / DEFER
E3   eligibility + conversion:  [rules] ____ / DEFER
OD-11a linking:                 NONE / URL / TITLE-HASH / SIMILARITY ____ / DEFER
OD-11b cross-interval:          ALLOWED / FORBIDDEN / DEFER
OD-11c counting unit:           CONFIRM provisional / OTHER ____ / DEFER
OD-12a calendar source:         ____ / CALLER-SUPPLIED OK / DEFER
OD-12b theme cutoffs:           YES / NO / DEFER
E1a MODEL:                      [exact identifier + revision] / DEFER
E1b licence reviewed:           APPROVE / DENY / DEFER
E1c metadata-only check:        APPROVE / DENY / DEFER
E1d weights provenance:         [source + hash procedure] / DEFER
E1e DEPENDENCY INSTALLATION:    APPROVE [list] / DENY / DEFER
E1f NETWORK ACCESS:             APPROVE [scope] / DENY / DEFER
E1g EXECUTION / PROVIDER:       LOCAL / EXTERNAL [name] / DENY / DEFER
E1h EXTERNAL DATA TRANSMISSION: APPROVE [fields, retention, region] / DENY / DEFER
E2a-e POLARITY VALIDATION:      [approved procedure, independence rules, metrics, criteria] / DEFER
E2c SEALED-KEY ACCESS:          APPROVE [who, when, why] / DENY / DEFER
E4   DAILY FEATURES:            AUTHORISE (after prerequisites) / NOT YET / DEFER
E5a-e FEATURES AND EVALUATION:  [target, instruments, window, split/embargo, arms, metrics, criteria] ; RUN EVALUATION: yes / no
E6a  FILTER VALIDATION PLAN:    [plan] / DEFER
E7a-c FULL-WINDOW ACQUISITION:  plan [window, limits]; NETWORK: approve/deny/defer; DOWNLOAD: approve/deny/defer
```

## Source ambiguities

- The original owner-decision message is not visible, so earlier "selected" items carry the owner-instruction attribution recorded in S2.8B–D and cannot be re-verified here.
- E2b–E2d, E5b–E5d and the data-handling conditions in E1h are assembled from the S3 report and this request; there is no earlier owner record for their exact form, so they are marked BLOCKED/PROPOSED rather than assumed.
- The completion report names OD-13 as new; no other record mentions it.

Nothing in this worksheet changes any code, policy, threshold or approval record.

## Later owner decisions (recorded after the sections above)

| Item | Decision | Status | Note |
| --- | --- | --- | --- |
| Tone mapping `gdelt_tone_mean_v0` | Approved strictly as a labelled descriptive document-tone baseline, reported with `n_valid`, `n_records`, `n_valid_all_zero`; all-zero-excluded tone is a sensitivity variant; not title sentiment, market direction or a forecast target | OWNER-CONFIRMED | `tone_baseline.APPROVED_MAPPING`. Applies no other gate: derived output still requires all 8 required policies applied. |
| E1c metadata-only read | Exactly three anonymous GETs per model (API metadata, model card, config) for `ProsusAI/finbert` and `mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis`, `huggingface.co` only, abort on off-domain redirect | OWNER-CONFIRMED and EXECUTED | 6 requests, all HTTP 200, no redirects, no weights or other destinations. Results are model-card claims, not verified licensing. E1a, E1b, E1d-E1h remain open. |

## Policy application decisions (2026-10-20)

Recorded on the owner's explicit instruction. Registry key = `orchestrator.POLICY_STATUS[...]`; provenance = `orchestrator.POLICY_PROVENANCE[...]`.

| # | Registry key | Decision | Status now |
| --- | --- | --- | --- |
| 1 | `deduplication_and_story_updates` | Apply provisionally. Primary analysis counts every eligible record; the current deduplication is a sensitivity analysis | `APPLIED_PROVISIONAL` |
| 2 | `cross_interval_story_uniqueness` | Apply. Each record counts in its verified availability interval; no claim of unique underlying stories | `APPLIED_APPROVED` |
| 3 | `source_coverage_threshold` | Apply provisionally and informationally: 0.75 primary, 0.50 / 0.90 sensitivity. Coverage never turns missing data into neutral sentiment or verified no-news. Implemented as: the verdict never decides usability unless a threshold is `APPLIED_APPROVED` | `APPLIED_PROVISIONAL` |
| 4 | `near_empty_slot_handling` | Apply provisionally: 14 days, at least 7 prior observations, below 10% of the median. Unknown stays unknown | `APPLIED_PROVISIONAL` |
| 5 | `scoring_coverage_threshold` | Apply as report-only; no scoring cutoff | `APPLIED_APPROVED` |
| 6 | `late_batch_strictness` | Apply provisionally with a caller-declared lookback per run; the residual limit is reported (`WindowReport.residual_limitations`); the window is never silently extended | `APPLIED_PROVISIONAL` |
| 7 | `holiday_and_early_close_calendars` | Accept caller-supplied calendars provisionally, marked unverified | `APPLIED_PROVISIONAL` |
| 8 | `scorer_approval_and_polarity_validation` | KEEP BLOCKED until model, licensing, runtime, weights, independent labels and validation criteria are resolved | `UNRESOLVED_NOT_APPLIED` (unchanged) |
| 9 | derived-tone gate | Keep all 8 required policies; not narrowed | unchanged (`derive_interval_tone`, `pipeline.blocking_gates`) |
| 10 | polarity targets | `wording_tone` and `market_direction` are separate targets, never pooled or compared without an explicitly approved mapping | enforced (`polarity_validation.TARGETS`, `APPROVED_CONSTRUCT_MAPPINGS` = empty) |
| 11 | label source | Fresh human labels from the deterministic sampler, frozen and hashed before any scoring; AI suggestions are not independent labels | enforced (`validate_target_evidence`); no labels exist |
| 12 | model | Both transformer candidates deferred; licensing first | unchanged |
| 13 | evaluation | An approved protocol is required before any forecast evaluation | unchanged (`pipeline.EVALUATION_APPROVED = False`) |
| 14 | OD-09 vocabulary | Deferred | unchanged |

Effect: of the 8 required policies, 7 are applied (5 provisional, 2 approved) and 1 (the scorer policy) still blocks derived tone, scoring, daily features and evaluation.

## Annotation milestone decisions (2026-10-20)

| Decision | Applied as |
| --- | --- |
| Targets `wording_tone` and `market_direction` | separate passes, instruction sheets and export hashes (`annotation_tools.target_export_sha256`); never pooled |
| Fresh human labels; D13 overlap labels not reused or read | the D13 overlap items are only EXCLUDED (id column of the original overlap manifest) |
| Seed 42; up to 200 equity, 200 rates; all eligible gold | equity_us 200 of 2,631, rates_us 200 of 2,844, gold 147 of 147 (shortfall 53; no acquisition) |
| Annotators see only item id, theme, title | enforced by the export (`item_id, theme, title, code, note`) |
| Double-label 20% per theme; blind adjudication | 40 / 40 / 30 items; adjudication records carry the no-model-output attestation |
| Freeze and hash before scoring | `build_freeze_manifest` (refuses incomplete or invalid label sets); nothing frozen yet because no labels exist |
| MIX and UNC kept distinct | counts only, outside the 3-class metrics (`annotation_tools.NOT_COMPARABLE_TREATMENT`) |
| Metrics and acceptance criteria | remain PROPOSALS (completion report 11.3); not approved |
| Isolation test exception | `scripts/build_sentiment_validation_sample.py` is the single allowed importer of the sentiment package outside it; it has its own no-network/no-model/no-label test |

Hashes and sizes: completion report section 11.4. Sample outputs: `datasets/derived/sentiment_validation_v1/`.
