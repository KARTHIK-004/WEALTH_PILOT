# Phase B2-U12: M2 selected as the preferred methodology, and the smallest plan to formalise it

Date: 2026-10-19. Status: **a recorded preference and a plan. Documentation only: no code, data, record or switch was changed.** B2 is incomplete, AI execution is blocked, and nothing was committed.

Written for: you, the project owner.

## 1. What this records, and what it does not

**Recorded (your words, 2026-10-19):** your preferred methodology is **M2**, "subject to formalising the unresolved decisions and approval gates". This is your **selection of the preferred methodology only (decision D1)**.

**Not approved by this selection, and still blocked:** provider access or selection; data transmission; AI execution; any adapter; any change to the build lock; retention changes or deletion; any gate A to D record; freezing the evaluation criteria; any bridge fix; full GDELT acquisition. Every one of those needs its own explicit approval, listed in section 6.

**Not yet recorded anywhere as an approval:** no gate record exists, and none was created. The methodology choice is documented here and in `docs/MEMORY.md`; Gate A will bind it later, through the exclusion setting, only when you approve that gate.

## 2. M2, exactly as documented

Source: `reports/phaseB2_completion_decision_document.md` section 2 (table at lines 52 to 61); the "overlap first" rule is line 69.

- **The 312 overlap items:** you label them yourself, blind, and they are **never sent** to a provider.
- **The other 1,181 items:** an AI suggestion is generated, and **every item is reviewed by you**; the use of AI is disclosed.
- **Overlap-first rule (part of the M2 proposal):** label all 312 and record their hash **before any AI suggestion is generated or shown for any item**, because about three normalised titles appear in both sets and a suggestion on a twin could influence an overlap label.
- **Amendment:** M2 needs an amendment to the B2-I section 4.7 decision rule (the "B8 amendment"), because AI-assisted labels would enter the decision.

**Terminology, to avoid a later mix-up.** In M2 the 312 are a *blind* human reference in the plain sense: labelled without any AI suggestion. That is different from the protocol field `blind_item_ids`, a **designated blind subset** from the B2-T hybrid design (labelled blind while hidden AI suggestions exist). **M2 has no designated blind subset**, so `blind_item_ids` stays empty. I use "human-only reference subset" for the 312 below; please say if you meant something else.

## 3. Consequences of choosing M2

### 3.1 What it makes necessary [VERIFIED against the code and documents]

| Consequence | Detail |
| --- | --- |
| A provider is needed | Gates A, B, C and D, a pinned model and version, an adapter (none exists), temperature, limits |
| Transmission | **1,181 items**, five fields each (`item_id`, `batch_date_utc`, `source_domain`, `url`, `title`); 45 URLs carry query strings; the 312 are not sent |
| Exclusion setting | `overlap_and_blind` is the setting that matches M2 (measured: 1,181 sendable, 312 excluded). **Not approved**; it is decision D2 |
| Polarity | needed, because AI suggestions must follow the rubric: the only implemented option is `P1_required_as_in_existing_rubric` (D6) |
| Review-origin mapping | `human_uncertain` and `human_insufficient_evidence` have no defined working-copy basis (D7) |
| Retention | raw responses are not expirable in the current layout (D10) |
| Effort [ESTIMATED, 15 to 30 s per item, unmeasured] | 312 items 1.3 to 2.6 h, plus review of 1,181 (speed unmeasured) |
| Evidence base | about **79%** of the labels (1,181 of 1,493) are AI-exposed and **not independent**; the independent 312 hold about **40 members per series** (an expectation: realised counts are in the sealed key), below the 100-member reporting floor, so they can check a result but cannot carry it |

### 3.2 A consequence found in this phase: the current evaluation cannot reach a PASS or FAIL under M2 [VERIFIED by reading `evaluate.py` and `decision.py`]

The evaluation computes its decision **only on the human-only reference scope** (U8). Under M2 that scope is the 312 items, about 40 members per series, below the floor, so every series would come out `INSUFFICIENT_EVIDENCE`, whatever the AI-assisted labels show. AI-exposed labels appear only in an exploratory scope that deliberately takes no decision. So M2 needs **a decision, and then code, on how AI-assisted and independent evidence combine** in the filter decision. That is the B8 amendment, now listed as decision **D12**. Options (none chosen, none implemented):

