# Phase 36 — Household Goals & Emergency-Fund Planning

Completion report. Historical record: this file describes Phase 36 as it was
implemented and verified, and is not rewritten by later phases.

---

## 1. Objective

Give a household its own financial goals — stored, validated, isolated and
manageable — separate from individual goals, integrated with the existing
household financial summary without creating a second emergency-fund formula.

## 2. Existing Architecture Reused

- **Household ownership and authorization**: Phase 32's membership checks and
  Phase 33's ownership-scoped helpers (`_list_rows`, `_create_row`,
  `_owned_row`, `_update_row`, `_delete_row`), imported and reused — the same
  single implementation of "scoped by both ids; a record of another household is
  a 404", not a copy.
- **Conventions**: `household_id`-only ownership with no `customer_id`;
  controlled vocabularies as CHECK constraints mirrored by Pydantic `Literal`s;
  `Numeric(14, 2)` money; nullable-means-not-provided; `is_active`;
  `extra="forbid"` request schemas; partial-merge `PUT`.
- **The individual goal model** as the reference for field semantics.
- **The Phase 34 summary** as the single source of the emergency-fund
  requirement.
- **Frontend**: the config-driven `HouseholdFinanceSection` (table, dialogs,
  two-step delete, loading/error/empty states, primary-only controls) — goals
  are a fifth resource in it, not a new component system.

## 3. `household_goals` Schema

| Column | Type | Rule |
| --- | --- | --- |
| `id` | Integer PK | |
| `household_id` | FK → `households.id`, `ON DELETE CASCADE`, indexed | required |
| `name` | `String(100)` | required, not blank |
| `goal_type` | `String(30)` | CHECK in (emergency_fund, house, education, retirement, travel, major_purchase, other) |
| `target_amount` | `Numeric(14, 2)` | CHECK `> 0` |
| `current_savings` | `Numeric(14, 2)` | **nullable**; CHECK `IS NULL OR >= 0` |
| `target_date` | `Date` | required |
| `notes` | `String(500)` | nullable |
| `is_active` | `Boolean` | default `true` |
| `created_at`, `updated_at` | timestamptz | |

No `customer_id`, and **no derived column**: no inflation-adjusted target,
required contribution, contribution gap, probability, feasibility, priority or
emergency-fund requirement.

## 4. Migration ID

`c3e8f2a9d154` — `add household goals`, revising `a7c41e9b6f30` (Phase 35).
Creates only `household_goals` and its `household_id` index.

- Applied to the **development** database and the **test** database
  (`a7c41e9b6f30 -> c3e8f2a9d154`); `alembic current` on both:
  `c3e8f2a9d154 (head)`; `alembic heads`: one head.
- `alembic check` on both: **"No new upgrade operations detected."**
- Row counts on all pre-existing relevant tables compared before and after on
  both databases: **unchanged**.
- `test_migration_history.py` (database-free) proves one linear head, that this
  migration creates only `household_goals`, that its downgrade drops exactly
  what it created, and that no household migration operates on
  `financial_goals`.

## 5. API Routes

| Method | Path | Result |
| --- | --- | --- |
| `GET` | `/api/households/{household_id}/goals` | 200, list in `id` order |
| `POST` | `/api/households/{household_id}/goals` | 201 |
| `GET` | `/api/households/{household_id}/goals/{goal_id}` | 200 |
| `PUT` | `/api/households/{household_id}/goals/{goal_id}` | 200, partial merge |
| `DELETE` | `/api/households/{household_id}/goals/{goal_id}` | 204 |

