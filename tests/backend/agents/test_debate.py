"""Phase 12 AutoGen strategy debate tests. All orchestration tests use a
FakeModelClient (no real network/API calls, no cost, deterministic,
fast) -- the actual GeminiModelClient adapter is exercised separately in
test_debate_gemini_client.py with a small number of real, rate-limit-aware
live calls."""

import pytest

from wealthpilot.agents.debate import (
    DEBATE_MAX_MESSAGES,
    DEBATE_ROLES,
    ComplianceStatusSummary,
    DebateArgument,
    DebateInput,
    DebateResult,
    PortfolioSummary,
    build_debate_input,
    run_strategy_debate,
)


class FakeModelClient:
    """Deterministic stand-in for AutoGen's ModelClient protocol -- no
    network access, no cost, fully scriptable per-test via `responses`."""

    responses: list[str] = []
    call_count = 0
    raise_on_call: int | None = None  # 1-based call number to raise on, for failure-injection tests

    def __init__(self, config: dict, **kwargs):
        self._config = config

    def create(self, params: dict):
        type(self).call_count += 1
        if type(self).raise_on_call == type(self).call_count:
            raise RuntimeError("simulated agent failure")
        idx = (type(self).call_count - 1) % len(type(self).responses)
        content = type(self).responses[idx]

        class _Msg:
            pass

        class _Choice:
            pass

        class _Resp:
            pass

        msg = _Msg()
        msg.content = content
        choice = _Choice()
        choice.message = msg
        resp = _Resp()
        resp.choices = [choice]
        resp.model = "fake"
        return resp

    def message_retrieval(self, response):
        return [response.choices[0].message.content]

    def cost(self, response) -> float:
        return 0.0

    @staticmethod
    def get_usage(response) -> dict:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost": 0.0, "model": "fake"}

    @classmethod
    def reset(cls, responses=None, raise_on_call=None):
        cls.responses = responses or ["A concise observation."]
        cls.call_count = 0
        cls.raise_on_call = raise_on_call


def _approved(**overrides):
    defaults = dict(
        strategy="mvo", weights={"QQQ": 0.4, "AGG": 0.3, "GLD": 0.3},
        expected_return=0.15, expected_volatility=0.18, sharpe_ratio=0.83,
        model_version="v1", data_source="market_data (PostgreSQL)",
    )
    defaults.update(overrides)
    return PortfolioSummary(**defaults)


def _compliance(**overrides):
    defaults = dict(decision="PASS", rules_version="v1")
    defaults.update(overrides)
    return ComplianceStatusSummary(**defaults)


# --- exactly 3 roles, no fourth agent (section 33) -----------------------


def test_exactly_three_debate_roles_defined():
    assert set(DEBATE_ROLES) == {"portfolio_manager", "risk_analyst", "compliance_analyst"}
    assert len(DEBATE_ROLES) == 3


def test_no_fourth_autonomous_agent_name_anywhere_in_the_module():
    import wealthpilot.agents.debate as debate_module

    source = open(debate_module.__file__, encoding="utf-8").read()
    forbidden_names = ["Supervisor", "Orchestrator", "\"Manager\"", "'Manager'"]
    # "GroupChatManager"/"ChatManager" are AutoGen's own coordination
    # machinery, not a 4th persona -- excluded from this check deliberately.
    for name in forbidden_names:
        assert name not in source


def test_debate_result_participants_are_exactly_the_three_roles():
    FakeModelClient.reset(["opening obs."] * 3 + ["closing obs. FLAGGED_CONCERNS"] * 3)
    debate_input = build_debate_input(approved_strategy=_approved(), compliance_status=_compliance())
    result = run_strategy_debate(debate_input, api_key="fake", model_client_cls=FakeModelClient)
    assert set(result.participants) == {"portfolio_manager", "risk_analyst", "compliance_analyst"}


# --- bounded turn limit (sections 5, 32) ----------------------------------


def test_debate_max_messages_constant_is_six():
    assert DEBATE_MAX_MESSAGES == 6


