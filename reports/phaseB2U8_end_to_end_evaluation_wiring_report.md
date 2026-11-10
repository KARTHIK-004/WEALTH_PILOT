# Phase B2-U8: end-to-end evaluation wiring and M2 protocol readiness

Date: 2026-10-19. Status: **offline wiring implemented and tested. This is not B2 completion.** AI execution is still blocked. No model or provider was called, no data was sent, no label or suggestion was created, no freeze or approval record was made, and nothing was committed.

Written for: you, the project owner. M2 is implemented only as a **proposed** configuration that the code can describe and enforce; it was not approved or chosen. Every methodology, metric, provider, data-handling and execution decision is still pending.

**Labels:** [VERIFIED] checked in code, by a test or by a read-only run; [IMPLEMENTED] code exists and is tested; [BLOCKED] cannot be done without evidence or a decision that does not exist; [PENDING] a decision that stays yours.

---

## 1. Current state verified before any change

| Check | Result |
| --- | --- |
| B2-U7 report and MEMORY entry present | [VERIFIED] |
| GDELT suite at the start | [VERIFIED] **690 passed**, as the U7 report states |
| Overlap membership (real review folder, read-only) | [VERIFIED] 1,493 items; **312** overlap; **1,181** non-overlap; the manifest, the original's `overlap_subset` column and `annotation_B.csv` agree. The counts were not forced: they are what the files say |
| Blind subset | [VERIFIED] **no blind subset is designated anywhere.** No real experiment config exists (only a scratch probe outside the repo). The M2 text "any designated blind items stay excluded" is enforced, but there are none to exclude |
| Provenance bridge (real folder) | [VERIFIED] `VERIFIED`; every item `unlabelled`; 0 independent candidates |
| Freeze record / evaluation results | [VERIFIED] neither exists |
| Build lock; adapter registry | [VERIFIED] `False`; `{}` |
| Execution prerequisites | [VERIFIED] via the non-writing `ai dry-run` on the scratch probe config (which sets `overlap_and_blind`): **14 unmet** plus "`--confirm-ai-run` not given" (15 listed because the dry run never passes it). They are: build lock, provider/model, temperature, polarity, credentials variable, two limits, data-terms review, retention, run ID, and gates A to D with no approval record |
| Approval and execution records | [VERIFIED] none exist; no `provider_exclusion` approval, no run manifest, no suggestion store |
| Sealed key | [VERIFIED] 142,900 bytes, modified 2026-10-13 22:28:16 +0530, same as before U7; **not opened** (a metadata read only) |

`ai run` and `--confirm-ai-run` were **not** run. The dry run is read-only: it reports `provider_called: false`, `data_sent: false`, `files_written: false`.

## 2. What was implemented

### 2.1 AI-origin evidence wired into freeze and evaluation [IMPLEMENTED: new `ai_origin.py`]

`merge_ai_origin` (U7) had no caller. It now does, through one function that freeze and evaluation both use:

```
ai_origin.verified(paths, export_dir)  =  provenance.verify(paths)  +  ai_origin.attach(report, export_dir)
```

The data flow:

1. `provenance.verify` checks the original, overlap manifest, backup, working copy and merge history (U7), and gives each item an origin: `human_only`, `ai_exposed` or `unlabelled`.
2. If any label is `ai_exposed`, an AI-origin export (`b2t_annotation_v1`) is **required**. With none supplied the bridge is `BLOCKED` (`ai_origin_missing`). If an export is supplied it is verified even when no label needs it.
3. The export is verified as a file: both files are regular files, the manifest schema is `b2t_annotation_v1`, the CSV hash equals the manifest's, the columns are exactly the export columns, and the row count matches.
4. Each row is verified against the bridge: the item exists once; its source fields equal the original; its overlap membership equals the verified membership; its label content and duplicate reference equal the working copy; `label_origin` is a recognised review origin and agrees with `ai_exposure`; the reviewer is a named human with a UTC time and a well-formed review-record hash; an AI-seen label cites a suggestion and an unexposed one does not; an overlap item never cites one and is never AI-exposed.
5. Coverage: **every non-overlap item needs a review record** in the export. Overlap items may be absent. A manifest whose overlap count differs from the verified membership is refused.
6. Nothing is repaired, inferred or defaulted. A label that is empty in the working copy is never filled from the export (it is a `label_mismatch`), and a missing label is never read as negative or neutral (`annotate.validate` still refuses an incomplete set).

