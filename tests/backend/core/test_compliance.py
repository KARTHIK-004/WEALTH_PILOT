"""Phase 9 compliance engine: YAML loading/validation, PASS/WARN/REJECT
aggregation with REJECT dominance, every individual rule, fail-closed
missing-data handling, the binding gate, determinism, serialization,
security (no eval/exec via YAML), and the end-to-end gate contract."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from wealthpilot.core.compliance import (
    ComplianceProposal,
    ComplianceRejectedError,
    DEFAULT_RULES_PATH,
    RuleDefinition,
    RulesConfig,
    enforce_gate,
    evaluate_compliance,
    load_rules,
    rules_summary,
)
from wealthpilot.core.optimizer import GENERAL_SINGLE_ASSET_CAP, RISK_LEVEL_QQQ_BANDS


def _rules_config(rule_dicts, version="test-v1"):
    return RulesConfig.model_validate({"version": version, "rules": rule_dicts})


# --- YAML loading / schema validation ------------------------------------


def test_default_rules_file_loads_successfully():
    rules = load_rules()
    assert rules.version == "v1"
    assert len(rules.rules) == 5


def test_default_rules_file_is_the_real_repo_file():
    assert DEFAULT_RULES_PATH == Path("config/compliance_rules.yaml").resolve() or DEFAULT_RULES_PATH.name == "compliance_rules.yaml"
    assert DEFAULT_RULES_PATH.exists()


def test_rule_ids_are_unique():
    rules = load_rules()
    ids = [r.id for r in rules.rules]
    assert len(ids) == len(set(ids))


def test_all_five_expected_rule_ids_present():
    rules = load_rules()
    ids = {r.id for r in rules.rules}
    assert ids == {
        "weights_sum_to_one",
        "no_negative_weights",
        "qqq_within_risk_band",
        "single_asset_cap",
        "emergency_fund_savings_first",
    }


def test_all_default_rules_are_reject_severity():
    """Approved 2026-09-14: no WARN rule exists yet."""
    rules = load_rules()
    assert all(r.severity == "REJECT" for r in rules.rules)


def test_schema_rejects_unknown_condition():
    with pytest.raises(ValidationError, match="unrecognized condition"):
        RuleDefinition(id="x", description="d", severity="REJECT", condition="not_a_real_rule", message="m")


def test_schema_rejects_invalid_severity():
    with pytest.raises(ValidationError, match="severity must be"):
        RuleDefinition(id="x", description="d", severity="BLOCK", condition="weights_sum_to_one", message="m")


def test_schema_rejects_blank_id():
    with pytest.raises(ValidationError, match="must not be blank"):
        RuleDefinition(id="  ", description="d", severity="REJECT", condition="weights_sum_to_one", message="m")


def test_schema_rejects_duplicate_rule_ids():
    with pytest.raises(ValidationError, match="duplicate rule id"):
        _rules_config(
            [
                {"id": "dup", "description": "d1", "severity": "REJECT", "condition": "weights_sum_to_one", "message": "m1"},
                {"id": "dup", "description": "d2", "severity": "REJECT", "condition": "no_negative_weights", "message": "m2"},
            ]
        )


def test_load_rules_raises_on_empty_file(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="empty or not valid YAML"):
        load_rules(path)


# --- rule version -------------------------------------------------------


def test_compliance_result_records_the_rules_version():
    rules = _rules_config([{"id": "r1", "description": "d", "severity": "REJECT", "condition": "weights_sum_to_one", "message": "m"}], version="v42")
    result = evaluate_compliance(ComplianceProposal(weights={"A": 1.0}), rules)
    assert result.rules_version == "v42"


# --- individual rules: PASS -----------------------------------------------


def test_weights_sum_to_one_passes_for_valid_weights():
    rules = _rules_config([{"id": "r1", "description": "d", "severity": "REJECT", "condition": "weights_sum_to_one", "message": "m"}])
    result = evaluate_compliance(ComplianceProposal(weights={"QQQ": 0.5, "AGG": 0.5}), rules)
    assert result.decision == "PASS"


def test_no_negative_weights_passes_for_all_non_negative():
    rules = _rules_config([{"id": "r1", "description": "d", "severity": "REJECT", "condition": "no_negative_weights", "message": "m"}])
    result = evaluate_compliance(ComplianceProposal(weights={"QQQ": 0.5, "AGG": 0.5}), rules)
    assert result.decision == "PASS"


def test_qqq_within_risk_band_passes_within_bounds():
    rules = _rules_config([{"id": "r1", "description": "d", "severity": "REJECT", "condition": "qqq_within_risk_band", "message": "m"}])
    result = evaluate_compliance(
        ComplianceProposal(risk_level="Balanced", weights={"QQQ": 0.45, "AGG": 0.3, "GLD": 0.25}), rules
    )
    assert result.decision == "PASS"


def test_single_asset_cap_passes_at_or_below_cap():
    rules = _rules_config([{"id": "r1", "description": "d", "severity": "REJECT", "condition": "single_asset_cap", "message": "m"}])
    result = evaluate_compliance(
        ComplianceProposal(weights={"QQQ": GENERAL_SINGLE_ASSET_CAP, "AGG": 0.15, "GLD": 0.15}), rules
    )
    assert result.decision == "PASS"


def test_emergency_fund_rule_passes_when_sufficient():
    rules = _rules_config([{"id": "r1", "description": "d", "severity": "REJECT", "condition": "emergency_fund_savings_first", "message": "m"}])
    result = evaluate_compliance(ComplianceProposal(emergency_fund_sufficient=True), rules)
    assert result.decision == "PASS"


def test_emergency_fund_rule_passes_when_insufficient_but_is_savings_first():
    rules = _rules_config([{"id": "r1", "description": "d", "severity": "REJECT", "condition": "emergency_fund_savings_first", "message": "m"}])
    result = evaluate_compliance(
        ComplianceProposal(emergency_fund_sufficient=False, is_savings_first_recommendation=True), rules
    )
    assert result.decision == "PASS"


# --- individual rules: REJECT ---------------------------------------------


def test_weights_sum_to_one_rejects_underallocated_weights():
    rules = _rules_config([{"id": "r1", "description": "d", "severity": "REJECT", "condition": "weights_sum_to_one", "message": "m"}])
    result = evaluate_compliance(ComplianceProposal(weights={"QQQ": 0.4, "AGG": 0.3}), rules)
    assert result.decision == "REJECT"


def test_no_negative_weights_rejects_a_short_position():
    rules = _rules_config([{"id": "r1", "description": "d", "severity": "REJECT", "condition": "no_negative_weights", "message": "m"}])
    result = evaluate_compliance(ComplianceProposal(weights={"QQQ": 1.2, "AGG": -0.2}), rules)
    assert result.decision == "REJECT"


@pytest.mark.parametrize("risk_level", list(RISK_LEVEL_QQQ_BANDS.keys()))
def test_qqq_within_risk_band_rejects_out_of_band_weight_for_every_risk_level(risk_level):
    rules = _rules_config([{"id": "r1", "description": "d", "severity": "REJECT", "condition": "qqq_within_risk_band", "message": "m"}])
    result = evaluate_compliance(ComplianceProposal(risk_level=risk_level, weights={"QQQ": 1.0, "AGG": 0.0, "GLD": 0.0}), rules)
    assert result.decision == "REJECT"


def test_qqq_within_risk_band_uses_the_general_cap_intersected_bound():
    """Aggressive's nominal 80% ceiling is tightened to 70% by Phase 8's
    general cap -- this rule must reuse that same intersection, not the
    raw (uncapped) 80% band."""
    rules = _rules_config([{"id": "r1", "description": "d", "severity": "REJECT", "condition": "qqq_within_risk_band", "message": "m"}])
    result = evaluate_compliance(
        ComplianceProposal(risk_level="Aggressive", weights={"QQQ": 0.75, "AGG": 0.25, "GLD": 0.0}), rules
    )
    assert result.decision == "REJECT"  # 0.75 is within the nominal 0.55-0.80 band but above the 0.70 cap


def test_single_asset_cap_rejects_above_cap():
    rules = _rules_config([{"id": "r1", "description": "d", "severity": "REJECT", "condition": "single_asset_cap", "message": "m"}])
    result = evaluate_compliance(ComplianceProposal(weights={"QQQ": 0.71, "AGG": 0.15, "GLD": 0.14}), rules)
    assert result.decision == "REJECT"


def test_emergency_fund_rule_rejects_normal_allocation_when_insufficient():
    rules = _rules_config([{"id": "r1", "description": "d", "severity": "REJECT", "condition": "emergency_fund_savings_first", "message": "m"}])
    result = evaluate_compliance(
        ComplianceProposal(emergency_fund_sufficient=False, is_savings_first_recommendation=False), rules
    )
    assert result.decision == "REJECT"


# --- WARN and aggregation ------------------------------------------------


def test_a_warn_rule_alone_produces_warn_not_reject():
    rules = _rules_config([{"id": "r1", "description": "d", "severity": "WARN", "condition": "weights_sum_to_one", "message": "m"}])
    result = evaluate_compliance(ComplianceProposal(weights={"QQQ": 0.4}), rules)
    assert result.decision == "WARN"


def test_reject_dominates_over_warn_regardless_of_rule_order():
    rules = _rules_config(
        [
            {"id": "warn_rule", "description": "d", "severity": "WARN", "condition": "single_asset_cap", "message": "m"},
            {"id": "reject_rule", "description": "d", "severity": "REJECT", "condition": "weights_sum_to_one", "message": "m"},
        ]
    )
    result = evaluate_compliance(ComplianceProposal(weights={"QQQ": 0.9, "AGG": 0.2}), rules)  # both trigger
    assert result.decision == "REJECT"


def test_reject_dominates_even_when_reject_rule_evaluated_first():
    rules = _rules_config(
        [
            {"id": "reject_rule", "description": "d", "severity": "REJECT", "condition": "weights_sum_to_one", "message": "m"},
            {"id": "warn_rule", "description": "d", "severity": "WARN", "condition": "single_asset_cap", "message": "m"},
        ]
    )
    result = evaluate_compliance(ComplianceProposal(weights={"QQQ": 0.9, "AGG": 0.2}), rules)
    assert result.decision == "REJECT"


def test_no_triggered_rules_produces_pass():
    result = evaluate_compliance(ComplianceProposal(risk_level="Balanced", weights={"QQQ": 0.4, "AGG": 0.3, "GLD": 0.3}, emergency_fund_sufficient=True))
    assert result.decision == "PASS"
    assert all(rr.passed for rr in result.rule_results)


def test_multiple_reject_rules_all_reported_individually():
    result = evaluate_compliance(
        ComplianceProposal(risk_level="Conservative", weights={"QQQ": 0.95, "AGG": -0.1, "GLD": 0.15}, emergency_fund_sufficient=True)
    )
    assert result.decision == "REJECT"
    triggered_ids = {rr.rule_id for rr in result.rule_results if rr.triggered}
    assert "weights_sum_to_one" not in triggered_ids  # 0.95-0.1+0.15=1.0, sums fine
    assert "no_negative_weights" in triggered_ids
    assert "qqq_within_risk_band" in triggered_ids
    assert "single_asset_cap" in triggered_ids


# --- fail-closed on missing data ------------------------------------------


def test_missing_weights_rejects_every_weight_dependent_rule():
    result = evaluate_compliance(ComplianceProposal(emergency_fund_sufficient=True))
    assert result.decision == "REJECT"
    weight_rule_ids = {"weights_sum_to_one", "no_negative_weights", "qqq_within_risk_band", "single_asset_cap"}
    triggered = {rr.rule_id for rr in result.rule_results if rr.triggered}
    assert weight_rule_ids <= triggered


def test_missing_emergency_fund_status_rejects():
    result = evaluate_compliance(ComplianceProposal(risk_level="Balanced", weights={"QQQ": 0.4, "AGG": 0.3, "GLD": 0.3}))
    assert result.decision == "REJECT"
    ef_result = next(rr for rr in result.rule_results if rr.rule_id == "emergency_fund_savings_first")
    assert ef_result.triggered
    assert "unavailable" in ef_result.reason


def test_missing_data_never_silently_passes():
    """The single most important fail-closed property: a completely empty
    proposal must REJECT, never PASS."""
    result = evaluate_compliance(ComplianceProposal())
    assert result.decision == "REJECT"


def test_missing_risk_level_rejects_qqq_band_rule():
    result = evaluate_compliance(ComplianceProposal(weights={"QQQ": 0.4, "AGG": 0.3, "GLD": 0.3}, emergency_fund_sufficient=True))
    assert result.decision == "REJECT"
    qqq_result = next(rr for rr in result.rule_results if rr.rule_id == "qqq_within_risk_band")
    assert qqq_result.triggered


# --- invalid input handling ------------------------------------------


def test_unrecognized_risk_level_is_rejected_not_silently_ignored():
    result = evaluate_compliance(
        ComplianceProposal(risk_level="SuperAggressive", weights={"QQQ": 0.5, "AGG": 0.3, "GLD": 0.2}, emergency_fund_sufficient=True)
    )
    assert result.decision == "REJECT"
    qqq_result = next(rr for rr in result.rule_results if rr.rule_id == "qqq_within_risk_band")
    assert "unrecognized risk_level" in qqq_result.reason


# --- compliance does not modify portfolio weights -------------------------


def test_evaluate_compliance_never_mutates_the_proposal_weights():
    original_weights = {"QQQ": 0.9, "AGG": 0.05, "GLD": 0.05}
    proposal = ComplianceProposal(risk_level="Conservative", weights=dict(original_weights), emergency_fund_sufficient=True)
    evaluate_compliance(proposal)
    assert proposal.weights == original_weights  # untouched, even though it REJECTs


# --- determinism -----------------------------------------------------


def test_evaluate_compliance_is_deterministic():
    proposal = ComplianceProposal(risk_level="Balanced", weights={"QQQ": 0.4, "AGG": 0.3, "GLD": 0.3}, emergency_fund_sufficient=True)
    r1 = evaluate_compliance(proposal)
    r2 = evaluate_compliance(proposal)
    assert r1.decision == r2.decision
    assert [rr.rule_id for rr in r1.rule_results] == [rr.rule_id for rr in r2.rule_results]
    assert [rr.triggered for rr in r1.rule_results] == [rr.triggered for rr in r2.rule_results]


# --- serialization -----------------------------------------------------


def test_compliance_result_is_json_serializable_with_no_hidden_reasoning():
    result = evaluate_compliance(
        ComplianceProposal(risk_level="Balanced", weights={"QQQ": 0.4, "AGG": 0.3, "GLD": 0.3}, emergency_fund_sufficient=True)
    )
    payload = result.model_dump()
    assert payload["decision"] == "PASS"
    assert isinstance(payload["rule_results"], list)
    for rr in payload["rule_results"]:
        assert set(rr.keys()) == {"rule_id", "description", "severity", "triggered", "passed", "message", "reason"}
    # JSON round-trip
    json_text = result.model_dump_json()
    assert "PASS" in json_text


# --- binding gate -----------------------------------------------------


def test_enforce_gate_returns_result_unchanged_on_pass():
    result = evaluate_compliance(
        ComplianceProposal(risk_level="Balanced", weights={"QQQ": 0.4, "AGG": 0.3, "GLD": 0.3}, emergency_fund_sufficient=True)
    )
    returned = enforce_gate(result)
    assert returned is result


def test_enforce_gate_returns_result_unchanged_on_warn():
    rules = _rules_config([{"id": "r1", "description": "d", "severity": "WARN", "condition": "single_asset_cap", "message": "m"}])
    result = evaluate_compliance(ComplianceProposal(weights={"QQQ": 0.9, "AGG": 0.1}), rules)
    assert result.decision == "WARN"
    returned = enforce_gate(result)
    assert returned is result


def test_enforce_gate_raises_on_reject():
    result = evaluate_compliance(ComplianceProposal())  # empty -> REJECT
    with pytest.raises(ComplianceRejectedError):
        enforce_gate(result)


def test_rejected_error_carries_the_full_result():
    result = evaluate_compliance(ComplianceProposal())
    try:
        enforce_gate(result)
        pytest.fail("expected ComplianceRejectedError")
    except ComplianceRejectedError as e:
        assert e.result is result
        assert e.result.decision == "REJECT"


# --- end-to-end safety contract: REJECT never reaches "downstream" --------


def _simulate_downstream_explanation(proposal: ComplianceProposal) -> str:
    """Minimal stand-in for what a future explanation/Gemini node would do
    -- proves the GATE, not the (not-yet-built) LangGraph wiring. Phase 10
    is not implemented here; this function exists only inside this test."""
    result = evaluate_compliance(proposal)
    enforce_gate(result)  # <-- the only thing standing between "evaluated" and "explained"
    return f"Explanation generated for decision={result.decision}"


def test_end_to_end_reject_never_reaches_the_explanation_step():
    rejecting_proposal = ComplianceProposal(
        risk_level="Conservative", weights={"QQQ": 1.0, "AGG": 0.0, "GLD": 0.0}, emergency_fund_sufficient=True
    )
    with pytest.raises(ComplianceRejectedError):
        _simulate_downstream_explanation(rejecting_proposal)


def test_end_to_end_pass_reaches_the_explanation_step():
    passing_proposal = ComplianceProposal(
        risk_level="Balanced", weights={"QQQ": 0.4, "AGG": 0.3, "GLD": 0.3}, emergency_fund_sufficient=True
    )
    explanation = _simulate_downstream_explanation(passing_proposal)
    assert "PASS" in explanation


def test_end_to_end_a_caller_cannot_accidentally_bypass_reject_by_ignoring_the_return_value():
    """Even a caller that calls enforce_gate() purely for its side effect
    and discards the return value still gets the exception -- there is no
    code path where a REJECT decision lets execution continue past
    enforce_gate()."""
    rejecting_proposal = ComplianceProposal()
    result = evaluate_compliance(rejecting_proposal)
    reached_past_gate = False
    with pytest.raises(ComplianceRejectedError):
        enforce_gate(result)
        reached_past_gate = True  # pragma: no cover -- must never execute
    assert reached_past_gate is False


# --- security: no eval/exec via YAML --------------------------------------


def test_load_rules_uses_safe_load_and_cannot_execute_arbitrary_python(tmp_path):
    """A YAML payload using the `!!python/object/apply` tag (which
    yaml.load / yaml.unsafe_load WOULD execute) must be refused, not
    silently run, when loaded through this module's loader."""
    malicious = tmp_path / "malicious.yaml"
    malicious.write_text(
        "version: v1\n"
        "rules: !!python/object/apply:os.system ['echo pwned']\n",
        encoding="utf-8",
    )
    with pytest.raises(yaml.YAMLError):
        load_rules(malicious)


