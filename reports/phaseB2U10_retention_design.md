# Phase B2-U10: raw-response retention and hash-chain design (PROPOSED, NOT IMPLEMENTED)

Date: 2026-10-19. Status: **a reviewable design and test plan. Nothing here is implemented, migrated or deleted.** No existing artifact was touched. Implementation needs your approval of the design and of the retention policy (decision D14 in the [readiness report](phaseB2U10_readiness_report.md)).

Written for: you, the project owner, and a reviewer of the hash-chain code.

**Labels:** [VERIFIED] read in the code; [PROPOSED] design, not built; [PENDING] your decision.

---

## 1. The problem, verified

- A provider response is stored verbatim in `raw_response` inside each suggestion record of `suggestions/ai_suggestions_raw_v1.jsonl` (`ai/runner.py`). [VERIFIED]
- `ChainedJsonl.append` computes `record_sha256 = sha256_obj(body)` over the **whole** record, and the next record's `prev_sha256` commits to it; `_scan` recomputes both on every read (`ai/chain.py`). [VERIFIED]
- So removing or editing a response changes the body, breaks the chain at that line, and invalidates every later record. `retention.py` already lists the file as "not expirable in the current layout". [VERIFIED]
- What is stored beside the response: the item ID, input fingerprint, attempt, prompt and rubric hashes, parameters, provider name, model ID and version, request ID, token counts, latency, the parsed output, the validation result and any provider error detail. The request text is **not** stored, only the prompt hash. [VERIFIED]
- Other artifacts with text: the derived valid CSV (parsed fields, evidence excerpts) and the queue CSV (both already expirable); reviews (free-text notes); export and snapshot (public titles and URLs, protected). [VERIFIED]

Today there is no real response in any chain: no run has ever happened. The design therefore concerns **future** experiments only.

## 2. Principles [PROPOSED]

1. The chain proves **what was accepted and when**, never carries sensitive text, and verifies the same whether or not payloads still exist.
2. Deletion is itself an audited, verifiable event, never a silent absence.
3. No existing chain, record or file is rewritten, migrated in place or deleted by this design.
4. Fail closed: a missing or corrupt payload that is not covered by a valid expiry record is an error.
5. The retention period, and who may change it, is a gated, approved setting.

## 3. Design

### 3.1 Separate the payload from the integrity-critical metadata

A new record schema, `b2t_ai_suggestion_v2`, replaces `raw_response` with a reference:

```
raw_response_ref: { "sha256": <64 hex>, "bytes": <int>, "encoding": "utf-8" }
raw_response_sha256: <same hash>          (already present)
```

The response text is written to `suggestions/payloads/<sha256>.txt`, a **content-addressed** file. The chain records only the hash and size, so the chain's own hash never depends on the text.

Permanently kept in the chain (enough to audit what was accepted): item ID, input fingerprint, attempt, run ID, prompt and rubric versions and hashes, parameters, provider name, model ID and version, request ID, token counts, latency, status, validation result, the **parsed** output, and the payload's hash and size. Provider error detail is truncated to a fixed length and scrubbed of anything resembling a credential **before** it is stored.

### 3.2 Stable identifiers and reference integrity

- The identifier is the SHA-256 of the exact bytes. It is stable, collision-resistant and self-verifying: a present payload is valid only if its bytes hash to its name.
- Two records with the same response share one file (same hash, same bytes), which is safe. A name whose bytes hash to something else is corrupt.
- Every v2 record must reference a payload hash; a record without one is a v2 schema error.

### 3.3 Verification states

For each v2 record the verifier computes exactly one state:

| State | Condition | Result |
| --- | --- | --- |
| `PRESENT_OK` | file exists, bytes hash to the reference, size matches | pass |
| `PRESENT_CORRUPT` | file exists, hash or size differs | **fail** |
| `EXPIRED_AUTHORIZED` | file absent and a valid `payload_expired` event for exactly this hash exists in the audit chain | pass (payload intentionally gone) |
| `MISSING_UNAUTHORIZED` | file absent and no such event | **fail** |
| `EXPIRY_PENDING` | file present and a valid expiry event exists (an interrupted deletion) | pass, with a warning; the next expiry run finishes it |
| `EXPIRY_INVALID` | an expiry event exists but is malformed, names the wrong hash, or fails the authority check (3.5) | **fail** |

The chain's hash check is unchanged and independent of these states.

### 3.4 Expiry metadata is itself verifiable

