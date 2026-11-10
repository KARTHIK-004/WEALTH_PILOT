# Phase B2-U5: AI-assisted annotation workflow repairs (offline)

Date: 2026-10-19. Status: **repairs implemented and tested offline. Execution is still disabled and blocked. Nothing was run.**

Written for: you, the project owner. This is an implementation and verification report, not an approval of any AI run.

**Labels:** [VERIFIED] confirmed by a check; [MEASURED] observed in data; [IMPLEMENTED] code exists and is tested; [PROPOSED] needs your decision; [UNVERIFIED] not confirmed.

---

## 1. Baseline and post-change state

Recorded before the first edit and compared after the last [VERIFIED].

| Item | Before | After |
| --- | --- | --- |
| Items / overlap / non-overlap | 1,493 / 312 / 1,181 | same |
| Labelled; AI suggestions | 0; 0 | 0; 0 |
| `annotation_A.csv`, backup, working copy | `11db13e668bd3da8…` (all three) | same |
| `annotation_B.csv` (overlap fingerprint) | `211729002893c1e4ce5ae3787112ca4dbe119607a928a2621d36247fe2d3874e` | same |
| `selection_log.json`; `ANNOTATION_INSTRUCTIONS.md` | `15fa2302…`; `e9d73df6…` | same |
| Sealed key | 142,900 bytes, modified 2026-10-13 22:28 +0530; not opened | same (size and time only) |
| All files under `datasets/` (568; size, time, SHA-256; key by size and time) | digest `eee92e352e0bcbbea4da6347611875f74fbcdd42b0753dd8b77f49489a9d738b` | **identical** |
| Prompt hash; rubric hash; item-set hash | `e5711d49…`; `d513a76b…`; `f88185ac…` | **unchanged** |
| Build lock; adapter registry | `False`; `{}` | `False`; `{}` |
| GDELT `NETWORK` / `DEV_SAMPLE` switches | `True` / `True` | unchanged |
| Pip freeze fingerprint | `3393be502c93f2299cc40bc2ac786caf` | unchanged |
| Git status | 83 entries, one commit `71b363f`; the GDELT tool and its tests are untracked | 84 entries (the 83, plus this report), same commit; no commit made |
| GDELT tests | 430 passed | **577 passed** |

---

## 2. Defects, root causes, fixes and tests

### 2.1 The dropped duplicate answer (`near_dup_of`) [IMPLEMENTED]

- **Path traced.** The model is not asked for `near_dup_of` (one request sees one item). The reviewer's prompt "Same story as item" came from the shared labeller. `AiReviewer._enter` returned only the content fields and `note`, and `record_review` wrote `"near_dup_of": ""` unconditionally. The export copied that empty value.
- **Root cause.** The recording function had no input for the field, so the answer had nowhere to go.
- **Fix** (`ai/reviewer.py`, `ai/export.py`):
  - `record_review` accepts `labels["near_dup_of"]` for every action. For `accept`, only `near_dup_of` and `note` may accompany it; content labels are still refused ("takes no labels").
  - **No duplicate = the empty string**, the same as the human dataset. Whitespace is trimmed.
  - A value must look like an item ID (`D` and four digits). Malformed or non-text values are refused. An unknown ID, or the item itself, is refused by the shared rubric validator (`annotate.content_errors`), using the item set of this experiment's snapshot as the universe. Nothing is written on any refusal.
  - Changing a recorded duplicate is a correction: it needs a reason and supersedes the earlier record.
  - Interactive review: a new `d` choice ("accept, and same story as another item"); the edit, reject, blind and no-suggestion paths now keep the answer to "Same story as item".
  - Export re-checks every reference and refuses to write a dataset containing an invalid one. The export manifest counts the references.
- **Not changed:** the original human-only dataset, its columns, its labeller and its validator [VERIFIED by the unchanged hashes and the existing 30 validator tests].
- **Tests** (`test_ai_repairs_duplicates_temperature.py`): valid reference stored for accept, edit, reject, uncertain, blind and no-suggestion; empty and whitespace forms; 8 malformed forms; non-text; unknown; self; accept with content labels still refused; correction supersedes; reaches the export and its count; export refuses an invalid reference injected into the records; four interactive paths.

### 2.2 A blind label cited a suggestion it never saw [IMPLEMENTED]

- **Found by** the new evaluation checks, not in your list. `record_review` stored `suggestion_ref` for a blind label whenever a hidden suggestion existed. B2-T defines the field as the exact suggestion *shown*, so a blind row looked as if it had seen one.
- **Fix:** `suggestion_ref` is stored only for the AI-seen actions. A blind label cites none.
- **Tests:** the clean synthetic dataset passes only with the fix; evaluation rejects a blind row that cites a suggestion.

### 2.3 Configuration hardening that the fixes needed [IMPLEMENTED]

