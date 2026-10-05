"""Phase 34 — the deterministic household aggregation engine
(`core/household_finance.py`).

These are pure unit tests: no database, no FastAPI, no network. Money is
`Decimal` throughout and compared exactly — never with `pytest.approx` — because
the whole point of aggregating in `Decimal` is that the result is exact
(Phase 34 section 33).
"""

from decimal import Decimal

import pytest

from wealthpilot.core.goals import EMERGENCY_FUND_TARGET_MONTHS, assess_emergency_fund
from wealthpilot.core.household_finance import (
    FINANCE_FREQUENCIES,
    AssetRecord,
    ExpenseRecord,
    IncomeRecord,
    LiabilityRecord,
    assess_household_emergency_fund,
    derive_cash_flow,
    derive_net_position,
    monthly_equivalent,
    summarize_assets,
    summarize_expenses,
    summarize_household_finances,
    summarize_income,
    summarize_liabilities,
)
from wealthpilot.db.models import HOUSEHOLD_FINANCE_FREQUENCIES


def D(value: str) -> Decimal:
    return Decimal(value)


def income(amount="1000.00", frequency="monthly", is_active=True) -> IncomeRecord:
    return IncomeRecord(amount=D(amount), frequency=frequency, is_active=is_active)


def expense(amount="500.00", frequency="monthly", is_essential=True, is_active=True) -> ExpenseRecord:
    return ExpenseRecord(amount=D(amount), frequency=frequency, is_essential=is_essential, is_active=is_active)


def asset(current_value="1000.00", is_liquid=True) -> AssetRecord:
    return AssetRecord(current_value=D(current_value), is_liquid=is_liquid)


def liability(outstanding_amount="1000.00", monthly_payment="100.00") -> LiabilityRecord:
    return LiabilityRecord(
        outstanding_amount=D(outstanding_amount),
        monthly_payment=None if monthly_payment is None else D(monthly_payment),
    )


# ---------------------------------------------------------------- vocabulary


def test_engine_frequency_vocabulary_matches_the_database_vocabulary():
    """`core/` holds no database import, so this is what stops the two drifting."""
    assert FINANCE_FREQUENCIES == HOUSEHOLD_FINANCE_FREQUENCIES


def test_monthly_equivalent_normalizes_only_recurring_frequencies():
    assert monthly_equivalent(D("1200.00"), "monthly") == D("1200.00")
    assert monthly_equivalent(D("1200.00"), "yearly") == D("100")
    assert monthly_equivalent(D("1200.00"), "one_time") is None


def test_monthly_equivalent_rejects_an_unknown_frequency():
    with pytest.raises(ValueError, match="unknown frequency"):
        monthly_equivalent(D("10.00"), "weekly")


def test_yearly_normalization_is_not_rounded_prematurely():
    """100 / 12 keeps full Decimal precision — no early rounding to 2dp."""
    monthly = monthly_equivalent(D("100.00"), "yearly")
    assert monthly == D("100.00") / Decimal(12)
    assert monthly * Decimal(12) == D("100.00")


# -------------------------------------------------------------------- income


def test_monthly_income_is_taken_as_is():
    assert summarize_income([income("5200.00")]).recurring_monthly == D("5200.00")


def test_yearly_income_is_divided_by_twelve():
    assert summarize_income([income("12000.00", "yearly")]).recurring_monthly == D("1000")


def test_one_time_income_is_separate_and_never_recurring():
    summary = summarize_income([income("900.00", "one_time")])
    assert summary.one_time == D("900.00")
    assert summary.recurring_monthly is None


def test_one_time_income_does_not_increase_recurring_monthly_income():
    """Phase 34 section 34, stated directly."""
    without = summarize_income([income("5200.00")])
    with_one_time = summarize_income([income("5200.00"), income("900.00", "one_time")])
    assert with_one_time.recurring_monthly == without.recurring_monthly == D("5200.00")
    assert with_one_time.one_time == D("900.00")


def test_inactive_income_is_stored_and_counted_but_never_aggregated():
    summary = summarize_income([income("5200.00"), income("400.00", is_active=False)])
    assert summary.recurring_monthly == D("5200.00")
    assert summary.record_count == 2
    assert summary.active_record_count == 1


