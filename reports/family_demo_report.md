# Demo Experience Update — Individual + Family Demo

A demo-experience update, not a development phase: no Phase 37, no new
feature, no schema. It makes the existing product demonstrable in two clearly
separate scenarios — individual analysis and household context — using real
persisted data and the existing public API (ADR-036).

---

## 1. Existing Individual Demo — Preserved

| Persona | id | What it demonstrates | Analysis (unchanged) |
|---|---|---|---|
| WealthPilot Demo — Complete | 29098 | the full approved path; the **Individual Demo** lands here | `approved` (165) |
| WealthPilot Demo — Savings | 29099 | the savings-first mechanism | `approved`, savings-first (166) |
| WealthPilot Demo — Compliance | 29100 | the binding, fail-closed compliance REJECT | `rejected` (167) |
| WealthPilot Demo Customer | 29096 | the pending-information case (no FAR-Trans link) | `pending_information` (168) |

**Verified unchanged.** All four personas were snapshotted before the family
was seeded and again afterwards, reading through the real app against the
development database. The analysis ran inside a transaction that was rolled
back. The **full `POST /api/analysis` response, the profile including
individual goals, the questionnaire answers and the financial inputs are
identical** for all four. The only difference is the intended one: 29099 and
29100 now belong to the family household.

The individual demo's login resolution is unchanged (ADR-030). Only its button
label changed, from "Use Demo Account" to "Use Individual Demo". "Complete" and
"WealthPilot Demo Customer" were deliberately kept out of every household, so
the individual demo shows exactly what it showed before, down to its
"No household created yet." card.

## 2. Family Demo — Added

- **Household**: "WealthPilot Demo Family" — **id 6** in this environment
  (ids 1–5 were consumed by earlier rolled-back verification runs; PostgreSQL
  sequences do not roll back).
- **Primary**: "WealthPilot Demo — Savings" (29099) — relationship `self`, role
  `primary`, not a dependent.
- **Spouse**: "WealthPilot Demo — Compliance" (29100) — relationship `spouse`,
  role `member`.
- **Dependent**: none. The existing implementation supports one cleanly, but
  adding one would need a new customer record, and the brief makes the
  dependent optional and asks for no unnecessary customer records.
- **Existing customers only**: no customer record was created.

**Built entirely through the public household API** by
`backend/scripts/seed_demo_data.py setup-family`:
- It finds members by exact name via `GET /api/profiles/lookup`, never by a
  hard-coded id.
- It uses no new schema or migration and makes no direct database write.
- The only direct write is in `reset-family`, because no household-deletion API
  exists by design (ADR-031).
- `--in-process` runs it through the real app via FastAPI's `TestClient`, so no
  server needs starting.

## 3. Household Financial Records

Synthetic household-level demo values in EUR. They are never training data,
never read by any model, and never an input to any individual analysis.

| Resource | Records |
|---|---|
| Income (5) | Primary salary (net) 2,800/month · Spouse salary (net) 3,100/month · Rental income 9,600/year · Annual bonus 3,000 one-time · Previous part-time job 600/month **inactive** |
| Expenses (8) | Rent 1,650 · Groceries 750 · Energy and water 190 · Public transport and fuel 260 (monthly, essential) · Home and car insurance 1,440/year essential · Dining and leisure 350 · Streaming subscriptions 45 (monthly, non-essential) · New sofa 1,200 one-time |
| Assets (4) | Joint current account 6,000 liquid · Emergency savings account 9,500 liquid · Index fund 22,000 · Family car 12,000 |
| Liabilities (2) | Car loan 7,800 outstanding, 310/month, 5.9% · Credit card **0** outstanding, monthly payment **not provided** |

Each record was chosen to exercise one Phase 34 rule:
- yearly amounts count as amount ÷ 12 per month;
- one-time records stay out of recurring figures;
- inactive records are stored but not counted;
- essential expenses form the emergency-fund basis;
- liquidity follows the stored flag;
- a recorded zero sits beside an unknown and the two are never conflated.

**Summary, as returned live** by the unchanged engine
(`GET /api/households/6/financial-summary`):
- recurring monthly income **6,700**; one-time income 3,000;
- recurring monthly expenses **3,365** (essential 2,970, non-essential 395);
  one-time expenses 1,200;
- monthly cash flow **3,335**;
- total assets 49,500 (liquid 15,500); outstanding liabilities 7,800, with
  recorded monthly payments of 310;
- net position **41,700**;
- emergency fund required **17,820** against 15,500 liquid: shortfall 2,320,
  **insufficient**.

## 4. Household Goals

| Goal | Type | Target | Current | By |
|---|---|---|---|---|
| Emergency fund | emergency_fund | 18,000 | 9,500 | 2027-12-31 |
| Home deposit | house | 45,000 | 6,000 | 2030-06-30 |
| Family holiday | travel | 4,000 | *not provided* | 2027-08-01 |

The emergency-fund goal's 18,000 is the family's own stated target. The
calculated requirement (17,820) comes only from the summary, and the Goals tab
restates it for reference: one calculated figure, never two (ADR-035).

## 5. Demo UI

