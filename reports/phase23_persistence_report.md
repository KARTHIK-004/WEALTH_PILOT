# Phase 23 — Persist Questionnaire Answers + Post-Creation Goals

## 1. Phase Objective

Close the two backend persistence gaps Phase 22 discovered and empirically
confirmed: questionnaire answers had no storage mechanism, and a goal
could only be recorded for a customer at the exact moment `POST
/api/profiles` created them, never afterward. Phase 23 adds the minimum
real backend persistence needed for both, and updates the two Phase 22
onboarding pages to use it — while leaving every ML/AI/compliance
component completely untouched.

## 2. Phase 22 Limitation Being Solved

From `reports/phase22_onboarding_report.md` §4/§5: (1) no endpoint existed
to save a questionnaire answer, so `onboarding-questionnaire-page.tsx`
kept answers in local `useState` only, behind a permanent "not saved"
notice; (2) `financial_goals` could only be written via `POST
/api/profiles`'s embedded `goals` field at customer-creation time — with
no endpoint to attach a goal to an already-existing customer, which is
exactly the state a profile is in by the time a user reaches the
onboarding goals step (Create User has already submitted). Both were
empirically demonstrated in Phase 22 via real API calls, not just code
review, and are now closed the same way: with real, empirically-verified
persistence (§18).

## 3. Existing Architecture Inspected

Fresh reads this phase (not assumed from memory): `backend/wealthpilot/
api/schemas.py` (full file), `backend/wealthpilot/api/main.py`,
`backend/wealthpilot/api/routers/profiles.py`, `backend/wealthpilot/db/
models.py` (full file), `backend/wealthpilot/db/base.py`,
`backend/wealthpilot/api/dependencies.py`, `backend/wealthpilot/api/
errors.py`, `backend/wealthpilot/api/services/questionnaire_service.py`,
`backend/alembic/env.py` and the most recent migration
(`5b8f87dbcef1_add_customer_risk_snapshots.py`, for style), `tests/
backend/api/test_profiles.py` and `conftest.py` (fixture patterns),
`frontend/src/lib/api-client.ts`, `frontend/src/types/api.ts`,
`frontend/src/pages/{create-user-page,onboarding-questionnaire-page,
onboarding-goals-page}.tsx`, `frontend/src/components/shell/
{onboarding-steps,onboarding-no-profile}.tsx`, `frontend/src/App.tsx`,
Phase 20's `auth-context.tsx`, Phase 21's `customer-context.tsx` usage.

## 4. Questionnaire Persistence Design

