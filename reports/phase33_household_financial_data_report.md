# Phase 33 — Household Financial Data Foundation

Completion report. Historical record: this file describes Phase 33 as it was
implemented and verified, and is not rewritten by later phases.

---

## 1. Objective

Extend the Phase 32 household foundation so that a household can store its
**own** financial information — income, expenses, assets and liabilities —
instead of only identity and membership.

This is a **data foundation only**. Phase 33 gives the household somewhere to
record what the family actually has and owes, and stops there. It deliberately
does not interpret, combine, total or act on any of it.

---

## 2. Scope

**In scope (implemented):**

- Four new database tables for household income, expenses, assets and
  liabilities, plus the Alembic migration, applied to the dev and test
  databases.
- Pydantic v2 request/response schemas for all four resources.
- A service layer and a router giving each resource list / create / update /
  delete, reusing the Phase 32 authorization model unchanged.
- Frontend display and management of those records on the existing Customer
  Profile Household card.
- Database-level and API-level tests, isolation/mutation verification, a
  rollback-safe live check against the real demo personas, and a source-level
  render check of the resulting UI.
- Documentation updates, including a new ADR.

**Explicitly out of scope and NOT implemented** (per the phase instruction):

- Any household financial calculation whatsoever — no total, sum, net worth,
  savings rate, debt-to-income ratio, surplus, per-member split, coverage or
  projection.
- Any summary / totals / net-worth / savings / debt-ratio endpoint or screen.
- Any change to the individual financial-input system, the recommendation
  pipeline, risk modelling, goal feasibility, emergency-fund calculation,
  portfolio optimization, compliance logic, Gemini logic, LangGraph routing,
  AutoGen, or any ML model.
- Any bank, payment, investment-account or other external financial API
  integration. **None was added, and no such library, credential, client or
  configuration key exists in this phase's changes.**
- Any customer-switching UI, any frontend financial calculation, any
  client-supplied `household_id`, any change to authentication.

---

## 3. Files Changed

**Created (8):**

| File | Purpose |
| --- | --- |
| `backend/alembic/versions/d2be70d8b07f_add_household_financial_data_tables.py` | Migration: the four new tables and their indexes |
| `backend/wealthpilot/api/routers/household_finances.py` | 16 routes (4 resources x list/create/update/delete) |
| `backend/wealthpilot/api/services/household_finance_service.py` | Ownership-scoped CRUD orchestration; no arithmetic |
| `tests/backend/db/test_household_finance_models.py` | 39 schema/constraint tests against real PostgreSQL |
| `tests/backend/api/test_household_finances.py` | 110 API tests (CRUD, validation, authorization, isolation, regression) |
| `frontend/src/hooks/use-household-finances.ts` | TanStack Query hooks for the four resources |
| `frontend/src/components/profile/household-finance-section.tsx` | Config-driven table + dialog for one resource |
| `reports/phase33_household_financial_data_report.md` | This report |

**Modified (19):**

Backend — `backend/wealthpilot/db/models.py` (four models + four vocabulary
tuples appended; nothing existing altered), `backend/wealthpilot/api/schemas.py`
(12 schemas, 4 `Literal` types, one blank-string validator appended),
`backend/wealthpilot/api/errors.py` (one new 404 error class),
`backend/wealthpilot/api/services/household_service.py` (two additive helpers,
`require_member` / `require_primary_member`, refactored out of the existing
Phase 32 checks — behaviour unchanged),
`backend/wealthpilot/api/main.py` (router registration: one import, one line).

Frontend — `frontend/src/types/api.ts` (**regenerated** from `app.openapi()`,
never hand-edited: +990 lines, -0), `frontend/src/lib/api-client.ts` (16 new
methods), `frontend/src/components/profile/household-card.tsx` (tabs added
around the existing member table; the Phase 32 content itself is unchanged).

Documentation — `docs/DECISIONS.md` (ADR-032, appended), `docs/RULES.md`
(Rule 32 added; Rule 31's closing bullet now points forward instead of saying
"until a later phase"), `docs/ARCHITECTURE.md`, `docs/DESIGN.md` (§27),
`docs/PRD.md` (§14.17, §37, §38, §40), `docs/SECURITY.md`,
`docs/TEST_PLAN.md`, `docs/MEMORY.md`, `CLAUDE.md` (§14),
`.claude/rules/backend.md`, `TASKS.md`.

