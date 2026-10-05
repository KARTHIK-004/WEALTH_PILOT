# Phase 34 — Household Financial Aggregation, Emergency Fund & Goal Foundation

Completion report. Historical record: this file describes Phase 34 as it was
implemented and verified, and is not rewritten by later phases.

> **Verification status at the time of writing.** Everything that does not need
> the database has been run and passed (see §15, §18). The database-backed
> tests — the new Phase 34 API suite and the full backend regression suite —
> **have not been run**, because TCP port 5432 to the hosted database is
> currently blocked from this machine (§22). No estimated or assumed result
> appears anywhere in this report.

---

## 1. Objective

Build the first household-level financial *interpretation* layer on top of the
Phase 33 household source records: deterministic aggregation of income,
expenses, assets and liabilities, a monthly cash-flow view, a net position, and
a household emergency-fund assessment.

Phase 34 establishes household **calculations** only. It deliberately does not
connect any of them to advice.

---

## 2. Scope

**In scope (implemented):**

- A pure, deterministic aggregation engine, `core/household_finance.py`.
- One read-only endpoint, `GET /api/households/{household_id}/financial-summary`.
- A read-only "Financial summary" section on the existing Household card.
- Tests, documentation, and ADR-033.

**Explicitly out of scope and NOT implemented:**

- Any connection from household figures to the recommendation pipeline, risk
  model, goal engine, portfolio optimizer, compliance gate, Gemini, AutoGen or
  LangGraph. `POST /api/analysis` is untouched.
- Household goal feasibility, Monte Carlo, inflation-adjusted targets or
  contribution gaps; a household risk profile; a household portfolio; a
  household recommendation or compliance decision.
- Any savings rate, debt-to-income ratio, score, rating, ranking or
  percentage-complete metric.
- Any new table, column or migration; any mutation endpoint for calculations;
  any currency or multi-currency support; any change to authentication.

---

## 3. Household Aggregation Architecture

```
GET /api/households/{id}/financial-summary
  -> routers/household_summary.py          (thin route, auth dependency only)
  -> services/household_summary_service.py (4 scoped queries; maps + serializes)
  -> core/household_finance.py             (ALL arithmetic; pure, Decimal, DB-free)
```

`core/household_finance.py` is a pure module in the same shape as
`core/goals.py`: it imports no database, no FastAPI, no ML, no LLM and no clock,
takes plain record models in and returns plain numbers out. That is where every
household figure is computed, exactly once. The service performs **no
arithmetic**: it loads rows, builds the engine's input records, calls the
engine, and maps the result onto the public schema. The route performs none
either.

**Nothing derived is persisted.** A summary is recomputed from the source
records on every request, so it can never drift from them, and no total is
written back to `households`. This is why Phase 34 needed no migration.

**Query approach** (§37 of the phase instruction): four `SELECT`s, one per
resource, each scoped by `household_id`, then deterministic `Decimal`
aggregation in Python. The number of queries does not depend on the number of
records, so there is no N+1. SQL aggregate expressions were deliberately not
used: keeping the arithmetic in one unit-testable `core/` module — provable
without a database — matters more here than pushing four sums into Postgres.

---

## 4. Income Semantics

| Field | Meaning |
| --- | --- |
| `recurring_monthly` | Sum of **active** monthly amounts plus **active** yearly amounts ÷ 12 |
| `one_time` | Sum of **active** one-time amounts, kept entirely separate |
| `record_count` / `active_record_count` | All records / those with `is_active = true` |
| `available` | Whether the household has recorded any income at all |

Inactive records stay stored and still count in `record_count`, but take part in
no monetary figure. A one-time income never becomes recurring income.

---

## 5. Expense Semantics

Same normalization and same active-only rule as income, plus the split that the
emergency fund depends on:

- `recurring_essential_monthly` — active recurring expenses with
  `is_essential = true`
- `recurring_nonessential_monthly` — active recurring expenses with
  `is_essential = false`
- `recurring_monthly` — both together
- `one_time` — separate, excluded from all of the above