`GET /api/questionnaire` returns stable identifiers already:
`Question.number` (int) and `QuestionOption.key` (a single letter, always
`a`-`e` per `questionnaire_service.py`'s `_OPTION_RE`). Per this phase's
own instruction ("do NOT copy questionnaire text into the database"), the
new table stores **only** `question_number`/`selected_option_key` — never
question or option text; the real text always comes fresh from `GET
/api/questionnaire` (unchanged). A small new pure function,
`questionnaire_service.is_valid_answer(question_number, option_key)`,
re-uses the same cached, parsed questionnaire data to validate a submitted
answer references a real question and a real option of that question —
checked before anything is written.

## 5. New Database Table/Model

`backend/wealthpilot/db/models.py` — one new SQLAlchemy model,
`QuestionnaireAnswer` (table `questionnaire_answers`):

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `customer_id` | Integer, FK → `customers.id` | |
| `question_number` | Integer | matches `Question.number` |
| `selected_option_key` | `String(1)` | matches `QuestionOption.key` |
| `created_at` | `DateTime(timezone=True)`, `server_default=now()` | matches every other table's convention |
| `updated_at` | `DateTime(timezone=True)`, `server_default=now()`, `onupdate=now()` | the one deliberate deviation from convention — no other table has this column, added specifically because this is the first table in this schema with genuine update-in-place semantics (§12); live-verified to change only on an actual update (§18) |

`UniqueConstraint("customer_id", "question_number", name=
"uq_questionnaire_answers_customer_question")` enforces at most one row
per (customer, question) — the same per-natural-key uniqueness pattern
`Transaction`/`MarketData` already use elsewhere in this file, not a new
style. No risk score, category, confidence, ML prediction, portfolio
allocation, recommendation, or financial advice is stored anywhere in this
table — it holds exactly two identifiers per answer.

No new goal table was created — `financial_goals` (Phase 1/21, unchanged)
is reused exactly as-is for the new goal-creation endpoint (§7).

## 6. Migration Details

Revision `8fed3799c0c5` ("add questionnaire_answers"), `down_revision =
'0757912ec0da'` (the prior head, confirmed via `alembic history`/`alembic
current` on both databases before generating anything). Generated with
`alembic revision --autogenerate`; the autogenerate diff detected **only**
the new table (the accompanying "Detected sequence ... assuming SERIAL"
lines are informational noise about pre-existing sequences, not schema
drift) — reviewed and applied unmodified. `upgrade()` creates exactly the
table described in §5 (PK, FK, unique constraint); `downgrade()` drops it
— non-destructive rollback support. Applied via `alembic upgrade head`
(dev `DATABASE_URL`) and `ALEMBIC_TARGET=test alembic upgrade head` (test
`TEST_DATABASE_URL`) — both were at head `0757912ec0da` beforehand,
confirmed at head `8fed3799c0c5` afterward via a direct
`SELECT version_num FROM alembic_version` on each database. No other
table was touched; no existing row was modified or dropped.

## 7. Goal Persistence Design

No second goal table. `POST /api/profiles/{profile_id}/goals` (new)
creates one `FinancialGoal` row using the exact same model Phase 1/21
already defined, and accepts/returns the exact same `GoalCreate`/`GoalOut`
Pydantic schemas `POST /api/profiles`'s embedded-goals path already used —
no new field. `POST /api/profiles`'s own embedded `goals` behavior is
completely untouched (still the exact same code path, still works — §13,
regression-tested).

**No dedicated goals-retrieval endpoint was added.** `GET
/api/profiles/{profile_id}` already returns a customer's full goal list
(`ProfileResponse.goals`, unchanged since Phase 21) — inspected first, per
this phase's own "verify no existing [mechanism] can already represent the
data" instruction, and confirmed sufficient. Adding a second, redundant
`GET /api/profiles/{id}/goals` would have been unnecessary CRUD expansion
(§9's explicit caution); the frontend goals page instead reuses the
existing `useProfileQuery` hook unmodified.

## 8. API Routes Added

All three added to the existing `profiles.py` router (same file as `GET
/api/questionnaire`/`POST /api/profiles`/`GET /api/profiles/{id}` —
inspected first and judged the most consistent location, since these are
all nested under the same `/api/profiles` resource):

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/profiles/{profile_id}/questionnaire` | upsert one or more answers |
| GET | `/api/profiles/{profile_id}/questionnaire` | retrieve this profile's currently persisted answers |
| POST | `/api/profiles/{profile_id}/goals` | create one goal for an existing profile (201) |

No route was added to `main.py` — `profiles.router` was already
registered; no path-ordering conflict exists (each new path has an extra
static segment beyond `/api/profiles/{profile_id}`, so it cannot collide
with that route regardless of registration order, unlike the
already-documented `/api/analysis/stream` vs. `/api/analysis/{id}` case
from Phase 15).

## 9. Request/Response Schemas

Added to `api/schemas.py` (public Pydantic v2 models only, never an
internal `AgentState`/ML structure):

- `QuestionnaireAnswerIn { question_number: int (>0), option_key: str (1 char) }`
- `QuestionnaireAnswersSubmitRequest { answers: list[QuestionnaireAnswerIn] (min 1) }`
- `QuestionnaireAnswerOut { question_number, option_key, updated_at }`
- `QuestionnaireAnswersResponse { customer_id, answers: list[QuestionnaireAnswerOut] }`

Goal creation reuses `GoalCreate` (request) and `GoalOut` (response) —
already defined, no new goal schema. OpenAPI generation was verified live
(`GET /openapi.json` against a running instance listed all three new
paths and every new schema correctly — §18) before regenerating frontend
types.

## 10. Frontend Changes

`frontend/src/types/api.ts` regenerated via the project's existing
`npm run generate-types` command (`openapi-typescript` against a live
`/openapi.json`) — never hand-edited; confirmed the new schemas/operations
appear correctly (§18). `lib/api-client.ts` gained three thin methods
(`getQuestionnaireAnswers`, `submitQuestionnaireAnswers`, `createGoal`),
all typed from the regenerated `Schemas[...]`, no hand-written mirror.
`hooks/use-questionnaire.ts` gained `useQuestionnaireAnswersQuery`/
`useSubmitQuestionnaireAnswers`; a new `hooks/use-create-goal.ts` wraps
the goal endpoint. `pages/onboarding-questionnaire-page.tsx` and `pages/
onboarding-goals-page.tsx` were updated to call these real endpoints
instead of only holding local state (§10/§11 detail below). No other page
was changed; `onboarding-steps.tsx`/`onboarding-no-profile.tsx` are reused
unmodified.

**Questionnaire page**: previously saved answers (`useQuestionnaireAnswersQuery`)
preselect the matching radio buttons on load (once, via a ref-guarded
effect, so a background refetch never clobbers in-progress edits). "Save
& Continue to Goals" submits the current answer set via
`useSubmitQuestionnaireAnswers` and navigates only inside that mutation's
`onSuccess` callback — a failed save shows a real `ErrorState` and does
not advance. If zero questions are answered, nothing is submitted (there
is nothing valid to submit) and the page simply continues, never claiming
a save that didn't happen. The submit button reads "Saving…" and is
disabled while pending, preventing a duplicate submission from a
double-click.

**Goals page**: no more local-only draft list. Each "Add goal" click is
its own real `POST` via `useCreateGoal`; on success the form clears and
the (unmodified) `useProfileQuery` is refetched so the newly-confirmed
goal (with its real backend `id`) appears in the "saved goals" list drawn
from `ProfileResponse.goals`. A failed attempt shows a real `ErrorState`
for that one attempt only — there is no batch/"all goals saved" message
anywhere in this file, since there is no batch operation for such a claim
to be about (§11 detail below). Saved goals have no remove control (Phase
23 deliberately implements CREATE + RETRIEVE only, not DELETE, per its own
§9 instruction).

## 11. Active Profile Handling

Both pages read `useCustomer().profileId` (Phase 17's context,
unmodified) and render the existing `OnboardingNoProfile` empty state
(with links to `/create-user` and `/login`) when it is `null` — unchanged
from Phase 22. No customer id is hard-coded anywhere in this phase's
code (confirmed by grep — §24). Every new hook takes `profileId` as an
explicit parameter and is only enabled/callable when it is non-null.

## 12. Duplicate/Update Behavior

`submit_questionnaire_answers` looks up an existing row by
`(customer_id, question_number)` for each submitted answer: if found, it
updates `selected_option_key` in place (SQLAlchemy's `onupdate=func.now()`
then refreshes `updated_at` automatically on flush); if not found, it
inserts a new row. The `uq_questionnaire_answers_customer_question`
constraint makes a true duplicate impossible even under a race. Live- and
test-verified (§18/§23): re-submitting question 1 with a new option left
exactly 2 rows total (not 3), updated only that row's `updated_at`, and
left question 2's row and `updated_at` completely untouched.

Goal creation has no update/upsert concept — each `POST
/api/profiles/{id}/goals` call always creates one new row (matching a
real financial goal being an additive record, and matching this phase's
explicit "CREATE + RETRIEVE, avoid unnecessary CRUD expansion" scope).

## 13. Cross-Customer Isolation

Every new route filters exclusively by the `profile_id` in the URL path
(`WHERE customer_id = profile_id` in every query; `FinancialGoal`/
`QuestionnaireAnswer` rows are created with that same `customer_id`) — the
backend enforces this through the query itself, not through any
frontend-side filtering. Live-verified this phase (§18) with two real
temporary customers: Customer A's questionnaire answers and goal were
never visible when querying Customer B, and vice versa. Also covered by
an automated test, `test_questionnaire_answers_are_isolated_per_customer`
and `test_goals_created_via_new_endpoint_are_isolated_per_customer`
(§23).

## 14. Error Handling

Every new route continues to use the existing RFC 7807 system unchanged —
`CustomerNotFoundError` (404, already existed, reused as-is) for a
nonexistent profile; a new use of the already-existing `InvalidRequestError`
(400, already existed — no new error class was needed) for an
invalid question number or an option that doesn't belong to the referenced
question; Pydantic's existing `RequestValidationError` handler (422) for a
structurally malformed payload (missing field, empty `answers` list,
non-positive `target_amount`, etc.) — all already produce
`application/problem+json` via the pre-existing, unmodified
`register_exception_handlers`. No stack trace, SQL text, or internal
exception ever appears in any response body (confirmed live — §18).

## 15. Security Considerations

No secret, API key, database URL, or token was added anywhere in this
phase's code (confirmed by grep across every new/modified file). No
authentication mechanism was added or changed — the new routes rely on
the same `profile_id` path parameter and `get_session` dependency every
existing `/api/profiles/*` route already uses; there is still no
backend-verified session concept in this system (unchanged from Phase 20's
disclosed prototype-authentication scope). Data isolation is enforced at
the database-query level (§13), not merely by what the frontend chooses
to display.

## 16. Financial-Calculation Audit

A grep of every new/modified backend and frontend file for
`sharpe`/`volatility`/`monte carlo`/`feasibility`/`future value`/
`inflation`/`contribution gap`/`risk_score =`/similar found matches only
in **pre-existing, unmodified** parts of `schemas.py` (Phase 14/15's
already-existing `GoalSection`/`PortfolioSection`/`ScenarioSummary`
schemas) and `db/models.py` (Phase 10's already-existing `RiskAssessment.
risk_score` column) — none inside any code this phase actually added.
Phase 7's goal-math functions were not opened, imported, or called by any
new code. The only "calculation" anywhere in this phase's new code is
parsing a raw string into the number/date the existing `GoalCreate`
schema already expects — not a derived value.

## 17. ML/AI Boundary Audit

No file under `backend/wealthpilot/{core,agents}` was modified (confirmed
by the same mtime-based file-scope check used every phase this session —
§20/§24). No file under `training/`, `models/`, or `datasets/` was
touched. The Phase 4 risk model, Phase 7 goal engine, Phase 8 portfolio
optimizer, Phase 9 compliance, Phase 11 LangGraph, Phase 12 AutoGen, and
Phase 13 Gemini explanation are byte-for-byte unchanged. Neither new
endpoint calls `POST /api/analysis` or any agent/graph function — a
questionnaire save and a goal save are each a single, isolated database
write and nothing else.

## 18. Live API Verification

Performed against a freshly started local backend (port 8033), with two
real temporary customers:

1. `POST /api/profiles` → Customer A (`customer_id 29094`), Customer B
   (`customer_id 29095`), no embedded goals.
2. `GET /api/questionnaire` → 5 sections; question 2 confirmed as
   "Gender" with real options `a`/`b`.
3. Selected and persisted two real answers for Customer A: `POST
   /api/profiles/29094/questionnaire` with `question_number 1 → "b"` and
   `question_number 2 → "a"` → 200, both echoed back with `updated_at`
   timestamps.
4. `GET /api/profiles/29094/questionnaire` → exactly those two answers,
   unchanged.
5. Re-submitted question 1 with a **different** valid option (`"d"`) →
   200; the response showed question 1's `updated_at` advance to a new
   timestamp while question 2's `updated_at` stayed exactly the original
   value — direct proof of row-level update, not a blind overwrite.
6. A follow-up `GET` confirmed exactly 2 answers total (not 3) — no
   duplicate row was created.
7. Created a real goal for Customer A (`POST
   /api/profiles/29094/goals`) → 201, `id: 2`, every field echoed exactly
   as submitted.
8. `GET /api/profiles/29094` → the goal present in `goals[]`, exact match.
9. Cross-customer isolation: submitted a different answer for Customer B
   (`question 1 → "a"`) — `GET /api/profiles/29095/questionnaire`
   returned only that one answer, never Customer A's; `GET
   /api/profiles/29095` returned `"goals": []`, never Customer A's goal.
10. Live-verified four RFC 7807 error paths: invalid `question_number`
    (400, "Invalid request"), option not belonging to the question (400,
    "Invalid request"), nonexistent customer (404, "Customer not found"),
    and an invalid goal amount (422, "Validation error") — all
    `application/problem+json`, no stack trace or SQL text in any body.

Data matched submitted values exactly in every case above.

## 19. Frontend Verification

No headless-browser tool is available in this environment — **not
verified — reason: no browser tool available.** No click-through of
Create User → Questionnaire → Save → Goals → Save → Dashboard was
performed, and no such claim is made. Verified instead through: real API
calls against a running backend (§18, exercising the exact payload shapes
the new hooks send), route-level source inspection (both pages'
`handleContinue`/`handleAddGoal` logic traced by hand against the live
API responses above), `tsc -b` (0 errors), `vite build` (succeeds), and
the full backend regression suite (§24).

## 20. Database Cleanup Verification

All test data created in §18 was deleted directly from the (dev)
database after verification: `DELETE FROM questionnaire_answers WHERE
customer_id IN (29094, 29095)` (3 rows), `DELETE FROM financial_goals
WHERE customer_id IN (29094, 29095)` (1 row), `DELETE FROM customers
WHERE id IN (29094, 29095)` (2 rows). A follow-up `SELECT count(*)` on
all three tables scoped to those ids returned **0** for each. No
pre-existing data was touched (both customer ids were freshly assigned by
the database during this verification run). The test-only backend server
process was stopped afterward.

## 21. TypeScript Result

`npx tsc -b` — **0 errors**, re-run after every frontend file change this
phase (including after the API-types regeneration).

## 22. Build Result

`npx vite build` — succeeds. Output grew from 952.60 kB (Phase 22) to
953.90 kB (gzip 292.85 kB) — still a single JS chunk (the pre-existing,
previously-documented no-code-splitting finding, unchanged in kind).

## 23. Lint Result

`npx oxlint` — **0 errors**, 8 warnings — identical set to Phase 22 (all
pre-existing `only-export-components`/`set-state-in-effect` advisories;
no new warning was introduced by this phase's changes).

## 24. Backend Regression Result

Full `pytest` suite: **713 passed, 3 skipped, 0 failed** (689.49s).
16 new tests were added to `tests/backend/api/test_profiles.py` this
phase (questionnaire create/retrieve/update/duplicate-prevention/invalid-
question/invalid-option/nonexistent-customer/isolation/empty-submission,
and goals create/retrieve/nonexistent-customer/invalid-amount/missing-
field/isolation/embedded-goals-regression) — 697 (prior baseline) + 16 =
713, confirming every pre-existing test still passes unmodified and
nothing was deleted or weakened. The 3 skips are the same
pre-existing, timing-dependent Gemini-daily-quota effect already
documented in `reports/phase20_login_report.md` §15 (this phase touched
no Gemini-related code).

## 25. Known Limitations

- **No update/delete endpoint for a goal** — by this phase's own explicit
  scope ("CREATE + RETRIEVE... avoid unnecessary CRUD expansion"), a goal
  cannot be edited or removed once saved through the onboarding UI. A
  future phase would need to add that deliberately.
- **`updated_at` exists only on `questionnaire_answers`**, a deliberate,
  documented deviation from every other table's column set (§5) — not an
  inconsistency introduced by accident.
- **No interactive browser verification was performed** (§19) — no
  headless-browser tool is available in this environment; everything
  claimed above was verified via real API calls, source review, and
  automated tests only.
- **No frontend automated test runner exists in this repository**
  (pre-existing, not introduced or resolved by this phase).
- The single ~954 kB JS bundle / no-code-splitting finding is unchanged in
  kind from Phase 20-22, only marginally larger in size.
- Questionnaire answers, once saved, still have no connection to the
  Phase 4 risk model or any recommendation logic — by design (§9/§17 of
  this phase's own brief) — they remain pure user input, not a model
  feature.

## 26. Phase 24 Statement

**Phase 24 was NOT started.** No demo data, customer switching, demo
customer population, advanced dashboard redesign, presentation polish,
chart redesign, production/JWT/OAuth authentication, new ML model,
questionnaire-based risk model, or recommendation/portfolio change was
made. This report and its accompanying code/schema/migration changes are
the complete, final deliverable of Phase 23.