No other file in the repository was touched. No file was deleted.

---

## 4. Database Schema

Four independent tables, each owned by a household through `household_id`
alone. **None of them has a `customer_id` column** — a record belongs to the
household, not to the member who entered it (asserted by a test). Money is
`Numeric(14, 2)`, matching every other money column in the schema.

**`household_incomes`** — `id`, `household_id` (FK to `households.id`,
`ON DELETE CASCADE`, indexed), `source` `String(100)`, `amount`
`Numeric(14,2)`, `frequency` `String(20)`, `is_active`
`Boolean NOT NULL DEFAULT true`, `created_at`, `updated_at`. CHECKs: frequency
in vocabulary; `amount > 0`; `source` not blank.

**`household_expenses`** — `id`, `household_id`, `category` `String(30)`,
`description` `String(200)` **nullable**, `amount` `Numeric(14,2)`, `frequency`
`String(20)`, `is_essential` `Boolean NOT NULL` (**no default**), `is_active`
`Boolean NOT NULL DEFAULT true`, timestamps. CHECKs: category and frequency in
vocabulary; `amount > 0`.

**`household_assets`** — `id`, `household_id`, `name` `String(100)`,
`asset_type` `String(30)`, `current_value` `Numeric(14,2)`, `is_liquid`
`Boolean NOT NULL`, timestamps. CHECKs: asset type in vocabulary;
`current_value >= 0`; `name` not blank.

**`household_liabilities`** — `id`, `household_id`, `name` `String(100)`,
`liability_type` `String(30)`, `outstanding_amount` `Numeric(14,2)`,
`monthly_payment` `Numeric(14,2)` **nullable**, timestamps. CHECKs: liability
type in vocabulary; `outstanding_amount >= 0`;
`monthly_payment IS NULL OR monthly_payment >= 0`; `name` not blank.

Deliberate modelling decisions:

- **Nullable `monthly_payment`** — "not provided" and "no monthly payment" are
  different facts, and NULL is never stored as 0.
- **`is_essential` has no default** — whether an expense is essential is the
  household's own judgement and is never guessed.
- **Income `source` is free text** — an income source is the household's own
  description; a fixed vocabulary would force a household to misfile its
  income. Frequency, expense category, asset type and liability type *are*
  controlled vocabularies (CHECK constraint + mirrored Pydantic `Literal`, with
  a test asserting the two never drift).
- **Where zero is legal** — income and expense `amount` must be `> 0` (a
  zero-amount income is a data-entry error); `current_value` and
  `outstanding_amount` allow `>= 0` (a repaid loan or an emptied account is a
  real zero).
- **No derived column anywhere**, and no table references any other financial
  table. The existing `customers`, `financial_inputs`, `households` and
  `household_members` tables are unmodified.

---

## 5. Migration ID

`d2be70d8b07f` — `add household financial data tables`, revising
`f59ab6395383` (Phase 32). It contains only the four `create_table` calls and
the four `household_id` indexes; it alters no existing table.

Applied to **both** databases — `DATABASE_URL` (dev) and, via
`ALEMBIC_TARGET=test`, `TEST_DATABASE_URL`. Both report head `d2be70d8b07f`.

---

## 6. API Endpoints

16 new routes, 8 new paths, all under an existing household:

| Method | Path |
| --- | --- |
| `GET` / `POST` | `/api/households/{household_id}/income` |
| `PUT` / `DELETE` | `/api/households/{household_id}/income/{income_id}` |
| `GET` / `POST` | `/api/households/{household_id}/expenses` |
| `PUT` / `DELETE` | `/api/households/{household_id}/expenses/{expense_id}` |
| `GET` / `POST` | `/api/households/{household_id}/assets` |
| `PUT` / `DELETE` | `/api/households/{household_id}/assets/{asset_id}` |
| `GET` / `POST` | `/api/households/{household_id}/liabilities` |
| `PUT` / `DELETE` | `/api/households/{household_id}/liabilities/{liability_id}` |

