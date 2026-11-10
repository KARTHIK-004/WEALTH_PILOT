# Phase B2-U11: methodology decision sheet

Date: 2026-10-19. Status: **a decision sheet. Nothing in it is approved, selected or implemented.** B2 is incomplete, AI execution is blocked, and nothing was committed.

Written for: you, the project owner. Each decision has numbered choices, what each choice does, and the exact words I need from you. Recommendations are marked and are mine, never decisions.

Companions: [bridge-hardening plan](phaseB2U11_bridge_hardening_plan.md), [statistical reconciliation](phaseB2U11_statistical_reconciliation.md), [execution report](phaseB2U11_execution_report.md). Earlier packs: [U10 readiness report](phaseB2U10_readiness_report.md), [retention design](phaseB2U10_retention_design.md), [gate audit](phaseB2U10_gate_audit.md).

> **Update (B2-U12, 2026-10-19):** you selected **M2 as your preferred methodology (D1 only)**. That is recorded in `phaseB2U12_m2_selection_and_plan.md`; it approves no provider, transmission, execution, retention change, gate, criterion freeze, fix or acquisition. D12 (evidence-combination rule) and D13 (overlap-first enforcement) were added there.

**Labels:** [VERIFIED] checked in code, documents or by a read-only run; [DERIVED] reproduced arithmetic; [RECOMMENDATION] mine; [PENDING] yours.

---

## 0. How to answer

Reply with the decision numbers and your choice in plain words, for example: "D1: M1. D2: not applicable. D3: not applicable. D11: authorise F1, F2 and F3; hold F4." Anything you leave out stays pending. **Nothing here is an approval until you write it.**

## 1. M1, M2 and M3: exact definitions [VERIFIED]

Source: `reports/phaseB2_completion_decision_document.md`, section 2, table at lines 52 to 61 (the U6 addendum, sections 12 to 15, repeats M2's status). Nothing has been renamed or reinterpreted. **One lettering caution:** the earlier B2-T proposal (`phaseB2T_…proposal.md`, line 214) used options A to D with similar but not identical designs; the M-labels below are the only ones in the decision document and are the ones this sheet uses.

| | **M1: all human** | **M2: protected overlap, AI-assisted rest** | **M3: changed design** |
| --- | --- | --- | --- |
| Documented meaning | you label all 1,493 items without AI | the 312 overlap items are labelled by you, blind and **never sent** to a provider; the other 1,181 get an AI suggestion and **every item is reviewed by you**, disclosed | the 312 overlap items are labelled by you blind **and sent**, with hidden AI suggestions for a human-versus-AI comparison; the 1,181 as in M2 |
| AI annotation required | no | yes (for 1,181) | yes (for 1,493) |
| Provider required | no | yes | yes |
| Items exposed to a provider | none | 1,181 | 1,493 |
| Required exclusion mode | not applicable (no run) | `overlap_and_blind` [VERIFIED: with no blind subset it excludes exactly the 312 overlap items] | not expressible by the two exclusion modes: both exclude blind items. Needs `none` (which also removes the overlap protection as a setting) or a new mode that does not exist |
| Independent labels | all 1,493 | 312 | 312, plus blind AI output on them |
| Evaluation design | all labels are independent; the pre-registered estimators apply; the full sample meets the 100-member reporting floor if fewer than half the members are ambiguous | the decision rests largely on AI-exposed labels (1,181 of 1,493, about 79%); the independent 312 hold about 40 members per series, **below the floor** ("indicative" only) | as M2, plus a human-versus-AI agreement result |
| Limitations | about 6 to 12 h of your time [ESTIMATED, 15 to 30 s per item, unmeasured]; the batch workflow for the 1,181 is slower and more error-prone than the interactive labeller | anchoring on 1,181 labels; independent evidence cannot carry the decision; amends B2-I section 4.7 (B8 amendment) | as M2, plus the exclusion conflict and a design that needs its own approval |
| Data handling and retention | nothing leaves the machine; no retention question | five fields (`item_id`, `batch_date_utc`, `source_domain`, `url`, `title`) for 1,181 items sent; 45 URLs carry query strings; raw responses are not expirable today | as M2 for 1,493 |
| Approval gates | none | A, B, C and D | A, B, C and D, plus approval of the changed design |
| Implementation and dependencies | **none required**: `annotate label` (overlap only) and the batch export and merge workflow (`export-batch --all`, edit, `merge`) already exist; a labeller extension for the 1,181 is optional and needs your authorisation | exclusion code, bridge and provenance (built, synthetic-tested); still missing: provider decision, **an adapter**, polarity, data handling, retention policy, gate records, and the label path for real use | as M2 plus a blind-subset design and an exclusion mode |
| Scientific and operational risks | slow and error-prone batch workflow; one annotator, so no human-versus-human agreement (B2-I fallback: re-label 10% after 7 or more days) | AI-exposed labels are not independent; provider variability; a reviewer who accepts too readily | everything in M2 plus complexity |
| Can proceed without opening the sealed key | **yes through labelling and freeze**; evaluation opens the key once, after the freeze, by design | yes through review and freeze; evaluation opens the key once, after the freeze | same |

**[RECOMMENDATION, not a decision] M1.** It is the only option that completes B2 with independent labels at the reporting floor, with no provider, no data transmission, no gates and no required code change, and it leaves the question of AI assistance to a later, separately approved experiment. The cost is your time, and it departs from the AI-assisted plan you chose on 2026-10-13. If AI assistance is still wanted, M2 is the efficiency option, accepted knowing that the independent labels cannot carry the decision. I do not recommend M3 unless a human-versus-AI agreement result is itself wanted. Implementing nothing in this phase.

**Needed from you (D1):** the words "M1", "M2" or "M3".

---

## D1. Methodology
See section 1. Choices: **1) M1, 2) M2, 3) M3.** Consequence: everything else on this sheet is either required or not applicable depending on this choice; with M1, D2, D3, D7, D9 and D10 fall away.

