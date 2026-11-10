"""ADR-043 -- `core/behaviour_findings.py` and `core/personalized_insight.py`. Synthetic monthly records only. Findings restate existing features without a new formula or
threshold; the composer is display-only, puts behaviour first, lets the risk assessment win, and never invents sentiment."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from wealthpilot.core.behaviour_features import MonthlyObservation, compute_behaviour_features
from wealthpilot.core.behaviour_findings import FINDINGS_VERSION, NOT_INCLUDED, OBSERVED, UNAVAILABLE, derive_findings
from wealthpilot.core.personalized_insight import PURPOSE, RiskProfileView, compose_insight
from wealthpilot.core.user_text_sentiment import analyse_user_text

D = Decimal


def months(*rows: dict) -> list[MonthlyObservation]:
    return [MonthlyObservation(period=date(2026, i + 1, 1), **r) for i, r in enumerate(rows)]


def findings_for(*rows: dict):
    return derive_findings(compute_behaviour_features(months(*rows)))


def by_code(f, code):
    return next(x for x in f.findings if x.code == code)


# ================================================================ findings

def test_no_records_means_no_findings_and_no_zeros():
    f = findings_for()
    assert (f.version, f.history, f.observation_count, f.latest_period) == (FINDINGS_VERSION, "none", 0, None)
    assert by_code(f, "history_sufficiency").status == UNAVAILABLE
    for code in ("expenses_trend", "savings_trend", "investment_contribution_trend", "savings_activity", "expense_to_income_ratio"):
        x = by_code(f, code)
        assert x.status == UNAVAILABLE and x.direction is None and "0" not in x.statement.split(":")[0] and x.values.get("absolute_change") is None


def test_one_month_has_ratios_but_no_trend():
    f = findings_for({"income": D(1000), "expenses": D(400), "savings": D(200)})
    assert f.history == "single_month" and by_code(f, "expenses_trend").status == UNAVAILABLE
    r = by_code(f, "expense_to_income_ratio")
    assert r.status == OBSERVED and r.values["ratio"] == pytest.approx(0.4) and "40.0%" in r.statement and "2026-01" in r.statement
    assert by_code(f, "investment_contribution_to_income_ratio").status == UNAVAILABLE             # not reported: unavailable, never 0


def test_direction_comes_only_from_the_sign_of_the_change():
    f = findings_for({"income": D(1000), "expenses": D(400), "savings": D(300)}, {"income": D(1000), "expenses": D(500), "savings": D(300), "investment_contribution": D(0)})
    e, s = by_code(f, "expenses_trend"), by_code(f, "savings_trend")
    assert (e.direction, e.values["absolute_change"], e.values["relative_change"]) == ("increased", 100.0, 0.25) and "increased by ₹100" in e.statement and "25.0%" in e.statement
    assert (s.direction, s.statement) == ("unchanged", "Savings were unchanged from the previous month.")
    g = findings_for({"expenses": D(500)}, {"expenses": D(300)})
    assert by_code(g, "expenses_trend").direction == "decreased"


def test_no_judgement_words_and_no_thresholds_are_ever_used():
    f = findings_for({"income": D(1000), "expenses": D(990)}, {"income": D(1000), "expenses": D(2000)})
    text = " ".join(x.statement for x in f.findings).lower()
    for word in ("overspend", "distress", "irregular", "unusual", "risky", "healthy", "poor", "worry", "should", "recommend"):
        assert word not in text, word


def test_activity_counts_reported_months_only_and_unreported_months_are_not_zero():
    f = findings_for({"savings": D(100)}, {"savings": D(0)}, {"savings": D(50)})
    a = by_code(f, "savings_activity")
    assert a.status == OBSERVED and a.values["months_with_amount"] == 2 and a.values["known_months"] == 3 and "2 of the 3 reported months" in a.statement
    sparse = findings_for({"savings": D(100)}, {"savings": D(100)})
    assert by_code(sparse, "savings_activity").status == UNAVAILABLE and "at least" in by_code(sparse, "savings_activity").statement


def test_debt_and_goal_progress_are_not_included_and_never_zero():
    f = findings_for({"income": D(1000), "expenses": D(400)})
    for code in ("debt_burden", "goal_progress"):
        x = by_code(f, code)
        assert x.status == NOT_INCLUDED and x.values == {} and x.direction is None
    assert "nothing is assumed" in by_code(f, "debt_burden").statement and "existing goal analysis" in by_code(f, "goal_progress").statement


def test_data_quality_notes_are_carried_through():
    f = findings_for({"income": D(1000), "expenses": D(600), "savings": D(300), "investment_contribution": D(300)})
    notes = [x for x in f.findings if x.category == "data_quality"]
    assert notes and "exceed income" in notes[0].statement and f.data_quality_notes


# ================================================================ composer

def behaviour_only_findings():
    return findings_for({"income": D(1000), "expenses": D(400)}, {"income": D(1000), "expenses": D(500)})


def test_without_text_or_profile_the_behaviour_insight_is_still_valid_and_nothing_is_invented():
    i = compose_insight(behaviour_only_findings(), analyse_user_text(None), None)
    assert i.status == "behaviour_only" and i.conflicts == () and i.purpose == PURPOSE
    kinds = {s.kind for s in i.statements}
    assert kinds == {"behaviour_fact"}                                                              # no sentiment statement, no risk statement
    assert any("No text was provided" in c for c in i.caveats) and any("No stored risk assessment" in c for c in i.caveats)
    assert i.statements == compose_insight(behaviour_only_findings(), None, None).statements       # no text and "no text object" are the same


def test_with_text_and_profile_the_insight_is_complete_and_every_statement_names_its_sources():
    text = analyse_user_text("I'm worried about losing my savings, and I want to invest more safely.")
    i = compose_insight(behaviour_only_findings(), text, RiskProfileView("Conservative", "stored risk assessment", None))
    assert i.status == "complete" and i.conflicts == ()
    assert all(s.sources for s in i.statements)
    assert any(s.kind == "stated_by_user" and "unconfirmed" in s.text for s in i.statements) and any(s.kind == "risk_assessment" for s in i.statements)
    assert any("unvalidated" in c for c in i.caveats)


def test_the_assessment_wins_and_a_disagreement_is_reported_not_resolved():
    text = analyse_user_text("I want to invest safely and avoid losing my savings.")
    i = compose_insight(behaviour_only_findings(), text, RiskProfileView("Aggressive", "stored risk assessment", None))
    c = i.conflicts[0]
    assert [x.code for x in i.conflicts] == ["capital_preservation"] and "stored assessment remains in force" in c.detail and "unconfirmed" in c.detail
    assert (c.inferred_preference, c.stored_category, c.authoritative_source, c.preference_status, c.action) == (
        "capital_preservation", "Aggressive", "stored risk assessment", "unconfirmed", "confirm_or_correct")
    assert any("remains the profile in force" in s.text for s in i.statements)
    ok = compose_insight(behaviour_only_findings(), text, RiskProfileView("Conservative", "stored risk assessment", None))
    assert ok.conflicts == ()
    growth = analyse_user_text("I want higher returns.")
    assert [c.code for c in compose_insight(behaviour_only_findings(), growth, RiskProfileView("Conservative", "x", None)).conflicts] == ["growth_seeking"]
    assert compose_insight(behaviour_only_findings(), growth, RiskProfileView("Balanced", "x", None)).conflicts == ()      # only unambiguous pairings are conflicts


def test_low_information_text_adds_no_preference_and_says_so():
    i = compose_insight(behaviour_only_findings(), analyse_user_text("The train was late."), None)
    assert not any(s.kind == "stated_by_user" for s in i.statements) and any("does not contain enough personal-finance context" in c for c in i.caveats)
    vague = compose_insight(behaviour_only_findings(), analyse_user_text("I had a good day today."), None)
    assert not any(s.kind == "stated_by_user" for s in vague.statements) and any("not enough reliable financial context" in c for c in vague.caveats)
    assert vague.status == "behaviour_only"                                                          # an abstained reading does not make the insight `complete`
    negated = compose_insight(behaviour_only_findings(), analyse_user_text("I am not worried about my savings."), None)
    assert any("could not be read reliably" in c for c in negated.caveats) and any("weak interpretation" in c for c in negated.caveats)


def test_without_any_behaviour_the_insight_degrades_without_failing():
    empty = findings_for()
    assert compose_insight(empty, None, None).status == "unavailable"
    assert compose_insight(empty, analyse_user_text("I feel confident about my savings plan."), None).status == "profile_only"
    assert compose_insight(empty, None, RiskProfileView("Balanced", "x", None)).status == "profile_only"


def test_the_composer_never_advises_or_changes_anything():
    text = analyse_user_text("I'm worried about my loan but confident about saving.")
    i = compose_insight(behaviour_only_findings(), text, RiskProfileView("Balanced", "x", None))
    joined = " ".join(s.text for s in i.statements).lower()
    for word in ("buy", "sell", "you should", "we recommend", "allocate", "switch"):
        assert word not in joined, word
    assert "not financial advice" in i.purpose.lower() and "does not change" in i.purpose.lower()
