# Phase B2-U10: methodology decision pack and readiness report

Date: 2026-10-19. Status: **documentation and verification only. No code, data, label, record or switch was changed.** AI execution is blocked, B2 is incomplete, and nothing was committed.

Written for: you, the project owner. This is the decision pack. Verified facts, derivations and recommendations are kept apart; every decision below is yours and none was made here.

Companion files: [retention design](phaseB2U10_retention_design.md), [gate A to D audit](phaseB2U10_gate_audit.md), [B2 completion plan](phaseB2U10_completion_plan.md).

> **Superseded in part by B2-U11 (2026-10-19).** (1) The D10 and D11 recommendation to derive a `label_basis` from content is **withdrawn**: the rubric does not authorise it (`phaseB2U11_methodology_decision_sheet.md`, D7). (2) "64.9%" in section 3.3 is 64.88%. (3) U11 reproduced every other figure in section 3.3 independently (`phaseB2U11_statistical_reconciliation.md`). The rest of this report is unchanged.

**Labels:** [VERIFIED] checked in code, by a command or by a read-only probe; [DERIVED] arithmetic from public numbers, reproducible; [ASSUMPTION] cannot be checked with what may be opened; [RECOMMENDATION] mine, not an approval; [PENDING] your decision.

---

## 1. Verified baseline

| Item | Reported (U9) | Verified now | Match |
| --- | --- | --- | --- |
| Git HEAD | `71b363f` | `71b363feaaf6148be1fd462d313ff1735cf005b0`, branch `master`, 0 staged, 89 status entries (the gdelt package, its tests and the B2 reports are untracked; `docs/MEMORY.md` is modified) | yes |
| GDELT suite | 794 passed | `pytest tests/backend/data/gdelt -q -p no:cacheprovider`: **794 passed in 51 s**, exit 0, real code with synthetic fixtures | yes |
| Build lock `AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD` | `False` | `False`; adapter registry `{}` | yes |
| `NETWORK` / `DEV_SAMPLE` / `CONFIRMATION_SAMPLE` | unchanged | `True` / `True` / `False` | yes |
| Real review folder | provenance verified, 0 labelled | provenance `VERIFIED`; 1,493 items, 312 overlap, 1,181 non-overlap; all `unlabelled`; no freeze, no results, no `ai_suggestions_A.csv`; merge log present | yes |
| Evaluation fingerprint (real folder) | `48ceaaba…` | `48ceaaba5b64325da5adf7be84240211fad0d544e90af50f039130ac425bf2fb` | yes |
| Execution prerequisites | 15 listed by the dry run | the non-writing `ai dry-run` (scratch probe config outside the repo) lists **15** (14 plus the unset `--confirm-ai-run`); `provider_called`, `data_sent`, `files_written` all `False` | yes |
| Sealed key | unopened | 142,900 bytes, modified 2026-10-13 22:28:16 +0530, same as U7 to U9; **metadata read only** | yes |
| Files under `datasets/` | unchanged | 0 files newer than the U7 baseline marker | yes |
| Approval, execution, suggestion, review, export records | none | none exist (no experiment config exists in the repo; no experiment folder exists) | yes |

No reported safety invariant has failed. One reported **conclusion** is corrected below (section 3.3).

## 2. Label-bridge audit

Read: `ai_bridge.py`, `ai_origin.py`, `annotate.py` (validator, merge), `ai/store.py`, `ai/export.py`, `ai/reviewer.py`, `evaluate.py`, `cli.py`, and `test_label_bridge.py`.

### 2.1 What was confirmed [VERIFIED by reading and by the tests]

| Claim | Result |
| --- | --- |
| `load` exposes suggestions only after every check passes | yes: any problem returns an **empty** valid set (all or nothing). Checks: hash chain, snapshot is of this original, verified overlap equals the original's, record schema, no overlap or unknown item, input fingerprint, `validation.ok`, the shared rubric validator, derived CSV equals the chain's output |
| Verified reviews are checked against verified suggestions | yes, in `ai_origin`: citation equals the valid suggestion's record hash; accepted equals the suggestion; edited and rejected differ; "no suggestion" refused if the store holds one |
| Suggestion-chain hash bound into the freeze fingerprint | yes (`ai_origin/suggestions_raw_chain`) |
| `labels_for_merge` refuses `human_uncertain` and `human_insufficient_evidence` | yes, listed as refused with the reason |
| Legacy validator default unchanged | yes: `ai_suggestions=None` takes the old path; `save_item` and the labeller were not changed |
| Both a legacy file and a B2-T store: refused | yes, an integrity error; nothing accepted |
| Forged, modified, incomplete, inconsistent inputs fail closed | yes for the cases tested (29 tests) and the three probes below |
| No legacy records, guessed conversions or overwrites | yes: no write path in `ai_bridge.py` or `ai_origin.py` (a test asserts it); already-labelled items are refused |
| Reads do not create or mutate records | yes: a tree-hash test shows `load` and `labels_for_merge` change nothing |