`POST` returns 201, `DELETE` returns 204, `PUT` is a **partial merge**
(`exclude_unset` — the same semantics `FinancialInputsUpdate` already uses: an
omitted field keeps its stored value). Every error is RFC 7807 problem+json.

There is **no summary, totals, net-worth, savings or debt-ratio route**. A test
asserts that no path in the generated OpenAPI document contains any of those
words, so one cannot be added unnoticed.

---

## 7. Authorization Behavior

Identical to Phase 32, reused rather than reimplemented — the caller's
associated customer travels in the `X-Customer-Id` header
(`api/dependencies.py::get_acting_customer_id`) and is authorized against
household membership.

| Situation | Result |
| --- | --- |
| No / malformed `X-Customer-Id` | **401** |
| Unknown household | **404** |
| Caller is not a member of that household | **403**, with no data from the denied household in the body |
| Caller is a member (any role), reading | **200** |
| Caller is a member but not the primary, mutating | **403** |
| Caller is the primary, mutating | **200 / 201 / 204** |
| Record id that belongs to a different household | **404**, never 403 |
| `household_id` sent in a request body | **422** |

Two of those are deliberate design choices, not accidents:

- A record id from another household returns **404 rather than 403** so the
  status code cannot be used to learn that the record exists — the same
  convention Phase 32 chose for `remove_member`.
- **`household_id` is server-controlled.** It is read from the URL path only,
  appears in no update schema, and every request schema is
  `model_config = ConfigDict(extra="forbid")`, so an attempt to move a record
  into another household by sending `household_id` in the body is rejected as a
  422 rather than silently honoured.

**On authentication, stated plainly and unchanged from Phase 32: the header is
asserted, not authenticated.** The prototype has no server session or token, so
a client that sends another customer's id receives that customer's view,
exactly as it can on every `profile_id` route. This stops accidental and
URL-edited cross-household access; it does not stop a malicious client. Phase
33 adds no authentication and makes no claim to have any (`docs/SECURITY.md`,
ADR-020).

---

## 8. Validation Rules

