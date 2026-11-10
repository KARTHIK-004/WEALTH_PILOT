"""Financial behaviour features from optional monthly records (Research
Enhancement Track, Phase B1; `docs/DECISIONS.md` ADR-042).

Pure and deterministic: no database, no clock, no randomness, no ML, no LLM.
It reads a list of monthly observations and returns plain numbers, each with
an explicit reason whenever it cannot be computed. Nothing here is a model, a
score or a judgement about the person: the values are ratios and changes of
amounts the user reported. They are NOT sentiment, emotion or a psychological
state, they do not imply any holding, and no analysis step consumes them yet.

DEFINITIONS (all amounts are rupees per calendar month, one observation per
month; `docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md` section 6):

- income:       money received in the month, on the basis stated by the user
                (`net` or `gross`) or `None` when the user did not say.
- expenses:     total spending on living costs in the month. It EXCLUDES money
                moved to savings or investments, so the three outflows below
                are disjoint.
- savings:      money newly set aside into savings in the month. A transfer
                from savings into an investment is not new savings.
- investment_contribution:
                money newly invested in the month. Money moved out of existing
                savings into an investment counts as neither new savings nor
                new income.

FEATURE RULES

- A ratio needs the income and the numerator of that SAME month. Income that is
  missing or zero gives no ratio, with the reason stated. A missing amount is
  never zero.
- A change compares the latest month with the month immediately before it. If
  that month is absent, or either value is unknown, the change is unavailable.
  A relative change also needs a previous value above zero.
- Consistency needs at least `MIN_CONSISTENCY_OBSERVATIONS` known months inside
  the `CONSISTENCY_WINDOW_MONTHS` ending at the latest reported month. It is
  the share of those KNOWN months with an amount above zero. Months with no
  report are not counted as zero activity; the number of known months is
  returned beside it so the reader can see how much it rests on.
- Amounts of different currencies or malformed observations are rejected, never
  silently combined or repaired.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Iterable

FEATURE_SET_VERSION = "behaviour_features_v1"
DEFAULT_CURRENCY = "INR"
CONSISTENCY_WINDOW_MONTHS = 12
MIN_CONSISTENCY_OBSERVATIONS = 3
INCOME_BASES = ("net", "gross")


@dataclass(frozen=True)
class MonthlyObservation:
    """One customer-reported month. `period` is the first day of the month.
    Every amount is optional; `None` means not reported (never zero)."""

    period: date
    income: Decimal | None = None
    expenses: Decimal | None = None
    savings: Decimal | None = None
    investment_contribution: Decimal | None = None
    income_basis: str | None = None
    currency: str = DEFAULT_CURRENCY


@dataclass(frozen=True)
class FeatureValue:
    """A number, or the reason there is none. Exactly one of the two is set."""

    value: float | None = None
    unavailable_reason: str | None = None


@dataclass(frozen=True)
class RatioFeatures:
    expense_to_income: FeatureValue
    savings_to_income: FeatureValue
    investment_contribution_to_income: FeatureValue


@dataclass(frozen=True)
class ChangeFeature:
    absolute_change: FeatureValue
    relative_change: FeatureValue


@dataclass(frozen=True)
class ConsistencyFeature:
    """Share of known months with an amount above zero, plus what it rests on."""

    share_with_amount: FeatureValue
    known_months: int
    window_months: int


@dataclass(frozen=True)
class BehaviourFeatures:
    feature_set_version: str
    currency: str
    observation_count: int
    latest_period: date | None
    latest_income_basis: str | None
    latest_ratios: RatioFeatures
    expenses_change: ChangeFeature
    savings_change: ChangeFeature
    investment_contribution_change: ChangeFeature
    savings_consistency: ConsistencyFeature
    investment_contribution_consistency: ConsistencyFeature
    data_quality_notes: list[str] = field(default_factory=list)
    # The month-over-month change in reported income (the same `_change` helper as the other amounts). Always set by `compute_behaviour_features`; it is the last field so that existing
    # positional construction keeps its meaning.
    income_change: ChangeFeature = field(default_factory=lambda: ChangeFeature(FeatureValue(unavailable_reason="Income change was not computed."), FeatureValue(unavailable_reason="Income change was not computed.")))


def _first_of_month(value: date) -> bool:
    return value.day == 1


def _month_index(value: date) -> int:
    return value.year * 12 + value.month - 1


def _validate(observations: list[MonthlyObservation]) -> str:
    seen: set[date] = set()
    currencies = {o.currency for o in observations}
    if len(currencies) > 1:
        raise ValueError(f"observations mix currencies {sorted(currencies)}; amounts are never combined across currencies")
    for obs in observations:
        if not _first_of_month(obs.period):
            raise ValueError(f"period {obs.period} is not the first day of a month")
        if obs.period in seen:
            raise ValueError(f"duplicate reporting period {obs.period}")
        seen.add(obs.period)
        if obs.income_basis is not None and obs.income_basis not in INCOME_BASES:
            raise ValueError(f"income_basis must be one of {INCOME_BASES} or None")
        for name in ("income", "expenses", "savings", "investment_contribution"):
            amount = getattr(obs, name)
            if amount is None:
                continue
            if not isinstance(amount, Decimal) or not amount.is_finite():
                raise ValueError(f"{name} must be a finite Decimal or None")
            if amount < 0:
                raise ValueError(f"{name} must not be negative")
    return next(iter(currencies), DEFAULT_CURRENCY)


def _ratio(numerator: Decimal | None, income: Decimal | None, numerator_label: str) -> FeatureValue:
    if income is None:
        return FeatureValue(unavailable_reason="Income was not reported for this month.")
    if income == 0:
        return FeatureValue(unavailable_reason="Income is zero for this month, so a ratio is undefined.")
    if numerator is None:
        return FeatureValue(unavailable_reason=f"{numerator_label} was not reported for this month.")
    return FeatureValue(value=float(numerator / income))


def _change(by_month: dict[int, MonthlyObservation], latest: MonthlyObservation, attr: str, label: str) -> ChangeFeature:
    previous = by_month.get(_month_index(latest.period) - 1)
    if previous is None:
        reason = f"No record for the month before {latest.period:%Y-%m}, so no change can be measured."
        return ChangeFeature(FeatureValue(unavailable_reason=reason), FeatureValue(unavailable_reason=reason))
    now, before = getattr(latest, attr), getattr(previous, attr)
    if now is None or before is None:
        reason = f"{label} was not reported in both months."
        return ChangeFeature(FeatureValue(unavailable_reason=reason), FeatureValue(unavailable_reason=reason))
    absolute = FeatureValue(value=float(now - before))
    if before == 0:
        relative = FeatureValue(unavailable_reason="The previous month's amount is zero, so a relative change is undefined.")
    else:
        relative = FeatureValue(value=float((now - before) / before))
    return ChangeFeature(absolute, relative)


def _consistency(by_month: dict[int, MonthlyObservation], latest: MonthlyObservation, attr: str, label: str) -> ConsistencyFeature:
    end = _month_index(latest.period)
    window = range(end - CONSISTENCY_WINDOW_MONTHS + 1, end + 1)
    known = [getattr(by_month[i], attr) for i in window if i in by_month and getattr(by_month[i], attr) is not None]
    if len(known) < MIN_CONSISTENCY_OBSERVATIONS:
        reason = (
            f"Needs {label.lower()} reported in at least {MIN_CONSISTENCY_OBSERVATIONS} of the last "
            f"{CONSISTENCY_WINDOW_MONTHS} months; found {len(known)}."
        )
        return ConsistencyFeature(FeatureValue(unavailable_reason=reason), len(known), CONSISTENCY_WINDOW_MONTHS)
    share = sum(1 for amount in known if amount > 0) / len(known)
    return ConsistencyFeature(FeatureValue(value=share), len(known), CONSISTENCY_WINDOW_MONTHS)


def compute_behaviour_features(observations: Iterable[MonthlyObservation]) -> BehaviourFeatures:
    """Derives the feature set from `observations`. Raises `ValueError` for a
    malformed observation set; an empty or sparse set is valid and simply
    yields features that are unavailable, each with its reason."""
    items = sorted(observations, key=lambda o: o.period)
    currency = _validate(items)
    by_month = {_month_index(o.period): o for o in items}

    if not items:
        reason = "No monthly records have been reported."
        unavailable = FeatureValue(unavailable_reason=reason)
        change = ChangeFeature(unavailable, unavailable)
        consistency = ConsistencyFeature(unavailable, 0, CONSISTENCY_WINDOW_MONTHS)
        return BehaviourFeatures(
            FEATURE_SET_VERSION, currency, 0, None, None,
            RatioFeatures(unavailable, unavailable, unavailable),
            change, change, change, consistency, consistency,
            income_change=change,
        )

    latest = items[-1]
    ratios = RatioFeatures(
        expense_to_income=_ratio(latest.expenses, latest.income, "Expenses"),
        savings_to_income=_ratio(latest.savings, latest.income, "Savings"),
        investment_contribution_to_income=_ratio(latest.investment_contribution, latest.income, "Investment contribution"),
    )
    notes: list[str] = []
    parts = (latest.income, latest.expenses, latest.savings, latest.investment_contribution)
    if all(p is not None for p in parts) and latest.income > 0:
        if latest.expenses + latest.savings + latest.investment_contribution > latest.income:
            notes.append(
                "In the latest month, expenses, savings and investments together exceed income. "
                "This can be genuine (for example spending from earlier savings) or a sign that an "
                "amount was counted twice; it is flagged, not corrected."
            )
    # Income basis can differ between months; ratios use each month's own income only.
    bases = {o.income_basis for o in items if o.income is not None}
    if len(bases - {None}) > 1:
        notes.append("Income was reported on different bases (net and gross) in different months.")
    if None in bases and len(bases) > 1:
        notes.append("Income basis (net or gross) was not stated for every month that reports income.")

    return BehaviourFeatures(
        feature_set_version=FEATURE_SET_VERSION,
        currency=currency,
        observation_count=len(items),
        latest_period=latest.period,
        latest_income_basis=latest.income_basis,
        latest_ratios=ratios,
        income_change=_change(by_month, latest, "income", "Income"),
        expenses_change=_change(by_month, latest, "expenses", "Expenses"),
        savings_change=_change(by_month, latest, "savings", "Savings"),
        investment_contribution_change=_change(by_month, latest, "investment_contribution", "Investment contribution"),
        savings_consistency=_consistency(by_month, latest, "savings", "Savings"),
        investment_contribution_consistency=_consistency(by_month, latest, "investment_contribution", "Investment contribution"),
        data_quality_notes=notes,
    )


__all__ = [
    "BehaviourFeatures",
    "ChangeFeature",
    "ConsistencyFeature",
    "FEATURE_SET_VERSION",
    "FeatureValue",
    "MonthlyObservation",
    "RatioFeatures",
    "compute_behaviour_features",
]