### 2.2 What each kind of test does and does not prove

| Kind | Example | Proves | Does **not** prove |
| --- | --- | --- | --- |
| Rule tests | forged citation refused; tampered chain rejected | the rule fires | that the rule set is complete |
| Synthetic pipeline | scripted fake provider through review, export, merge, freeze, evaluate | the pieces connect and refuse correctly | anything about real AI output |
| Actual AI output | none exists | n/a | n/a |
| Evaluation validity | none: no real labels, no approved protocol | n/a | n/a |

The last two have **not** been established. Nothing here should be read as evidence about model quality, label quality or filter performance.

### 2.3 Gaps found by this audit [VERIFIED by read-only probes on synthetic data; not fixed]

Three throwaway probes (a temporary test file, deleted afterwards; repository state unchanged) tried to defeat the bridge after a valid export existed.

| ID | Probe | Result | Severity |
| --- | --- | --- | --- |
| **F1** | Append a *non-terminal* attempt to the suggestion chain after the export | still `VERIFIED`. The export manifest records the chain heads (`chain_heads.suggestions`, `.reviews`, `.audit`) but nothing compares them with the current chains. The derived-CSV check catches only terminal changes. After a freeze the fingerprint would catch it, before a freeze nothing does | low to medium |
| **F2** | Edit the **review** chain after the export | still `VERIFIED`, although reading that chain raises `ChainError`. The review chain is never read on the freeze and evaluate path, and `review_record_sha256` is only format-checked (a self-consistent export with a made-up hash verifies). Review authenticity therefore rests on the export file's own hash only | **medium** |
| **F3** | Delete the suggestion chain | `load` returns `None` and the **legacy** source applies. Fail-safe here (the validator then refuses AI labels because `ai_suggestions_A.csv` is absent), but silent: the export manifest says a chain should exist | low |

**Smallest safe correction (proposed, needs your authorisation; read-only):** in `ai_bridge.load` and `ai_origin.attach`, (a) verify the review chain; (b) require the manifest's `chain_heads.suggestions` and `.reviews` to equal the current chain heads; (c) require each export row's `review_record_sha256` to equal the current review record's hash for that item; (d) if the manifest names a suggestion chain and the chain is absent, block instead of falling back. About 40 lines plus tests; no change to the validator, no new write path.

### 2.4 A defect in U8's evaluation output [VERIFIED by derivation, section 3.3; not fixed]

**F4.** The U8 `independent_reference` scope computes **capture recall** with parent-cell weights on a roughly 20% subset while the rule-of-three term uses the realised subset count. The numerator shrinks by about 0.2 and the bound grows by about 5, so the number is internally inconsistent. Pooled recall, a ratio in which both sides scale together, is not affected the same way. Proposed correction: label capture recall in that scope "not valid under parent weights" until D3 (reweighting) is decided. That is a small change to a reported, non-deciding field; it is not made here.

## 3. Statistical findings

### 3.1 What is established, what is assumed, what needs evidence