Pydantic `HouseholdGoalCreate` / `Update` / `Response`; RFC 7807 for every
error. OpenAPI now has **29 paths**; the exact household route inventory test
was updated in the same change (the lesson of Phase 33's stale inventory), and
the individual `POST /api/profiles/{id}/goals` is untouched.

## 6. Authorization

Phase 32/33's model, reused — no new role system, no new permission:

| Caller | Read (list / get) | Create / update / delete |
| --- | --- | --- |
| Primary | 200 | 201 / 200 / 204 |
| Member | 200 | **403** |
| Dependent | 200 | **403** |
| Non-member | **403** | **403** |
| Missing / malformed `X-Customer-Id` | **401** | **401** |
| Unknown household | **404** | **404** |
| Goal id from another household | **404** | **404** |

`household_id` comes from the path only; sending it in a body is a 422. The
header is asserted, not authenticated (`docs/SECURITY.md`).

## 7. Goal Semantics

Each field was compared against the individual goal before choosing (ADR-035):

- **Mirrored:** `target_amount > 0` and a required `target_date`.
- **`current_savings` — same name, deliberately nullable.** The individual
  column defaults to `0`, which predates CLAUDE.md §12; here "not provided"
  stays `null`, and a recorded `0` stays `0`.
- **`goal_type` is a controlled vocabulary** because individual goal types are
  free text and no canonical vocabulary exists to reuse; `name` is the
  household's own label.
- **No `inflation_adjusted` flag.** The individual model has none — inflation is
  always applied through `GoalAssumptions.annual_inflation_rate`, which has no
  default. A boolean would be a new financial assumption.
- **No `priority`.** The individual goal's integer is carried as data but never
  used in any calculation; mirroring it would add ordering semantics the phase
  forbids. Goals are listed in `id` order — no ranking, no "best goal".
- **`is_active`** stores and toggles; inactive goals are kept and listed. No
  temporal redesign.
- **Dates:** any valid calendar date, mirroring the individual goal API.
  `core/goals.py::validate_goal_for_creation` (future dates only) is not applied
  by either API — an existing gap, recorded rather than closed for one side.
- **Validation hardening:** an explicit `null` on a required field in a `PUT` is
  a 422, and every number is finite and within its column's storage limit — both
  would otherwise surface as a database 500.

## 8. Emergency-Fund Integration

One source of truth, preserved. An `emergency_fund` goal's `target_amount` is
the **household's own stated target** — a stored input. The **calculated**
requirement (`EMERGENCY_FUND_TARGET_MONTHS` × recurring essential expenses)
remains exactly where Phase 34 put it, in the financial summary, and is not
computed or stored anywhere else. The goals tab shows the summary's calculated
figure beside the goals for reference, labelled as calculated and stating that a
goal's target does not change it — a displayed API value, not arithmetic.

Verified: creating an `emergency_fund` goal (and any other goal) leaves the
**whole financial-summary response byte-identical**; the summary's emergency
fund still agrees with `core/goals.py::assess_emergency_fund` for the same
inputs.

## 9. `core/goals.py` Reuse

**`core/goals.py` is unchanged**, and no goal math is run for household goals.
The engine can only produce an inflation-adjusted target, required
contribution, contribution gap, Monte Carlo probability or feasibility from a
`GoalAssumptions` (explicit return and inflation rates with no default, a
contribution amount), a current date and a historical return series. A
household has none of these; ADR-033 forbade deriving a contribution from cash
flow; and the household engine may not read the clock. Exposing results "only
when all required inputs are genuinely available" therefore means exposing
none. The UI says so plainly. Household goal math becomes possible only once
households have explicit, user-supplied assumptions — a separate decision with
its own persistence and ADR.

## 10. Frontend Changes

- A sixth tab, **Goals**, on the household card, using the existing
  config-driven table and dialog: Name, Goal type, Target amount, Current
  amount, Target date, Active, Notes; add, edit (two-step delete) for the primary
  only; loading, empty, RFC 7807 error and validation states inherited.
- A new `date` field kind (native date input; ISO string sent unchanged).
- `HouseholdGoalsEmergencyFundReference`: one muted line above the goals table
  restating the summary's calculated requirement.
- A factual note: "No projection, required contribution or feasibility is
  calculated — the household's return, inflation and contribution assumptions
  are not recorded."
- Four `api-client.ts` methods; `goals` added to the existing hook's resource
  map. **No financial arithmetic** anywhere; no ranking, priority, "best goal"
  or recommendation wording.

## 11. Tests

- `tests/backend/db/test_household_goal_models.py` — **30**: exact columns with
  no derived or `customer_id` column, nullability, `Numeric`/`Date` types, the
  cascading indexed FK, `is_active` default, vocabulary agreement across Python,
  the API `Literal` and the CHECK, every type accepted and unknowns rejected,
  `target_amount > 0`, null-versus-zero `current_savings`, blank names rejected,
  round-trip, cascade, two-household separation, and the individual
  `financial_goals` table unchanged.
- `tests/backend/api/test_household_goals.py` — **85**: CRUD including
  get-one; every goal type; null-versus-zero and clearing; `is_active`; the
  validation matrix (missing fields, blank/oversized text, unknown types, zero,
  negative, non-numeric, non-finite and over-limit numbers, impossible and
  malformed dates, non-boolean flags, unknown and derived fields); explicit-`null`
  rejection; the full permission matrix; two-way isolation on every verb with
  no-leak checks; goal-id substitution; hostile strings; emergency-fund,
  summary, individual-goal, individual-analysis and financial-inputs
  regressions; OpenAPI shape.
- `tests/backend/db/test_migration_history.py` — **+4** Phase 36 checks (11 in
  all).
- `tests/backend/api/test_households.py` — the exact route inventory now
  includes the five goal routes.
- `tests/backend/db/test_household_finance_metadata.py` — its head check now
  asserts "fully migrated past Phase 35" instead of pinning an exact head that
  every later migration would make stale.

## 12. Database Validation

`alembic current` (both databases): `c3e8f2a9d154 (head)`. `alembic heads`: one.
`alembic check` (both): no pending operations. Migration additive, linear,
downgrade verified structurally, pre-existing row counts unchanged.

Targeted DB-backed run — every never-before-executed Phase 35 and 36 test file,
detached and in isolation: **236 passed, 0 failed** (30:19): goals API 85, goal
models 30, Phase 35 metadata API 39 and models 11, engine 61, migration
history 11.

## 13. Full-Suite Result

**`1260 passed, 3 skipped, 152 warnings in 5977.95s (1:39:37)` — 0 failed,
0 errors, pytest exit code 0.** This is one clean, fully isolated, detached run of
`pytest tests/ -v` (1263 tests collected), started 2026-09-26 20:10:52 and exited
21:50:35. The 3 skips are the documented live-Gemini tests
(`test_debate_gemini_client.py` x2, `test_explanation_gemini_client.py` x1),
which skip when Gemini is unavailable or out of quota (CLAUDE.md section 19).

How it was reached, per `docs/TEST_PLAN.md` section 22: an earlier full run the
same day ended `1249 passed, 2 skipped, 12 errors in 21318.72s (5:55:18)`,
exit code 1. All 12 errors were in `tests/backend/api/test_household_goals.py`,
all at **test setup** (no test body ran), all at
`tests/backend/api/conftest.py:56` (`engine.connect()` in the `db_connection`
fixture): the first raised `server closed the connection unexpectedly` / `the
connection is lost`, the other eleven `[Errno 11001] getaddrinfo failed`. No
product frame appeared in any traceback, so all 12 were classified
DATABASE/NETWORK. After a DB-free probe confirmed the database reachable, exactly
those 12 were re-run in isolation, unmodified: **12 passed, 0 failed** (164.96s,
exit code 0). The clean run above was then taken fresh; the earlier run is not
used as the result. (A development server started outside this work was also
running during the clean run; the run still completed with no failure or
error.)

## 14. TypeScript / Lint / Build

- `npx tsc -b`: **0 errors**.
- `npx oxlint`: **0 errors, 8 warnings** — the unchanged pre-existing baseline.
- `npm run build`: **succeeds** — JS 1,094.83 kB (gzip 327.13 kB), CSS 97.80 kB.
- `frontend/src/types/api.ts` regenerated from `app.openapi()` (no server
  started): **+313 / −0**; a second generation is byte-identical.
- Source-level render checks (server-side render of the real page against real
  API payloads — **not a browser**): Phase 36 **20/20** (six tabs, factual
  headers, null vs zero, inactive shown, `id` order, the calculated
  emergency-fund reference, escaped hostile note, named controls, no
  feasibility/priority/recommendation wording, one `<h1>`); regressions Phase 35
  **17/17** and Phase 34 **39/39**. One Phase 35 harness pin (four Notes fields)
  was updated to five, since the goals form legitimately adds one.

## 15. Security / Isolation

All passing in the 236-test run: households A and B each populated; A cannot
list, read, create in, update or delete B's goals and vice versa, with no goal
name, amount or note of the victim in any denied response and the victim's goal
unchanged afterwards; goal-id substitution → 404 on get/update/delete with no
leak; unauthorized create/read/update/delete by non-members, members and
dependents as in §6; SQL-injection-style names and XSS-style notes stored and
returned verbatim as data; oversized text and malformed numbers → 422. The
render check confirms React emits a hostile note as escaped text.

## 16. Demo-Persona Regression

Live check against the real development database inside one transaction that
was rolled back: **34/34 passed**. The four canonical personas (29096 pending
information, 29098 approved, 29099 approved/savings-first, 29100 rejected) were
confirmed before; an isolated household on 29098/29099 received Phase 35 records
and two Phase 36 goals; the financial summary was **byte-identical** before and
after the goals; permissions held for the member and the non-member; then
**every persona's full analysis response was byte-identical**, **every
persona's individual goals unchanged**, and their individual financial inputs
unchanged. All 11 tables' row counts were restored by the rollback. No
canonical persona data was modified.

## 17. Known Limitations

- **No goal math for households** (§9), by necessity rather than omission.
- Any member — including a dependent — can read every goal and note.
- The creation-time future-date rule in `core/goals.py` is applied by neither
  the individual nor the household goal API.
- **Pre-existing defects found and documented, not fixed (outside Phase 36):**
  the Phase 33 record endpoints return a **500 instead of 422** for an explicit
  `null` on a required field in a `PUT` and for a non-finite or out-of-range
  amount (both probed and confirmed); the Phase 28 `FinancialInputsUpdate`
  schema also accepts non-finite values. The new goal schemas (and Phase 35's
  `interest_rate`) are hardened against both.
- No browser-based testing was performed; the header identity is asserted, not
  authenticated.

## 18. Files Changed

**Created:** `backend/alembic/versions/c3e8f2a9d154_add_household_goals.py`,
`backend/wealthpilot/api/routers/household_goals.py`,
`backend/wealthpilot/api/services/household_goal_service.py`,
`tests/backend/db/test_household_goal_models.py`,
`tests/backend/api/test_household_goals.py`, this report.

**Modified:** `backend/wealthpilot/db/models.py` (`HouseholdGoal`),
`backend/wealthpilot/api/schemas.py` (goal schemas; storage-limit bounds),
`backend/wealthpilot/api/main.py` (router registration),
`frontend/src/lib/api-client.ts`, `frontend/src/hooks/use-household-finances.ts`,
`frontend/src/components/profile/household-finance-section.tsx`,
`frontend/src/components/profile/household-financial-summary.tsx`,
`frontend/src/components/profile/household-card.tsx`,
`frontend/src/types/api.ts` (regenerated); tests
`tests/backend/api/test_households.py` (route inventory),
`tests/backend/db/test_migration_history.py`,
`tests/backend/db/test_household_finance_metadata.py` (head check); docs
`docs/DECISIONS.md` (ADR-035), `docs/RULES.md` (Rule 35),
`docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/TEST_PLAN.md`, `docs/PRD.md`,
`docs/DESIGN.md`, `docs/PROJECT_PLAN.md`, `docs/MEMORY.md`, `TASKS.md`,
`CLAUDE.md`, `.claude/rules/backend.md`.

**Git audit:** the repository still has no commits, so every path is untracked
and `git diff` has no baseline; the change set was audited by modification time
instead. Files changed since the Phase 34 report: 34, all household-scoped.
**Nothing** changed under `core/`, `agents/`, `training/`, `models/`,
`config/`, `datasets/`, `analysis_service.py`, the individual profile/goal
routes or the demo seed scripts. `reports/phase33_household_financial_data_report.md`
appears in that window only because of the honesty correction made during
Phase 34, already disclosed in its report. Nothing was committed.

**Pre-existing finding from the final git audit (documented, not changed):** the
root `.gitignore` (last modified 2026-09-24 23:24, before Phases 35 and 36) has
no rule for `datasets/`, so `git status` now lists the ten raw files under
`datasets/raw/` as untracked, contrary to CLAUDE.md's "datasets/raw/ ...
gitignored". Neither phase touched `.gitignore` or `datasets/`: every raw file
still matches its recorded Phase 5 SHA-256 hash, and the `datasets/`
directories were last modified 2026-09-13. `.env` and both virtualenvs are
still ignored. Restoring the rule (for example `datasets/raw/*` with a tracked
`.gitkeep`) is left to the project owner, and should be done before any first
commit so the raw datasets are not committed.

## 19. Final Completion Status

**COMPLETE.** Every gate is verified: `household_goals` applied to both
databases with `alembic check` clean and row counts unchanged; 236/236 targeted
DB-backed tests; the live persona check 34/34; render checks 20/20 (and
regressions 17/17 and 39/39); `tsc` 0 errors, `oxlint` 0 errors / 8 baseline
warnings, `npm run build` passing; and the clean full suite **1260 passed,
3 skipped, 0 failed, 0 errors** (exit code 0). No Phase 37 implementation was
performed.
