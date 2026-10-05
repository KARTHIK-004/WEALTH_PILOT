# WealthPilot AI — Security

## 1. Security Goals

Protect secrets from ever reaching source control, logs, or a response
body. Keep customer data scoped to its own customer id. Prevent any
LLM/agent output from being trusted as a financial number or from leaking
internal reasoning. Disclose prototype-security limitations plainly
rather than implying production-grade guarantees that do not exist.

## 2. Secrets Management

Every secret (`GEMINI_API_KEY`, `GEMINI_PROJECT_NUMBER`,
`DATABASE_URL`, `TEST_DATABASE_URL`) lives only in `.env` (gitignored;
`.env.example` documents the shape with empty values, tracked). Read via
`pydantic-settings` (`config/settings.py`) — never read from a hard-coded
string, never echoed in a log line, a report, a commit message, or an API
response. `git status` at any point in this project's development history
shows `.env`/`.env.example` handled correctly (`.env` untracked, never
staged).

## 3. Environment Variables

`GEMINI_API_KEY`/`GEMINI_PROJECT_NUMBER`/`GEMINI_MODEL` — backend-only,
used by `agents/debate.py`/`agents/explanation.py`; never sent to the
frontend in any form. `DATABASE_URL`/`TEST_DATABASE_URL` — two distinct
values specifically so the test suite can never touch development data.
`ENVIRONMENT`/`LOG_LEVEL` — non-sensitive configuration.

## 4. Database Security