| Conclusion | Status | Basis |
| --- | --- | --- |
| Overlap membership is a pre-registered 20% hash rule on the record ID, and it reproduces the file exactly | **[VERIFIED]** | recomputed again now from public columns: 312 of 312, 0 mismatches; B2-I section 4.4 step 4 states the rule; z = 0.87 against 298.6 expected |
| Public columns are balanced between overlap and non-overlap | [VERIFIED] | by duplicate mark, month, top domains, item index (no signal) |
| Membership is independent of the cell | [DERIVED by construction] | the rule uses the record ID only; the cell is assigned from content |
| Realised overlap counts per cell, and per series | **[ASSUMPTION / unverified]** | they live only in the sealed key, which stays closed. Expected 38.6 (C1), 40, 40, 20, 40, 60, 60, standard deviations 4 to 7 |
| The independent subset holds about 40 members per series | [DERIVED, expectation] | 20% of 193, 200, 200; the realised number is unverified |
| That subset is below the 100-member reporting floor (30 to 99: "indicative only") | [DERIVED] | follows from the expectation; would need the realised counts to confirm |
| Wilson lower bound needs 31 of 40 relevant for 0.60 | [DERIVED, reproduced from `estimators.wilson`] | 70 of 100, 130 of 193, 134 of 200; unweighted and optimistic (the batch bootstrap is wider) |
| Labels are independent of the hash | [ASSUMPTION] | no labels exist |
| Realised representativeness of the 312 | **not established** | design randomness gives representativeness in expectation, not for this draw, and 312 is small where it matters |

Why this does not justify a representativeness claim: random selection protects against systematic bias but not against the luck of one draw. With about 40 members per series, one more or fewer relevant item moves precision by 2 to 3 points, and the realised per-cell mix is unknown.

### 3.2 Does changing weights or targets change the estimand?

- **Reweighting by realised overlap counts (D3).** The parent estimand is a population quantity weighted by N_c/n_c. A random subset weighted by N_c/n'_c estimates the **same** population quantity with fewer items and wider uncertainty. Reusing N_c/n_c weights on a subset estimates a slightly different, distorted quantity (each cell scaled by its realised fraction), which is why F4 arises. Reweighting changes the **estimator**, not the estimand, but it still changes a pre-registered formula and so needs your approval.
- **Changing a target or the floor.** Moving 0.70, 0.60, 0.90 or 100 changes the **acceptance rule**, not the estimate. The criteria are frozen only by an explicit approval. Choosing a target after seeing data would be tuning; none has been seen.
- **Changing which recall gates (D5)** changes the question the criterion answers (section 3.3).

### 3.3 Independent derivation of the capture-recall finding [DERIVED; reproducible with the scratch script `u10_capture.py`, public numbers only]

Inputs (public, from `selection_log.json`): rows per cell 193, 2,848, 1,953, 1,560, 20,300, 24,492, 193,590; items 193, 200, 200, 100, 200, 300, 300. Weights N_c/n_c: 1.0, 14.24, 9.77, 15.6, 101.5, 81.64, 645.3. The formula, read from `estimators.capture_recall`:

```
capture recall = num / (num + r6 + c7)
   num = weighted R in C1 to C5;   r6 = weighted R in C6
   c7  = weighted R in C7 if any C7 item is R, else the rule-of-three term  N_C7 x 3 / n_C7
```

| Quantity | Value |
| --- | --- |
| Total weight of captured cells C1 to C5 | 26,854 (C5 alone is 75.6%) |
| Rule-of-three term, no R among 300 C7 items | 193,590 x 3 / 300 = **1,936** |
| **Best case** (every captured item R, none in C6 or C7) | 26,854 / (26,854 + 1,936) = **0.933** |
| Weighted R needed for 0.90 | num ≥ 9 x 1,936 = 17,423, i.e. **at least 64.9% of the captured weight must be R**, with none in C6 or C7 |
| An R found in C7 | replaces the bound by 645.3 per item; three such items equal the bound |
| An R found in C6 | adds 81.6 to the denominator |

So **U9 overstated the full-sample result.** It said capture recall "cannot meet 0.90 by arithmetic". Correctly: it **can** (best case 0.933), but only if about two thirds of the captured weight is relevant and the two cue-free cells contain no relevant items; with C5 carrying 76% of that weight this would need roughly 53% to 60% of C5 to be R even if C1 to C4 were nearly all R. Whether that is plausible depends on labels that do not exist. It is a very demanding target, not an impossible one.