| Option | Rule | Effect |
| --- | --- | --- |
| **a** | decide on all labels, including AI-exposed ones, and report the independent subset as a stratified sensitivity result | the decision rests on AI-exposed labels; the independent subset can contradict it but not carry it; needs new code |
| **b** | decide on the independent subset only (the current code) | cannot decide under M2 (always below the floor); AI assistance would then only speed labelling and its labels would not enter the decision |
| **c** | decide on all labels **and** require the independent subset to be consistent with them, by a pre-registered consistency rule | stronger than (a); needs a rule fixed before the first label and new code |

This choice has to be made **before the first label**, because B2-I says the decision rules are fixed first.

### 3.3 How the 312 stay separate from AI-assisted labels

| Control | Status |
| --- | --- |
| The 312 are never sent: the exclusion is checked on submission, resume, retry, a provider wrapper, the queue, review and store validation | [VERIFIED, tested on synthetic data] **only once D2 is approved and recorded**; unset blocks execution |
| Overlap membership comes from a verified manifest, never from IDs or order; it reproduces the pre-registered 20% hash rule exactly (312 of 312) | [VERIFIED] |
| The validator rejects any AI-based `label_basis` on an overlap row and any AI suggestion for an overlap item | [VERIFIED, existing] |
| Each item gets a verified origin (`human_only`, `ai_exposed`, `unlabelled`); an AI-exposed label on an overlap item is a conflict, never a stratum | [VERIFIED] |
| The bridge refuses any suggestion record or citation for an overlap item | [VERIFIED, synthetic tests] |
| The evaluation keeps the reference scope (human-only) apart from the exploratory scope (all labels) | [VERIFIED] |
| **Overlap first: label all 312 and record their hash before any suggestion is generated or shown** | **[NOT ENFORCED IN CODE.** The AI pipeline deliberately never reads the working copy, and no command snapshots a partial label set. At present this is procedure only. `annotate freeze` needs all 1,493 items labelled, so it cannot record the 312 alone.**]** New decision **D13** |
| Realised overlap counts per cell | [UNRESOLVED] only in the sealed key |

### 3.4 What exists for M2 and what does not

| Exists (built offline, synthetic-tested) | Missing |
| --- | --- |
| exclusion code; provenance and AI-origin verification; the bridge (`ai_bridge.py`); the four-way decision on the reference scope; the evaluation fingerprint and stale-freeze refusal; the retention and bridge-hardening designs | the provider decision and **an adapter**; the decision-rule code for D12; an enforcement or procedure for overlap-first (D13); retention implementation (if raw-response expiry is wanted); the real experiment config and gate records; the review workflow for 1,181 items in practice (the batch merge path works but is slower and more error-prone than the interactive labeller); the F1 to F4 fixes; frozen criteria |

## 4. Decisions still open, and what M2 changes about each

| ID | Decision | What M2 changes |
| --- | --- | --- |
| D2 | exclusion mode | `overlap_and_blind` is implied; **not approved**; `blind_item_ids` empty |
| D3 | independent-subset weighting | now relevant: the subset is the independent evidence |
| D4 | recall gate, target, n of the bound | unchanged, now needed; the subset cannot reach 0.90 capture recall (needs at least 195 C7 items, about 60 expected) |
| D5 | bootstrap generator; meaning of "bootstrap polarity" | unchanged; clarification still needed |
| D6 | polarity option | now required (AI is used) |
| D7 | mapping of two review origins | now required |
| D8 | freeze the criteria | now also depends on D12; must precede the first label |
| D9 | provider and data handling | now required |
| D10 | retention | now required before any real response exists |
| D11 | F1, F2, F3, F4a, F4b | F1 to F3 matter for any AI-assisted freeze; F4b depends on D3 |
| **D12 (new)** | how AI-assisted and independent evidence combine (B8 amendment) | the crux of M2 |
| **D13 (new)** | how overlap-first is enforced and its hash recorded | M2-specific |

## 5. The smallest dependency-ordered plan

**Principle.** Nothing below is scheduled as approved. Each step names what it needs from you and what it unlocks. Steps in the same round can be answered together and do not wait on each other unless an arrow says so. Fixes F1, F2, F3, F4a and F4b stay **separate** authorisation items.

