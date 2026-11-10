# Phase B2-U3: AI-assisted annotation pipeline (built, disabled)

Date: 2026-10-19. Status: **implemented and tested offline; disabled and fail-closed; not executed.**

**Nothing was run against a model.** No provider was chosen or called, no data was sent anywhere, no AI suggestion
exists, and no label was assigned. The sealed key was not opened (its size and modified time were only read). No GDELT
data was acquired, no dependency was installed, and nothing was committed or pushed.

## 1. What was implemented

A separately versioned annotation experiment for all 1,493 items. It needs four approvals, a provider adapter, a
build-code change and an explicit run flag before it can do anything. None of them exists today.

| Part | What it does |
| --- | --- |
| Snapshot (`ai init`) | Copies the original files into a new versioned folder, read-only. Records the original overlap list (312 items) as history. Never touches the original folder |
| Input schema | Loads only the original, unlabelled `annotation_A.csv`. Refuses labels, duplicate IDs, wrong columns. Computes a SHA-256 fingerprint per item and for the item set |
| Request builder | Builds one request per item from five approved fields only: `item_id`, `batch_date_utc`, `source_domain`, `url`, `title`. An item with control characters is never sent and is never edited |
| Provider interface | Provider-neutral `SuggestionProvider` protocol, error kinds with retry rules, and an **empty** adapter registry. A disabled provider raises on any call |
| Output validation | Strict. No repair, no markdown stripping. Reuses the existing rubric validator, so a suggestion is held to the same rules as a human label |
| Run (`ai run`) | Sequential, resumable, idempotent. Retry limits with backoff, one re-ask for invalid output, request/token/cost caps, a STOP file, redaction of the credential value |
| Stores | Append-only SHA-256 hash chains for raw suggestions, human reviews and audit events. A partial last line is moved aside, never deleted |
| Review queue | Orders items for a human by plain rules. **Every item is reviewed by a person.** There is no automatic acceptance |
| Human review | Accept, edit, reject, uncertain, insufficient evidence, plus no-suggestion and blind. Reviewer, time, reason and AI exposure are recorded |
| Reports | `ai progress` (counts and next action), `ai qc` (descriptive only, not accuracy) |
| Export | A separate dataset `b2t_annotation_v1`. Refuses until every item has a review. Never overwrites. Every row carries `ai_exposure` and `label_origin` |

Model self-reported uncertainty is shown to the reviewer as a hint. It is never treated as a calibrated probability.

### Suggestion record fields

Each raw record holds: item ID and input fingerprint; the three theme relevance values; polarity for each relevant
theme; company notice; ambiguity code and note; verbatim evidence excerpts; an insufficient-evidence flag; the
model's self-reported uncertainty per theme; provider, model ID and version, request ID; prompt version and SHA-256;
rubric version and SHA-256; run ID; start and finish time; token counts; latency; the raw response verbatim with its
SHA-256; the parsed object; the validation result with errors and flags; attempt number; terminal status; and the
hash-chain fields.

Two schema decisions are recorded here for approval, because they go beyond the original plan:

- **`near_dup_of` is not requested from the model.** One request sees one item and cannot see the others. Duplicates
  are handled by the existing pipeline duplicate mark and by the human reviewer.
- **Polarity is required for every `R` theme**, as in the rubric. If B2-T wanted "no polarity in v1", the model would
  have to answer `UNC`. That needs your decision.

## 2. Files changed

New, in `backend/wealthpilot/data/gdelt/ai/` (14 files, about 1,900 lines):
`__init__.py`, `fingerprints.py`, `rubric.py`, `rubric_v1.md` (registered by SHA-256 `d513a76b…ff57`), `provider.py`,
`schema.py`, `prompt.py`, `chain.py`, `config.py`, `store.py`, `runner.py`, `queue.py`, `reviewer.py`, `export.py`.

Changed:

- `backend/wealthpilot/data/gdelt/__init__.py`: the build lock `AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD = False`.
- `backend/wealthpilot/data/gdelt/cli.py`: the `ai` command group, and a `BLOCKED:` exit (code 3) for blocked execution.
- `backend/wealthpilot/data/gdelt/README.md`, `docs/MEMORY.md`: documentation.
- `tests/backend/data/gdelt/conftest.py`: synthetic fixtures and a scripted fake provider.
- `tests/backend/data/gdelt/test_sample_isolation.py`: the import allow-list now scans subpackages too (`glob` to `rglob`).

