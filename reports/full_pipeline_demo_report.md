# Full-Pipeline Demo Persona — Report (2026-10-23)

Goal: a fully populated, synthetic demo account for which the Risk Profile, Portfolio, Recommendation, Goals, Why and Behaviour pages show results produced by the
existing application pipeline. Nothing was hard-coded, no compliance rule was bypassed, `neondb` was never connected to, nothing was committed.

## 1. Diagnosis (why the pages were empty)
| Symptom | Cause (verified) |
| --- | --- |
| "Risk profile not available yet", goals "not reviewed", no portfolio or recommendation | The profile used was persona D / an ordinary profile: no `risk_inputs.external_customer_id`, so no feature row, so `risk_analyst -> information_request -> END` (`agents/graph.py`). The link has no public API by design; only `seed_demo_data.py` writes it. |
| Even the linked persona A came back `rejected` on a fresh local database | `market_data` was empty: "no market_data rows found for QQQ, AGG, GLD" -> no weights -> compliance (fail-closed) rejected `weights_sum_to_one`, `no_negative_weights`, `qqq_within_risk_band`, `single_asset_cap`. Goal feasibility was also `null` (the Monte Carlo reads the same table). |
| Behaviour page empty for every demo persona | the demo package had no monthly records |
| "Your risk assessment on file" empty for every real user | the pipeline never writes `risk_assessments` (NOT NULL `risk_score`, no ordinal score exists), and the endpoint read only that table |

## 2. What was built
- **Persona E** `WPDEMO-E` "WealthPilot Demo — Full Pipeline", linked to the genuine FAR-Trans customer `F7D82BE85FF183D757BA` (dataset label `Balanced`, 52 months, 370 transactions 2018-01..2022-11; type `Mass`, band `CAP_LT30K`), chosen from `find_demo_risk_candidates.py` output and checked against `customer_information.csv`. `Predicted_*` / `Not_Available` filtering untouched; no label, transaction or result invented; the persona files hold no computed value.
- Twelve **monthly records** (2025-10..2026-09), three goals, a complete 25-answer questionnaire, complete financial inputs (essential 38,000; liquid assets 300,000 = 7.9 months, above the six-month target; contribution 20,000).
- Package/seed/validator support for optional `monthly_records/` (idempotent; writes only missing months; never overwrites a month the user changed).
- `scripts/load_local_market_data.py` (public prices into a named SQLite file only, via the project's own `fetch_ohlcv`; gitignored snapshot).
- Fix: the Behaviour & Sentiment endpoint's stored assessment now falls back to the latest analysis run (shape and `data_source` unchanged).
- Sign-in entry "Use Full Pipeline Demo" (find-only, like the family demo).
- `seed_demo_data.py verify` works on the local SQLite database (JSON column parsed).

## 3. Selecting it
Sign in -> **Use Full Pipeline Demo** (the persona is found by exact name; unseeded environments get a message). Local customer id in my verification database was 5 (ids differ per database; the package stores none).

## 4. Seed / reset (local, throwaway database)
```
python scripts/local_synthetic_backend.py --db demo.db --prepare-only
python scripts/load_local_market_data.py --db demo.db            # public prices; snapshot cached for offline rebuilds
python scripts/local_synthetic_backend.py --db demo.db --port 8001
cd backend ; (DATABASE_URL=sqlite:///.../demo.db)  python scripts/seed_demo_data.py setup  --base-url http://127.0.0.1:8001
                                                   python scripts/seed_demo_data.py verify --base-url http://127.0.0.1:8001
```
A second `setup` created nothing (5 customers, 12 goals, 12 monthly records unchanged). Reset a local demo by deleting the `.db` file (`seed_demo_data.py reset` uses PostgreSQL-only SQL and is for a hosted database).

## 5. Results returned by the application for persona E (live run, prices 2022-01-03 .. 2026-10-22, 3,617 rows)
| Stage | Result |
| --- | --- |
| Risk (existing model, FAR-Trans features) | **Balanced**, confidence 0.6629; probabilities Aggressive 0.1626, Balanced 0.6629, Conservative 0.0039, Income 0.1706; equals the dataset's own label |
| Graph | passed `information_request`; ran risk, financial health, goals, market, portfolio, compliance; status **approved** |
| Emergency fund | required 228,000; current 300,000; shortfall 0; sufficient |
| Goal: Home Down Payment | target 1,200,000 -> 1,483,959.80 inflation-adjusted; required contribution 17,580.94; difference -2,419.06; Monte Carlo 83.97% -> **Feasible** |
| Goal: Child Higher Education | 1,800,000 -> 3,170,955.90; required 12,596.20; difference -7,403.80; 99.02% -> **Feasible** |
| Goal: Retirement Corpus | 9,000,000 -> 37,391,991.72; required 24,413.58; difference +4,413.58; 68.23% -> **At Risk** |
| Market regime (latest) | e.g. QQQ Volatile, ^IXIC Range-bound, ^NDX Volatile |
| Portfolio (graph's first pass, MVO) | QQQ 0.35, AGG 0.00, GLD 0.65; E[r] 17.4%, volatility 15.8%, Sharpe 1.10 |
| Recommendation | **approved, equal_weight** (Balanced's risk-conditioned strategy): QQQ / AGG / GLD 1/3 each; E[r] 10.06%, volatility 11.59%, Sharpe 0.868. Rationale: goal feasibility "At Risk" prefers MVO and the Volatile regime prefers HRP, but risk suitability overrides both |
| Compliance | **PASS**, 5 rules evaluated, none triggered (version v1) |
| Behaviour (12 months) | expenses +1,000 (+1.9%); savings -1,000 (-5.6%); investing unchanged; 2026-09 expenses 53%, savings 17%, investing 20% of income; savings and investing reported 12 of 12 months; debt and goal progress stated as not computed |
| Explanation | locally `failed: configuration_failure` (no Gemini key; the offline launcher blanks it). The Why page's plain-language view is built from the computed values; the written tab needs a key |
Other personas on the same database: A approved (Aggressive 0.913, MVO QQQ 0.55 / GLD 0.45, PASS), B savings-first (Balanced 0.764), C **rejected** by compliance (`emergency_fund_savings_first`, no recommendation, no explanation), D pending.

## 6. Verification
See `docs/TEST_PLAN.md` section 26 for the commands and counts. Browser: real sign-in through the new button, then Risk, Portfolio, Recommendation, Goals, Why This Recommendation, Behaviour & Sentiment and Financial Health at 1366 px and the first six at 390 px; values equal the API; no horizontal overflow.

## 7. Limitations
- The aggregate CSV covers A-D only (it is exported from the live application's database; regenerating it locally would rewrite their rows); E joins it when the owner regenerates it against the live database.
- E's allocation and goal figures depend on the loaded prices; a fresh public download is not the data the Phase 6 models were evaluated on. Pipeline tests use test-only synthetic prices and assert contracts, not prices.
- The written (Gemini) explanation was not exercised (no key in the offline launcher).
- Not applied to `neondb` (forbidden here): the owner runs `seed_demo_data.py setup` against their own environment, which already holds market data.
- Ordinary profiles still stop at "information request" by design; this task did not change that.
