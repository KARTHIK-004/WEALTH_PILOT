"""Phase 7 — deterministic Goal Engine.

Pure, DB-free calculation module (BUILD_PLAN.md: "Builds: core/goals.py.
Depends on: Phase 1 schema (goal fields)" — compatibility with the existing
`financial_goals` table, not a live DB dependency). No FastAPI, LangGraph,
AutoGen, or Gemini code may import financial-calculation logic from anywhere
else; those layers call into this module and pass through its numbers
unchanged (CLAUDE.md rule 1: "The LLM never computes a number").

`GoalInput` mirrors the existing `financial_goals` table exactly
(`backend/wealthpilot/db/models.py`: `goal_type, target_amount, target_date,
current_savings, priority`) — no field was added to it. Fields the project
documents describe only as user/scenario-adjustable inputs (contribution
amount, contribution frequency, expected return, inflation rate — see
MASTER_PROMPT.md section 27, "Scenario Simulator") live in a separate
`GoalAssumptions` object passed alongside the goal, not persisted on it.

Documented methodology decisions (CLAUDE.md rule "never invent financial
logic" — every one of these was either given explicitly by the project
documents or approved via an explicit question before implementation):

- **Payment timing**: ordinary annuity — contributions land at the END of
  each period. This is not a free choice: it is the shape of the exact
  formula PROJECT_PLAN.md section 2.6 gives,
  `FV = PV(1+r)^n + PMT * [((1+r)^n - 1) / r]`, which only holds for
  end-of-period payments.
- **Compounding / contribution frequency**: `GoalAssumptions.
  contribution_periods_per_year` defaults to 12 (monthly) because
  PROJECT_PLAN.md section 2.6 explicitly asks to "solve for PMT to get the
  required *monthly* investment" and MASTER_PROMPT.md's own example field is
  `required_monthly_saving`. The default is overridable — the underlying
  formulas are period-length-agnostic — but monthly is what the documents
  actually specify, not an invented convenience.
- **Interest-rate conversion**: nominal/APR-style, `periodic_rate =
  annual_rate / periods_per_year`. The formula above uses a single `r`
  applied directly to `(1+r)^n` with no separate effective-rate conversion
  step, so this is the reading that matches the given formula, not an
  independent choice.
- **Expected return and inflation rate**: NEVER hardcoded. Both are
  required arguments on `GoalAssumptions` with no default value — Pydantic
  refuses to construct the object without them. This mirrors
  MASTER_PROMPT.md section 27, which lists "Inflation assumption" (and
  "Investment horizon") as a *Scenario Simulator* input the user adjusts,
  not a constant the engine owns. Zero inflation or zero return are valid,
  explicit choices the caller must make (`annual_inflation_rate=0.0` is a
  real, deliberate argument, never a silent default).
- **Monte Carlo return sampling**: empirical bootstrap resampling (with
  replacement) from a caller-supplied `historical_returns` array — per
  PROJECT_PLAN.md section 2.6, "sample returns from the historical
  distribution over N paths." This module performs zero data I/O and never
  reads Phase 6's `market_data` table directly: which historical series to
  bootstrap from is a decision for whichever later phase wires the Goal
  Engine into the agent/API layer — Phase 8 (portfolio construction) does
  not exist yet, so there is no customer-specific return series to pick
  today. (Approved 2026-09-14 via AskUserQuestion.)
- **Monte Carlo simulation count**: `MONTE_CARLO_SIMULATIONS = 10_000`,
  approved 2026-09-14.
- **Monte Carlo percentiles reported**: 10th (downside) / 50th (median) /
  90th (upside) of the ending-value distribution. This is a reporting-shape
  choice, not a financial assumption — it does not change the computed
  success probability, only which extra percentiles are surfaced alongside
  it — so it was decided and documented here rather than put to a question.
- **Goal feasibility thresholds**: Feasible >= 0.80, At Risk 0.50-0.79, Not
  Feasible < 0.50 (on Monte Carlo success probability), approved 2026-09-14.
- **Emergency-fund target**: 6 months of essential expenses, approved
  2026-09-14. "Essential expenses" and "liquid assets" are supplied by the
  caller as plain numbers (`monthly_essential_expenses`,
  `current_liquid_assets`) — this module does not decide which DB/dataset
  fields feed them.
- **random_state**: 42 throughout (CLAUDE.md rule 9).

No MVO, HRP, 1/N, covariance optimization, asset selection, or portfolio
weights are computed anywhere in this module — that is Phase 8's exclusive
responsibility (CLAUDE.md rule 10 territory; PROJECT_PLAN.md section 2.6
scopes Goal Planning to TVM + Monte Carlo goal-success probability only).
"""