`freeze(paths, ai_origin_dir)` refuses on any problem, before it writes anything. `evaluate(paths, ai_origin_dir=...)` re-checks the freeze, label completeness, the **fingerprint** and the provenance, **all before the key is read**. The export's two file hashes and whether an export was supplied are part of the evaluation fingerprint, so changing, adding or dropping the export after the freeze makes the freeze stale. The CLI takes the export from `annotate freeze|evaluate --ai-experiment <experiment.yaml>` (it reads only the experiment file's destination).

### 2.2 Scopes: exploratory versus independent reference [IMPLEMENTED]

Each series now carries two scopes.

| Scope | Items | What it is |
| --- | --- | --- |
| `exploratory_all_labelled` | every labelled item, any origin | Descriptive only. May include AI-exposed labels, which are not independent. **No decision is taken on it** (the `decision` key moved out of this scope) |
| `human_only_reference` | items whose origin is `human_only` | The only scope that gets a decision |

`evaluation_mode` for the reference scope is `INDEPENDENT_REFERENCE` only if provenance verified **and** there are at least 100 non-ambiguous human-only series members. Otherwise it is `BLOCKED`, with the reason (no human-only labels, below the reporting floor, or provenance did not verify). The decision is still computed, so a blocked scope reads `INSUFFICIENT_EVIDENCE` or `INVALID_EVALUATION`, never a pass.

AI-exposed labels are excluded from the reference scope even when they would lift the numbers. A test shows 20 AI-exposed members moving a series from 110 non-ambiguous members (exploratory) to 90 (reference), which drops it below the floor.

The four outcomes are unchanged (`PASS`, `FAIL`, `INSUFFICIENT_EVIDENCE`, `INVALID_EVALUATION`). Pooled recall and capture recall are reported separately in both scopes; capture recall never appears among the criteria. Every decision carries `authoritative: false`, `criteria_status: PROPOSED_NOT_APPROVED` and the new `authorizes_execution_or_deployment: false`. The result lists `approvals_unresolved` (criteria, methodology, bootstrap generator, recall interpretation and completion wording).

Nothing can approve the criteria from outside: the status is a constant, the decision, evaluation and AI-origin modules read no environment variable or config file, and a test confirms no command-line option mentions approval, criteria or authority. Approval remains a deliberate code change by you.

**A methodology assumption stays open and is stated in every result:** estimates on the reference subset reuse the original cell weights. That the overlap subset is representative within each cell is not approved. On the real data this is expected to leave each series below the 100-member floor on the independent subset alone (about 40 to 42 members), so the reference scope would be `BLOCKED`.

### 2.3 The M2 partition [IMPLEMENTED as a description and a check]

`protocol_partition` separates the three groups from verified membership only:

| Group | Source |
| --- | --- |
| human-only reference | the 312 verified original overlap items |
| blind | `protocol.blind_item_ids`, which must all be overlap items and dataset items |
| AI-eligible | all items minus the excluded set |

It reports `matches_proposed_m2` (true only for `overlap_and_blind`), `approved: false`, the counts and a hash of the eligible set, and lists every inconsistency (mode unset, membership unverified, blind IDs not in the dataset or not overlap items, an overlap or blind item left eligible). The dry run prints it; `run_suggestions` refuses on any problem. On the real data with the scratch probe: **312 reference, 0 blind, 1,181 eligible**, eligible-set hash `97f33744…`.

Nothing was chosen. The mode is still unset in any real config and blocks execution; `none` is never a default and no code path turns it on. M3 is not implemented or enabled.

The exclusion and approval binding were already in place from U7 and were re-verified: the mode is in Gate A and the exact excluded set is in Gate D, so a change to the protocol or to membership invalidates a stale approval (U7 tests). The eligible set is determined by the item set (already in Gate D) minus the excluded set (already in Gate D), so no new binding was needed. One test now runs an M2 configuration through submission, resume, queue reconstruction, review and store validation: only the 5 eligible items of the synthetic set are ever sent, a resume sends nothing, excluded items are queued as `excluded_from_provider`, an AI-seen review of an excluded item is refused, and a store holding a stray record for an excluded item stops the next run.

### 2.4 Polarity [IMPLEMENTED: tests only, nothing decided]

