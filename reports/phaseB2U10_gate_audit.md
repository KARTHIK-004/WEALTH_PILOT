# Phase B2-U10: gate A to D readiness audit

Date: 2026-10-19. Status: **audit only. No approval record, experiment config or hash was created.** Every gate is a missing record, not a failed check.

Written for: you, the project owner, who is the only person who can approve these gates. Part of the [U10 readiness report](phaseB2U10_readiness_report.md).

**Sources read:** `ai/config.py` (`GATES`, `GATE_NAMES`, `bindings`, `blockers`, `_approval`, `authorize_run`), `ai/runner.py` (`dry_run`, `run_suggestions`), the B2-U4 approval package, and the output of the non-writing `ai dry-run` on a scratch probe config **outside the repository** (`u4_experiment_probe.yaml`, deliberately incomplete, never an approval). No experiment configuration exists in the repository, so there is nothing to approve yet.

## 1. How a gate works [VERIFIED]

An approval is a YAML record with `approved: true` (only the boolean counts), `approved_by` (initials or a name, never an email), `approved_on`, a `reference`, and `binds_sha256`, the 64-hex hash the dry run prints for that gate. The hash is computed from the configuration (below), so **any later change to the bound content makes the approval stale** and execution blocks. `authorize_run` lists **every** unmet prerequisite and returns an authorisation only if none is unmet. Two things sit outside the gates and also block: the build lock and the adapter registry.

## 2. Gate table

| Gate | Authoritative definition | Required evidence | Current evidence | Missing prerequisites | Owner | Safe next action | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **A: methodology** | `bindings["A"]` hashes: `experiment_id`, `protocol_id`, `blind_item_ids`, `review_required_for_every_item` (fixed `True`), `polarity_option`, `provider_exclusion`, and the original overlap file's SHA-256 | A complete experiment config with `provider_exclusion` and `polarity_option` set; an approval record whose `binds_sha256` equals the dry run's gate A hash; your decision on the methodology | No experiment config in the repo. In the probe: `provider_exclusion = overlap_and_blind`, `polarity_option` unset, `blind_item_ids` empty, overlap hash from `selection_log.json` (verified: 312 overlap items). Probe gate A hash `3709072b81a7…` is **not for approval**. No approval record | the methodology decision (D1); `provider_exclusion` (D2); `polarity_option` (D7a); the blind-subset decision; the approval record | project owner | decide D1, D2 and D7a first; then create a real config and re-run the dry run | **blocked: no record** (no check has failed) |
| **B: provider and model** | `bindings["B"]` hashes: provider name, `model_id`, `model_version`, `temperature`, `credentials_env_var`, `prompt_version`, `prompt_sha256`, `rubric_version`, `rubric_sha256`, `output_version` | Provider, pinned model and version, temperature within the model's range, a credentials variable name (the value is never read here), an **adapter registered for that provider**, and the approval record | None set. Prompt and rubric hashes are computed and stable. **Adapter registry is empty**; no adapter code exists. No approval record | the provider decision (D8); temperature; the credentials variable; **an adapter** (a separate approved change, possibly a library approval); the approval record | project owner | none until D1 and D8; M1 needs no Gate B | **blocked: no record, no adapter** |
| **C: data handling** | `bindings["C"]` hashes: `transmission_fields` (must equal the approved five), `destination`, `retention_days`, `provider_data_terms_reviewed` | A decision on what may be transmitted; `provider_data_terms_reviewed: true` (a statement only you can make after reading the provider's terms); `retention_days` set (1 to 3650); the approval record | `transmission_fields` match the approved list in the probe; `provider_data_terms_reviewed: false`; `retention_days` unset; no approval record | D9; the provider's terms (after D8); a retention period (D14); the approval record | project owner | decide the principle in D9; do not set `provider_data_terms_reviewed` until the terms are read | **blocked: no record** |
| **D: execution** | `bindings["D"]` hashes: `experiment_id`, the item-set fingerprint, `run_id`, the **excluded-item set hash**, and all limits (`max_requests`, `max_input_tokens`, output tokens, attempts, re-asks, backoff, optional cost and prices) | A run ID; `max_requests` and `max_input_tokens` positive; limits within bounds; if a cost cap is set, a currency and both unit prices (no price is assumed); a dry run whose printed hash you approve; explicit execution authorisation | Item-set hash `f88185ac…` (probe); excluded-set hash from the probe's `overlap_and_blind`; limits unset except output tokens 400; no run ID; no approval record | run ID; the two limits; any spending cap and prices; gates A to C valid; the build lock; an adapter; `--confirm-ai-run`; explicit authorisation | project owner | none until A to C | **blocked: no record; depends on A to C** |

## 3. Everything the dry run lists as unmet (15) [VERIFIED]

1. Build lock is `False`. 2. `--confirm-ai-run` not given (the dry run never passes it, so this line always shows). 3. Provider, model and version not set. 4. Temperature not set. 5. Polarity option not recorded. 6. Credentials variable not set. 7. `max_requests` not set. 8. `max_input_tokens` not set. 9. Provider data terms not reviewed. 10. Retention days not set. 11. Run ID not set. 12 to 15. Gates A, B, C and D have no approval record.

In the probe the exclusion mode **is** set, so it is not listed; in any real config left unset it adds a sixteenth line. The adapter-missing line appears once a provider name is set.

## 4. Missing record versus failed check

- **Missing record:** all four gates. Nothing has been tried and rejected; there is nothing to evaluate yet.
- **Failed check:** none. A gate fails only when an approval record exists whose `binds_sha256` differs from the current content, or when its fields are invalid. No record exists, so none can be stale.
- **Currently satisfied evidence:** only the non-gate safeguards: exclusion code and tests, bridge and provenance verification, the evaluation fingerprint. These are prerequisites to trust, not approvals.

## 5. Ambiguities recorded (clarification welcome)

1. **No field names the methodology.** Gate A binds `provider_exclusion`, `blind_item_ids` and `polarity_option`, which together *imply* M2 or M3, but "M1", "M2" or "M3" is not itself a configured or hashed value. M1 needs no experiment at all. Whether Gate A should also bind an explicit methodology identifier is a design question (it would change the Gate A hash).
2. **M3 conflicts with both exclusion modes** (it needs blind items sent). Whether M3 would use `none` or a new mode is undecided and not implemented.
3. **Hash stability.** Gate hashes depend on the rubric and prompt files and the item set. A change to any of them after approval silently makes the approval stale (by design), so the approval should be created last.
4. **The retention policy** appears in Gate C only as `retention_days`; what that period applies to (derived files only today, raw responses not at all) is explained in the retention design, not in the gate.

## 6. Constraints preserved [VERIFIED]

The build lock is `False`; the adapter registry is empty; no approval or experiment record was created; no config was written into the repository; the probe is outside it and writes nothing.