```
ROUND 1: decisions, no code (answer together)
   D2  confirm overlap_and_blind and an empty blind_item_ids
   D12 evidence-combination rule (a, b or c)               ← the crux
   D4  recall gate, target, n of the bound
   D5  bootstrap generator; meaning of "bootstrap polarity" and "pooled capture recall"
   D3  weighting (parent, reweight + minimum per cell, or no subset estimate)
   D6  polarity option (P1 is the only implemented)
   D7  mapping of the two review origins (keep refusing / state a mapping / use accept-edit-reject only)
   D13 overlap-first: procedure only, or a code control
        │
ROUND 1b: authorisations (independent of each other and of the decisions, except F4b)
   F1   F2   F3   F4a        each yes or no
   F4b  yes or no            ← only after D3 = reweight
        │
ROUND 2: D8 freeze the criteria and the D12 rule         ← needs D3, D4, D5, D12; must precede the first label
        │
ROUND 3: code that Round 1 decides (each needs its own authorisation)
   R3.1 evidence-combination code for D12 (a or c)       ← skipped if D12 = b
   R3.2 overlap-first control for D13                    ← skipped if D13 = procedure only
   R3.3 any of F1 to F4 you authorised
        │
ROUND 4: provider and data handling                      ← needs D1 (done), D6
   D9   provider, pinned model and version, temperature, terms and tier, credentials variable name,
        fields sent, headlines and 45 query-string URLs acceptable?, limits, spending cap, authorise one adapter
   D10  approve, reject or revise the retention design; set the period
        ├─ R4.1 retention implementation (only if approved; must precede the first real response)
        └─ R4.2 adapter (separate authorisation; written but not registered)
        │
ROUND 5: the real configuration
   R5.1 experiment config; dry run; you create gate A, B, C, D records bound to the dry-run hashes
        │
ROUND 6: labelling (overlap first)
   R6.1 label the 312 with `annotate label` (no AI, nothing sent); record their hash         ← needs Round 2, D13
   R6.2 lift the build lock, register the adapter, explicit execution authorisation, run      ← needs Rounds 1 to 5 and R6.1
   R6.3 review all 1,181 (`ai review`), export, bridge into the working copy (`labels_for_merge` and `annotate merge`)
   R6.4 `annotate freeze` (you create it) and `annotate evaluate` (the only step that opens the key, once)
```

**Why this is the smallest set.**
- Round 1 holds only the decisions that change what is built or what is claimed; nothing in it needs code.
- F1 to F3 only tighten verification and are needed before any AI-assisted freeze, so they are in Round 1b rather than later; each is a separate yes or no.
- R3.1 and R3.2 disappear if D12 = b (but then M2 cannot decide, see 3.2) or D13 = procedure only.
- R4.1 disappears only if you decide that raw responses need not expire, which is still a decision (D10), not a default.
- Full-window acquisition is **not** on this path and stays a separate authorisation.

**What can be done now, offline, without any approval beyond what you have given:** nothing further is required of me except to record answers. F1 to F4b wait for your yes or no.

## 6. What I need from you, in one reply

Write each of these (or "defer"); anything missing stays pending:

1. **D2:** "overlap_and_blind, blind_item_ids empty", or other.
2. **D12:** a, b or c.
3. **D4:** gate on pooled recall, capture recall or both; keep 0.90 or restate; which n for the rule of three.
4. **D5:** stdlib or NumPy generator; what "bootstrap polarity" and "pooled capture recall" mean.
5. **D3:** parent weights, reweight (with a minimum per cell), or no subset estimate.
6. **D6:** P1, or another option.
7. **D7:** keep refusing, state the mapping, or use accept, edit or reject only.
8. **D13:** overlap-first by procedure only, or by a code control.
9. **F1, F2, F3, F4a, F4b:** each "authorise" or "hold".
10. Later, in their own replies: D8 (freeze), D9, D10, the gate records, the build-lock change and the execution authorisation.

## 7. State after this phase [VERIFIED]

HEAD `71b363f`; build lock `False`; adapter registry empty; no gate, freeze, approval, experiment or export record; sealed key unopened (142,900 bytes, 2026-10-13 22:28:16 +0530); `datasets/` unchanged; `NETWORK` and `DEV_SAMPLE` unchanged; no network or provider activity; no commit. **B2 remains incomplete.**

## 8. Decision log (appended 2026-10-19)

### D2 decided: exclusion mode `overlap_and_blind`, `blind_item_ids` empty

**Your words:** "D2: overlap_and_blind. Keep blind_item_ids empty. This is an exclusion-mode decision only; provider access, data transmission and AI execution remain unapproved."

**Recorded as:** the project owner's decision for D2. Scope: **the exclusion setting only.**

**What it means [VERIFIED against `ai/config.py` and the non-writing dry run in U11]:**
- Every original overlap item is excluded from any provider submission: 312 items, taken from the verified manifest, never inferred from IDs or order.
- No item is designated blind (`blind_item_ids` empty), so the blind part of the mode excludes nothing extra. The partition reports `matches_proposed_m2: true`, 312 human-only reference items, 0 blind items, 1,181 AI-eligible items (eligible-set hash `97f33744776fb73c0dc50093251f132b82fd6e4682f9643127fb4c04956c87ec`).
- The 312 stay protected on every path (submission, resume, retry, a provider wrapper, the queue, review, store validation), and a change to membership or to the setting makes any later approval stale.

