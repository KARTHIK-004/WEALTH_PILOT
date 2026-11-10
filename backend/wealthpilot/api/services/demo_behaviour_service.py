"""Fictional demonstration data for the Financial Behaviour & Sentiment page (development / demo mode only).

Everything here is invented and fixed: six clearly fictional months for one individual, and a fictional family (three members and a household). NOTHING is read from or written to a database, a
customer record, any tamper-evident record store or a model, and the module has no logger. The figures shown beside the months are NOT written here: they come from the same functions the
customer route uses (`compute_behaviour_features`, `derive_findings`, `analyse_user_text` through `personalized_insight_service.build_insight_from_features`, and for the household the real
`core/household_finance` engine), so the demo shows the real calculation and the real rules-baseline reading (`user_text_rules_v1`) of fictional inputs. The routes that serve it are guarded by
`DEMO_MODE_ENABLED` (default false).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from wealthpilot.api.schemas import DemoFamilyFinancialBehaviourResponse, DemoFinancialBehaviourResponse, DemoMemberOut, DemoMonthOut
from wealthpilot.api.services import household_summary_service, personalized_insight_service
from wealthpilot.api.services.monthly_records_service import _change, _value
from wealthpilot.core import household_finance as engine
from wealthpilot.core.behaviour_features import DEFAULT_CURRENCY, MonthlyObservation, compute_behaviour_features

DEMO_CUSTOMER_ID = 0                    # no customer has this id: the demo is not anyone's record
DEMO_HOUSEHOLD_ID = 0                   # nor is there a household with this id
DATA_SOURCE = "demo_fixture"
NOTICE = ("Demonstration data. Every month, amount and sentence here is fictional and fixed. It is not read from, and never written to, any customer record or database, "
          "and it does not affect any risk profile, allocation or recommendation.")
FAMILY_NOTICE = ("Demo data — fictional family example. Every name, month, amount and sentence here is invented and fixed. It is not read from, and never written to, any customer record or "
                 "database, and it does not affect any risk profile, allocation or recommendation.")
EXAMPLE_TEXT = "I feel more confident about saving this month, but I am still watching my expenses."
HOUSEHOLD_LABEL = "The Demo family (fictional)"
# (period, income, expenses, savings): fictional rupee amounts, oldest first.
FIXTURE_MONTHS: tuple[tuple[str, int, int, int], ...] = (
    ("2026-03", 62000, 41500, 8000),
    ("2026-04", 62000, 43200, 6500),
    ("2026-05", 63500, 42800, 9000),
    ("2026-06", 63500, 45100, 5500),
    ("2026-07", 65000, 43900, 8500),
    ("2026-08", 65000, 42600, 10500),
)
# The fictional family: (label, role, [(period, income, expenses, savings, investment_contribution)]). A None is "not reported", never zero.
FAMILY_MEMBERS: tuple[tuple[str, str, tuple[tuple[str, int | None, int | None, int | None, int | None], ...]], ...] = (
    ("Primary member (demo)", "Primary household member", (
        ("2026-03", 58000, 36000, 7000, 5000), ("2026-04", 58000, 37200, 6500, 5000), ("2026-05", 59000, 36800, 8000, 6000),
        ("2026-06", 59000, 38500, 7000, 6000), ("2026-07", 60000, 37900, 8500, 7000), ("2026-08", 60000, 36500, 9500, 7500))),
    ("Partner (demo)", "Partner", (
        ("2026-03", 42000, 25000, 4000, None), ("2026-04", 42000, 25800, 3500, None), ("2026-05", 43000, 25500, 4200, None),
        ("2026-06", 43000, 26400, 3800, None), ("2026-07", 44000, 25900, 4500, 2000), ("2026-08", 44000, 26100, 4800, 2500))),
    ("Dependent (demo)", "Dependent", (
        ("2026-06", None, 6000, None, None), ("2026-07", None, 6400, None, None), ("2026-08", None, 6200, None, None))),
)


def _amount(value: int | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def _observation(period: str, income: int | None, expenses: int | None, savings: int | None, investment: int | None = None) -> MonthlyObservation:
    return MonthlyObservation(period=date(int(period[:4]), int(period[5:7]), 1), income=_amount(income), expenses=_amount(expenses), savings=_amount(savings),
                              investment_contribution=_amount(investment), income_basis=None if income is None else "net")


def _float(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _months(observations: list[MonthlyObservation]) -> list[DemoMonthOut]:
    """One row per month. Each ratio and change is the existing feature code run over the months up to and including that month, so a first month has no change (with the reason)."""
    rows = []
    for index, observation in enumerate(observations):
        so_far = compute_behaviour_features(observations[: index + 1])
        rows.append(DemoMonthOut(
            period=f"{observation.period:%Y-%m}", income=_float(observation.income), expenses=_float(observation.expenses), savings=_float(observation.savings),
            investment_contribution=_float(observation.investment_contribution), income_basis=observation.income_basis,  # type: ignore[arg-type]
            expense_to_income=_value(so_far.latest_ratios.expense_to_income), savings_to_income=_value(so_far.latest_ratios.savings_to_income),
            income_change=_change(so_far.income_change), expenses_change=_change(so_far.expenses_change), savings_change=_change(so_far.savings_change),
            investment_contribution_change=_change(so_far.investment_contribution_change)))
    return rows


def build_demo(text: str | None) -> DemoFinancialBehaviourResponse:
    """The fictional months with their calculated ratios and changes, the insight for them (with the optional text read by the rules baseline) and the model status."""
    observations = [_observation(p, i, e, s) for p, i, e, s in FIXTURE_MONTHS]
    features = compute_behaviour_features(observations)
    insight = personalized_insight_service.build_insight_from_features(DEMO_CUSTOMER_ID, features, text, lambda: None)
    return DemoFinancialBehaviourResponse(notice=NOTICE, example_text=EXAMPLE_TEXT, currency=DEFAULT_CURRENCY, months=_months(observations), insight=insight,
                                          sentiment_model=personalized_insight_service.sentiment_model_status(), data_source=DATA_SOURCE)


def _household_summary():
    """The real household engine over INVENTED household records: two incomes, four expenses (one yearly, one one-time), three assets and two loans (one with no stated payment)."""
    d = Decimal
    incomes = [engine.IncomeRecord(amount=d(60000), frequency="monthly", is_active=True), engine.IncomeRecord(amount=d(44000), frequency="monthly", is_active=True)]
    expenses = [engine.ExpenseRecord(amount=d(18000), frequency="monthly", is_essential=True, is_active=True), engine.ExpenseRecord(amount=d(6000), frequency="monthly", is_essential=True, is_active=True),
                engine.ExpenseRecord(amount=d(120000), frequency="yearly", is_essential=True, is_active=True), engine.ExpenseRecord(amount=d(60000), frequency="one_time", is_essential=False, is_active=True)]
    assets = [engine.AssetRecord(current_value=d(150000), is_liquid=True), engine.AssetRecord(current_value=d(300000), is_liquid=True), engine.AssetRecord(current_value=d(3500000), is_liquid=False)]
    liabilities = [engine.LiabilityRecord(outstanding_amount=d(1800000), monthly_payment=d(21000)), engine.LiabilityRecord(outstanding_amount=d(220000), monthly_payment=None)]
    return household_summary_service.build_summary_response(DEMO_HOUSEHOLD_ID, engine.summarize_household_finances(incomes, expenses, assets, liabilities))


def build_family_demo(text: str | None) -> DemoFamilyFinancialBehaviourResponse:
    """A fictional family: each member's months with calculated ratios and changes and a records-only insight (the optional text is the PRIMARY member's note and is read by the rules baseline),
    plus the household engine's totals over invented household records."""
    members = []
    for index, (label, role, rows) in enumerate(FAMILY_MEMBERS):
        observations = [_observation(*row) for row in rows]
        insight = personalized_insight_service.build_insight_from_features(DEMO_CUSTOMER_ID, compute_behaviour_features(observations), text if index == 0 else None, lambda: None)
        members.append(DemoMemberOut(label=label, role=role, months=_months(observations), insight=insight))
    return DemoFamilyFinancialBehaviourResponse(notice=FAMILY_NOTICE, household_label=HOUSEHOLD_LABEL, example_text=EXAMPLE_TEXT, currency=DEFAULT_CURRENCY, members=members,
                                                household_summary=_household_summary(), sentiment_model=personalized_insight_service.sentiment_model_status(), data_source=DATA_SOURCE)