- Unknown keys under `provider` and `protocol` are now refused (a misspelled `temprature` can no longer vanish silently).
- `run_id` must be 1–64 letters, digits, `.`, `_` or `-`, because it now names the run-manifest file.
- Tests: `test_unknown_provider_and_protocol_keys_are_refused`, `test_a_run_id_that_names_a_file_must_be_safe`.

---

## 3. The polarity decision that remains yours [PROPOSED; nothing chosen]

### 3.1 The exact conflict [VERIFIED]

| Source | What it says |
| --- | --- |
| `annotate.content_errors` (`annotate.py`), for each of `rel_equity`/`pol_equity`, `rel_rates`/`pol_rates`, `rel_gold`/`pol_gold` | polarity is **required** when the relevance is `R` (`POS`, `NEG`, `NEU`, `MIX` or `UNC`) and **must be blank** otherwise |
| Where that rule is applied | human labelling and the working copy; AI output validation (`validate_output`); review recording (`record_review`); the new evaluation checks |
| B2-I section 3.8 | polarity is recorded per `R` theme, "not analysed in this review", "kept for a later, separately approved evaluation" |
| `ai/rubric_v1.md` and `OUTPUT_KEYS` | the model must return `pol_equity`, `pol_rates`, `pol_gold`, with a polarity for every `R` theme |
| **B2-T section 8.4** | "Polarity: **Not requested in v1** ... Fields stay blank" |

An `R` theme with blank polarity is invalid under the validator, for humans and for the AI alike. B2-T's text and the validator cannot both hold.

### 3.2 The smallest compatible options

| Option | Change needed | Comparability with the existing human labels | Effect on the research question |
| --- | --- | --- | --- |
| **P1: as built** (`P1_required_as_in_existing_rubric`) | None. Polarity is asked for every `R` theme, and `UNC` is allowed | Full: the same fields and rules as the human-only labelling | None, because polarity is not analysed. Carries the hindsight risk B2-T named, on a field nobody reads yet |
| **P2: instruct `UNC` for every `R`** | New rubric text (a new rubric version), so a new Gate B hash. Validator unchanged | **Reduced.** Polarity on AI-suggested rows would be a placeholder, and an accepted row would carry `UNC` instead of a human judgement. Not comparable with the human-only rows | None for relevance. Later polarity analysis would have no usable values on accepted rows |
| **P3: polarity not collected** | A new schema version where every `pol_*` must be blank, a validator mode for it, new rubric text, and an export change. Human reviewers also leave polarity blank | Relevance, ambiguity and company fields stay comparable. **No polarity exists for any item in this dataset** | None for relevance; a later polarity study would need those items re-labelled |

### 3.3 What was implemented, and what was not

- **Implemented:** a required config key `protocol.polarity_option`. It is `null` until you set it, and while it is `null` execution is blocked ("the polarity decision is yours"). It is covered by Gate A. **Only P1 exists in code; any other value is refused at load** ("not implemented; any other polarity policy is a separate, approved change").
- **Not done:** P2 and P3 are not implemented, no rubric or validator rule was changed, and **no config sets this key**. The template value stays `null`. Recording `P1_...` is a choice only you can make.
- Tests: missing option blocks; unimplemented options refused (5 forms); the option is part of Gate A; a characterisation test pins that an `R` theme without polarity is invalid.

---

## 4. Temperature [IMPLEMENTED, provider-neutral]

- **Where:** `provider.temperature` in the experiment config, one value for the run.
- **Validation:** a real number from **0.0 to 2.0** inclusive. Booleans, text, lists, `NaN` and infinities are refused at load, and nothing is clamped or rounded. A missing value is a blocker ("no default is substituted"). The 0–2 range is only a provider-neutral outer bound.
- **Approval fingerprint:** the exact value is inside the Gate B hash. Changing it after approval invalidates Gate B and nothing else (tested); `0` and `0.0` hash the same, and `0.2` does not.
- **Passed to the provider:** the request carries the approved temperature. An adapter must pass exactly that value or refuse.
- **Persisted** (the model identifier is persisted with it):
  - every suggestion record: `params.temperature` and `provider.model_id`/`model_version`;
  - a new **run manifest**, `audit/run_manifest_<run_id>.json`, written read-only at the start of a run, holding provider, model ID and version, temperature, output cap, timeout, prompt and rubric hashes, polarity option, the four approval hashes and every limit. The `run_started` audit event records its SHA-256;
  - a resumed run must reproduce the manifest exactly, or it is blocked;
  - the export manifest lists the temperatures used.
- **Missing temperature at run time:** refused even with an authorization that matches the incomplete config (tested).
- **Unresolved, provider-specific:** the allowed range differs by provider and model, and some models may not accept a temperature at all. Whether the model you choose can honour it is [UNVERIFIED]. No adapter was registered and no provider was called.