PostgreSQL, accessed only via SQLAlchemy's parameterized query
construction — no raw string-interpolated SQL anywhere in
`backend/wealthpilot/`. The few genuinely-necessary raw `text()` calls
(e.g. `scripts/seed_demo_data.py`'s one direct `risk_inputs` write) use
bound parameters, never string formatting of user-controlled input into
SQL.

## 5. API Security

Every per-customer route is path-scoped by `profile_id` and every query
filters by it at the ORM level (`docs/DECISIONS.md` ADR-024) — this is a
data-scoping guarantee, not an authorization one (see §6). Errors never
leak a stack trace or raw exception message (RFC 7807 problem details
only, `api/errors.py`).

## 6. Customer Isolation

Data isolation exists (one customer's resources are never returned by a
request scoped to a different `profile_id`) but authorization does not:
this prototype has no concept of "this authenticated session is allowed
to access customer N." Any request that supplies a valid `profile_id`
can read/write that customer's data, regardless of which account is
"logged in." This is a disclosed, accepted characteristic of the
prototype-auth scope (`docs/DECISIONS.md` ADR-020), not something to
silently patch with a larger auth system unless explicitly instructed.

### Household authorization (Phase 32)

Household routes are the first routes that authorize against something: they
require the caller's associated customer in the `X-Customer-Id` header
(missing or malformed → 401) and serve a household only to a customer who
belongs to it (unknown household → 404, non-member → 403, with no data from the
denied household in the response). Only the household's primary member can add
or remove members; `GET /api/profiles/{id}/household` answers only for the
calling customer. A customer can belong to at most one household, so a
membership cannot be used to pull the same person into two households.

What this does **not** do, plainly: the header is an asserted identity — the
prototype has no server session, so a client that sends another customer's id
gets that customer's view, exactly as it can with every `profile_id` route
(§6). It protects against accidental or URL-edited cross-household access, not
against a malicious client, and adding a member needs no consent from the added
customer (a primary can attach any existing customer who is not already in a
household, and the member list then shows that customer's name to the
household). Membership grants no access to the member's own profile, analysis or
financial data. Invitation/consent and real sessions are future work, not
implied here.

### Household financial records (Phase 33)

The household's own income, expenses, assets and liabilities reuse exactly the
same identity and authorization as above — the asserted `X-Customer-Id` header,
401 when it is missing, 404 for an unknown household, 403 for a non-member —
with one addition: **only the primary member may create, update or delete a
record**, while any member may read. Two isolation properties are deliberate and
tested. A record id that belongs to a different household returns **404, not
403**, so the status code cannot be used to discover that a record exists.
`household_id` is taken from the URL path only: it appears in no update schema
and every request schema is `extra="forbid"`, so an attempt to move a record
into another household by sending `household_id` in the body is a 422, not a
silent re-homing.

The honest limits: the header is still asserted, not authenticated, so this stops
accidental and URL-edited cross-household access and not a malicious client; and
there is no per-record visibility control, so every member of a household can
read all of its financial detail (a dependent child sees the household's
liabilities). Household financial data is also never an input to
`POST /api/analysis`, so a wrong household record cannot change any customer's
risk, goal, portfolio or compliance result (`docs/DECISIONS.md` ADR-032).

### Household financial summary (Phase 34)

`GET /api/households/{id}/financial-summary` reuses exactly the same identity
and membership check, with no primary-only restriction because it is read-only:
401 without `X-Customer-Id`, 404 for an unknown household, 403 for a non-member,
200 for any member. Every underlying query is scoped by the path's
`household_id`, so one household's records can never join into another's totals,
and the endpoint accepts no request body at all — there is nothing in which a
caller could smuggle a different `household_id`. A denied response carries none
of the denied household's figures.

The honest limits are unchanged and one is worth restating plainly: the summary
concentrates a household's whole financial position into a single response, and
**any** member can read it — a dependent sees the household's liabilities, net
position and emergency-fund shortfall. There is still no per-record or
per-member visibility control, and the `X-Customer-Id` identity is still
asserted rather than authenticated. Nothing in the summary is persisted and it
exposes no customer id or member detail.

### Household financial metadata (Phase 35)

`notes`, `description` and `interest_rate` travel through exactly the same
routes and authorization as the Phase 33 facts they annotate — no new route,
no new permission. Free text is length-bounded by the schema (500 / 200
characters, rejected with a 422 beyond that), stored through parameterized SQL,
and rendered by React as escaped text; tests store SQL-injection-style and
`<script>`-style strings and confirm they come back verbatim as data, the
tables still exist afterwards, and the page emits them as escaped text rather
than markup. Notes are household-visible: any member can read every note, so
a household should not record anything in a note it would not show every
member.

### Household goals (Phase 36)

Goal routes reuse the identical membership check and ownership scoping as the
Phase 33 records (the same helper functions, not a copy): any member reads,
only the primary writes, a goal id from another household is a 404, and denied
responses carry none of the goal's name, amount or notes. Goal names and notes
are length-bounded and stored as data through parameterized SQL, and React
renders them as escaped text. The new schemas also close two client-error-as-
500 paths for the goal fields — an explicit `null` on a required field, and a
non-finite or out-of-range number are both 422s. The same two paths remain open
on the Phase 33 record schemas and the Phase 28 financial-inputs schema; they are
recorded as known defects rather than fixed outside their phase.

## 7. Authentication

Client-side-only credential check (`frontend/src/lib/prototype-auth.ts`)
against one hard-coded demo credential; a local Create-User flow grants a
session without any backend involvement. No server session, no token, no
password hashing (there is no real password store to hash). `localStorage`
state (`wealthpilot-prototype-authenticated`, `wealthpilot-profile-id`,
`wealthpilot-demo-customer-id`) is fully visible and editable via browser
devtools by design of this being a prototype — the post-login-flow fix
removed the in-app UI control that invited exactly this kind of tampering,
but did not and could not make client-side storage itself tamper-proof
without real server-side sessions (out of this project's current scope).

## 8. Input Validation

Every request body is a Pydantic v2 schema with explicit field
constraints (e.g. `ge=0` for amounts, `gt=-1.0` for rates, `gt=0` for
periods) mirrored between frontend form validation (required/format/
obviously-invalid checks only) and backend schema validation (the actual
enforcement point) — the frontend check is a UX convenience, never the
security boundary.

## 9. Error Handling

RFC 7807 problem+json for every 4xx/5xx response
(`type`/`title`/`status`/`detail`/`instance`) — never a bare 500, never a
Python traceback in a response body. `agents/graph.py::_safe_call`
converts any unexpected node exception into a structured
`processing_failure`, logged server-side, never surfaced to the client as
raw exception text.

## 10. Logging

Structured JSON logging (`config/logging.py`) — no secret value is ever
logged; a request's own body is not logged verbatim where it could
contain a customer's financial figures beyond what operational debugging
genuinely requires.

## 11. AI Security

Gemini/AutoGen never receive a raw, unvalidated instruction to "decide" a
financial outcome — every call receives an already-computed dict and a
structured-output contract. Their output is validated against that dict
before being trusted for anything user-facing.

## 12. Prompt Injection

`agents/explanation.py`'s tests
(`test_prompt_injection_attempt_is_included_only_as_untrusted_context`,
`test_prompt_injection_text_cannot_bypass_numeric_validation`,
`test_end_to_end_prompt_injection_does_not_override_source`) verify that
any customer-supplied free text reaching a prompt is treated as untrusted
context only — it cannot alter a computed number, override validation, or
change which fields get explained.

## 13. Gemini Output Validation

Every structured field Gemini returns is checked against the exact
source value it claims to explain; any mismatch, missing field, timeout,
or API failure produces the templated fallback (`validation_passed:
false`) instead of a silently-accepted, possibly-fabricated number.

## 14. Agent Security

No LangGraph node, AutoGen persona, or Gemini call can write to
`state.compliance_result`, `state.portfolio_result`, or any other
financial-authority field except through its own designated, tested node
function — there is no generic "agent writes arbitrary state" pathway.

## 15. Compliance Enforcement

`enforce_gate` raises on REJECT; nothing in the codebase catches
`ComplianceRejectedError`. This is the structural mechanism preventing
bypass — not a convention a caller could forget to check.

## 16. Data Leakage Protection

See `docs/RULES.md` Rules 8-9 and `docs/DECISIONS.md` ADR-008. Leakage
here means point-in-time correctness of training data, a data-science
security concern distinct from (but documented alongside) traditional
application security.

## 17. Demo Data

No demo persona contains a real email address, phone number, government
ID, or financial account identifier (verified by grep on every new
demo-related file each time the demo population changed). FAR-Trans
transactional data used for a demo persona's risk linkage carries no PII
(`reports/phase2_data_quality_report.md`).

## 18. Sensitive Data

No customer's real financial account numbers, tax identifiers, or
government-issued IDs are collected, stored, or displayed anywhere in
this system — no such field exists on any schema.

## 19. Chain-of-Thought Protection

The `NodeEvent`/SSE data shape (`node`/`status`/`duration_ms`/`summary`/
`model_version`) has no field for a prompt, reasoning trace, or
transcript — this is a structural guarantee (nothing to strip or filter),
not a filtering step that could be bypassed or forgotten. If the pipeline
fails mid-stream, `GET /api/analysis/stream` emits only one fixed frame
(`"Analysis failed"` / `"An unexpected error occurred."`); the exception,
SQL and parameters stay in the server log. This was observed live in
Phase 29, when a hosted-database connection dropped mid-`INSERT` during a
stream capture.

## 20. Security Testing

See `docs/TEST_PLAN.md` §23. No automated secret-scanning CI gate exists
at this time — verification is manual (grep) per phase, performed before
that phase is reported complete.

## 21. Known Prototype Limitations

This is explicitly prototype-grade authentication and authorization, not
production-grade: no server session/token, no real password store, no
per-account data authorization (only per-request data scoping), and
client-side state that a determined user can edit via devtools. These
limitations are disclosed consistently across `docs/DECISIONS.md`
ADR-020, `reports/post_login_profile_flow_report.md` §17, and here —
never claimed away as "production-ready" anywhere in this project's
documentation.
