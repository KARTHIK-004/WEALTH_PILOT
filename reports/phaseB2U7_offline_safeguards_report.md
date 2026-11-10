# Phase B2-U7: offline annotation safeguards and evaluation integrity

Date: 2026-10-19. Status: **offline safeguards implemented and tested. This is not B2 completion.** AI execution is still blocked. Nothing was run against a model, no data was sent, no label or suggestion was created, no freeze was made, and nothing was committed.

Written for: you, the project owner. Every methodology, metric, provider, data-handling and execution decision is still pending; none was approved here.

**Labels:** [VERIFIED] checked in code or by a test; [IMPLEMENTED] code exists and is tested; [PENDING] a decision that stays yours.

---

## 1. U6 findings verified against the code

The authoritative U6 record is the addendum in `reports/phaseB2_completion_decision_document.md` (sections 11 to 16). Each finding was re-checked in the source before changing anything.

| U6 finding | Verified | Action |
| --- | --- | --- |
| The AI pipeline queued every sendable item, so overlap items could be sent | **Confirmed** (`runner.run_suggestions`) | fixed (A) |
| The freeze and evaluation did not verify provenance or stratify by label origin | **Confirmed** | fixed (B, E) |
| The 100-member floor was reported but not part of the pass or fail check | **Confirmed** (`proposed_thresholds`) | fixed (C) |
| The bootstrap uses `random.Random(42)`, not numpy `default_rng(42)` | **Confirmed** (`estimators.cluster_bootstrap`) | recorded and pinned (D); generator **not** changed |
| No per-cell Wilson, no unique-story precision, no `NEAR_DUP` count | **Confirmed** | added (E) |
| A freeze stored a code fingerprint but evaluation never compared it | **Confirmed** (`evaluate.py` checked only the working-copy hash) | fixed (F) |

---

## 2. What was implemented

### A. Explicit, fail-closed provider exclusion [IMPLEMENTED]

- **New config key `protocol.provider_exclusion`** with three values: `overlap_and_blind` (every original overlap item, and so every blind item), `blind_only`, or `none` (an explicit "nothing excluded"). **Unset blocks execution**, so a setting must be chosen deliberately. Unknown values are refused. **No value is approved or recorded anywhere; the config template keeps it `null`.**
- **Membership comes only from verified provenance** (`store.verified_overlap`, `store.source_overlap_ids`): the recorded overlap manifest, the snapshot's `overlap_subset` column and `annotation_B.csv` must agree exactly, and `annotation_B.csv` must match its recorded SHA-256. A missing, malformed, inconsistent or unverifiable manifest raises an error before any request. Nothing is inferred from item IDs or order (tested with overlap items at the end of the list).
- **Excluded items cannot reach the provider by any path:** the pending list drops them (so resume and repeated runs cannot reach them); the request loop refuses one (so no retry or re-ask can); a wrapper around the provider refuses any request for one; a store that already holds a suggestion for an excluded item refuses the whole run as contaminated; the review layer refuses an AI-seen action or a stray suggestion for one; the queue and progress report show it as "excluded from provider" and never expect a suggestion.
- **Approval hashes:** the mode is inside the **Gate A** binding, and the hash of the exact excluded set is inside the **Gate D** binding. Unverified membership produces a binding that can never match an approval. Changing the mode after approval invalidates exactly Gates A and D (tested). No approval record exists, so none was invalidated, and none was fabricated.
- The dry run reports the exclusion mode, the number excluded, and token estimates for only the items that would be sent. It still writes nothing.

**A conflict I did not resolve.** You asked that the control also exclude blind-evaluation items. The B2-T "hybrid" design (M3) needs blind items to be *sent* so that hidden suggestions exist for a human-versus-AI comparison. Both cannot hold. I made the choice explicit: under `overlap_and_blind` and `blind_only` blind items are always excluded, so M3 is impossible; M3 is possible only under `none`, which sends every overlap item, and you must approve that. Which behaviour you want is [PENDING].

### B. Provenance bridge [IMPLEMENTED: new `provenance.py`]

`provenance.verify` ties together the original `annotation_A.csv`, the `annotation_B.csv` overlap manifest, the build backup, the human working copy and `merge_log.jsonl`. It returns `VERIFIED` or **`BLOCKED`** with every problem listed, and invents nothing. It blocks on:

- a missing artifact; a hash that differs from `selection_log.json`; a backup that differs from the original;
- a missing, duplicate or unknown item; a malformed item ID; changed original source fields;
- an overlap manifest that is not exactly the original overlap items;
- a working copy whose hash differs from the last logged write (an edit outside the logged workflow), or a changed copy with no history at all; an unreadable merge log;
- an unrecognised label basis; an **AI-based label on an overlap item** (a conflict, not a stratum); an invalid duplicate reference.

Each item gets an origin: `human_only` (`own`), `ai_exposed` (`accepted_ai`, `corrected_ai`, `rejected_ai`) or `unlabelled`, plus a count of logged corrections. Only an overlap item with a `human_only` label is an *independent candidate*; an AI-exposed label is never one. `merge_ai_origin` checks future `b2t_annotation_v1` metadata against these records and blocks any disagreement (exposure versus origin, an AI-exposed overlap item, duplicates, unknown items).

