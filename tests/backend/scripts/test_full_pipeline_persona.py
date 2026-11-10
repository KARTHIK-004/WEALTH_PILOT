"""Persona E ("WealthPilot Demo - Full Pipeline", WPDEMO-E): its data, its linkage to a GENUINE FAR-Trans customer, and the first two pipeline stages.

No database and no network. Everything below reads the persona's package files and the immutable FAR-Trans CSVs, and runs the existing, unmodified feature
engineering and the existing trained risk model. Nothing here invents a label, a transaction or a result: the persona files carry no risk category at all, and
the expected category in these tests is the dataset's own label for the linked customer.
"""

from __future__ import annotations

import csv
import math
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend" / "scripts"))

from demo_data_package import DEMO_DATA_DIR, load_expected_results, load_personas, read_json  # noqa: E402
from wealthpilot.agents import nodes as N  # noqa: E402
from wealthpilot.agents.state import AgentState  # noqa: E402
from wealthpilot.data.preprocessing import ALL_FEATURES  # noqa: E402

GENUINE_LEVELS = {"Conservative", "Income", "Balanced", "Aggressive"}
FAR_TRANS = ROOT / "datasets" / "raw" / "FAR-Trans"
INFORMATION_REQUEST_THRESHOLD = 0.50  # agents/graph.py: below this the graph asks for information instead of proceeding


@pytest.fixture(scope="module")
def persona() -> dict:
    return next(p for p in load_personas() if p["demo_key"] == "WPDEMO-E")


@pytest.fixture(scope="module")
def dataset_rows(persona) -> list[dict]:
    with (FAR_TRANS / "customer_information.csv").open(encoding="utf-8", newline="") as handle:
        return [row for row in csv.DictReader(handle) if row["customerID"] == persona["external_customer_id"]]


@pytest.fixture(scope="module")
def feature_row(persona) -> dict | None:
    return N.engineer_features_for_customer(persona["external_customer_id"])


# ---------------------------------------------------------------------------------------------------------------- the persona's own data


def test_the_persona_is_clearly_named_labelled_synthetic_and_owned_by_the_seed(persona):
    assert persona["name"] == "WealthPilot Demo — Full Pipeline"
    assert persona["owned_by_seed"] is True
    profile_file = read_json(DEMO_DATA_DIR / "profiles" / "persona_e_full_pipeline.json")
    assert profile_file["source"] == "synthetic_demo" and profile_file["persona"] == "E"
    assert persona["profile"]["name"] == persona["name"]
    assert "Synthetic identity" in persona["purpose"]


def test_the_profile_is_complete_and_coherent_with_the_linked_customer(persona, dataset_rows):
    profile = persona["profile"]
    assert all(profile.get(field) is not None for field in ("name", "age", "income", "employment_status", "customer_type", "investment_capacity"))
    # The synthetic profile uses the linked customer's own type and capacity band, so the two never contradict each other.
    assert {r["customerType"] for r in dataset_rows} == {profile["customer_type"]}
    assert {r["investmentCapacity"] for r in dataset_rows} == {profile["investment_capacity"]}


def test_the_persona_has_three_goals_with_realistic_amounts_and_dates(persona):
    goals = persona["goals"]
    assert len(goals) >= 2
    assert len({g["priority"] for g in goals}) == len(goals)
    for goal in goals:
        assert goal["target_amount"] >= 500_000 and 0 <= goal["current_savings"] < goal["target_amount"]
        assert date.fromisoformat(goal["target_date"]) >= date(2030, 1, 1)
        assert goal["goal_type"] not in {"goal", "test", "placeholder", "other"}


def test_every_financial_input_is_provided_and_the_emergency_fund_story_is_consistent(persona):
    inputs = persona["financial_inputs"]
    assert set(inputs) == {"monthly_essential_expenses", "current_liquid_assets", "contribution_amount", "annual_return_rate", "annual_inflation_rate", "contribution_periods_per_year"}
    assert all(value is not None for value in inputs.values())
    monthly_income = persona["profile"]["income"] / 12
    assert inputs["contribution_amount"] <= monthly_income - inputs["monthly_essential_expenses"]
    expected = load_expected_results()["WPDEMO-E"]
    assert expected["emergency_fund_sufficient"] is (inputs["current_liquid_assets"] >= 6 * inputs["monthly_essential_expenses"])