Whether an expense is essential is **read from the household's stored
`is_essential` judgement** and never inferred from the category.

---

## 6. Asset Semantics

- `total` — sum of every asset's `current_value` as stored
- `liquid` — sum over assets the household marked `is_liquid = true`
- `record_count` / `liquid_record_count`

Liquidity comes from the explicit `is_liquid` flag, never inferred from
`asset_type`. Values are used exactly as stored: no market price is fetched and
no appreciation, depreciation or revaluation is applied.

---

## 7. Liability Semantics

- `outstanding` — sum of `outstanding_amount` as stored
- `monthly_payment` — sum over **only** those liabilities that actually record
  one. A `NULL` `monthly_payment` means "not provided" and contributes nothing;
  it is never aggregated as a payment of 0.
- `record_count`

No debt-to-income ratio is computed, and no Phase 5 debt-related ML feature was
touched.

---

## 8. Monthly Normalization

| Frequency | Monthly contribution |
| --- | --- |
| `monthly` | the amount, unchanged |
| `yearly` | `amount / 12` |
| `one_time` | **none** — reported separately |

No amortization period is invented for a one-time record, and a one-time amount
is never assumed to repeat. Division is `Decimal`, at full context precision:
`100.00` yearly becomes `8.333…` per month, not a prematurely rounded `8.33`.

---

## 9. Cash-Flow Semantics

`monthly = recurring_monthly_income − recurring_monthly_expenses`, computed only
when **both** are known; otherwise `null` with a reason naming the missing side.
One-time income and one-time expenses are excluded by construction.

This is deliberately **not** called savings, no savings rate is derived from it,
and it is not treated as a contribution capacity — the project's architecture
defines `GoalAssumptions.contribution_amount` as a user-supplied input, so
equating it with cash flow would be an invented methodology (ADR-033).

---

## 10. Net-Position Semantics

`value = total_assets − total_outstanding_liabilities`, computed only when both
sides are known; otherwise `null`. Income and expenses are not part of it. A
missing side is never treated as zero — a household with assets but no recorded
liabilities has an *unknown* net position, not a net position equal to its
assets.

---

## 11. Emergency-Fund Semantics

`required = target_months × recurring_monthly_essential_expenses`, where
`target_months` is imported from `core/goals.py`'s
`EMERGENCY_FUND_TARGET_MONTHS` (6) rather than restated, and sufficiency uses
the same `current_liquid_assets >= required` comparison the individual engine
uses. A test asserts the household result agrees with
`core.goals.assess_emergency_fund` on the same inputs, so the two can never
diverge. **The individual implementation was not modified.**

| State | When |
| --- | --- |
| `sufficient` | both inputs known and `liquid >= required` |
| `insufficient` | both inputs known and `liquid < required` |
| `unknown` | essential expenses or liquid assets not known |

`shortfall = max(required − current_liquid_assets, 0)`, in exact `Decimal`.
A recorded liquid asset worth `0` is a **known** fact, so it yields a known,
insufficient position — not `unknown`.

It is **informational only**: Phase 34 produces no savings-first verdict, no
`approved`/`rejected` status, no recommendation and no compliance decision from
it.

---

## 12. API

One new route, read-only:

```
GET /api/households/{household_id}/financial-summary  ->  200
```

Response (`HouseholdFinancialSummaryResponse`): `household_id`, `income`,
`expenses`, `assets`, `liabilities`, `cash_flow`, `net_position`,
`emergency_fund`, `data_completeness`. Each section carries its figures plus
`available` and the project's usual `unavailable_reason` sentence;
`data_completeness` is `available`/`unavailable` per area — never a percentage
or a score. No customer id or member detail appears anywhere in the response.

No mutation endpoint was added for calculations (there is nothing to store), and
the Phase 33 CRUD endpoints are unchanged. The household route inventory is now
27 paths, pinned exactly by test.

---

## 13. Authorization

Phase 32/33's model, reused unchanged and with no primary-only restriction
because the endpoint is read-only:

