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
    PIPELINE_HOUSEHOLD_KEY,
    REPO_ROOT,
    canonical_json,
    load_family,
    load_personas,
    read_json,
)
from validate_demo_data import (
    DEMO_DATA_REFERENCE,
    GUARD_EXCLUDED_RAW_SOURCES,
    build_manifest,
    check_training_data_guard,
    guarded_raw_files,
    main,
    training_data_hashes,
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
    assert (counts["individual_personas"], counts["households"], counts["household_members"]) == (6, 2, 4)
    assert (counts["monthly_record_sets"], counts["monthly_records"]) == (1, 12)   # only the full-pipeline persona reports months
    questions = len([q for s in get_questionnaire_sections() for q in s["questions"]])
    # Four personas answer every question; the two pending personas (D and the full-pipeline partner F) leave questions 16-25 unanswered.
    assert counts["questionnaire_answers"] == 4 * questions + 2 * (questions - 10)
    assert counts["transactions"] == 0 and manifest["transactions"]["included"] is False


def test_the_manifest_guards_every_raw_training_file():
    raw = REPO_ROOT / "datasets" / "raw"
    if not raw.exists():
        pytest.skip("raw datasets are not present in this checkout")
    present = {p.relative_to(REPO_ROOT).as_posix() for p in raw.rglob("*") if p.is_file() and p.name != ".gitkeep" and p.relative_to(raw).parts[0] not in GUARD_EXCLUDED_RAW_SOURCES}
    guarded = set(read_json(DEMO_DATA_DIR / "manifest.json")["training_data_guard"])
    assert guarded == present                                       # every file in scope is guarded, nothing else is
    assert not any(rel.startswith("datasets/raw/gdelt/") for rel in guarded)


def test_the_guard_boundary_is_explicit_and_every_other_raw_source_is_guarded_by_default(tmp_path):
    assert GUARD_EXCLUDED_RAW_SOURCES == frozenset({"gdelt"})        # widening this is a deliberate, reviewed change
    raw = tmp_path / "datasets" / "raw"
    for rel in ("FAR-Trans/a.csv", "kaggle/dir/b.csv", "some_new_source/c.csv", "gdelt/english_gkg_v1/manifest/manifest.sqlite", "gdelt/english_gkg_v1/manifest/manifest.sqlite-wal", "FAR-Trans/.gitkeep"):
        (raw / rel).parent.mkdir(parents=True, exist_ok=True)
        (raw / rel).write_bytes(rel.encode())
    guarded = training_data_hashes(tmp_path)
    assert sorted(guarded) == ["datasets/raw/FAR-Trans/a.csv", "datasets/raw/kaggle/dir/b.csv", "datasets/raw/some_new_source/c.csv"]    # a NEW raw source is guarded, gdelt is not
    assert [p.relative_to(tmp_path).as_posix() for p in guarded_raw_files(tmp_path)] == sorted(guarded)
    assert training_data_hashes(tmp_path / "missing") == {} and guarded_raw_files(tmp_path / "missing") == []


def test_changing_a_gdelt_working_file_never_trips_the_guard_but_changing_a_guarded_file_does(tmp_path):
    raw = tmp_path / "datasets" / "raw"
    for rel in ("FAR-Trans/a.csv", "gdelt/english_gkg_v1/manifest/manifest.sqlite-wal"):
        (raw / rel).parent.mkdir(parents=True, exist_ok=True)
        (raw / rel).write_bytes(b"v1")
    recorded = training_data_hashes(tmp_path)
    (raw / "gdelt/english_gkg_v1/manifest/manifest.sqlite-wal").write_bytes(b"changed by the sentiment pipeline")      # a legitimate working-area write
    assert check_training_data_guard(recorded, tmp_path) == ([], [])
    (raw / "FAR-Trans/a.csv").write_bytes(b"v2")
    errors, _ = check_training_data_guard(recorded, tmp_path)
    assert errors and "FAR-Trans/a.csv changed" in errors[0]


def test_the_loader_gives_the_seed_its_personas_and_family():
    personas = load_personas()
    assert [p["demo_key"] for p in personas] == ["WPDEMO-A", "WPDEMO-B", "WPDEMO-C", "WPDEMO-D", "WPDEMO-E", "WPDEMO-F"]
    assert [p["owned_by_seed"] for p in personas] == [True, True, True, False, True, True]
    # Only the full-pipeline persona reports months: the others have no such key, never an empty or zero-filled history.
    assert ["monthly_records" in p for p in personas] == [False, False, False, False, True, False]
    assert [r["period"] for r in personas[4]["monthly_records"]][0] == "2025-10" and len(personas[4]["monthly_records"]) == 12
    # An unknown input is absent, never zero: the Compliance persona omits its emergency-fund inputs.
    assert "monthly_essential_expenses" not in personas[2]["financial_inputs"]
    assert "current_liquid_assets" not in personas[2]["financial_inputs"]
    assert personas[0]["questionnaire_complete"] and personas[1]["questionnaire_complete"]
    assert personas[2]["questionnaire_complete"] and not personas[3]["questionnaire_complete"]
    family = load_family()
    assert family["primary_name"] == personas[1]["name"]
    assert [m["name"] for m in family["members"]] == [personas[2]["name"]]  # the primary is the creator, not added
    pipeline = load_family(household_key=PIPELINE_HOUSEHOLD_KEY)
    assert (pipeline["demo_key"], pipeline["primary_name"]) == (PIPELINE_HOUSEHOLD_KEY, personas[4]["name"])   # E is the primary; F (the partner) is the only member added
    assert [(m["name"], m["relationship"], m["role"]) for m in pipeline["members"]] == [(personas[5]["name"], "spouse", "member")]
    assert set(pipeline["record_keys"]) == {"income", "expenses", "assets", "liabilities", "goals"} and all(pipeline[r] for r in pipeline["record_keys"])


def test_every_answer_is_a_real_option_of_its_question():
    questions = {q["number"]: q for s in get_questionnaire_sections() for q in s["questions"]}
    for persona in load_personas():
        for answer in persona["answers"]:
            assert answer["option_key"] in {o["key"] for o in questions[answer["question_number"]]["options"]}
        answered = {a["question_number"] for a in persona["answers"]}
        if persona["questionnaire_complete"]:
            assert answered == set(questions)
        else:
            assert persona["demo_key"] in ("WPDEMO-D", "WPDEMO-F") and answered == set(range(1, 16))


# ---------------------------------------------------------------------------
# Planted defects -- each must be reported
# ---------------------------------------------------------------------------

MR = "monthly_records/persona_e_full_pipeline.json"

DEFECTS = [
    ("a skipped reported month", MR, lambda o: o["records"].pop(3), "must be consecutive"),
    ("a repeated reported month", MR, lambda o: o["records"][1].update(period=o["records"][0]["period"]), "must be consecutive"),
    ("spending beyond income in a month", MR, lambda o: o["records"][0].update(expenses=90000), "exceed income"),
    ("an invented monthly field", MR, lambda o: o["records"][0].update(notes="x"), "not a MonthlyRecordUpdate field"),
    ("a negative monthly amount", MR, lambda o: o["records"][0].update(income=-1), "MonthlyRecordUpdate rejects"),
    ("a missing amount zero-filled by omission", MR, lambda o: o["records"][0].update(savings=None), "every amount is reported"),
    ("a month that is not YYYY-MM", MR, lambda o: o["records"][0].update(period="Oct 2025"), "must look like YYYY-MM"),
    ("too few months for the behaviour findings", MR, lambda o: o.update(records=o["records"][:2]), "at least 3 reported months"),
    ("months for an unknown persona", MR, lambda o: o.update(demo_key="WPDEMO-Z"), "is not a persona"),
    ("income that contradicts the persona", MR, lambda o: [r.update(income=400000) for r in o["records"]], "does not fit the persona's annual income"),
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
     lambda o: o["answers"].pop(), "marked complete but questions"),
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
    ("an EMI with no matching debt-payment expense", "household/expenses/pipeline_household.json",
     lambda o: o["records"].pop(6), "monthly payments of its liabilities"),
    ("a loan whose payment the expenses do not carry", "household/liabilities/pipeline_household.json",
     lambda o: o["records"][0].update(monthly_payment=12000), "monthly payments of its liabilities"),
    ("a persona in two households", "household/members/pipeline_household.json",
     lambda o: o["members"].append({"demo_key": "WPDEMO-B", "relationship": "other", "role": "member"}), "also in household"),
    ("a member count the pipeline household does not have", "expected_results/pipeline_household.json",
     lambda o: o["expected"].update(member_count=3), "member_count must equal"),
    ("a pipeline household whose primary is not a persona", "household/households/pipeline_household.json",
     lambda o: o.update(primary_demo_key="WPDEMO-Z"), "unknown persona"),
    ("the partner's household income not fitting the members' own incomes", "household/income/pipeline_household.json",
     lambda o: [r.update(amount=r["amount"] * 10) for r in o["records"]], "not consistent with its members"),
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


def test_an_answer_that_is_not_an_option_is_reported(tmp_path):
    copy = _copy(tmp_path)

    def change(obj):
        obj["answers"][0]["option_key"] = "z"

    _edit(copy, "questionnaire/persona_a_approved.json", change)
    assert any("is not an option of question 1" in e for e in _errors(copy))


def test_only_the_pending_persona_may_leave_questions_unanswered(tmp_path):
    copy = _copy(tmp_path)

    def change(obj):
        obj["answers"].pop()
        obj.update(complete=False, unanswered_questions=[25])

    _edit(copy, "questionnaire/persona_a_approved.json", change)
    assert any("only the pending-information persona" in e for e in _errors(copy))


def test_a_pending_questionnaire_marked_complete_is_reported(tmp_path):
    copy = _copy(tmp_path)
    _edit(copy, "questionnaire/persona_d_pending_information.json", lambda o: o.update(complete=True))
    assert any("marked complete but questions" in e for e in _errors(copy))


PLAUSIBILITY_DEFECTS = [
    ("an implausibly low income", "profiles/persona_a_approved.json",
     lambda o: o["profile"].update(income=12000), "outside the plausible range"),
    ("essential spending beyond the income", "financial_inputs/persona_a_approved.json",
     lambda o: o["financial_inputs"].update(monthly_essential_expenses=100000), "not a plausible share"),
    ("a contribution income cannot fund", "financial_inputs/persona_a_approved.json",
     lambda o: o["financial_inputs"].update(contribution_amount=90000), "exceeds what income leaves"),
    ("savings that contradict the insufficient fund", "financial_inputs/persona_b_savings_first.json",
     lambda o: o["financial_inputs"].update(current_liquid_assets=400000), "contradicts its inputs"),
    ("a Compliance persona whose emergency fund is known", "financial_inputs/persona_c_compliance_rejected.json",
     lambda o: o["financial_inputs"].update(monthly_essential_expenses=40000, current_liquid_assets=10000),
     "unknown emergency-fund position"),
    ("a Compliance rejection by a rule that does not exist", "expected_results/persona_c_compliance_rejected.json",
     lambda o: o["expected"].update(triggered_compliance_rules=["invented_rule"]), "not an existing compliance rule"),
    ("a Pending persona with trading history", "profiles/persona_d_pending_information.json",
     lambda o: o.update(risk_data_link={"external_customer_id": "0" * 20}), "expected pending information"),
    ("a placeholder goal name", "individual_goals/persona_b_savings_first.json",
     lambda o: o["goals"][1].update(goal_type="Goal"), "is a placeholder"),
    ("household spending beyond its income", "household/expenses/demo_family.json",
     lambda o: o["records"][0].update(amount=300000), "exceeds recurring income"),
    ("a household with no liquid assets", "household/assets/demo_family.json",
     lambda o: [r.update(is_liquid=False) for r in o["records"]], "no liquid assets"),
]


@pytest.mark.parametrize(("label", "rel", "change", "fragment"), PLAUSIBILITY_DEFECTS,
                         ids=[d[0] for d in PLAUSIBILITY_DEFECTS])
def test_a_plausibility_defect_is_reported(tmp_path, label, rel, change, fragment):
    copy = _copy(tmp_path)
    _edit(copy, rel, change)
    errors = _errors(copy)
    assert any(fragment in e for e in errors), errors


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