def test_an_income_that_is_only_inactive_leaves_recurring_income_unknown():
    summary = summarize_income([income("400.00", is_active=False)])
    assert summary.recurring_monthly is None
    assert summary.available is True  # something was recorded, just nothing active


def test_multiple_income_records_of_mixed_frequency_combine():
    summary = summarize_income([income("5200.00"), income("12000.00", "yearly"), income("900.00", "one_time")])
    assert summary.recurring_monthly == D("6200.00")
    assert summary.one_time == D("900.00")
    assert summary.record_count == 3 and summary.active_record_count == 3


def test_no_income_records_is_unknown_not_zero():
    summary = summarize_income([])
    assert summary.available is False
    assert summary.recurring_monthly is None
    assert summary.one_time is None
    assert summary.record_count == 0 and summary.active_record_count == 0


# ------------------------------------------------------------------ expenses


def test_monthly_and_yearly_expenses_normalize_the_same_way_as_income():
    summary = summarize_expenses([expense("1400.00"), expense("600.00", "yearly")])
    assert summary.recurring_monthly == D("1450.00")


def test_essential_and_nonessential_expenses_are_split_by_the_stored_flag():
    summary = summarize_expenses(
        [expense("1400.00", is_essential=True), expense("600.00", is_essential=False)]
    )
    assert summary.recurring_essential_monthly == D("1400.00")
    assert summary.recurring_nonessential_monthly == D("600.00")
    assert summary.recurring_monthly == D("2000.00")


def test_one_time_expense_is_separate_and_never_recurring():
    summary = summarize_expenses([expense("300.00", "one_time")])
    assert summary.one_time == D("300.00")
    assert summary.recurring_monthly is None
    assert summary.recurring_essential_monthly is None


def test_one_time_expense_does_not_increase_recurring_monthly_expenses():
    """Phase 34 section 34, stated directly."""
    without = summarize_expenses([expense("1400.00")])
    with_one_time = summarize_expenses([expense("1400.00"), expense("300.00", "one_time")])
    assert with_one_time.recurring_monthly == without.recurring_monthly == D("1400.00")
    assert with_one_time.one_time == D("300.00")


def test_inactive_expense_is_excluded_from_every_expense_aggregate():
    summary = summarize_expenses([expense("1400.00"), expense("900.00", is_active=False)])
    assert summary.recurring_monthly == D("1400.00")
    assert summary.recurring_essential_monthly == D("1400.00")
    assert summary.record_count == 2 and summary.active_record_count == 1


def test_only_nonessential_expenses_leave_essential_expenses_unknown():
    summary = summarize_expenses([expense("600.00", is_essential=False)])
    assert summary.recurring_nonessential_monthly == D("600.00")
    assert summary.recurring_essential_monthly is None


def test_no_expense_records_is_unknown_not_zero():
    summary = summarize_expenses([])
    assert summary.available is False
    assert summary.recurring_monthly is None
    assert summary.recurring_essential_monthly is None
    assert summary.recurring_nonessential_monthly is None
    assert summary.one_time is None


# -------------------------------------------------------------------- assets


def test_liquid_assets_use_the_stored_flag_not_the_asset_type():
    summary = summarize_assets([asset("21000.00", is_liquid=True), asset("150000.00", is_liquid=False)])
    assert summary.total == D("171000.00")
    assert summary.liquid == D("21000.00")
    assert summary.record_count == 2 and summary.liquid_record_count == 1


def test_only_illiquid_assets_leave_liquid_assets_unknown():
    summary = summarize_assets([asset("150000.00", is_liquid=False)])
    assert summary.total == D("150000.00")
    assert summary.liquid is None
    assert summary.available is True


def test_a_zero_value_liquid_asset_is_a_known_zero_not_unknown():
    """Phase 34 section 35, stated directly."""
    summary = summarize_assets([asset("0.00", is_liquid=True)])
    assert summary.liquid == D("0.00")
    assert summary.total == D("0.00")
    assert summary.available is True


def test_multiple_assets_sum_exactly():
    summary = summarize_assets([asset("0.01"), asset("0.02"), asset("0.03")])
    assert summary.total == D("0.06")


