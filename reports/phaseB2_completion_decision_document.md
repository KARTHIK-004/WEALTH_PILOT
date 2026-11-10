# B2 completion drive: decision document (Stage 1)

Date: 2026-10-19. Status: **Stage 1 complete. Stages 2 to 4 are blocked on your decisions. Nothing was run.**

Written for: you, the project owner. Each decision below is yours; none is made or inferred from the request to finish B2.

**Stopping point.** Stage 1 (verify, review, decide) is done. Stage 2 (execution configuration) needs your approvals, so it was not started. No model was run, no data was sent, no provider was chosen, the sealed key was not opened (size and time only), no original file changed, and nothing was committed.

**Labels:** [VERIFIED] read or checked; [MEASURED] from the data's counts or files; [ESTIMATED] computed with stated assumptions; [PROPOSED] needs your approval; [UNVERIFIED] unknown.

---

## 1. Verified state (2026-10-19)

| Item | Value |
| --- | --- |
| Review items / overlap / non-overlap | 1,493 / 312 / 1,181 |
| Labelled; AI suggestions; freeze or evaluation file | 0; 0 (no `ai_suggestions_A.csv`); none |
| `annotation_A.csv`, backup, working copy | `11db13e668bd3da8…` (identical) |
| `annotation_B.csv` (overlap fingerprint) | `211729002893c1e4…` |
| Sealed key | 142,900 bytes, modified 2026-10-13 22:28 +0530; not opened |
| Approval records | GDELT `run_config.yaml`: only `dev_sample` (consumed on 2026-10-13). **No AI experiment config exists, so no AI gate A, B, C or D has a record** |
| AI execution locks | build lock `False`; adapter registry empty; `ai run` blocked (B2-U5) |
| GDELT `NETWORK` and `DEV_SAMPLE` switches | still `True` (unchanged) |
| Tests | 577 pass in `tests/backend/data/gdelt/` as of B2-U5. Not re-run here; no code changed |

**Passing tests is not the research outcome.** B2's research outcome needs labels, a freeze, an evaluation and a decision under criteria fixed in advance. None of those exist yet.

---

## 2. Review of the B2-U5 changes

The duplicate answer, temperature, retention and evaluation changes are implemented and tested on synthetic data. Reviewing them against what a completed B2 needs, I found these **residual gaps and one correction**. None was fixed here, because each depends on a decision.

1. **Correction to B2-U4.** The B2-U4 methodology table marked "Option A (original design)" as supported by the built pipeline because blind labelling works. **The pipeline still transmits every blind item to the provider** (it generates hidden suggestions for them). "Overlap items never sent" is **not** supported. It needs a new protocol field, which changes the Gate A and Gate D hashes. Under your current boundary (no AI output on the overlap items without your approval), this matters.
2. **The built AI dataset does not feed the filter evaluation.** `annotate freeze` and `annotate evaluate` read only the original working copy. The new `b2t_annotation_v1` export and `ai evaluate` check integrity and, with validated provenance, count human-versus-AI pairs. Nothing computes precision and recall from them. If AI assistance is used, a bridge is needed (section 7).
3. **The existing evaluation does not stratify by label origin.** It flags "AI-based labels present, NOT independent" as one switch and computes every statistic over all labels together. A sensitivity result on the independent labels alone is not built.
4. **Bootstrap generator differs from the pre-registered text.** B2-I section 4.6 says `numpy default_rng(42)`; the code uses `random.Random(42)` (the package is standard-library only) and says so in its output. Resampling the same 192 batches gives different intervals. It needs your acceptance.
5. **Evaluation is one-shot.** `annotate evaluate` writes `evaluation_results.json` read-only and never overwrites it, so a mistaken run cannot be repeated without a deliberate procedure. The criteria must be frozen first (section 5).
6. **Retention of raw provider responses is unresolved** (B2-U5 section 5): not expirable in the current layout. It is a Gate C matter if AI is used.

