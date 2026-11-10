# Phase B2-U9: label-bridge investigation and research readiness audit

Date: 2026-10-19. Status: **the label bridge is implemented offline and tested; the readiness audit is complete. This is not B2 completion.** AI execution is still blocked. No model or provider was called, no data was sent, no label, suggestion, freeze or approval record was created, and nothing was committed.

Written for: you, the project owner. Verified facts are kept apart from recommendations. Every methodology, metric, provider, data-handling and execution decision is still pending.

> **Superseded in part by B2-U10 (2026-10-19), section 3.3 of `phaseB2U10_readiness_report.md`.** Section 4 says capture recall "cannot meet 0.90" on all items. That is overstated: the best case is 0.933, so 0.90 is reachable only if at least 64.9% of the captured weight is relevant with none in C6 or C7. On the independent subset the conclusion stands (best case 0.735 with realised reweighting; 0.357 under parent weights, which is an inconsistency in the U8 scope output). The rest of this report is unchanged.

**Labels:** [VERIFIED] checked in code, by a test or by a read-only run; [IMPLEMENTED] code exists and is tested; [DERIVED] arithmetic from public numbers, not data; [UNVERIFIED] cannot be checked with what may be opened; [PENDING] a decision that stays yours.

---

## 1. Starting state, verified before any edit

| Check | Result |
| --- | --- |
| U7 and U8 reports, decision document, architecture document, instructions | read; the U8 conclusions below were each re-checked against the source |
| GDELT suite | [VERIFIED] **765 passed**, as the U8 report states |
| Repository | [VERIFIED] `HEAD` `71b363f`; 88 status entries (the gdelt package is untracked as a whole) |
| Build lock; adapter registry | [VERIFIED] `False`; `{}` |
| Real review folder (read-only) | [VERIFIED] provenance `VERIFIED`; 1,493 items, 312 overlap, 1,181 non-overlap; 0 labelled; no freeze, results, suggestion file or approval record |
| U8's blocking claim | [VERIFIED, with a correction below] the legacy validator refuses an AI-based label unless `ai_suggestions_A.csv` holds a valid suggestion, and the B2-T store keeps suggestions elsewhere |

**Correction to U8.** U8 called the formats incompatible. Reading both, they are not: the B2-T derived CSV's columns (`VALID_CSV_COLUMNS`) are a **superset** of the legacy file's required columns (`AI_SUGGESTION_COLUMNS`), and the legacy loader allows extra columns. What was missing was a way to supply the B2-T suggestions to the validator **after verifying them**, without writing a legacy file. That is the only thing built.

## 2. The label bridge

### 2.1 The traced data flow

```
B2-T:  ai run (blocked) -> suggestions/ai_suggestions_raw_v1.jsonl (hash chain; derived CSV)
       ai review        -> review/reviews_v1.jsonl (hash chain; a human action per item, AI seen or not)
       ai export        -> export/annotation_b2t_v1.csv + EXPORT_MANIFEST.json   (reads reviews, never the working copy)

Legacy: annotate export-batch -> (human fills labels) -> annotate merge -> working copy -> freeze -> evaluate
        annotate.validate accepts label_basis != own only for an item in ai_suggestions_A.csv
```

Nothing joined the two. No code carried a reviewed B2-T label into the working copy, and the validator could not see the B2-T suggestions.

### 2.2 What was built [IMPLEMENTED]

A read-only module, `ai_bridge.py`, plus small, backward-compatible hooks.