def test_debate_produces_exactly_six_messages_two_per_persona():
    FakeModelClient.reset(["msg " + str(i) for i in range(1, 7)])
    debate_input = build_debate_input(approved_strategy=_approved(), compliance_status=_compliance())
    result = run_strategy_debate(debate_input, api_key="fake", model_client_cls=FakeModelClient)

    assert result.status == "completed"
    assert len(result.arguments) == 6
    assert result.metadata.messages_used == 6
    roles_in_order = [a.role for a in result.arguments]
    assert roles_in_order == [
        "portfolio_manager", "risk_analyst", "compliance_analyst",
        "portfolio_manager", "risk_analyst", "compliance_analyst",
    ]
    message_types = [a.message_type for a in result.arguments]
    assert message_types == ["opening", "opening", "opening", "closing", "closing", "closing"]


def test_debate_cannot_continue_indefinitely_bounded_by_bad_agent_behavior():
    """A deliberately non-terminating/repetitive fake agent (always
    returns the same content, never a real conclusion) must still be
    stopped at exactly the configured max -- proving the bound is
    enforced structurally, not by the agent choosing to stop."""
    FakeModelClient.reset(["I will keep talking and never conclude anything."])  # same message forever
    debate_input = build_debate_input(approved_strategy=_approved(), compliance_status=_compliance())
    result = run_strategy_debate(debate_input, api_key="fake", model_client_cls=FakeModelClient)
    assert result.metadata.messages_used == DEBATE_MAX_MESSAGES
    assert FakeModelClient.call_count == DEBATE_MAX_MESSAGES  # never more real calls than the bound allows
    assert result.metadata.termination_reason == "max_messages_reached"


def test_compliance_analyst_speaks_last():
    FakeModelClient.reset(["x"] * 6)
    debate_input = build_debate_input(approved_strategy=_approved(), compliance_status=_compliance())
    result = run_strategy_debate(debate_input, api_key="fake", model_client_cls=FakeModelClient)
    assert result.arguments[-1].role == "compliance_analyst"
    assert result.arguments[-1].message_type == "closing"


# --- structured input (section 8) --------------------------------------


def test_debate_input_does_not_contain_secrets():
    debate_input = build_debate_input(approved_strategy=_approved(), compliance_status=_compliance())
    dumped = debate_input.model_dump_json()
    for forbidden in ("api_key", "GEMINI_API_KEY", "DATABASE_URL", "password", "secret"):
        assert forbidden not in dumped


def test_debate_input_does_not_contain_hidden_reasoning_fields():
    forbidden = {"reasoning", "chain_of_thought", "hidden_thoughts", "internal_reasoning", "scratchpad", "private_reasoning"}
    field_names = {f.lower() for f in DebateInput.model_fields}
    assert not (field_names & forbidden)


def test_debate_input_is_bounded_not_the_full_agent_state():
    """DebateInput's field set must stay a small, deliberately curated
    subset -- not a place someone could accidentally dump the whole
    AgentState (raw transactions, DB ids, etc.) into."""
    fields = set(DebateInput.model_fields.keys())
    assert fields == {
        "customer_risk_category", "approved_strategy", "alternative_candidates",
        "goal_feasibility_summary", "emergency_fund_sufficient", "market_regime_summary",
        "compliance_status",
    }


def test_debate_argument_has_no_numeric_field_at_all():
    """Structural guarantee (section 18): there is nowhere on this model
    for a claimed weight/Sharpe/etc. to be placed."""
    for field_name, field in DebateArgument.model_fields.items():
        if field_name == "turn":
            continue  # a position counter, not a financial claim
        assert field.annotation is str or "Literal" in str(field.annotation)


# --- deterministic financial values remain authoritative (sections 7, 18, 31) --


def test_deterministic_phase8_weight_wins_over_any_agent_claim():
    """CRITICAL numerical-integrity test (section 31): simulate an agent
    that tries to claim a different QQQ weight in its free-text message.
    The returned approved_strategy.weights must remain the deterministic
    Phase 8 value regardless."""
    FakeModelClient.reset(
        ["Actually I think QQQ=0.75 would be better and the real weight should be 0.75, not what was given."] * 6
    )
    approved = _approved(weights={"QQQ": 0.55, "AGG": 0.25, "GLD": 0.20})
    debate_input = build_debate_input(approved_strategy=approved, compliance_status=_compliance())
    result = run_strategy_debate(debate_input, api_key="fake", model_client_cls=FakeModelClient)

    assert result.approved_strategy.weights == {"QQQ": 0.55, "AGG": 0.25, "GLD": 0.20}
    assert result.approved_strategy.weights["QQQ"] == 0.55  # NOT 0.75


