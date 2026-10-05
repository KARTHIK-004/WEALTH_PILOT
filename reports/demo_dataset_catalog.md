# Demo Dataset Catalog

This catalog documents every customer in WealthPilot AI's controlled demo
population — three synthetic identities (Demo Data phase), plus Phase 24's
pre-existing canonical demo customer (preserved, unchanged). Every field
and result below was read directly from a real API response or a
read-only database query; nothing here is asserted from memory or
intention. **INTENDED PURPOSE is stated separately from ACTUAL PIPELINE
RESULT for every customer, and no customer is described as "approved"
unless the API genuinely returned that status.**

**Updated by Phase 28** (`reports/phase28_financial_input_savings_first_report.md`):
until this phase, no customer's ACTUAL result could ever be "approved" —
a structural gap explained in full in
`reports/demo_data_completion_report.md` §4 and (with a second,
independently-found cause) in
`reports/live_analysis_flow_fix_report.md` §2. Phase 28 closed that gap
with a real, explicit financial-input data contract
(`GET`/`PUT /api/profiles/{id}/financial-inputs`) and a compliance-rule
correction distinguishing a legitimate savings-first proposal from an
invalid portfolio. Two of the three synthetic personas below now
genuinely reach `approved` (one via a real MVO portfolio, one via a real,
approved savings-first recommendation) — re-verified live, not assumed.
The other two personas (Compliance, and Phase 24's own canonical
customer) are unchanged, continuing to demonstrate the fail-closed REJECT
and pending-information paths respectively.

---

## 1. WealthPilot Demo Customer (Phase 24 — preserved, unchanged)

- **Customer ID**: 29096
- **Purpose**: The original canonical Demo Account customer (Phase 24),
  resolved automatically when a viva presenter clicks the individual demo
  entry (now labelled "Use Individual Demo") on the login page — and, since
  the Live Analysis Flow phase, only when "Complete" is not seeded. Represents the "Information Required" case.
- **Profile**: name "WealthPilot Demo Customer", age 34, income 62000,
  employment status "Full-time", customer type "Mass", investment
  capacity "CAP_30K_80K". `data_source`: `user-entered`.
- **Questionnaire**: 25 answers (all real questions from `GET
  /api/questionnaire`, a fixed middle-option selection — see Phase 24's
  own report).
- **Goals**: 2 (Retirement, House Purchase) — created via `POST
  /api/profiles/{id}/goals` in Phase 24.