`protocol.polarity_option` is unchanged: unset blocks execution, the only implemented value is `P1_required_as_in_existing_rubric`, and it is hashed into Gate A. New tests show a missing option is a blocker and is never defaulted; empty, whitespace, wrong-case, padded, unknown, numeric, boolean, list and mapping values are all rejected, not coerced; recording the one implemented option creates no approval; and the existing rule (a relevant theme needs a polarity) still refuses a label without one. The rubric and historical labels were not changed.

## 3. Evaluation data flow

```
annotation_A.csv  ─┐
annotation_B.csv   ├─►  provenance.verify  ──►  ai_origin.attach(export)  ──►  VERIFIED / BLOCKED
backup, working,   │        (origin per item)       (files, rows, coverage)
merge_log.jsonl   ─┘                                        │
                                                            ▼
              annotate freeze [--ai-experiment]  ── refuses on BLOCKED, incomplete labels, or no verified export
                     │  records the evaluation fingerprint (code + protocol + inputs incl. export hashes)
                     ▼
              annotate evaluate [--ai-experiment]
                     1. freeze present, working copy unchanged
                     2. labels still complete and valid
                     3. fingerprint equals the frozen one          (else: stale freeze)
                     4. provenance + AI origin verified            (else: BLOCKED)
                     ───────────────  the sealed key is opened only after all four  ───────────────
                     5. aggregates: exploratory scope, and a decision on the human_only reference scope (non-authoritative)
```

## 4. Files

New: `backend/wealthpilot/data/gdelt/ai_origin.py`; `tests/backend/data/gdelt/test_end_to_end_evaluation_wiring.py`; this report.

Changed:

- `evaluate.py`: the two-scope results, the export argument, the fingerprint inputs and code list (`ai_origin.py` added), the docstring.
- `decision.py`: `PENDING_APPROVALS` and `authorizes_execution_or_deployment`.
- `provenance.py`: each item now carries its label content and source fields, so the export can be checked against them.
- `ai/config.py`: `protocol_partition`.
- `ai/runner.py`: the partition in the dry run and a refusal on any inconsistency.
- `cli.py`: `--ai-experiment` for `annotate freeze` and `annotate evaluate`.
- `tests/backend/data/gdelt/conftest.py`: the `write_export` fixture (a synthetic export builder).
- `tests/backend/data/gdelt/test_estimators_evaluate.py`: two tests now build a verified export, and one reads the decision from the reference scope.
- `docs/MEMORY.md`: one entry.

Not touched: the rubric, `annotate.py`, `review.py`, the data under `datasets/`, the switches, and every historical report.

## 5. Tests

| Run | Result |
| --- | --- |
| GDELT suite before | 690 passed |
| New wiring tests (75): AI-origin file, row, coverage, conflict and fabrication cases; freeze and evaluate refusal before the key; fingerprint and stale-freeze cases for the export; scope and floor behaviour; PASS, FAIL and blocked reference scopes; no outcome authorizes anything; no input approves the criteria; no provider path; partition and every-path exclusion; polarity | 75 passed |
| GDELT suite after | **765 passed, 0 failed** (47 s) |

A mutation check: removing the per-row export checks made 10 of the new tests fail, so they do test that code. The mutation was reverted and the suite re-run.

**Not run:** the hosted-database backend suite, the frontend checks and the full-project suite. This task touched only the GDELT package and its tests. No live provider, network or sealed-key test exists or was run.

## 6. Protocol and approval state [VERIFIED]

| Item | State |
| --- | --- |
| Methodology M1 / M2 / M3 | **pending**; M2 described and enforceable, not approved |
| `provider_exclusion` in a real config | unset; blocks execution |
| Acceptance criteria | `PROPOSED_NOT_APPROVED`, reference `None` |
| Bootstrap generator | `random.Random(42)`, 2,000 resamples, unchanged; B2-I's numpy `default_rng(42)` discrepancy still documented, not decided |
| Polarity option | unset in any real config; blocks execution |
| Gates A to D | no approval record exists |
| Build lock; adapters | `False`; none |
| `NETWORK_ENABLED_IN_THIS_BUILD` / `DEV_SAMPLE_ENABLED_IN_THIS_BUILD` / `CONFIRMATION_SAMPLE_ENABLED_IN_THIS_BUILD` | `True` / `True` / `False`; unchanged (the file was not edited) |

## 7. Fingerprints

