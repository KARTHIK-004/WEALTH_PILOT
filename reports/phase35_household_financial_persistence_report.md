# Phase 35 — Household Financial Data Persistence & Management

Completion report. Historical record: this file describes Phase 35 as it was
implemented and verified, and is not rewritten by later phases.

---

## 1. Phase Objective

Make household financial facts — income, expenses, assets and liabilities —
persistent, editable, validated, isolated and available to the Phase 34
aggregation layer, while keeping every derived value derived.

## 2. Scope

**What the inspection found.** Everything the specification asked for at its
core already existed. Phase 33 had created the four tables
(`household_incomes`, `household_expenses`, `household_assets`,
`household_liabilities`) with exactly the sixteen CRUD routes specified, and
Phase 34's financial summary already read those same rows through
`household_summary_service.py` → `core/household_finance.py`. Creating four new
tables, as the specification literally described, would have duplicated the
source of truth and orphaned both earlier phases.

**Conflicts with accepted decisions**, put to the project owner before any code
was written:

| Specification asked for | Already in place | Conflict |
| --- | --- | --- |
| Four new tables | The four Phase 33 tables | Duplicate source of truth |
| Required `effective_date`, optional `end_date` | `is_active` boolean | The spec also said "reuse Phase 34's target-date convention exactly" and "do not redesign temporal semantics"; ADR-033's engine has no clock |
| `amount >= 0` | CHECK `amount > 0` | ADR-032 chose `> 0` deliberately |
| Required `monthly_payment` | Nullable | ADR-032 and the spec's own "unknown ≠ zero" rule |

**Owner's decision:** reuse the existing tables; add only the genuinely missing
factual fields; keep the existing ADR semantics. Implemented exactly that.

**Not implemented, by that decision and the phase boundary:** new tables,
temporal validity, relaxed constraints, any household risk, ML, portfolio,
recommendation, AI explanation, or external account integration.

## 3. Database Schema

Seven **optional** columns added to the four existing tables:

| Table | Added | Type |
| --- | --- | --- |
| `household_incomes` | `notes` | `String(500)` |
| `household_expenses` | `notes` | `String(500)` |
| `household_assets` | `description`, `notes` | `String(200)`, `String(500)` |
| `household_liabilities` | `interest_rate`, `description`, `notes` | `Numeric(6, 4)`, `String(200)`, `String(500)` |

All nullable with **no default**, so no existing row needed a backfill and no
value was invented. `interest_rate` uses the `Numeric(6, 4)` rate convention of
`financial_inputs` and has a CHECK `interest_rate IS NULL OR interest_rate >= 0`.
No existing column was removed, renamed or re-typed and no constraint weakened.

## 4. Migration ID

`a7c41e9b6f30` — `add household financial metadata columns`, revising
`d2be70d8b07f` (Phase 33). Only `add_column` ×7 and one `create_check_constraint`.

Applied to **both** databases (`d2be70d8b07f -> a7c41e9b6f30`). `alembic check`
on both: **"No new upgrade operations detected."** Row counts on ten relevant
tables compared before and after on both databases: **unchanged**. (Phase 36's
migration has since been applied on top; see its report.)

## 5. API Routes

No new route. The Phase 33 routes carry the new fields:

`GET`/`POST /api/households/{id}/{income|expenses|assets|liabilities}` and
`PUT`/`DELETE` on each `/{record_id}` — `notes` on all four request and response
schemas, `description` on assets and liabilities, `interest_rate` on
liabilities. Pydantic schemas throughout; no database model is exposed.

## 6. Authorization Model

Phase 32/33's, unchanged: the asserted `X-Customer-Id` header (not
authentication — `docs/SECURITY.md`), any member reads, **only the primary
writes**, a non-member gets 403, an unknown household 404, a record id from
another household 404. Re-verified with the new fields: a non-primary member and
a dependent can read but not create, update or delete.

## 7. Phase 34 Integration

Already in place and preserved exactly: the summary reads the persisted rows via
`household_summary_service.py` → `core/household_finance.py`. **The engine was
not changed.** Its input records deliberately have no field for `notes`,
`description` or `interest_rate`, so the new metadata cannot reach the
arithmetic even by accident — a test asserts this, and a second test builds two
households with identical facts but different metadata and asserts their
summaries are identical.