**What it does not do:**
- It creates **no** experiment config and **no** gate record. Gate A will bind this setting (`provider_exclusion`) together with the polarity option, the empty blind list and the overlap file hash only when you create that record, after D6; until then nothing is bound.
- It does not approve provider access, data transmission, AI execution, an adapter, retention changes or acquisition. The build lock is `False` and the adapter registry is empty.
- It does not decide the other open items. D12 (how AI-assisted and independent evidence combine) and D13 (how overlap-first is enforced) are still the crux.

**Still true after this decision:** under M2 the current evaluation can only return `INSUFFICIENT_EVIDENCE` until D12 is decided and coded; the overlap-first rule is procedure only until D13 is decided.

### Plan state after D2

| Item | State |
| --- | --- |
| D1 methodology | **M2 selected (preferred)** |
| D2 exclusion mode | **decided: `overlap_and_blind`, `blind_item_ids` empty** |
| D3, D4, D5, D6, D7, D12, D13 | open (Round 1) |
| F1, F2, F3, F4a, F4b | each awaiting your authorisation; none implemented |
| D8 freeze, D9 provider and data handling, D10 retention, gate records, build-lock change, execution, acquisition | not approved |

**Next question I need answered, in order of what unblocks the most:** D12 (a, b or c), then D4 and D5, then D3, D6, D7 and D13.

### D12 decided: option (c) (appended 2026-10-19)

**Your words:** "D12 option (c)".

**Recorded as:** the project owner's selection for D12, using the option text from section 3.2 unchanged: **(c) decide on all labels and require the independent subset to be consistent with them, by a pre-registered consistency rule.** Scope: the **principle of how the evidence combines** only.

**What it means under M2 (D1 = M2, D2 = `overlap_and_blind`, no blind subset):**
- The filter decision is taken on **all labels**, including AI-exposed ones, which are disclosed by origin and never described as independent.
- The 312 human-only reference items act as a **gate**: the result stands only if they are consistent with the all-label result under a rule fixed **before the first label**.
- The four outcomes (`PASS`, `FAIL`, `INSUFFICIENT_EVIDENCE`, `INVALID_EVALUATION`) stay. How a consistency failure maps onto them is not yet defined.

**What it does not do:**
- The consistency rule **does not exist yet**, so (c) is selected but **not specified, not implemented and not frozen**. The current code still decides only on the human-only scope.
- No criterion, weighting, recall metric, bootstrap method, minimum sample size or threshold was set or changed. D3 to D8 stay open.
- No gate record, experiment config, provider access, data transmission, AI execution, retention change, fix authorisation or acquisition is approved. Build lock `False`; adapter list empty.

**New sub-decision D12.1: the consistency rule (needed before D8, the freeze).** It must say, in your words:
1. **What is compared:** the independent (312) stratum against the AI-exposed stratum on precision only, or also on the lower bound or recall.
2. **Direction and form:** a one-directional guard that flags independent precision **lower** than the AI-exposed precision (anchoring would inflate the AI-exposed side), or a two-sided comparison. At about 40 members per series the independent stratum can only detect a large gap, so the rule has to be a guard, not a claim of equivalence.
3. **Tolerance:** the size of gap, or the test and its error rate, at which the guard fails. This is a **new threshold that only you can set**; I will not propose a number tuned to data.
4. **Outcome mapping:** which of the four outcomes a failed guard gives, and how a below-floor independent stratum is treated (it is always below the 100-member floor).
5. **Weighting:** the comparison depends on D3 (parent weights distort a subset estimate), and on D4 and D5 for the metric and the bootstrap.

**Plan state:** D1 M2, D2 `overlap_and_blind`, D12 (c) are decided; D12.1, D3, D4, D5, D6, D7, D13 and the F1 to F4b authorisations are open; D8 (freeze) must follow D12.1, D3, D4 and D5.

### Approved decisions and offline implementation (2026-10-19)

**Approved by you:** D12.1 precision-only one-directional guard, tolerance 0.10, no significance test, a failed guard maps to `INSUFFICIENT_EVIDENCE`; D3 realised-cell reweighting with at least 30 non-ambiguous human-only members per series and at least one reference item in every cell a metric uses (otherwise the subset estimate is refused); "bootstrap polarity" is an undefined term, dropped, bootstrap unchanged; F1, F2, F3 and F4b authorised, F4a held; D4 pooled recall 0.90 as the gate with capture recall reported separately (rule-of-three, unchanged); D5 `random.Random(42)`; D6 `P1_required_as_in_existing_rubric`; D7 accept/edit/reject only, unsupported origins stay blocked; D13 offline overlap-first control with verification against the originals, label schema, provenance and the recorded hash.