def test_no_asset_records_is_unknown_not_zero():
    summary = summarize_assets([])
    assert summary.available is False
    assert summary.total is None and summary.liquid is None


# --------------------------------------------------------------- liabilities


def test_multiple_liabilities_sum_outstanding_and_monthly_payments():
    summary = summarize_liabilities([liability("118000.00", "850.00"), liability("4000.00", "120.00")])
    assert summary.outstanding == D("122000.00")
    assert summary.monthly_payment == D("970.00")
    assert summary.record_count == 2


def test_a_zero_outstanding_liability_is_a_known_zero():
    summary = summarize_liabilities([liability("0.00", "0.00")])
    assert summary.outstanding == D("0.00")
    assert summary.monthly_payment == D("0.00")
    assert summary.available is True


def test_a_liability_without_a_monthly_payment_is_not_counted_as_zero():
    """`monthly_payment = NULL` means "not provided" — it must not drag the
    aggregate down as if the household paid nothing on that debt."""
    summary = summarize_liabilities([liability("118000.00", "850.00"), liability("4000.00", None)])
    assert summary.outstanding == D("122000.00")
    assert summary.monthly_payment == D("850.00")


def test_liabilities_with_no_monthly_payment_at_all_leave_it_unknown():
    summary = summarize_liabilities([liability("118000.00", None)])
    assert summary.outstanding == D("118000.00")
    assert summary.monthly_payment is None


def test_no_liability_records_is_unknown_not_zero():
    summary = summarize_liabilities([])
    assert summary.available is False
    assert summary.outstanding is None and summary.monthly_payment is None


# ----------------------------------------------------------------- cash flow


def test_cash_flow_is_income_minus_expenses_when_both_are_known():
    flow = derive_cash_flow(summarize_income([income("5200.00")]), summarize_expenses([expense("2000.00")]))
    assert flow.monthly == D("3200.00")
    assert flow.available is True


def test_cash_flow_may_be_negative():
    flow = derive_cash_flow(summarize_income([income("1000.00")]), summarize_expenses([expense("2500.00")]))
    assert flow.monthly == D("-1500.00")


def test_cash_flow_is_unknown_when_income_is_missing():
    flow = derive_cash_flow(summarize_income([]), summarize_expenses([expense("2000.00")]))
    assert flow.monthly is None and flow.available is False
    assert flow.recurring_monthly_expenses == D("2000.00")


def test_cash_flow_is_unknown_when_expenses_are_missing():
    flow = derive_cash_flow(summarize_income([income("5200.00")]), summarize_expenses([]))
    assert flow.monthly is None and flow.available is False
    assert flow.recurring_monthly_income == D("5200.00")


def test_cash_flow_is_unknown_when_both_are_missing():
    flow = derive_cash_flow(summarize_income([]), summarize_expenses([]))
    assert flow.monthly is None and flow.available is False


def test_cash_flow_excludes_one_time_records_entirely():
    flow = derive_cash_flow(
        summarize_income([income("5200.00"), income("10000.00", "one_time")]),
        summarize_expenses([expense("2000.00"), expense("5000.00", "one_time")]),
    )
    assert flow.monthly == D("3200.00")


# -------------------------------------------------------------- net position


def test_net_position_is_assets_minus_liabilities():
    net = derive_net_position(summarize_assets([asset("171000.00")]), summarize_liabilities([liability("118000.00")]))
    assert net.value == D("53000.00")
    assert net.available is True


def test_net_position_may_be_negative():
    net = derive_net_position(summarize_assets([asset("1000.00")]), summarize_liabilities([liability("5000.00")]))
    assert net.value == D("-4000.00")


def test_net_position_is_unknown_when_assets_are_missing():
    net = derive_net_position(summarize_assets([]), summarize_liabilities([liability("5000.00")]))
    assert net.value is None and net.available is False


def test_net_position_is_unknown_when_liabilities_are_missing():
    net = derive_net_position(summarize_assets([asset("1000.00")]), summarize_liabilities([]))
    assert net.value is None and net.available is False


def test_net_position_preserves_genuine_zeroes():
    net = derive_net_position(summarize_assets([asset("0.00")]), summarize_liabilities([liability("0.00")]))
    assert net.total_assets == D("0.00")
    assert net.total_outstanding_liabilities == D("0.00")
    assert net.value == D("0.00")
    assert net.available is True