| Piece | Behaviour |
| --- | --- |
| `ai_bridge.load(paths, export_dir)` | Returns a **verified** suggestion set, or `None` when no B2-T suggestion chain sits next to the export (then the legacy source applies, unchanged). It rejects the **whole set** unless: the raw hash chain verifies; the experiment snapshot is of this exact original file; the verified overlap equals the original's; every record is for a known, non-overlap item; each terminal `valid` record carries the item's current input fingerprint, has `validation.ok`, and passes the **same rubric validator as a human label**; and the derived CSV equals what the chain produces. It writes nothing |
| `annotate.validate / merge(..., ai_suggestions=...)` | An optional argument. Default `None` is exactly the old behaviour. When given, it replaces the legacy file as the suggestion source. If `ai_suggestions_A.csv` also exists, **both are refused** (two sources for one item set are ambiguous). Overlap items still need `label_basis = own` whatever the source |
| `ai_bridge.labels_for_merge(paths, export_dir)` | Pure. Turns *verified review records* into label rows for the existing batch merge, and lists every item it refuses. It writes no file |
| `ai_origin.attach` (extended) | When the bridge exists, each AI-seen review must cite **the verified valid suggestion for that item** (`suggestion_ref` equals its record hash); an **accepted** label must equal that suggestion; an **edited or rejected** label must differ from it; a review that says "no suggestion existed" is refused if the verified store holds one; and the review origin must agree with the working copy's `label_basis` |
| `freeze`, `evaluate`, CLI | Use the bridge when `--ai-experiment` names an experiment. The suggestion chain's hash is in the evaluation fingerprint, so changing the store after a freeze makes the freeze stale. `annotate validate`, `merge`, `freeze` and `evaluate` all take `--ai-experiment` |

**Origin to `label_basis` mapping, and what is deliberately not mapped:**

| Review origin | `label_basis` |
| --- | --- |
| `human_no_suggestion`, `human_blind` | `own` |
| `accepted_ai` | `accepted_ai` |
| `edited_ai` | `corrected_ai` |
| `rejected_ai_after_seeing` | `rejected_ai` |
| `human_uncertain`, `human_insufficient_evidence` | **refused, not guessed.** The AI was seen, but which of the three AI bases applies is a protocol decision |

### 2.3 What was not done, on purpose

No legacy suggestion record was created; no human approval was fabricated; the legacy validator was not weakened (its default path and every existing test are unchanged); no label, original, backup, working copy or snapshot was altered; no conversion was guessed. `labels_for_merge` refuses an item that is already labelled (a change is a correction, not an overwrite), an item with an unmapped origin, and everything if the export or the store does not verify. The provider adapter is absent and every gate is closed.

### 2.4 What this does and does not prove [VERIFIED]

**Proved on synthetic data only:** the real pipeline code was run with a scripted fake provider (the lock lifted inside a test) through suggestion, review, export, bridge, merge, verification, freeze and evaluation. The legacy merge, given the same labels, accepts none of them; the bridged merge accepts all 8. Forged exports (an "accepted" label that is not the suggestion, a false citation, a false "no suggestion"), a tampered chain, a hand-edited derived CSV, a wrong snapshot, an overlap-item suggestion, wrong-input suggestions and rubric-invalid suggestions are each refused. Mutation check: removing two of the bridge's checks made 2 tests fail.

**Not proved:** anything on real AI output. None exists. Whether a *human* is willing to run `labels_for_merge` into a batch and merge is a workflow, not code. The two unmapped origins need your decision before any item with them can enter the working copy.

## 3. Reference-sample representativeness audit

Read: `annotation_A.csv` (public columns only), `selection_log.json`, the build code and the B2-I text. **The sealed key was not opened** (size and time checked, unchanged).

### 3.1 Known selection facts [VERIFIED]

