# Full-Pipeline Demo: Household, Debt & Commitments, Spending, Monthly Records — Report (2026-10-24, ADR-051)

Goal: every supported section of the full-pipeline demo account (WPDEMO-E) shows backend-derived information, and anything unsupported says so with its exact blocker. Nothing was committed or pushed, `neondb`
was never connected to, no migration was added, no formula, risk model or compliance rule changed.

## 1. Verified root causes

| Section (as seen) | Cause | Evidence |
| --- | --- | --- |
| **"0 reported months"** | **Not a code defect on the path the demo uses.** Signing in with *Use Full Pipeline Demo* on a correctly seeded database shows "12 reported months", the 12-row table and the findings (checked through the real UI). The page is empty for persona A — the profile that "Sign In" and "Use Individual Demo" open — which has no monthly records by design, and for any database where `setup` has not been (re)run since E gained its months. One real staleness defect was found and fixed: saving or deleting a month did not refresh the `personalized-insight` query behind the behaviour pages. | UI run; `GET .../monthly-financial-records` = 12 rows for E's id only; `test_all_twelve_months_...`, `test_a_profile_without_months_...` |
| **Household Finance (no household)** | **Missing synthetic seed data.** E belonged to no household, and a household member must be an existing customer, so a real second member needed a customer. | `GET /api/profiles/{E}/household` → `household: null` |
| **Household with two members impossible on the local demo database** | **Defect in the throwaway SQLite launcher.** SQLite ignores `postgresql_where`, so `uq_household_members_one_primary` ("one primary per household") became "one member per household"; `setup-family` failed locally with 409. The same defect was in the pipeline test fixture. | reproduced; `test_local_synthetic_backend.py` |
| **Debt & Commitments "Not available"** | **Genuinely unsupported feature for an individual** (ADR-033: loans and EMIs exist only as a household's liabilities; no individual debt table). The card said "not available", which implies missing data. | `core/behaviour_findings` also reports `debt_burden: not_included` |
| **"Spending pattern not available"** | **Unsupported by design.** `expense_persona` is the Kaggle-only expense-clustering model, never applied to a FAR-Trans customer (ADR-010; `agents/nodes.py`). An individual's spending is stored as one monthly total (no categories). | `financial_health.expense_persona_unavailable_reason` |

## 2. What was built

- **Persona F** `WPDEMO-F` "WealthPilot Demo — Full Pipeline Partner" (synthetic, light, pending information like D) so E's household has a real second member.
- **Household `WPDEMO-HHE`** "WealthPilot Demo — Full Pipeline Household" (E primary/self, F spouse): 5 income, 12 expense, 7 asset, 3 liability and 5 goal records, seeded through the public household API.
- Seed: `setup` builds it; `verify` / `reset` cover it; `setup-family|verify-family|reset-family --household family|pipeline`. Idempotent, never overwrites an edit. Validator: 6 personas, 2 households, 49 files, new EMI-vs-debt-expense coherence check. Manifest, seed plan, README, runbook updated.
- Frontend: "Debt & Commitments" now says *Not recorded for an individual* and points a household member to the household's liabilities (no household figure shown there); "Spending and expenses" additionally shows the backend's spending findings from the reported months (loading / error / empty / data states; no category breakdown claimed); a saved month refreshes the findings query.
- Local SQLite launcher: partial-index predicate applied and old files repaired.

## 3. What the account now displays (from the application, local SQLite rebuild, market data loaded)

| Where | Shown (backend-computed) |
| --- | --- |
| Financial Health → Spending and expenses | "Expenses increased by ₹1,000 compared with the previous month (1.9%)." and "In 2026-09, expenses were 53.0% of that month's reported income."; spending pattern unavailable with its reason |
| Financial Health → Debt & Commitments | "Not recorded for an individual" + pointer to the household's loans and EMIs |
| Financial Health / Behaviour & Sentiment | 12 reported months, latest 2026-09, all findings |
| Customer Profile → Monthly record | the 12 months table (Oct 2025 – Sept 2026) |
| Customer Profile → Household | primary + spouse; recurring income ₹1,55,000; recurring expenses ₹96,000 (essential ₹80,000 / other ₹16,000); cash flow ₹59,000; one-time income ₹1,20,000 and expenses ₹85,000; assets ₹23,70,000 (liquid ₹5,00,000); liabilities ₹6,50,000; monthly liability payments ₹16,000; net position ₹17,20,000; emergency fund required ₹4,80,000, current ₹5,00,000, shortfall ₹0, **sufficient** |
| Household → Liabilities tab | Car loan ₹3,40,000 EMI ₹9,500 at 9.25%; Education loan ₹3,10,000 EMI ₹6,500 at 9.50%; Credit card ₹0 (payment "Not provided" — a known zero beside an unknown) |

Consistency (documented in `demo_data/README.md`, enforced by the validator and tests): primary salary = E's latest reported income (100,000); non-EMI household spending 80,000 = E's reported 53,000 + partner's share 27,000; E's saving + investing (37,000) < household cash flow (59,000); E's ₹3,00,000 easy-access savings are one liquid asset; each EMI is both a liability payment and a debt-payment expense. Unavoidable difference: E's own essential spending input (38,000) is for one person; the household's essential spending (80,000) is for two people and two loans.

## 4. Commands

```
python scripts/local_synthetic_backend.py --db demo.db --prepare-only          # repo root
python scripts/load_local_market_data.py --db demo.db
python scripts/local_synthetic_backend.py --db demo.db --port 8001
cd backend ; DATABASE_URL=sqlite:///.../demo.db python scripts/seed_demo_data.py setup  --base-url http://127.0.0.1:8001   # run twice: the second creates nothing
             DATABASE_URL=sqlite:///.../demo.db python scripts/seed_demo_data.py verify --base-url http://127.0.0.1:8001
python scripts/seed_demo_data.py setup-family --household pipeline | verify-family --household pipeline | reset-family --household pipeline
python scripts/seed_demo_data.py reset      # hosted PostgreSQL only; a local demo is reset by deleting its .db file
```
On a hosted database that already holds E from before: run `setup` once (adds only what is missing: F, the household, any missing month).

## 5. Verification

DB-free group 1088 passed / 1 skipped; isolated `test_seed_demo_data.py` 38 passed on `neondb_test` only; validator valid; frontend `tsc` / `typecheck:tests` / `oxlint` (0 errors) / `npm test` 162 / mutations 140 of 140 / build; backend mutations 12 of 12. Browser (local SQLite, real UI sign-in): Financial Health and Customer Profile (Household incl. Liabilities tab) at 1366 px; Financial Health, Customer Profile, Behaviour & Sentiment at 390 px; no horizontal overflow; values equal the API.

## 6. Remaining limitations (exact blockers)

- **Individual debts/EMIs** have no storage or endpoint (adding them needs a schema, an ADR and a decision about the individual pipeline); they exist as household liabilities only.
- **Spending pattern (expense persona)** stays unavailable for a FAR-Trans customer by ADR-010; **per-category individual spending** has no record (monthly records hold one spending total).
- The aggregate CSV `wealthpilot_complete_demo_dataset.csv` (exported from the live database) still covers A–D; E, F and the households join it when the owner regenerates it against the live database.
- A database where `setup` was never re-run still shows "0 reported months" / no household for E: run `setup` there (and use *Use Full Pipeline Demo*; "Sign In" opens persona A).
- Not exercised: the hosted development database (forbidden here), a live Gemini explanation.