def test_malformed_condition_field_cannot_smuggle_a_python_expression():
    with pytest.raises(ValidationError):
        RuleDefinition(
            id="x", description="d", severity="REJECT",
            condition="__import__('os').system('echo pwned')", message="m",
        )


def test_default_rules_yaml_contains_no_python_tags():
    """Static check on the actual repo file: it must be plain, tag-free
    YAML (no `!!python/...` construct anywhere)."""
    text = DEFAULT_RULES_PATH.read_text(encoding="utf-8")
    assert "!!python" not in text


# --- Kaggle/FAR-Trans population separation --------------------------


def test_compliance_proposal_has_no_kaggle_expense_field():
    """Phase 5's Kaggle-only expense-persona clusters must never become a
    compliance input for FAR-Trans customers (deferred synthetic-assembly
    decision) -- verified structurally: ComplianceProposal has no field
    that could carry an expense-cluster/persona value at all."""
    fields = set(ComplianceProposal.model_fields.keys())
    assert fields == {"risk_level", "weights", "emergency_fund_sufficient", "is_savings_first_recommendation"}
    forbidden_substrings = ("expense", "cluster", "persona", "kaggle", "savings_rate")
    for field_name in fields:
        for forbidden in forbidden_substrings:
            assert forbidden not in field_name.lower()


# --- metrics summary -----------------------------------------------------


def test_rules_summary_is_json_safe_and_not_a_fabricated_ml_metric():
    rules = load_rules()
    summary = rules_summary(rules)
    assert summary["version"] == "v1"
    assert summary["n_rules"] == 5
    assert len(summary["rules"]) == 5
    for r in summary["rules"]:
        assert set(r.keys()) == {"id", "severity", "condition"}
    # No fabricated evaluation statistics (accuracy/pass-rate/etc.) --
    # this is a static config summary, not a trained model's metrics.
    assert "accuracy" not in summary
    assert "pass_rate" not in summary