For the **independent subset** the conclusion stands but for a different reason. With realised reweighting (N_c/n'_c) and about 60 C7 items the bound is 193,590 x 3 / 60 = 9,680 and the best case is 26,854 / (26,854 + 9,680) = **0.735**, below 0.90 even if every captured item were relevant. Run through the existing estimator with parent weights the same best case gives **0.357**, because the numerator is scaled by about 0.2 while the bound is scaled by 5 (F4). Neither reaches 0.90.

Pooled recall (the U7 gate) is a different ratio: weighted R among series members over weighted R in C1 to C6. It needs no rule-of-three term, but the heavy C5 and C6 weights make it sensitive: for example, if 80% of a series' members were relevant, gold tolerates no relevant item in C5 or C6, rates about two and three, equity about one and two. This assumes in-series weight comes only from the series' own cell. It is an illustration of fragility, not a result.

**No weight, denominator, target or rule was changed.**

## 4. Decision register

Methodology labels: **M1, M2 and M3 are defined in `reports/phaseB2_completion_decision_document.md` section 2 (table at lines 52 to 61).** The earlier B2-T proposal used a different lettering (options A to D) with similar but not identical designs; the M-labels below are the ones in the decision document. If you meant B2-T's lettering, say so.

| | M1: all human | M2: protected overlap, AI-assisted rest | M3: changed design |
| --- | --- | --- | --- |
| Overlap 312 | you, blind | you, blind; never sent | you, blind; **sent**, hidden AI suggestions |
| Non-overlap 1,181 | you, no AI | AI suggestion, every item reviewed by you | as M2 |
| Transmission | none | 1,181 items | 1,493 items |
| Independent labels | all 1,493 | 312 | 312 |
| Provider and gates A to D | no | yes | yes, plus approval of the design |

**One ambiguity needs your clarification:** the request item "bootstrap polarity and the precise statistical interpretation" mixes two separate things, which I have split into **D7a** (the polarity option, a label-rubric setting) and **D7b** (the statistical interpretation of the bootstrap). Please say which you meant, or both.

---

### D1. Methodology: M1, M2 or M3
- **Meaning.** Decides who labels what, whether any AI is used, and what the independent evidence is.
- **Options.** M1, M2, M3 (above). Nothing else is implemented.
- **Evidence available.** Exclusion and bridge code for M2 (tested, synthetic); the independent subset's size (section 3); effort estimates (15 to 30 s per item, unmeasured): M1 about 6 to 12 h; M2 1.3 to 2.6 h plus review of 1,181.
- **Consequences.** *Validity:* only M1 gives 1,493 independent labels and meets the floor; M2's decision rests on AI-exposed labels (about 79% of the evidence); M3 adds a human-versus-AI result. *Safety:* M1 needs no provider and sends nothing. *Reproducibility:* all three are reproducible; M2 and M3 add provider variability. *Implementation:* M1 none required; M2 and M3 need gates A to D, an adapter, the label path and the B8 amendment.
- **Unknown.** Review speed; model quality; whether you will accept AI-exposed labels in the decision.
- **[RECOMMENDATION]** M1 if the goal is to complete B2 with independent evidence and no provider; M2 only if the AI assistance you chose on 2026-10-13 is still wanted and you accept that the independent labels cannot carry the decision. M3 only if human-versus-AI agreement is itself a wanted result.
- **Approval needed.** A written choice of "M1", "M2" or "M3", with the overlap-first rule if M2 or M3.
- **Affects.** Everything: gates A and D, `protocol.provider_exclusion`, the label path, the criteria's evidence base, effort, the completion plan.

### D2. Exclusion setting (`protocol.provider_exclusion`)
- **Meaning.** Which items may ever reach a provider. Unset blocks execution.
- **Options.** `overlap_and_blind` (the M2 setting), `blind_only`, `none`.
- **Evidence.** Real data: 312 overlap, 0 blind, 1,181 eligible (probe config); the exclusion code is tested on every path.
- **Consequences.** `overlap_and_blind` protects the independent labels. `none` sends everything and is only consistent with M3. `blind_only` leaves non-blind overlap items sendable, which defeats M2. M3 needs blind items sent, which both exclusion modes forbid: **M3 requires `none` or a new mode.**
- **Unknown.** Whether M3 would use a new mode (not implemented).
- **[RECOMMENDATION]** `overlap_and_blind` with M2; not applicable to M1.
- **Approval needed.** The value, recorded in the experiment config and bound by Gate A.
- **Affects.** Gates A and D hashes; dry run; runner; queue; review; tests in `test_ai_overlap_exclusion.py`.

### D3. Reweighting the independent subset by realised cell counts
- **Meaning.** Whether subset estimates use N_c/n'_c instead of the parent N_c/n_c.
- **Options.** Keep parent weights (current); reweight by realised overlap count per cell; do not estimate on the subset at all.
- **Evidence.** Selection is random within cell (verified). Realised counts are known only from the key, which is legitimately read at evaluation.
- **Consequences.** *Validity:* parent weights distort capture recall (F4) and add variance; reweighting is the standard fix and keeps the estimand. *Reproducibility:* deterministic either way. *Implementation:* a change to `Scored.weight` for the subset scope and tests.
- **Unknown.** Realised counts; whether any cell has none (then the cell cannot be reweighted).
- **[RECOMMENDATION]** Reweight, and refuse a subset estimate if any series cell has fewer than a set minimum of overlap items.
- **Approval needed.** The option, and the minimum per cell.
- **Affects.** `estimators.py`, `evaluate.py`, the evaluation fingerprint, the results format, tests.

### D4. Freezing the evaluation criteria in their current form
- **Meaning.** Whether precision ≥ 0.70, bootstrap lower bound ≥ 0.60, pooled recall ≥ 0.90 and the 100-member floor become the approved rule.
- **Options.** Freeze as is; freeze with changes; freeze after D5 and D6.
- **Evidence.** The numbers are B2-I section 4.7, pre-registered, applied literally; no labels exist, so nothing has been tuned.
- **Consequences.** Approval removes "PROPOSED" and makes an outcome authoritative (a code change by you, by design).
- **Unknown.** Whether the pre-registered numbers are attainable (section 3.3).
- **[RECOMMENDATION]** Do not freeze until D5 and D6 are decided, because they change what the criteria mean.
- **Approval needed.** An explicit approval with a reference, then a reviewed change to `decision.py` (`CRITERIA_STATUS`, `CRITERIA_APPROVAL_REFERENCE`).
- **Affects.** `decision.py`, the fingerprint, results, the completion wording.

### D5. Capture-recall target and which recall gates
- **Meaning.** B2-I section 4.7 says "pooled capture recall"; the code gates on **pooled recall** and reports capture recall separately. The documents use the terms inconsistently.
- **Options.** Gate on pooled recall (current); gate on capture recall; gate on both; keep 0.90 or restate it.
- **Evidence.** Section 3.3: capture recall 0.90 is reachable only if at least 64.9% of captured weight is R with none in C6 or C7; the independent subset cannot reach it (best case 0.735).
- **Consequences.** Keeping an unmeetable-in-practice target as a gate makes FAIL likely regardless of filter quality; reporting it separately is honest but changes the criterion's role.
- **Unknown.** The actual label distribution.
- **[RECOMMENDATION]** Keep pooled recall as the gate and capture recall as reported-with-bound (the U7 reading), and record that as the decision rather than leave it implicit. Do not change 0.90 without a stated reason.
- **Approval needed.** Which recall(s) gate, the target, and the wording.
- **Affects.** `decision.py`, B2-I section 4.7 interpretation, the completion wording.

### D6. Bootstrap generator
- **Meaning.** B2-I names numpy `default_rng(42)`; the code uses stdlib `random.Random(42)` because the package may import only the standard library.
- **Options.** Record the stdlib generator as the method of record (current); adopt numpy (a library approval, since the package is standard-library-only); neither.
- **Evidence.** Deterministic and pinned by tests; a golden interval (0.525, 0.675) is a pin, not independent validation.
- **Consequences.** A matching seed does not give matching resamples across generators; changing it changes every interval and the fingerprint.
- **Unknown.** None material.
- **[RECOMMENDATION]** Record the stdlib generator as the method of record.
- **Approval needed.** "stdlib `random.Random(42)`" or "numpy `default_rng(42)`".
- **Affects.** `estimators.py`, the fingerprint, bootstrap tests, B2-I wording.

### D7a. Polarity option
- **Meaning.** The rubric requires a polarity for a theme labelled R; `protocol.polarity_option` records how AI suggestions are asked to handle it.
- **Options.** `P1_required_as_in_existing_rubric` (the only implemented option); anything else is a separate change.
- **Evidence.** Existing rule unchanged and tested; polarity does not affect the filter decision under any option.
- **Consequences.** Needed only if AI is used (M2, M3). Hashed into Gate A.
- **[RECOMMENDATION]** P1 if M2 or M3.
- **Approval needed.** The option name.
- **Affects.** Gate A, the prompt and rubric, `blockers`.

### D7b. Statistical interpretation of the bootstrap *(needs your clarification, see above)*
- **Meaning, as I read it.** What the bootstrap lower bound is: a 2.5th percentile of a batch-clustered resample of weighted precision, 2,000 resamples, resamples with an undefined statistic skipped and counted.
- **Options.** Keep as implemented; change the interval type, resample count, unit or handling of undefined resamples (each a methodology change).
- **Evidence.** Pinned by tests; wider than the unweighted Wilson numbers; with about 1.6 subset items per batch the subset bootstrap is noisy.
- **[RECOMMENDATION]** Keep as implemented and state the definition in the frozen criteria.
- **Approval needed.** Confirmation of the definition, or the change.
- **Affects.** `estimators.py`, `decision.py`, tests.

### D8. Provider selection
- **Meaning.** Provider, pinned model and version, terms and tier.
- **Options.** None exists in code: the adapter registry is empty, and choosing a provider also needs an adapter and possibly a library approval.
- **Evidence.** The B2-U4 package researched options and prices; nothing is approved.
- **Consequences.** Needed only for M2 and M3; binds Gate B; an adapter is a separate approved change.
- **[RECOMMENDATION]** None justified before D1.
- **Approval needed.** Provider, model, version, the credentials variable name, and authorisation to write one adapter.
- **Affects.** Gate B, `provider.ADAPTERS`, dependencies, tests.

### D9. Data handling
- **Meaning.** What leaves the machine and how long it is kept.
- **Options.** M1: nothing. M2: five fields (`item_id`, `batch_date_utc`, `source_domain`, `url`, `title`) for 1,181 items; M3: 1,493.
- **Evidence.** Titles and URLs are public news metadata; 45 URLs carry query strings; raw responses are not expirable today (retention design).
- **Consequences.** Binds Gate C (fields, destination, retention days, terms reviewed).
- **Unknown.** The provider's exact terms.
- **[RECOMMENDATION]** Decide the principle now (whether sending third-party headlines is acceptable), the terms after D8.
- **Approval needed.** Fields, destination, retention period, terms confirmation.
- **Affects.** Gate C, `retention.py`, the retention design.

### D10. `human_uncertain` to `label_basis`
- **Meaning.** The reviewer saw an AI suggestion and marked the item uncertain (at least one theme A, note required). Which working-copy basis records that: `accepted_ai`, `corrected_ai` or `rejected_ai`.
- **Options.** (a) derive it from content: identical to the suggestion is `accepted_ai`, otherwise `corrected_ai`; (b) always `corrected_ai`; (c) keep refusing and require a re-review with another action.
- **Evidence.** All three bases classify the label as **AI-exposed**, so independence stratification is the same under every option; the choice affects only descriptive reporting and which validator checks apply to the item.
- **[RECOMMENDATION]** (a), because it is deterministic and checkable against the verified suggestion.
- **Approval needed.** The chosen option.
- **Affects.** `ai_bridge.BASIS_FOR_ORIGIN` and `UNMAPPED_ORIGINS`, `ai_origin` consistency check, tests.

### D11. `human_insufficient_evidence` to `label_basis`
- Same structure as D10. Additional point: such an item carries `insufficient_evidence = Y` in the review record, which the working-copy format has no column for. **[RECOMMENDATION]** the same rule as D10, and record the flag in `note`. **Approval needed:** the option.

### Decisions this pack adds (not in your list)
- **D12.** Authorise the bridge hardening F1 to F3 (section 2.3).
- **D13.** Authorise the F4 labelling fix in the independent-reference scope.
- **D14.** Raw-response retention: keep, or approve the payload-file design (retention design).

## 5. Safety confirmation [VERIFIED]

No network or provider activity; the sealed key was not opened; nothing under `datasets/` changed; the switches are unchanged; no real label, suggestion, freeze, approval or export record exists; no commit or push. The probes used synthetic data in a temporary directory and a temporary test file that was deleted (the file count is back to 89 status entries). Three new scratch scripts live outside the repository (`u10_capture.py` among them).

## 6. Tests

| Command | Result |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest tests/backend/data/gdelt -q -p no:cacheprovider` (real code, synthetic fixtures) | **794 passed**, 0 failed, 0 skipped, 51 s, exit 0 |
| Hosted-database backend suite, frontend (`tsc`, build, `oxlint`), full-project suite | **not run**; nothing outside the GDELT package changed, and they need hosted services |

## 7. What remains

B2 is incomplete: no approved methodology, no labels, no evaluation, no ingestion. All of section 4 is pending. The next steps are in the [completion plan](phaseB2U10_completion_plan.md).
