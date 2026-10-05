"""The demo dataset (`demo_data/`) and its validator
(`backend/scripts/validate_demo_data.py`) -- no database, no server.

The committed dataset must pass. Each kind of defect the validator exists to
catch is planted in a temporary copy -- with the manifest regenerated, so the
manifest check is not what catches it -- and must be reported by name.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend" / "scripts"))

from demo_data_package import (
    DEMO_DATA_DIR,
    REPO_ROOT,
    canonical_json,
    load_family,
    load_personas,
    read_json,
    select_option,
)
from validate_demo_data import (
    DEMO_DATA_REFERENCE,
    build_manifest,
    check_training_data_guard,
    main,
    validate,
    write_manifest,
)
from wealthpilot.api.services.questionnaire_service import get_questionnaire_sections

A = "profiles/persona_a_approved.json"
MEMBERS = "household/members/demo_family.json"


def _copy(tmp_path: Path) -> Path:
    copy = tmp_path / "demo_data"
    shutil.copytree(DEMO_DATA_DIR, copy)
    return copy


def _edit(copy: Path, rel: str, change, *, regenerate_manifest: bool = True) -> None:
    obj = read_json(copy / rel)
    change(obj)
    (copy / rel).write_text(canonical_json(obj), encoding="utf-8")
    if regenerate_manifest:
        write_manifest(copy, REPO_ROOT)


def _errors(copy: Path) -> list[str]:
    return validate(copy, REPO_ROOT, check_training_data=False)


# ---------------------------------------------------------------------------
# The committed dataset
# ---------------------------------------------------------------------------


def test_the_committed_dataset_is_valid():
    assert validate() == []


def test_the_validator_exits_zero_and_says_so(capsys):
    assert main([]) == 0
    assert "DEMO DATA VALID" in capsys.readouterr().out


def test_regenerating_the_manifest_is_byte_stable(tmp_path):
    copy = _copy(tmp_path)
    before = (copy / "manifest.json").read_bytes()
    write_manifest(copy, REPO_ROOT)
    assert (copy / "manifest.json").read_bytes() == before


def test_the_manifest_counts_describe_the_dataset():
    manifest = read_json(DEMO_DATA_DIR / "manifest.json")
    counts = manifest["counts"]
    assert manifest["source"] == "synthetic_demo"
    assert "MUST NOT be used as additional ML training data" in manifest["not_for_training"]
    assert (counts["individual_personas"], counts["households"], counts["household_members"]) == (4, 1, 2)
    assert counts["questionnaire_answers"] == 4 * len([q for s in get_questionnaire_sections() for q in s["questions"]])
    assert counts["transactions"] == 0 and manifest["transactions"]["included"] is False


def test_the_manifest_guards_every_raw_training_file():
    raw = REPO_ROOT / "datasets" / "raw"
    if not raw.exists():
        pytest.skip("raw datasets are not present in this checkout")
    present = {p.relative_to(REPO_ROOT).as_posix() for p in raw.rglob("*") if p.is_file() and p.name != ".gitkeep"}
    assert set(read_json(DEMO_DATA_DIR / "manifest.json")["training_data_guard"]) == present


def test_the_loader_gives_the_seed_its_personas_and_family():
    personas = load_personas()
    assert [p["demo_key"] for p in personas] == ["WPDEMO-A", "WPDEMO-B", "WPDEMO-C", "WPDEMO-D"]
    assert [p["owned_by_seed"] for p in personas] == [True, True, True, False]
    assert "financial_inputs" not in personas[2] and "financial_inputs" not in personas[3]  # absent, never zeros
    family = load_family()
    assert family["primary_name"] == personas[1]["name"]
    assert [m["name"] for m in family["members"]] == [personas[2]["name"]]  # the primary is the creator, not added


def test_every_answer_is_the_personas_own_position_rule():
    questions = {q["number"]: q for s in get_questionnaire_sections() for q in s["questions"]}
    for persona in load_personas():
        for answer in persona["answers"]:
            options = questions[answer["question_number"]]["options"]
            assert answer["option_key"] == select_option(options, persona["answer_offset"])


# ---------------------------------------------------------------------------
# Planted defects -- each must be reported
# ---------------------------------------------------------------------------

DEFECTS = [
    ("duplicate demo key", "profiles/persona_d_pending_information.json",
     lambda o: o.update(demo_key="WPDEMO-A"), "duplicate demo_key"),
    ("orphan household member", MEMBERS,
     lambda o: o["members"][1].update(demo_key="WPDEMO-Z"), "unknown persona"),
    ("a second primary", MEMBERS,
     lambda o: o["members"][1].update(relationship="self", role="primary"), "exactly one primary"),
    ("a primary who is not self", MEMBERS,
     lambda o: o["members"][0].update(relationship="spouse"), "primary member must have relationship 'self'"),
    ("self for a non-primary", MEMBERS,
     lambda o: o["members"][1].update(relationship="self"), "reserved for the primary"),
    ("unknown household primary", "household/households/demo_family.json",
     lambda o: o.update(primary_demo_key="WPDEMO-Z"), "unknown persona"),
    ("an invented profile field", A,
     lambda o: o["profile"].update(risk_category="Aggressive"), "not a ProfileCreateRequest field"),
    ("an invented goal field", "individual_goals/persona_a_approved.json",
     lambda o: o["goals"][0].update(monte_carlo_probability=0.9), "not a GoalCreate field"),
    ("savings above the target", "individual_goals/persona_b_savings_first.json",
     lambda o: o["goals"][0].update(current_savings=10_000_000), "exceeds its target_amount"),
    ("a negative household amount", "household/income/demo_family.json",
     lambda o: o["records"][0].update(amount=-1), "HouseholdIncomeCreate rejects"),
    ("an invented household field", "household/assets/demo_family.json",
     lambda o: o["records"][0].update(market_value=1), "HouseholdAssetCreate rejects"),
    ("a duplicate idempotency key", "household/expenses/demo_family.json",
     lambda o: o["records"][1].update(description=o["records"][0]["description"]), "duplicate description"),
    ("missing inputs without a reason", "financial_inputs/persona_c_compliance_rejected.json",
     lambda o: o.pop("financial_inputs_unavailable_reason"), "without a financial_inputs_unavailable_reason"),
    ("a stored null inside provided inputs", "financial_inputs/persona_a_approved.json",
     lambda o: o["financial_inputs"].update(contribution_amount=None), "omit an unknown field"),
    ("a FinancialInputsUpdate field that does not exist", "financial_inputs/persona_b_savings_first.json",
     lambda o: o["financial_inputs"].update(monthly_income=4000), "not a FinancialInputsUpdate field"),
    ("an option the question does not have", "questionnaire/persona_a_approved.json",
     lambda o: o["answers"][0].update(option_key="z"), "is not an option"),
    ("an unanswered question", "questionnaire/persona_b_savings_first.json",
     lambda o: o["answers"].pop(), "every question"),
    ("a FAR-Trans link to nobody", A,
     lambda o: o["risk_data_link"].update(external_customer_id="0" * 20), "is not a FAR-Trans customer"),
    ("an unlinked persona without a reason", "profiles/persona_d_pending_information.json",
     lambda o: o.pop("risk_data_link_unavailable_reason"), "without a risk_data_link_unavailable_reason"),
    ("the wrong source label", "profiles/persona_b_savings_first.json",
     lambda o: o.update(source="far_trans"), "synthetic_demo"),
    ("an unsupported strategy", "scenarios/strategy_comparisons.json",
     lambda o: o["scenarios"][0]["scenario_b"].update(portfolio_strategy="momentum"), "ScenarioCompareRequest rejects"),
    ("a contribution what-if the simulator cannot express", "scenarios/strategy_comparisons.json",
     lambda o: o["scenarios"][0]["scenario_a"].update(contribution_amount=500), "portfolio_strategy only"),
    ("a scenario for an unknown persona", "scenarios/strategy_comparisons.json",
     lambda o: o["scenarios"][0].update(persona_demo_key="WPDEMO-Z"), "unknown persona"),
    ("a financial number as an expected state", "expected_results/persona_a_approved.json",
     lambda o: o["expected"].update(sharpe_ratio=0.87), "unknown expected-state key"),
    ("an expected member count the data does not have", "expected_results/demo_family.json",
     lambda o: o["expected"].update(member_count=3), "member_count must equal"),
    ("'nothing triggered' for a never-evaluated compliance", "expected_results/persona_d_pending_information.json",
     lambda o: o["expected"].update(triggered_compliance_rules=[]), "not evaluated"),
]


@pytest.mark.parametrize("rel, change, fragment", [d[1:] for d in DEFECTS], ids=[d[0] for d in DEFECTS])
def test_a_planted_defect_is_reported(tmp_path, rel, change, fragment):
    copy = _copy(tmp_path)
    assert _errors(copy) == []
    _edit(copy, rel, change)
    errors = _errors(copy)
    assert any(fragment in e for e in errors), errors


def test_an_answer_off_its_personas_rule_is_reported(tmp_path):
    copy = _copy(tmp_path)
    question = next(q for s in get_questionnaire_sections() for q in s["questions"] if len(q["options"]) > 2)
    other = select_option(question["options"], -1)            # a real option, but not persona A's (the first)

    def change(obj):
        next(a for a in obj["answers"] if a["question_number"] == question["number"])["option_key"] = other

    _edit(copy, "questionnaire/persona_a_approved.json", change)
    assert any("selection rule" in e for e in _errors(copy))


def test_a_persona_in_two_households_is_reported(tmp_path):
    copy = _copy(tmp_path)
    second = {"demo_key": "WPDEMO-FAM2", "source": "synthetic_demo", "household_name": "Another household",
              "primary_demo_key": "WPDEMO-C"}
    (copy / "household/households/second.json").write_text(canonical_json(second), encoding="utf-8")
    members = {"household_demo_key": "WPDEMO-FAM2", "source": "synthetic_demo",
               "members": [{"demo_key": "WPDEMO-C", "relationship": "self", "role": "primary"}]}
    (copy / "household/members/second.json").write_text(canonical_json(members), encoding="utf-8")
    write_manifest(copy, REPO_ROOT)
    assert any("also in household" in e for e in _errors(copy))


def test_an_edit_without_regenerating_the_manifest_is_reported(tmp_path):
    copy = _copy(tmp_path)
    _edit(copy, "household/income/demo_family.json", lambda o: o["records"][0].update(amount=2801),
          regenerate_manifest=False)
    errors = _errors(copy)
    assert any("sha256 of household/income/demo_family.json differs" in e for e in errors), errors


def test_an_unlisted_file_is_reported(tmp_path):
    copy = _copy(tmp_path)
    extra = {"source": "synthetic_demo", "scenarios": []}
    (copy / "scenarios/extra.json").write_text(canonical_json(extra), encoding="utf-8")
    assert any("scenarios/extra.json is not listed in the manifest" in e for e in _errors(copy))


def test_a_non_canonical_file_is_reported(tmp_path):
    copy = _copy(tmp_path)
    obj = read_json(copy / A)
    (copy / A).write_text(json.dumps(obj, indent=4), encoding="utf-8")
    write_manifest(copy, REPO_ROOT)
    assert any("canonical format" in e for e in _errors(copy))


def test_the_manifest_is_never_written_for_invalid_data(tmp_path, capsys):
    copy = _copy(tmp_path)
    _edit(copy, MEMBERS, lambda o: o["members"][1].update(demo_key="WPDEMO-Z"), regenerate_manifest=False)
    before = (copy / "manifest.json").read_bytes()
    assert main(["--write-manifest", "--data-dir", str(copy)]) == 1
    assert "NOT WRITING THE MANIFEST" in capsys.readouterr().out
    assert (copy / "manifest.json").read_bytes() == before


def test_the_validator_exits_nonzero_on_failure(tmp_path, capsys):
    copy = _copy(tmp_path)
    _edit(copy, A, lambda o: o["profile"].update(risk_category="Aggressive"))
    assert main(["--data-dir", str(copy)]) == 1
    assert "DEMO DATA INVALID" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Separation from the training data
# ---------------------------------------------------------------------------


def test_a_changed_raw_training_file_is_detected(tmp_path):
    raw = tmp_path / "datasets" / "raw" / "FAR-Trans"
    raw.mkdir(parents=True)
    (raw / "transactions.csv").write_text("customerID,amount\nX,1\n", encoding="utf-8")
    guard = {k: v for k, v in build_manifest(DEMO_DATA_DIR, tmp_path)["training_data_guard"].items()}
    assert list(guard) == ["datasets/raw/FAR-Trans/transactions.csv"]
    assert check_training_data_guard(guard, tmp_path) == ([], [])
    (raw / "transactions.csv").write_text("customerID,amount\nX,2\n", encoding="utf-8")
    errors, _ = check_training_data_guard(guard, tmp_path)
    assert errors and "must never be modified" in errors[0]


def test_a_raw_file_absent_from_the_checkout_is_noted_not_failed(tmp_path):
    errors, notes = check_training_data_guard({"datasets/raw/kaggle/x.csv": "0" * 64}, tmp_path)
    assert errors == [] and "not present in this checkout" in notes[0]


def test_the_reference_check_finds_the_dataset_but_not_the_seed_script_name():
    assert DEMO_DATA_REFERENCE.search("pd.read_json('demo_data/profiles/a.json')")
    assert DEMO_DATA_REFERENCE.search("from demo_data_package import load_personas")
    assert not DEMO_DATA_REFERENCE.search("see backend/scripts/seed_demo_data.py")
