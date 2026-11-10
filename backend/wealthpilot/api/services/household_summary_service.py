"""Phase 34 — the household financial summary (read-only orchestration).

Loads a household's Phase 33 source records, hands them to the deterministic
engine in `core/household_finance.py`, and maps the result onto the public API
schema. It contains **no financial logic of its own**: every number in the
response is computed exactly once, in `core/`, and carried through unchanged
(`docs/DECISIONS.md` ADR-033, CLAUDE.md section 7).

Query approach (Phase 34 section 37): four `SELECT`s, one per resource, each
scoped by `household_id`, then deterministic Decimal aggregation in Python.
There is no N+1 — the record count does not change the query count — and no
SQL aggregate expression, because keeping the arithmetic in one tested `core/`
module matters more here than pushing four sums into the database.

Authorization is Phase 32/33's, reused unchanged: the caller is the asserted
`X-Customer-Id` customer and must be a member of the household. Reading a
summary needs no primary role — it is read-only — but a non-member gets 403, an
unknown household 404 and a missing identity 401, and a household can never see
another household's figures because every query is scoped by the path's
`household_id`.

Nothing here writes to the database, and nothing here reaches the individual
analysis pipeline: no risk model, portfolio optimizer, compliance rule,
recommendation, LangGraph node, AutoGen debate or Gemini prompt reads any of it.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from wealthpilot.api.schemas import (
    HouseholdAssetSection,
    HouseholdCashFlowSection,
    HouseholdDataCompletenessSection,
    HouseholdEmergencyFundSection,
    HouseholdExpenseSection,
    HouseholdFinancialSummaryResponse,
    HouseholdIncomeSection,
    HouseholdLiabilitySection,
    HouseholdNetPositionSection,
)
from wealthpilot.api.services.household_service import require_member
from wealthpilot.core import household_finance as engine
from wealthpilot.db.models import HouseholdAsset, HouseholdExpense, HouseholdIncome, HouseholdLiability


def _money(value: Decimal | None) -> float | None:
    """The engine works in `Decimal`; the public contract is a float, exactly as
    Phase 33's record endpoints already serialize money. This is the ONLY place
    a household summary figure changes representation, and `None` stays `None`
    — never 0 (CLAUDE.md section 12)."""
    return None if value is None else float(value)


def _reason(missing: list[str], template: str) -> str | None:
    """A plain sentence naming what is not known, or `None` when everything the
    section needs is known."""
    if not missing:
        return None
    joined = missing[0] if len(missing) == 1 else " and ".join((", ".join(missing[:-1]), missing[-1]))
    return template.format(missing=joined)


# ---------------------------------------------------------------------------
# Loading — one scoped query per resource
# ---------------------------------------------------------------------------


def _rows(session: Session, model: type, household_id: int) -> list:
    return list(
        session.scalars(select(model).where(model.household_id == household_id).order_by(model.id)).all()
    )


def _load_records(session: Session, household_id: int) -> tuple[list, list, list, list]:
    incomes = [
        engine.IncomeRecord(amount=row.amount, frequency=row.frequency, is_active=row.is_active)
        for row in _rows(session, HouseholdIncome, household_id)
    ]
    expenses = [
        engine.ExpenseRecord(
            amount=row.amount, frequency=row.frequency, is_essential=row.is_essential, is_active=row.is_active
        )
        for row in _rows(session, HouseholdExpense, household_id)
    ]
    assets = [
        engine.AssetRecord(current_value=row.current_value, is_liquid=row.is_liquid)
        for row in _rows(session, HouseholdAsset, household_id)
    ]
    liabilities = [
        engine.LiabilityRecord(outstanding_amount=row.outstanding_amount, monthly_payment=row.monthly_payment)
        for row in _rows(session, HouseholdLiability, household_id)
    ]
    return incomes, expenses, assets, liabilities


# ---------------------------------------------------------------------------
# Mapping — engine result to the public schema, no arithmetic
# ---------------------------------------------------------------------------


def _income_section(summary: engine.IncomeSummary) -> HouseholdIncomeSection:
    return HouseholdIncomeSection(
        recurring_monthly=_money(summary.recurring_monthly),
        one_time=_money(summary.one_time),
        record_count=summary.record_count,
        active_record_count=summary.active_record_count,
        available=summary.available,
        unavailable_reason=None if summary.available else "No income has been recorded for this household.",
    )


def _expense_section(summary: engine.ExpenseSummary) -> HouseholdExpenseSection:
    return HouseholdExpenseSection(
        recurring_monthly=_money(summary.recurring_monthly),
        recurring_essential_monthly=_money(summary.recurring_essential_monthly),
        recurring_nonessential_monthly=_money(summary.recurring_nonessential_monthly),
        one_time=_money(summary.one_time),
        record_count=summary.record_count,
        active_record_count=summary.active_record_count,
        available=summary.available,
        unavailable_reason=None if summary.available else "No expenses have been recorded for this household.",
    )


def _asset_section(summary: engine.AssetSummary) -> HouseholdAssetSection:
    return HouseholdAssetSection(
        total=_money(summary.total),
        liquid=_money(summary.liquid),
        record_count=summary.record_count,
        liquid_record_count=summary.liquid_record_count,
        available=summary.available,
        unavailable_reason=None if summary.available else "No assets have been recorded for this household.",
    )


def _liability_section(summary: engine.LiabilitySummary) -> HouseholdLiabilitySection:
    return HouseholdLiabilitySection(
        outstanding=_money(summary.outstanding),
        monthly_payment=_money(summary.monthly_payment),
        record_count=summary.record_count,
        available=summary.available,
        unavailable_reason=None if summary.available else "No liabilities have been recorded for this household.",
    )


def _cash_flow_section(summary: engine.CashFlowSummary) -> HouseholdCashFlowSection:
    missing = []
    if summary.recurring_monthly_income is None:
        missing.append("recurring monthly income")
    if summary.recurring_monthly_expenses is None:
        missing.append("recurring monthly expenses")
    return HouseholdCashFlowSection(
        recurring_monthly_income=_money(summary.recurring_monthly_income),
        recurring_monthly_expenses=_money(summary.recurring_monthly_expenses),
        monthly=_money(summary.monthly),
        available=summary.available,
        unavailable_reason=_reason(missing, "Monthly cash flow is not shown because {missing} is not known."),
    )


def _net_position_section(summary: engine.NetPositionSummary) -> HouseholdNetPositionSection:
    missing = []
    if summary.total_assets is None:
        missing.append("total assets")
    if summary.total_outstanding_liabilities is None:
        missing.append("outstanding liabilities")
    return HouseholdNetPositionSection(
        total_assets=_money(summary.total_assets),
        total_outstanding_liabilities=_money(summary.total_outstanding_liabilities),
        value=_money(summary.value),
        available=summary.available,
        unavailable_reason=_reason(missing, "Net position is not shown because {missing} is not known."),
    )


def _emergency_fund_section(summary: engine.EmergencyFundSummary) -> HouseholdEmergencyFundSection:
    missing = []
    if summary.required is None:
        missing.append("recurring monthly essential expenses")
    if summary.current_liquid_assets is None:
        missing.append("liquid assets")
    return HouseholdEmergencyFundSection(
        required=_money(summary.required),
        current_liquid_assets=_money(summary.current_liquid_assets),
        shortfall=_money(summary.shortfall),
        status=summary.status,
        target_months=summary.target_months,
        available=summary.available,
        unavailable_reason=_reason(
            missing, "The emergency-fund position is not known because {missing} is not recorded."
        ),
    )


def _completeness(summary: engine.HouseholdFinancialSummary) -> HouseholdDataCompletenessSection:
    state = {True: "available", False: "unavailable"}
    return HouseholdDataCompletenessSection(
        income=state[summary.income.available],
        expenses=state[summary.expenses.available],
        assets=state[summary.assets.available],
        liabilities=state[summary.liabilities.available],
        emergency_fund=state[summary.emergency_fund.available],
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def get_financial_summary(
    session: Session, household_id: int, acting_customer_id: int
) -> HouseholdFinancialSummaryResponse:
    """The household's deterministic financial summary. Read-only: it performs
    no write, and the same stored records always produce the same response."""
    require_member(session, household_id, acting_customer_id)

    summary = engine.summarize_household_finances(*_load_records(session, household_id))
    return build_summary_response(household_id, summary)


def build_summary_response(household_id: int, summary: engine.HouseholdFinancialSummary) -> HouseholdFinancialSummaryResponse:
    """The public response for an already computed engine summary: pure mapping, no arithmetic, no session. Shared by the stored-records route above and the fictional family demo, so the
    demo's household totals are the real engine's output over invented records."""
    return HouseholdFinancialSummaryResponse(
        household_id=household_id,
        income=_income_section(summary.income),
        expenses=_expense_section(summary.expenses),
        assets=_asset_section(summary.assets),
        liabilities=_liability_section(summary.liabilities),
        cash_flow=_cash_flow_section(summary.cash_flow),
        net_position=_net_position_section(summary.net_position),
        emergency_fund=_emergency_fund_section(summary.emergency_fund),
        data_completeness=_completeness(summary),
    )