Verified against the specification's reference dataset (monthly salary 60,000;
yearly 120,000; one-time bonus 50,000; monthly essential expenses 20,000; yearly
expense 120,000; one-time expense 30,000; liquid cash 100,000; loan 200,000):
recurring income **70,000**, recurring expenses **30,000**, cash flow **40,000**
(one-time excluded), net position **−100,000**, emergency fund required
**120,000** vs 100,000 → **insufficient**, shortfall **20,000** — both in the
test suite and live against the real database.

## 8. NULL vs Zero Semantics

Unchanged and extended to the new fields: an omitted `notes`, `description` or
`interest_rate` is stored and returned as `null`, never `0` or `""`; a recorded
`0` interest rate is returned as `0`. The frontend renders `null` as "Not
provided" and a stored `0` rate as "0.00%". `monthly_payment` remains nullable
and `amount > 0` remains in force (ADR-032).

## 9. Temporal Semantics

**Unchanged: `is_active` remains the activity rule.** No `effective_date` or
`end_date` was added. The Phase 34 engine therefore still has no clock and no
target date, and its output is byte-identical for the same facts. Date-bounded
validity would be a real change to Phase 34's semantics needing its own
target-date convention and ADR (ADR-034).

## 10. Frontend Changes

`components/profile/household-finance-section.tsx`: an optional **Notes** field
on every record dialog, **Description** on assets and liabilities, and
**Interest rate** on liabilities — a new `rate` field kind entered as a decimal
("0.0425 means 4.25%") and submitted verbatim, exactly the Phase 28
financial-inputs convention, and displayed with the existing `formatPercent`.
The liabilities tab note states that the rate is recorded for reference only and
nothing is calculated from it. No arithmetic was added. Notes use the existing
single-line `Input` (the project has no textarea primitive).

## 11. Tests Added

- `tests/backend/db/test_household_finance_metadata.py` — **11** (types, the
  rate CHECK, round-trip, NULL-stays-NULL, a known-zero rate, ADR-032 rules not
  weakened, a pre-existing-shaped row reading back with NULL metadata, cascade).
- `tests/backend/api/test_household_finance_metadata.py` — **39** (round-trip,
  update/clear, oversized and malformed input, storage-limit bounds, hostile
  strings, dependent/non-primary write denial, two-way isolation, record-ID
  substitution, the reference dataset, emergency-fund agreement with
  `core/goals.py`, the metadata-cannot-move-a-figure twin test, and
  individual-analysis/inputs regressions).
- `tests/backend/db/test_migration_history.py` — **7** at Phase 35 (database-
  free: single head, linear chain, purely additive, all new columns nullable
  with no default, downgrade reverses upgrade); extended by Phase 36.
- `tests/backend/core/test_household_finance.py` — **+2** (metadata cannot reach
  the engine; `interest_rate` never used).
- `tests/backend/db/test_household_finance_models.py` — its exact-schema and
  nullability pins updated to the new contract (a deliberate schema change,
  documented in the test).

## 12. Database-Free Test Results