Enforced in the API schema **and** again by a database CHECK constraint
(defence in depth — a direct database write cannot bypass the API's rules).

Common to all four resources: unknown fields → 422 (`extra="forbid"`); strings
are length-bounded and may not be blank or whitespace-only; a controlled
vocabulary value outside its list → 422; `PUT` with `{}` is a valid no-op merge.

| Resource | Rules |
| --- | --- |
| Income | `source` required, 1–100 chars, free text; `amount > 0`; `frequency` in {monthly, yearly, one_time}; `is_active` defaults true |
| Expenses | `category` in {housing, food, utilities, transportation, education, healthcare, insurance, debt_payment, childcare, entertainment, other}; `description` optional, <= 200 chars, `null` when not provided; `amount > 0`; `frequency` as above; `is_essential` **required, no default**; `is_active` defaults true |
| Assets | `name` required, <= 100 chars; `asset_type` in {cash, bank_account, fixed_deposit, investment, real_estate, vehicle, retirement, other}; `current_value >= 0`; `is_liquid` required |
| Liabilities | `name` required, <= 100 chars; `liability_type` in {mortgage, personal_loan, education_loan, vehicle_loan, credit_card, other}; `outstanding_amount >= 0`; `monthly_payment` optional, `>= 0` when given, **stays `null` when omitted** |

**NULL is not zero**, throughout: an omitted optional value is stored and
returned as `null`, never coerced to `0`; a stated `0` is stored and returned
as `0`. Both were verified end-to-end against the live database in the same
request cycle (§11).

---

## 9. Frontend Changes

The existing Customer Profile → Household card is unchanged in its Phase 32
content. Behind the existing "View Household" toggle there is now a `Tabs`
control (`aria-label="Household sections"`): **Members** (the Phase 32 table,
untouched) followed by **Income**, **Expenses**, **Assets**, **Liabilities**.

All four financial tabs render one config-driven component,
`components/profile/household-finance-section.tsx`, over
`hooks/use-household-finances.ts` and 16 new typed `lib/api-client.ts` methods:

- Each tab opens with a muted line stating what is *not* happening — for
  example "No total is calculated", "No debt ratio, schedule or interest is
  calculated".
- Tables show only the record's own stored columns. There is no totals row, no
  summary, no chart and no derived figure.
- **The primary member** gets an "Add ..." button and per-row Edit and Delete
  buttons whose accessible names include the record ("Edit Home loan"); Delete
  is a two-step Confirm / Cancel, matching the member table. Add and Edit share
  one `Dialog` described as "Stored for the household exactly as entered.
  Nothing is calculated from it."
- **Every other member** gets the same tables read-only, with no Actions column
  and the line "Only the household's primary member can add, edit or delete
  financial records."
- Loading → `LoadingState`; failure → `ErrorState` showing the RFC 7807
  problem's own title and detail with a retry (never a stack trace); empty → a
  plain sentence, never an implied zero.
- A `null` renders as "**Not provided**"; a stored `0` renders as a formatted
  zero. `is_essential` and `is_liquid` start **unselected** in the form,
  because they are the household's judgement.

**There is zero financial arithmetic in Phase 33 frontend code.** The only
number handling in the component is display formatting of a value the API
returned (`formatCurrency`) and parsing a typed field back to a number on
submit. `types/api.ts` was regenerated from `app.openapi()` and verified
byte-identical to a fresh generation; it was not hand-edited. No new library
was added, no shadcn primitive was hand-written, and no customer-switching UI
was introduced.

---

## 10. Tests

New: **149 tests, all passing.**

- `tests/backend/db/test_household_finance_models.py` — **39 tests**, 293s.
  Each table's exact column set asserted *whole* (so a derived or aggregate
  column cannot be added unnoticed, and no table has a `customer_id`);
  `Numeric(14, 2)` precision; which columns are nullable (only `description`
  and `monthly_payment`); `is_active`'s database default; the indexed,
  cascading `household_id` foreign key; round-trip and delete-cascade
  behaviour; every sign CHECK; every vocabulary value accepted and an
  out-of-vocabulary value rejected; Python ↔ API `Literal` ↔ CHECK-constraint
  agreement; and the Phase 32 tables unchanged. Expected violations are
  provoked inside a `begin_nested()` SAVEPOINT so a failed write does not
  discard the test's own setup rows.
- `tests/backend/api/test_household_finances.py` — **110 tests**, 1452s
  (24:12). Table-driven across all four resources: full CRUD; per-resource
  specifics (free-text income source, optional description, defaultless
  `is_essential`, `monthly_payment` null-vs-zero); the validation matrix;
  partial-update merge semantics; the full authorization matrix of §7; the
  OpenAPI route set including the "no aggregate route" assertion; a schema
  check that no household financial response model carries a derived field;
  and the regression guards of §12.

Full regression suite: see §13.

---

## 11. Security and Isolation Validation

**Mutation testing** — the isolation tests were proven to actually bite, not
merely pass:

- Removing the household scope from the record lookup (so a record id alone
  would resolve) → **4 tests failed**.
- Removing the primary-role check from mutations → **8 tests failed**.

Both mutations were reverted and the files verified byte-identical to their
pre-mutation state afterwards.

**Live check against the real dev database** (`TestClient(app)` in-process, no
server started, everything inside one outer transaction that was **rolled
back**): **37/37 checks passed**. It exercised the real demo personas — 29098
as primary, 29099 as a member, 29100 as an outsider — and confirmed
create/read/update/delete, that a member and the primary read identical lists,
that a non-member gets 403 with no leaked data, that a non-primary member
cannot create, that a record id from another household is 404, that a missing
header is 401, that `household_id` in a body is 422, that an omitted
`monthly_payment` stayed `null` while a stated `0` outstanding stayed `0`, and
that no aggregate route exists. Row counts for all eight touched tables were
identical before and after, so the demo personas were left exactly as they
were.

**Frontend render check** (source-level server-side render of the real page
with the real captured API responses; **not a browser**): **52/52 checks
passed** — the Phase 32 summary intact, five tab triggers, each resource's
headers and stored values rendered as returned, primary-vs-member controls,
empty / loading / RFC 7807 error states, `null` rendered as "Not provided"
while a stated `0` renders as zero, every button has an accessible name,
exactly one `<h1>`, no totals or customer-switcher wording, and no
`undefined`/`NaN` leaks. A profile with no household still shows "No household
created yet." and no financial UI.