## D2. Exclusion mode
Verified against the code (`excluded_item_ids` in `ai/config.py`) and by the non-writing dry run on a scratch configuration outside the repository, on the real 1,493 items. [VERIFIED]

| Mode | What it excludes | Items that could reach a provider (real data) | Items excluded | Consistent with |
| --- | --- | --- | --- | --- |
| `overlap_and_blind` | every original overlap item and every designated blind item | **1,181** | 312 | M2 (partition check reports `matches_proposed_m2: true`) |
| `blind_only` | only the designated blind items. **No blind subset exists in the project**, so it currently excludes nothing | **1,493** | 0 | none of M1 to M3 as defined: it would send overlap items that M2 forbids and M3 needs sending with a blind design that does not exist |
| `none` | nothing | **1,493** | 0 | M3's transmission, but also removes every protection |

Notes: an unset mode blocks execution; `none` is never a default; items with input problems are never sent under any mode (none exist in the real data). Technical availability is not scientific appropriateness: `blind_only` and `none` are only meaningful once a blind-subset design is approved, which has not happened. [RECOMMENDATION] `overlap_and_blind` if you choose M2; not applicable for M1; M3 cannot be set up with the current modes. **Needed (D2):** one of the three words, or "not applicable". Affects Gates A and D hashes.

## D3. Independent-subset weighting
| | Parent weights (current) | Realised-cell-count reweighting |
| --- | --- | --- |
| Formula | each item weighs N_c / n_c of the **parent** cell | each item weighs N_c / n'_c, where n'_c is the number of reference items **actually in** cell c |
| Quantity estimated | a distorted quantity: each cell is scaled by its own realised overlap fraction, which varies around 0.2 | the **same population quantity** as the full-sample estimator, from fewer items |
| Known effect | internally inconsistent for capture recall (numerator scaled by about 0.2, rule-of-three term by about 5; section 4.3 of the [reconciliation](phaseB2U11_statistical_reconciliation.md)) | consistent; wider uncertainty |
| Needs | nothing | the realised cell of each reference item, which exists **only in the sealed key** |

Are realised cell counts available without opening the key? **No.** `selection_log.json` holds parent cell sizes only; cell membership and series membership are in the key. They become available legitimately only inside the evaluation step, after the freeze. Sparse cells: expected overlap items per cell are 38.6, 40, 40, 20, 40, 60, 60 (standard deviations 4 to 7); a cell with very few reference items cannot be reweighted stably, and a cell with none cannot be estimated at all. Design verification (the hash rule reproduces exactly) shows selection was random in expectation; it does **not** show that this realised draw represents each cell, because realised counts are unseen. [RECOMMENDATION] reweight, and refuse a subset estimate if any series cell has fewer reference items than a minimum you set. **Not needed under M1** (all labels are independent). **Needed (D3):** "parent weights", "reweight" (with the minimum per cell), or "no subset estimate".

## D4. Recall definitions and gates
Traced to the code (`estimators.py`) and to B2-I section 4.6 (line 448 to 449). [VERIFIED]