| Situation | Result |
| --- | --- |
| No / malformed `X-Customer-Id` | **401** |
| Unknown household | **404** |
| Non-member | **403**, carrying none of the denied household's figures |
| Any member (primary, member or dependent) | **200** |
| Any mutating verb on the route | **405** |

Every underlying query is scoped by the path's `household_id`, and the endpoint
accepts **no request body at all**, so there is nothing in which a caller could
supply a different `household_id`.

**The `X-Customer-Id` header is asserted, not authenticated.** The prototype has
no server session or token; this stops accidental and URL-edited cross-household
access, not a malicious client. Phase 34 adds no authentication and claims none.

---

## 14. Frontend

The expanded Household card now renders a read-only **Financial summary** block
above the existing Phase 33 tabs
(`components/profile/household-financial-summary.tsx` over
`hooks/use-household-summary.ts`): the recurring monthly view (income, expenses
with essential/other beneath, cash flow), one-time records in their own labelled
block, an assets/liabilities table ending in net position, the emergency-fund
position with a neutral status badge, and one Available/Unavailable badge per
area.

**There is zero financial arithmetic in it.** Every figure is rendered exactly
as the API returned it; the only number handling is `formatCurrency`. It shows
no score, percentage, rating, ranking, progress bar or recommendation, and the
emergency-fund badge uses the neutral `outline` variant for every status so the
status is read from its text, never colour alone. `null` renders as "Not
provided" and a stored `0` as a formatted zero.

The Phase 33 record mutations now also invalidate the summary query, so editing
a record yields a freshly **recomputed** summary from the server rather than a
locally adjusted one.

---

## 15. Tests

**Run and passing:**

- `tests/backend/core/test_household_finance.py` — **59 tests, all passing in
  0.25s**, with **no database**. Pure `Decimal` arithmetic: monthly/yearly/
  one-time normalization; inactive records; empty sets; essential vs
  non-essential; liquid vs illiquid; nullable `monthly_payment`; cash flow and
  net position with each side missing in turn; genuine zeroes kept distinct from
  unknowns; the exact emergency-fund boundary (required, required − 1,
  required + 1) compared exactly rather than approximately; agreement with
  `core/goals.py::assess_emergency_fund`; determinism; and an assertion that no
  score/ratio/recommendation field exists in the result.
- Source-level render check of the real page against real payloads —
  **39/39 checks passed** (§18).
- The two OpenAPI-level guards in `tests/backend/api/test_households.py`
  (route inventory, no financial field in Phase 32 schemas) — **2 passed**.

**Written but NOT yet run (database unreachable, §22):**

- `tests/backend/api/test_household_summary.py` — the endpoint suite: response
  shape, values traced to stored records, one-time records excluded from cash
  flow, the summary following create/update/delete, null-vs-zero at the API
  boundary, the emergency-fund boundary end to end, the full authorization
  matrix, cross-household isolation with two populated households, the OpenAPI
  route set, and the individual-analysis regression guards.
- The full backend regression suite.

---

## 16. Security and Isolation

Written and covered by `test_household_summary.py`, **not yet executed**:
a member of household A receiving 403 for household B with none of B's figures
in the body; each household's summary containing only its own records; adding
records to B never changing A's summary; `household_id` always being the path's;
and the absence of any customer id in the response.

Executed and passing now: the OpenAPI-level guards proving the summary route is
the *only* aggregate path and that no mutation verb is exposed on it.

No secret was printed, logged or committed at any point, and nothing in the new
code logs a request body.

---

## 17. Individual-Analysis Regression

By construction: no module under `core/` (other than the new file), `agents/`,
`training/`, `models/` or `config/` was modified; `analysis_service.py` is
untouched; and nothing imports `household_summary_service` or
`household_finance` from the analysis path. Grep confirms the household summary
is reachable only from its own router.

The behavioural regression tests that re-run each demo persona's analysis before
and after a household summary exists are **written but not yet executed** —
they are database-backed (§22). Phase 34 therefore does not yet *claim* a
verified byte-identical analysis result; it claims only that no code on that
path was changed.

---