**What holds:** the duplicate answer is kept and validated; temperature is required, validated and hashed into Gate B; the run manifest is written; evaluation refuses to count an AI-exposed label as independent and refuses a blind comparison without valid provenance.

---

## 3. Annotation methodology: preserving an independent subset

**Principle.** The 312 overlap items are the protected, independent evaluation subset. They are labelled by you, without any AI output visible and, unless you approve a changed design, **without being sent to any provider at all**. The original human-only dataset is not changed to make evaluation easier.

**Options** (the filter evaluation itself needs a label for every one of the 1,493 items):

| | M1: all human | **M2: protected overlap, AI-assisted rest** | M3: changed design |
| --- | --- | --- | --- |
| Overlap 312 | you, blind | you, blind; **never sent** | you, blind; **sent**, hidden AI suggestions (human-versus-AI comparison) |
| Non-overlap 1,181 | you, no AI | AI suggestion, **every item reviewed by you**, disclosed | as M2 |
| External transmission | **none** | 1,181 items | 1,493 items |
| Independent labels | all 1,493 | 312 | 312 (plus blind AI output on them) |
| Needs a provider, Gates A–D | **no** | yes | yes, plus explicit approval of the changed design |
| New code needed | **none required.** The 312 overlap items use `annotate label`; the 1,181 others use the existing batch export and merge workflow (`export-batch --all`, edit, `merge`). A labeller extension for them is optional and would need your authorisation | yes (section 7) | yes (section 7) |
| Amendment to the B2-I section 4.7 decision | no | **yes** (AI-assisted labels in the decision) | yes |
| Your effort [ESTIMATED by B2-T, 15 to 30 s per item, unmeasured] | 1,493 items: about 6 to 12 hours | 312 items: 1.3 to 2.6 h, plus review of 1,181 (speed unmeasured) | as M2, plus the blind comparison |

**Recommendation, yours to accept or reject.** **M1 is the only path that completes B2 with no provider, no data transmission and no required code change.** It uses the existing tools: `annotate label` (overlap items only), the batch export and merge workflow for the other 1,181 (slower and more error-prone than the interactive labeller), then `annotate freeze` and `annotate evaluate`. **M2 is the efficiency option** if you still want the AI assistance you chose on 2026-10-13. M3 is not recommended unless you want human-versus-AI agreement as a result in its own right.

**Why the independent subset cannot carry the decision alone** [ESTIMATED from the pre-registered cell sizes]. The overlap is about 20.9% of each series cell, so it holds about 40 gold, 42 rates and 42 equity series members. Under the B2-I section 4.6 reporting rule, 30 to 99 non-ambiguous members is "indicative" only, never an estimate. With about 42 members, an observed precision of at least about 0.76 is needed for even a Wilson lower bound of 0.60 (at 100 members, 0.70; at 200, 0.67). The batch-clustered bootstrap is wider, so these are optimistic. So under M2 the independent labels can check the result but cannot make it.

**Procedural controls (M2 and M3):**

1. **Overlap first.** Label all 312 overlap items, and record their hash, **before any AI suggestion is generated or shown for any item.** About three normalised titles appear in both sets (B2-T), and this stops a suggestion on a twin from influencing the overlap label.
2. Every AI-assisted label keeps its origin (accepted, edited, rejected after seeing, uncertain), reviewer, time and reason.
3. No label made after seeing a suggestion is described as independent anywhere.
4. The non-overlap labels are never mixed into the original human-only fields without the origin recorded.

---

## 4. Handling rules (existing rules, restated; nothing new invented)