def test_net_position_ignores_income_and_expenses():
    """It is a balance-sheet figure: only assets and liabilities take part."""
    summary = summarize_household_finances(
        [income("9999.00")], [expense("8888.00")], [asset("1000.00")], [liability("400.00")]
    )
    assert summary.net_position.value == D("600.00")


# ------------------------------------------------------------ emergency fund


def ef(essential: str | None, liquid: str | None):
    expenses = summarize_expenses([] if essential is None else [expense(essential, is_essential=True)])
    assets = summarize_assets([] if liquid is None else [asset(liquid, is_liquid=True)])
    return assess_household_emergency_fund(expenses, assets)


def test_required_amount_is_six_months_of_essential_expenses():
    status = ef("1000.00", "0.00")
    assert status.target_months == EMERGENCY_FUND_TARGET_MONTHS == 6
    assert status.required == D("6000.00")


def test_emergency_fund_sufficient_when_liquid_assets_exceed_the_requirement():
    status = ef("1000.00", "10000.00")
    assert status.status == "sufficient"
    assert status.shortfall == D("0")
    assert status.available is True


def test_emergency_fund_insufficient_reports_the_exact_shortfall():
    status = ef("1000.00", "2500.00")
    assert status.status == "insufficient"
    assert status.shortfall == D("3500.00")


def test_emergency_fund_boundary_exactly_at_requirement_is_sufficient():
    """Phase 34 section 33, case 1 — exact Decimal comparison, no tolerance."""
    status = ef("1000.00", "6000.00")
    assert status.status == "sufficient"
    assert status.shortfall == D("0")


def test_emergency_fund_boundary_one_below_requirement_is_insufficient():
    """Phase 34 section 33, case 2."""
    status = ef("1000.00", "5999.00")
    assert status.status == "insufficient"
    assert status.shortfall == D("1.00")


def test_emergency_fund_boundary_one_above_requirement_is_sufficient():
    """Phase 34 section 33, case 3."""
    status = ef("1000.00", "6001.00")
    assert status.status == "sufficient"
    assert status.shortfall == D("0")


def test_emergency_fund_is_unknown_without_essential_expenses():
    status = ef(None, "10000.00")
    assert status.status == "unknown"
    assert status.required is None and status.shortfall is None
    assert status.current_liquid_assets == D("10000.00")
    assert status.available is False


def test_emergency_fund_is_unknown_without_liquid_assets():
    status = ef("1000.00", None)
    assert status.status == "unknown"
    assert status.shortfall is None
    assert status.current_liquid_assets is None
    assert status.available is False
    assert status.required == D("6000.00")  # the requirement itself is still known


def test_emergency_fund_is_unknown_with_no_records_at_all():
    status = ef(None, None)
    assert status.status == "unknown"
    assert status.available is False


def test_zero_liquid_assets_is_a_genuine_zero_not_unknown():
    """Phase 34 section 35: a household that recorded a liquid asset worth 0 has
    a KNOWN emergency-fund position — an insufficient one."""
    status = ef("1000.00", "0.00")
    assert status.status == "insufficient"
    assert status.current_liquid_assets == D("0.00")
    assert status.shortfall == D("6000.00")
    assert status.available is True


def test_nonessential_expenses_do_not_raise_the_emergency_fund_requirement():
    expenses = summarize_expenses(
        [expense("1000.00", is_essential=True), expense("5000.00", is_essential=False)]
    )
    status = assess_household_emergency_fund(expenses, summarize_assets([asset("6000.00")]))
    assert status.required == D("6000.00")
    assert status.status == "sufficient"


def test_inactive_essential_expenses_do_not_raise_the_requirement():
    expenses = summarize_expenses(
        [expense("1000.00", is_essential=True), expense("9000.00", is_essential=True, is_active=False)]
    )
    assert assess_household_emergency_fund(expenses, summarize_assets([asset("6000.00")])).required == D("6000.00")