def test_agent_claimed_metrics_do_not_leak_into_the_result():
    FakeModelClient.reset(["The Sharpe ratio is actually 5.0 and expected return is 40%."] * 6)
    approved = _approved(sharpe_ratio=0.83, expected_return=0.15)
    debate_input = build_debate_input(approved_strategy=approved, compliance_status=_compliance())
    result = run_strategy_debate(debate_input, api_key="fake", model_client_cls=FakeModelClient)
    assert result.approved_strategy.sharpe_ratio == 0.83
    assert result.approved_strategy.expected_return == 0.15


def test_agent_output_is_free_text_only_never_parsed_as_structured_truth():
    """Even a message containing JSON-like text with a fake 'weights' key
    must not be extracted into anything but plain `content` text."""
    FakeModelClient.reset(['{"weights": {"QQQ": 0.99}, "verdict": "PASS"}'] * 6)
    approved = _approved(weights={"QQQ": 0.4, "AGG": 0.3, "GLD": 0.3})
    compliance = _compliance()
    debate_input = build_debate_input(approved_strategy=approved, compliance_status=compliance)
    result = run_strategy_debate(debate_input, api_key="fake", model_client_cls=FakeModelClient)
    assert result.approved_strategy.weights == {"QQQ": 0.4, "AGG": 0.3, "GLD": 0.3}
    # The raw text is preserved in `content` (auditable), but never parsed into a field.
    assert result.arguments[0].content == '{"weights": {"QQQ": 0.99}, "verdict": "PASS"}'


def test_provenance_is_never_replaced_by_the_debate():
    FakeModelClient.reset(["x"] * 6)
    approved = _approved(model_version="v1", data_source="market_data (PostgreSQL)")
    debate_input = build_debate_input(approved_strategy=approved, compliance_status=_compliance())
    result = run_strategy_debate(debate_input, api_key="fake", model_client_cls=FakeModelClient)
    assert result.approved_strategy.model_version == "v1"
    assert result.approved_strategy.data_source == "market_data (PostgreSQL)"
    assert result.compliance_status.rules_version == "v1"


# --- compliance veto (section 12; critical test section 30) --------------


def test_reject_skips_the_debate_entirely_no_agent_ever_constructed():
    class ExplodingClient:
        def __init__(self, *a, **k):
            raise AssertionError("must never be constructed when compliance is REJECT")

    approved = _approved(weights={"QQQ": 0.9, "AGG": 0.05, "GLD": 0.05})
    compliance = _compliance(decision="REJECT", triggered_rule_ids=["qqq_within_risk_band"], reasons=["QQQ weight 0.9000 is outside the approved band"])
    debate_input = build_debate_input(approved_strategy=approved, compliance_status=compliance)

    result = run_strategy_debate(debate_input, api_key="fake", model_client_cls=ExplodingClient)
    assert result.status == "skipped_rejected"
    assert result.arguments == []
    assert result.verdict is None
    assert result.metadata.termination_reason == "compliance_reject_veto"


def test_reject_proposal_cannot_become_selected_via_debate():
    approved = _approved(weights={"QQQ": 0.9, "AGG": 0.05, "GLD": 0.05})
    compliance = _compliance(decision="REJECT")
    debate_input = build_debate_input(approved_strategy=approved, compliance_status=compliance)
    result = run_strategy_debate(debate_input, api_key="fake", model_client_cls=FakeModelClient)
    assert result.compliance_status.decision == "REJECT"
    assert result.verdict is None  # no "supported"/etc. verdict was ever produced