| Fact | Evidence |
| --- | --- |
| Overlap membership is a pre-registered **hash rule**: an item is overlap if the first 8 hex digits of SHA-256(`seed\|iaa\|<GKGRECORDID>`) are below `0x33333333` (probability 0.2 per item) | B2-I section 4.4 step 4; `review.py` |
| The rule reproduces the file **exactly** | recomputed for all 1,493 items from the public `gkg_record_id`: 312 of 312 overlap items match and 0 mismatches |
| Membership uses only the record ID, so it is independent of the item's cell by construction | the cell is assigned from content in a separate step |
| The items themselves were drawn within each cell by a seeded hash order (a stratified random sample), and were then shuffled | `review.py` |
| Observed 312 of 1,493 (20.9%) against 298.6 expected, standard deviation 15.5 | z = 0.87, consistent with the rule |
| Public columns are balanced between overlap and non-overlap | by duplicate mark: ORIGINAL 20.6%, SYNDICATED 22.0%, DUP_SAME_BATCH 3 of 10; by month, chi-square 23.8 on 24 degrees of freedom; by the 15 biggest domains, chi-square 3.1 on 2; mean item index 745.5 against 747.4 |
| The original **purpose** of the overlap | B2-I defined it as the subset a **second annotator** labels, to measure agreement (Cohen's kappa), not as an independent reference for precision |
| Labels | 0 of 1,493 labelled, so nothing about relevance, ambiguity, polarity or company-notice coverage can be examined |

### 3.2 Not verifiable here [UNVERIFIED]

| Question | Why it cannot be answered now |
| --- | --- |
| How many overlap items fall in each cell and series (C1 to C7) | cell and series membership exist only in the sealed key |
| Whether labels are independent of the hash | no labels exist; the hash is standard SHA-256 over an ID, so independence is a reasonable design assumption, not an observation |
| Coverage by theme, relevance, ambiguity, polarity, company-notice status | no labels; theme membership is in the key |
| Unique-story status for labels | needs annotator `near_dup_of` labels; only the pipeline's `mech_dup` mark exists (224 of 1,493 items are not ORIGINAL) |

### 3.3 What can and cannot be claimed

**Selection was random by rule, stratified only through the cells of the parent sample, and not convenience-based. That is a known design fact, verified.** It does **not** by itself make the 312 representative of the evaluation question:

1. Overlap is a per-item coin flip with probability 0.2 **within each cell**, so each cell's overlap count is random: expected C1 38.6, C2 40, C3 40, C4 20, C5 40, C6 60, C7 60 (standard deviations 4 to 7). Realised counts are in the key and unknown here.
2. The estimators weight each item by N_c/n_c of the **parent** cell. Applied to the overlap subset, each cell is scaled by its realised overlap fraction, which varies around 0.2 (relative standard deviation about 14% for n_c = 200). Ratios stay approximately right but gain extra variance that the bootstrap over batches only partly captures. The usual fix is to reweight by the realised overlap count per cell; that changes a pre-registered estimator and is **yours to decide**. At evaluation time the key legitimately supplies those counts.
3. Pseudo-random selection gives representativeness *in expectation*, not for this realisation, and 312 is small where it matters (section 4).

**Representativeness of the reference subset is therefore: design-verified (random within cell), realisation-unverified, label-independence assumed.** It is not claimed.

## 4. Statistical feasibility [DERIVED from the public cell sizes; no data, no tuning]

Pre-registered cells: C1 193 items from 193 rows (a census), C2 200 of 2,848, C3 200 of 1,953, C4 100 of 1,560, C5 200 of 20,300, C6 300 of 24,492, C7 300 of 193,590. Per-item weights: 1.0, 14.2, 9.8, 15.6, 101.5, 81.6, 645.3. The proposed, **unapproved** criteria are precision at least 0.70, bootstrap lower bound at least 0.60, pooled recall at least 0.90, and a 100 non-ambiguous-member reporting floor. Nothing here changes them.

### 4.1 Members per scope

| Scope | Gold | Rates | Equity | Against the 100 floor |
| --- | --- | --- | --- | --- |
| All 1,493 items (human or AI-assisted) | about 193 (C1) | about 200 or more | about 200 or more | above the floor, if fewer than half are ambiguous |
| Independent overlap subset (about 20%) | about 39 | about 40 | about 40 | **below** (30 to 99 is "indicative" only) |

### 4.2 Metric by metric

| Metric | What it needs | Status on the independent subset | Status on all items |
| --- | --- | --- | --- |
| **Precision** and interval | at least 100 non-ambiguous members to be an estimate | **estimable but imprecise, and below the floor.** At about 40 members, even a perfect-looking 0.70 has a Wilson interval of 0.55 to 0.82; a lower bound of 0.60 needs 31 of 40 relevant (0.775). At 100 it needs 70; at 193, 130 (0.674); at 200, 134 (0.67). These unweighted Wilson numbers are **optimistic**: the batch-clustered bootstrap is wider | estimable; the interval is as above or wider |
| **Bootstrap lower bound** | the same, plus enough batches | 192 batches, about 1.6 subset items each: runs, but the bootstrap is noisy and below the floor | runs; about 7.8 items per batch |
| **Pooled recall** | R labels in C1 to C6, weighted | **estimable but fragile.** The cue-free cells carry big weights (C5 101.5, C6 81.6 per relevant item). Recall of 0.90 allows outside relevant weight of at most one ninth of the in-series weight. *If* about 80% of a series' members were relevant: gold allows 0 relevant items in C5 or C6 (and 1 in C4); rates allows about 2 in C5 and 3 in C6; equity about 1 in C5 and 2 in C6. A single unlucky item decides the criterion. These are arithmetic illustrations under an assumed precision, **not results** | the same fragility, with 5 times the items |
| **Capture recall** and its rule-of-three bound | C7 labels | **cannot meet 0.90.** With no relevant item among 300 C7 items the bound adds 193,590 x 3 / 300 = **1,936** of weight; 0.90 needs the captured relevant weight to be at least 17,423, while the whole captured weight is 26,854 (every captured item would have to be about 65% relevant by weight). On the independent subset the bound is about 9,680 | the same |
| **Unique-story precision** | `near_dup_of` labels and the duplicate mark | **estimable only after labelling.** The duplicate mark alone does not give it; 224 items are marked non-original, so it removes members and widens intervals | estimable after labelling |
| **Per-cell results** | per-cell labels | about 20 to 60 items per cell in the subset (Wilson half-width about 0.2 at 20): descriptive only | 100 to 300 per cell |
| **Label-origin stratification** | verified origin per item | meaningful only with the bridge. AI-exposed labels are **not independent** (anchoring), so that stratum cannot judge the filter. Under M2 the human-only stratum is the 312 overlap items | meaningful |

### 4.3 The four categories, applied

- **Cannot be estimated:** capture recall at the 0.90 criterion (the rule-of-three bound makes it unmeetable by arithmetic); any metric on a series with no members; unique-story precision before duplicate labels exist.
- **Estimable but imprecise:** precision, bootstrap lower bound and pooled recall on the independent subset (below the floor; reported as indicative only); pooled recall on all items (a few heavy-weight items decide it).
- **Estimable but not meeting a criterion:** cannot be stated: no labels exist, and no outcome is computed or implied.
- **Invalid evaluation:** any run with blocked provenance, a stale freeze, an unverified AI origin or an unverified suggestion store, which the code refuses before the key is read.

## 5. Methodology decision matrix

Verified facts first, then the recommendation separately. Nothing is selected.

| Criterion | M1: all human | M2: overlap human-only, rest AI-assisted | M3: changed design (hidden blind suggestions) |
| --- | --- | --- | --- |
| Independence of the reference | complete: all 1,493 human-only | the 312 overlap only (about 40 members per series) | blind subset only, and it is exposed to a hidden suggestion on the AI side, not to the human |
| AI contamination risk | none | the 1,181 AI-assisted labels are anchored; the 312 are protected by the exclusion code (verified) | highest design complexity; blind items must be sent, which the exclusion setting forbids |
| Human effort [ESTIMATED, 15 to 30 s per item, unmeasured] | about 6 to 12 h | 312 items 1.3 to 2.6 h, plus review of 1,181 (speed unmeasured) | as M2 plus the blind comparison |
| Precision and recall estimation | all 1,493 independent: the only option that meets the floor with independent labels | the decision rests on AI-exposed labels (not independent) unless the floor-limited 312 carry it, which they cannot | as M2 |
| Blind human-versus-AI comparison | no | no (no blind subset) | yes, the only option |
| Sample-size constraints | none beyond the pre-registered cells | independent evidence is below the floor | blind subset size to be set |
| Provider exposure and data handling | none | 1,181 titles and URLs sent; 45 URLs carry query strings | 1,181 plus the blind items |
| Implementation complexity | existing tools (`annotate label` covers overlap only; the batch workflow covers the rest) | bridge now built offline; label path, polarity and approvals still needed | M2 plus an unresolved conflict with the exclusion setting |
| Approvals needed | methodology; criteria; completion wording | everything in the list in section 8 | as M2 plus the blind-subset design |

**What exists:** the exclusion code (M2, tested), the bridge and provenance verification (M2 and M3, tested on synthetic data), the decision and evaluation code (all). **What is missing:** every approval; any real AI output; the unmapped-origin decision; a real run. **Recommendation (yours to accept or reject):** unchanged from the decision document. M1 is the only path that completes B2 with independent labels at the floor, with no provider and no new code. M2 is the efficiency option, but it should be accepted knowing the independent reference cannot reach the floor, so the filter decision would rest on AI-exposed labels. M3 only if human-versus-AI agreement is wanted as a result.

## 6. Raw provider-response retention assessment [VERIFIED by reading; nothing deleted, rewritten or migrated]

### 6.1 Which artifacts hold what

| Artifact | Raw responses or sensitive text | Retention policy today |
| --- | --- | --- |
| `suggestions/ai_suggestions_raw_v1.jsonl` | **the provider's response text verbatim** (`raw_response`), its hash, the parsed output, provider error details and request IDs. The request text itself is **not** stored, only the prompt hash | **none can apply**: the response text is inside the hash-chained record |
| `suggestions/ai_suggestions_raw_v1.jsonl.partial-N` | raw fragments of a crashed write | **expirable** (covered) |
| `suggestions/ai_suggestions_valid_v1.csv` | the parsed suggestion, evidence excerpts (title fragments), notes | **expirable** (derived, rebuildable) |
| `queue/review_queue_v1.csv` | derived queue | **expirable** |
| `review/reviews_v1.jsonl` | the human's labels, free-text `note` and `reason_note`, reviewer ID | protected, not expirable |
| `audit/events_v1.jsonl`, run manifests | counts, hashes, event details; no response text | protected |
| `export/` | titles, URLs and domains from the source, labels, notes | protected |
| `snapshot/`, `inputs/` | the original files (titles, URLs); item fingerprints only | protected |

The titles, URLs and domains are public news metadata, not personal data, but they are what a provider would have received.

### 6.2 Why expiry is impossible in the current layout [VERIFIED]

Each record's `record_sha256` is the hash of its whole body, **including `raw_response`**, and the next record commits to it. Deleting or editing a response changes the body, so the chain, which is the proof that nothing was altered, fails at that line. `retention.py` already documents this and excludes the file.

### 6.3 Proposed design [PROPOSED; not built]

1. **Payload files.** The chain stores only `raw_response_sha256` and a `payload_ref`; the text lives in `suggestions/payloads/<sha256>.txt`. The chain never contains the text, so removing a payload cannot break it.
2. **Expiry record.** Expiring a payload deletes the file and appends an audit event (`payload_expired`: hash, reason, time, count), so the deletion is itself in the chain.
3. **Verification that tolerates absence.** The verifier recomputes a present payload's hash and accepts a missing payload only if an expiry event covers that exact hash.
4. **Minimise what stays.** Keep the parsed output, the validation result and the hash (enough to audit what was accepted); truncate provider error detail before it is stored.
5. **New layout version only.** Existing chains are never migrated or rewritten; the change applies to a new experiment folder with a new schema tag, so old and new are not mixed.
6. **Clock and scope** stay as in `retention.py` (audit-log run end; nothing expires with no run).

**Tests needed before it could be approved** (synthetic only): the chain still verifies after a payload is removed; a payload edited in place is detected by its hash; a removed payload with no expiry event is refused; an expiry event for the wrong hash is refused; the old layout still verifies unchanged; no path outside the experiment folder is touched; the dry run is the default and deletion needs confirmation; and a resumed run after an expiry behaves correctly. **Decisions needed from you:** whether the research record must keep the raw responses at all, for how long, and the retention period (still unset).

## 7. Tests and safety verification

| Run | Result |
| --- | --- |
| GDELT suite before | 765 passed |
| New: `test_label_bridge.py` | **29 passed**: bridge loading and each rejection; legacy validator unchanged; two-source refusal; mapping, refusals and no invention; forged exports; the whole path from store to evaluation; stale freeze on a changed store; no write, no provider path |
| GDELT suite after | **794 passed, 0 failed** |
| Not run | the hosted-database backend suite, the frontend checks and the full-project suite (nothing outside the GDELT package changed) |

Changed files: new `ai_bridge.py` and `test_label_bridge.py`; edited `annotate.py` (an optional argument and a helper, default behaviour unchanged), `ai_origin.py`, `evaluate.py`, `cli.py`, `ai/store.py` (the derived CSV's bytes are now computed by a function that does not write; `write_valid_csv` is unchanged in effect), and `test_end_to_end_evaluation_wiring.py` (one test now states which basis each origin needs).

Confirmations, [VERIFIED]: no provider or network call; no data transmitted; **the sealed key was not opened** (142,900 bytes, 2026-10-13 22:28:16 +0530, unchanged); no real label or suggestion created; no freeze, approval record or export created; no acquisition; the original, backup, working copy, `annotation_B.csv` and selection log hashes are unchanged and **no file under `datasets/` is newer than the U7 baseline marker** (0 of 568); `NETWORK` and `DEV_SAMPLE` unchanged (`True`, `True`; confirmation sample `False`); build lock `False`; adapter registry empty; `HEAD` still `71b363f`; no commit or push. The evaluation fingerprint on the real folder is now `48ceaaba5b64325da5adf7be84240211fad0d544e90af50f039130ac425bf2fb` (it changed because the evaluation code set changed; no freeze exists, so nothing was invalidated).

## 8. Outstanding decisions and blockers

**Decisions still yours [PENDING]:**

1. Methodology M1, M2 or M3, and the `provider_exclusion` value; whether blind items may ever be sent.
2. Whether the independent subset may be reweighted by its realised cell counts (section 3.3), and whether it is accepted as representative.
3. The review origins `human_uncertain` and `human_insufficient_evidence`: which `label_basis` they map to.
4. Freezing the criteria, which recall gates, and whether the 0.90 capture-recall target stays (it cannot be met).
5. The bootstrap generator; the completion wording; the B8 amendment; the polarity option.
6. Provider, model, terms, data handling, temperature, limits, spending cap; raw-response retention and the payload-file design.
7. Locking the GDELT switches; the code path that writes bridged labels in practice; gate A to D records; the build-lock change and an adapter; explicit execution authorization; and, separately, full-window acquisition.

**Blockers:** none are new in code. AI-assisted labels still cannot be *created* (no provider, no approval); the bridge handles them once a properly approved run exists. Remaining implementation gaps: `annotate label` still covers only the 312 overlap items; raw responses are not expirable; the blind-comparison floor flags are partial.

## 9. Final execution-gate status [VERIFIED]

| Gate | State |
| --- | --- |
| Build lock `AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD` | `False` |
| Provider adapter registry | empty |
| Gates A to D | no approval record |
| `provider_exclusion`, `polarity_option`, temperature, provider, limits | unset in any real configuration |
| `--confirm-ai-run` | not run; the non-writing dry run still lists 15 unmet prerequisites (14 plus the unset flag) |
| Freeze; evaluation results | none |
| Acceptance criteria | `PROPOSED_NOT_APPROVED` |
| Full-window acquisition | not authorized |

**B2 remains incomplete.** It needs an approved methodology, a valid evaluation on adequate evidence, and separately authorized full-window ingestion. None of these exists.