Engine 61/61 and migration history 11/11 (including Phase 36's checks) pass
with no database.

## 13. DB-Backed API Test Results

A first targeted run was **killed at 71% by a session ending** and is not
counted. It had surfaced one failure, `test_metadata_is_deleted_with_its_household`,
diagnosed from its traceback as a **defect in the test**: it deleted the
household through the ORM (which tries to null out
`household_members.household_id`) instead of exercising the database's
`ON DELETE CASCADE`. Corrected to use raw SQL, as Phase 33's cascade test does.

The definitive targeted run covered every Phase 35 and 36 test file, detached
and in isolation: **236 passed, 0 failed** (30:19) — including all 11 Phase 35
database tests and all 39 Phase 35 API tests.

## 14. Full-Suite Result

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

## 15. Frontend Validation

At Phase 35's frontend state: `npx tsc -b` 0 errors; `npx oxlint` 0 errors,
8 warnings (the unchanged baseline); `npm run build` succeeds (JS 1,091.67 kB,
gzip 326.57 kB). Re-verified after Phase 36's changes: still 0 / 8 / succeeds.

## 16. OpenAPI / Type Generation

`frontend/src/types/api.ts` regenerated from `app.openapi()` (no server
started): **+42 / −0**; a second generation is byte-identical. OpenAPI still 27
paths — Phase 35 added no route. (Regenerated again in Phase 36.)

## 17. Security / Isolation Validation

All in the 236-test run and passing: cross-household read/modify/delete denied
both ways (A→B and B→A) with a check that no note, description or amount of the
other household appears in the response; record-ID substitution → 404 with no
leak; dependent and non-primary mutation → 403; oversized text and invalid
values → 422; SQL-injection-style and `<script>`-style notes stored and returned
verbatim as data, the tables intact afterwards. The source-level render check
confirmed React emits a hostile note as escaped text, not markup.

**Found while validating, and fixed in this phase's own field:** a non-finite
`interest_rate` (`"1e400"` parses to `inf`) or one beyond `Numeric(6, 4)`
(> 99.9999) passed validation and would have failed in the database as a 500.
The field is now finite and bounded by its storage limit (a technical limit,
not a financial rule), with tests for 100 → 422, `"inf"` → 422 and 99.9999 → 201.
The same defect class in Phase 33's own fields is recorded, not fixed (§19).

## 18. Demo-Persona Regression

Live check against the real development database, inside one transaction
rolled back at the end: **34/34 passed**. The four personas resolve to
29096/29098/29099/29100 and are in their canonical states (pending_information,
approved, approved/savings-first, rejected); the reference dataset persists and
summarizes to the exact values in §7; changing `interest_rate` moves no summary
figure; a non-member sees nothing; **every persona's full analysis response is
byte-identical** afterwards and their individual financial inputs unchanged; all
11 tables' row counts restored by the rollback.

## 19. Known Limitations

- No temporal validity (by decision, ADR-034); `is_active` is the only activity
  rule.
- `interest_rate` is recorded, never used — no schedule, payoff date or interest
  figure exists.
- Notes are single-line inputs, and any household member can read every note.
- **Pre-existing defects found, not fixed (outside this phase):** the Phase 33
  record schemas return **500 instead of 422** for an explicit `null` on a
  required field in a `PUT`, and for a non-finite or out-of-range amount
  (probed: `"1e400"` → 500, `1e13` → 500). The Phase 28 financial-inputs
  schema also accepts non-finite values.
- No browser-based testing was performed; frontend verification was `tsc`,
  `oxlint`, `vite build` and a source-level server render.

## 20. Files Changed

**Created:** `backend/alembic/versions/a7c41e9b6f30_add_household_financial_metadata_columns.py`,
`tests/backend/db/test_household_finance_metadata.py`,
`tests/backend/api/test_household_finance_metadata.py`,
`tests/backend/db/test_migration_history.py`, this report.

**Modified:** `backend/wealthpilot/db/models.py`, `backend/wealthpilot/api/schemas.py`,
`backend/wealthpilot/api/services/household_finance_service.py`,
`frontend/src/components/profile/household-finance-section.tsx`,
`frontend/src/types/api.ts` (regenerated),
`tests/backend/db/test_household_finance_models.py` (schema pins),
`tests/backend/core/test_household_finance.py` (+2 guards), and documentation:
`docs/DECISIONS.md` (ADR-034), `docs/RULES.md` (Rule 34), `docs/ARCHITECTURE.md`,
`docs/SECURITY.md`, `docs/TEST_PLAN.md`, `docs/PRD.md`, `docs/DESIGN.md`,
`docs/PROJECT_PLAN.md` (an addendum pointing to the household ADRs; its
methodology is untouched), `docs/MEMORY.md`, `TASKS.md`, `CLAUDE.md`,
`.claude/rules/backend.md`.

**Not touched:** ML artifacts, datasets, risk, portfolio, compliance, Gemini,
LangGraph, AutoGen, `core/`, `agents/`, individual financial inputs, and demo
persona data. Nothing was committed.

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

## 21. Final Completion Status

**COMPLETE.** Every gate is verified: the additive migration applied to both
databases with `alembic check` clean and row counts unchanged; 236/236 targeted
DB-backed tests; the live persona check 34/34; the render check 17/17; `tsc` 0
errors, `oxlint` 0 errors / 8 baseline warnings, `npm run build` passing; and the
clean full suite **1260 passed, 3 skipped, 0 failed, 0 errors** (exit code 0).
No Phase 36 or later work is claimed by this report.