**Implemented, offline, in four batches (all synthetic-tested; 852 GDELT tests pass, from 794):**

| Batch | Change | Files |
| --- | --- | --- |
| 1: F1, F2, F3 | the suggestion-chain head must equal the manifest's; the review chain is verified and each exported review hash must equal the current review record; the manifest's review and audit heads must appear in their chains (the audit head is only an ancestor); a missing suggestion chain in a real B2-T layout is refused (no legacy fallback), except for an experiment whose manifest records a genesis head | `ai_bridge.py`, `ai_origin.py` |
| 2: D3, F4b | `evaluate._reweighted` gives each subset item weight N_c / n'_c; a subset estimate is refused if fewer than 30 non-ambiguous human-only members or a metric cell has no item; capture recall in the subset now uses consistent weights (best case 0.7351 where the old output gave 0.3569) | `evaluate.py` |
| 3: D12(c), D12.1 | the decision uses all labels (AI-exposed ones disclosed, never independent); the guard flags AI-exposed precision exceeding human-only precision by more than 0.10 (equality passes; both strata realised-reweighted); a failed or not-evaluable guard gives `INSUFFICIENT_EVIDENCE`, `INVALID_EVALUATION` stays, the base outcome is kept; the reference scope takes no decision of its own; the settings are in the evaluation fingerprint | `decision.py`, `evaluate.py` |
| 4: D13 | `annotate lock-overlap` verifies the overlap label rows against the original items, the approved label schema (human-only rubric validator) and the provenance records, and writes a read-only record with their SHA-256; `protocol.overlap_labels_sha256` binds it into Gate D; the dry run and `ai run` refuse without a matching record (the AI package reads only the record, never a label); every run manifest carries the hash; freeze and evaluate revalidate the labels against it and check the manifests, before the key, whenever any label is AI-exposed; timestamps are recorded but not relied on | `overlap_lock.py` (new), `ai/config.py`, `ai/runner.py`, `evaluate.py`, `cli.py` |

**Points to confirm (my interpretation, reversible):**
1. A guard that cannot be evaluated (the human-only estimate was refused) also gives `INSUFFICIENT_EVIDENCE`, because the independent check then cannot be made.
2. A failed guard maps to `INSUFFICIENT_EVIDENCE` even when the base outcome is `FAIL` (the approved wording); the base outcome is kept in the result so nothing is hidden.
3. When no label is AI-exposed (all human), the guard is not applicable and the base decision stands.
4. The 0.10 tolerance is recorded in the result as a pre-registered operational threshold, not a statistically validated boundary.

**Effect on the real data:** none. No lock record, config, gate record, freeze or suggestion exists; the non-writing dry run now lists one more unmet prerequisite (16, the unset overlap-labels hash). The criteria are still `PROPOSED_NOT_APPROVED` and no result is authoritative.

**Still open:** D8 (freeze the criteria), D9 provider and data handling, D10 retention, gate A to D records, the build-lock change and an adapter, execution authorisation, and full-window acquisition. F4a stays on hold. Nothing was staged or committed.

### Points 1 to 4 confirmed, and D8 decided (2026-10-19)

**Confirmed by you:** (1) a guard that cannot be evaluated because the human-only estimate was refused gives `INSUFFICIENT_EVIDENCE`; (2) a failed guard gives `INSUFFICIENT_EVIDENCE` even when the base outcome is `FAIL`, with the base outcome preserved and displayed (`base_outcome` in every decision); (3) with no AI-exposed label the guard is not applicable and the base decision stands; (4) the `overlap_items` count in `selection_log.json` is skipped only when the field is absent and must equal the verified membership when present. All four were already the implemented behaviour and are covered by tests; no other integrity check was weakened.

**D8 approved: freeze the current evaluation criteria.** Precision at least 0.70; bootstrap lower bound at least 0.60; pooled recall at least 0.90; reporting floor of 100 non-ambiguous members. Recorded as the project owner's approval of 2026-10-19.

**Verified before freezing: the criteria match B2-I and the implemented code.**