| Topic | Rule | Source |
| --- | --- | --- |
| Ambiguous (`A`) | One primary `amb_code`; others in `note`. Excluded from the precision point estimate; bounds treat them as all-not-`R` and all-`R`; a lenient `R`+`RL` version is also shown | B2-S, B2-I 4.6 |
| Duplicate stories | The pipeline's duplicate mark is read-only. The annotator names the other item in `near_dup_of`. Direction is derived at evaluation: earlier availability time, then record sequence, never publication time or item ID. Precision is reported over all items and over unique stories. Not a decision gate | B2-S, B2-I 3.6, B2-U5 |
| Company notices | `Y` never combines with `R` (validator). Reported: share of company-flagged items labelled `Y`, and the share of series members labelled `Y`. Not a decision gate | B2-I 4.6, 4.7 |
| Polarity | Recorded for `R` themes, **not analysed and never informs the filter decision** | B2-I 3.8 |
| Agreement | One annotator, so no human-versus-human agreement. The B2-I fallback applies: re-label 10% after at least 7 days and report within-annotator consistency. Only M3 would add human-versus-AI agreement. No agreement bar gates the filter decision | B2-I 4.5 |
| Clustered uncertainty | Batch-cluster bootstrap, 2,000 resamples, seed 42, over the 192 batches, plus unweighted Wilson per cell as a cross-check | B2-I 4.6 (generator: section 2, item 4) |
| AI-assisted labels | Disclosed by origin; counted separately; never independent | B2-T, B2-U3 |

---

## 5. Measurable filter acceptance criteria [PROPOSED; to be frozen before any label]

B2-I section 4.7 says these are "to be fixed before the first label" and "suggestions, not derived from data". They are still only *proposed*, and **no label exists yet, so they can still be fixed.** **Every number below is B2-I's; I added none.**

**Per series** (`EQUITY_US`, `RATES_US`, `GOLD`), on the final labels:

| Criterion | Rule |
| --- | --- |
| P: precision | at least **0.70** (ambiguous excluded) |
| L: lower bound | batch-cluster bootstrap 95% lower bound at least **0.60** |
| R: recall | pooled recall at least **0.90** (definition: see below) |
| Rep: reporting floor | at least 100 non-ambiguous members, so the figure is an "estimate". Fewer is "indicative" or counts only and cannot pass |

**Outcomes:** **FREEZE** (P, L, R and Rep all met); **REVISE** (a criterion not met with Rep met: one revision citing stage D record IDs, judged on stage C only, which needs a separate approval to download); **NOT USABLE** (revision fails; no further tuning); **INCONCLUSIVE** (Rep not met). The company-flag, duplicate and agreement figures are reported, not gating.

**A defect in the pre-registered wording, needing your decision before any label.** B2-I section 4.7 says "pooled capture recall at least 0.90", but section 4.6 defines two different recalls:

- **(i) Pooled recall:** weighted `R` among series members divided by weighted `R` over cells C1 to C6. **This is what the code gates on.** It is attainable.
- **(ii) Capture recall:** weighted `R` in captured cells C1 to C5 divided by weighted `R` over all cells including C7. When no sampled C7 item is `R`, the C7 share is replaced by the rule-of-three bound, so the result is only a lower bound. **At 0.90 this is arithmetically unattainable at these sample sizes** [MEASURED cell counts, ESTIMATED]: C7 has 193,590 rows and 300 sampled items, so the bound is up to 1,936 `R` rows in C7. A lower bound of 0.90 would need about 17,400 weighted `R` in the captured cells, which is 65% of all 26,854 captured rows. For gold, whose series cell has 193 rows, the best case is a lower bound near 0.09.

**Proposed reading:** the decision gates on (i); (ii) is reported with its bound as a disclosed limit, as section 4.6 says ("never one unqualified number"). This is a real choice, not a typo fix, and it decides whether any series can pass. It needs your approval.

**Scope of "B2 complete".** A FREEZE or NOT USABLE outcome settles the **filter research question**. It does **not** satisfy the B2 acceptance criteria of the architecture document (stored articles with source, licence, `published_at` and `ingested_at` for the whole window, duplicate and unmapped share, the cutoff test), which need the full-window ingestion that is not approved. **So B2 cannot be marked complete on the filter outcome alone.** You decide whether to report B2 as "filter outcome reached, ingestion pending".

---

## 6. Polarity options and their impact on comparability

Only relevant if AI is used (M2 or M3). Under M1 your existing rubric and validator apply unchanged, and **polarity does not affect the filter decision under any option** (section 4).