**No secret** was printed, logged or committed at any point in this phase, and
nothing in the new code logs a request body.

---

## 12. Regression Validation

- All four demo personas' `POST /api/analysis` responses are **byte-identical**
  before and after household financial data exists — including their analysis
  ids, so the analysis cache key is unchanged too (29096
  `pending_information`/168, 29098 `approved`/165, 29099 `approved`
  savings-first/166, 29100 `rejected`/167).
- The individual `financial_inputs` endpoints return unchanged values (29098
  `current_liquid_assets` 40000, 29099 4000).
- No file under `core/`, `agents/`, `training/`, `models/` or
  `config/compliance_rules.yaml` was modified. No model was retrained or
  re-saved. Compliance rules, precedence and the fail-closed gate are
  untouched.
- The household financial tables are read by nothing outside
  `household_finance_service.py`; no LangGraph node, agent, Gemini prompt or
  compliance rule references them.

---

## 13. TypeScript, Lint and Build Results

- `npx tsc -b` — **0 errors**.
- `npx oxlint` — **0 errors, 8 warnings**, exactly the pre-existing baseline
  (shadcn primitives / provider files). Phase 33 introduced no new warning: an
  intermediate version did (a `react(only-export-components)` warning from
  exporting a constant beside components), and it was fixed by moving the
  constant to its only consumer before completion.
- `npm run build` — succeeds. 3,007 modules; JS 1,082.16 kB (gzip 324.79 kB),
  CSS 97.80 kB. The single-chunk size is the known, accepted characteristic
  documented in `docs/TEST_PLAN.md` §18.
- `frontend/src/types/api.ts` regenerated from `app.openapi()` (no server
  started) and verified byte-identical to a fresh generation.
- Backend regression suite: **not completed during Phase 33.** Two attempts to
  run `pytest tests/ -v` to completion were each killed by the development
  session ending — the first partway through, the second at 44%. Neither
  produced a summary line, and no clean full run is claimed. The phase-scoped
  suites *were* run to completion in isolation and passed (39 database tests,
  110 API tests). The consequence is recorded in §16: a pre-existing Phase 32
  guard that Phase 33 should have updated was left failing, and was only found
  in Phase 34. The full regression suite is being completed as part of Phase
  34's validation (`reports/phase34_household_financial_aggregation_report.md`
  §15).

---

## 14. Documentation Changes

- `docs/DECISIONS.md` — **ADR-032** added: household financial data is stored
  source data only, never aggregated. No existing ADR's substance was edited.
- `docs/RULES.md` — **Rule 32** added; Rule 31's final bullet now points
  forward to it rather than saying "until a later phase adds them".
- `docs/ARCHITECTURE.md` — §4 (the finance tabs), §6 (the router and the
  absence of any summary route), §7 (ER diagram + the four tables), §23 (a new
  limitation).
- `docs/DESIGN.md` — new §27, Household Financial Records (the former §27,
  Demo Experience, became §28; nothing references it by number).
- `docs/PRD.md` — new §14.17; §37 (out of scope) now says plainly that
  aggregation is still out; §38 and §40 updated.
- `docs/SECURITY.md` — a Phase 33 subsection covering the 404-not-403 record
  rule, the server-controlled `household_id`, and the honest limits (asserted
  header, no per-record visibility control).
- `docs/TEST_PLAN.md` — §3 and §4 describe the 39 and 110 new tests and the two
  mutation checks.
- `docs/MEMORY.md` — current phase, backend/frontend/database/API state, test
  and build status.
- `CLAUDE.md` §14, `.claude/rules/backend.md`, `TASKS.md` — updated.

---

## 15. Known Limitations

- **No aggregation exists, by design.** A household cannot see its own total
  income, net worth, savings rate or debt ratio, because computing one requires
  a methodology decision this project has not specified. That is the phase's
  stated boundary, not an oversight.