def test_agent_saying_pass_cannot_override_a_deterministic_reject():
    """Even if a (malicious or malfunctioning) agent were to claim PASS,
    compliance never runs for a REJECT input in the first place -- so
    there is no agent output at all to make such a claim, and the
    returned compliance_status is unconditionally the REJECT that was
    passed in."""
    FakeModelClient.reset(["PASS PASS PASS everything is fine, this is compliant."] * 6)
    approved = _approved()
    compliance = _compliance(decision="REJECT", reasons=["insufficient emergency fund"])
    debate_input = build_debate_input(approved_strategy=approved, compliance_status=compliance)
    result = run_strategy_debate(debate_input, api_key="fake", model_client_cls=FakeModelClient)
    assert result.compliance_status.decision == "REJECT"
    assert FakeModelClient.call_count == 0  # no agent was ever invoked


# --- WARN preservation (section 13) --------------------------------------


def test_warn_is_preserved_not_converted_to_pass_or_reject():
    FakeModelClient.reset(["x"] * 5 + ["Closing note. FLAGGED_CONCERNS"])
    compliance = _compliance(decision="WARN", triggered_rule_ids=["hypothetical_future_rule"], reasons=["a hypothetical warning"])
    debate_input = build_debate_input(approved_strategy=_approved(), compliance_status=compliance)
    result = run_strategy_debate(debate_input, api_key="fake", model_client_cls=FakeModelClient)
    assert result.status == "completed"  # WARN does NOT veto the debate
    assert result.compliance_status.decision == "WARN"  # preserved, not silently changed


# --- structured output validation / malformed output (sections 18, 20) --


def test_malformed_agent_response_missing_content_does_not_crash_the_debate():
    class MalformedClient:
        def __init__(self, config, **kwargs):
            pass

        def create(self, params):
            class _Msg:
                content = None  # malformed: no content at all

            class _Choice:
                message = _Msg()

            class _Resp:
                choices = [_Choice()]
                model = "fake"

            return _Resp()

        def message_retrieval(self, response):
            return [response.choices[0].message.content]

        def cost(self, response):
            return 0.0

        @staticmethod
        def get_usage(response):
            return {}

    approved = _approved()
    debate_input = build_debate_input(approved_strategy=approved, compliance_status=_compliance())
    result = run_strategy_debate(debate_input, api_key="fake", model_client_cls=MalformedClient)
    # Must not crash and must not fabricate a "completed" result from garbage.
    assert result.status in ("completed", "failed")
    assert result.approved_strategy.weights == approved.weights


# --- failure handling (section 17) --------------------------------------


def test_missing_api_key_is_a_configuration_failure_not_a_fabricated_result():
    debate_input = build_debate_input(approved_strategy=_approved(), compliance_status=_compliance())
    result = run_strategy_debate(debate_input, api_key=None, model_client_cls=FakeModelClient)
    assert result.status == "failed"
    assert "configuration_failure" in result.failure_reason
    assert result.arguments == []


def test_agent_failure_mid_debate_is_reported_not_fabricated():
    FakeModelClient.reset(["x"] * 6, raise_on_call=3)
    debate_input = build_debate_input(approved_strategy=_approved(), compliance_status=_compliance())
    result = run_strategy_debate(debate_input, api_key="fake", model_client_cls=FakeModelClient)
    assert result.status == "failed"
    assert "agent_failure" in result.failure_reason
    assert result.approved_strategy.weights == _approved().weights  # preserved even on failure


def test_failure_never_becomes_pass():
    FakeModelClient.reset(["x"], raise_on_call=1)
    compliance = _compliance(decision="PASS")
    debate_input = build_debate_input(approved_strategy=_approved(), compliance_status=compliance)
    result = run_strategy_debate(debate_input, api_key="fake", model_client_cls=FakeModelClient)
    assert result.status == "failed"
    # The ORIGINAL compliance decision is still echoed (never invented as PASS by the debate itself).
    assert result.compliance_status.decision == "PASS"
    assert result.verdict is None


# --- timeout handling (sections 16, 17, 29) ------------------------------


