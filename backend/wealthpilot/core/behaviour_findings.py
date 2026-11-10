"""Observed-fact findings from the existing behaviour features (Research Enhancement Track, ADR-043).

Pure and deterministic: no database, clock, randomness, ML or LLM. It adds NO new formula and NO threshold. Every finding restates a value that
`core/behaviour_features.py` already computed from the customer's own monthly records, in words, with the direction of a change taken from its sign.
It never labels a person ("overspending", "distressed", "irregular"): a label needs a threshold that no approved document defines (CLAUDE.md section 10),
so the facts and their data-quality limits are reported and the reader judges.

Rules that keep it honest:

- A finding is `observed` (a number exists) or `unavailable` (with the reason); an unavailable value is never shown as 0 or "unchanged".
- Direction is `increased`, `decreased` or `unchanged` from the sign of the absolute change against the immediately previous month, nothing more.
- Debt, EMI and goal progress are NOT computed here: the monthly records hold no debt amounts, and goal progress belongs to the existing goal engine.
  They are reported as `not_included` with that reason, never as zero.
- History sufficiency is a count (`none`, `single_month`, `multiple_months`), not a judgement.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from wealthpilot.core.behaviour_features import BehaviourFeatures, ChangeFeature, ConsistencyFeature, FeatureValue

FINDINGS_VERSION = "behaviour_findings_v1"
OBSERVED, UNAVAILABLE, NOT_INCLUDED = "observed", "unavailable", "not_included"


@dataclass(frozen=True)
class Finding:
    code: str
    category: str                         # trend | activity | ratio | data_quality | coverage
    status: str                           # observed | unavailable | not_included
    statement: str                        # one plain sentence restating the fact (or the reason there is none)
    sources: tuple[str, ...]              # the behaviour-feature fields this restates
    direction: str | None = None          # increased | decreased | unchanged (trend findings only)
    values: dict[str, float | None] = field(default_factory=dict)


@dataclass(frozen=True)
class BehaviourFindings:
    version: str
    history: str                          # none | single_month | multiple_months
    observation_count: int
    latest_period: str | None
    findings: tuple[Finding, ...]
    data_quality_notes: tuple[str, ...]


def _money(amount: float, currency: str) -> str:
    symbol = "₹" if currency == "INR" else f"{currency} "
    return f"{symbol}{amount:,.0f}"


def _trend(code: str, label: str, feature: ChangeFeature, currency: str) -> Finding:
    absolute, relative = feature.absolute_change, feature.relative_change
    sources = (f"{code}_change.absolute_change", f"{code}_change.relative_change")
    if absolute.value is None:
        return Finding(f"{code}_trend", "trend", UNAVAILABLE, f"{label}: no month-on-month change is available. {absolute.unavailable_reason}", sources)
    direction = "increased" if absolute.value > 0 else "decreased" if absolute.value < 0 else "unchanged"
    values = {"absolute_change": absolute.value, "relative_change": relative.value}
    if direction == "unchanged":
        text = f"{label} {'were' if label.endswith('s') else 'was'} unchanged from the previous month."
    else:
        text = f"{label} {direction} by {_money(abs(absolute.value), currency)} compared with the previous month"
        text += f" ({abs(relative.value) * 100:.1f}%)." if relative.value is not None else f" (a percentage is unavailable: {relative.unavailable_reason})"
    return Finding(f"{code}_trend", "trend", OBSERVED, text, sources, direction, values)


def _activity(code: str, label: str, feature: ConsistencyFeature) -> Finding:
    sources = (f"{code}_consistency.share_with_amount", f"{code}_consistency.known_months")
    share = feature.share_with_amount
    if share.value is None:
        return Finding(f"{code}_activity", "activity", UNAVAILABLE, f"{label}: {share.unavailable_reason}", sources, values={"known_months": float(feature.known_months)})
    active = round(share.value * feature.known_months)
    text = (f"{label} were above zero in {active} of the {feature.known_months} reported months within the last {feature.window_months} "
            "(months that were not reported are not counted).")
    return Finding(f"{code}_activity", "activity", OBSERVED, text, sources, values={"months_with_amount": float(active), "known_months": float(feature.known_months), "share": share.value})


def _ratio(code: str, label: str, value: FeatureValue, period: str | None) -> Finding:
    sources = (f"latest_ratios.{code}",)
    if value.value is None:
        return Finding(f"{code}_ratio", "ratio", UNAVAILABLE, f"{label} as a share of income: {value.unavailable_reason}", sources)
    return Finding(f"{code}_ratio", "ratio", OBSERVED, f"In {period}, {label.lower()} were {value.value * 100:.1f}% of that month's reported income.", sources, values={"ratio": value.value})


def derive_findings(features: BehaviourFeatures) -> BehaviourFindings:
    """Restate `features` as observed-fact findings. Never raises for sparse data."""
    n = features.observation_count
    history = "none" if n == 0 else "single_month" if n == 1 else "multiple_months"
    period = None if features.latest_period is None else f"{features.latest_period:%Y-%m}"
    cur = features.currency
    out: list[Finding] = [
        Finding("history_sufficiency", "coverage", OBSERVED if n else UNAVAILABLE,
                {"none": "No monthly records have been reported, so no behaviour finding can be made.",
                 "single_month": "One month has been reported: month-on-month changes need at least two consecutive months.",
                 "multiple_months": f"{n} months have been reported."}[history], ("observation_count",), values={"observation_count": float(n)}),
        _trend("income", "Income", features.income_change, cur),
        _trend("expenses", "Expenses", features.expenses_change, cur),
        _trend("savings", "Savings", features.savings_change, cur),
        _trend("investment_contribution", "Investment contributions", features.investment_contribution_change, cur),
        _activity("savings", "Savings", features.savings_consistency),
        _activity("investment_contribution", "Investment contributions", features.investment_contribution_consistency),
        _ratio("expense_to_income", "Expenses", features.latest_ratios.expense_to_income, period),
        _ratio("savings_to_income", "Savings", features.latest_ratios.savings_to_income, period),
        _ratio("investment_contribution_to_income", "Investment contributions", features.latest_ratios.investment_contribution_to_income, period),
        Finding("debt_burden", "coverage", NOT_INCLUDED, "Debt and EMI burden is not computed: the monthly records hold no debt or EMI amounts, so nothing is assumed.", ("monthly_financial_records",)),
        Finding("goal_progress", "coverage", NOT_INCLUDED, "Goal progress is calculated by the existing goal analysis, not by this behaviour view.", ("financial_goals",)),
    ]
    out += [Finding(f"data_quality_{i + 1}", "data_quality", OBSERVED, note, ("data_quality_notes",)) for i, note in enumerate(features.data_quality_notes)]
    return BehaviourFindings(FINDINGS_VERSION, history, n, period, tuple(out), tuple(features.data_quality_notes))


__all__ = ["BehaviourFindings", "FINDINGS_VERSION", "Finding", "NOT_INCLUDED", "OBSERVED", "UNAVAILABLE", "derive_findings"]