New tests: `test_ai_schema_prompt_chain.py` (55), `test_ai_gates_snapshot.py` (57), `test_ai_run_review_export.py` (53).

Not created: `ai/experiment.example.yaml`. You declined that file, so the configuration template is in section 4 of this report.

## 3. Disabled by default

Execution is blocked by independent locks. Lifting one does not lift the others.

1. **Build lock.** `AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD` is `False`. Only a reviewed code change lifts it.
2. **No adapter.** The provider registry is empty. Writing one for a chosen provider is a separate change.
3. **`--confirm-ai-run`** must be given.
4. **Four hash-bound approval gates.** Each record must name its approver, date and reference, and carry the hash of
   exactly what it approves:

   | Gate | Approves | Hash covers |
   | --- | --- | --- |
   | A | Methodology | experiment ID, protocol, blind subset, the original overlap file hash |
   | B | Provider and model | provider, model ID and version, credentials variable name, prompt hash, rubric hash, output version |
   | C | Data handling | the fields that may leave the machine, destination, retention, provider terms reviewed |
   | D | Execution | experiment ID, the item-set hash, run ID, every limit |

   Approving one gate never satisfies another. Changing the model, a limit or an item invalidates the matching gate.
5. **Credentials.** The config holds only the *name* of an environment variable. The variable must exist, and its value
   is never read into a log or file.
6. **Refused config keys.** A config with an `enabled` or `auto_accept` key is refused. `review_required_for_every_item`
   cannot be `false`.

A fully approved config in the shipped build still reports exactly two blockers: the build lock and the missing adapter
(tested).

## 4. Proposed configuration (not created, no provider chosen)

This is the template for `experiment.yaml`. Every provider field is `null` until you approve one. It was not written to disk.

```yaml
experiment_id: b2t_ai_assisted_v1
source:
  review_files: datasets/raw/gdelt/english_gkg_v1/review/b2i_review_v1/review_files
destination: datasets/raw/gdelt/english_gkg_v1/review/b2t_ai_assisted_v1   # new; never reused
protocol:
  id: option_B_all_items_ai_assisted
  blind_item_ids: []                  # Option B: none. A blind subset must be original overlap items
  review_required_for_every_item: true
provider:
  name: null                          # Gate B
  model_id: null
  model_version: null
  credentials_env_var: null           # the NAME of an environment variable, never the key
  timeout_seconds: 60
prompt:
  version: b2t_prompt_v1
  rubric_version: b2t_rubric_v1
limits:
  max_requests: null                  # Gate D; required, positive
  max_input_tokens: null              # Gate D; required, positive
  max_output_tokens_per_request: 400
  max_attempts_per_item: 3
  max_reasks_per_item: 1
  backoff_seconds: [2, 4, 8]
  max_cost: null                      # needs currency and both unit prices; no price is assumed
  currency: null
  unit_price_input_per_1k: null
  unit_price_output_per_1k: null
data_handling:                        # Gate C
  provider_data_terms_reviewed: false
  retention_days: null
  external_transmission_fields: [item_id, batch_date_utc, source_domain, url, title]
run_id: null
approvals:
  A: null
  B: null
  C: null
  D: null
# an approval is a record, for example:
#   A: {approved: true, approved_by: "AB", approved_on: 2026-10-20, reference: "...", binds_sha256: "<hash from ai dry-run>"}
```

**Provider status.** No provider is selected. `google-genai` 0.3.0 is installed, but its approval (2026-09-14) covers
the application's debate and explanation features, not this research use. Using it here is a Gate B decision.
`anthropic` is not installed. `openai` is installed but undeclared. No SDK was imported by the pipeline (tested in a
fresh process).

## 5. Artifact layout

Everything is under the new destination folder, a sibling of the original review folder.

```text
<destination>/
  snapshot/        read-only copies of the original files + SNAPSHOT_FINGERPRINTS.json + historical_overlap.json
  inputs/          ai_input_v1.jsonl                one fingerprint per item
  suggestions/     ai_suggestions_raw_v1.jsonl      every attempt, raw responses verbatim (hash chain)
                   ai_suggestions_valid_v1.csv      derived; rebuilt from the raw chain
  review/          reviews_v1.jsonl                 human review actions (hash chain)
  audit/           events_v1.jsonl                  run-level events; no titles or free text
  queue/           review_queue_v1.csv              derived review order
  export/          annotation_b2t_v1.csv + EXPORT_MANIFEST.json   read-only; written once
  fingerprints.json
```

The sealed key is never copied. The human working copy is copied once, as it was at snapshot time, for provenance only,
and is never read by the pipeline afterwards.