## 18. TypeScript, Lint and Build

All run at the final state of the code:

- `npx tsc -b` — **0 errors**.
- `npx oxlint` — **0 errors, 8 warnings**, exactly the pre-existing baseline
  (shadcn primitives / provider files). No new warning.
- `npm run build` — **succeeds**. JS 1,089.74 kB (gzip 326.28 kB), CSS
  97.80 kB.
- `frontend/src/types/api.ts` — regenerated directly from `app.openapi()` (no
  server started): **+251 lines, −0**, purely additive.
- Source-level render check (SSR of the real Customer Profile page against real
  API payloads; **not a browser**) — **39/39 passed**: figures rendered exactly
  as returned, one-time amounts never folded into recurring figures, null vs
  zero visibly distinct, emergency-fund status factual, no score/ranking/
  recommendation wording, loading and RFC 7807 error states, one `<h1>`, each
  section with its own heading and `aria-labelledby`, and the Phase 33 tabs
  still intact.

---

## 19. Documentation

- `docs/DECISIONS.md` — **ADR-033** added; a dated note under ADR-032 records
  that its aggregation half is superseded, without editing its substance.
- `docs/RULES.md` — **Rule 33** added; Rule 32's first bullet now points to it.
- `docs/ARCHITECTURE.md` — §4 (the summary block), §6 (the route and its
  layering), §7 (no migration added), §23 (limitations).
- `docs/PRD.md` — new §14.17/§14.18 split, §37, §38, §40.
- `docs/DESIGN.md` — new §27a, Household Financial Summary.
- `docs/SECURITY.md` — a Phase 34 subsection, including the plain statement that
  any member can read the household's whole financial position.
- `docs/TEST_PLAN.md` — the two new test files described.
- `docs/MEMORY.md`, `TASKS.md`, `CLAUDE.md` §14, `.claude/rules/backend.md`.

Phase 32 and Phase 33 reports were not rewritten.

---

## 20. Files Changed

**Created (8):** `backend/wealthpilot/core/household_finance.py`,
`backend/wealthpilot/api/services/household_summary_service.py`,
`backend/wealthpilot/api/routers/household_summary.py`,
`tests/backend/core/test_household_finance.py`,
`tests/backend/api/test_household_summary.py`,
`frontend/src/hooks/use-household-summary.ts`,
`frontend/src/components/profile/household-financial-summary.tsx`,
`reports/phase34_household_financial_aggregation_report.md`.

**Modified — Phase 34 proper (A, 16):** `api/schemas.py` (9 response schemas +
2 literal types), `api/main.py` (router registration),
`frontend/src/lib/api-client.ts` (one method),
`frontend/src/types/api.ts` (regenerated),
`frontend/src/components/profile/household-card.tsx` (renders the summary),
`frontend/src/hooks/use-household-finances.ts` (also invalidates the summary),
`docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/DESIGN.md`, `docs/MEMORY.md`,
`docs/PRD.md`, `docs/RULES.md`, `docs/SECURITY.md`, `docs/TEST_PLAN.md`,
`CLAUDE.md`, `.claude/rules/backend.md`, `TASKS.md`.

**Modified — required compatibility (B, 3):**

- `backend/wealthpilot/api/routers/household_finances.py` — its docstring
  asserted that no summary route exists, which Phase 34 makes false. Corrected
  to point at the new module; no behaviour changed.
- `tests/backend/api/test_household_finances.py` — two guards narrowed rather
  than deleted: "no aggregate route exists" now pins the one permitted route by
  name, and the "no derived field" schema check now names the twelve
  source-record schemas explicitly instead of matching a name substring.
- `tests/backend/api/test_households.py` — the exact household route inventory.
  See §22: this was **already failing before Phase 34 began**.

**Unrelated (C): none.**

---

## 21. Known Limitations

- **Phase 34 reports; it does not advise.** No household savings rate, debt
  ratio, score, goal feasibility, risk profile, portfolio or recommendation
  exists, by design.