---

## 5. Retention [IMPLEMENTED for a limited scope]

`ai retention --experiment <yaml> [--confirm-delete]`. Dry run by default; deletion needs the explicit flag.

**What `retention_days` now expires** (nothing else is ever listed):

- `suggestions/ai_suggestions_valid_v1.csv` and `queue/review_queue_v1.csv` (both rebuilt from the protected records);
- `suggestions/ai_suggestions_raw_v1.jsonl.partial-N` (crash fragments that can hold a truncated provider response).

**Clock:** the end of the last recorded run, read from the hash-chained audit log, not from file times (tested). No recorded run, an unfinished run, or an unreadable end time means nothing expires. The audit chain is verified first; a tampered chain stops the command. A deletion appends a `retention_deleted` event; a dry run writes nothing.

**Safety rules [tested on synthetic folders]:** `retention_days` must be a whole number from 1 to 3650 (nothing is defaulted); the folder must look like an AI experiment (a snapshot and an audit log), so the original review folder and arbitrary folders are refused and decoy `annotation_A.csv`, `key_sealed.csv` and backup files survive; a directory or other non-file in an expirable name is never touched; deletion never recurses.

**Never touched:** the snapshot and every original file, the item inputs, the raw suggestion chain, the review chain, the audit log and run manifests, the export, fingerprints, approvals, and everything outside the folder.

**Limitation, reported as a required design change:** the raw provider responses sit **inside** the hash-chained suggestion records. Deleting or editing one breaks the chain that shows nothing was altered, so **they are not expirable in the current layout**. To make them expirable, the response text would move to a separate payload file, and the chain would keep only its SHA-256. That also decides what the research record must keep. I did not make that change and deleted nothing. Gate C should be approved with this limit in view; the dry run now prints the covered and uncovered artifacts.

No real data was deleted. No real AI experiment folder exists.

---

## 6. Evaluation [IMPLEMENTED: integrity and methodology-neutral aggregation]

`ai evaluate --experiment <yaml> [--blind-provenance <json>]` and `ai/evaluation.py`. It prints a report and writes nothing. It reads the exported dataset, the snapshot items, the recorded overlap list and the suggestion records. It does not name or open the sealed key (tested).

**Integrity checks, each reported without stopping the others:** schema (columns); missing, duplicate and unknown items against the experiment's item set; rubric validity of each row (shared validator); `annotator_type`; timestamps; the link between `label_origin` and `ai_exposure`; suggestion references (an AI-seen label must cite its item's valid suggestion, an unexposed label must cite none, and a "no suggestion" label cannot exist where a valid suggestion does); duplicate references.

**Conditions kept apart:** human-only (no AI exposure), independent-human candidates (blind), AI-assisted (accepted or edited), and AI-exposed (everything made after seeing a suggestion). **An AI-exposed label is never counted as independent**: relabelling an exposed row as blind, or clearing its exposure flag, is reported as an error and withholds the comparison (tested).

**Blind comparison** only runs if the supplied provenance validates: all fields present; the fingerprint equals the SHA-256 of the sorted item IDs; every ID is an original overlap item; the subset was **committed before the first suggestion was generated** (time read from the suggestion records); the experiment matches; every registered item is an unexposed blind label and no unregistered item is. It then reports, per rubric field and for the company notice: pairs, agreements, raw agreement, a Wilson 95% interval, the confusion table, and R-versus-not-R. Ambiguous (`A`) pairs are shown both ways (all pairs, and excluding `A` with the excluded count and the reporting floor), **neither designated primary**.

**Limits, printed in every report:** one human annotator; Wilson intervals ignore batch clustering and are too narrow; headline-only evidence; agreement is not accuracy; small denominators. The report lists what it does **not** claim (agreement as accuracy, model quality, research validity, two-human agreement).

**Decisions needed before any statistical evaluation:** how `A` is treated in the primary analysis; whether kappa and AC1 are reported (the existing arithmetic is deliberately not wired in); a clustered bootstrap; whether AI-assisted labels may support the B2-I section 4.7 filter decision (an amendment); and the polarity option.

**Not done:** no evaluation of real data (no real export exists and no AI-assisted labels exist). No agreement or quality figure is claimed. All tests use synthetic folders.

---

## 7. Tests

All offline; the autouse guards block sockets, DNS and the database. The build lock is lifted only inside a test, for a scripted fake provider.

| File | Tests |
| --- | ---: |
| `test_ai_repairs_duplicates_temperature.py` (new) | 73 |
| `test_ai_retention_evaluation.py` (new) | 74 |
| `test_ai_run_review_export.py` | 53 |
| `test_ai_gates_snapshot.py` | 57 |
| `test_ai_schema_prompt_chain.py` | 55 |
| `test_ai_suggestion_validation.py` | 30 |
| `test_sample_isolation.py` (scans the `ai/` subpackage too) | 15 |