Expiry is recorded in the existing hash-chained **audit log** as `payload_expired` with: payload hash, bytes, expiry time, the retention period and the approval reference that authorised it, the retention clock's source (the run-end event's hash), and a count. Because the audit log is chained, the deletion record cannot be altered or removed without breaking the audit chain. The `policy_sha256` of the approved retention setting (Gate C's `retention_days`) is included so a record can be checked against the policy in force.

### 3.5 Authority and clock

An expiry is valid only if: the experiment's Gate C approval is present and binds the current retention period; the audit log records a finished run; and `now >= run_end + retention_days`. All three are checked by the verifier from the chains, not trusted from the event. The retention period is part of the Gate C hash, so changing it invalidates the approval and needs a new approval by you.

### 3.6 Atomicity, interruption and failure recovery

- **Write order (new response):** write the payload to a temporary file in the same directory, flush and fsync, then atomically rename to `<sha256>.txt`; **only then** append the chain record. A crash after the rename and before the append leaves an orphan payload (harmless, reported by an orphan check, never silently trusted). A record can therefore never point at a payload that was not durably written.
- **Expiry order:** append the `payload_expired` event first, then delete the file. A crash between leaves `EXPIRY_PENDING`, finished by a rerun. Deleting first would produce `MISSING_UNAUTHORIZED`, so that order is forbidden.
- **Repeated expiry runs** are idempotent: an already expired hash is skipped and no duplicate event is written.
- **Partial write of a chain line** is already handled (`.partial-N` quarantine); fragments may contain response text, so they stay in the expirable set.

### 3.7 Access control and minimisation

- Payload files are written read-only; the directory is created owner-only where the platform allows (limited on Windows, so the design does not rely on it).
- Response text is **never** logged, printed or placed in an error message, an audit event or a report: events carry hashes and counts only. A test greps events, exceptions and CLI output for a canary string.
- Deletion removes only files whose names match the payload pattern inside the experiment folder, never a directory, and refuses symlinks.
- The parsed output, kept permanently, is already restricted to validated fields; evidence excerpts are bounded in length by the existing schema.

### 3.8 Backward compatibility and migration

- Existing **v1** records (inline `raw_response`) remain valid and **non-expirable**; the verifier recognises the schema per record, so a mixed chain verifies.
- **No in-place migration.** The new layout applies only to a **new** experiment folder with a new schema tag. There is no real v1 data today, so nothing needs migrating. If a v1 experiment ever exists, it stays protected as is.
- A configuration switch selects the layout, defaulting to the current one until you approve the design; the adapter and run code are unchanged otherwise.

### 3.9 Rollback

Because it is new-folder only, rollback is: stop using the v2 layout and discard the experiment folder created with it. Code rollback is a revert of the change; no existing data depends on it. A "partial migration" cannot occur because there is no migration; the closest case, a v2 experiment interrupted mid-expiry, is covered by `EXPIRY_PENDING`.

### 3.10 Behaviour on missing or corrupt references

Per section 3.3: corrupt, unauthorised-missing and invalid-expiry are failures; the run, export, review and evaluation paths all call the same verifier and refuse. A **review** that depends on a record whose payload expired still works, because it uses the parsed output, not the payload.

### 3.11 What stays a decision for you [PENDING]

Whether the research record must keep raw responses at all; how long (`retention_days`); whether the parsed output alone is a sufficient permanent record; and whether to approve this design before any experiment folder is created.

## 4. Test matrix (to be built before approval; synthetic data and a scripted fake provider only)

| # | Scenario | Expected result | Failure semantics |
| --- | --- | --- | --- |
| 1 | Valid payload, valid chain | all records `PRESENT_OK`; chain verifies | none |
| 2 | Payload bytes edited in place | `PRESENT_CORRUPT` | verification error; run, export and evaluate refused |
| 3 | Chain metadata edited (a field, the reference hash) | the chain breaks at that line (`ChainError`) | refused |
| 4 | Payload missing before any expiry | `MISSING_UNAUTHORIZED` | refused |
| 5 | Payload expired after the authorised period with a valid event | `EXPIRED_AUTHORIZED`; chain verifies; reviews and export still work | pass |
| 6 | Expiry event with the wrong hash, a bad time, or a retention period that differs from Gate C | `EXPIRY_INVALID` | refused |
| 7 | Expiry attempted before `run_end + retention_days` | nothing deleted; reported "not expired" | no event written |
| 8 | Record references a hash with no payload and no event | `MISSING_UNAUTHORIZED` | refused |
| 9 | Crash after payload rename, before the chain append | orphan payload reported; chain unchanged; the response is re-requested only by a new approved run, never reconstructed | orphan listed, no silent use |
| 10 | Crash after the expiry event, before deletion | `EXPIRY_PENDING`; rerun deletes and completes | warning, then pass |
| 11 | Two records share one hash | one file, both `PRESENT_OK` | pass |
| 12 | A payload file whose name hashes to different bytes | `PRESENT_CORRUPT` | refused |
| 13 | Legacy v1 record with inline `raw_response` | verifies; reported as non-expirable | pass |
| 14 | Mixed v1 and v2 chain | each record judged by its own schema; whole chain verifies | pass |
| 15 | Expiry run repeated | second run deletes nothing and writes no event | idempotent |
| 16 | Deletion attempted without confirmation, on a symlink, outside the folder, or on a protected file | refused; nothing deleted | refused |
| 17 | Response text appears in an event, exception, CLI output or report | canary never found | test fails if found |
| 18 | The retention period changed in the config after approval | Gate C hash differs; expiry refused until re-approved | refused |
| 19 | Interrupted v2 layout creation (partial folder) | init refuses to reuse the folder | refused |
| 20 | The v1 verifier run on a v2 chain, and the reverse | each fails closed with a clear schema error | refused |

## 5. Implementation sequence (after approval)

1. v2 schema and a pure verifier with the states in 3.3, and tests 1 to 8, 11 to 14 (offline, no runner change).
2. Payload writer with the write order in 3.6; tests 9, 12, 17, 19.
3. Expiry in `retention.py` with the event order in 3.6 and the authority checks in 3.5; tests 5, 6, 7, 10, 15, 16, 18.
4. Switch the runner to the v2 layout behind the approved configuration switch; update the export and bridge to read the v2 chain; test 20 and the full GDELT regression.

None of these starts without approval. Item 4 touches the provider path, so it needs your explicit authorisation separately and still leaves the build lock and adapter list unchanged.
