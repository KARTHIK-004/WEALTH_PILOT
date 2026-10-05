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