| Option | Change | Comparability with your human labels |
| --- | --- | --- |
| **P1** (the only one implemented; `P1_required_as_in_existing_rubric`) | none: polarity for every `R` theme, `UNC` allowed | full |
| P2: AI answers `UNC` for every `R` | new rubric text and a new Gate B hash | reduced: an accepted row carries a placeholder, not your judgement |
| P3: polarity not collected | a new schema version, a validator mode, new rubric text, an export change | relevance, ambiguity and company fields stay comparable; no polarity exists for these items |

B2-T proposed "no polarity" (P2 or P3 in effect), but the validator requires polarity for `R`. Recording `protocol.polarity_option` is your choice; I have not set it.

---

## 7. What needs approval before any AI execution (M2 or M3 only)

Nothing is selected. Values are proposals; every one needs your approval. Verified provider pricing and data terms are in the B2-U4 package (retrieved 2026-10-19). **Re-confirm them on the live pages at approval time**, because prices change and Google's page listed a scheduled change.

| Item | Needed | Proposal or note |
| --- | --- | --- |
| Provider and model | exact provider, pinned model ID **and version** (the config requires a version) | none selected; `google-genai` approval (2026-09-14) is app-scoped; `anthropic` is not installed; a new library needs approval |
| Data transmitted | the five fields: `item_id`, `batch_date_utc`, `source_domain`, full `url`, `title` | **1,181 items under M2** (not 1,493). 45 URLs across the set carry query strings; whether sending third-party headlines is acceptable is your decision |
| Provider terms | training use, human review, retention, tier | B2-U4 section 3.3: a free or unpaid Google tier allows training and human review; Anthropic and OpenAI list about 30 days default retention; zero retention needs vendor approval. The tier of any existing key is [UNVERIFIED] (`.env` not read) |
| Local retention | what happens to raw responses | **unresolved**: not expirable in the current layout (needs a payload-file design) |
| Temperature | one value in the allowed range | the model must accept it |
| Requests | cap | **1,600** (1,181 needed; about 35% headroom) |
| Input tokens | cap | **2,400,000** (1,378,386 estimated, about 1.7 times; the estimate is characters ÷ 4) |
| Output tokens per request | cap | 400 |
| Timeout; retries; re-asks; back-off | | 60 s; 3 attempts; 1 re-ask; 2, 4, 8 s |
| Concurrency | | 1 (sequential only) |
| Spending cap | currency, both unit prices, a cap | **1.5 times the estimate at the approved prices.** For the sampled models in B2-U4, one full non-overlap run is about $0.33 to $15 [ESTIMATED, from list prices of 2026-10-19] |
| Run ID; polarity option; blind subset | | run ID your choice; polarity per section 6; under M2 there is **no** blind subset and the overlap items are excluded from transmission |
| Gate hashes | A, B, C, D | printed by `ai dry-run` after the config is filled; they cannot be known until then |

**Code changes required before Stage 2, after approval** (each alters hashes or datasets, so none was made):

1. A protocol field that excludes the overlap items from transmission and from the item set a run uses (M2).
2. A bridge so AI-assisted labels reach the freeze and evaluation, with a label-origin-stratified sensitivity result, and the section 5 decisions encoded (M2, M3).
3. The build-lock change and a reviewed provider adapter, last.

---

## 8. The path from here

| Stage | M1 (all human) | M2 or M3 |
| --- | --- | --- |
| 1 Decide | section 9, items 1 to 5 | items 1 to 12 |
| 2 Configuration | not needed | build and validate the config; code changes above; dry run shows matching hashes; locks stay on until approvals are valid |
| 3 Execution | not needed | one sequential run on the **development sample only**, with hard limits, after your explicit authorisation |
| 4 Review and evaluate | you label the 312 overlap items (`annotate label`) and the other 1,181 (batch export and merge, or an authorised labeller extension), then `annotate freeze`, then `annotate evaluate` (the only step that opens the sealed key, once, after the freeze) | overlap first; then review; then the bridged evaluation |