- **Any member sees everything.** The summary concentrates the household's whole
  financial position into one response, and any member — including a dependent —
  can read it. There is no per-record or per-member visibility control.
- **The identity is asserted, not authenticated** (ADR-020), unchanged.
- **"Unknown" can surprise.** Because an aggregate is `null` unless a record
  contributes to it, a household that recorded only one-time income sees
  *unknown* recurring income. The system never asks whether a set of records is
  complete, so it cannot honestly report zero instead.
- **No caching.** The summary is recomputed per request from four queries. That
  is correct and always fresh, but not free for a large household.
- **Single currency**, unchanged; no currency field and no conversion.
- **No browser-based visual or interactive testing was performed.** Frontend
  verification was `tsc` / `oxlint` / `vite build` plus a source-level
  server-side render against real API payloads. That is not a browser test and
  is not claimed to be one.
- **Database-backed tests have not been run** (§22).

---

## 22. Unexpected Findings

- **A Phase 32 test was already failing before Phase 34 began.**
  `test_households.py::test_openapi_lists_exactly_the_household_routes` asserts
  an exact household route inventory; Phase 33 added eight paths without
  updating it. It was not caught during Phase 33 because that phase's
  full-suite run never reached it — the run was killed by a session ending at
  44%, and the test sits at 42%. It is now corrected to list all three phases'
  routes explicitly. This is recorded here, and in Phase 33's own report, rather
  than quietly fixed.
- **The hosted database became unreachable mid-phase.** TCP connections to port
  5432 time out on all three of the host's resolved addresses, while the same
  host answers on port 443 and general internet connectivity is normal
  (sub-100 ms to three unrelated hosts). The database worked earlier in the same
  session. This is therefore a network-level block on the Postgres port, not a
  code fault, not a Neon outage and not the documented intermittent latency.
  Consequently no database-backed test could be run, and none is claimed.
- The prompt's illustrative currency (`₹`) differs from the project's own
  documented assumption (EUR, `docs/PROJECT_PLAN.md` Part 0). The existing
  assumption was preserved, per §31's instruction to keep the existing
  convention.
- Four initial render-check failures were traced to the harness, not the UI:
  React's SSR comment separator between adjacent text nodes became a space when
  tags were stripped, and `aria-label` attributes vanish under tag-stripping.
  The badge was changed to a single text node (cleaner markup) and the two
  harness checks corrected; no UI defect existed.

---

## 23. Git Status

**Nothing was committed.** The repository still has zero commits on `master`, so
`git status --short` lists every top-level directory as untracked, exactly as
before this phase. No file was deleted, reset, stashed or reverted; no unrelated
work was touched; no `.gitignore` change was made to tidy the status. All
scratch scripts, fixtures and harnesses live outside the repository, in the
session scratchpad.

Scope audit: 27 project files changed, classified in §20 as A (Phase 34) or B
(required compatibility). There are no C (unrelated) changes.

---

## 24. Explicit Statement — Recommendation Logic Was Not Changed

**Phase 34 changed no recommendation logic, and connected no household figure to
any advice path.**

`agents/recommendation.py`, `core/recommendation.py`, `core/compliance.py`,
`core/optimizer.py`, `core/goals.py`, `agents/nodes.py`, `agents/graph.py`,
`agents/debate.py`, `agents/explanation.py`, `api/services/analysis_service.py`,
`config/compliance_rules.yaml` and every trained model are **unmodified**. The
recommendation precedence (Compliance > Savings-first > Risk > Goal > Market) is
untouched, the compliance gate remains binding and fail-closed, and no household
value is read by any of them.

The household emergency-fund assessment is informational: it emits no
savings-first verdict, no `approved`/`rejected`/`blocked` status and no
recommendation. Household aggregation reaches exactly one endpoint and one UI
block, and nothing else.

Connecting any household figure to goal feasibility, a household risk view, a
household portfolio or a household recommendation is deliberately left to a
later phase, and would need its methodology specified and its own ADR first
(ADR-033).

---

**Phase 34 implementation is complete. Database-backed verification is
outstanding (§22). No Phase 35 work was started.**