## 6. Effect on the original experiment

- **The original files are unchanged.** SHA-256 checked after the work: `annotation_A.csv` `11db13e668bd3da8…`,
  `annotation_B.csv` `211729002893c1e4…`, backup and working copy `11db13e668bd3da8…`. The sealed key was not opened
  (142,900 bytes, modified 2026-10-13, as before).
- **The design changes if AI assistance is used.** The original experiment was human-only on the 312 overlap items. AI
  assistance on those items changes that design. The original overlap list is kept as history in `historical_overlap.json`.
- **AI-seen labels are not independent.** A label made after seeing a suggestion carries `ai_exposure = seen`. The
  export manifest says so, and counts how many original overlap items were AI-exposed. Only rows with `ai_exposure = none`
  were made without AI exposure. A blind subset (Option C or D) is the only way to keep an independent human comparison.
- **The existing `annotate freeze` and `annotate evaluate` do not read the new dataset** (tested). They keep working on the original dataset only.
- **Nothing about B3 or model training changed.**

## 7. Tests

All offline and synthetic. The autouse guards block sockets, DNS and the database.

| File | Tests |
| --- | --- |
| `test_ai_schema_prompt_chain.py` | 55: input schema, output validation (every rejection path), evidence excerpts, flags, request contents, hash chain tampering, partial-line recovery, provider interface |
| `test_ai_gates_snapshot.py` | 57: build lock and no adapter, each gate missing/mismatched/invalidated by a change, config strictness, dry run writes nothing, CLI exit codes, snapshot, original-file immutability, tamper detection, overlap membership kept |
| `test_ai_run_review_export.py` | 53: run via a scripted fake provider with the lock lifted inside the test only: provenance, resume, interruption, retries and limits, re-ask, model mismatch, caps, STOP, redaction, queue, every review rule, interactive reviewer, export, no-network and no-SDK checks |

Results (2026-10-19, Windows, `.venv`):

- `pytest tests/backend/data/gdelt -q -p no:cacheprovider`: **430 passed** (265 before this task, plus 165 new).
- `compileall -W error` on the tool and its tests: clean. Unused-import scan: 0.
- Not run: the hosted-database backend suite. It needs network access to the hosted databases and was not authorised for this task.
- Not done: any live-provider test, because no adapter exists and none may be called.

## 8. Current verified counts

| Item | Value |
| --- | --- |
| Items in the fixed sample | 1,493 |
| Original overlap items | 312 |
| Non-overlap items | 1,181 |
| Items labelled | 0 |
| AI suggestions | 0 |
| Freeze or evaluation file | none |
| GDELT `NETWORK` and `DEV_SAMPLE` switches | unchanged (still on) |
| Pip freeze fingerprint | `3393be50…`, unchanged |

## 9. Decisions still needed from you

1. **Methodology (Gate A):** which option for the 312 overlap items, and the size of any blind subset (B2-T proposed 150).
2. **Provider and model (Gate B):** which provider and model version. This needs an adapter written and reviewed, and a decision on the `google-genai` approval scope.
3. **Data handling (Gate C):** whether item titles and URLs may be sent to an external provider, retention, and that you reviewed the provider's terms.
4. **Execution (Gate D):** run ID, request and token caps, and a cost cap only with approved pricing.
5. **The two schema decisions** in section 1 (`near_dup_of`, polarity).
6. **Lifting the build lock** (a reviewed code change) and running the command.

## 10. Commands

Available now (local, no network, nothing sent):

```text
.venv/Scripts/python.exe -m wealthpilot.data.gdelt ai dry-run --experiment <experiment.yaml>
```

The dry run writes nothing. It prints the item counts, token estimates, the four hashes to approve, and every unmet
prerequisite. `ai init` (which snapshots the originals into the new folder), `ai queue`, `ai review`, `ai progress`,
`ai qc` and `ai export` are also local and need no provider. They were not run against the real data in this task.

**Execution command, UNAVAILABLE until all approvals, a provider adapter and the build-lock change exist:**

```text
.venv/Scripts/python.exe -m wealthpilot.data.gdelt ai run --experiment <experiment.yaml> --confirm-ai-run
```

Today it exits with code 3 and prints `BLOCKED:` plus every unmet prerequisite. Do not run it expecting output beyond that.

## 11. Unrelated issues noticed (not changed)

- `docs/MEMORY.md` has older markdown-lint warnings (heading spacing, a compact table). Not part of this task.