| Criterion | B2-I section 4.7 and 4.6 | Implemented (`decision.CRITERIA`, `estimators`) | Match |
| --- | --- | --- | --- |
| Precision, ambiguous excluded | at least 0.70 | 0.70, equality passes | yes |
| Bootstrap lower bound | at least 0.60 | 0.60, 2.5th percentile of 2,000 batch-cluster resamples | yes (generator differs, see below) |
| Recall | "pooled capture recall" at least 0.90 | gates on `pooled_recall` at 0.90; capture recall reported with its rule-of-three bound | **interpretation recorded (D4)** |
| Reporting floor | 100 or more non-ambiguous members is an estimate; fewer is indicative or counts only and cannot pass | 100; below it the outcome is `INSUFFICIENT_EVIDENCE`; applied to precision and its lower bound, on the all-labels scope | yes |

**Discrepancies found, reported and not silently changed:**
1. **Recall wording.** B2-I 4.7 says "pooled capture recall"; the code gates on pooled recall. This is the D4 interpretation you confirmed; the historical text is unchanged and a note points here.
2. **Bootstrap generator.** B2-I names numpy `default_rng(42)`; the code uses `random.Random(42)` (D5, confirmed). A matching seed does not give matching resamples; no result exists, so none is affected.
3. **Outcome vocabulary.** B2-I uses FREEZE, REVISE, NOT USABLE and INCONCLUSIVE; the code uses `PASS`, `FAIL`, `INSUFFICIENT_EVIDENCE`, `INVALID_EVALUATION`. Roughly `PASS` is FREEZE and `INSUFFICIENT_EVIDENCE` is INCONCLUSIVE; `FAIL` stands for REVISE or NOT USABLE. **The B2-I revision path (one revision, estimated on stage C only, which needs a separate download approval) is not implemented and is not part of D8.**
4. **Additions to B2-I 4.7** that you approved separately and that are now part of the evaluation: the D12(c) combination of all labels with the consistency guard (the B8 amendment), the D12.1 tolerance of 0.10, and the D3 subset minimum. They are bound into the same freeze.
5. **Names.** `estimators.PROPOSED_THRESHOLDS` and `proposed_threshold_checks` keep their old names (they are in the fingerprint and decide nothing); the approved values are in `decision.CRITERIA`.