The confirmation sample (stage C) and the full acquisition stay unauthorised. Under B2-I section 4.7, stage C opens only if a revision is made or a theme has fewer than 100 member rows (decided from counts only). The smallest series cell, gold, has 193 rows, so the count trigger does not fire, and only a revision would trigger it. Opening it needs its own approval.

---

## 9. Decisions needed from you

| # | Decision | Needed for |
| --- | --- | --- |
| 1 | Methodology: **M1**, M2 or M3 (and, for M2 or M3, the overlap-first rule) | everything |
| 2 | Freeze the section 5 criteria: the P, L, R and Rep rules and the four outcomes | any evaluation |
| 3 | Which recall gates the decision: (i) as built, or (ii) (the (ii) reading cannot pass) | any evaluation |
| 4 | Accept the stdlib bootstrap generator in place of `numpy default_rng(42)` | any evaluation |
| 5 | Scope: may B2 be reported as "filter outcome reached, ingestion pending", given the ingestion criteria stay unmet | the final status |
| 6 | Permit AI-assisted labels in the section 4.7 decision (the B8 amendment) | M2, M3 |
| 7 | Polarity option | M2, M3 |
| 8 | Provider, pinned model and version, temperature, terms and tier | M2, M3 |
| 9 | Data handling: transmit 1,181 titles and URLs; retention, including raw responses | M2, M3 |
| 10 | Limits and spending cap (section 7) | M2, M3 |
| 11 | Authorise the section 7 code changes | M2, M3 |
| 12 | Authorise the run, only after Stage 2's dry run matches | M2, M3 |
| 13 | Lock the GDELT `NETWORK` and `DEV_SAMPLE` switches (still on) | safety, any option |

---

## 10. What is complete, what is not

- **Completed:** the Stage 1 verification, the review of the B2-U5 changes, the methodology, handling rules, criteria and approval checklist above.
- **Not run:** Stages 2, 3 and 4; any labelling, suggestion, evaluation or freeze; any provider call; any test (no code changed).
- **B2 is not complete.** The labelled review, the freeze, the evaluation, the filter decision and the full-window ingestion criteria are all unmet.
- **Evidence still needed:** your decisions in section 9, then labels (and, for M2 or M3, an approved run), then the frozen criteria applied to a valid evaluation.

---

# Addendum (B2-U6, 2026-10-19): decision record, implementation audit and remaining checklist

**Nothing in this addendum is an approval.** The five rows below are recommendations awaiting your explicit confirmation. No code, test, gate, data file or annotation file was changed, and no model, provider or network was used. The sealed key was not opened and no credential was read.

## 11. Verified state (re-checked, read-only)

| Item | Value |
| --- | --- |
| Items / overlap / non-overlap | 1,493 / 312 / 1,181 |
| Human labels; AI suggestions; freeze or evaluation file | 0; 0; none |
| Approval records | GDELT `run_config.yaml`: `dev_sample` only (consumed). No AI experiment config, so no AI gate A, B, C or D record |
| Build lock; adapter registry | `False`; empty. `CONFIRMATION_SAMPLE_ENABLED_IN_THIS_BUILD` is also `False` |
| GDELT `NETWORK` / `DEV_SAMPLE` switches | both `True` (unchanged) |
| Full-window ingestion | **not done**: no window-wide driver exists, full acquisition has no enabling switch and is always refused; only the 192-batch development sample is on disk |
| Original files | `annotation_A.csv`, backup and working copy `11db13e668bd3da8…`; `annotation_B.csv` `211729002893c1e4…`; key 142,900 bytes, modified 2026-10-13 22:28 +0530, not opened |

## 12. Decision table: pending your confirmation (recommendations, **not approvals**)