- `pytest tests/backend/data/gdelt -q -p no:cacheprovider`: **577 passed, 0 failed** (430 before this task, plus 147 new).
- `compileall -W error` on the tool and its tests: clean. Unused-import scan: 0.
- **Not run:** the full project suite, the hosted-database backend tests, and the frontend checks (not authorised, and not relevant to this change). **I do not claim the full project suite passed.**
- Existing tests needed only fixture updates (the synthetic config gained `temperature` and `polarity_option`); no existing assertion was changed.
- Failures during development: three were test mistakes (a wrong row number in a scripted interactive test, a date that could not be serialised, an over-strict word check). Two were real code problems found by the new tests: the blind `suggestion_ref` issue (section 2.2), and a crash in the evaluation summary on inconsistent rows, which is now guarded.

**Verification on the real project** (a placeholder config in the scratchpad, pointing at the real unlabelled item file; no model, no write):

- `ai dry-run`: exit 0, `provider_called`, `data_sent` and `files_written` all `false`; 1,493 sendable items, 312 overlap; files under `datasets/` identical before and after.
- `ai run --confirm-ai-run`: **exit 3, `BLOCKED` with 14 unmet prerequisites** (12 before; the two new ones are the temperature and the polarity decision). Without the flag: also exit 3.
- `ai retention` and `ai evaluate` on a destination that does not exist: exit 1, and nothing is created.

---

## 8. Execution-gate status and what remains

| Lock | Status |
| --- | --- |
| Build lock `AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD` | `False` |
| Provider adapter registry | empty |
| `--confirm-ai-run` | required |
| Gates A, B, C, D | no approval record exists |
| `ai run --confirm-ai-run` | **blocked** |

**Still needed before anything can run (all yours):** Gate A (methodology and the blind subset); the polarity option; Gate B (provider, pinned model and version, temperature, and an adapter that is written and reviewed); Gate C (what leaves the machine, provider terms, retention, and the raw-response limit in section 5); Gate D (run ID and limits); the build-lock change; and the run command.

---

## 9. Changes that affect approval hashes or comparability

No approval record exists, so **no existing approval was invalidated.** The effects:

- **Gate A binding** now also covers `protocol.polarity_option`. **Gate B binding** now also covers `provider.temperature`. Gates C and D keep their formulas. Any binding value printed earlier (including the B2-U4 probe, already marked "not for approval") no longer matches, and none was approved.
- **Unchanged:** the prompt hash, the rubric hash, the item-set hash, the overlap fingerprint, and every original file.
- **Config schema:** two new keys, unknown `provider`/`protocol` keys refused, a stricter `run_id`.
- **Records:** suggestion `params` gain `temperature`; review `suggestion_ref` is now empty for blind labels; `labels.near_dup_of` may be non-empty; the export manifest gains `near_dup_references` and `temperatures`. The exported CSV columns and the `b2t_annotation_v1` schema name are unchanged, and no AI-assisted dataset exists yet to be affected.
- **Experiment definition:** the original human-only dataset, its schema, rubric and validator are unchanged, so comparability with the original labels is unchanged. The polarity question (section 3) remains the one open comparability decision.

---

## 10. Confirmations [each VERIFIED above]

- **No model was run and no provider was called.** The adapter registry is empty, and the tests use a scripted fake with the network blocked.
- **No project data was transmitted.** No web access was used in this task.
- **No real labels or AI suggestions were generated.** 0 of 1,493 labelled; 0 suggestions; no AI-assisted export exists.
- **The sealed key was not opened.** Only its size and modified time were read (unchanged). `.env` and credentials were not read.
- **No original annotation item, working copy, backup, overlap list or prior output changed** (digest of all 568 files under `datasets/` identical).
- **No GDELT download or acquisition.** The switches are unchanged.
- **No commit and no push.** Git status is the same entries on the same single commit, plus this report.

## 11. Files changed

Changed: `ai/config.py`, `ai/provider.py`, `ai/prompt.py`, `ai/store.py`, `ai/runner.py`, `ai/reviewer.py`, `ai/export.py`, `cli.py`, `README.md` (all under `backend/wealthpilot/data/gdelt/`), `tests/backend/data/gdelt/conftest.py`, `docs/MEMORY.md`.

New: `ai/retention.py`, `ai/evaluation.py`, `tests/backend/data/gdelt/test_ai_repairs_duplicates_temperature.py`, `tests/backend/data/gdelt/test_ai_retention_evaluation.py`, this report.

Not changed: the rubric text, the validator, the original annotation code, earlier reports (the B2-U4 package is not edited; its section 1 defects are resolved here except for the open decisions above).