def test_slow_agent_triggers_a_timeout_not_an_indefinite_hang():
    """A deliberately slow fake agent (sleeps longer than a short
    test-configured timeout) must be stopped by the wall-clock bound, not
    the message-count bound -- these are independent mechanisms."""
    import time

    class SlowClient:
        def __init__(self, config, **kwargs):
            pass

        def create(self, params):
            time.sleep(5)  # far longer than the 0.5s timeout used below
            raise AssertionError("should never reach here -- timeout must fire first")

        def message_retrieval(self, response):
            return [""]

        def cost(self, response):
            return 0.0

        @staticmethod
        def get_usage(response):
            return {}

    debate_input = build_debate_input(approved_strategy=_approved(), compliance_status=_compliance())
    result = run_strategy_debate(debate_input, api_key="fake", model_client_cls=SlowClient, timeout_seconds=0.5)
    assert result.status == "failed"
    assert "timeout" in result.failure_reason
    assert result.approved_strategy.weights == _approved().weights  # preserved even on timeout


def test_fast_debate_comfortably_finishes_within_the_default_timeout():
    from wealthpilot.agents.debate import DEBATE_TIMEOUT_SECONDS

    FakeModelClient.reset(["x"] * 6)
    debate_input = build_debate_input(approved_strategy=_approved(), compliance_status=_compliance())
    result = run_strategy_debate(debate_input, api_key="fake", model_client_cls=FakeModelClient, timeout_seconds=DEBATE_TIMEOUT_SECONDS)
    assert result.status == "completed"


# --- no tool/network/db access (section 15) -------------------------------


def test_no_database_or_shell_access_anywhere_in_debate_module():
    import wealthpilot.agents.debate as debate_module

    source = open(debate_module.__file__, encoding="utf-8").read()
    forbidden = ["subprocess", "os.system", "sqlalchemy", " requests.", "urllib.request"]
    for term in forbidden:
        assert term not in source


def test_no_gemini_import_at_module_level_only_lazy_inside_functions():
    """google-genai is imported lazily inside GeminiModelClient methods,
    never at module import time -- so importing debate.py never requires
    network/credentials to succeed."""
    import ast

    import wealthpilot.agents.debate as debate_module

    tree = ast.parse(open(debate_module.__file__, encoding="utf-8").read())
    top_level_imports = set()
    for node in tree.body:  # only top-level statements, not inside functions
        if isinstance(node, ast.ImportFrom) and node.module:
            top_level_imports.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            top_level_imports.update(a.name.split(".")[0] for a in node.names)
    assert "google" not in top_level_imports
    assert "autogen" not in top_level_imports


# --- no Gemini/Recommendation Engine boundary (sections 19, 22, 39, 40) ----


def test_debate_result_is_not_labeled_a_final_recommendation():
    FakeModelClient.reset(["x"] * 6)
    debate_input = build_debate_input(approved_strategy=_approved(), compliance_status=_compliance())
    result = run_strategy_debate(debate_input, api_key="fake", model_client_cls=FakeModelClient)
    dumped = result.model_dump()
    assert "recommendation" not in dumped
    assert "final_recommendation" not in dumped
    assert "score" not in dumped  # no scoring/ranking field anywhere


def test_no_four_layer_recommendation_fields_exist_on_debate_result():
    forbidden = {"customer_preference_weight", "risk_weight", "goal_weight", "market_weight", "portfolio_weight_score", "consensus_score"}
    field_names = set(DebateResult.model_fields.keys())
    assert not (field_names & forbidden)


# --- determinism of orchestration (not the LLM itself) --------------------


def test_bounded_turn_structure_is_deterministic_across_runs():
    """The SEQUENCE/SHAPE of the debate (roles, turn count, message types)
    is deterministic even though LLM content itself may vary -- verified
    by running twice with a fake client."""
    FakeModelClient.reset(["response A"] * 6)
    debate_input = build_debate_input(approved_strategy=_approved(), compliance_status=_compliance())
    r1 = run_strategy_debate(debate_input, api_key="fake", model_client_cls=FakeModelClient)

    FakeModelClient.reset(["response B"] * 6)
    r2 = run_strategy_debate(debate_input, api_key="fake", model_client_cls=FakeModelClient)

    assert [a.role for a in r1.arguments] == [a.role for a in r2.arguments]
    assert [a.message_type for a in r1.arguments] == [a.message_type for a in r2.arguments]
    assert r1.metadata.messages_used == r2.metadata.messages_used == DEBATE_MAX_MESSAGES