def test_household_emergency_fund_agrees_with_the_individual_engine():
    """The household layer must never diverge from `core/goals.py`'s semantics:
    same 6-month target, same `current >= required` comparison."""
    for essential, liquid in (("1000.00", "5999.00"), ("1000.00", "6000.00"), ("1000.00", "6001.00"), ("0.01", "0.00")):
        household = ef(essential, liquid)
        individual = assess_emergency_fund(float(essential), float(liquid))
        assert float(household.required) == pytest.approx(individual.required_amount)
        assert float(household.shortfall) == pytest.approx(individual.shortfall)
        assert (household.status == "sufficient") is individual.sufficient


def test_emergency_fund_rejects_a_nonpositive_target():
    with pytest.raises(ValueError, match="target_months"):
        assess_household_emergency_fund(summarize_expenses([]), summarize_assets([]), target_months=0)


# ----------------------------------------------------------- whole summary


def test_summary_combines_every_section_from_source_records_only():
    summary = summarize_household_finances(
        [income("5200.00"), income("12000.00", "yearly"), income("900.00", "one_time"), income("400.00", is_active=False)],
        [expense("1400.00", is_essential=True), expense("600.00", is_essential=False)],
        [asset("21000.00", is_liquid=True), asset("150000.00", is_liquid=False)],
        [liability("118000.00", "850.00")],
    )
    assert summary.income.recurring_monthly == D("6200.00")
    assert summary.income.one_time == D("900.00")
    assert summary.expenses.recurring_essential_monthly == D("1400.00")
    assert summary.assets.liquid == D("21000.00")
    assert summary.liabilities.outstanding == D("118000.00")
    assert summary.cash_flow.monthly == D("4200.00")
    assert summary.net_position.value == D("53000.00")
    assert summary.emergency_fund.required == D("8400.00")
    assert summary.emergency_fund.status == "sufficient"


def test_an_empty_household_knows_nothing_and_assumes_nothing():
    summary = summarize_household_finances([], [], [], [])
    for section in (summary.income, summary.expenses, summary.assets, summary.liabilities):
        assert section.available is False
    assert summary.cash_flow.monthly is None
    assert summary.net_position.value is None
    assert summary.emergency_fund.status == "unknown"


def test_the_summary_is_deterministic():
    """Same records in, byte-identical summary out — no randomness, no clock."""
    records = (
        [income("5200.00"), income("12000.00", "yearly")],
        [expense("1400.00"), expense("600.00", is_essential=False)],
        [asset("21000.00"), asset("150000.00", is_liquid=False)],
        [liability("118000.00", "850.00")],
    )
    first = summarize_household_finances(*records)
    second = summarize_household_finances(*records)
    assert first.model_dump() == second.model_dump()


def test_the_summary_exposes_no_score_ratio_or_recommendation_field():
    """Phase 34 is factual: no savings rate, debt ratio, score or strategy."""
    summary = summarize_household_finances([income()], [expense()], [asset()], [liability()])
    forbidden = ("score", "ratio", "rate", "rank", "recommend", "strategy", "risk", "probability", "savings")
    def walk(model, path=""):
        for field, value in model.model_dump().items():
            assert not any(word in field.lower() for word in forbidden), f"{path}{field}"
    walk(summary)
    for section_name in ("income", "expenses", "assets", "liabilities", "cash_flow", "net_position", "emergency_fund"):
        walk(getattr(summary, section_name), f"{section_name}.")


# ------------------------------------------------ Phase 35 metadata isolation


def test_engine_inputs_cannot_carry_phase_35_metadata():
    """Phase 35 added `notes`, `description` and `interest_rate` to the stored
    records. None of them may influence a summary figure, so the engine's input
    records deliberately have no field for them -- the metadata cannot reach the
    arithmetic even by accident (ADR-034)."""
    metadata = {"notes", "description", "interest_rate"}
    for record in (IncomeRecord, ExpenseRecord, AssetRecord, LiabilityRecord):
        assert not metadata & set(record.model_fields), record.__name__


def test_interest_rate_is_never_used_to_derive_anything():
    """No debt ratio, schedule, payoff date or interest figure exists: the
    liability summary is built from outstanding amount and payment only."""
    summary = summarize_liabilities([liability("118000.00", "850.00")])
    assert set(summary.model_dump()) == {"outstanding", "monthly_payment", "record_count", "available"}