- **Transaction-history design**: none — this customer has no
  `risk_inputs.external_customer_id` linkage at all, by design (Phase
  24's own choice to demonstrate a genuinely "user-entered, no FAR-Trans
  history" customer).
- **Intended demonstration state**: `pending_information` ("Information
  Required").
- **ACTUAL analysis state** (re-verified this phase): `pending_information`.
- **Risk result**: unavailable — `"engineered feature row was not
  provided (no genuine risk label or no point-in-time-visible
  transactions for this customer)"`.
- **Financial-health / goal / market / portfolio / compliance /
  recommendation / explanation**: not reached (the graph halts at
  `information_request` → `pending_information` immediately after risk
  classification).
- This phase made **no change** to this customer's data or behavior. It
  was re-verified present exactly once, and its verification-only
  `analysis_runs`/`agent_logs` byproducts from this phase's own testing
  were cleaned up afterward.

---

## 2. WealthPilot Demo — Complete

- **Customer ID**: 29098
- **Purpose (INTENDED)**: The most complete real demonstration this
  architecture can produce today — highest available risk-model
  confidence, enough real trading history for behaviour-drift detection
  to also produce a genuine (non-"unavailable") result, a full 25-answer
  questionnaire, and two goals.
- **Profile**: name "WealthPilot Demo — Complete", age 41, income 98000,
  employment status "Full-time", customer type "Premium", investment
  capacity "CAP_80K_300K". `data_source`: `user-entered` (the same value
  `POST /api/profiles` always assigns, unmodified).
- **Questionnaire configuration**: 25 real answers, each the FIRST option
  of its question (a fixed, position-based, content-blind selection rule
  — see `reports/demo_data_completion_report.md` §5).
- **Goals**: Retirement (target €400,000 by 2050-01-01, current savings
  €35,000, priority 1), House Purchase (target €90,000 by 2031-06-01,
  current savings €20,000, priority 2).
- **Transaction-history design**: `risk_inputs.external_customer_id =
  "4E6A7212289A2EA941BB"` — a REAL, already-present, genuinely
  risk-labeled FAR-Trans customer (chosen by
  `scripts/find_demo_risk_candidates.py` for having the highest
  risk-model confidence, 0.913, among candidates with ≥4 months of
  trading history). This is the system's OWN existing linkage mechanism
  (`data/ingestion.py` sets the identical field for FAR-Trans's entire
  real population) — not a fabricated transaction history, and not
  personal information (FAR-Trans transactional data carries no PII).
- **Financial inputs (Phase 28)**: `monthly_essential_expenses` €3,000,
  `current_liquid_assets` €40,000 (comfortably above the 6×€3,000=€18,000
  required — a genuinely SUFFICIENT emergency fund, not engineered to
  bypass any rule), `contribution_amount` €1,000/month,
  `annual_return_rate` 7%, `annual_inflation_rate` 3% — submitted via the
  real `PUT /api/profiles/29098/financial-inputs`, plausible but
  clearly-synthetic numbers, the same category of synthetic data every
  other profile field already is.
- **Intended demonstration state**: as complete as possible — now
  including a real, sufficient set of financial inputs.
- **ACTUAL analysis state** (`analysis_id 165`, live-verified in Phase
  29 — supersedes id 150, computed under the Phase 28 goal-frequency
  defect; see §8): **`approved`**.
- **Risk result**: category `Aggressive`, confidence **0.9126**
  (class probabilities: Aggressive 0.913, Balanced 0.072, Income 0.015,
  Conservative 0.001) — a real, high-confidence classification, unchanged
  from before Phase 28 (financial inputs do not affect risk classification).
- **Financial-health / behaviour result**: `behaviour_drift_flag: false`,
  `isolation_forest_anomaly: false` — a genuine, non-"unavailable"
  behaviour-model result (this customer's real linked history has 21
  months of trading activity, well above the 4-month minimum).
  `expense_persona`: unavailable (permanent, structural — FAR-Trans has
  no income/expense fields; see completion report §4) — unchanged, this
  is not affected by the new financial-input contract either.
- **Goal result** (Phase 29, corrected): Retirement — required
  contribution €887.40/month vs €1,000 supplied (contribution gap
  −€112.60, i.e. ahead of plan), Monte Carlo success probability **94.1%**,
  feasibility **"Feasible"**; House Purchase — required €1,146.88/month
  vs €1,000 supplied (gap +€146.88), probability **50.3%**, feasibility
  **"At Risk"**. Probability and deterministic gap agree in direction.
  (The earlier version of this line — "Not Feasible, 0%" for both — was an
  artifact of a daily-vs-monthly return-frequency defect in Phase 28's
  wiring, not an honest result; fixed in Phase 29, ADR-027.)
- **Emergency fund**: required €18,000, current €40,000, shortfall €0,
  **sufficient: true**.
- **Market result**: real regime data for 5 instruments (^IXIC, ^NDX,
  QQQ, AGG, GLD).
- **Portfolio result**: strategy `mvo`, risk level `Aggressive`, real
  optimizer weights **QQQ 55.0% / AGG ~0.0% / GLD 45.0%**, expected return
  17.4%, expected volatility 16.4%, Sharpe ratio 1.062 — genuine Phase 8
  `core.optimizer` output, unmodified.
- **Compliance result**: `PASS`. Zero rules triggered.
- **Recommendation**: `status: "approved"`, `selected_strategy: "mvo"` —
  the SAME weights as the portfolio result, copied verbatim (Phase 14,
  unmodified).
- **Explanation**: `status: "completed"`. Gemini's own live call fell back
  to Phase 13's existing, already-approved templated restatement this run
  (`validation_passed: false`, a pre-existing fallback path, not something
  Phase 28 touches) — the summary/risk/goal/portfolio/market/compliance
  explanation fields are all populated, and the standard disclaimer is
  present.

---

## 3. WealthPilot Demo — Savings

- **Customer ID**: 29099
- **Purpose (INTENDED)**: Explicitly demonstrates the savings-first
  mechanism — since emergency-fund status is never supplied to the live
  pipeline for ANY customer, `savings_first_node` (not the MVO/HRP/1-N
  optimizer) is the real node that runs for every customer that clears
  the risk-confidence gate, this one included.
- **Profile**: name "WealthPilot Demo — Savings", age 29, income 52000,
  employment status "Full-time", customer type "Mass", investment
  capacity "CAP_30K_80K".
- **Questionnaire configuration**: 25 real answers, each a middle option
  of its question — deliberately a different selection pattern from
  "Complete."
- **Goals**: Emergency Fund (target €15,000 by 2028-01-01, current
  savings €3,000, priority 1), Retirement (target €220,000 by 2055-01-01,
  current savings €5,000, priority 2).
- **Transaction-history design**: `risk_inputs.external_customer_id =
  "71162EE533DC9878B32D"` — a real FAR-Trans customer predicted
  `Balanced` with confidence 0.764 and 14 months of trading history.
- **Financial inputs (Phase 28)**: `monthly_essential_expenses` €2,500,
  `current_liquid_assets` €4,000 — deliberately, KNOWINGLY insufficient
  (6×€2,500=€15,000 required, €4,000 on hand), consistent with this
  persona's own "Emergency Fund" goal above showing only €3,000 saved so
  far. `contribution_amount` €400/month, `annual_return_rate` 6%,
  `annual_inflation_rate` 3%.
- **Intended demonstration state**: savings-first behavior visible in the
  node trace, now reaching a real `approved` overall result with
  `recommendation.status == "savings_first"` (previously proven
  unreachable — see completion report §4 — now closed by Phase 28).
- **ACTUAL analysis state** (`analysis_id 166`, live-verified in Phase
  29 — supersedes id 151, computed under the Phase 28 goal-frequency
  defect; see §8): **`approved`**.
- **Risk result**: category `Balanced`, confidence **0.7636** — unchanged
  from before Phase 28.
- **Financial-health result**: `behaviour_drift_flag: false`,
  `isolation_forest_anomaly: false` (real result, 14 months of history).
- **Goal result** (Phase 29, corrected): Emergency Fund (due 2028) —
  required €794.64/month vs €400 supplied (gap +€394.64), success
  probability **0.0%**, **"Not Feasible"** (a short deadline against about
  double the supplied contribution — a real result, not the earlier
  artifact); Retirement (due 2055) — required €543.03/month vs €400
  supplied (gap +€143.03), probability **88.6%**, **"Feasible"** (a long
  horizon lets the bootstrap's historical growth carry the shortfall;
  deterministic gap and Monte Carlo can legitimately differ because the
  former assumes the customer's stated 6% return and the latter
  resamples real market history). The earlier version of this line
  ("Not Feasible" for both) reflected the Phase 28 daily-vs-monthly
  return-frequency defect (ADR-027).
- **Emergency fund**: required €15,000, current €4,000, **shortfall
  €11,000**, **sufficient: false**.
- **Market result**: real regime data for 5 instruments, same as every
  persona (this node's output does not vary by customer).
- **Portfolio result**: strategy `savings_first`, `weights: null`,
  `unavailable_reason`: "normal portfolio optimization deferred:
  emergency-fund shortfall of 11000.00 -- build liquidity before
  investing" — a real, honest `savings_first_node` output (Phase 10,
  unmodified), no longer an error (Phase 28's `savings_first_node` fix).
- **Compliance result**: `PASS`. Zero rules triggered —
  `emergency_fund_savings_first` correctly recognizes a genuine
  savings-first proposal for a known-insufficient fund as compliant
  (its own unmodified rule logic), and the four weight-validation rules
  correctly recognize the absent weights as expected for this legitimate
  case (Phase 28's compliance fix), not as an invalid portfolio.
- **Recommendation**: `status: "savings_first"`, `selected_strategy:
  null` — Phase 14's own, unmodified savings-first handling, reached live
  for the first time this phase.
- **Explanation**: `status: "completed"` (same templated-fallback pattern
  as "Complete" above).

---

## 4. WealthPilot Demo — Compliance

- **Customer ID**: 29100
- **Purpose (INTENDED)**: The central, most pedagogically important state
  every real customer that clears risk-confidence currently reaches —
  demonstrates that the compliance gate is real, binding, and cannot be
  bypassed, with the full 5-rule breakdown visible on the Recommendation
  page / via `GET /api/analysis/{id}`.
- **Profile**: name "WealthPilot Demo — Compliance", age 58, income
  71000, employment status "Full-time", customer type "Professional",
  investment capacity "CAP_80K_300K".
- **Questionnaire configuration**: 25 real answers, each the LAST option
  of its question — a third, distinct selection pattern.
- **Goals**: Retirement (target €300,000 by 2038-01-01, current savings
  €60,000, priority 1), Education (target €40,000 by 2029-01-01, current
  savings €10,000, priority 2).
- **Transaction-history design**: `risk_inputs.external_customer_id =
  "977880FDFA6713338EDC"` — a real FAR-Trans customer predicted
  `Conservative` with confidence 0.777 and 6 months of trading history.
- **Financial inputs (Phase 28)**: deliberately NOT supplied — see
  `purpose` above. This is the one persona Phase 28 left untouched,
  precisely so it keeps demonstrating the fail-closed REJECT path for
  genuinely missing data.
- **Intended demonstration state**: `blocked_rejected`/`rejected` — this
  is the ONE persona whose intended and actual state fully agree, both
  before and after Phase 28.
- **ACTUAL analysis state** (`analysis_id 167`, re-verified in Phase 29;
  same result as the superseded id 152):
  **`rejected`** (as intended).
- **Risk result**: category `Conservative`, confidence **0.7772** —
  unchanged.
- **Financial-health result**: `behaviour_drift_flag: false`,
  `isolation_forest_anomaly: false` (real result, 6 months of history —
  above the 4-month minimum) — unchanged.
- **Goal result**: both goals still show `unavailable_reason: "no
  GoalAssumptions (contribution/return/inflation) supplied"` — unchanged,
  since no financial inputs were supplied for this persona.
- **Emergency fund**: `sufficient: null` (genuinely unknown — no data
  supplied) — unchanged.
- **Market result**: same as every persona.
- **Portfolio result**: strategy `savings_first`, `weights: null`,
  `unavailable_reason`: "normal portfolio optimization deferred:
  emergency-fund sufficiency could not be confirmed (required financial
  inputs not supplied) -- a savings-first recommendation is given
  conservatively rather than assuming sufficiency" — Phase 28's
  `savings_first_node` fix means this is now a valid result rather than a
  silent `missing_data` error (though the terminal compliance decision is
  unaffected either way).
- **Compliance result**: `REJECT` — **now with a single, precisely
  accurate triggered rule, `emergency_fund_savings_first`** ("emergency
  -fund status was not provided"), rather than the previous 5-rule
  breakdown. The four weight-validation rules that previously triggered
  for the misleading reason "portfolio weights were not provided" now
  correctly recognize a legitimate savings-first proposal's absent
  weights as expected, not invalid (Phase 28's compliance fix) — a MORE
  accurate, not weaker, compliance explanation: the terminal decision
  (`REJECT`) is completely unchanged, only the stated reasoning is now
  precise rather than partly misleading.
- **Recommendation / explanation**: `null` — unchanged (never computed;
  gated behind `overall_status == "approved"`, which this persona,
  by its own continued design, does not reach).

---

## 5. Cross-Cutting Notes

- **Historical note**: earlier versions of this section observed that all
  three synthetic personas reached the identical terminal state
  (`rejected`), for the structural reasons `reports/
  demo_data_completion_report.md` §4 and `reports/
  live_analysis_flow_fix_report.md` §2 documented. Phase 28 closed both
  gaps (see §8 below); this is no longer true — see §2-§4 above for each
  persona's current, real, individually-verified result.
- **Real variety, now including terminal state**: three genuinely
  different risk categories (Aggressive/Balanced/Conservative) with three
  genuinely different confidence levels, three different real
  behaviour-model results, three different questionnaire answer patterns,
  and now — since Phase 28 — three different real terminal outcomes:
  `approved` (real MVO portfolio), `approved` (real savings-first
  recommendation), and `rejected` (fail-closed, missing data) — every one
  of them a real, non-fabricated, model/rule-computed difference.
- **Idempotency**: `scripts/seed_demo_data.py setup` re-run after Phase 28
  reused the existing customer/questionnaire/goals rows unchanged
  (zero new rows) and only added the previously-absent `financial_inputs`
  row for "Complete"/"Savings" — re-running it again is a genuine no-op
  for every field, including financial inputs (the script checks for an
  existing, non-null `monthly_essential_expenses` before submitting).
- **Cleanup discipline**: every `analysis_runs` row created purely by a
  live-verification call whose profile hash matched an already-cached run
  reused that SAME cached row (confirmed: identical `analysis_id` before
  and after each such check) — no duplicate rows were created by
  verification alone; only genuine input changes (adding financial
  inputs) produced new, real, intentionally-kept rows.

## 6. Live Analysis Flow Phase — Demo-Account Resolution Change

`frontend/src/lib/demo-customer.ts`'s `resolveDemoCustomer()` (called by
both "Sign In" and "Use Demo Account", per the post-login profile-flow
fix) now prefers "WealthPilot Demo — Complete" (looked up by exact name
via the new, minimal `GET /api/profiles/lookup` endpoint) over Phase 24's
original "WealthPilot Demo Customer", falling back to the original
customer only when "Complete" is not present in this environment. Full
rationale, the endpoint's design, and why it was the smallest necessary
API addition are in `reports/live_analysis_flow_fix_report.md`. As of
Phase 28, the customer that resolution now reaches ("Complete", 29098)
genuinely reaches `approved` — the demo account's primary experience is a
real approved recommendation, not a REJECT.

## 7. Phase 28 — Financial-Input Data Contract

Full rationale, schema, API design, compliance-rule fix, and
`savings_first_node` fix are documented in full in `reports/
phase28_financial_input_savings_first_report.md`. Summary as it applies
to this catalog: a new `financial_inputs` table (one row per customer,
every field independently nullable) plus `GET`/`PUT /api/profiles/{id}/
financial-inputs` let a customer's `monthly_essential_expenses`/
`current_liquid_assets` (emergency-fund inputs) and `contribution_amount`/
`annual_return_rate`/`annual_inflation_rate`/
`contribution_periods_per_year` (`GoalAssumptions`) be supplied for the
first time — wired into `analysis_service.py::_build_graph_dependencies`,
never duplicating any calculation `core/goals.py` already owns. A
companion fix in `core/compliance.py` correctly recognizes a legitimate
savings-first proposal's absent portfolio weights as expected, not
invalid. "WealthPilot Demo — Complete" and "WealthPilot Demo — Savings"
now have real financial inputs on file (via the real API, never direct
SQL); "WealthPilot Demo — Compliance" and Phase 24's canonical customer
deliberately do not, preserving their own original demonstration
purposes. Every number in §2-§4 above was read directly from a real,
live `POST /api/analysis` response after this change — none was
hand-entered into the database or asserted from intention.

## 8. Phase 29 — Final Integration Re-Verification

All four personas were re-run through the real `POST /api/analysis` and
(for the three that reach the graph's terminal states) the real `GET
/api/analysis/stream`, in-process against the real database. Outcomes
match each persona's intended state: **29098** `approved` (real MVO
weights, compliance PASS, recommendation `approved`/`mvo`); **29099**
`approved` with `recommendation.status == "savings_first"` (no weights);
**29100** `rejected` (exactly one triggered rule,
`emergency_fund_savings_first`, "required data unavailable: emergency-fund
status was not provided"; no recommendation, no explanation);
**29096** `pending_information` (no risk result, nothing downstream).

Two defects were found and fixed by that validation, both recorded in
`reports/phase29_final_integration_report.md`: (1) goal Monte Carlo was
fed daily returns for monthly periods, forcing every goal to 0.0% — the
goal results in §2/§3 above are the corrected ones (ADR-027); (2) the SSE
`savings_first` summary always said "Emergency fund insufficient", even for
29100 whose sufficiency is *unknown* — it now says "could not be
confirmed" in that case. Because the cache key now includes a pipeline
version, every persona recomputed and received a new analysis id
(165–168, superseding 150–153; the superseded rows are left in place as
history — the frontend only ever reads the current run via `POST
/api/analysis`). SSE-created recommendation rows from the verification
runs were removed afterwards; each approved persona retains one
recommendation row from the Phase 28 run and one from the Phase 29
recompute.

## 9. Family Demo Household (demo-experience update)

A single canonical household, built by `backend/scripts/seed_demo_data.py
setup-family` through the real public household API (ADR-036). Idempotent:
records are keyed by their natural label, so a second run creates nothing.

- **Household**: "WealthPilot Demo Family" — id **6** in this environment
  (ids 1–5 were consumed by earlier rolled-back verification runs; PostgreSQL
  sequences do not roll back).
- **Primary**: "WealthPilot Demo — Savings" (29099) — `self` / `primary` / not a
  dependent. **Spouse**: "WealthPilot Demo — Compliance" (29100) — `spouse` /
  `member`. No dependent (it would need a new customer record).
- **Not members**: "WealthPilot Demo — Complete" (29098) and "WealthPilot Demo
  Customer" (29096), so the individual demo is unchanged.
- **Individual data**: unchanged for all four personas — profile, individual
  goals, questionnaire, financial inputs and the full analysis response were
  compared before and after seeding and are identical.

Synthetic household-level values (EUR, demo only — never training data, never
an input to any individual analysis):

| Resource | Records |
|---|---|
| Income (5) | Primary salary (net) 2,800 monthly · Spouse salary (net) 3,100 monthly · Rental income 9,600 yearly · Annual bonus 3,000 one-time · Previous part-time job 600 monthly, **inactive** |
| Expenses (8) | Rent 1,650 · Groceries 750 · Energy and water 190 · Public transport and fuel 260 (monthly, essential) · Home and car insurance 1,440 yearly, essential · Dining and leisure 350 · Streaming subscriptions 45 (monthly, non-essential) · New sofa 1,200 one-time |
| Assets (4) | Joint current account 6,000 (liquid) · Emergency savings account 9,500 (liquid) · Index fund 22,000 · Family car 12,000 |
| Liabilities (2) | Car loan 7,800 outstanding, 310/month, 5.9% · Credit card **0** outstanding, monthly payment **not provided** |
| Goals (3) | Emergency fund 18,000 by 2027-12-31 (9,500 saved) · Home deposit 45,000 by 2030-06-30 (6,000 saved) · Family holiday 4,000 by 2027-08-01 (current amount not provided) |

Financial summary, as the unchanged Phase 34 engine returns it: recurring
monthly income **6,700**; one-time income 3,000; recurring monthly expenses
**3,365** (essential 2,970, non-essential 395); one-time expenses 1,200;
monthly cash flow **3,335**; total assets 49,500 (liquid 15,500); outstanding
liabilities 7,800 with recorded monthly payments 310; net position **41,700**;
emergency fund required **17,820** against 15,500 liquid — shortfall 2,320,
**insufficient**.

## 10. Demo Dataset Package (`demo_data/`, ADR-038)

Every value in sections 1-9 now lives in `demo_data/`, the single source. The
seed script reads it and no longer holds it inline. See `demo_data/README.md`
for the full description.

| Key | Persona | Files |
| --- | --- | --- |
| `WPDEMO-A` | WealthPilot Demo — Complete (§2) | profile, 25 answers (first option), inputs, 2 goals |
| `WPDEMO-B` | WealthPilot Demo — Savings (§3) | profile, 25 answers (middle option), inputs, 2 goals |
| `WPDEMO-C` | WealthPilot Demo — Compliance (§4) | profile, 25 answers (last option), inputs `null` + reason, 2 goals |
| `WPDEMO-D` | WealthPilot Demo Customer (§1) | profile, 25 answers (middle option), inputs `null` + reason, 2 goals; no FAR-Trans link (`null` + reason) |
| `WPDEMO-FAM` | WealthPilot Demo Family (§9) | household, 2 members, 5 income, 8 expenses, 4 assets, 2 liabilities, 3 goals |

**Faithful to what is stored.** The extraction was checked against the stored
data before anything was changed:

- the loaded personas and family equal the former inline constants exactly,
  including order;
- every persona's 25 stored answers equal its position rule;
- persona D's stored profile and goals equal the frontend fallback's
  constants.

**Also included:**

- five strategy scenarios (the only parameter the simulator accepts), plus the
  four what-ifs it cannot express, each with the reason;
- the expected contract-level states for each persona and the household;
- a seed plan;
- a generated manifest (version 1.0.0) with counts, per-file SHA-256, a content
  hash and a SHA-256 guard over the ten raw training files.

**Not included:** synthetic transactions, because the application cannot
consume them.

**Full suite (this change):** `pytest tests/ -v` ran detached and in isolation from 2026-09-30 21:03:45 to
23:12:42. Result: `1326 passed, 1 skipped, 158 warnings in 7732.26s (2:08:52)`, 0 failed, 0 errors, pytest exit
code 0. The one skip is a live-Gemini test, which skips when Gemini is unavailable (CLAUDE.md §19).