- **Any member can read all of the household's financial detail.** There is no
  per-record or per-member visibility control, so a dependent sees the
  household's liabilities.
- **The `X-Customer-Id` identity is asserted, not authenticated** — unchanged
  prototype scope (ADR-020).
- **No currency field.** Every amount is assumed to be in the single display
  currency the rest of the prototype uses.
- **No household deletion route** still (Phase 32's decision); deleting a
  household would cascade to its financial records if one were ever added.
- **No audit trail** of which member entered or last changed a record — the
  tables carry timestamps but no actor.
- **No browser-based visual or interactive testing was performed**, because no
  headless-browser tool exists in this environment. Frontend verification was
  `tsc` / `oxlint` / `vite build` plus a source-level server-side render of the
  real page against real captured API responses. That is not a browser test and
  is not claimed to be one.

---

## 16. Unexpected Findings

- **A Phase 32 guard was left failing by this phase** —
  `tests/backend/api/test_households.py::test_openapi_lists_exactly_the_household_routes`
  asserts an *exact* inventory of household routes, and Phase 33 added eight
  paths without updating it. It was not caught here because neither attempt at
  the full regression suite reached it (the test sits at 42%; the runs died at
  44% and earlier). It was found and corrected during Phase 34. This entry was
  added to this report after the fact rather than the report being rewritten to
  look clean: the phase-scoped suites passed, but the claim that the wider suite
  was unaffected had not been verified when this report was first written.
- **The Phase 32 household code otherwise needed no correction**; the two
  helpers added to `household_service.py` are refactors of checks that already
  existed, with unchanged behaviour.
- The Phase 32 `remove_member` convention of returning 404 (not 403) for a
  member id belonging to another household turned out to be exactly the right
  precedent for record ids, so Phase 33 followed it rather than inventing a
  second convention.
- The hosted database was slow again during this phase, as in Phase 32. The
  long API test file takes ~24 minutes on its own; the full suite was therefore
  launched as a detached process so that a session interruption could not
  truncate it.
- One scratch-only issue, worth recording because it cost a re-run: the
  source-level render harness first reported 38 failures purely because its
  text anchor spanned a newline while the project's files use CRLF endings, so
  the harness could not flip the card's initial state. The harness was made
  line-ending agnostic and then reported 52/52. **No project file was involved
  in or changed by this**; it was a defect in a throwaway verification script.

---

## 17. Git Status

**Nothing was committed.** The repository still has zero commits on `master`
(`git log` reports "your current branch 'master' does not have any commits
yet"), so `git status --short` lists every top-level directory as untracked —
exactly as it did before this phase. `git status --short --untracked-files=all`
reports 357 untracked files.

No file was deleted, reset, stashed or reverted; no unrelated user work was
touched; no `.gitignore` change was made to tidy the status. All scratch
verification scripts, captured fixtures and test output live outside the
repository, in the session scratchpad directory.

---

## 18. Explicit Statement — No Household Calculations Were Added

**Phase 33 added no household financial calculation of any kind.**

No total, sum, average, net worth, savings rate, savings capacity,
debt-to-income ratio, expense ratio, surplus, deficit, coverage, per-member
split, projection, forecast or score is computed anywhere from household
financial data — not in the database (no computed column, view or aggregate
query), not in `household_finance_service.py`, not in a route handler, not in a
response schema, not in a React component, and not in a Gemini prompt. No
summary endpoint and no summary screen exists, and a test asserts that no such
route path exists.

Household financial data is also never an input to anything: `POST
/api/analysis`, the individual `financial_inputs` contract, risk
classification, behaviour detection, goal feasibility, the emergency-fund
evaluation, portfolio construction, the compliance gate and the recommendation
engine neither read nor are affected by these tables — verified by comparing
every demo persona's full analysis response before and after the data exists.

Adding any such figure in a later phase requires its methodology to be
specified first and then implemented as deterministic logic in `core/` with its
own tests, exactly as the individual engine was built (`docs/DECISIONS.md`
ADR-032, `docs/RULES.md` Rule 32).

---

**Phase 33's implementation is complete.** Its full-suite verification was not
completed within the phase (see §13/§16) and was carried into Phase 34.