from __future__ import annotations

from datetime import date

import numpy as np
from pydantic import BaseModel, Field, field_validator

RANDOM_STATE = 42
MONTE_CARLO_SIMULATIONS = 10_000
MONTE_CARLO_PERCENTILES = (10, 50, 90)  # downside, median, upside

FEASIBLE_THRESHOLD = 0.80
AT_RISK_THRESHOLD = 0.50

EMERGENCY_FUND_TARGET_MONTHS = 6


# ---------------------------------------------------------------------------
# Goal representation
# ---------------------------------------------------------------------------


class GoalInput(BaseModel):
    """Mirrors the `financial_goals` table exactly — no invented fields."""

    customer_id: int = Field(gt=0)
    goal_type: str = Field(min_length=1, max_length=100)
    target_amount: float = Field(gt=0)
    current_savings: float = Field(ge=0, default=0.0)
    target_date: date
    priority: int = Field(default=1, ge=1)

    @field_validator("goal_type")
    @classmethod
    def _non_blank_goal_type(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("goal_type must not be blank")
        return v


def validate_goal_for_creation(goal: GoalInput, current_date: date | None = None) -> None:
    """Creation-time check: a NEW goal's target_date must be strictly after
    `current_date` (defaults to today). Deliberately separate from the
    analysis functions below, which must also accept an ALREADY-EXISTING
    goal whose target_date has arrived (`target_date == current_date`,
    zero periods remaining) — a legitimate state to analyze, just not one
    that can be newly created.
    """
    if current_date is None:
        current_date = date.today()
    if goal.target_date <= current_date:
        raise ValueError(
            f"target_date ({goal.target_date}) must be after current_date "
            f"({current_date}) to create a new goal"
        )


class GoalAssumptions(BaseModel):
    """Scenario-adjustable calculation inputs — never persisted on the goal
    itself (MASTER_PROMPT.md section 27 treats these as user-tunable, not
    fixed). `annual_return_rate` and `annual_inflation_rate` have NO
    default: every caller must state them explicitly.
    """

    contribution_amount: float = Field(ge=0)
    contribution_periods_per_year: int = Field(default=12, gt=0)
    annual_return_rate: float = Field(gt=-1.0)
    annual_inflation_rate: float = Field(gt=-1.0)


# ---------------------------------------------------------------------------
# Date / period helpers
# ---------------------------------------------------------------------------


def years_between(current_date: date, target_date: date) -> float:
    if target_date < current_date:
        raise ValueError(
            f"target_date ({target_date}) is before current_date ({current_date}); "
            "a past deadline cannot be forecast forward"
        )
    return (target_date - current_date).days / 365.25


def n_periods_between(current_date: date, target_date: date, periods_per_year: int) -> int:
    """Whole periods between two dates, rounded to the nearest period (not
    floored/ceiled) — documented per section 6's requirement to be explicit
    about period-counting convention."""
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be a positive integer")
    years = years_between(current_date, target_date)
    return round(years * periods_per_year)


def periodic_rate_from_annual(annual_rate: float, periods_per_year: int) -> float:
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be a positive integer")
    if annual_rate <= -1.0:
        raise ValueError("annual_rate must be > -1.0")
    return annual_rate / periods_per_year


# ---------------------------------------------------------------------------
# Time Value of Money
# ---------------------------------------------------------------------------


def future_value(
    present_value: float, periodic_rate: float, n_periods: int, periodic_contribution: float = 0.0
) -> float:
    """FV = PV(1+r)^n + PMT * [((1+r)^n - 1) / r], ordinary annuity
    (end-of-period contributions). r == 0 handled separately to avoid
    division by zero (limit of the annuity factor as r -> 0 is n)."""
    if n_periods < 0:
        raise ValueError("n_periods must be >= 0")
    if periodic_rate <= -1.0:
        raise ValueError("periodic_rate must be > -1.0")
    if n_periods == 0:
        return present_value
    if periodic_rate == 0.0:
        return present_value + periodic_contribution * n_periods
    growth = (1.0 + periodic_rate) ** n_periods
    return present_value * growth + periodic_contribution * ((growth - 1.0) / periodic_rate)


def present_value(future_value_amount: float, periodic_rate: float, n_periods: int) -> float:
    """PV = FV / (1+r)^n."""
    if n_periods < 0:
        raise ValueError("n_periods must be >= 0")
    if periodic_rate <= -1.0:
        raise ValueError("periodic_rate must be > -1.0")
    if n_periods == 0:
        return future_value_amount
    return future_value_amount / ((1.0 + periodic_rate) ** n_periods)


def required_periodic_contribution(
    present_value_amount: float, target_future_value: float, periodic_rate: float, n_periods: int
) -> float:
    """Solves the `future_value` formula for PMT. May return a negative
    value when the present value alone already overshoots the target —
    that is a real, informative result (current trajectory exceeds the
    goal without any further contribution), not an error.

    `n_periods == 0` is a genuine edge case (target date has arrived): if
    the goal is already funded (`present_value_amount >=
    target_future_value`) the required contribution is 0; otherwise there
    are no remaining periods left to close a positive gap, which is a
    real error, not a number to silently paper over.
    """
    if n_periods < 0:
        raise ValueError("n_periods must be >= 0")
    if periodic_rate <= -1.0:
        raise ValueError("periodic_rate must be > -1.0")
    if n_periods == 0:
        shortfall = target_future_value - present_value_amount
        if shortfall <= 0:
            return 0.0
        raise ValueError(
            "n_periods is 0 with a positive funding shortfall: the target date has "
            "arrived and no further contribution periods remain to close the gap"
        )
    growth = (1.0 + periodic_rate) ** n_periods
    grown_present_value = present_value_amount * growth
    remaining = target_future_value - grown_present_value
    annuity_factor = float(n_periods) if periodic_rate == 0.0 else (growth - 1.0) / periodic_rate
    return remaining / annuity_factor


def inflation_adjusted_target(nominal_target: float, annual_inflation_rate: float, years: float) -> float:
    """Nominal target grown forward at the inflation rate — the amount that
    will actually be needed at `target_date`, distinct from the
    `nominal_target` entered on the goal itself."""
    if annual_inflation_rate <= -1.0:
        raise ValueError("annual_inflation_rate must be > -1.0")
    if years < 0:
        raise ValueError("years must be >= 0")
    return nominal_target * (1.0 + annual_inflation_rate) ** years


# ---------------------------------------------------------------------------
# Goal funding analysis (TVM + required contribution, combined)
# ---------------------------------------------------------------------------


class GoalFundingAnalysis(BaseModel):
    nominal_target_amount: float
    inflation_adjusted_target_amount: float
    current_savings: float
    remaining_amount: float
    years_remaining: float
    periods_remaining: int
    contribution_periods_per_year: int
    assumed_annual_return: float
    assumed_annual_inflation: float
    required_periodic_contribution: float
    contribution_gap: float
    already_achieved: bool


def analyze_goal_funding(
    goal: GoalInput, assumptions: GoalAssumptions, current_date: date
) -> GoalFundingAnalysis:
    """Combines TVM + inflation adjustment + required contribution into one
    deterministic result. `contribution_gap` is `required_periodic_contribution
    - assumptions.contribution_amount` (PROJECT_PLAN.md section 2.6: "the
    shortfall against current trajectory is the funding gap") — positive
    means the current contribution plan falls short, zero or negative means
    on track or ahead.
    """
    years = years_between(current_date, goal.target_date)
    periods = n_periods_between(current_date, goal.target_date, assumptions.contribution_periods_per_year)
    periodic_rate = periodic_rate_from_annual(
        assumptions.annual_return_rate, assumptions.contribution_periods_per_year
    )
    adjusted_target = inflation_adjusted_target(goal.target_amount, assumptions.annual_inflation_rate, years)
    required_pmt = required_periodic_contribution(goal.current_savings, adjusted_target, periodic_rate, periods)

    return GoalFundingAnalysis(
        nominal_target_amount=goal.target_amount,
        inflation_adjusted_target_amount=adjusted_target,
        current_savings=goal.current_savings,
        remaining_amount=adjusted_target - goal.current_savings,
        years_remaining=years,
        periods_remaining=periods,
        contribution_periods_per_year=assumptions.contribution_periods_per_year,
        assumed_annual_return=assumptions.annual_return_rate,
        assumed_annual_inflation=assumptions.annual_inflation_rate,
        required_periodic_contribution=required_pmt,
        contribution_gap=required_pmt - assumptions.contribution_amount,
        already_achieved=goal.current_savings >= adjusted_target,
    )


# ---------------------------------------------------------------------------
# Monte Carlo goal simulation
# ---------------------------------------------------------------------------


class MonteCarloResult(BaseModel):
    n_simulations: int
    n_periods: int
    success_probability: float
    median_ending_value: float
    downside_percentile_value: float
    upside_percentile_value: float
    target_amount: float
    shortfall_at_median: float
    surplus_at_median: float


def run_goal_monte_carlo(
    current_savings: float,
    periodic_contribution: float,
    n_periods: int,
    target_amount: float,
    historical_returns: np.ndarray,
    n_simulations: int = MONTE_CARLO_SIMULATIONS,
    random_state: int = RANDOM_STATE,
) -> MonteCarloResult:
    """Bootstrap Monte Carlo: for each of `n_simulations` independent paths,
    draw `n_periods` periodic returns WITH REPLACEMENT from
    `historical_returns` and apply them to the running balance as an
    ordinary annuity (contribution added at period end, matching
    `future_value`'s timing convention): `balance = balance*(1+r) +
    contribution`. Success = ending balance >= `target_amount`.

    `target_amount` influences only the post-simulation success/shortfall/
    surplus comparison, never the simulated balance paths themselves — the
    balance distribution depends solely on
    (current_savings, periodic_contribution, n_periods, historical_returns,
    random_state). This is verified directly in
    tests/backend/core/test_goals.py (two runs with different
    target_amount, same seed and everything else, must produce identical
    `median_ending_value`/percentiles).

    Deterministic: a fresh `numpy.random.default_rng(random_state)` is
    created on every call, so identical arguments always reproduce
    identical results.
    """
    if n_periods < 0:
        raise ValueError("n_periods must be >= 0")
    if n_simulations <= 0:
        raise ValueError("n_simulations must be a positive integer")
    historical_returns = np.asarray(historical_returns, dtype=float)
    if historical_returns.size == 0:
        raise ValueError("historical_returns must be non-empty")

    if n_periods == 0:
        ending_values = np.full(n_simulations, float(current_savings))
    else:
        rng = np.random.default_rng(random_state)
        draw_idx = rng.integers(0, historical_returns.size, size=(n_simulations, n_periods))
        sampled_returns = historical_returns[draw_idx]
        ending_values = np.full(n_simulations, float(current_savings))
        for t in range(n_periods):
            ending_values = ending_values * (1.0 + sampled_returns[:, t]) + periodic_contribution

    success_probability = float(np.mean(ending_values >= target_amount))
    downside, median, upside = (float(np.percentile(ending_values, p)) for p in MONTE_CARLO_PERCENTILES)

    return MonteCarloResult(
        n_simulations=n_simulations,
        n_periods=n_periods,
        success_probability=success_probability,
        median_ending_value=median,
        downside_percentile_value=downside,
        upside_percentile_value=upside,
        target_amount=target_amount,
        shortfall_at_median=max(0.0, target_amount - median),
        surplus_at_median=max(0.0, median - target_amount),
    )


def classify_feasibility(success_probability: float) -> str:
    """Feasible >= 0.80, At Risk 0.50-0.79, Not Feasible < 0.50 (approved
    2026-09-14)."""
    if not 0.0 <= success_probability <= 1.0:
        raise ValueError("success_probability must be within [0, 1]")
    if success_probability >= FEASIBLE_THRESHOLD:
        return "Feasible"
    if success_probability >= AT_RISK_THRESHOLD:
        return "At Risk"
    return "Not Feasible"


# ---------------------------------------------------------------------------
# Emergency fund + savings-first
# ---------------------------------------------------------------------------


class EmergencyFundStatus(BaseModel):
    required_amount: float
    current_amount: float
    shortfall: float
    surplus: float
    sufficient: bool
    target_months: int


def assess_emergency_fund(
    monthly_essential_expenses: float,
    current_liquid_assets: float,
    target_months: int = EMERGENCY_FUND_TARGET_MONTHS,
) -> EmergencyFundStatus:
    if monthly_essential_expenses < 0:
        raise ValueError("monthly_essential_expenses must be >= 0")
    if current_liquid_assets < 0:
        raise ValueError("current_liquid_assets must be >= 0")
    if target_months <= 0:
        raise ValueError("target_months must be a positive integer")

    required = monthly_essential_expenses * target_months
    return EmergencyFundStatus(
        required_amount=required,
        current_amount=current_liquid_assets,
        shortfall=max(0.0, required - current_liquid_assets),
        surplus=max(0.0, current_liquid_assets - required),
        sufficient=current_liquid_assets >= required,
        target_months=target_months,
    )


def savings_first_required(status: EmergencyFundStatus) -> bool:
    """IF emergency fund insufficient THEN savings-first = TRUE
    (PROJECT_PLAN.md section 2.6 / MASTER_PROMPT.md section 14) — the exact
    rule specified, nothing more. Does not decide, compute, or return
    anything about portfolio optimization; that is Phase 8's exclusive
    responsibility."""
    return not status.sufficient
