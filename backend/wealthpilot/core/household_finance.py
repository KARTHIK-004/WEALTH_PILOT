"""Phase 34 — deterministic household financial aggregation.

Pure, DB-free calculation module, in the same shape as `core/goals.py`: it
takes plain records in and returns plain numbers out. It performs no I/O, no
ML, no LLM call, no market lookup and no date-dependent arithmetic, so the same
records always produce the same summary (`docs/RULES.md` Rule 33).

**Scope.** This module aggregates the Phase 33 household source records
(income, expenses, assets, liabilities) into a factual summary and assesses the
household's emergency fund. It deliberately computes NOTHING else: no savings
rate, no debt-to-income ratio, no score, no ranking, no goal feasibility, no
Monte Carlo, no portfolio weight and no recommendation
(`docs/DECISIONS.md` ADR-033). Nothing here is wired into the individual
analysis pipeline.

Documented semantics — every one of these is a stated rule of this phase, not
an invented convenience:

- **Monthly normalization.** `monthly` contributes its amount unchanged;
  `yearly` contributes `amount / 12`. `one_time` is NEVER converted into a
  recurring monthly figure — no amortization period is invented and a one-time
  record is never assumed to repeat. One-time records are summed separately so
  they stay identifiable.
- **Active records only.** Income and expenses carry `is_active`; only active
  records take part in any aggregate. An inactive record stays stored and
  counted in `record_count`, but is excluded from every monetary figure. Assets
  and liabilities have no `is_active` column in the Phase 33 schema and none is
  invented here.
- **NULL is not zero** (CLAUDE.md section 12). A monetary aggregate is `None`
  unless at least one record actually contributes to it, and `None` means "not
  known", never "zero". A household with no income records has *unknown*
  recurring income, not income of 0; a household whose only liquid asset is
  recorded with `current_value = 0` has liquid assets of exactly 0, which is a
  known fact. The same rule applies within a resource: if a household records
  only one-time income, its *recurring* income is unknown rather than zero,
  because nothing in this system asks a household to confirm that what it
  entered is complete.
- **Emergency fund.** `required = 6 x recurring monthly essential expenses`,
  reusing `core.goals.EMERGENCY_FUND_TARGET_MONTHS` — the same 6-month constant
  and the same `current >= required` comparison the individual engine uses
  (`core.goals.assess_emergency_fund`), so the two can never disagree. The
  individual implementation is untouched; this is the household-level
  application of the same semantics, with Decimal money instead of float.
  `status` is `sufficient` / `insufficient` / `unknown` and nothing else.
- **Decimal throughout.** Money arrives as `Decimal` (the `Numeric(14, 2)`
  columns), is aggregated as `Decimal`, and is never rounded here. Conversion
  to the API's float convention happens once, at the service boundary, exactly
  as Phase 33 already does (`docs/DECISIONS.md` ADR-033).
- **Single currency.** No currency field, no conversion — the project's single
  documented currency assumption is preserved unchanged.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from wealthpilot.core.goals import EMERGENCY_FUND_TARGET_MONTHS

MONTHS_PER_YEAR = Decimal(12)

FREQUENCY_MONTHLY = "monthly"
FREQUENCY_YEARLY = "yearly"
FREQUENCY_ONE_TIME = "one_time"

#: The frequency vocabulary this module understands. It mirrors
#: `db.models.HOUSEHOLD_FINANCE_FREQUENCIES` exactly; `core/` stays free of any
#: database import, so a test asserts the two never drift instead.
FINANCE_FREQUENCIES: tuple[str, ...] = (FREQUENCY_MONTHLY, FREQUENCY_YEARLY, FREQUENCY_ONE_TIME)

EmergencyFundState = Literal["sufficient", "insufficient", "unknown"]


# ---------------------------------------------------------------------------
# Inputs — plain mirrors of the Phase 33 stored records (no ORM, no session)
# ---------------------------------------------------------------------------


class IncomeRecord(BaseModel):
    """Mirrors `household_incomes`: the fields aggregation needs, nothing more."""

    amount: Decimal = Field(gt=0)
    frequency: str
    is_active: bool


class ExpenseRecord(BaseModel):
    """Mirrors `household_expenses`. `is_essential` is the household's own
    stored judgement — it is never inferred from the category here."""

    amount: Decimal = Field(gt=0)
    frequency: str
    is_essential: bool
    is_active: bool


class AssetRecord(BaseModel):
    """Mirrors `household_assets`. Liquidity is the explicit stored `is_liquid`
    flag, never inferred from `asset_type`. `current_value` is used exactly as
    stored — no market price, appreciation or revaluation is applied."""

    current_value: Decimal = Field(ge=0)
    is_liquid: bool


class LiabilityRecord(BaseModel):
    """Mirrors `household_liabilities`. `monthly_payment` is genuinely optional:
    `None` means "not provided", which is not a payment of 0."""

    outstanding_amount: Decimal = Field(ge=0)
    monthly_payment: Decimal | None = Field(default=None, ge=0)


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


class IncomeSummary(BaseModel):
    recurring_monthly: Decimal | None
    one_time: Decimal | None
    record_count: int
    active_record_count: int
    available: bool


class ExpenseSummary(BaseModel):
    recurring_monthly: Decimal | None
    recurring_essential_monthly: Decimal | None
    recurring_nonessential_monthly: Decimal | None
    one_time: Decimal | None
    record_count: int
    active_record_count: int
    available: bool


class AssetSummary(BaseModel):
    total: Decimal | None
    liquid: Decimal | None
    record_count: int
    liquid_record_count: int
    available: bool


class LiabilitySummary(BaseModel):
    outstanding: Decimal | None
    monthly_payment: Decimal | None
    record_count: int
    available: bool


class CashFlowSummary(BaseModel):
    """Recurring monthly income less recurring monthly expenses. One-time
    records are excluded by construction. This is deliberately NOT called
    savings, and no savings rate is derived from it."""

    recurring_monthly_income: Decimal | None
    recurring_monthly_expenses: Decimal | None
    monthly: Decimal | None
    available: bool


class NetPositionSummary(BaseModel):
    """Assets less outstanding liabilities. Income and expenses are not part of
    it, and a missing side makes the whole figure unknown rather than zero."""

    total_assets: Decimal | None
    total_outstanding_liabilities: Decimal | None
    value: Decimal | None
    available: bool


class EmergencyFundSummary(BaseModel):
    required: Decimal | None
    current_liquid_assets: Decimal | None
    shortfall: Decimal | None
    status: EmergencyFundState
    target_months: int
    available: bool


class HouseholdFinancialSummary(BaseModel):
    income: IncomeSummary
    expenses: ExpenseSummary
    assets: AssetSummary
    liabilities: LiabilitySummary
    cash_flow: CashFlowSummary
    net_position: NetPositionSummary
    emergency_fund: EmergencyFundSummary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _total(values: Iterable[Decimal]) -> Decimal | None:
    """Sum, or `None` when nothing contributed.

    This one helper carries the NULL-is-not-zero rule for every aggregate in
    this module: an empty set of contributing records is *unknown*, never 0.
    A record that really does hold 0 contributes 0 and makes the total known.
    """
    total: Decimal | None = None
    for value in values:
        total = value if total is None else total + value
    return total


def monthly_equivalent(amount: Decimal, frequency: str) -> Decimal | None:
    """The recurring monthly value of one record, or `None` when the record is
    not recurring. `one_time` deliberately has no monthly equivalent."""
    if frequency == FREQUENCY_MONTHLY:
        return amount
    if frequency == FREQUENCY_YEARLY:
        return amount / MONTHS_PER_YEAR
    if frequency == FREQUENCY_ONE_TIME:
        return None
    raise ValueError(f"unknown frequency {frequency!r}; expected one of {FINANCE_FREQUENCIES}")


def _recurring_monthly(records: Iterable[IncomeRecord | ExpenseRecord]) -> Decimal | None:
    return _total(
        monthly
        for record in records
        if (monthly := monthly_equivalent(record.amount, record.frequency)) is not None
    )


def _one_time(records: Iterable[IncomeRecord | ExpenseRecord]) -> Decimal | None:
    return _total(record.amount for record in records if record.frequency == FREQUENCY_ONE_TIME)


# ---------------------------------------------------------------------------
# Per-resource aggregation
# ---------------------------------------------------------------------------


def summarize_income(records: list[IncomeRecord]) -> IncomeSummary:
    active = [record for record in records if record.is_active]
    return IncomeSummary(
        recurring_monthly=_recurring_monthly(active),
        one_time=_one_time(active),
        record_count=len(records),
        active_record_count=len(active),
        available=bool(records),
    )


def summarize_expenses(records: list[ExpenseRecord]) -> ExpenseSummary:
    active = [record for record in records if record.is_active]
    return ExpenseSummary(
        recurring_monthly=_recurring_monthly(active),
        recurring_essential_monthly=_recurring_monthly(r for r in active if r.is_essential),
        recurring_nonessential_monthly=_recurring_monthly(r for r in active if not r.is_essential),
        one_time=_one_time(active),
        record_count=len(records),
        active_record_count=len(active),
        available=bool(records),
    )


def summarize_assets(records: list[AssetRecord]) -> AssetSummary:
    liquid = [record for record in records if record.is_liquid]
    return AssetSummary(
        total=_total(record.current_value for record in records),
        liquid=_total(record.current_value for record in liquid),
        record_count=len(records),
        liquid_record_count=len(liquid),
        available=bool(records),
    )


def summarize_liabilities(records: list[LiabilityRecord]) -> LiabilitySummary:
    return LiabilitySummary(
        outstanding=_total(record.outstanding_amount for record in records),
        # A liability with no recorded monthly payment contributes nothing --
        # "not provided" must not be aggregated as a payment of 0.
        monthly_payment=_total(
            record.monthly_payment for record in records if record.monthly_payment is not None
        ),
        record_count=len(records),
        available=bool(records),
    )


# ---------------------------------------------------------------------------
# Derived views
# ---------------------------------------------------------------------------


def derive_cash_flow(income: IncomeSummary, expenses: ExpenseSummary) -> CashFlowSummary:
    known = income.recurring_monthly is not None and expenses.recurring_monthly is not None
    return CashFlowSummary(
        recurring_monthly_income=income.recurring_monthly,
        recurring_monthly_expenses=expenses.recurring_monthly,
        monthly=(income.recurring_monthly - expenses.recurring_monthly) if known else None,
        available=known,
    )


def derive_net_position(assets: AssetSummary, liabilities: LiabilitySummary) -> NetPositionSummary:
    known = assets.total is not None and liabilities.outstanding is not None
    return NetPositionSummary(
        total_assets=assets.total,
        total_outstanding_liabilities=liabilities.outstanding,
        value=(assets.total - liabilities.outstanding) if known else None,
        available=known,
    )


def assess_household_emergency_fund(
    expenses: ExpenseSummary,
    assets: AssetSummary,
    target_months: int = EMERGENCY_FUND_TARGET_MONTHS,
) -> EmergencyFundSummary:
    """The household application of `core.goals.assess_emergency_fund`'s
    semantics: the same 6-month target and the same `current >= required`
    comparison, in Decimal, with an explicit `unknown` state for the cases the
    individual engine never has to represent (its caller supplies both numbers
    or skips the assessment entirely).

    A missing essential-expense figure or a missing liquid-asset figure makes
    the status `unknown` — never a shortfall computed against an assumed 0.
    """
    if target_months <= 0:
        raise ValueError("target_months must be a positive integer")

    essential = expenses.recurring_essential_monthly
    liquid = assets.liquid
    if essential is None or liquid is None:
        return EmergencyFundSummary(
            required=None if essential is None else essential * target_months,
            current_liquid_assets=liquid,
            shortfall=None,
            status="unknown",
            target_months=target_months,
            available=False,
        )

    required = essential * target_months
    shortfall = max(Decimal(0), required - liquid)
    return EmergencyFundSummary(
        required=required,
        current_liquid_assets=liquid,
        shortfall=shortfall,
        status="sufficient" if liquid >= required else "insufficient",
        target_months=target_months,
        available=True,
    )


def summarize_household_finances(
    incomes: list[IncomeRecord],
    expenses: list[ExpenseRecord],
    assets: list[AssetRecord],
    liabilities: list[LiabilityRecord],
) -> HouseholdFinancialSummary:
    """The whole deterministic summary, from the household's own source records
    and nothing else. No customer, questionnaire, risk, market, portfolio or
    model input takes part."""
    income_summary = summarize_income(incomes)
    expense_summary = summarize_expenses(expenses)
    asset_summary = summarize_assets(assets)
    liability_summary = summarize_liabilities(liabilities)

    return HouseholdFinancialSummary(
        income=income_summary,
        expenses=expense_summary,
        assets=asset_summary,
        liabilities=liability_summary,
        cash_flow=derive_cash_flow(income_summary, expense_summary),
        net_position=derive_net_position(asset_summary, liability_summary),
        emergency_fund=assess_household_emergency_fund(expense_summary, asset_summary),
    )