| # | Recommendation | Approved? |
| --- | --- | --- |
| 1 | **M2**: all 312 overlap items human-only; the 1,181 others AI-assisted, every item human-reviewed | **No: pending** |
| 2 | **Criteria**: precision ≥ 0.70; bootstrap lower bound ≥ 0.60; pooled capture recall ≥ 0.90; existing 100-member reporting floor | **No: pending** |
| 3 | **Recall**: decide on pooled capture recall; report the rule-of-three bounds and sample-size limits separately | **No: pending** |
| 4 | **Bootstrap generator**: document the generator actually used; propose the smallest correction | **No: pending** |
| 5 | **Status wording**: "filter outcome reached, ingestion pending" only as a qualified partial outcome; B2 not fully complete while ingestion criteria are unmet | **No: pending** |

### Decision 1: methodology M2

- **Current state:** not chosen. Neither M1, M2 nor M3 is recorded as a decision.
- **Proposed choice:** M2, with the overlap-first rule and with the overlap items never sent to any provider.
- **Evidence:** the overlap is a hash-selected 20.9% subset, kept human-only by design (B2-I 4.4). The original `annotate.py` validator already enforces overlap protection on its own path: an AI label basis is refused on an overlap row (line 215) and an AI suggestion for an overlap item is invalid (line 277). **The new AI pipeline does not enforce it** (section 13).
- **Research consequences:** about 40 to 42 independent members per series, which is "indicative" only under B2-I 4.6, so the independent subset can check the result but cannot carry the decision. AI-assisted labels would carry about 79% of the evidence, which is the B8 amendment.
- **Implementation changes needed:** overlap exclusion in the AI pipeline; a bridge from AI-assisted labels to the freeze and evaluation, stratified by label origin (sections 13 and 14).
- **Approval still required:** yes, plus the B8 amendment (AI-assisted labels in the §4.7 decision).

### Decision 2: acceptance criteria

- **Current state:** the numbers exist only as "PROPOSED" (B2-I 4.7; `estimators.PROPOSED_THRESHOLDS`). Not frozen. No label exists, so they can still be frozen.
- **Proposed choice:** precision 0.70, lower bound 0.60, pooled recall 0.90, 100-member floor, per series; outcomes FREEZE, REVISE, NOT USABLE, INCONCLUSIVE (section 5 above).
- **Evidence:** every number is B2-I's. **The code checks only the first three. It does not apply the 100-member floor to the decision**: `proposed_thresholds` has three checks and the floor appears only as a reporting label.
- **Research consequences:** without the floor in the rule, a series with fewer than 100 non-ambiguous members could register "all met". The floor is reported, not enforced.
- **Implementation change:** add the floor and the four outcomes to the threshold check (evaluation code only; no gate hash).
- **Approval still required:** yes, before any label is made.

### Decision 3: recall interpretation

- **Current state:** the code gates on `pooled_recall` (weighted `R` among series members ÷ weighted `R` over C1 to C6). `capture_recall` (C1 to C5 over all cells, with the rule-of-three bound for C7) is computed and reported but does not gate.
- **Proposed choice:** gate on `pooled_recall`. Your wording says "pooled capture recall"; B2-I uses "pooled" and "capture" for two different quantities, so **please confirm this means the implemented `pooled_recall`**, not `capture_recall`.
- **Evidence:** B2-I 4.6 defines both; 4.7 names "pooled capture recall". Capture recall at 0.90 cannot be reached with the bound (C7 allows up to 1,936 relevant rows; 0.90 would need about 17,400 captured, 65% of the 26,854 captured rows).
- **Research consequences:** the decision does not cover what the capture rule misses in C7 (rows with no cue). That is stated as an explicit limit, with the lower bound reported.
- **Implementation change:** none to the gate; add the limit statement to the report output.
- **Approval still required:** yes.

### Decision 4: bootstrap generator