| What | Value |
| --- | --- |
| Evaluation fingerprint, real folder, no export | `30ff7a6591cc8e7ed57cb202f0738f0339320160c7a4f3b626c8226a71de8115`. It changed from U7's `0a1728c6…` because the evaluation code and its code list changed; **no freeze exists, so nothing was invalidated** |
| Code hashes (first 12) | estimators `29d52a0aa802`, evaluate `ad5e3c8007f4`, decision `2f357f762ce7`, provenance `9b0ae440e1fb`, ai_origin `212623ea0ffd`, annotate `0064c1999990`, review `835a40783d68` |
| Inputs (first 12) | `annotation_A.csv` and backup `11db13e668bd`; `annotation_B.csv` `211729002893`; `selection_log.json` `15fa23029c02`; no export |
| Itemset (scratch probe) | `f88185acaa32068757fa778e8f655b1c9aa081931dd78ca02d9ca79a8cdacb10` |
| AI-eligible set (M2 probe) | `97f33744776fb73c0dc50093251f132b82fd6e4682f9643127fb4c04956c87ec` |
| Bindings the probe would ask gates A to D to approve | A `3709072b…`, B `6a12ebcc…`, C `f713f72a…`, D `89b92101…`. These are for a scratch config that sets no provider, so **they are not for approval** |

## 8. No external calls, no data changes [VERIFIED]

No provider or model was called and no adapter was registered or implemented. `ai run` and `--confirm-ai-run` were not run. No project data was transmitted and no network request or acquisition occurred. The sealed key was not opened and no `.env` or credential was read. No label, suggestion, freeze or approval record was created, and no export exists. The original `annotation_A.csv`, backup, working copy, `annotation_B.csv` and `selection_log.json` hashes are unchanged (section 4 of the U7 report lists them); the key's size and time are unchanged; **no file under `datasets/` is newer than the baseline taken at the start of the U7 session** (0 of 568). The locked development sample was not touched. Git `HEAD` is still `71b363f`; nothing was committed or pushed.

The earlier U7 "datasets digest" could not be reproduced byte for byte (its recipe was not saved), so the unchanged-data claim above rests on the original-file hashes, the key metadata and the modification-time check, not on a digest comparison.

## 9. What is blocked, separately from what is undecided

### 9.1 Blocked: missing record format or linkage [BLOCKED]

1. **There is no defined path that carries B2-T review labels into the working copy.** The existing validator (`annotate.validate`) accepts an AI-based `label_basis` only if a legacy `ai_suggestions_A.csv` in the review folder holds a matching valid suggestion. The B2-T pipeline keeps its suggestions in its own versioned store, not in that file. So an M2 label made through `ai review` cannot reach the working copy and pass validation today, and **a freeze of AI-assisted labels cannot succeed end to end**. I did not invent a conversion, did not relax the validator and did not create the legacy file. Exactly what is missing: an approved record format and a reviewed code path that writes the reviewed B2-T labels into `annotation_A.working.csv` with a logged write and a `label_basis`, or an approved change to the validator's suggestion source. The tests exercise the verification with both files supplied, which proves the checks but not a real flow.
2. **No blind-comparison record exists** in this wiring. The export does not carry hidden suggestions for blind items, and blind items are excluded under M2, so M3's human-versus-AI comparison cannot use this path.

### 9.2 Implementation gaps that do not need a decision [open]

1. `annotate label` still covers only the 312 overlap items; the other 1,181 use the batch export and merge workflow.
2. Raw provider responses are still not expirable (B2-U5).
3. Blind-comparison floor flags are still only on part of the comparison output.
4. The reference scope on the independent overlap subset alone will fall below the 100-member floor on the real data; this is a property of the sample, not a code gap.

### 9.3 Decisions still yours [PENDING]

The methodology (M1, M2 or M3), including the `provider_exclusion` value and whether blind items may ever be sent (this conflicts with M3, which needs them sent); whether the reference scope is representative within cells; freezing the acceptance criteria and which recall gates; the bootstrap generator; the completion wording; the B8 amendment; the polarity option; provider, model, terms, data handling, temperature, limits and spending cap; raw-response retention; locking the GDELT switches; authorizing the label bridge in 9.1; gate A to D records; the build-lock change and an adapter; explicit execution authorization; and, separately, full-window acquisition.

**B2 remains incomplete.** It needs an approved methodology, a valid evaluation on adequate evidence, and separately authorized full-window ingestion. None of these exists.