**Real data** [VERIFIED, read-only; the key was not touched]: provenance on the real review folder is `VERIFIED`: 1,493 items, 312 overlap, all unlabelled, no corrections, no duplicate references.

### C. Four-way threshold decision [IMPLEMENTED: new `decision.py`]

`decide_series` returns `PASS`, `FAIL`, `INSUFFICIENT_EVIDENCE` or `INVALID_EVALUATION`.

- A criterion is `met`, `not_met` or `undetermined`. Any `not_met` gives `FAIL`; otherwise any `undetermined` gives `INSUFFICIENT_EVIDENCE`; otherwise `PASS`. A missing metric is never a pass.
- **The floor of 100 non-ambiguous members** applies to precision and its lower bound (99 is insufficient, 100 is enough). Pooled recall needs no floor, so a determinable recall failure is a `FAIL` even when precision cannot be judged.
- Exact boundaries: equal passes, the next value below fails (tested at 0.70, 0.60 and 0.90).
- `INVALID_EVALUATION` is returned for failed integrity or provenance, or any non-finite, out-of-range or wrongly typed value. It is never a pass or a fail.
- **Pooled recall is the gate metric. Capture recall and its rule-of-three bound are passed through under their own key and never decide** (tested: a capture recall of 0.01 does not change a `PASS`).
- **The thresholds stay PROPOSED.** `CRITERIA_STATUS = "PROPOSED_NOT_APPROVED"` and `CRITERIA_APPROVAL_REFERENCE = None`. Every decision carries `authoritative: false` and the statement "computed against PROPOSED, unapproved criteria: not an acceptance decision". A decision becomes authoritative only when the status is `APPROVED` **and** a reference is recorded; a status or a reference alone is not enough (tested). There is no mechanism that sets either from data, so approving the criteria needs your explicit act and a code change, which the fingerprint (F) then makes visible.

### D. Bootstrap reproducibility [IMPLEMENTED: documented and pinned]

Verified: `random.Random(42)`, 2,000 resamples, resampling whole batches. Recorded as constants (`BOOTSTRAP_GENERATOR`, `BOOTSTRAP_SEED`, `BOOTSTRAP_RESAMPLES`) and in the evaluation output with a note that **B2-I names numpy `default_rng(42)` and a matching seed does not give the same resamples across generators**. **The generator was not changed.** Tests pin the current method: determinism for a seed, a different sequence for another seed, whole-batch resampling, an independent stdlib reimplementation that matches value for value, and a golden interval (a pin from running the current code once, not an independent validation). Switching generators is a methodology decision [PENDING] and changes the evaluation fingerprint.

### E. Report completeness [IMPLEMENTED]

The evaluation output now adds, per series: unique-story precision (or "unavailable" if duplicate information is missing, never assumed `ORIGINAL`), an unweighted Wilson interval per sampling cell (`None`, not zero, for an empty cell), precision by label origin (a separate `ai_exposed` stratum, `None` when absent), and the four-way decision with capture recall beside it. At top level: the annotator `NEAR_DUP` count (`None` if unknown), label-origin counts, the provenance summary, the criteria status and the evaluation fingerprint.

### F. Freeze and fingerprint ordering [IMPLEMENTED]

A freeze now stores an **evaluation fingerprint**: hashes of the evaluation code (`estimators.py`, `evaluate.py`, `decision.py`, `provenance.py`, `annotate.py`, `review.py`), the protocol constants (criteria, status, approval reference, thresholds, bootstrap generator, seed and resamples, rule-of-three), and the inputs (original and overlap manifest, selection log, backup). A freeze is **refused if provenance is blocked**. Evaluation refuses a stale freeze (naming which part changed) or a freeze with no fingerprint, and does so **before** provenance, and before the key is touched. Tests use a spy that fails if the key is read. **No freeze was created.** Because a freeze is never overwritten, a stale freeze cannot be repaired automatically; the owner would have to remove it deliberately.

---

## 3. Files

Changed, under `backend/wealthpilot/data/gdelt/`:

- `ai/config.py`: the `provider_exclusion` key, `excluded_item_ids`, and the Gate A and Gate D bindings.
- `ai/store.py`: `verified_overlap`, `source_overlap_ids`.
- `ai/runner.py`: exclusion in the dry run and the run, the contamination check, the provider guard.
- `ai/queue.py`, `ai/reviewer.py`, `cli.py`: exclusion in the queue, progress, review and the run gate.
- `estimators.py`: bootstrap constants, `unique_story_precision`, `cell_wilson`, `near_dup_count`, two optional fields on `Scored`.
- `evaluate.py`: the fingerprint, the provenance gate, the new report sections.

New: `decision.py`, `provenance.py`, `tests/backend/data/gdelt/test_ai_overlap_exclusion.py`, `test_evaluation_integrity.py`, and this report.