- **Login page**: a "Demo Accounts" panel with **Use Individual Demo** ("one
  customer's own analysis") and **Use Family Demo** ("a household's members,
  income, expenses, assets, liabilities, summary and goals. Household figures
  are context only — there is no household risk score or recommendation").
- **Family session**: lands on `/profile?household=open` with the Household
  section expanded and scrolled into view; the header badge reads **Family
  Demo**. An unseeded environment shows a clear error, and nothing is
  fabricated in the browser.
- **Individual session**: unchanged, badge **Demo Account**.
- **One customer per session** (ADR-021): the choice happens at login; there is
  still no in-app switcher.

## 6. Idempotency

- **Tests**, against the test database: a second `setup_family` run creates
  nothing (`created == []`) and leaves every count and the summary unchanged. A
  partially seeded household is completed rather than duplicated. A persona
  already in a different household makes setup stop rather than alter it.
- **The real development database**: a second `setup-family` reported **0
  created, 24 already present**, with the same summary.

## 7. Authorization

`verify-family` passed **16/16** on the development database (exit code 0):
- The primary is `self`/`primary`/not dependent, and the spouse is
  `spouse`/`member`.
- Every demo record is present exactly once.
- Member entries carry identity and membership fields only.
- Both individual-demo personas belong to no household, and each gets **403**
  on the family household.

The tests additionally cover:
- 403 on members, income, goals and the summary for non-members, with no family
  data in the denial;
- no household route that exposes a member's profile, analysis, questionnaire,
  financial inputs, portfolio or recommendation;
- `reset` matching the demo household by exact name **and** primary, so a
  same-named household with a different owner is untouched.

## 8. Individual Regression

- **All four personas unchanged**: identical before and after the family was
  seeded (see §1), including their full analysis responses.
- **Seed-script tests**: `tests/backend/api/test_seed_demo_data.py` passed
  **28/28** (13 existing, unchanged, plus 15 new).
- **Full suite**: no complete run exists for this change on its own.

  The run started on 2026-09-26 at 23:36:50 stopped writing at 01:06:52 on
  2026-09-27. It had reached 51% (659 of 1,278 tests) and never recorded an
  exit code. It had printed one FAILED test, `test_setup_family_is_idempotent`.
  pytest prints tracebacks only at the end of a run, so there is no traceback
  and the failure is **unclassified**.

  On 2026-09-30 the whole file (`tests/backend/api/test_seed_demo_data.py`) was
  re-run in isolation: **28 passed**, including that test. The first complete
  full-suite run that includes this change is the one recorded for the demo
  dataset package (`reports/demo_dataset_catalog.md` §10, ADR-038).

## 9. Frontend Validation

- `npx tsc -b`: **0 errors**.
- `npx oxlint`: **0 errors, 8 warnings**, the unchanged baseline.
- `npm run build`: **passes** (JS 1,097.27 kB, gzip 328.00 kB).
- **Render check** of the demo experience: a server-side render of the real app
  against real API payloads, reached through the real
  `/profile?household=open` URL. **This is not a browser test.** Result:
  **16/16**.
  - The login page offers both scenarios with honest descriptions, and has no
    customer-id input.
  - The family session is badged "Family Demo" and arrives with the household
    open, showing the engine's figures.
  - The spouse appears by name, relationship and role only; their income, age
    and analysis status never appear.
  - There is no household risk score or recommendation wording.
  - The individual session keeps "Demo Account" and "No household created yet."
- **Regression render checks** after the household-card change: Phase 34
  **39/39**, Phase 35 **17/17**, Phase 36 **20/20**.

## 10. Exact Files Changed

**Code:**
- `backend/scripts/seed_demo_data.py`: family spec, `setup_family` /
  `verify_family` / `reset_family`, `--in-process`; `reset` removes the family
  household first.
- `tests/backend/api/test_seed_demo_data.py`: 15 new tests.
- `frontend/src/lib/demo-customer.ts`: find-only `resolveFamilyDemoCustomer`,
  the family-session label.
- `frontend/src/components/login-form.tsx`: two demo entries.
- `frontend/src/components/shell/account-identity.tsx`: "Family Demo" badge.
- `frontend/src/components/profile/household-card.tsx`: opens on
  `?household=open`.

**Documentation:**
- `docs/DECISIONS.md` (ADR-036)
- `docs/final_demo_script.md` (new §17 Family demo)
- `docs/final_viva_talking_points.md`
- `docs/demo_runbook.md`
- `docs/ARCHITECTURE.md`
- `docs/MEMORY.md`
- `reports/demo_dataset_catalog.md` (§9)
- `TASKS.md`
- this report

**Data** (development database, through the public API): household 6, one
membership, and 22 household records and goals.

**Not changed:**
- application code under `backend/wealthpilot` (routers, services, `core/`,
  `agents/`, models, schemas);
- migrations, ML models, datasets, training;
- the risk, expense, behaviour and market models;
- portfolio, compliance, recommendation, Gemini, LangGraph and AutoGen;
- every persona's individual data.

Nothing was committed or pushed.

---

    INDIVIDUAL DEMO: PRESERVED
    FAMILY DEMO: ADDED
    INDIVIDUAL ANALYSIS LOGIC: UNCHANGED
    HOUSEHOLD SECURITY: PRESERVED
    PHASE 37: NOT CREATED
