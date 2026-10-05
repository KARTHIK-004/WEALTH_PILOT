# Phase 7 — Goal Engine Report

## 1. Status

**COMPLETE.**

## 2. Goal data model

`backend/wealthpilot/core/goals.py::GoalInput` mirrors the existing `financial_goals` table (`backend/wealthpilot/db/models.py:96-110`, unmodified) exactly: `customer_id, goal_type, target_amount, current_savings, target_date, priority`. No field was added merely for convenience — `id`/`created_at` are DB-assigned and excluded from the calculation-layer model.

Fields the project documents describe only as _scenario-adjustable_ (MASTER_PROMPT.md section 27's "Scenario Simulator": contribution amount, investment horizon, inflation assumption) live in a separate `GoalAssumptions` object, never persisted on the goal itself:

| Field                           | Constraint | Default                                                                                     |
| ------------------------------- | ---------- | ------------------------------------------------------------------------------------------- |
| `contribution_amount`           | >= 0       | none (required)                                                                             |
| `contribution_periods_per_year` | > 0        | 12 (monthly — PROJECT_PLAN.md §2.6 explicitly asks for "the required _monthly_ investment") |
| `annual_return_rate`            | > -1.0     | **none (required, no invented default)**                                                    |
| `annual_inflation_rate`         | > -1.0     | **none (required, no invented default)**                                                    |

Validation (Pydantic v2): `target_amount > 0`, `current_savings >= 0`, `customer_id > 0`, `priority >= 1`, `goal_type` non-blank (stripped, not restricted to an enumerated taxonomy — none of the three authoritative documents enumerate a closed set of goal types, so none was invented). A separate `validate_goal_for_creation(goal, current_date)` enforces `target_date` strictly after `current_date` for **new** goals — kept apart from the analysis functions below, which must also accept an _existing_ goal whose `target_date` has already arrived.

## 3. TVM methodology

Closed-form, exactly the formula given in PROJECT_PLAN.md §2.6:

```text
FV = PV(1+r)^n + PMT · [((1+r)^n − 1) / r]
```

- **Payment timing**: ordinary annuity (contributions at period end) — this is the shape the given formula requires, not a free choice.
- **Compounding/contribution frequency**: generic (`periods_per_year` parameter); `GoalAssumptions` defaults it to 12 because the spec explicitly asks for a monthly figure.
- **Interest-rate conversion**: nominal/APR-style, `periodic_rate = annual_rate / periods_per_year` — the given formula applies a single `r` directly with no separate effective-rate step.
- **Period counting**: `n_periods_between(current_date, target_date, periods_per_year) = round(years_between * periods_per_year)` — rounded to the nearest whole period, documented explicitly since section 6 requires the convention to be stated.
- `r == 0` and `n == 0` are handled as explicit limiting cases (no division by zero): `r=0` reduces to `PV + PMT·n`; `n=0` returns `PV` unchanged.
- Verified against hand-computed/spreadsheet values (not just "runs without error"), e.g. `future_value(10000, 0.06, 10, 0) == 17908.48` and `future_value(0, 0.01, 24, 500) == 13486.73`.

## 4. Inflation methodology

`inflation_adjusted_target(nominal_target, annual_inflation_rate, years) = nominal_target * (1+annual_inflation_rate)^years`. `annual_inflation_rate` has **no default anywhere in the module** — MASTER_PROMPT.md §27 lists it as a user-adjustable Scenario Simulator input, not a system constant, so every caller (including every test) must state it explicitly, and `0.0` is a valid, deliberate choice rather than a silent fallback. `GoalFundingAnalysis` reports `nominal_target_amount` and `inflation_adjusted_target_amount` as two distinct fields so they are never conflated.

## 5. Required contribution calculation

`required_periodic_contribution` solves the FV formula for `PMT`. `analyze_goal_funding()` combines TVM + inflation adjustment + required contribution into one `GoalFundingAnalysis` result, including `contribution_gap = required_periodic_contribution - assumptions.contribution_amount` (PROJECT_PLAN.md §2.6: "the shortfall against current trajectory is the funding gap") — positive means underfunded, zero/negative means on track or ahead. A negative _required_ contribution (present value alone already overshoots the target) is returned as-is, not clamped, since it is genuinely informative.

Edge case: at `n_periods == 0` (target date has arrived), a goal already funded (`current_savings >= target`) returns a required contribution of `0.0`; one with a genuine remaining shortfall raises `ValueError` — there are no periods left to close a positive gap, and silently returning a number there would misrepresent an impossible schedule.

## 6. Monte Carlo methodology

Empirical bootstrap resampling — PROJECT_PLAN.md §2.6: "sample returns from the historical distribution over N paths." For each of `n_simulations` independent paths, `n_periods` periodic returns are drawn **with replacement** from a caller-supplied `historical_returns` array and applied as an ordinary annuity: `balance = balance*(1+r) + contribution`, matching the TVM timing convention exactly. Success = ending balance >= `target_amount`.

`historical_returns` is a required argument with **zero data-fetching inside this module** — `core/goals.py` never queries Phase 6's `market_data` table or anything else. This was an explicit, approved design choice (2026-09-14): Phase 8 (portfolio construction) does not exist yet, so there is no customer-specific return series to justify picking today, and BUILD_PLAN.md's own Phase 7 entry describes `core/goals.py` with no DB dependency. Whichever later phase wires the Goal Engine into the agent/API layer decides what array to pass.

Reproducibility: a fresh `numpy.random.default_rng(random_state)` is created on every call (never a shared/global generator), so identical arguments always reproduce an identical result — verified directly by a test that calls the function twice with the same inputs.

## 7. Monte Carlo assumptions

| Parameter             | Value                                                                                                                                                                                                                                                                                                                                      | Source                                                                                                                                                                |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Number of simulations | 10,000                                                                                                                                                                                                                                                                                                                                     | Approved 2026-09-14                                                                                                                                                   |
| Time step             | matches `contribution_periods_per_year` (whatever periodicity the caller's `historical_returns` and contribution schedule share)                                                                                                                                                                                                           | Design consequence of the bootstrap approach — no separate "time step" concept needed                                                                                 |
| Return distribution   | empirical bootstrap (with replacement) from caller-supplied historical returns                                                                                                                                                                                                                                                             | PROJECT_PLAN.md §2.6                                                                                                                                                  |
| Random seed           | 42                                                                                                                                                                                                                                                                                                                                         | CLAUDE.md rule 9                                                                                                                                                      |
| Contribution schedule | ordinary annuity, same `periodic_contribution` every period                                                                                                                                                                                                                                                                                | Matches TVM timing                                                                                                                                                    |
| Inflation handling    | **not applied inside the Monte Carlo loop itself** — a caller wanting an inflation-adjusted target compares the simulated balances against an already inflation-adjusted `target_amount` (e.g. `analyze_goal_funding`'s `inflation_adjusted_target_amount`), computed once via `inflation_adjusted_target()` before calling the simulation | Keeps the simulation loop free of a second, redundant inflation compounding                                                                                           |
| Success criterion     | `ending_balance >= target_amount`, checked once at the horizon                                                                                                                                                                                                                                                                             | PROJECT_PLAN.md §2.6 ("report the share reaching the target")                                                                                                         |
| Reported percentiles  | 10th (downside) / 50th (median) / 90th (upside) of the ending-value distribution                                                                                                                                                                                                                                                           | Reporting-shape choice, documented in the module docstring — does not affect the success-probability number itself, so decided directly rather than put to a question |

Verified: `target_amount` never influences the simulated balance paths themselves (only the post-simulation success/shortfall/surplus comparison) — proven by a test running two simulations with identical inputs except `target_amount`, asserting identical `median_ending_value`/percentiles.

## 8. Feasibility methodology

`classify_feasibility(success_probability)` → **Feasible** (>= 0.80), **At Risk** (0.50-0.79), **Not Feasible** (< 0.50). Thresholds and category names approved 2026-09-14 (none of the three authoritative documents specify numeric thresholds — MASTER_PROMPT.md's example output only shows an illustrative `success_probability: 0.78` with no accompanying category). Deterministic given identical `success_probability`; rejects any input outside `[0, 1]`.

## 9. Emergency-fund methodology

`assess_emergency_fund(monthly_essential_expenses, current_liquid_assets, target_months=6)` → `required_amount = monthly_essential_expenses * target_months`; `shortfall = max(0, required - current)`; `surplus = max(0, current - required)`; `sufficient = current >= required`. The 6-month target was approved 2026-09-14 (not specified in any authoritative document). "Essential expenses" and "liquid assets" are plain caller-supplied numbers — this module does not decide which upstream field (e.g. Kaggle's `essential_spending`/`emergency_fund` columns, noted during investigation but not wired up here) feeds them; that is an integration decision for a later phase.

## 10. Savings-first logic

`savings_first_required(status) = not status.sufficient` — the exact rule given in PROJECT_PLAN.md §2.6 / MASTER_PROMPT.md section 14 ("IF emergency fund insufficient: savings-first condition = TRUE"), nothing more. No portfolio logic, allocation, or optimization of any kind is computed here or anywhere else in this phase.

## 11. Validation

Pydantic v2 (`GoalInput`, `GoalAssumptions`) plus explicit `ValueError`s inside every calculation function for conditions Pydantic field constraints can't express (e.g. `n_periods < 0`, `periodic_rate <= -1.0`, a positive shortfall at `n_periods == 0`, `success_probability` outside `[0,1]`). No condition is silently coerced into a "valid-looking" number.

## 12. Edge cases handled

Goal already achieved; zero current balance; zero contribution; zero return; negative return (allowed, rejected only at/below -100%); target date equal to current date (valid for _analysis_, invalid for _creation_); target date in the past (rejected everywhere with a clear message); very short horizon (1 period); very long horizon (600 periods / 50 years); zero inflation; emergency fund insufficient/already sufficient/exactly at target; target amount <= current amount; invalid (non-positive) contribution frequency; invalid date types; invalid (negative/zero where disallowed) monetary values. Every case above has a dedicated test, not just an assertion that the function runs.

## 13. Tests

**95 new Phase 7 tests**, all passing (`tests/backend/core/`):

| File                     | Tests | Covers                                                                                                                                                                                                    |
| ------------------------ | ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_validation.py`     | 20    | `GoalInput`/`GoalAssumptions` field validation, creation-vs-analysis date boundary, required-vs-defaulted assumption fields                                                                               |
| `test_tvm.py`            | 26    | FV/PV against hand-computed values, required contribution (incl. negative-PMT and zero-period cases), inflation adjustment, period-counting, short/long horizons, `analyze_goal_funding` integration      |
| `test_monte_carlo.py`    | 20    | Reproducibility, output shape, success-probability monotonicity, edge cases (zero periods, zero balance, negative/constant returns, empty array), target-amount non-leakage, bootstrap order-independence |
| `test_feasibility.py`    | 9     | Threshold boundaries (inclusive), out-of-range rejection, determinism                                                                                                                                     |
| `test_emergency_fund.py` | 13    | Required/shortfall/surplus/sufficiency math, custom target months, savings-first rule                                                                                                                     |
| `test_serialization.py`  | 4     | JSON round-trip of every output model, no leaked numpy scalar types                                                                                                                                       |

**Full project test suite: 218 tests, all passing** (`pytest tests/ --collect-only -q` confirms 218 collected, 0 skipped; 218 passed in 234s). No regressions in Phases 0-6.

## 14. Database changes

**None.** `financial_goals` already matched the specification exactly; `backend/wealthpilot/db/models.py` (last modified 2026-09-13, before this phase started) was not touched. No Alembic migration was created — `backend/alembic/versions/` still holds only the three pre-existing migrations from Phases 1 and 3. No other table (`customers`, `customer_risk_snapshots`, `transactions`, `market_data`) was read or written by this phase's code.

## 15. Files created/modified

- **Created**: `backend/wealthpilot/core/goals.py` (the entire Goal Engine).
- **Created**: `tests/backend/core/test_{validation,tvm,monte_carlo,feasibility,emergency_fund,serialization}.py`.
- **Created**: this report.
- **Modified**: nothing else. `models/metrics.json` was not touched — none of the three authoritative documents call for a Goal Engine metrics section (unlike Phases 4-6, which train and version actual models), so none was invented merely for symmetry; its four existing top-level keys (`risk`, `behaviour`, `expense`, `market`) are unchanged, confirmed both by content inspection and by its file modification time predating this phase's work.

## 16. Known limitations

1. **No data source is wired up for `historical_returns`, `monthly_essential_expenses`, or `current_liquid_assets`.** By design (§6, §9) — this module is a pure calculation engine with zero DB/API dependency, per BUILD_PLAN.md's own scoping of `core/goals.py`. A later phase must decide, e.g., which Phase 6 instrument(s) or blend feed the Monte Carlo bootstrap, and which Kaggle/transaction fields populate the emergency-fund inputs.
2. **`years_between`'s day-count convention** (`(target_date - current_date).days / 365.25`) does not model leap years exactly day-by-day; it is a standard approximation, not a bug, but is worth naming explicitly since it feeds every period-count calculation.
3. **No withdrawal-phase or tax modeling.** Out of scope per the authoritative documents (none mention either), and per the explicit instruction not to invent tax/withdrawal assumptions.

## 17. Manual verification

- [x] Authoritative documents (CLAUDE.md, PROJECT_PLAN.md, MASTER_PROMPT.md, BUILD_PLAN.md) inspected before writing any code.
- [x] Goal schema (`GoalInput`) matches the existing `financial_goals` table exactly — no invented fields.
- [x] TVM calculations verified against hand-computed values (not just "runs").
- [x] Inflation calculation distinguishes nominal vs. inflation-adjusted target as two separate output fields.
- [x] Required contribution solves back to a known PMT in both nonzero- and zero-rate cases.
- [x] Monte Carlo uses the approved methodology (empirical bootstrap, caller-supplied return series, 10,000 simulations, seed 42).
- [x] Monte Carlo is reproducible (same seed + inputs -> bit-identical results, directly tested).
- [x] Feasibility classification follows the approved thresholds exactly (0.80 / 0.50, both boundaries inclusive on the higher side).
- [x] Emergency-fund calculation follows the approved 6-month target.
- [x] Savings-first rule implemented exactly as specified, nothing more.
- [x] No portfolio weights were generated anywhere in this phase.
- [x] No portfolio optimization (MVO/HRP/1-N/covariance/asset selection) was implemented.
- [x] No Phase 8 code was started — `backend/wealthpilot/core/optimizer.py` does not exist.
- [x] No LLM calculates any financial value — this module has no Gemini/LangGraph/AutoGen dependency at all.
- [x] Previous Phase 0-6 functionality remains intact — full suite re-run, 218/218 passing.
- [x] `models/metrics.json`'s four existing sections are byte-for-byte unchanged (file modification time predates this phase).
- [x] Database integrity verified — `db/models.py` untouched, no new Alembic migration, no table read or written by this phase's code.
- [x] Complete test suite passes (218 collected, 218 passed, 0 skipped).
- [x] Raw datasets (`datasets/raw/FAR-Trans/`, `datasets/raw/kaggle/`) untouched — modification timestamps unchanged from Phase 6's own check.
- [x] No unapproved dependency added — `goals.py` imports only `numpy` and `pydantic`, both already in `backend/pyproject.toml`'s approved dependency list; the file itself is unmodified since Phase 6's yfinance version bump.

## 18. Next phase

**Phase 8 — Portfolio Optimization.**

**Do not begin Phase 8.** Awaiting explicit approval of this report.
