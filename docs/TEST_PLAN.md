# WealthPilot AI — Test Plan

Documents actual testing strategy and actual commands. Every command
below is verified to exist and run in this repository — none is
aspirational.

## 1. Unit Tests

`tests/backend/core/` — pure functions in `core/goals.py`,
`core/optimizer.py`, `core/compliance.py`: TVM formulas, Monte Carlo
determinism, emergency-fund math, every compliance rule's trigger
condition in isolation.

## 2. Integration Tests

`tests/backend/agents/test_graph_execution.py`,
`tests/backend/agents/test_financial_inputs_integration.py` — the
compiled LangGraph run end-to-end against real, already-linked FAR-Trans
customers (`customer_id=1`, `customer_id=2`), never mocked, to verify
actual routing and actual node outputs.

## 3. Database Tests

`tests/backend/db/test_models.py` — schema/constraint-level checks
(unique constraints, FK behavior) against `TEST_DATABASE_URL` via the
`db_session` fixture (`tests/backend/conftest.py`), rolled back after
every test via a SAVEPOINT-based transaction wrapper.
`tests/backend/db/test_household_models.py` (Phase 32, 23 tests) proves the
database itself enforces the household rules against real PostgreSQL — one
household per customer, one primary per household (partial unique index), the
controlled relationship/role vocabularies, primary implies `self`, `self` never
a dependent, `is_dependent` matches the role, foreign keys and cascades, that
the `households`/`household_members` tables carry no financial column, that the
`customers` table is unchanged, and that the Python vocabularies match the API
`Literal` types and the CHECK constraints. Expected violations are provoked
inside a SAVEPOINT (`begin_nested`) so the failed write does not discard the
test's own setup rows.

`tests/backend/db/test_household_finance_models.py` (Phase 33, 39 tests) does
the same for the four household financial tables: the exact column set of each
(asserted whole, so a derived/aggregate column cannot be added unnoticed and no
table has a `customer_id`), `Numeric(14, 2)` money precision, which columns are
nullable (only an expense's `description` and a liability's `monthly_payment`),
`is_active`'s database default, the indexed cascading `household_id` foreign
key, round-trip and delete-cascade behaviour, the sign CHECKs (amount > 0;
value/outstanding ≥ 0; `monthly_payment IS NULL OR >= 0`), every controlled
vocabulary accepted and an out-of-vocabulary value rejected, Python ↔ API
`Literal` ↔ CHECK-constraint agreement, and that the Phase 32 tables are
unchanged.

## 4. API Tests

`tests/backend/api/*.py` — one file per router
(`test_profiles.py`, `test_analysis.py`, `test_scenarios.py`,
`test_qa.py`, `test_sse.py`, and — Phase 32, 51 tests —
`test_households.py`: creation and automatic primary membership, retrieval and
listing, member addition, duplicate / already-in-another-household / second-
primary / invalid-relationship / invalid-role / primary-self combination
rejections, primary-cannot-be-removed, unknown household and customer, the
missing-identity 401 matrix, the isolation matrix (A→Household A allowed,
A→Household B denied, B→Household B allowed, cross-household add / modify /
delete denied, non-primary members cannot manage, membership is not account
access), RFC 7807 shape on every error, a database-race 409, the OpenAPI route
list and "no financial field" schema check, and the regression guards that
`POST /api/analysis` (body and cache key) and the financial-input endpoints are
unchanged by household membership). A temporary mutation that disabled the
non-member check was confirmed to fail three isolation tests, then reverted.