- **Current state (verified in code):** `estimators.cluster_bootstrap` uses `random.Random(42)`, 2,000 resamples, resampling whole batches with replacement (one draw per batch), a percentile interval at 2.5% and 97.5% with linear interpolation, undefined resamples skipped and counted. `evaluate.py` records this in its output.
- **Documented method:** B2-I 4.6: batch-cluster bootstrap, 2,000 resamples, **`numpy default_rng(42)`**. **They differ**: the random stream differs, so interval endpoints will not equal a numpy run. The sampling unit, resample count and seed value match. The code discloses the departure (module docstring and result).
- **Smallest correction, proposed:** record that the stdlib generator is the method of record, with no code change. Importing numpy instead would break the standard-library-only isolation test and is not recommended.
- **Research consequence:** reproducibility only: results must cite the generator.
- **Approval still required:** yes.

### Decision 5: completion wording

- **Current state:** B2 is paused; no filter outcome exists.
- **Proposed choice:** once a filter outcome exists, the only permitted wording is "filter outcome reached, ingestion pending", labelled a qualified partial outcome.
- **Evidence:** the architecture document's B2 criteria (stored-article metadata, duplicate and unmapped share, the cutoff test across the window) are met only for the 192-batch sample, and full-window ingestion is unapproved and has no driver.
- **Consequence:** B2 cannot be marked fully complete.
- **Implementation change:** none (documentation); full acquisition needs its own authorization.
- **Approval still required:** yes, for the wording.

## 13. Audit of M2 and overlap protection (against the actual code)

| Requirement | Finding |
| --- | --- |
| No overlap item can be sent to the provider | **Not guaranteed.** `runner.run_suggestions` queues every sendable item, overlap and blind included. `blind_item_ids` only hides a suggestion from the reviewer. The original path's protection does not apply to this pipeline |
| Overlap distinguished from non-overlap by validated provenance | **Yes.** `init_experiment` reads `overlap_subset` from the original file, requires `annotation_B.csv` to equal exactly those IDs (and both files to match `selection_log.json`), and records `historical_overlap.json` |
| Human-only labels never counted independent if AI-exposed | New dataset: yes (`ai_exposure`; evaluation rejects mismatches). Original working copy: `label_basis = own` means no AI seen, enforced only by the validator and by there being no AI tool on that path |
| AI-assisted labels keep provenance | New dataset: yes (suggestion hash, model, prompt, rubric, temperature, reviewer, times). **Original working copy format: only `label_basis`**; a bridge would have to carry the rest alongside |
| Duplicate references valid after export and merge | Validated at recording and export. **No merge or bridge into the original working copy exists, so this cannot be verified for M2**; it must be tested when the bridge is built |
| Polarity consistent across rubric, config, validator, provider schema, evaluation | **Consistent under P1**: `rubric_v1.md`, the output schema, `annotate.content_errors` (used by suggestions, reviews, evaluation and the original validator) and the only config option all require polarity for `R`. The inconsistency is the B2-T text ("not requested"), unresolved |
| Blind comparison not overclaimed | **Partly.** The reporting floor is attached only to the "excluding A" view of the three relevance fields. The "all pairs" and company-notice results carry Wilson intervals with no floor flag, and there is no overall "indicative only" label. M2 has no blind subset, so this matters only for M3 |

**Exact code changes needed before M2 execution (none made):**

1. **Overlap exclusion.** A protocol field such as `provider_excluded_item_ids`; a runner filter so excluded items are never built into a request; a blocker unless the excluded set equals `historical_overlap.json` exactly; dry-run counts; and a test that a fake provider never receives an overlap ID. This changes the **Gate A and Gate D** bindings.
2. **Bridge and stratified evaluation.** Carry AI-assisted labels and provenance into the freeze and evaluation, with results on all labels and on independent labels only.
3. **Floor and outcomes in the threshold check; blind-comparison floor flags** (M3 only).
4. Adapter, sampling parameters and build lock, last (Gate B).

## 14. Audit of evaluation reproducibility (B2-I 4.6 and 4.7 against the code)