| Term | Definition in code | Documented in B2-I 4.6 |
| --- | --- | --- |
| `pooled_recall` (theme T) | weighted R among T's series members ÷ weighted R over cells C1 to C6 (no C7) | same |
| `capture_recall` (theme T) | weighted R in C1 to C5 ÷ weighted R over **all** cells; if no non-ambiguous C7 item is R, the C7 share is the rule-of-three term N_C7 × 3 / n_C7 and the result is flagged a lower bound | same, "3/n, one-sided 95%" |
| rule-of-three bound | weight N_C7 × 3 / n, where n is the number of **non-ambiguous** C7 items in the code (B2-I does not say which n) | 3/n |

**The pre-registered decision rule (B2-I 4.7) says "pooled capture recall ≥ 0.90"**, which can be read as pooled recall, capture recall, or capture recall pooled across series. **The evaluation gate currently uses `pooled_recall`**; `capture_recall` is reported separately and never decides. That is a choice made in U7, not a documented decision. The two metrics are different quantities and are not interchangeable.

The U10 calculations were reproduced independently (section 3 of the reconciliation): full sample best case **0.9328**; independent subset **0.7351** under realised reweighting and **0.3569** under parent weights. A 0.90 capture-recall target is reachable in the full sample only if at least 64.88% of the captured weight is relevant with none in C6 or C7. [DERIVED]

Choices: **1) gate on pooled recall (current), 2) gate on capture recall, 3) gate on both, 4) other (state it).** Then: keep 0.90, or restate it with a reason. [RECOMMENDATION] option 1 with capture recall reported with its bound, recorded as the decision; keep 0.90 unless you have a stated reason. Nothing was changed. **Needed (D4):** the gating metric(s), the target, and which `n` the bound uses.

## D5. Bootstrap
| | `random.Random(42)` (current) | NumPy `default_rng(42)` (B2-I text) |
| --- | --- | --- |
| Status | implemented, pinned by tests; the package is standard-library only | named in B2-I 4.6; would need a library approval for this package |
| Reproducibility | deterministic; same seed gives the same resamples | deterministic, but a **different stream** |
| Effect of switching | every interval changes and the evaluation fingerprint changes; no results exist yet, so no existing result is invalidated | same |

A matching seed does not give matching resamples across generators. [RECOMMENDATION] record the stdlib generator as the method of record; do not switch for style. **"Bootstrap polarity" is not a documented concept.** I searched the documents and code: the words never appear together. It could mean (a) the annotation polarity option (D6); (b) the direction of the statistical bound (the code uses the 2.5th percentile as the lower bound of a two-sided 95% interval, unit = batch, 2,000 resamples); or (c) something else. **I will not guess: please say which, or "both".** **Needed (D5):** the generator, and the clarification.

## D6. Annotation polarity
- **Rubric values** [VERIFIED, `annotate.POL_VALUES`]: `POS`, `NEG`, `NEU`, `MIX`, `UNC`. Polarity is required when a theme is labelled `R`, and must be blank otherwise; a missing or invalid value makes the label invalid. It is recorded "for a later, separately approved evaluation" and does not affect the filter decision under any option.
- **Protocol option** (`protocol.polarity_option`): the only implemented value is `P1_required_as_in_existing_rubric`. Unset blocks execution; any other value is rejected, not coerced. The B2-U4 package (section 6.2) lists alternatives that are **not implemented**: (b) tell the model to answer `UNC` for every `R`, (c) allow blank polarity under a versioned schema (a rubric and validator change).
- Validation was not changed and no default was introduced. [RECOMMENDATION] `P1`, only if M2 or M3. **Needed (D6):** the option name, or "not applicable".

## D7. Label-basis mapping for two review origins
Existing definitions [VERIFIED, `ai/reviewer.py` and the rubric addendum]: `accept` gives `accepted_ai`; `edit` gives `edited_ai`; `reject` gives `rejected_ai_after_seeing`; the working-copy bases are `accepted_ai` ("checked and accepted"), `corrected_ai` ("changed an AI suggestion"), `rejected_ai` ("discarded and labelled yourself"). `uncertain` gives `human_uncertain` and `insufficient_evidence` gives `human_insufficient_evidence`; **no existing definition says which working-copy basis either one is.** The rubric does not authorise deriving it from content. All three bases classify a label as AI-exposed, so independence is unaffected by the choice.

**Correction to U10:** I recommended deriving the basis from content (identical to the suggestion gives `accepted_ai`, otherwise `corrected_ai`). That is not supported by an explicit rule, so **that recommendation is withdrawn.**