Phase 33, 110 tests — `test_household_finances.py`, table-driven across all
four resources (income, expenses, assets, liabilities): full CRUD; per-resource
specifics (free-text income source, optional expense description, `is_essential`
with no default, a nullable `monthly_payment` that stays `null` while a stated
`0` stays `0`); the validation matrix (blank/too-long strings, non-numeric and
wrong-sign amounts, out-of-vocabulary values, unknown fields, and a
`household_id` sent in a body → 422 via `extra="forbid"`); partial-update
merge semantics; authorization and isolation (401 without `X-Customer-Id`, 403
for a non-member read and for a non-primary mutation, 404 for an unknown
household, 404 — never 403 — for a record id belonging to another household,
and no denied household's data anywhere in an error body); the OpenAPI route
set, including an assertion that **no** route path contains `summary`,
`totals`, `net-worth`, `savings` or `debt-ratio`; a schema check that no
household financial response model carries a derived field; and regression
guards that `POST /api/analysis` and the individual financial-input endpoints
are unchanged once household financial data exists. Two temporary mutations —
one dropping the household scope from the record lookup, one dropping the
primary check from mutations — were confirmed to fail 4 and 8 tests
respectively, then reverted (the files verified byte-identical afterwards).
Uses `client` (synthetic customer,
`TEST_DATABASE_URL`, mocked graph via `patch_graph`/`approved_steps`/
`rejected_steps` for controlled terminal states) or `real_client`
(rollback-safe, real `DATABASE_URL`, for read-only tests against genuine
FAR-Trans customers) — see `tests/backend/api/conftest.py`'s own
docstring for exactly when each applies.

`tests/backend/core/test_household_finance.py` (Phase 34, 59 tests) covers the
deterministic aggregation engine with **no database at all** — pure `Decimal`
arithmetic, so it runs in well under a second and is unaffected by hosted-DB
latency. It covers the whole Phase 34 matrix: monthly/yearly/one-time
normalization, inactive records, empty sets, essential vs non-essential
expenses, liquid vs illiquid assets, nullable `monthly_payment`, cash flow and
net position with each side missing in turn, genuine zeroes kept distinct from
unknowns, the exact emergency-fund boundary (required, required − 1,
required + 1, compared exactly rather than approximately), agreement with
`core/goals.py::assess_emergency_fund`, determinism, and an assertion that no
score/ratio/recommendation field exists anywhere in the result.

`tests/backend/api/test_household_summary.py` (Phase 34) covers the endpoint
around that engine: the documented response shape, values traced back to the
stored records, one-time records staying out of cash flow, the summary
following create/update/delete, null-vs-zero at the API boundary, the
emergency-fund boundary end to end, the authorization matrix (member 200,
non-primary member 200, dependent 200, non-member 403, unknown household 404,
missing/malformed identity 401, every mutating verb 405), cross-household
isolation with two fully populated households, the OpenAPI route set, and
regression guards that the individual analysis and individual financial inputs
are untouched.

Phase 35 adds three files. `tests/backend/db/test_migration_history.py`
(7 tests) needs **no database**: it reads `backend/alembic/versions/` through
Alembic's `ScriptDirectory` and proves a single head, a linear chain, and that
the Phase 35 migration is purely additive (only `add_column` plus one CHECK,
only the four household tables, every new column nullable with no default,
and a downgrade that reverses every step). `tests/backend/db/
test_household_finance_metadata.py` (11 tests) checks the new columns' types
and CHECK against real PostgreSQL, round-trips, NULL-stays-NULL, a known-zero
rate, that ADR-032's `amount > 0` and nullable `monthly_payment` were not
weakened, and that a pre-existing-shaped row reads back with NULL metadata.
`tests/backend/api/test_household_finance_metadata.py` (36 tests) covers the
new fields through the API, oversized/malformed/negative input, hostile
strings stored verbatim, dependent and non-primary write denial, two-way
cross-household isolation with a no-leak check on the new fields, record-ID
substitution, the Phase 34 summary over the specification's reference dataset,
agreement with `assess_emergency_fund`, and a twin-household test proving
metadata cannot move any summary figure.

Phase 36 adds `tests/backend/db/test_household_goal_models.py` (the table's
exact columns with no derived or `customer_id` column, nullability, `Numeric`
precision, the cascading indexed FK, the goal-type vocabulary agreeing across
Python, the API `Literal` and the CHECK constraint, `target_amount > 0`, a
null-versus-zero `current_savings`, and the individual `financial_goals` table
unchanged) and `tests/backend/api/test_household_goals.py` (CRUD including
get-one, the validation matrix including storage-limit and non-finite numbers,
explicit-`null` rejection, the primary/member/dependent/non-member/unknown/401
matrix, two-way isolation on every verb with no-leak checks, goal-id
substitution, hostile strings, `is_active` behaviour, and the three
regressions: the individual goals and analysis untouched, the summary's
emergency fund unchanged by an `emergency_fund` goal and still agreeing with
`assess_emergency_fund`, and the whole financial summary unchanged by goals).
`test_migration_history.py` gained Phase 36 checks (one new table only, a
downgrade that drops exactly it, and no household migration operating on
`financial_goals`).

Plain-language explanations (ADR-037): `tests/backend/agents/
test_explanation_readability.py` checks the Gemini-output validator with the
specification's own examples. **This file is prepared but not yet in the
repository** (the backend part is not applied; see `docs/MEMORY.md`), so the
checks below are planned, not live:

- restating the real values passes;
- swapped weights ("45% in QQQ"), an invented amount ("₹30,000", "₹1,50,000"),
  an invented probability (97.5%) and a derived count ("94 out of 100") are all
  rejected;
- an honest grouped amount ("₹4,000") passes even when no source amount is 0.
  This is a regression test for the old pattern, which read "30,000" as "000".

It also checks the templated fallback for structure and readability: every
section filled, sentences of 40 words or fewer, no unexplained acronym, the
canonical disclaimer, and only traceable numbers. Finally it checks that the
prompt asks for plain language without losing any original safety rule.

The Simple view is checked by a source-level render of the real page against
the four personas' cached analyses (not a browser). Every EUR and % figure in
it must be a value from that persona's own API response.

## 5. RFC7807 Error Tests

`tests/backend/api/test_rfc7807.py` — every error path returns
`application/problem+json` with `status`/`title`/`detail`/`instance`,
never a bare 500 or an unstructured error body.

## 6. ML Tests

`tests/training/risk/`, `tests/training/behaviour/`,
`tests/training/expense/` — model-training correctness, metrics-output
shape, and artifact serialization.

## 7. Data Quality Tests

`tests/backend/data/test_ingestion.py` — FAR-Trans loading, `Predicted_*`
/`Not_Available` filtering, join integrity.

## 8. Leakage Tests

`tests/training/risk/test_preprocessing_isolation.py` — the preprocessor
is never fit on the full dataset during CV, never sees a fold's held-out
rows.

## 9. Time-Series Tests

`tests/training/market/` — walk-forward split correctness, embargo gap
enforcement, no shuffled split anywhere in the market-model pipeline.

## 10. Portfolio Tests

`tests/backend/core/test_optimizer.py` (naming approximate — see
`tests/backend/core/`) — MVO/HRP/1-N weight correctness, QQQ-band and
single-asset-cap enforcement, Ledoit-Wolf shrinkage behavior.

## 11. Compliance Tests

`tests/backend/core/test_compliance.py` — every rule's trigger condition,
fail-closed behavior on missing data, REJECT's unconditional precedence,
and (Phase 28) the savings-first weight-exemption boundary (a
savings-first proposal that inconsistently supplies weights is still
fully validated — see `docs/DECISIONS.md` ADR-018).
`tests/backend/agents/test_compliance_gate_safety.py` — `enforce_gate`'s
binding behavior against a real portfolio-manager output.

## 12. Recommendation Tests

`tests/backend/agents/test_recommendation_node.py` — persistence
behavior, precedence, savings-first handling.

## 13. LangGraph Tests

`tests/backend/agents/test_graph_construction.py` (compiles without
error), `tests/backend/agents/test_graph_execution.py` (real routing:
low-confidence halt, savings-first branch, provenance preservation,
determinism, processing-failure handling).

## 14. AutoGen Tests

`tests/backend/agents/test_debate.py` — bounded turn structure,
malformed-response resilience, determinism across runs.

## 15. Gemini Tests

`tests/backend/agents/test_explanation.py` (validation/fallback logic,
mocked client), `tests/backend/agents/test_explanation_gemini_client.py`
and `tests/backend/agents/test_debate_gemini_client.py` (real API calls —
**skipped** when Gemini quota/credentials are unavailable; 3 such skips
are the current, expected baseline, unrelated to any regression).

## 16. Agent-State Tests

`tests/backend/agents/test_state.py` — `apply_delta` semantics: new
-object-only merge, error accumulation across multiple deltas,
`blocked`/`block_reason` derivation from `compliance_result`.

## 17. Frontend Type Checking

```
cd frontend
npx tsc -b
```
Expect 0 errors. Also implicitly run as the first step of `npm run build`.

## 18. Frontend Build

```
cd frontend
npm run build
```
Expect a successful Vite production build; a "chunk larger than 500 kB"
warning is a known, accepted, pre-existing characteristic (single-bundle
build, not code-split) — not a failure.

## 19. Lint

```
cd frontend
npx oxlint
```
Expect 0 errors. A fixed baseline of 8 `react(only-export-components)`/
`react(set-state-in-effect)` warnings exists in shadcn/ui primitives and
provider files — pre-existing, not introduced by any recent phase; a new
warning beyond that baseline should be investigated, not ignored.

## 20. Demo Tests

`tests/backend/api/test_seed_demo_data.py` — the seed script's pure
logic, an integration-style create/link/persist flow, idempotency-guard
behavior, and reset-safety exact-name-matching (never a prefix/wildcard
match that could reach an unrelated customer row). Since ADR-038 it also
seeds all four personas from `demo_data/` through the real app and checks
four things:

- every stored value equals the dataset;
- a second run creates nothing;
- an existing value is never overwritten;
- persona D equals the frontend fallback's own constants.

`tests/backend/scripts/test_validate_demo_data.py` (no database) runs the
dataset validator. The committed `demo_data/` must pass, and regenerating the
manifest must be byte-stable. Each kind of defect is planted in a temporary
copy, with the manifest regenerated so the manifest check cannot be what
catches it, and must be reported. The planted defects include:

- a duplicate key, an orphan member, a second primary, a primary who is not
  `self`, and a persona in two households;
- an invented profile, goal or household field;
- a negative amount, and a null without a reason;
- an option the question lacks, and an answer off its rule;
- a fake FAR-Trans link;
- an unsupported strategy, and a contribution what-if;
- a financial number used as an expected state;
- an edit without regenerating the manifest, an unlisted file, and a
  non-canonical format.

The raw-training-data guard is tested on a temporary copy. Live checks against
the development database are `seed_demo_data.py verify` and `verify-family`
(`--in-process`).

## 21. End-to-End Tests

No browser-automation E2E suite exists in this project (no headless
-browser tool has been available in its development environment to
date). "End-to-end" verification instead means: a real, unmocked call
through `get_or_run_analysis`/`run_analysis_graph` against a real linked
customer, asserting on the full resulting `AnalysisResult` shape — see
`tests/backend/agents/test_financial_inputs_integration.py` for the
established pattern. Do not claim browser-based E2E testing was
performed unless a headless-browser tool was actually used.

Frontend chart data binding (Phase 30, a manual scratch check — not part of
the committed suite, because the project has no frontend test runner and no
library may be added): Vite's SSR build of a temporary entry under
`frontend/`, rendering the real page components with `renderToString` against
real API responses captured in-process from the demo personas (`TestClient`,
no server). Recharts 3 draws no `<svg>` on the server, so its primitives are
replaced by stubs that record the props they receive; the assertions cover
the exact data passed to each chart, the surrounding text/tables, status-safe
rendering (savings-first has no allocation, rejected has no chart, pending has
nothing) and null handling. It proves data binding, **not** appearance,
interaction or responsiveness. Delete the temporary entry and build output
afterwards. Phase 30 ran 65 such checks, all passing.

Phase 31 extended the same approach to the whole routed application (App inside
its real providers, `MemoryRouter` at each route, all four demo personas): route
and navigation audit (one `<h1>`, one `aria-current` link, no dead `href`),
identity, status-safe rendering per persona, loading / RFC 7807 error /
API-unreachable / no-profile / empty states, text hygiene (no `undefined`, `NaN`,
`null`, raw error text or ranking words), the disclaimer on every page, and a
rendered-markup accessibility audit (labels, button names, table headers,
heading order, `role="img"` labels, `role="alert"` / `role="status"`) — 71
checks, all passing. A second scratch check ran the real
`lib/demo-customer.ts::resolveDemoCustomer` against a stubbed API (six
resolution scenarios). The live-API side was a rollback-safe in-process
regression (every route in the API surface, mutating routes exercised only on a
scratch customer inside a transaction that is rolled back): 56 checks, all
passing, with the database verified unchanged afterwards.

## 22. Regression Testing

```
pytest tests/ -v
```
Run in full isolation — no other process (another pytest run, a
diagnostic script) touching either database concurrently. Piping through
`tail` on a long run hides real-time progress; prefer direct/unbuffered
output for any run expected to take more than a couple of minutes, so a
stall can be distinguished from a slow-but-healthy run (see
`docs/RULES.md` Rule 26 and "Transient Failures" below).

**Transient Failures**: this suite has, on at least four separate
occasions across this project's development, shown a small number of
failures in one full run (typically "server closed the connection
unexpectedly" or an otherwise-passing test failing only under full-suite
load) that did not reproduce when the same test(s) were re-run
individually immediately afterward. The established diagnostic procedure:
(1) re-run the specific failing test(s) in isolation; (2) if they pass
cleanly, attribute the original failure to a transient, full-suite
-duration connection/resource artifact rather than a logic regression;
(3) get one final, clean, fully-isolated full-suite run before reporting
completion. Never dismiss a failure without this isolation check, and
never accept a failing suite as "probably fine" without it either.

**Network-outage variant (Phase 29)**: the databases are hosted (Neon
Postgres), so a machine network drop mid-run produces a burst of failures
and errors — in Phase 29, one run showed 9 failed / 20 errors, all in
tests touching either database. Recognize it by the tracebacks (printed at
the END of a `-v` run): `psycopg.OperationalError` with `[Errno 11001]
getaddrinfo failed`, `Network is unreachable (10051)`, `Socket is not
connected (10057)`, or `server closed the connection unexpectedly`,
followed by `PendingRollbackError` in later tests sharing the session. A
DB-free probe distinguishes an ongoing outage from a code problem:
resolve the database host and open a TCP connection to port 5432 from
Python (`socket.getaddrinfo` + `socket.create_connection`, no SQL, without
printing the host). Once it is reliably reachable, re-run the failing
tests in isolation, then take one clean full run. If reachability is still
intermittent, a "single clean full run" may not be obtainable — say so
honestly and report (a) the full-run result, (b) each failure classified
from its own traceback as network vs assertion, and (c) the isolated
re-run of every failing test, rather than claiming a clean run that did
not happen.

**Skip count**: the 3 live-Gemini tests (`test_debate_gemini_client.py`×2,
`test_explanation_gemini_client.py`×1) skip when Gemini is unavailable or
out of quota at that moment; the count is *up to* 3, not a fixed 3 — in one
Phase 29 run one of them actually executed and passed.

## 23. Security Testing

Grep new/modified files for API-key/credential/token patterns before
considering a phase complete (established practice, not an automated CI
gate at this time). Verify customer-isolation tests exist for any new
per-customer persistence endpoint (create/read/update all get an
"isolated per customer" test — see `tests/backend/api/test_profiles.py`
for the established pattern applied to questionnaire, goals, and
financial inputs).

## 24. Acceptance Criteria

A phase/task is considered tested and complete only when: the relevant
new/changed backend tests pass; the full `pytest tests/ -v` suite passes
(or its failures are diagnosed as transient per §22 and a clean re-run
confirms it); `npx tsc -b`, `npm run build`, and `npx oxlint` all pass
with no new errors or warnings beyond the established baseline; and the
result is reported honestly, including any verification that could not
be performed (e.g. browser-based visual testing) rather than silently
omitted or overclaimed.

## Running the database-backed tests safely (checked 2026-10-20)

`tests/backend/conftest.py` and `tests/backend/api/conftest.py` use `TEST_DATABASE_URL` only, inside a rolled-back outer transaction; `real_client` fixtures also read `DATABASE_URL`
(read-only intent). In this workspace both URLs point at the same hosted Neon host (databases `neondb` and `neondb_test`) and there is no local PostgreSQL. A hosted database is not
verified as disposable from the repository alone, so the DB-backed suites (for example `tests/backend/api/test_monthly_records.py`) were NOT run for ADR-043.
To run them safely: (1) point `TEST_DATABASE_URL` at a throwaway local or dedicated test PostgreSQL that holds no real data, (2) `ALEMBIC_TARGET=test alembic upgrade head`,
(3) run only the targeted file (`pytest tests/backend/api/test_monthly_records.py`), and avoid `real_client` tests unless `DATABASE_URL` is also a disposable copy.
Offline checks that need no database: `tests/backend/core/test_user_text_sentiment.py`, `test_behaviour_findings_and_insight.py`, `test_user_text_rubric_examples.py`,
`test_behaviour_features.py`, and `tests/backend/api/test_personalized_insights.py` (stub session).

Local provisioning check (2026-10-20): no PostgreSQL server binaries (`postgres`, `pg_ctl`, `initdb`, `psql`), no PostgreSQL service, no Docker, no embedded-Postgres package in `.venv`
(only the `psycopg` client), and nothing listening on port 5432. A disposable local database therefore cannot be provisioned with already-approved tools. Exact prerequisite: a PostgreSQL
server the owner installs or provides (approved stack: PostgreSQL; the project uses no Docker), an empty database for tests, `TEST_DATABASE_URL` pointing at it, then
`ALEMBIC_TARGET=test alembic upgrade head` and `pytest tests/backend/api/test_monthly_records.py`. Alternatively the owner confirms in writing that the hosted `neondb_test` is disposable.

### Local disposable PostgreSQL on this machine (Windows 11) -- NOT executed; needs the owner's go-ahead

Checked 2026-10-20 without installing anything: `winget` 1.29 is present; `winget search postgresql --source winget` lists `PostgreSQL.PostgreSQL.16` (16.15-5), `.17` (17.11-5) and `.18` (18.6-5);
`winget show --id PostgreSQL.PostgreSQL.17 --exact` shows an EDB `.exe` installer (SHA256 listed). `alembic heads` (offline) reports one head, `e5b1c7d93a20`. `to_sqlalchemy_url` rewrites
`postgresql://` to `postgresql+psycopg://`, so a plain `postgresql://` URL is correct (psycopg 3.2.3, SQLAlchemy 2.0.36, Alembic 1.14.0). The Settings object reads `.env`, but a process
environment variable overrides it, so session variables are enough and `.env` is never edited. Run everything from the repository root in Windows PowerShell 5.1.

**1. Install (elevated PowerShell; interactive, so no password lands in shell history).** The installer asks for a superuser password (use letters and digits only, so the URL needs no escaping),
keeps port 5432 and creates the `postgresql-x64-17` service:

```powershell
winget install --id PostgreSQL.PostgreSQL.17 --exact --source winget --interactive
```

**2. Create an empty database (psql prompts for the password):**

```powershell
$psql = "C:\Program Files\PostgreSQL\17\bin\psql.exe"
& $psql -U postgres -h localhost -c "CREATE DATABASE wealthpilot_test;"
```

**3. Session-only URLs (both point at the local database, so nothing can reach Neon).** The password is typed at a prompt and kept in this window only:

```powershell
$sec = Read-Host "postgres password" -AsSecureString
$pw  = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
$env:TEST_DATABASE_URL = "postgresql://postgres:$pw@localhost:5432/wealthpilot_test"
$env:DATABASE_URL      = $env:TEST_DATABASE_URL
Remove-Item Env:ALEMBIC_TARGET -ErrorAction SilentlyContinue
```

**4. Verify the effective host through the app's own Settings (reads no database) -- stop unless both print `localhost`:**

```powershell
.\.venv\Scripts\python.exe -c "from urllib.parse import urlsplit as u; from wealthpilot.config import get_settings as g; s=g(); print(u(s.test_database_url).hostname, u(s.database_url).hostname)"
```

**5. Verify the database is empty and disposable, still before any migration (read-only queries):**

```powershell
$env:PGPASSWORD = $pw
& $psql -U postgres -h localhost -d wealthpilot_test -tAc "select current_database(), inet_server_addr(), version();"
& $psql -U postgres -h localhost -d wealthpilot_test -tAc "select count(*) from information_schema.tables where table_schema not in ('pg_catalog','information_schema');"
& $psql -U postgres -h localhost -l
```

Proceed only if: the first query shows `wealthpilot_test` on `127.0.0.1` or `::1`; the second prints `0` (no user tables, so not a copy of real data); the server is the local one you just installed
(`-l` shows only `postgres`, `template0`, `template1`, `wealthpilot_test`); and you created the database yourself in step 2.

**6. Migrate the empty test database (this is the first database-changing command; run it only after step 5 passes):**

```powershell
cd backend; $env:ALEMBIC_TARGET = "test"; ..\.venv\Scripts\alembic.exe upgrade head; Remove-Item Env:ALEMBIC_TARGET; cd ..
```

**7. Run only the target file (its fixtures use `client`/`make_customer`, i.e. `TEST_DATABASE_URL` only):**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/backend/api/test_monthly_records.py -v
```

**8. Clean up the session:** `Remove-Item Env:PGPASSWORD, Env:TEST_DATABASE_URL, Env:DATABASE_URL; $pw = $null`. To discard the database afterwards: `& $psql -U postgres -h localhost -c "DROP DATABASE wealthpilot_test;"`.

Caveats: the migration chain has not been run on an empty database in this workspace, so a failure at step 6 is information, not a regression to hide. Tests that need FAR-Trans or `market_data`
(the `real_client`/`real_session` fixtures) are out of scope for this local database; do not run the full suite against it. Remaining prerequisite: the owner installs PostgreSQL and passes step 5
(or confirms in writing that the hosted `neondb_test` is disposable). Until then the DB-backed suites are not run.

#### Execution status (2026-10-20): local PostgreSQL NOT installed (the monthly-records file was later run against the Neon test database; see the next section)

Checked on Windows 11 Pro 10.0.26300 (64-bit), Windows PowerShell 5.1, `winget` 1.29.380. The current shell is **not elevated** and the EDB installer needs administrator approval (UAC), which is a user-only action,
so nothing was installed: no PostgreSQL service exists, no `wealthpilot_test` database was created, no migration ran, and `tests/backend/api/test_monthly_records.py` has not been run. Neon was not contacted and `.env` was not edited.
Prepared instead: `scripts/local_test_db.ps1` (parses with 0 errors; never executed). After the owner completes step 1 above, `.\scripts\local_test_db.ps1 -Stage All` prompts for the password and runs Create, then Verify (stops unless: both
effective settings resolve to `localhost`, database name is exactly `wealthpilot_test`, the server is loopback, no other non-template database exists, zero user tables), then `ALEMBIC_TARGET=test alembic upgrade head`, then the monthly-records file.
`-Stage Verify` runs only the read-only checks. Re-running Migrate on an already-migrated database stops by design ("non-empty"). The script never drops anything. Smallest remaining user action: run step 1 from an elevated PowerShell.

Regression results recorded the same day (commands run from the repository root, or `frontend/` for the last three): `pytest tests/backend/data/gdelt -q` 1,492 passed in 87.84 s (exit 0); the offline user-text/behaviour/pilot files (see below)
all pass; `npx tsc -b` exit 0; `npm run build` exit 0 (one chunk-size warning); `npx oxlint` exit 0, 0 errors, 8 pre-existing warnings.

#### Neon test database run (2026-10-20): `test_monthly_records.py` 53 passed

Owner instruction: use the Neon test database (`TEST_DATABASE_URL` -> `neondb_test`; `DATABASE_URL` -> `neondb`, same host). Credentials were never printed; `.env` is git-ignored, was never tracked and is not in HEAD, and no other file contains a Neon host.
No evidence of exposure was found, so rotation is not required by anything observed; the owner may still rotate at their discretion and must then update `.env` locally only (never the repository).

Read-only gate (psycopg `READ ONLY` transactions, no URL printed): host equals the dev host and ends in `.neon.tech`; database name exactly `neondb_test` (dev is `neondb`, a separate database); the role owns the database and is not a superuser; PostgreSQL 18.6; no other
sessions; 21 user tables, all empty except `alembic_version` (1 row, revision `e5b1c7d93a20`, the single Alembic head), so there was no data to preserve; no database comment marks it disposable, so disposability rests on the repository's designation
(`tests/backend/conftest.py` uses `TEST_DATABASE_URL` exclusively, every test runs in a rolled-back outer transaction), the owner's instruction, and the empty contents. The dev database was never connected to.

Run (a guarded runner set BOTH `TEST_DATABASE_URL` and `DATABASE_URL` to the test URL for child processes only, and refused to start unless the effective Settings resolved to `neondb_test` on the same Neon host):
`ALEMBIC_TARGET=test alembic current` exit 0 -> `e5b1c7d93a20 (head)`; `ALEMBIC_TARGET=test alembic upgrade head` exit 0 (no-op, already at head); `alembic current` exit 0 -> same head;
`pytest tests/backend/api/test_monthly_records.py -v` exit 0, **53 passed, 2 warnings (third-party deprecations), 325.72 s** (about 6 s per test over the network). A first attempt was stopped by an external 115 s timeout at test 11 (not a test failure);
a read-only re-inspection afterwards showed the database unchanged (still only the `alembic_version` row, 0 other sessions). This does not cover the full suite or the `real_client` tests, which also read `neondb`.

#### Isolated database-backed suites on `neondb_test` (2026-10-20): 569 + 53 passed, development database not used

Classification by fixture implementation (`tests/backend/conftest.py`, `tests/backend/api/conftest.py`): **category 1** (isolated: `client`/`db_session`/`db_connection`/`make_customer` bind to `TEST_DATABASE_URL`, rolled-back outer transaction): `tests/backend/api/` (goal_period_frequency, household_finance_metadata, household_finances, household_goals, household_summary, households,
monthly_records, profiles, qa, rfc7807, scenarios, seed_demo_data, sse, and the non-real tests of analysis), `tests/backend/db/` (all six files), `tests/backend/data/test_ingestion.py`. **Category 2** (development database; NOT run): `real_client`/`real_db_session`/`real_session` -- 2 tests in `api/test_analysis.py` and 91 tests in six agent files that call `get_engine(settings.database_url)`
(`test_compliance_gate_safety`, `test_financial_inputs_integration`, `test_graph_execution`, `test_graph_safety_contracts`, `test_nodes`, `test_recommendation_node`; some tests in them may be DB-free but share the fixtures). **No database access** (inspected, not run here): `api/test_health.py`, `api/test_lifespan.py` (static health data; artifact loading), `api/test_personalized_insights.py` (stub session), `db/test_migration_history.py` is structural.
Not DB-backed and covered elsewhere: core, training, scripts, data/gdelt.

Run mechanism (outside the repository): a pytest plugin that deselects any test whose fixture closure includes a `real_*` fixture, wraps the engine factory so any engine not pointing at exactly `neondb_test` on the expected Neon host raises, and adds TCP keepalive/`tcp_user_timeout` to connections; a runner that sets BOTH `TEST_DATABASE_URL` and `DATABASE_URL` to the test URL and `ALEMBIC_TARGET=test` for child processes only and
refuses to start unless the effective Settings resolve to `neondb_test`. No URL was printed. Result: 569 category-1 tests (excluding `test_monthly_records.py`, 53 passed earlier) all passed, 0 blocked engine attempts, every engine created was to `neondb_test`; no migration was run (head `e5b1c7d93a20` already applied).
Transient infrastructure failures, each classified from its traceback (`psycopg.OperationalError ... server closed the connection unexpectedly`, not an assertion) and each passing when re-run alone: `test_household_finances.py::test_missing_required_fields_are_422[income-payload0]` and `::test_unknown_household_is_404_on_every_route[expenses]` (setup) -- 16 passed re-run;
`test_households.py::test_unknown_household_is_a_404_and_a_non_member_gets_a_403` (a 673 s call that ended in a dropped connection) -- 1 passed in 7.29 s. A single query also hung silently for 18 minutes on a dead Neon connection; that run was stopped and resumed with keepalives, and the first slow `test_analysis` failure in the interrupted run is likewise attributed to the connection (it passes alone). Chunk durations: 58 min for the large chunk, 78 s for `test_analysis`, 114 s and 7 s for re-runs.
A read-only re-inspection afterwards: only the `alembic_version` row exists, 0 other sessions. The runner and plugin used for this run were temporary; the committed, tested version is described in the next section.

#### Reproducible isolated runner: `scripts/run_isolated_db_tests.py` (2026-10-20)

```
python scripts/run_isolated_db_tests.py --preflight                      # resolve + report host and database only; no database access, no tests
python scripts/run_isolated_db_tests.py --preflight --check-connection   # plus one read-only `select current_database()`
python scripts/run_isolated_db_tests.py --suite api --suite db           # selected suites (default: api, db, ingestion); extra pytest args after `--`
python scripts/run_isolated_db_tests.py --alembic current                # read-only; ALEMBIC_TARGET=test is set for this command only
python scripts/run_isolated_db_tests.py --alembic upgrade --confirm-migrate   # never automatic; needs the explicit flag
```

Reads `TEST_DATABASE_URL` / `DATABASE_URL` from the process environment, falling back to `.env` (the process environment wins, like the application's Settings), or `--env-file`. `scripts/isolated_db/guard.py` accepts exactly one target:
database `neondb_test` on a `.neon.tech` host equal to the expected host (`--expected-host`, else `WEALTHPILOT_EXPECTED_TEST_DB_HOST`, else the host of `DATABASE_URL`). It refuses a missing or empty URL, `neondb` or any other name, an unknown host or a different Neon host, several hosts,
a query string that could override host or database (`host`, `hostaddr`, `dbname`, `service`), a non-PostgreSQL or unparsable URL, and a target whose expected host cannot be confirmed; it then asks the application's own Settings (no database access) to confirm the same host and database.
The child process gets BOTH URLs set to the test URL (so an unexpected use of `DATABASE_URL` lands on `neondb_test`, never `neondb`) and no `ALEMBIC_TARGET` unless an alembic command is requested. The pytest plugin (`scripts/isolated_db/pytest_plugin.py`) deselects every test whose fixtures
reach the development database (`real_*`), raises for any engine that is not exactly the resolved target, and adds configurable TCP keepalive arguments (`--keepalive-idle/-interval/-count/-user-timeout-ms`, `--no-keepalive`) to the TEST connection only; fixtures and their rollback are not touched.
Suites exclude the six agent files that call `get_engine(settings.database_url)` and the DB-free API files (`test_health`, `test_lifespan`, `test_personalized_insights`). Nothing printed contains a URL or password; the runner never drops, truncates or migrates on its own.
Guard tests: `tests/backend/scripts/test_isolated_db_runner.py` (46 tests, fake URLs only, no network). Verified 2026-10-20: real preflight resolved `neondb_test` and matched Settings; read-only connection check connected to `neondb_test`; with `TEST_DATABASE_URL` set to the development URL and with no configuration the preflight exited 2 with a refusal;
`--suite ingestion` 4 passed (24.75 s, 0 blocked engines) and `--suite db -k household_models` 23 passed (147.79 s, 0 blocked engines). The 622 earlier results were not repeated. The 93 development-database tests stay excluded.

#### Demo-manifest guard regression (found and fixed 2026-10-20, ADR-045)

`test_validate_demo_data.py::test_regenerating_the_manifest_is_byte_stable` and `::test_the_manifest_guards_every_raw_training_file` failed because the guard hashed every file under `datasets/raw/`, which now includes 547 files of the GDELT sentiment acquisition area (a live SQLite manifest with `-wal`/`-shm`, run logs, filtered output; not a training dataset, with its own provenance and manifest).
Fix: an explicit boundary, `GUARD_EXCLUDED_RAW_SOURCES = {"gdelt"}` in `backend/scripts/validate_demo_data.py`, with `guarded_raw_files()` as the single definition of scope; every other raw source, including any new one, stays guarded. `demo_data/manifest.json` needed no regeneration and stayed byte-stable. After the fix: `pytest tests/backend/scripts/test_validate_demo_data.py` 57 passed (25.67 s), `python backend/scripts/validate_demo_data.py` reports DEMO DATA VALID with 10 raw training files unchanged.

#### Dry-run package and documentation audit tests (2026-10-20)

`tests/backend/scripts/test_dry_run_package_audit.py` (16 tests, offline): excerpt holds annotator material only and its leak patterns are live; markers missing, nested or unbalanced raise; stale package copies and stale excerpts are detected even if the manifest hash is rewritten; two rebuilds are byte-identical with no timestamp; no Python source contains a stray control character (0x08 had silently replaced regex `\b` in three tests/scripts);
the A1-A11 classes match the decision sequence; O1/O4 approval stays limited to the fictional dry run in every document; O2/O3/O7 stay unresolved and O5/O6 PROPOSED; unsupported-language handling is stated as annotation policy, not baseline behaviour; no document claims agreement, completed annotation, validation, freezing, distribution or readiness for real text.
Hazard to remember when editing tests or scripts from a shell heredoc: backslash sequences can be altered in transit (`\b` became a backspace, `\n` a real newline); write such files with the editor tools and run the control-character test.

#### Adversarial and mutation tests for the dry-run package (2026-10-20)

`tests/backend/scripts/test_dry_run_package_adversarial.py` (58 tests; 1 skipped where symlinks need a privilege, with a privilege-free equivalent beside it) attacks `scripts/build_dry_run_package.py`: bad marker layouts (missing, unbalanced, reversed, nested, duplicate, empty, misspelled), altered package files with the manifest hash also rewritten, a manifest that lies about counts or hashes or is malformed,
extra/missing/hidden/path-like/symlinked entries, leakage through headings, comments, JSON metadata and template cells, CRLF vs LF checkouts, byte-identical rebuilds, and registers with a missing or invalid attestation date, duplicate codes (case/space-insensitive), BOM, wrong columns or failed independence. Every case has a clean CONTROL and one mutation.
Defects this exposed and fixed in the builder: no check of the attestation date; a spreadsheet BOM rejected the register; manifest `text_count`, `ids_sha256` and `rubric_excerpt_sha256` were never checked; extra keys or pre-filled labels in the texts/template were not refused; symlinks were followed; `build` left unexpected files and reported success; a malformed manifest crashed `verify`; hashes depended on line endings;
a misspelled marker silently shrank the excerpt; hyphenated author headings and ambiguity ids passed the leak words; errors were tracebacks. Documented rules are in the script's docstring; no participant eligibility rule was added (the register stays the owner's own attestation, which the tool cannot verify).
`tests/backend/scripts/test_regression_tests_are_effective.py` (22 tests) runs the real regression tests against bad fixtures and mutations (a backspace for a word boundary, a never-matching or weakened regex, planted control bytes in every scanned file class) and requires them to fail, with clean controls that must pass.

#### Financial behaviour & sentiment feature: frontend tests (2026-10-21)

The frontend had no test framework (no vitest, jest, Testing Library or browser runner) and none was added. `npm test` (from `frontend/`) uses only what is installed: Node's built-in test runner (Node 24 runs TypeScript directly), Vite's SSR loader and `react-dom/server`.
`tests/user-text-input.test.ts` (24 tests) covers the pure input rules and transitions in `src/lib/user-text-input.ts`: the 1000-character limit and the control-character class are cross-checked against the backend SOURCE code point by code point; blank input is sent as no text; invalid or duplicate submissions are refused; Clear forgets the text;
stale results are detected; `uncertain` is never shown as neutral; confidence is never shown as 0; and source scans enforce the privacy boundaries (no browser storage, cookies, URL, console, beacons or env flags; query `gcTime: 0`, text only in the in-memory key; the card keyed by profile; the POST body and route match the client).
`tests/component.test.mjs` + `behaviour-sentiment-view.cases.tsx` (22 tests) render the real components to static HTML for every state: records only, conflict, uncertain, mixed-language cue, no records, no assessment, loading, error with earlier data present, unreachable service, stale and pending results, validation and limit messages, hostile and unusual text, an unrecognised sentiment value, a provided confidence, accessibility wiring, and the card wired to a seeded cache.
Every response they render is a REAL backend response captured by `scripts/export_insight_fixtures.py` (`frontend/tests/fixtures/*.json`, synthetic figures and invented sentences, no mock data); `tests/backend/api/test_personalized_insights_hardening.py` fails if a fixture drifts from the backend.
`npm run test:mutations` applies 43 in-memory mutations (no file touched; Node module hooks for the logic, a Vite plugin for the components) and requires every one to be detected, after an unmutated control passes: 43 of 43 detected (one equivalent mutant, removing an explicit `aria-hidden` that lucide-react adds itself, was replaced by a real accessibility mutation).
`tsc -b` also type-checks `tests/` through `tsconfig.test.json`. NOT covered, because no DOM or browser is available and none was added: typing, focus movement, clicking, real layout at different widths, and visual appearance. No browser-based visual testing was done.

Backend additions: `tests/backend/api/test_personalized_insights_hardening.py` (33; stub session, no database) and `tests/backend/core/test_user_text_sentiment_edges.py` (65). Together they cover wrongly typed or shaped bodies, blank and boundary text, every control character, exact version/source metadata, no logging or writes (AST checks), isolation from compliance/recommendation/agents in both directions, no table or migration for user text, generated-type and client-call consistency with the OpenAPI schema, and the classifier's conservative edge cases (pinned as characterisation of the unvalidated baseline, not accuracy).
Mutation spot-checks of the backend tests (6 effective mutations, e.g. restoring the 422 echo, changing the data source or the limit, serving a validated status or an invented confidence) were all detected. Offline run on 2026-10-21: `pytest tests/backend/core tests/backend/api/test_personalized_insights.py tests/backend/api/test_personalized_insights_hardening.py tests/backend/api/test_health.py tests/backend/api/test_lifespan.py tests/backend/scripts` 767 passed, 1 skipped; `npm test` 46 passed; `npx tsc -b` and `npm run build` exit 0; `npx oxlint` 0 errors, 8 pre-existing warnings. Generated `types/api.ts` is byte-identical to a fresh generation from the live schema.

#### Real-browser verification and the dedicated Financial Behaviour & Sentiment page (2026-10-21)

**What was run in a real browser.** `agent-browser` (installed globally, driving the installed Chrome) against the Vite dev server (`npm run dev`) and the real FastAPI app on a throwaway LOCAL SQLite file via `scripts/local_synthetic_backend.py --db <file>.db`: it puts a SQLite URL (and a blank `GEMINI_API_KEY`) in the process environment before the app is imported, so `.env`, Neon and Gemini are never touched; the schema comes from the models (no migration), with the three PostgreSQL-only constructs translated for SQLite only.
The FAR-Trans and market-data tables are empty, so the real pipeline answers `pending_information`; a stored assessment (one synthetic row) and four monthly records were inserted into that local file; the populated analysis pages were not exercised with real pipeline output.
Scenarios passed: sign-in with the demo account; Financial Health summary and link; the new page via link, sidebar and the phone off-canvas sidebar; typing, counter, 1,001/1,000 characters, a control character, Enter and button submit, Clear; duplicate submits while pending (1 POST for 1 click + 3 Enter presses); results compared with the API response (21/21 values); loading, error (unreachable, 400/422/500) with retry, empty and no-record states;
profile switching by sign-out/sign-in without a page reload (no text, marker or earlier results carried over); privacy (marker absent from `localStorage`, `sessionStorage`, cookies, IndexedDB, cache storage, URL, request URLs, console and server logs); desktop 1366, tablet 820 and phone 390 (no horizontal overflow); keyboard tab order, visible focus rings, Enter on links; accessible names; a sweep of all 18 routes at two widths (console errors, failed API calls, unnamed controls, overflow, placeholder words, stuck loading).
**Defects found and fixed in that pass:** (1) the status sentence was cut off on phones (non-wrapping badge); (2) `Button` rendered as a `Link` logged a Base UI error on 6 pages (10 call sites, now `nativeButton={false}`) and the new summary link would have been announced as a button (now a plain link with `buttonVariants`);
(3) Create User, both onboarding pages and Login had no `<main>` landmark; (4) Create User had `noValidate` and no validation, so empty or invalid values reached the API as a generic error (now `lib/profile-form.ts`, mirroring the backend schema, field-level messages, focus on the first invalid field); (5) on a phone the sidebar sheet stayed open over the page after choosing an item (now closes);
(6) "Clear" was enabled with nothing to clear. **Not verified / known:** the 10 `Button`-as-`Link` sites still announce as buttons; the populated Risk, Portfolio, Recommendation, Why and Scenario pages were swept structurally only; native date and month inputs could not be driven by the tool's `fill`; visual design was inspected on screenshots, not against a design file.
**Commands (from `frontend/` unless stated):** `npx tsc -b` exit 0 (includes `tests/`); `npx oxlint` 0 errors, 8 pre-existing warnings; `npm run build` exit 0; `npm test` 81 passed (user-text input 24, profile form 12, summary/routing/nav 12, component cases 33); `npm run test:mutations` 67 of 67 mutations detected;
from the repo root `pytest tests/backend/core tests/backend/api/test_personalized_insights.py tests/backend/api/test_personalized_insights_hardening.py tests/backend/api/test_health.py tests/backend/api/test_lifespan.py tests/backend/scripts` 767 passed, 1 skipped.

## 25. Sensitive-Data Protection Prototype (ADR-047, 2026-10-21)

Design and limits: `docs/THREAT_MODEL.md`. All fixtures are synthetic; every encryption key is random bytes generated while the
test runs (nothing is stored). No test in this section connects to the development database (`neondb`).

**DB-free (SQLite file in pytest's temp directory, no network)** -- `tests/backend/security/`:

```
.venv\Scripts\python.exe -m pytest tests/backend/security -q -p no:cacheprovider
```

| File | Covers |
| --- | --- |
| `test_crypto.py` (43) | round trip (incl. unicode/empty); ciphertext does not contain plaintext; 200 fresh nonces; envelope matches standard AES-256-GCM via an independent decrypt; modified ciphertext/tag/nonce/length; moved record id / owner / purpose; swapped key id; wrong key; unknown key id; malformed/downgraded envelopes; no key => fail closed, no default; malformed key configuration; rotation; size bound; encryption failure returns nothing; self-test is a real round trip; no plaintext/key/nonce in errors, reprs, settings or logs |
| `test_ledger.py` (39) | exact canonical bytes and hash vector; every field affects the hash; UTC normalization; empty / genesis / valid chains (multi-batch); modified payload, field, hash, previous-hash link; removal from the middle and the start; reordering; unknown schema version; fixed non-sensitive reasons; **newest-event removal and a full privileged rewrite still verify locally (documented limitation) and are caught only by an external head**; closed event allow-list and UUID-only references; stale-head append raises and the session stays usable; 6 concurrent threads produce one gapless valid chain |
| `test_anchor.py` (4) | the shipped anchor is "not configured", refuses submissions, fabricates no receipt; commitment carries only position + hash; local commitment-vs-event verification |
| `test_protected_notes_api.py` (47) | owner create/read/update/delete; audit order; metadata-only listing; `no-store`; plaintext absent from every stored byte; fresh nonce per update; 401 for missing/unusable identity on every route; 403 for another identity on every route with nothing changed; foreign / unknown / malformed record ids give identical 404s; ciphertext copied to another owner does not decrypt; no route exposes events; denial auditing; fail-closed (no key, encryption error, audit failure => atomic rollback, tampered ciphertext, retired key, failed commit); 422s never echo text; no plaintext or key in logs; security-status truthfulness (operational / empty / tampered / no secrets / no ledger write) |
| `test_boundaries.py` (7) | no agent / LLM / core / data / training module can reach the security package or key settings; key settings read in exactly two files; no blockchain/wallet SDK; only dependency added is `cryptography`; log calls are fixed text; ledger module names no sensitive field |
| `test_status_fixtures.py` (3) | the frontend's security-status fixtures equal what the real route returns today |
| `test_unmigrated_storage.py` (4) | a database without migration `f7a2d4b6c810` answers every route with a 503 naming the missing migration (no 500, no table created, nothing saved or logged as unhandled), identity is still checked first, and the same routes work once the tables exist (2026-10-22) |

Last recorded: **`147 passed`** (2026-10-23). DB-free regression group (`tests/backend/core`, `security`, `scripts`,
`db/test_migration_history.py`, `api/test_personalized_insights*.py`, `api/test_health.py`, `api/test_lifespan.py`): **`930 passed, 1 skipped`** (2026-10-23);
`tests/backend/data/gdelt`: `1492 passed`; `validate_demo_data.py`: `DEMO DATA VALID`; `scripts/export_security_fixtures.py --check`: `fixtures current`.

**DB-free elsewhere**: `tests/backend/db/test_migration_history.py` (single head `f7a2d4b6c810`; the migration creates only its two
tables and touches no existing table; downgrade drops exactly them).
Demo data: the manifest records the Alembic head, so `backend/scripts/validate_demo_data.py` and its manifest were moved to
`f7a2d4b6c810` (data-only metadata); `validate_demo_data.py` => `DEMO DATA VALID`.

**PostgreSQL (isolated Neon TEST database only)** -- the migration was applied to `neondb_test` with the guarded runner
(`python scripts/run_isolated_db_tests.py --alembic upgrade --confirm-migrate`; `--alembic current` => `f7a2d4b6c810 (head)`). It
has **not** been applied to `neondb` (the owner must run `alembic upgrade head` for `DATABASE_URL`).

```
python scripts/run_isolated_db_tests.py --suite api -- tests/backend/api/test_protected_records_postgres.py
python scripts/run_isolated_db_tests.py --suite api --suite db --suite ingestion     # the full isolated regression
```

`tests/backend/api/test_protected_records_postgres.py` (4) covers what only PostgreSQL shows: the real schema, the advisory-lock path,
bytea / timestamptz round trips, the UNIQUE backstop, and notes owner-scoped through the real stack.

**Isolated database-backed regression (2026-10-22, `neondb_test` only, 0 development-database tests, 0 blocked engine attempts)**: run
file by file through `scripts/run_isolated_db_tests.py` (an earlier single-process attempt was lost when the working session restarted at
17 %, 117 passed / 0 failed, and is not counted). 23 files (api 16, db 6, ingestion 1), **665 passed and 1 failed on the first pass**. The one failure,
`test_households.py::test_profile_household_shows_a_non_primary_members_own_role`, was `psycopg.OperationalError: server closed the connection
unexpectedly` (a connection-level error, not an assertion); it passed alone (`1 passed`) and the whole file passed in isolation afterwards
(`51 passed`). This is the known transient-network artifact above, not a regression. **No single uninterrupted 666-test run was performed**; the
claim is per-file clean runs plus that isolated re-run. The 3 live-Gemini tests are outside these suites.

**Agents and training (2026-10-23)**: `tests/backend/agents` file by file through the guarded runner: 187 passed, 0 failed, 3 skipped (live Gemini); 42 tests that use
development-database fixtures were deselected by the runner (never run against `neondb`). `tests/training`: 99 passed. Caveat: `--suite X -- <path>` also collects the
suite's own directory, so a one-file run needs a one-file suite registered (the runner is unchanged). See `reports/integration_requirements_audit_2026-10-22.md`.

**Not run**: the 42 development-database agent tests above.

**Frontend** (`frontend/`): `npx tsc -b`; `npm run typecheck:tests`; `npx oxlint`; `npm run build`; `npm test` (structural tests in
`tests/security-status.test.ts`, rendered-state cases in `tests/security-status-view.cases.tsx` against real recorded backend responses);
`npm run test:mutations` (21 added mutations D1-D21, each of which must make a test fail; one initially survived because no fixture had a
failed self-test, and a fixture was added). Browser verification: performed once against the offline SQLite launcher
(`scripts/local_synthetic_backend.py`, random key, synthetic customer, no Neon, no Gemini): operational view, the tampered-chain view and
390 px / 1366 px layouts were checked. Regenerate fixtures with `python scripts/export_security_fixtures.py` (`--check` to verify).

**Mutation check of the backend tests**: 20 source mutations (AAD drops owner / key id, constant nonce, shape check removed, previous-hash and
recomputed-hash checks removed, UUID restriction removed, sequence left out of the hash, external head ignored, sequence gap ignored,
identity check removed, owner scoping removed, audit event removed, 422 echo restored, cacheable responses, status not verifying the chain,
access logged before decryption, nonce reuse on update, denial logged as access, fixed fallback key) were applied one at a time; all were
caught except one equivalent mutant (a different fail-closed path), and a hardcoded fallback key was checked separately and caught.

**Financial Behaviour & Sentiment page redesign (ADR-048, 2026-10-22)**: `tests/behaviour-sentiment-view.cases.tsx` (rendered states against real recorded backend responses: intro, text area, insight rows with category/direction/sources, conflict and authority wording, separate assessment region, inconclusive vs found styling, empty/one-month/loading/error states, input stays usable after an error, line breaks, counter and validation without echo, accessibility wiring, responsive classes and order, hostile text) and `tests/behaviour-redesign.test.ts` (insight selection against every fixture, submit shortcut, inconclusive flag, no arithmetic / fetching / storage / URL / console / analytics in the new files, no `maxLength`, CLI-added Textarea and no new dependency, generated types only). Run with `npm test` from `frontend/` (133 passed).
**Mutation runner fix**: `tests/mutation-check.mjs` now verifies, before running, that every mutation's target text exists (line endings normalised), and the two loaders report a missing target as "not applied" (exit 3) instead of throwing, because a throw looked like a failing test. This revealed earlier mutations that had never applied (the route and navigation entries, and one summary mutation) and counted as kills; they were re-pointed. Current result: **110 of 110 detected**. The earlier "88 of 88" for the data-protection page was therefore partly overstated (D2 and D3 had not applied); the re-run covers them.

**Not tested / not claimed**: penetration testing, load testing, an independent review, PostgreSQL concurrency with real parallel
connections (concurrency is exercised on SQLite threads and, for the unique backstop, on PostgreSQL), and the full application in a browser
with a real PostgreSQL database.

## 26. Full-Pipeline Demo Persona (ADR-049, 2026-10-23)

Persona E ("WealthPilot Demo — Full Pipeline"), its monthly records, the stored-assessment fallback and the sign-in entry. No test connects to `neondb`.

| File | Covers |
| --- | --- |
| `tests/backend/scripts/test_full_pipeline_persona.py` (12) | persona facts; coherence with the linked customer's own type and capacity; goals; inputs; twelve consecutive months within income; no risk category or result in any persona file; the link is a real FAR-Trans customer used by no other persona; its dataset label is a genuine `Balanced` (never `Predicted_*` / `Not_Available`); 100+ transactions over 12+ months; a valid point-in-time feature row; the existing model returns the dataset's own label above the information threshold; an unlinked profile gets no row and no invented category |
| `tests/backend/pipeline/` (16) | the REAL app, models and FAR-Trans data on a throwaway SQLite file with **test-only synthetic prices** (no network, Gemini blanked): found by exact name; risk result; graph runs past the information-request node (agent log); goals evaluated; portfolio valid; recommendation follows the risk category (equal weight, 1/3 each); compliance PASS with 5+ rules; a REJECT keeps recommendation and explanation out of the response for every persona; the explanation never supplies a number; monthly behaviour findings equal the test's own arithmetic on the persona file; the stored assessment comes from the latest analysis (and an explicit `risk_assessments` row still wins); a growth wish against a Conservative assessment is a conflict and the analysis does not move; persona D stays pending with nothing invented; profile ids never mix; re-seeding creates nothing and never overwrites a month the user changed |
| `tests/backend/scripts/test_validate_demo_data.py` (+10 planted defects) | skipped / repeated / malformed months, spending beyond income, invented or negative fields, a missing amount, too few months, an unknown persona, income that contradicts the profile are each reported |
| `tests/backend/api/test_seed_demo_data.py` (isolated PostgreSQL, 34 passed) | five personas, four resettable, a second `setup` creates nothing (5 customers, 12 monthly records, 4 links) |
| `frontend/tests/demo-login.test.ts` (6) + mutations G1-G7 | the sign-in entry exists, finds only (no create), its name equals the backend package's, it is not a switcher, an unseeded environment is explained |

Results (2026-10-23): DB-free group (`core`, `security`, `scripts`, `pipeline`, migration history, insights, health, lifespan) **968 passed, 1 skipped**; `validate_demo_data.py` DEMO DATA VALID
(5 personas, 36 files); isolated `test_seed_demo_data.py` **34 passed**; frontend `tsc -b` 0, `typecheck:tests` 0, `oxlint` 0 errors / 8 existing warnings, build OK, `npm test` **141 passed**,
`npm run test:mutations` **119 of 119** (pre-flight verified); backend mutation check of the new code 7 of 7 caught; generated types identical to a fresh generation.
Browser (offline SQLite launcher, real UI sign-in): Risk, Portfolio, Recommendation, Goals, Why, Behaviour & Sentiment, Financial Health at 1366 px and Risk / Portfolio / Recommendation / Goals / Why /
Behaviour at 390 px, no horizontal overflow, values equal to the API response. Not run: the live Gemini explanation (no key in the offline launcher).

## 27. Financial Behaviour & Sentiment: Multi-Stage Interpretation (ADR-050, 2026-10-23)

No test touches a database or `neondb`; the insight tests use a session stub that fails on any use, and no network is used.

| File | Covers |
| --- | --- |
| `tests/backend/core/test_user_text_interpretation.py` (59) | relevance (relevant / unrelated / ambiguous); quality and language gates and their boundaries; negation, past feelings, other people, quotations, conflicting cues; frustrated / calm tones; the extended topics; every preference with bounded unconfirmed evidence; stance-verb rule; no preference from weak or unrelated text, from a negated statement, or from a feeling; opposing preferences withheld; evidence sanitising and bounds; the model seam (fallback, invalid readings, calibrated confidence only, own abstention threshold, never asked after an earlier abstention) |
| `tests/backend/core/test_user_text_rubric_hypothetical.py` (34; 20 from the fifteenth brief plus 14 added on 2026-10-29 for rule 13, the open "even if" record, the comma-less disagreement and the baseline behaviours of decision-sheet items AP1 to AP3, AP8 and AP9) | rules 11 and 12 of the annotation rubric are in the annotator excerpt with the six stated examples and outcomes; rules 1-10 and the label sets are unchanged; no author-only wording leaks; the rubric claims neither validation nor a freeze; the baseline gives no label, tone or preference for hypothetical, wish, negated-hypothetical, quoted and third-person hypothetical text; a current clause beside a hypothetical one is labelled; current statements unchanged; the one documented rubric / baseline disagreement ("even if") is still real and documented |
| `tests/training/sentiment/test_sentiment_policy_gates.py` (43) | the owner-approved `EvaluationPolicy` holds exactly the decided values (None = explicit NO_FLOOR / REPORT_ONLY), `approved=True` is refused for any tampered value, every field is required; `assess_against_policy`: the only route to `validated`, each evidence condition and each support, target, coverage, abstention, recall-floor, calibration and agreement gate with its boundary, abstention-gaming blocked, strict and accepted-only calibration distinct, the four validation words, informational gates, deterministic gate order; 23 in-memory mutations all detected; the four decided fields, the strict view deciding the macro-F1 gate, the lower-bound decision and the informational gates are covered |
| `tests/training/sentiment/test_frozen_evaluation.py` (40) | the frozen-set plumbing on sets generated in the test: hash verification of records, rubric and log (line-ending independent), manifest fields and types, record shape (no text in any message), declared counts, three splits required, exact and near-duplicate exclusion with an inclusive threshold, flags carried into the evidence basis (unapproved, synthetic, fixture, draft rubric, unattested all `not_validation_evidence`), prediction coverage, pre-adjudication ratings, the full chain, reproducibility, isolation; the confirmed schema (purpose, licence, provenance, creation timestamp, record-id / content / label / split hashes recomputed, annotator manifest, immutable manifest hash, declared evidence status compared, personal-data markers refused, missing or unknown schema version refused first); 20 in-memory mutations all detected |
| `tests/backend/core/test_consolidated_approval_form.py` (52) | the consolidated approval form's recorded state (each of the 55 entries exactly one of APPROVE / REJECT / KEEP UNRESOLVED / BLOCKED; only E1 and E2 approved, with the exact requested values; C1 to C4 blocked; F1 and the other 49 unresolved; no recommendation taken as an answer; no revision in an entry) and its dependency rules, on the real form and on invented answer sets: no phase unlocked today; a rejected, blocked or unresolved item never unlocks a phase; no download without an approved model with all its items, the metadata, D10 to D13, the cache location and E1; no evaluation without D1 to D20, a frozen manifest and the earlier phases; activation only with its own F1 approval; `validated` unreachable without E2; the Phase 2 gate under Option 2: exactly one candidate selected, B2 (the identifier), A3.9 to A3.13 and B1 to B10 approved, A3.1 to A3.8 provisional (not required for Phase 2, all required before a download), C / D / E / F neither needed nor unlocked, E1 fetch-only, metadata authorisation unlocking no file access or download, the approved query values (fields, 10 requests, host, redirects, anonymous, storage, seven stop conditions), the read-only owner constraint and the corrected B3 candidate; the standing rules, the hard gates and the findings stated in the text |
| `tests/backend/core/test_user_text_polite_forms.py` (30) | AP8 `CONTEXT_DEPENDENT`: current polite forms accepted; conditional, counterfactual and trailing-condition polite forms withheld (if, unless, provided that, as long as, assuming, and only if, but only if); a later sentence does not withhold an earlier form; a current polite form beside a conditional one keeps only the current; quoted, third-person and negated forms give no preference; the change is limited to the two polite phrases; a model is never shown the withheld clause; 7 in-memory mutations all detected |
| `tests/training/sentiment/test_hub_fetch.py` (98) | the offline E1 fetch step and restricted B9 metadata query (`hub_fetch.py`) with a scripted transport and a loopback server only, never a real host: policy validation, host allow-list on every request and redirect, the request cap, only three metadata URL kinds, authentication / identifier / revision / licence stops, sanitised records, per-file hash and size checks, allow-listed file formats (pickle-capable refused), destination outside the repository, rollback; 27 of 27 deliberate defects detected (the last two guard the dot-file listing fix) |
| `tests/training/sentiment/test_local_model_dir.py` (56; 1 skips without symlink privilege) and `test_local_model_dir_standin.py` (5; skipped without torch, 5 passed in the disposable S1 environment: real libraries, random local stand-in, socket / Hub / pickle / `torch.load` / cache guards, trainer and evaluation-script wiring) | the prepared Path B loader on synthetic local fixtures only: exact five-file directory, no pickle-capable or unknown file, no link or sub-directory, per-file hash and size, tampered or malformed manifest, floating revision, pinned identifier / revision, label order from the verified config, stable softmax, load parameters (`local_files_only`, no remote code, safetensors, CPU, the directory as the only reference), re-verification before load, E2-format payload accepted by the real loader, import and no-network boundary; 22 of 22 deliberate defects detected; the Path B wiring in the trainer and evaluation script (tests in `test_transformer_training_seam.py` and `test_evaluate_frozen_mode.py`): 9 of 12 detected, 3 equivalent |
| `tests/backend/core/test_s1_pin_list_records.py` (5) | the recorded S1 package set: the executed 35-wheel list with `setuptools==81.0.0` and `certifi` 2026.10.23 is authoritative, the early 84.2.1 table is superseded, six direct packages are not a sufficient `--require-hashes` set |
| `tests/backend/core/test_user_text_robustness.py` (12) | seeded arbitrary input (no real text): `analyse_user_text` either raises the two documented refusals without echoing the text or returns an analysis inside the contract (bounded masked evidence, no confidence, abstention shape, deterministic) |
| `tests/training/sentiment/test_evaluate_frozen_mode.py` (29) | the script's frozen-set mode on generated fixtures, including owner decision E2 (probability-bearing predictions: all-or-none per file, exact classes, finite values in [0, 1], sum 1, label = most probable class, nothing echoed; the rules baseline never carries probabilities; 9 of 11 loader and wiring defects detected, the other two behaviourally equivalent) and: one report, no record text or id anywhere, exit status independent of any target, precomputed predictions compared with the rules baseline without a winner, a tampered set refused before evaluation, a model artifact refused, uncovered predictions refused without echoing the file, the five arguments required, no command-line way to state the evidence, and the script imports nothing from the API, settings, agents or security |
| `tests/backend/core/test_evaluation_policy_records.py` (7) | each of AP1 to AP9 records its exact decision (and the comma-less rule under AP6), none blank, no invented number, no use of the original decisions' row label; the "even if" item names its three outcomes and records `KEEP_DOCUMENTED_DIFFERENCE`; the approval record holds all 26 statistical decisions each stated or adopted; the approved values appear in code only in the two owner-approved mappings and no identifier can enable, rank or select a model; the evaluation script is not connected to the statistics, the frozen plumbing, the API, settings or agents |
| `tests/backend/scripts/test_rubric_hash_records.py` (2) | the pilot-pack manifest records the current SHA-256 of the edited rubric and of its annotator excerpt, still says DRAFT / not frozen / not started, `builder.verify()` is clean, and the texts, template and instructions hashes are unchanged |
| `tests/training/sentiment/test_sentiment_statistics.py` (40) | the offline evaluation statistics against hand computations: perfect / imperfect / abstaining candidates, empty and one-class input, undersized groups and the support boundary, deterministic ordering, Wilson and bootstrap interval boundaries, kappa / Krippendorff alpha / specific agreement, calibration bins and ECE, rules-versus-model comparison, evidence eligibility, no fabricated, validated or pass / fail value, no new dependency; 22 in-memory mutations all detected |
| `tests/backend/core/test_user_text_hypothetical.py` (20) | hypothetical and conditional feelings and preferences are never a current view (10 + 4 texts), a current feeling beside a hypothetical one, consequent carry-over across a comma but not across a sentence or a contrast, indirect questions and idioms are not conditions, topics still reported, a model is never shown a hypothetical clause and cannot label a hypothetical-only text; 8 in-memory mutations all detected |
| `tests/backend/core/test_sentiment_ledger_boundary.py` (5) | no sentiment / insight / model / training module imports `wealthpilot.security` or names a ledger, anchor or blockchain; the security package imports none of them; the ledger event, head and payload shapes have no field that could carry sentiment, text, evidence, preference, label or risk data; `append` takes only an event type and an opaque reference |
| `tests/backend/core/test_user_text_sentiment.py`, `..._edges.py` (rewritten deliberately) | the documented example, taxonomy, unavailable vs abstained vs uncertain, determinism, input limits and control characters, supersession of the old "English cue word in another language is labelled" characterisation |
| `tests/backend/core/test_behaviour_findings_and_insight.py` | structured conflict fields, abstention caveats, abstained reading never makes the insight complete |
| `tests/backend/api/test_personalized_insights_interpretation.py` (24) | response contract per state; fallback with a failing model (no text or exception in the response); a calibrated model is the only source of confidence; the stored assessment is authoritative whatever the text; structured unconfirmed conflicts; the insight path imports no analysis / recommendation / compliance code and writes nothing; RFC 7807 400 / 422 / 404 without echo; backward-compatible fields; no text in logs, URLs, headers or metadata; evidence bounds; no network |
| `tests/backend/api/test_personalized_insights*.py`, hardening | updated versions (`personalized_insight_v2`, `user_text_rules_v1`), generated-type check for boolean constants, fixtures equal to what the backend returns today |
| `frontend/tests/user-text-input.test.ts`, `behaviour-sentiment-view.cases.tsx` | exact required messages (and the backend copies of the shared ones), the five presentations, "Not available" confidence, method / validation / limitations always shown, fallback, abstention, weak vs valid, conflict with authority wording, no storage in the new panels |
| `frontend/tests/mutation-check.mjs` | 131 mutations (12 new: N1-N12) |

Backend mutation check of the new code (`scratchpad/mutate_adr050.py`, not committed): 20 source mutations (relevance, negation, third person, quotes, past, language, stance, opposing preferences, confidence exposure, fallback, masking, bounds, conflicts, authority, thresholds, model threshold, control characters) -- 20 of 20 caught after one test was strengthened (the e-mail masking test had not reached the evidence).

Commands (from the repository root unless stated):

```
.venv\Scripts\python.exe -m pytest tests/backend/core tests/backend/api/test_personalized_insights.py tests/backend/api/test_personalized_insights_hardening.py tests/backend/api/test_personalized_insights_interpretation.py -q
.venv\Scripts\python.exe -m pytest tests/backend/core tests/backend/security tests/backend/scripts tests/backend/pipeline tests/backend/db/test_migration_history.py tests/backend/api/test_personalized_insights.py tests/backend/api/test_personalized_insights_hardening.py tests/backend/api/test_personalized_insights_interpretation.py tests/backend/api/test_health.py tests/backend/api/test_lifespan.py tests/backend/api/test_rfc7807.py -q
.venv\Scripts\python.exe scripts/export_insight_fixtures.py [--check]      # real backend responses -> frontend/tests/fixtures
cd frontend ; npx tsc -b ; npm run typecheck:tests ; npm test ; npm run test:mutations ; npx oxlint ; npm run build
```

Types: `frontend/src/types/api.ts` was regenerated with `openapi-typescript` from `app.openapi()` (no server started) and equals a fresh generation.

Results (2026-10-23): DB-free group **1063 passed, 1 skipped** (a final re-run of `core` + the three insight API files after the last small clause-splitting change: **628 passed**); fixtures match the backend; frontend `tsc -b` 0, `typecheck:tests` 0, `oxlint` 0 errors (existing warnings only), `npm test` **154 passed**, `npm run test:mutations` **131 of 131**, production build OK.
Not run: DB-backed suites (no disposable database was used for this change; nothing in it touches the schema), a real-browser visual check, and any live model (none exists).

## 28. Full-Pipeline Household, Honest Debt and Spending States, SQLite Partial Index (ADR-051, 2026-10-24)

No test connects to `neondb`. The PostgreSQL-backed seed tests ran only through the guarded isolated runner (`neondb_test`).

| File | Covers |
| --- | --- |
| `tests/backend/pipeline/test_full_pipeline_household.py` (15) | the REAL app on a throwaway SQLite file: E primary + partner F, every dataset record present exactly once, the application's household summary equal to arithmetic done in the test from the dataset files, EMIs recorded as liability payments AND debt-payment expenses, coherence with E's own monthly records / financial inputs, no individual analysis changed by the household, F honestly pending, membership isolation (403 / 401 / 404), only the primary writes, idempotency (a second `setup` creates nothing and keeps a user's edit), `setup` addresses exactly the pipeline household, twelve months stored for exactly E's id and returned by the behaviour endpoint, profiles without months report zero and never borrow another's |
| `tests/backend/scripts/test_local_synthetic_backend.py` (4) | the launcher's SQLite schema keeps `uq_household_members_one_primary`'s predicate (many members, one primary), repairs a file made by the older launcher, keeps its rows |
| `tests/backend/scripts/test_validate_demo_data.py` (+6 planted defects; counts 6 personas / 2 households) | an EMI with no debt-payment expense, a loan whose payment the expenses do not carry, a persona in two households, a wrong pipeline member count, an unknown pipeline primary, household income not matching its members |
| `tests/backend/api/test_seed_demo_data.py` (isolated PostgreSQL, **38 passed**) | six personas / five resettable, data shapes of the pipeline household, `setup_family` for the pipeline household on a real database (idempotent, verify passes), the two households coexist and deny each other's members |
| `frontend/tests/demo-data-flow.test.ts` (5) + `behaviour-sentiment-view.cases.tsx` (+3) | a saved month refreshes the findings query; each card keyed by the active profile; spending rows = the backend's findings only; a failed request is not shown as "empty"; no figure, storage or arithmetic in the new views; "Not recorded for an individual" and the household pointer |
| `frontend/tests/mutation-check.mjs` | 140 mutations (9 new: H1-H9) |

Backend mutation check of the new code and data (`scratchpad/mutate_adr051.py`, not committed): 12 mutations (setup no longer builds the household, wrong household selected, partner dropped from the loader, records re-created, launcher predicate / repair removed, validator EMI check removed, salary / partner / EMI / liquid-asset data broken, partner given a risk link) — 12 of 12 caught after one test was strengthened (a first run showed `setup` not building the household went unnoticed).

Local rebuild, documented workflow (throwaway SQLite): `local_synthetic_backend.py --db demo.db --prepare-only` -> `load_local_market_data.py --db demo.db` -> serve on 8001 -> `seed_demo_data.py setup` (twice: the second creates nothing) -> `verify` PASSED. Browser (offline SQLite launcher, real UI sign-in with "Use Full Pipeline Demo"): Financial Health and Customer Profile (household open, Liabilities tab) at 1366 px; Financial Health, Customer Profile and Behaviour & Sentiment at 390 px, no horizontal overflow, values equal to the API.

Results (2026-10-24): DB-free group **1088 passed, 1 skipped**; isolated `test_seed_demo_data.py` **38 passed**; `validate_demo_data.py` DEMO DATA VALID (6 personas, 2 households, 49 data files); frontend `tsc -b` 0, `typecheck:tests` 0, `oxlint` 0 errors (existing warnings), `npm test` **162 passed**, `npm run test:mutations` **140 of 140**, production build OK. Not run: other DB-backed suites (nothing else changed), a live Gemini explanation.

## 29. Trained Sentiment Model Seam, Offline Training Package (ADR-052, 2026-10-26)

No test needs a deep-learning package, a model weight, a dataset download or the network; no test connects to `neondb`. **No real model was trained, loaded or evaluated**: `TransformersBackend` and `fine_tune_with_torch` are the only untested parts (the packages are not installed).

| File | Covers |
| --- | --- |
| `tests/backend/core/test_sentiment_model.py` (41 + 1 skipped) | disabled; valid stand-in artifact; documented output shape; temperature scaling numerically; threshold can only be raised; unvalidated / uncalibrated / evidence-less / tiny-test-set artifacts refused; missing, outside-root (`..`, absolute), symlink (skipped here: no privilege), corrupted (weights, config, metadata, missing file), incompatible (vocabulary, positions, labels, version, name, pickle, escaping file) artifacts; missing packages; invalid configuration; exception, timeout and malformed-output handling with fixed reason codes and no text; intensity only from a validated head; cache and failure TTL; module has no network / logging / training code |
| `tests/backend/core/test_user_text_model_policy.py` (40) | model after every gate only; reads only the user's own current clauses; agree / opposite / non-opposite disagreement; negation safeguard never overridden; confidence only when calibrated; bands from the model's own cut-offs; every fallback reason, coercion of unknown codes, fallback off -> abstention; below threshold; 12 invalid-output shapes; no text or path in results |
| `tests/backend/api/test_personalized_insights_model.py` (18) | default-off response and status route; validated reading fills the new fields and changes nothing about the risk profile, conflicts or tone / topics / preferences; disagreement; below-threshold; exception without leakage; missing packages; fallback off; unparsable configuration; non-CPU device / missing token limit; a real stand-in artifact through settings -> verification -> service; read-only status route; no import path to analysis / recommendation / compliance / ledger / network; no text in logs, URL, headers or metadata |
| `tests/training/sentiment/` (54) | manifest gate (template, unapproved, fixture, each documentation field), label mapping, invalid-line counting without echo, normalisation, duplicates and conflicting labels, intensity range, reproducible group-aware split, leak detection, metrics against hand computations (including a floating-point R-squared defect found and fixed), temperature scaling, ECE, owner-target threshold selection, regression metrics, the whole pipeline with a fake trainer (unvalidated fixture artifact, validated test-double artifact accepted by the loader, targets decide validation, evidence list), command-line refusals, no deep-learning import, no backend import of training, rules-baseline evaluation on the held-out split |
| `frontend/tests/user-text-input.test.ts`, `behaviour-sentiment-view.cases.tsx` (+12) | exact method wording, method derived from backend fields only, every fallback reason worded, probabilities as received, intensity "Not available", validated / unvalidated / disagreement / fallback / model-unavailable states, profile switching, no rounding or arithmetic in the panel |
| `frontend/tests/mutation-check.mjs` | 150 mutations (10 new, T1-T10) |

Mutation checks of the new code (`scratchpad/mutate_adr052.py`, not committed): 21 backend / training mutations (hash check, path root, calibration need, temperature, calibrated flag, threshold lowering, time limit, exception leak, logit count, validated gate, opposite-polarity and safeguard policy, whole-text input, below-threshold use, silent fallback, fallback switch, probability validation, dataset approval, leakage detection, fixture validation, minimum test size) — 21 of 21 caught.

Commands: `.venv\Scripts\python.exe -m pytest tests/backend/core tests/backend/api/test_personalized_insights_model.py tests/training/sentiment -q`; `python scripts/export_insight_fixtures.py [--check]`; `cd frontend ; npx tsc -b ; npm run typecheck:tests ; npm test ; npm run test:mutations ; npx oxlint ; npm run build`; `python -m training.sentiment.train_sentiment_transformer --check-environment` (reports the missing packages; exit 2).

Results (2026-10-26): DB-free + training group **1254 passed, 2 skipped**; fixtures match the backend; generated types identical to a fresh generation; frontend `tsc -b` 0, `typecheck:tests` 0, `oxlint` 0 errors, `npm test` **174 passed**, `npm run test:mutations` **150 of 150**, production build OK; `validate_demo_data.py` valid. Not run: any real model or training, DB-backed suites (no schema change), a browser check of the new states (static component renders against real route responses only).

Sentiment phase completion run (2026-10-28, fourteenth brief): the user-text, insight-API, model-loader, provenance, tokenizer-integrity, training, ledger-boundary and documentation-guard groups together passed with the two documented skips (`test_transformer_standin.py`, which needs `torch`; one symbolic-link test); frontend `tsc -b` 0, `oxlint` 0 errors, `npm test` 174 passed, `typecheck:tests` 0, `test:mutations` 150 of 150; generated types identical to a fresh generation. Not run: database-backed suites, browser checks, any real model or training, the disposable S1 environment.

Rubric and evaluation-statistics run (2026-10-29, fifteenth brief): the user-text, rubric, pilot-pack, package, insight-API, model-loader, provenance, tokenizer-integrity, training (including the new statistics tests), ledger-boundary and documentation-guard groups together: 1121 passed, 3 skipped, 0 failed (skips: `test_transformer_standin.py` needs `torch`; two tests need symbolic-link privilege this account lacks); the package builder's `--verify` reports the package and DRAFT manifest consistent; 22 of 22 statistics mutations and 8 of 8 hypothetical-statement mutations detected. Frontend suites were not re-run (no frontend file changed). Not run: database-backed suites, browser checks, any real model, training or inference, the disposable S1 environment.

Evaluation-policy preparation run (2026-10-29, sixteenth brief): the user-text baseline, hypothetical, rubric, pilot-pack, package-builder, evaluation-policy-record, ledger-boundary, insight-API, model-loader, provenance, tokenizer-integrity, training (with the statistics tests) and documentation-guard groups together: 1140 passed, 3 skipped, 0 failed (skips: `test_transformer_standin.py` needs `torch`; two tests need symbolic-link privilege this account lacks); the package builder's `--verify` reports the package and DRAFT manifest consistent; 22 of 22 statistics and 8 of 8 hypothetical-statement mutations detected. Not run: frontend, database, browser, real-model, real-training or dataset tests (no such file changed).

Policy implementation run (2026-10-29, seventeenth brief): the user-text baseline, hypothetical, rubric, pilot-pack, package-builder, evaluation-policy-record, ledger-boundary, insight-API, model-loader, provenance, tokenizer-integrity, training (with the statistics, policy-gate and frozen-evaluation tests) and documentation-guard groups together: 1201 passed, 3 skipped, 0 failed (skips: `test_transformer_standin.py` needs `torch`; two tests need symbolic-link privilege this account lacks); the package builder's `--verify` reports the package and DRAFT manifest consistent; 61 of 61 in-memory mutations detected (18 policy gate, 13 frozen evaluation, 22 statistics, 8 hypothetical). Not run: frontend, database, browser, real-model, real-training or dataset tests (no such file changed).

Policy and wiring run (2026-10-29, eighteenth brief): the user-text baseline, hypothetical, polite-form, rubric, pilot-pack, package-builder, evaluation-policy-record, ledger-boundary, insight-API, model-loader, provenance, tokenizer-integrity, training (with the statistics, policy-gate, frozen-evaluation and frozen-mode tests) and documentation-guard groups together: 1266 passed, 3 skipped, 0 failed (skips: `test_transformer_standin.py` needs `torch`; two tests need symbolic-link privilege this account lacks); the package builder's `--verify` reports the package and DRAFT manifest consistent; 80 of 80 in-memory mutations detected (23 policy gate, 20 frozen evaluation, 7 polite-form baseline, 22 statistics, 8 hypothetical). Not run: frontend, database, browser, real-model, real-training or dataset tests (no such file changed).

Consolidated-form run (2026-10-29, nineteenth brief): the user-text baseline, polite-form, rubric, pilot-pack, package-builder, evaluation-policy-record, consolidated-form, ledger-boundary, insight-API, model-loader, provenance, tokenizer-integrity, training and documentation-guard groups together: 1273 passed, 3 skipped, 0 failed (skips: `test_transformer_standin.py` needs `torch`; two tests need symbolic-link privilege this account lacks); the package builder's `--verify` reports the package and DRAFT manifest consistent. No code changed in this phase. Not run: frontend, database, browser, real-model, real-training or dataset tests, and any phase that needs an approval nobody has given.

Approval-form answer run (2026-10-29, twentieth brief): the consolidated-form guard (46) passed; with the wider sentiment, rubric, pilot-pack, package, insight-API, model-loader, provenance, training and documentation-guard groups together: 1312 passed, 3 skipped, 0 failed (skips: `test_transformer_standin.py` needs `torch`; two tests need symbolic-link privilege this account lacks); the package builder's `--verify` reports the package and DRAFT manifest consistent. No code changed. Not run: frontend, database, browser, real-model, real-training or dataset tests.

Phase 2 gate run (2026-10-29, twenty-first brief): the consolidated-form guard (95) with the documentation guards: 220 passed, 0 failed, 0 skipped; the package builder's `--verify` reports the package and DRAFT manifest consistent. No code changed. Not run: the wider sentiment groups, frontend, database, browser, real-model, real-training or dataset tests (the brief asked for the form guard and the documentation tests only).

Phase 2 gate run (2026-10-29, twenty-second brief): the consolidated-form guard (52) with the documentation guards: 177 passed, 0 failed, 0 skipped; the package builder's `--verify` reports the package and DRAFT manifest consistent. No code changed. Not run: the wider sentiment groups, frontend, database, browser, real-model, real-training or dataset tests (the brief asked for the form guard and the documentation tests only).

Participant-register / D13 calibration run (2026-10-30): `test_participant_register.py` (96), `test_temperature_calibration.py` (40) and `test_frozen_register_and_calibration.py` (58) are new; the frozen-evaluation, evaluation-mode, local-loader and form guards were updated for schema 2 (register as a sixth input, calibration-split probabilities, `--participant-register`). With the whole sentiment training, form, policy-record, pin-list, certificate, rubric, pilot-pack, model-policy, ledger-boundary, tokenizer, provenance, baseline and dry-run package groups together: 1,427 passed, 5 skipped (two torch stand-in modules because `torch` is not installed in the project environment; three tests that need symbolic-link privilege), 0 failed; the package builder's `--verify` reports the package and DRAFT manifest consistent. Mutation checks (register, calibration and frozen-metadata logic): 28 of 30 mutants caught, the two survivors being equivalent (an `isfinite` test made redundant by `0 <= p <= 1`, and a "calibration changed a label" guard that cannot fire because only probabilities are rebuilt). The unrelated, pre-existing GDELT scaffold failure (`tests/backend/data/gdelt/test_sentiment_scaffold.py::test_no_production_entry_point_or_helper_imports_the_sentiment_scaffold`) is excluded and unchanged. No real data, register or manifest; no network, package, model or user text.

Deletion-policy / gate run (2026-10-30): the register validator now enforces the owner's deletion policy (project-owner authorization, retention only until evaluation, audit verification and the R14 decision, only hashes, aggregate metrics and decision records retained, rollback never restores raw text, completion verified and recorded; 5 of 5 mutants caught) and `test_no_fixture_is_real_evidence.py` (6) guards against a fixture passing as real evidence. With the whole sentiment training, form, policy-record, pin-list, certificate, rubric, pilot-pack, model-policy, ledger-boundary, tokenizer, provenance, baseline and dry-run package groups together: 1,435 passed, 5 skipped (two torch stand-in modules because `torch` is not installed; three tests that need symbolic-link privilege), 0 failed; the package builder's `--verify` reports the package and DRAFT manifest consistent. The unrelated, pre-existing GDELT scaffold failure is excluded and unchanged. All results are synthetic-only: no real data, register or manifest; no network, package, model or user text.

Phase-closure run (2026-10-30): The offline rules-based sentiment phase is complete. Transformer evaluation, real dataset creation and production activation are deferred because the required legal, dataset, storage and activation approvals are unresolved. Recorded: D20 REJECTED for this phase (form: 44 APPROVE, 2 REJECT, 0 BLOCKED, 10 KEEP UNRESOLVED), the guard tests describing earlier states read the state before the closure, and a new guard asserts the exact values and the closure statement in the form, approval record, ADRs, README, TEST_PLAN, THREAT_MODEL and MEMORY. Offline groups together (sentiment training incl. Path B stand-ins, register, D13 calibration, schema-2 frozen evaluation, fixture-safety guards; form, policy-record, pin-list, certificate; rules baseline incl. hypothetical, quotation, third-person, past-feeling and polite forms; rubric and pilot-pack; model-policy, ledger-boundary, tokenizer, provenance; dry-run package): 1,557 passed, 5 skipped (two torch stand-in modules because `torch` is not installed in the project environment; three tests that need symbolic-link privilege), 0 failed. Mutation checks: 28 of 30 (register, calibration, frozen metadata; two equivalent survivors) and 5 of 5 (deletion policy). The package builder's `--verify` reports the package and DRAFT manifest consistent. The unrelated, pre-existing GDELT scaffold failure (`test_no_production_entry_point_or_helper_imports_the_sentiment_scaffold`) is excluded and unchanged. Every result is synthetic-only: no real model, dataset, register, manifest or user text; no network or package access.

Final-state verification run (2026-10-30): `tests/backend/core/test_sentiment_final_state.py` (12 tests) checks the state directly: default settings and `.env.example` keep the flag false, the service reports the model disabled and returns no model, every sample is answered by `user_text_rules_v1` with a null intensity and no confidence, evidence is bounded and masked, quoted / third-person / unrelated text abstains and hypothetical-only or past-only text is not a current sentiment, a switched-on model without an artifact fails closed to the rules baseline, no raw text is logged, no weight file exists in the repository, the ledger / security code never mentions sentiment, no optimizer / goals / compliance / recommendation / household / backtest / agent module imports or mentions sentiment, the sentiment code has no language-model or network client (its only loader is local, `trust_remote_code=False`), and a fresh interpreter with the network blocked loads no model or network library and makes no connection. The offline groups together (sentiment training, form and policy records, register, D13 calibration, schema-2 frozen evaluation, fixture-safety, rules baseline, rubric and pilot pack, model policy, ledger boundary, tokenizer, provenance, insight API, dry-run package) were also run with every non-loopback socket connection or name lookup blocked and counted: 1,652 passed, 5 skipped (two torch stand-in modules because `torch` is not installed; three tests that need symbolic-link privilege), 0 failed, 0 external connection attempts. Frontend `tsc -b` reports no error and `oxlint` only the existing warnings in `components/ui`. The unrelated, pre-existing GDELT scaffold failure is excluded and unchanged. Production method `user_text_rules_v1`; `SENTIMENT_MODEL_ENABLED=false`; real model not downloaded; real dataset not created; real evaluation not run; production activation not performed; intensity regression disabled; ledger / blockchain sentiment payload none.

Demonstration-mode run (2026-10-31): backend `tests/backend/api/test_demo_financial_behaviour.py` (19: off by default and 404 when off; six fictional months; ratios and changes equal `compute_behaviour_features`; the sentence read by `user_text_rules_v1`; abstention for quoted, third-person and unrelated text; no database session, no ledger/security import, no logging of text; fixtures equal the route). Frontend `npm test`: 205 passed (new `tests/demo-mode.test.ts` and `tests/demo-financial-behaviour-view.cases.tsx`: months table and chart, calculated values equal the response, unavailable never zero, method panel, loading / unreachable / demo-disabled / other-error states, accessibility and responsive markers, the page with and without `?demo=true`, production build ignoring the query); `tsc -b` and `tsc -p tsconfig.test.json` clean; `oxlint` no warning in the new files; `npm run test:mutations`: 162 of 162 detected (DM1 to DM12 are new); `vite build` succeeds. Real browser rendering was NOT performed (no headless-browser tool was used): layout is verified by markup assertions only.

Financial Behaviour page run (2026-11-02): backend `test_demo_family_financial_behaviour.py` (family route off by default, three fictional members, ratios and changes equal `compute_behaviour_features`, household totals equal the household engine, the note read by `user_text_rules_v1`, no database, no logged text), the extended `test_demo_financial_behaviour.py`, `test_monthly_record_rules_offline.py` (25: negative, non-finite, over-precise, unknown-field and period rules; duplicate-month and non-negative table constraints; no database) and the regenerated insight fixtures (`income_trend` finding): with the whole `tests/backend/core`, `tests/backend/scripts`, `tests/training/sentiment` and insight API groups, 2,110 passed, 5 skipped (two torch stand-in modules; three tests that need symlink privilege), 0 failed, 0 external connection attempts (socket guard). The DB-backed `test_monthly_records.py` needs the hosted test database and was NOT run. Frontend `npm test`: 257 passed (new `behaviour-page-logic.test.ts`: simple-English sentiment, investment status, spending states, overview selection, `?demo=family`, source rules; new `behaviour-page.cases.tsx`: the real page, no-records, loading / outage states, the exact loan / EMI wording, every sentiment state in simple English with technical labels only inside the details, the family demonstration, unique ids and responsive markers, `?demo=family` routing); `tsc -b` and `tsc -p tsconfig.test.json` clean; `oxlint` no warning in the touched files; `npm run test:mutations` 176 of 176 detected; `vite build` succeeds. Four existing page-level tests were updated to the new page structure (same intent). Real browser rendering was NOT performed (no headless browser): layout is verified by markup assertions only. The unrelated GDELT scaffold failure is unchanged.

Demo reachability run (2026-11-03): real-browser checks (headless Chrome through `frontend/tests/route-probe.mjs`, localhost only; database-backed calls mocked with fictional JSON or blocked): the exact URL `http://localhost:5173/financial-behaviour?demo=family` (desktop and 390 px, no horizontal scroll, 3 articles, 3 charts, 4 tables, banner, members, trends, investment, spending, loan wording, household totals, simple-English note); signed out then each of the three demo sign-in buttons returns to that URL; the real page with no records (empty state plus the developer pointer, links open the demonstration, the sidebar link keeps it); an unknown value (notice plus the normal page); a production-style build (notice, no pointer, no demo data) and its plain URL (no notice); a backend with `DEMO_MODE_ENABLED=false` (the switched-off message); the real page with records. Component and unit tests: frontend `npm test` 265 passed (new `demo-reachability.cases.tsx`, `demoRequest`, `behaviourLinkTarget`, `destinationAfterLogin` tests; eight older assertions that pinned the silent-ignore or the old family sign-in destination were updated), `npm run test:mutations` 182 of 182 detected, `tsc -b` and `tsc -p tsconfig.test.json` clean, `oxlint` no warning in touched files, `vite build` succeeds; backend demo tests extended (actionable 404 detail, singular "Income was unchanged"). The unrelated GDELT scaffold failure is unchanged.

Pre-flight run (2026-11-03): `tests/backend/scripts/test_sentiment_preflight.py` (7) checks the read-only pre-flight on the real repository (blocked; A3.3, A3.5b, D20 and R14 named; exit status 1) and on invented state (passes only when every approval, package, artifact, manifest and R14 are present; a missing or unrecorded item blocks exactly its gate; the script reads files only). No model, dataset, package or network access.

## 30. Pretrained Research Comparison (ADR-053, 2026-11-03)

Backend: `tests/backend/core/test_sentiment_research_pair.py` (registry findings, label normalisation by name, comparison statuses and rules relation, artifact verification defects, timeout, back-off,
cache, privacy, isolation, activation), `tests/backend/api/test_sentiment_research_api.py` (status endpoint, additive response field, old-client compatibility, no path leak),
`tests/backend/scripts/test_write_pretrained_manifest.py`. Frontend: `frontend/tests/transformer-research.cases.tsx` (registered in `component.test.mjs`) and mutants TR1-TR12 in `mutation-check.mjs`.
All model output in these tests is a stand-in (TESTED_WITH_MOCKS); none is evidence about a real model. A real-weights smoke test does not exist and must be written when a candidate is approved.
Run: `PYTHONPATH=. .venv/Scripts/python.exe -m pytest tests/backend/core/test_sentiment_research_pair.py tests/backend/api/test_sentiment_research_api.py tests/backend/scripts -q`; `cd frontend && npm test && npx tsc -b && npx oxlint && npm run test:mutations`.

## 31. Replacement Candidate Reviews (ADR-054, 2026-11-03)

`tests/backend/core/test_sentiment_candidate_reviews.py` pins the four verdicts (none approved), the recorded revisions and sha256 values, that the replacements are not in the active registry and cannot load (licence gate first), the Bullish/Bearish mapping with native-label preservation, refusal of mixed or unknown vocabularies,
mocked-logit comparison across vocabularies, the status endpoint's `reviewed_candidates` (no local path), and that nothing was downloaded or installed. All model output is a stand-in (TESTED_WITH_MOCKS). A real-weights smoke test does not exist.

## 32. Scoped Horizon Approval Tests (ADR-054 addendum, 2026-11-04)

`tests/backend/core/test_sentiment_candidate_reviews.py` additionally pins: exactly one candidate (Horizon) is `approved_for_research_inference`; the owner decision names the revision, the research-only scope and every non-authorised item; the financial slot is empty and `tooshlegacy` stays blocked; the remaining gates (including the 4.57.1 incompatibility) are recorded; approval makes no candidate loadable and changes no production flag; the ADR addendum exists and the consolidated approval form is untouched. All inference output is mocked (TESTED_WITH_MOCKS); no network call occurs (socket guard: 0).

## 33. Stage A Verification and Test Fixes (2026-11-04)

Stage A inference is NOT part of the repository test suite: it runs from standalone scripts in the isolated environment and needs the downloaded weights; ordinary CI stays mock-only and needs no network. Fixes recorded: the saved insight fixtures are regenerated by `scripts/export_insight_fixtures.py` whenever the response gains a field; the previous-response test now allows exactly the documented additive key; `test_sentiment_preflight.py` asserts gate 5 mirrors the file system (it verifies nothing); the frontend research test builds its "older response" explicitly. Known hosted-database behaviour: a setup-time `psycopg.OperationalError: server closed the connection unexpectedly` can hit any database-backed test and moves between runs; classify it from the traceback, re-run the test alone, and never claim a clean run that did not happen. The full backend suite takes hours because the API tests make many round trips to the hosted database; run it directory by directory, one process at a time.

### 33.1 Database-boundary rule for running the suites (incident 2026-11-04)

**Run database-backed suites ONLY through `python scripts/run_isolated_db_tests.py` (for example `--suite api --suite db`).** It points both `TEST_DATABASE_URL` and `DATABASE_URL` at `neondb_test` and deselects every `real_*` test. Plain `pytest tests/backend/agents` (six files call `get_engine(settings.database_url)`) and `tests/backend/api/test_analysis.py` (`real_client`) **connect to the development database `neondb`** (read-only by test design; application-level writes through the supplied sessions were never audited) and `tests/backend/agents` also makes up to three live Gemini API calls. On 2026-11-04 the agents directory was run with plain `pytest` by mistake: development-database access CONFIRMED, intended mode read-only by test design, direct test-level writes in the inspected files none identified, application-level writes not fully verified, database state not verified, modification UNKNOWN. Treat `tests/backend/agents` and any `real_*` test as an explicit, owner-approved development-database read, never a default. Full account: `docs/sentiment/stage_a/STAGE_A_COMPLETION_REPORT.md` section 10.3.

## 34. Role-Slot Research Architecture, Lifecycle Guards and Final Regression (ADR-055, 2026-11-05)

New suites: `tests/backend/core/test_sentiment_research_slots.py` (registry, gates, normalisation, comparison, artifact defects, timeout and breaker, back-off, cache, config, unexpected exceptions, non-loading status, concurrent `loading`, single and two-slot panels, Tamil and code-mixed text never reaching a model, never-raise, privacy, isolation, production flags), `tests/backend/api/test_sentiment_research_api.py`, `tests/backend/core/test_user_text_rules_regression.py` (42 characterization tests over 30 fictional sentences; it pins current behaviour and proves nothing about accuracy) and the opt-in `tests/backend/core/test_horizon_real_weights_smoke.py` (skipped unless `WEALTHPILOT_REAL_WEIGHTS_SMOKE=1` and the verified files plus a manifest exist; NOT run). Frontend: `tests/transformer-research.cases.tsx` (15 cases) and mutants TR1-TR18 in `npm run test:mutations` (200 of 200 detected). DB-free suites run with the network guard; DB-backed suites run only through `scripts/run_isolated_db_tests.py`. Exact commands and results: `docs/sentiment/SENTIMENT_TEST_REPORT.md`.

Known non-sentiment findings: `tests/backend/data/gdelt/test_sentiment_scaffold.py::test_no_production_entry_point_or_helper_imports_the_sentiment_scaffold` fails for an unrelated reason (reported separately, not modified); `tests/backend/data/test_ingestion.py` needs the database (it errors under the network guard by design; use the isolated runner); an intermittent native `access violation` can abort a full `pytest tests/training` run (TensorFlow, xgboost and joblib processes; each sub-directory passes on re-run), unexplained, see the test report.

## 35. Test-only NVIDIA DLL lifetime guard for `tests/training` (R3 mitigation, 2026-11-09)

`tests/training/conftest.py` activates `tests/training/nvidia_dll_guard.py` on Windows: it keeps one reference to the NVIDIA driver DLL `nvdxgdmal64.dll` so the XGBoost CUDA-probe fault (`0xC0000005`, see `docs/sentiment/R3_TRAINING_NATIVE_CRASH_INVESTIGATION.md`) cannot occur. Test-only (nothing outside `tests/` imports it; a test enforces this), inert on other platforms and without the DLL, `WEALTHPILOT_NVIDIA_DLL_GUARD=0` disables it, and the pytest header prints its state. `tests/training/test_nvidia_dll_guard.py`: 22 tests with a fake driver store plus 2 real-machine tests. A whole-directory `pytest tests/training` run is again reliable on the investigated machine (5 of 5 passed with the guard; 4 of 5 crashed without it). The guard does not cover suites outside `tests/training/`.