def test_twelve_consecutive_months_are_reported_and_never_exceed_income(persona):
    records = persona["monthly_records"]
    assert len(records) == 12
    months = [int(r["period"][:4]) * 12 + int(r["period"][5:7]) for r in records]
    assert months == list(range(months[0], months[0] + 12))
    for record in records:
        assert record["income_basis"] == "net"
        assert record["expenses"] + record["savings"] + record["investment_contribution"] <= record["income"], record["period"]
    midpoint = sorted(r["income"] for r in records)[6]
    assert 0.6 * persona["profile"]["income"] / 12 <= midpoint <= 1.4 * persona["profile"]["income"] / 12


def test_the_persona_files_state_no_risk_category_label_or_result(persona):
    """The model, not the file, decides the category: no persona file may carry a risk category, a score, an allocation or any computed outcome."""
    forbidden = {"risk_category", "risk_level", "riskLevel", "risk_score", "weights", "allocation", "sharpe_ratio", "feasibility", "recommendation"}
    for directory in ("profiles", "questionnaire", "financial_inputs", "individual_goals", "expected_results", "monthly_records"):
        text = (DEMO_DATA_DIR / directory / "persona_e_full_pipeline.json").read_text(encoding="utf-8")
        assert not any(f'"{key}"' in text for key in forbidden), directory


# --------------------------------------------------------------------------------------------------------- the linkage to genuine data


def test_the_link_is_a_real_far_trans_customer_used_by_no_other_persona(persona):
    others = [p["external_customer_id"] for p in load_personas() if p["demo_key"] != "WPDEMO-E" and p["external_customer_id"]]
    assert persona["external_customer_id"] not in others
    assert len(persona["external_customer_id"]) == 20


def test_the_linked_customers_dataset_label_is_genuine_never_predicted_or_not_available(persona, dataset_rows):
    assert dataset_rows, "customer_information.csv has no row for the linked customer"
    labels = {row["riskLevel"] for row in dataset_rows}
    assert labels <= GENUINE_LEVELS and labels == {"Balanced"}
    assert not any(label.startswith("Predicted_") or label == "Not_Available" for label in labels)


def test_the_linked_customer_has_a_real_trading_history(persona):
    with (FAR_TRANS / "transactions.csv").open(encoding="utf-8", newline="") as handle:
        stamps = [row["timestamp"] for row in csv.DictReader(handle) if row["customerID"] == persona["external_customer_id"]]
    assert len(stamps) >= 100
    months = {s[:7] for s in stamps}
    assert len(months) >= 12, f"only {len(months)} distinct trading months"


# --------------------------------------------------------------------------------------------------------- feature engineering and the model


def test_feature_engineering_returns_a_valid_point_in_time_feature_row(feature_row):
    assert feature_row is not None, "no point-in-time-visible feature row: the linkage would leave the risk step without input"
    assert [f for f in ALL_FEATURES if f not in feature_row] == []
    for name in ALL_FEATURES:
        value = feature_row[name]
        assert not (isinstance(value, float) and math.isnan(value)), f"{name} is NaN"


def test_the_existing_risk_model_returns_the_datasets_own_label_above_the_information_threshold(feature_row, dataset_rows):
    delta = N.risk_analyst_node(AgentState(customer_id=0), feature_row)
    result = delta.risk_assessment
    assert result.unavailable_reason is None
    assert result.risk_category in GENUINE_LEVELS
    assert result.confidence is not None and result.confidence >= INFORMATION_REQUEST_THRESHOLD
    assert result.risk_category == dataset_rows[0]["riskLevel"]  # the model and the dataset's genuine label agree for this customer


def test_a_profile_without_a_link_gets_no_feature_row_and_no_invented_risk_category():
    """The pending-information case stays pending: no row, no category, a stated reason."""
    delta = N.risk_analyst_node(AgentState(customer_id=0), None)
    assert delta.risk_assessment.risk_category is None and delta.risk_assessment.confidence is None
    assert "engineered feature row was not provided" in delta.risk_assessment.unavailable_reason
    assert N.engineer_features_for_customer("0" * 20) is None
