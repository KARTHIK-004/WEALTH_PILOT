# WealthPilot AI — Threat Model: Sensitive-Data Protection Prototype

**Status**: academic prototype (ADR-047). Not a production control, not a compliance claim, and **not a real blockchain**.
**Scope**: the `wealthpilot/security/` package, the `protected_records` and `audit_ledger_events` tables, the
`/api/profiles/{id}/protected-notes` and `/api/profiles/{id}/security-status` routes, and the "Data Protection" page.
**Companion documents**: `docs/DECISIONS.md` ADR-047 (the decision), `docs/SECURITY.md` (the project's overall posture),
`docs/ARCHITECTURE.md` §24 (wiring), `docs/TEST_PLAN.md` §25 (how it is verified).

> **Academic prototype — not a real blockchain.** The audit ledger is a hash-linked log in the application's own
> PostgreSQL database. It is not decentralized, has no consensus mechanism, is not replicated or independently witnessed,
> is not immutable, and is not production-ready. Nothing in this document or in the UI claims otherwise.

---

## 1. What this protects, stated as four separate claims

The word "security" hides four different properties. This prototype provides the first two **only for one new record
type** and explicitly does **not** provide the last two.

| Property | Provided? | By what | Limit |
| --- | --- | --- | --- |
| **Confidentiality** of protected notes | Yes, partially | AES-256-GCM encryption at rest + owner-scoped access control | Only against someone who reads the database/backups **without** the key. A caller who asserts another customer's identity header is **not** stopped (§7). |
| **Integrity verification** of the audit trail | Yes, locally | SHA-256 hash chain + verifier | Detects edits, reordering and mid-chain deletion. Cannot detect a privileged rewrite of the whole chain, or removal of the newest events without an external head (§9, §10). |
| **Independent tamper resistance** | **No** | — | Nothing outside the application's database vouches for the chain. An external anchor interface exists (§12) but nothing implements it. |
| **Availability / recovery** | **No** | — | Losing the encryption key makes protected notes permanently unreadable. No replication, no key escrow, no recovery tooling (§8). |

No statement here is a regulatory-compliance claim. No certification, audit or penetration test has been performed.

---

## 2. Assets and the data inventory

Inventory taken from `backend/wealthpilot/db/models.py` (verified, not assumed). **"Protected" means encrypted at rest by
this feature. Today exactly one table is.**

| Data | Table(s) | Sensitivity | Stored as | Protected now? |
| --- | --- | --- | --- | --- |
| Customer-written private note (new) | `protected_records` | High (free text about a person's finances) | AES-256-GCM envelope | **Yes** |
| Audit events for protected notes (new) | `audit_ledger_events` | Low by construction (no content) | hash-linked rows | n/a (contains no sensitive data) |
| Name, age, income, employment status, risk inputs | `customers` | High | plaintext | No |
| Essential expenses, liquid assets, contribution, return/inflation assumptions | `financial_inputs` | High | plaintext numerics | No |
| Monthly income / expenses / savings / investment | `monthly_financial_records` | High | plaintext numerics | No |
| Questionnaire answers, financial goals | `questionnaire_answers`, `financial_goals` | Medium–High | plaintext | No |
| Household income, expenses, assets, liabilities, goals (incl. free-text notes/descriptions) | `household_*` | High | plaintext | No |
| Risk assessments, recommendations, analysis runs, agent logs | `risk_assessments`, `recommendations`, `analysis_runs`, `agent_logs` | Medium | plaintext / JSON | No |
| FAR-Trans transactions, market data | `transactions`, `market_data` | Low–Medium (research data) | plaintext | No |

Never present anywhere in the schema (`docs/SECURITY.md` §18): bank account numbers, tax identifiers, government IDs.
Optional user text for the sentiment feature (ADR-043) is analysed in memory and **not stored at all**.

**Not claimed**: repository-wide or database-wide encryption. The statement "sensitive data is encrypted" is **false** for
every row of the table above except the first.

---

## 3. Actors and trust boundaries

```
 Browser (untrusted; devtools-editable localStorage; asserts X-Customer-Id)
    │  HTTPS in a real deployment (the dev setup is plain HTTP on localhost)
    ▼
 ┌─────────────────────────── Application process (trusted) ───────────────────────────┐
 │ API route ─► protected_record_service ─► EncryptionService ─► KeyProvider ─► key     │
 │   (authorize)   (authorize, audit)         (AEAD only)        (boundary)    material │
 │                       │                                                              │
 │                       ├─► AuditLedger (LocalHashChainLedger) ─┐                      │
 │                       └─► SQLAlchemy session ─────────────────┤                      │
 └───────────────────────────────────────────────────────────────┼──────────────────────┘
                                                                 ▼
                                    PostgreSQL (ciphertext + hash-chained events; NO keys)
```

| Actor | Capability assumed | Considered? |
| --- | --- | --- |
| Another application user (or a curious customer) | Can call the API, can edit the URL and request headers | Yes — but see §7: header-asserting users are **not** stopped |
| Accidental misuse (stale tab, wrong profile id in a URL) | Sends mismatched identity/profile | Yes — refused with 403/404 |
| Reader of a database dump, backup or SQL console **without** the app's environment | Reads every row of every table | Yes — protected notes are unreadable; other data is not (§2) |
| Operator / DBA with database write access **and** no key | Edits rows | Partly — edits to ciphertext/metadata fail authentication; chain edits are detected unless the whole chain is rewritten (§10) |
| Attacker who has the application environment (key) **and** the database | Everything | **Not defended.** Game over for confidentiality and for the local chain |
| Malicious or compromised dependency / host | Arbitrary code in the process | Out of scope |
| LLM / AutoGen agents | Receive already-computed dicts only | By design no agent imports `wealthpilot.security`, receives a key, or calls the encryption/ledger code (tested: `tests/backend/security/test_boundaries.py`) |

---

## 4. Component boundaries

**Application layer** (`api/routers/protected_records.py`, `api/services/protected_record_service.py`) authenticates (as far
as the prototype can, §7), authorizes **every** operation against the path profile, validates input (length, type; never
echoes the text, `api/errors.py`), minimizes what it returns (metadata by default; plaintext only on an explicit read by the
owner) and asks the encryption service for cryptography. It owns the transaction.

**Encryption service** (`security/crypto.py`) encrypts and decrypts what it is handed. It does **not** grant access, does
not know who the caller is, never returns or logs a key, and its exceptions are fixed strings with no cause chain.

**Key-management boundary** (`security/keys.py`) is the `KeyProvider` interface: `active_key_id()` and `get_key(id)`. Only
`EncryptionService` calls it. Keys are never in the database, the repository, the frontend, the ledger or ordinary logs.
A production deployment would implement `KeyProvider` against a managed KMS/HSM using **envelope encryption** (the KMS holds a
key-encryption key; per-record or per-tenant data keys are wrapped by it); no caller would change. **The shipped
`EnvironmentKeyProvider` is a development provider and is not equivalent to a managed KMS** (§6).

**Off-chain repository** (`ProtectedRecord`, `protected_record_service.py`): all sensitive content lives in the private
database. The service encrypts before persistence, decrypts only after authorization, scopes every read/update/delete by
`customer_id` at the query, and never duplicates plaintext into a cache, log, or the ledger. Nothing in the ordinary
application requires a blockchain.

**Audit ledger** (`security/ledger.py`) is §9. **Anchor adapter** (`security/anchor.py`) is §12.

---

## 5. At-rest encryption

- **Algorithm**: AES-256-GCM via `cryptography` (already installed as a dependency of `google-auth`; now pinned explicitly in
  `pyproject.toml`). No custom cryptography.
- **Nonce**: 96 bits from the OS CSPRNG (`secrets.token_bytes`), freshly drawn for every encrypt, including every update of
  the same note. Random 96-bit nonces are safe up to roughly 2³² encryptions per key; a high-volume deployment must rotate
  keys before that or use KMS-managed per-record keys.
- **Envelope** (columns on `protected_records`): `envelope_version` (1), `algorithm`, `key_id` (non-secret), `nonce`,
  `ciphertext` (ciphertext ‖ 16-byte tag). A different version/algorithm is rejected before any key is touched, so a future
  algorithm can be added without ambiguity.
- **Associated data** (length-prefixed, unambiguous): envelope version, algorithm, key id, **purpose**, **record id**,
  **owner id**. A ciphertext copied to another row/owner/purpose, or whose metadata was edited (downgrade, swapped key id),
  fails authentication instead of decrypting. Verified by tests, including with an independent AES-GCM decryption.
- **Fail closed**: no key → 503, nothing written; encryption error → nothing written; authentication failure → the record is
  not returned and the response is a generic 500 problem; unknown key id → 503. There is **no plaintext fallback** and
  **no default key**: an unset `PROTECTED_DATA_KEYS` means the feature reports "not configured".
- **Plaintext handling**: the plaintext exists only in local variables for the duration of the request. It is never logged,
  never cached, never written to the ledger, never echoed in a validation error (route-scoped no-echo handler), and
  responses carrying it are `Cache-Control: no-store`. Python cannot guarantee memory is zeroed; that is a stated limit.
- **Log redaction**: the codebase logs fixed strings on security failures. A test drives every route (success, denial,
  tamper, validation failure) at DEBUG level and asserts neither the note text nor key material appears in any log record.
  **Limit**: a database-driver error that reaches the generic 500 handler can include the failing statement's bound parameters in
  the server-side log. For protected notes those parameters are the ciphertext, nonce, key id and opaque ids - never the plaintext or
  a key (encryption happens before persistence) - but ciphertext in a log is still not ideal; production should hide statement
  parameters in SQLAlchemy errors.

---

## 6. Key lifecycle (development provider) and its limits

| Stage | Prototype behaviour | Production expectation |
| --- | --- | --- |
| Generation | The operator generates 32 random bytes (e.g. `secrets.token_bytes(32)`) and base64-encodes them; `keys.generate_key_spec` formats `<id>:<b64>`. The application never generates or stores a key. | KMS-generated, never exported in the clear |
| Storage | `PROTECTED_DATA_KEYS` / `PROTECTED_DATA_ACTIVE_KEY_ID` in the process environment (`.env` is git-ignored). `SecretStr` keeps it out of reprs. | KMS / HSM; access policy; usage audit |
| Use | Loaded per request into an `AESGCM` object in memory | KMS decrypts a wrapped data key; the master key never leaves the KMS |
| Rotation | **Manual.** Add `<new_id>:<key>`, set it active, **keep the old id** so older notes still decrypt. | Automatic key-version rotation + background re-wrap |
| Re-encryption of old records | **Not implemented.** Old notes stay under the old key id until updated. | Re-encryption job with verification |
| Backup | **Keys must be backed up separately from database backups**, and never with them. The database holds only ciphertext. | KMS-managed key backup / multi-region |
| Recovery | **None.** Losing every copy of a key makes the notes it protects permanently unreadable. | Escrow / split knowledge / documented DR procedure |
| Revocation / deletion | Removing a key id makes its notes unreadable (503). Deleting a row removes the ciphertext, but backups and WAL may retain it. | Per-record keys enable true crypto-shredding |

**Why an environment variable is not a KMS**: it has no hardware protection, no access policy, no per-use audit trail, no
separation between "the app can use the key" and "a human or process on this host can read it". Anyone who can read the process
environment or the `.env` file can decrypt every protected note. The development provider exists to exercise the interface
honestly, nothing more.

---

## 7. Authentication and authorization — the decisive limitation

The project has **no server-side authentication** (ADR-020; `docs/SECURITY.md` §7, §21): the login is a client-side demo
credential, there is no session or token, and the only server-visible identity is the `X-Customer-Id` header the client
chooses to send. The prototype's household routes already treat that as an *asserted* identity (ADR-031). This feature reuses
exactly that mechanism rather than inventing a second one (a production-grade auth system would contradict CLAUDE.md §18 and
ADR-020 if built silently).

What is enforced, on **every** protected route:

1. `X-Customer-Id` must be present and a positive integer (else 401, RFC 7807).
2. It must equal the `profile_id` in the path (else 403). Cross-profile requests are refused for create, list, read, update,
   delete and status alike.
3. The customer must exist (else 404).
4. A record is looked up by `(id, customer_id = profile_id)`. An unknown id, a malformed id and **another profile's** id all
   return the **identical** 404, so the existence of someone else's record is never revealed.
5. Changing a record id or profile id in the URL cannot expose another profile's data.

**What this does not do**: a caller who sets *both* the path profile and the `X-Customer-Id` header to a victim's id passes
every check above and receives the victim's decrypted notes. The prototype cannot distinguish that caller from the victim,
because identity is asserted by the client. Therefore:

> Encryption at rest protects protected notes from someone who obtains **the database or a backup without the key**.
> It does **not** protect them from someone who can call the API and lie about who they are.

Closing this gap requires real authentication (a server-issued credential/session bound to a customer) — an explicit
production-hardening item (§14), not something this prototype pretends to have.

---

## 8. Backup, recovery, rotation and deletion

- **Database backup / restore**: backups contain ciphertext, metadata and the hash chain; they contain no key. A restored
  database is readable only if the matching key is supplied. Restore the key from its own backup.
- **Key loss**: unrecoverable (§6). There is no escrow.
- **Rotation**: manual, §6. Test that an older envelope still decrypts after rotation (covered by a test) and that removing a
  key too early is reported as unavailable, not as a decryption "success" or silent data loss.
- **Deletion**: `DELETE` removes the row and writes a `deleted` audit event. Backups, WAL and any replica may retain the
  ciphertext until they age out; true erasure would need per-record keys.
- **Migration not yet applied**: on a database that has not been upgraded (the development database until its owner runs `alembic upgrade head`), every protected route returns a plain 503 saying the migration has not been applied; nothing is read, saved or created, the identity check still runs first (401/403), and no unhandled exception is logged. Once the tables exist the same routes work without a restart.
- **Migration down**: `alembic downgrade e5b1c7d93a20` drops both new tables, destroying the encrypted notes and the audit
  chain. Nothing else is touched because nothing else was changed.

---

## 9. The audit ledger (local hash chain)

**Event content** (structurally enforced by an allow-list and a UUID-only reference check; there is no column that could hold
more): `sequence`, `event_type` (`protected_record.created|accessed|updated|deleted|access_denied`), `occurred_at` (UTC),
`record_ref` (the record's random UUID, or none), `schema_version`, `prev_hash`, `event_hash`. **No** amounts, names, e-mail
addresses, free text, tokens, passwords, keys, actor or reason.

**Hashing**: schema version 1. Canonical form is UTF-8 JSON of `{event_type, occurred_at, record_ref, schema_version,
sequence}` with sorted keys, `,`/`:` separators and ASCII escaping; `occurred_at` is `YYYY-MM-DDTHH:MM:SS.ffffffZ` in UTC.
`event_hash = SHA-256("wealthpilot/ledger/v1\n" ‖ prev_hash ‖ "\n" ‖ canonical)`. Genesis `prev_hash` is 64 zeros. One function
is used to write and to verify.

**Verifier** (`LocalHashChainLedger.verify`) walks events in `sequence` order and checks, per event: contiguous sequence
starting at 1, supported schema version, allowed fields, `prev_hash` equals the previous event's hash, and the recomputed hash
equals the stored hash. It reports the **first** invalid event with a fixed reason code
(`missing_genesis`, `sequence_gap`, `unsupported_schema_version`, `malformed_event`, `previous_hash_mismatch`,
`hash_mismatch`, `head_mismatch`) — never event data. An empty ledger is reported as `empty`, not `valid`.

**Concurrency**: `sequence` is allocated by the ledger inside the caller's transaction after a PostgreSQL transaction-scoped
advisory lock, so appenders serialize. `UNIQUE` constraints on `sequence`, `prev_hash` and `event_hash` are the backstop: a
losing concurrent append raises instead of forking the chain (tested on SQLite via a stale-head simulation and real threads,
and on PostgreSQL via the isolated runner).

**Atomicity**: success events (`created/accessed/updated/deleted`) are written in the **same transaction** as the data
change; an audit failure aborts the operation (fail closed) and a data failure leaves no event. `access_denied` has no data
change to be atomic with, so it is committed on its own, best-effort; if it cannot be written the denial still stands and a
fixed warning is logged. A read that fails authentication or decryption is **not** recorded as "accessed".

**Known operational weaknesses**: any caller can cause `access_denied` events by sending mismatched headers (no rate
limiting; unbounded growth); verification is O(n) and runs on every status request; reads write events.

---

## 10. Database compromise and privileged-attacker limits

| Attacker | Reads notes? | Edits a note? | Edits one audit event? | Rewrites the whole chain? | Removes the newest events? |
| --- | --- | --- | --- | --- | --- |
| Reads a dump/backup, no key | **No** | n/a | n/a | n/a | n/a |
| DB write access, no key | No | Not usefully: changes fail authentication (and fail closed) | **Detected** at that sequence | Cannot make new valid *records*, but **can** recompute a self-consistent chain (no key is needed for SHA-256) | **Not detected** locally |
| Has the key (app host) | **Yes** | Yes (can encrypt a forged note) | Detected unless chain also rewritten | **Yes — verifies as valid** | Not detected locally |
| Has the key **and** an externally recorded head | Yes | Yes | Detected | **Detected** (`head_mismatch`) | **Detected** |

A hash chain stored in the same database as the data it audits does not stop a privileged attacker from rewriting every
event and recomputing every hash. **A successful local verification means "internally consistent", never "the database was
never tampered with".** The test suite includes a test that performs exactly this full rewrite and asserts it still verifies
locally, and that an externally recorded head catches it — the limitation is covered, not hidden.

Mitigations that exist: AAD binding (ciphertext cannot be moved); `expected_head` verification; the anchor interface (§12).
Mitigations that do **not** exist: separate-credential/append-only database role for the ledger table, external anchoring,
write-once storage, signed events. All are production requirements (§14).

---

## 11. Existing unencrypted data and migration safety

**Decision**: protect a **new, clearly defined record type** instead of encrypting existing columns. Rationale: an in-place
change to `customers`, `financial_inputs`, `monthly_financial_records` or the household tables would rewrite user records, break
the goal/risk/behaviour engines and demo seeding that read those numbers, and could not be safely rolled back without a full
backup. The Alembic migration (`f7a2d4b6c810`) only creates two tables; a test asserts it adds/alters/drops/executes nothing on
existing tables.

**Therefore these remain unprotected** (and the UI says so): everything in the inventory (§2) except `protected_records`.

**If existing columns are ever migrated** (not done, not authorized here): (1) add the new encrypted column beside the old one —
no destructive change; (2) a separate, explicit, idempotent command (never an automatic migration) encrypts row by row with the
row id and owner in the AAD, decrypts each result and compares before committing; (3) run application reads against the
encrypted copy behind a flag while the plaintext remains; (4) only after a verified full backup and a soak period, a later
migration nulls the plaintext column; (5) rollback before step 4 is "ignore the new column", after step 4 it is "restore from
backup". Numeric columns the engines compute with (income, expenses…) would need a decrypt-on-read boundary inside the service
layer so `core/` stays pure, and database-side filtering/aggregation on them would be lost.

---

## 12. Local prototype vs a real permissioned blockchain

| Concern | This prototype | A real permissioned ledger would add |
| --- | --- | --- |
| Where events live | Same PostgreSQL database as the data | Separate nodes run by separate organizations |
| Who can rewrite history | Anyone with write access to the table | Requires consensus among independent parties |
| Ordering | Advisory lock + sequence number | Consensus protocol |
| Verification | Recompute hashes locally | Independent nodes agree on the same chain |
| Availability | Single database | Replication across nodes |
| Cost / complexity | None | Operations, governance, identity management, upgrades |

`security/anchor.py` defines the boundary a future integration would implement: `LedgerAnchor.submit_commitment` (append a
digest), `get_receipt`, `verify_commitment` (check a commitment against the off-chain event, locally via
`verify_commitment_against_ledger` and externally via the adapter) and `status` (available/unreachable/not configured). Only a
`LedgerCommitment` (sequence + head hash + schema version) may cross it — never a record, plaintext, key or personal
identifier. Vendor code would sit entirely behind it. **The shipped `UnconfiguredAnchor` is connected to nothing**: it
refuses submissions, returns no receipt, and answers "unverified". There is no wallet, cryptocurrency, tokenization,
smart-contract execution or public-chain upload, and none may be added through this interface.

---

## 13. Distinguishing what the code does from what it cannot do

- It **does** make protected notes unreadable to a database-only reader, bind them to their owner/record/purpose, detect
  tampering with them, refuse mismatched or foreign identities, record who-touched-which-record-when without content, and
  detect edits/reordering/mid-chain removal in that record.
- It **does not** authenticate users, hide notes from an identity-asserting API caller, protect existing data, protect against a
  host/key compromise, provide independent tamper evidence, recover from key loss, rate-limit, or run on a managed KMS.

---

## 14. Production-hardening requirements and unresolved risks

1. **Real server-side authentication and authorization** (session/token bound to a customer; remove reliance on a client-asserted
   header). *Highest priority; without it the confidentiality claim in §1 is limited to database-level readers.*
2. **Managed KMS/HSM** with envelope encryption, per-record or per-tenant data keys, rotation, usage audit, key backup/DR.
3. **Re-encryption/rotation tooling** and a tested key-loss procedure.
4. **Ledger separation**: a distinct database role with insert-only privileges on `audit_ledger_events`, ideally a separate
   database; signed events; write-once storage; **external anchoring** of the head to an independent party (the interface
   exists; no implementation does).
5. **Encrypt or otherwise protect existing sensitive data** per §11, with a reviewed migration plan.
6. **Rate limiting / abuse controls** for denial events; bounded or incremental ledger verification.
7. **Transport security** (TLS), secrets management for `DATABASE_URL` and the key variables, log aggregation controls.
8. **Independent security review and penetration test**; threat model review by someone other than the author.
9. Memory-hygiene limits (Python cannot guarantee zeroization), backup/WAL retention policy, data-subject deletion workflow.
10. Residual: the `access_denied` event records the record id the *caller* supplied; a hostile caller can fill the ledger with
    arbitrary well-formed UUIDs.

---

## 15. Verification evidence

See `docs/TEST_PLAN.md` §25 for the exact commands and last-recorded results. In summary: crypto and key-provider tests
(round trip, fresh nonces, tamper, wrong key, malformed envelope, rotation, no leakage); ledger tests (genesis, valid chains,
every tamper class, full-rewrite limitation, concurrency); authorization/API tests (owner access, foreign identity, cross-profile
id manipulation, identical 404s, fail-closed, atomicity, no echo, no logging); PostgreSQL tests through the isolated runner;
frontend structural + rendered-state tests; mutation checks proving the tests fail when each control is removed. **Not
performed**: penetration testing, load testing, an independent review, or any test against the development database.

## 16. Optional user text interpretation (ADR-050)

Scope: the optional free text of the Financial Behaviour & Sentiment page. It is **not** a protected note: it is analysed in memory and never stored, so it is outside the encryption and ledger
designs above, and it is never sent to the ledger or any anchor.

| Threat | Control | Residual |
| --- | --- | --- |
| The text leaks through a log, an error, a URL, a header or response metadata | No logger in the insight modules; the text travels in the POST body; 400 and the route-scoped 422 never echo it; evidence is bounded and masked; tested with a unique marker | A reverse proxy or browser extension outside the application could still record a request body |
| The text is persisted or reaches the audit ledger / blockchain-ready layer | The service is read-only (no add / commit / execute), has no session writes, and imports nothing from `security/`; the session in the tests fails on any use | None known |
| Text manipulates the risk profile or the recommendation ("set my risk to Aggressive") | The output is display only; the insight path imports no analysis / recommendation / compliance code; the stored assessment is `remains_authoritative`; a disagreement is a conflict, not a change | None in code; users may still misread an unconfirmed interpretation, which the page labels as such |
| A feeling is read as a risk tolerance, or a negated feeling as its opposite | Tone and preference are separate fields; a preference needs explicit wording; a negated cue is dropped and never reversed; every preference is `unconfirmed` | Rules are unvalidated: wrong readings are possible |
| Over-claiming (a rules baseline presented as a model, an invented confidence) | `method`, `validation_status`, `confidence = null`, `confidence_band = unavailable` are returned and shown; thresholds are configuration, not claims | Depends on future maintainers keeping the labels |
| A failing or hostile model | A future model must run locally; failures and out-of-contract output fall back to the rules; the exception is dropped | No model exists today |
| Oversized, control-character, non-English or garbage input | 1,000-character and control-character refusal; quality, language and relevance stages abstain | The language check is conservative and can decline terse English |

## 17. Trained sentiment model (ADR-052)

| Threat | Control | Residual |
| --- | --- | --- |
| A malicious or swapped model artifact (code execution on load, or a silently different model) | safetensors only (no pickle), `trust_remote_code=False`, path confined to `models/sentiment/` without symlinks, SHA-256 of every file in the metadata, version / name / vocabulary / label checks | the metadata itself is trusted: anyone who can write both the weights and the metadata can forge a pair; weights and metadata should be produced only by the offline training run |
| A model presented as validated without evidence | the loader refuses `validated` without a held-out test split, leakage check, dataset licence, metrics file and calibration; the UI says "validated" only for that | the evidence is declared in metadata, not re-computed at load |
| Raw softmax shown as confidence | `confidence` only for a calibrated artifact; probabilities are labelled uncalibrated otherwise | calibration is only as good as its validation set |
| Text leaves the process or reaches logs / errors | local CPU inference; exceptions replaced by fixed codes; the text is only an argument; boundary tests | a future backend could break this: any change to `TransformersBackend` needs the same tests |
| The model resurfaces what the safeguards excluded (quotes, other people, past feelings, hypothetical or conditional statements) | the model reads only the user's own current clauses; a negation-only safeguard is never overridden | the reworded clause text is a distortion the model was not trained on |
| A slow or hung model degrades the service | token limit, wall-clock limit, one worker, fallback to the rules | a timed-out inference keeps its worker busy until it ends |
| Sentiment influences risk, recommendation, portfolio or compliance | no import path exists (tested); display only; the stored assessment remains authoritative | none in code |

## 18. Real-checkpoint, dataset and evaluation path (ADR-052; PRE-APPROVAL ANALYSIS, nothing here has been executed)

Written 2026-10-29 for the owner's review before any hard gate is opened (`reports/sentiment_consolidated_approval_form.md`). "Exists" means in the repository and tested today; "Planned" depends on an approval that has not been given and is **not** a control yet. No model, tokenizer, revision, dataset or user text has been accessed, and no network call has been made.

| Threat | Control | Status | Residual |
| --- | --- | --- | --- |
| A floating reference (branch, tag, `main`, short hash) silently changes the model | only a full 40-character lowercase hash supplied by the caller is accepted; checked before any package is imported | Exists (tested) | the hash is only as trustworthy as the owner's source for it (a metadata query reads it from the same service that serves the files) |
| Files substituted or altered in transit or at the host | SHA-256 of every file recorded and compared (and a mismatch deletes the artifact); TLS with the environment's own `certifi` | Exists as offline-tested code (`training/sentiment/hub_fetch.py`, E1; never executed against a real host); TLS chain depends on D13 | a hash taken from the same source as the file proves integrity of the transfer, not honesty of the source, unless the owner supplies the hash out of band |
| A redirect or file-serving host the owner never approved | host allow-list and refusal of redirects to other hosts in the fetch step | Exists as offline-tested code (E1: the host allow-list is checked on every request and redirect; the transport itself follows no redirect and ignores environment proxies). The Hub library is deliberately not used, so its ability to enforce this stays unestablished. The metadata query ran against `huggingface.co` (2026-10-29): 5 requests in two runs, no redirect observed; the download path (`fetch_files`) has never been executed against a real host | until E1 exists, the only protection would be an accepted residual risk (C1 path C) |
| Pickle or code in the downloaded files (`.bin`, `.pt`, `training_args.bin`, repository code) | `use_safetensors=True`, `trust_remote_code=False`, safetensors-only artifact check, an explicit file list that excludes every pickle-capable format and rejects unexpected files | Exists for loading and artifacts (tested); the file list and the rejection of unexpected files are Planned (E1) | the library, not the repository, decides which files it fetches today |
| The Hub library asks the service to convert a checkpoint and fetches unreviewed files | pinned revision plus `use_safetensors=True` (an observed 5.12.1 property pinned by a test); no undocumented switch used | Exists, version-dependent (D10) | not a guarantee; path B (local conversion-free workflow) or a scoped risk acceptance is the D10 decision |
| Files written outside the approved destination (the library's default cache) | the destination is the only approved location; the default cache must stay absent or empty (checked after the run) | Exists as offline-tested code for the fetch (E1: explicit destination outside the repository, must not exist, rollback on any failure); C5 (the library's default cache) is still unresolved | the check is after the fact |
| Raw dataset text leaking into logs, errors, reports, caches or the ledger | error messages carry counts and fixed codes only; evaluation reports hold no text and no record id; `frozen_evaluation` never echoes a record; no logger in the sentiment code; no import path to the ledger | Exists (tested statically and behaviourally on generated fixtures) | to be re-verified when a real backend and real data exist |
| Personal data in the frozen manifest | e-mail, link and long-digit markers refused in any manifest string; annotators and the adjudicator are codes only | Exists (a pattern heuristic) | the heuristic can miss; de-identification (O2) is the owner's decision |
| Annotators not independent, or the labels not independent of the rubric author | a participant register attested by the owner | Exists as a record only | the code cannot verify independence |
| Duplicate or leaked examples inflating a metric | exact and near-duplicate exclusion verified across splits, inclusive threshold, three disjoint splits | Exists (tested); the near-duplicate method (normalized text, character 5-gram Jaccard) and threshold (0.90, equality counts) are owner-approved (D11) and the manifest must declare exactly them | character n-gram similarity does not catch paraphrases |
| Synthetic, unapproved or unfrozen data presented as validation | `EvidenceBasis` with eight required conditions; `validated` only when every condition and gate holds; the manifest cannot claim more than the checks support | Exists (tested) | whether independently authored fictional text counts as non-synthetic is the owner's decision (form item D3) |
| High precision reached by abstaining | coverage and abstention gates; strict view decides the macro-F1 gate | Exists (tested) | the thresholds are the owner's |
| A metric report read as an activation recommendation | the report says it recommends nothing; there is no lower-bound rule; activation is R14 | Exists (tested) | human interpretation |
| A compromised or vulnerable dependency in the training environment | the hash-pinned S1 list, installation offline with `--require-hashes`, a disposable environment outside the repository, the project environment untouched, OSV re-checked on the day | Exists as a procedure; installation needs D12 | `setuptools` 81.0.0 advisories are accepted for the isolated environment only; the `certifi` / `pip` advisory (D13) is open |
| Licence non-compliance (non-commercial, share-alike, unclear training-data terms) | the owner accepts or rejects each licence in writing; fine-tuned weights are not redistributed; `.safetensors` under `models/sentiment/` are git-ignored | Planned (form items A3.1 to A3.5) | I cannot give legal advice; a model-card claim is not verified permission |
| Training or fine-tuning on user text at run time | none exists: training is offline, explicit and human-invoked only; no request-time training | Exists (tested) | none in code |
| Sentiment influences a financial decision | no import path from sentiment to risk, goals, portfolio, recommendations or compliance (tested); the stored assessment remains authoritative | Exists (tested) | none in code |
| Personal data, contact details or credentials in the participant register | `participant_register.py` refuses e-mail addresses, links, long digit runs, credential-like strings, unknown fields and production-user identifiers; its errors are fixed descriptions with counts and positions, never a value or field name (tested on invented registers; no real register exists) | Exists (tested) | the validator cannot know that a code is a real name or that an attested person is independent: both stay the owner's attestation |
| A production service or an annotator receiving dataset access, model output or a recommendation | the register allows only the evaluator to be a non-production service, refuses `production_service`, and checks each role's `may_view` list (an annotator never sees model output, rules output, a risk profile or a recommendation; nobody sees a risk profile or recommendation); expired or not-yet-started authorizations are refused | Exists (tested) | the register is a statement; enforcing access at the storage layer is D16 / D18 operational work and no storage location is approved |
| Calibration fitted on the wrong data, or calibration read as validation | the D13 temperature is fitted on the calibration split only, applied to held-out probabilities only, with disjoint ids enforced; below 20 scored examples nothing is fitted; labels are never changed; the report says `validated: false` and recommends nothing; synthetic evidence stays `not_validation_evidence` (tested; 28 of 30 mutants caught, 2 equivalent) | Exists (tested) | the temperature is a power calibration of log-probabilities when the probabilities did not come from a softmax; a small calibration split gives a noisy temperature |
| Raw text or annotation files outliving the evaluation, or a rollback restoring deleted raw text | the register must carry a project-owner deletion authorization: raw text kept only until evaluation, audit verification and the R14 decision, then deleted; only hashes, aggregate metrics and decision records retained; rollback restores metadata and aggregates only; completion verified and recorded (validator tested, 5 of 5 mutants caught) | Exists (tested as a schema rule; no real data exists) | the deletion itself and its verification are operational and the storage path (D16) is not approved |
| A synthetic fixture or an agreement / calibration result being mistaken for real validation evidence | every fixture is visibly invented (dataset id, licence, `zq` tokens, `invented-` register); no FROZEN manifest or register outside the tests; agreement alone and calibration alone never give `validated`; synthetic data is `not_validation_evidence` (tested) | Exists (tested) | a human could still misread a document; the report always prints the dataset id |
| Scope creep after the phase closure: a real model, dataset or activation sneaking in | the closure is recorded as a fail-closed state: A3.3 unresolved, A3.5b and D20 rejected, so Phases 4 to 7 stay locked in the guarded form; no FinBERT, no real text, register or manifest, no activation; fixtures cannot yield `validated`; `SENTIMENT_MODEL_ENABLED=false` (tested). The offline rules-based sentiment phase is complete. Transformer evaluation, real dataset creation and production activation are deferred because the required legal, dataset, storage and activation approvals are unresolved. | Exists (tested) | a future phase must start with a new explicit approval request |

## Pretrained research comparison (ADR-053)

Threats considered: a tampered or substituted weight file (SHA-256 manifest + exact revision + recomputed manifest hash); a pickle-capable checkpoint (refused by name and never loaded); a path escape
(root confinement, symlink refusal); a model exception or timeout carrying the user's text (discarded; fixed reason code only); a configuration switch overriding a legal finding (status is a code
constant); a model result steering a financial decision (the object is composed after, and read by nothing; isolation tested); an unvalidated label presented as validated (always
`not_human_validated`, no confidence field). Residual: the manifest hashes detect corruption and inconsistent edits, not someone who rewrites a whole directory; no real model has been exercised.

**ADR-055 addendum (2026-11-05).** New threats and mitigations for the role slots: a first-request stampede (per-candidate non-blocking lock returns `loading`); a hung model stalling requests (timeout plus a 30 s circuit breaker); an unexpected exception leaking text or a path (fixed reason codes; `build_transformer_research` never raises); a registry or configuration change silently enabling an unapproved model (registration is a code constant; Horizon stays `pending_owner_approval`); a status call triggering a heavyweight load (status is non-loading, tested). Residual: the real-weights adapter path has not run.
