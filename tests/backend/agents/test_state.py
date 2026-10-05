"""AgentState/AgentStateDelta: validation, serialization, round-trip,
immutability, error accumulation, no-hidden-reasoning, and the
compliance-derived blocked/block_reason contract."""

import json

import pytest

from wealthpilot.agents.state import (
    AgentState,
    AgentStateDelta,
    CustomerProfile,
    NodeError,
    RiskAssessmentResult,
    apply_delta,
)
from wealthpilot.core.compliance import ComplianceProposal, evaluate_compliance


def test_agent_state_requires_customer_id():
    with pytest.raises(Exception):
        AgentState()  # missing required field


def test_agent_state_defaults_are_all_none_or_empty():
    state = AgentState(customer_id=1)
    assert state.customer_profile is None
    assert state.risk_assessment is None
    assert state.financial_health is None
    assert state.goal_results is None
    assert state.emergency_fund is None
    assert state.market_analysis is None
    assert state.portfolio_result is None
    assert state.compliance_result is None
    assert state.blocked is False
    assert state.block_reason is None
    assert state.errors == []


def test_agent_state_is_json_serializable():
    state = AgentState(customer_id=1, risk_assessment=RiskAssessmentResult(risk_category="Balanced", model_version="v1", data_source="models/risk"))
    payload = json.loads(state.model_dump_json())
    assert payload["customer_id"] == 1
    assert payload["risk_assessment"]["risk_category"] == "Balanced"


def test_agent_state_round_trips_through_json():
    state = AgentState(customer_id=42, risk_assessment=RiskAssessmentResult(risk_category="Aggressive", model_version="v1", data_source="models/risk"))
    restored = AgentState.model_validate_json(state.model_dump_json())
    assert restored == state


# --- no hidden chain-of-thought -----------------------------------------


def test_no_state_model_has_a_chain_of_thought_field():
    from wealthpilot import agents

    forbidden = {"reasoning", "chain_of_thought", "hidden_thoughts", "internal_reasoning", "scratchpad_reasoning", "scratchpad", "private_reasoning"}
    for model_cls in (AgentState, AgentStateDelta, CustomerProfile, RiskAssessmentResult, NodeError):
        field_names = {f.lower() for f in model_cls.model_fields}
        overlap = field_names & forbidden
        assert not overlap, f"{model_cls.__name__} has forbidden field(s): {overlap}"


# --- immutability / update isolation --------------------------------------


def test_apply_delta_returns_a_new_object_never_mutates_original():
    state = AgentState(customer_id=1)
    delta = AgentStateDelta(risk_assessment=RiskAssessmentResult(risk_category="Balanced", model_version="v1", data_source="models/risk"))
    new_state = apply_delta(state, delta)
    assert new_state is not state
    assert state.risk_assessment is None  # original untouched
    assert new_state.risk_assessment.risk_category == "Balanced"


def test_apply_delta_preserves_fields_the_delta_does_not_touch():
    state = AgentState(customer_id=1, risk_assessment=RiskAssessmentResult(risk_category="Balanced", model_version="v1", data_source="models/risk"))
    delta = AgentStateDelta(financial_health=None)  # touches nothing
    new_state = apply_delta(state, delta)
    assert new_state.risk_assessment.risk_category == "Balanced"


def test_apply_delta_never_silently_replaces_a_valid_result_with_none():
    state = AgentState(customer_id=1, risk_assessment=RiskAssessmentResult(risk_category="Balanced", model_version="v1", data_source="models/risk"))
    empty_delta = AgentStateDelta()
    new_state = apply_delta(state, empty_delta)
    assert new_state.risk_assessment is not None
    assert new_state.risk_assessment.risk_category == "Balanced"


def test_apply_delta_updates_only_the_fields_the_delta_owns():
    state = AgentState(customer_id=1)
    delta = AgentStateDelta(risk_assessment=RiskAssessmentResult(risk_category="Income", model_version="v1", data_source="models/risk"))
    new_state = apply_delta(state, delta)
    assert new_state.financial_health is None
    assert new_state.goal_results is None
    assert new_state.customer_id == 1


def test_errors_accumulate_across_multiple_deltas():
    state = AgentState(customer_id=1)
    state = apply_delta(state, AgentStateDelta(new_errors=[NodeError(node_name="a", error_type="missing_data", message="m1")]))
    state = apply_delta(state, AgentStateDelta(new_errors=[NodeError(node_name="b", error_type="validation", message="m2")]))
    assert len(state.errors) == 2
    assert state.errors[0].node_name == "a"
    assert state.errors[1].node_name == "b"


def test_updated_at_changes_on_every_apply_delta():
    state = AgentState(customer_id=1)
    original_updated_at = state.updated_at
    new_state = apply_delta(state, AgentStateDelta())
    assert new_state.updated_at >= original_updated_at


# --- compliance-derived blocked/block_reason ------------------------------


def test_blocked_is_false_by_default():
    state = AgentState(customer_id=1)
    assert state.blocked is False


def test_blocked_becomes_true_when_compliance_result_is_reject():
    state = AgentState(customer_id=1)
    result = evaluate_compliance(ComplianceProposal())  # empty proposal -> REJECT (fail-closed)
    new_state = apply_delta(state, AgentStateDelta(compliance_result=result))
    assert new_state.blocked is True
    assert new_state.block_reason is not None
    assert len(new_state.block_reason) > 0


def test_blocked_is_false_when_compliance_result_is_pass():
    state = AgentState(customer_id=1)
    proposal = ComplianceProposal(risk_level="Balanced", weights={"QQQ": 0.4, "AGG": 0.3, "GLD": 0.3}, emergency_fund_sufficient=True)
    result = evaluate_compliance(proposal)
    assert result.decision == "PASS"
    new_state = apply_delta(state, AgentStateDelta(compliance_result=result))
    assert new_state.blocked is False
    assert new_state.block_reason is None


def test_blocked_transitions_from_reject_back_to_false_on_a_new_pass_result():
    """A later compliance re-evaluation (e.g. after fixing a proposal) must
    correctly un-block state -- blocked always mirrors the LATEST
    compliance_result, not a sticky flag."""
    state = AgentState(customer_id=1)
    reject_result = evaluate_compliance(ComplianceProposal())
    state = apply_delta(state, AgentStateDelta(compliance_result=reject_result))
    assert state.blocked is True

    pass_proposal = ComplianceProposal(risk_level="Balanced", weights={"QQQ": 0.4, "AGG": 0.3, "GLD": 0.3}, emergency_fund_sufficient=True)
    pass_result = evaluate_compliance(pass_proposal)
    state = apply_delta(state, AgentStateDelta(compliance_result=pass_result))
    assert state.blocked is False
    assert state.block_reason is None


def test_blocked_and_block_reason_are_not_fields_on_agent_state_delta():
    """Structural guarantee: a node cannot set blocked/block_reason
    directly -- they only exist on AgentState, derived by apply_delta."""
    assert "blocked" not in AgentStateDelta.model_fields
    assert "block_reason" not in AgentStateDelta.model_fields