Test infrastructure changed (no assertion weakened): `conftest.py` (the synthetic config sets `provider_exclusion: none` explicitly and passes the overlap set to the gate helpers); `test_estimators_evaluate.py` (the synthetic folder now has an `annotation_B.csv`, fixture writes are logged as the real workflow does, one test now damages the key before the freeze because the selection log is now a fingerprinted input, and 10 tests were added).

Updated: `docs/MEMORY.md` (one short entry). **Not changed:** the original annotation files, the sealed key, the rubric, the validator, the development sample, any earlier report.

---

## 4. Tests

All offline; sockets and the database are blocked.

| File | Tests |
| --- | ---: |
| `test_ai_overlap_exclusion.py` (new) | 38 |
| `test_evaluation_integrity.py` (new) | 65 |
| `test_estimators_evaluate.py` (10 added) | 30 |
| rest of `tests/backend/data/gdelt/` | 557 |

- `pytest tests/backend/data/gdelt -q -p no:cacheprovider`: **690 passed, 0 failed** (577 before, plus 113 new). `compileall -W error` clean; unused-import scan 0.
- Coverage of the requested cases: overlap and blind exclusion; direct queue construction, resume, retries and re-asks; a missing, corrupt, tampered or inconsistent membership manifest (8 forms); label provenance, origin stratification and correction history; duplicate-reference integrity; the four outcomes, exact boundaries and the floor at 99, 100 and 101; invalid and conflicting values; bootstrap reproducibility; a stale freeze after a protocol, seed, implementation, membership or fingerprint-less change; AI execution still blocked; the key never read and no provider called.
- **Not run:** the hosted-database backend suite, the frontend checks and the full project suite. I do not claim them.

---

## 5. Current state and gates

| Item | Value |
| --- | --- |
| Items / overlap / non-overlap; labelled; suggestions | 1,493 / 312 / 1,181; 0; 0 |
| Freeze, evaluation, AI or `b2t` files under `datasets/` | none |
| Original files | `annotation_A.csv`, backup and working copy `11db13e668bd3da8…`; `annotation_B.csv` `211729002893c1e4…`; `selection_log.json` `15fa2302…`; **unchanged** |
| All files under `datasets/` (568; size, time, SHA-256; key by size and time) | digest `ce25a93a86eb06…`, **identical to the baseline taken before the work** |
| Sealed key | 142,900 bytes, modified 2026-10-13 22:28 +0530; **not opened** |
| Build lock; adapter registry | `False`; `{}` |
| `NETWORK` / `DEV_SAMPLE` / `CONFIRMATION_SAMPLE` switches | `True` / `True` / `False`; unchanged |
| AI approval records (gates A to D) | none exist; none fabricated |
| `ai run --confirm-ai-run` on the real item file (a placeholder config in the scratchpad) | **exit 3, `BLOCKED`, 14 unmet prerequisites** |
| Non-writing `ai dry-run` with `overlap_and_blind` | 1,493 items, **1,181 would be sent, 312 excluded**; `provider_called`, `data_sent` and `files_written` all `false`; the datasets digest unchanged |
| Pip freeze fingerprint | `3393be502c93f2299cc40bc2ac786caf`, unchanged |
| Git | the same single commit; the GDELT tool and tests are untracked; no commit |

**Execution is still blocked** by the build lock, the empty adapter registry, the missing gates, and the unset exclusion mode, temperature and polarity option, among others.

---

## 6. Remaining gaps and pending decisions

**Implementation gaps (not closed here):**

1. **The AI dataset is not yet consumed by the freeze and evaluation.** `merge_ai_origin` exists but nothing calls it, because no AI-assisted labels exist and the bridge format depends on the methodology. M2 still needs the bridge that carries AI-assisted labels and their provenance into the working-copy format.
2. **No independent-only decision.** Stratified precision is reported, but the bootstrap lower bound and recall are not computed per stratum, so no decision on independent labels alone exists.
3. **No mechanism to approve the criteria** (deliberate: it is an explicit owner act).
4. **`annotate label` still covers only the 312 overlap items**; the other 1,181 use the batch export and merge workflow.
5. Raw provider responses are still not expirable (B2-U5); the blind-comparison floor flags are still only on part of the comparison output (M3 only).

**Decisions still yours** (see the U6 addendum, sections 12 and 15): the methodology (M1, M2 or M3), including what `provider_exclusion` should be and whether blind items may ever be sent; freezing the acceptance criteria and which recall gates; the bootstrap generator; the completion wording; the B8 amendment; the polarity option; provider, model, data handling, temperature, limits and spending cap; the retention policy; locking the GDELT switches; the code that bridges AI-assisted labels; the gate records; the build-lock change; explicit execution authorization; and, separately, full-window acquisition.

## 7. Confirmations [each VERIFIED above]

No model or provider was called and no adapter was registered. No project data was transmitted and no network request or acquisition occurred. The sealed key was not opened and no credential was read. No label, AI suggestion, freeze or approval record was created. No original annotation file, backup, overlap list or development-sample file changed. No commit was made.