**How D8 was recorded (the repository's defined workflow).** `decision.py` states that approval is "a separate, explicit, recorded act by the project owner" made as a reviewed change to `CRITERIA_STATUS` and `CRITERIA_APPROVAL_REFERENCE`. That change was made: status `APPROVED`, reference "B2-U12 D8: project owner approval of 2026-10-19", and, as an added safeguard, `APPROVED_CRITERIA_SHA256` (the hash of the criteria, the guard and the recall gate). `criteria_authoritative()` is true only while all three hold, so changing any threshold later without a new approval removes the authority and makes every outcome non-authoritative again. Nothing can set it from data, a file, an environment variable or a command-line option (tested).

**What D8 does and does not do.** Outcomes are now authoritative against the approved criteria, and every decision still carries `authorizes_execution_or_deployment: false`. **No experiment freeze artifact, evaluation result, gate record or experiment config was created**; `annotate freeze` remains a separate operation that you create. The evaluation fingerprint changed (the criteria status is part of it); no freeze exists, so nothing was invalidated. Provider access, data transmission, AI execution, sealed-key access, an adapter, the build lock, retention and full-window acquisition remain unapproved. B2 remains incomplete.

**Tests:** 863 GDELT tests pass (852 before), including tests that each approved threshold, the guard tolerance, the subset minimum and the recall gate are exactly the approved values, that changing any of them removes the authority, and that an authoritative outcome authorizes nothing.

**Still open:** D9 provider and data handling, D10 retention, gate A to D records, the build-lock change and an adapter, execution authorisation, the B2 completion wording, and full-window acquisition. F4a stays on hold.

### D9 draft prepared; adapter not implemented because its authorisation is not recorded (2026-10-19)

**Prepared (unapproved draft):** `config/gdelt/b2t_haiku55_DRAFT_UNAPPROVED.yaml`, the proposed Anthropic `claude-haiku-5-5` configuration from the D9 sheet. It is headed as an unapproved draft and creates no record: all four approvals are `null`; `provider_data_terms_reviewed` is `false`; `retention_days`, `run_id` and `protocol.overlap_labels_sha256` are `null`; region, zero data retention and data transmission are not represented and stay unresolved; the credentials entry is only the proposed variable name `ANTHROPIC_API_KEY` (its value is never read). The values that follow from earlier decisions are D2 `overlap_and_blind` with no blind items, D6 `P1_required_as_in_existing_rubric`, and `temperature: 1.0` (the only value the model accepts). The limits are the D9 proposals (1,600 requests, 2,400,000 input tokens, 400 output tokens, cap USD 0.70) and are unapproved.

**Non-writing dry run on the draft** (`ai dry-run --experiment config/gdelt/b2t_haiku55_DRAFT_UNAPPROVED.yaml`): `provider_called`, `data_sent` and `files_written` all `False`; 1,493 items, **1,181 sendable, 312 excluded**; the M2 partition check reports no problems; estimated input 1,378,386 tokens, output upper bound 472,400, cost upper bound USD 0.374 at the draft prices. **12 unmet prerequisites:** the build lock; the missing `--confirm-ai-run`; no adapter for `anthropic`; the unset overlap-labels hash; the API-key variable not set (name checked only); terms not reviewed; no retention days; no run ID; and no gate A, B, C or D record. Draft gate hashes (for the dry run only, **not for approval**): A `52ea6eb1…`, B `07f89dd0…`, C `6d7f01f8…`, D `027088bb…`. The destination folder was not created.

**Adapter: stopped and asked.** `ai/provider.py` says writing and registering an adapter "is a separate change that needs approval Gate B (provider and model)". Gate B has no record, the provider and model are still an unapproved draft, and no recorded authorisation for an adapter exists in this log. So the standard-library HTTPS adapter and its fake-transport tests were **not** written. Nothing was registered, `ADAPTERS` is still empty and the build lock is `False`.

**Checked against the official documentation** (pages fetched 2026-10-19; no request sent): endpoint `POST https://api.anthropic.com/v1/messages`; headers `x-api-key`, `anthropic-version: 2023-06-01` and `content-type: application/json` (the version value is from the official errors page's curl example); model ID `claude-haiku-5-5`, a fixed ID with no date suffix and no alias; `temperature`, if sent, must be `1`; `thinking: {"type":"disabled"}` is accepted by Claude Haiku 5.5 at `high` effort or below, and a request with a small `max_tokens` can otherwise stop after a thinking block with `stop_reason: "max_tokens"`; assistant prefill is rejected; a safety refusal arrives as `stop_reason: "refusal"` with no fallback; errors are JSON with `type`, `message` and `request_id`, and a `request-id` header; 400 `invalid_request_error` (also for a spend limit you set), 401, 403, 404, 413, 429 `rate_limit_error` (a tier spend-cap 429 has no `retry-after` and keeps failing), 500 `api_error`, 504 `timeout_error`, 529 `overloaded_error`. **Not confirmed from the pages read:** the success response's `model` and `usage.output_tokens` fields and the full list of stop reasons (the reference page text was truncated before its response section); an adapter would need that page read in full before it can be finished.

### Adapter authorisation recorded (2026-10-19)

**Your words (B2-U13):** you explicitly authorised **writing and offline fake-transport testing only** of a standard-library HTTPS adapter, at `backend/wealthpilot/data/gdelt/ai/adapters/anthropic.py`, for the draft model `claude-haiku-5-5`.

**Recorded scope.** Authorised: write that one adapter module (plus its package marker and tests) and test it with fake transport and synthetic fixtures only.

**Not approved by this authorisation, and still blocked:** provider use; any real network request or data transmission; registering the adapter in `ADAPTERS`; enabling it or the build lock; any experiment execution or `ai run`; any Gate A, B, C or D approval; the terms attestation; retention, region or data-transmission approvals; reading the API key or the sealed key. The draft config stays unapproved. A passing test suite is not permission to execute.

### Adapter written and tested offline (2026-10-19)

**Written:** `backend/wealthpilot/data/gdelt/ai/adapters/anthropic.py` (standard library only) and the package marker `ai/adapters/__init__.py`. **Not registered:** `provider.ADAPTERS` is untouched and still empty; the module has `REGISTERED = False`; `build()` refuses unless the build lock is lifted and a gate-issued authorisation exists; the build lock is `False`. It follows the existing `SuggestionProvider` interface (`name`, `suggest(SuggestionRequest) -> ProviderResponse`, `ProviderError` kinds and `RETRYABLE_KINDS`) and the `factory(cfg, auth)` convention.

**Design.** Transport is injected (`Transport` protocol); the only code that can reach the network is `UrllibTransport` (HTTPS to `api.anthropic.com` only, no redirects), and no test constructs or calls it. One transport call per `suggest`: retries, back-off, attempt, request, input-token and cost caps stay in the existing runner, so the adapter cannot loop. The request body is exactly `model: claude-haiku-5-5`, `max_tokens`, `temperature: 1`, `thinking: {"type": "disabled"}`, `system`, and one user message; any other temperature, an oversized request or a bad output limit is refused before anything is sent. Headers: `x-api-key`, `anthropic-version: 2023-06-01`, `content-type: application/json`. A response is accepted only if it is an HTTP 200 assistant `message` with `stop_reason: "end_turn"`, plain text blocks and valid `usage` (input = `input_tokens` plus cache tokens); a refusal (`stop_reason: "refusal"`) is never retried and its explanation is never copied; a spend-cap 429 is not retried; the returned model is passed to the runner, which stops the run on a mismatch. Error details contain only the HTTP status, a documented error type and a fixed phrase; the key is redacted from everything and kept out of `repr`.

**Verified against the full official reference** (success response, `usage`, stop reasons, `temperature` note that Claude Haiku 5.5 accepts only 1.0, the official curl example for headers; read 2026-10-19, nothing sent). **Not verified, so handled safely:** any provider error message text (never used); whether a thinking block can appear with thinking disabled (any non-text block is treated as malformed and the item falls to human-only labelling); the rate limits for the owner's account tier.

**Tests:** `tests/backend/data/gdelt/test_anthropic_adapter.py`, 94 tests, fake transport and synthetic fixtures only: request schema, headers and pinned model; temperature 1 and disabled thinking; success and usage parsing; unexpected model, missing fields, malformed JSON; refusal; HTTP 400, 401, 402, 403, 404, 409, 413, 429 (ordinary and spend cap), 500, 504, 529, 503, 302; timeout and transport failure; one call per `suggest`; bounded retries and back-off through the real runner; the request, input-token and cost caps and the output limit; secret redaction (including that the key is absent from every stored record); no network; unregistered and disabled; the draft config unapproved; no gate record, experiment folder or freeze. A mutation check (thinking, refusal, rate-limit class, redaction) made 6 tests fail. The full GDELT suite passes: 957 (863 before).

**Still blocked and unapproved:** provider use, any real request or data transmission, registration, enabling the adapter, the build lock, `ai run`, gates A to D, the terms attestation, retention, region and data-transmission approvals, D10, the overlap-labels lock, and full-window acquisition. B2 remains incomplete.

### Offline validation and AI-only isolation implemented (2026-10-20, B2-U18)

**Scope (offline only; no methodology change).** Added: `annotation_rules.py` (rule-based validation: enumerations, polarity, ambiguity, duplicate references including self, unknown, malformed and circular links, missing, duplicate and unknown IDs, source-field and overlap-membership consistency, and non-human or AI-only annotator and basis detection); `ai_only.py` (a separate, hash-chained, permanently non-independent suggestion schema `b2_ai_only_suggestion_v1` and store, which must lie outside any annotation review folder, ingests a raw response only through the existing strict output validator, rejects an overlap item, stores no raw text (hash only) and is idempotent); `metric_status.py` and the read-only command `annotate metric-status` (per D8 metric: estimand, data needed, independent labels available, computable, uncertainty defensible, authoritative decision permitted); `decision.decide_without_independent_evidence` (always `INSUFFICIENT_EVIDENCE`, never authoritative). `provenance.verify` now also blocks a labelled working-copy row whose annotator is not human or whose basis is `ai_only` (`ai_only_contamination`, `non_human_annotator`).

**Isolation.** No evaluation, reference, bridge, lock or labeller module imports `ai_only`, and `ai_only` imports none of them (tests check both ways). The metric-status report is its only reader, and it counts AI-only records as exploratory and non-independent. With no valid independent human labels every accuracy metric is `unavailable` and every series decision is `INSUFFICIENT_EVIDENCE`; with AI-exposed labels alone the same. Provenance mismatch gives `invalid_provenance` and `INVALID_EVALUATION`. With independent labels the status is `requires_frozen_evaluation` and nothing is estimated.

**Unchanged:** the D8 thresholds, the criteria hash and approval, the D12/D12.1 guard, the D13 lock, the gates, the sealed key (never read), the build lock (`False`), the adapter registry (empty) and the draft config (unapproved). No provider call, network access, dataset change or label.

**Tests:** 68 new offline tests in `tests/backend/data/gdelt/test_offline_validation_ai_only.py`; the full GDELT suite passes (1,025, from 957). A mutation check (independence flag, overlap rule, contamination check, no-evidence decision) made 9 tests fail.

**Limitation:** AI-only suggestions exist only as a schema and store: nothing generates them (no provider is approved), and no accuracy can be reported from them. Authoritative accuracy still needs independent human labels.