Choices: **1) keep refusing such items (current), 2) you state a mapping for each origin, 3) reviewers use only `accept`, `edit` or `reject` for AI-seen items, recording doubt as a theme labelled `A` with its code and a note** (the validator already allows this, and each action maps to a defined basis). [RECOMMENDATION] option 3, because it needs no new rule and no code. **Needed (D7):** option 1, 2 (with the mapping) or 3, only if M2 or M3.

## D8. Evaluation criteria
[VERIFIED, `decision.py`] The status is `PROPOSED_NOT_APPROVED`; the approval reference is `None`; nothing can approve them from a file, an environment variable or a command-line option.

| Criterion | Existing implementation | Proposed policy | Approved | Missing evidence |
| --- | --- | --- | --- | --- |
| Precision ≥ 0.70 | applied literally, equality passes | B2-I 4.7 rule 1 | **no** | labels |
| Bootstrap lower bound ≥ 0.60 | 2.5th percentile, batch unit, 2,000 resamples, `random.Random(42)` | B2-I 4.7 | **no** | labels; D5 |
| Pooled recall ≥ 0.90 | the gate metric | read from "pooled capture recall" (D4) | **no** | labels; D4 |
| Reporting floor 100 non-ambiguous members | applies to precision and its lower bound; below it the outcome is `INSUFFICIENT_EVIDENCE` | B2-I 4.6 | **no** | the realised member counts |
| Capture recall and its bound | reported only | reported with a lower-bound flag | **no** | D4 |
| Outcomes | PASS, FAIL, INSUFFICIENT_EVIDENCE, INVALID_EVALUATION; none authorises anything | U7 | **no** | n/a |

**Not frozen here.** [RECOMMENDATION] decide D3, D4 and D5 first, because they change what the criteria mean. **Needed (D8):** later, an explicit approval with a reference.

## D9. Provider and data handling (only if M2 or M3)
Unresolved: the provider, the pinned model and version, the temperature, the credentials variable name (the value is never read here), the provider's terms and tier, an adapter (a separate approved change, possibly a library approval), the fields sent (the approved five), whether sending third-party headlines and 45 query-string URLs is acceptable, the destination, the limits and any spending cap. None was selected, no adapter exists, no data was sent, and no terms were assumed. **Needed (D9):** the decisions above, after D1.

## D10. Retention
Summary of the U10 proposal ([retention design](phaseB2U10_retention_design.md)): raw responses cannot expire today because each response sits inside a hashed chain record. The proposal stores each response in a content-addressed payload file and keeps only its hash in the chain; expiry is an audited event written before the file is deleted; six verification states fail closed; it applies to new experiment folders only, with no migration. Approvals still needed: the design itself; whether the research record must keep raw responses at all; the retention duration and the clock (audit-log run end); the expiry semantics (deletion after the period, by explicit confirmation); and, separately, authorisation to implement. **Not implemented; nothing deleted.** **Needed (D10):** approve, reject or revise, and the retention period.

## D11. Bridge hardening (each fix separately)
Full detail is in the [hardening plan](phaseB2U11_bridge_hardening_plan.md).

| Fix | What it does | Needs real AI output | Your authorisation |
| --- | --- | --- | --- |
| **F1** | verify the current suggestion-chain head against the manifest's recorded head | no | yes or no |
| **F2** | verify the review chain on the freeze and evaluation paths, and each export row's recorded review hash against the actual review record | no | yes or no |
| **F3** | refuse the silent fallback to the legacy source when the export names a suggestion chain that is missing | no | yes or no |
| **F4** | correct the inconsistent weighting of capture recall in the independent-reference scope | no | **separate**: it changes a reported estimator and depends on D3 |

[RECOMMENDATION] authorise F1 to F3 together (they only tighten verification) and decide F4 with D3. **Needed (D11):** "authorise F1", "authorise F2", and so on.

---

## 2. Summary of what you need to write

1. D1: M1, M2 or M3.
2. D2: the exclusion mode, or "not applicable".
3. D3: parent weights, reweight (with a minimum per cell), or no subset estimate.
4. D4: which recall gates, the target, and which n the bound uses.
5. D5: the bootstrap generator, and what "bootstrap polarity" means.
6. D6: the polarity option, or "not applicable".
7. D7: option 1, 2 or 3 for the two review origins, or "not applicable".
8. D8: nothing yet (deferred until D3 to D5).
9. D9: provider and data-handling decisions, only after D1.
10. D10: the retention design and period.
11. D11: F1, F2, F3 and F4, each yes or no.

**B2 remains incomplete.** It needs an approved methodology, a valid evaluation and separately authorised full-window ingestion.