| Element | B2-I | Code | Match |
| --- | --- | --- | --- |
| Precision | weighted share of series members labelled `R`; ambiguous excluded; bounds as all-not-`R` and all-`R`; lenient `R`+`RL` | `R` weight ÷ (`R`+`RL`+`I` weight) over members; weight = cell rows ÷ items sampled; both bounds and lenient reported | **Yes** |
| Pooled recall | weighted `R` among members ÷ weighted `R` over C1 to C6 | same | **Yes** |
| Capture recall, rule of three | C1 to C5 over all cells; if C7 has no `R`, bound C7 by 3/n, report a lower bound | bound = C7 rows × 3 ÷ (non-ambiguous C7 items sampled); flagged lower bound | **Yes** (B2-I does not say whether n excludes ambiguous items) |
| Bootstrap unit, replicates, seed value | batch; 2,000; 42 | batch; 2,000; 42 | **Yes** |
| Bootstrap generator | `numpy default_rng(42)` | `random.Random(42)` | **No** (decision 4) |
| Unweighted Wilson cross-check | **per cell** | one interval per theme over pooled members | **No** |
| Duplicate stories | precision over all items **and** over unique stories; count of annotator `NEAR_DUP` items | neither computed: no duplicate field in the scored item, `near_dup_of` unused | **No** |
| Ambiguous items | as precision above | as above | **Yes** |
| AI-exposed vs independent | not covered by B2-I | one flag if any AI basis exists; no stratified results | **Gap** |
| Reporting floor | 100 / 30 to 99 / under 30 | computed as a label per theme; **not part of the pass or fail check** | **Partial** |
| Decision check | precision, lower bound, recall | same three; thresholds labelled PROPOSED | **Yes**, floor missing |

**Proposed resolutions, each needing approval, none made:** (a) record the stdlib generator as the method of record; (b) add a per-cell Wilson cross-check; (c) add unique-story precision and the `NEAR_DUP` count, joining the duplicate mark from the working copy (the key does not carry it); (d) add the floor and outcomes to the check; (e) add label-origin-stratified results. Items (b) to (e) change evaluation code only, so no gate hash changes, but the freeze record stores a code fingerprint, so they must be made **before** the freeze. Real-data evaluation was not run and the key was not opened.

## 15. Remaining approval checklist for M2

| Decision | Can be decided now? | Depends on |
| --- | --- | --- |
| Methodology M2 and the overlap-first rule | **Yes** | none |
| Acceptance criteria and the recall reading | **Yes** (before any label) | none |
| Bootstrap generator; completion wording; B8 amendment | **Yes** | none |
| Polarity option | **Yes** | methodology (matters only if AI is used) |
| Lock the GDELT `NETWORK` and `DEV_SAMPLE` switches | **Yes** | none (reversible; breaks one test that asserts the post-acquisition state) |
| Raw-response retention policy (keep, or redesign so they can expire) | **Yes** (principle) | the layout change follows the decision |
| Data handling (1,181 title and URL pairs) | **Yes** (principle) | provider, for the exact terms |
| Authorize code changes (section 13, items 1 to 3) | **Yes** | methodology |
| Provider and pinned model with version | After the above | needs an adapter; library approval if an SDK is used |
| Temperature and other run parameters | No | the model's supported range |
| Request, token, retry, timeout and spending caps | No | provider prices and token counts (proposals in section 7) |
| Gate A, B, C, D records and hashes | No | a complete config; hashes change after the code changes |
| Build-lock change and adapter registration | No | all gates valid; done last |
| Explicit execution authorization | No | a dry run whose hashes match |
| Full-window acquisition | **Separate** | its own authorization; the driver does not exist; not required for the filter outcome |

**Hash effects:** the overlap-exclusion field changes the Gate A and Gate D bindings; adapter or sampling changes change Gate B; evaluation changes change no gate hash but change the code fingerprint stored at freeze. No approval record exists, so none is invalidated. Nothing was invented: no provider, price, approval or execution permission.

## 16. Verification of this addendum

- Read the code for the runner, estimators, evaluation, annotate validator, switches and the init provenance checks, and re-checked counts and hashes read-only.
- Documentation only: **no code or test changed and no test was run**, so I claim no test result. The last recorded result was 577 passing in `tests/backend/data/gdelt/` as of B2-U5.
- Checked that every report and document path cited here exists.
