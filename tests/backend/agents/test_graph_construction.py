"""Graph construction/compilation, node registration, and topology sanity."""

from wealthpilot.agents.graph import (
    NODE_APPROVED,
    NODE_COMPLIANCE_ANALYST,
    NODE_CUSTOMER_ANALYZER,
    NODE_FAILED,
    NODE_FINANCIAL_HEALTH,
    NODE_GOAL_ANALYST,
    NODE_INFORMATION_REQUEST,
    NODE_MARKET_ANALYST,
    NODE_PENDING_INFORMATION,
    NODE_PORTFOLIO_MANAGER,
    NODE_REPROFILE,
    NODE_RISK_ANALYST,
    NODE_SAVINGS_FIRST,
    RISK_CONFIDENCE_THRESHOLD,
    build_analysis_graph,
)
from wealthpilot.agents.state import AgentState


def test_graph_compiles_without_error():
    compiled = build_analysis_graph()
    assert compiled is not None


def test_graph_node_names_do_not_collide_with_state_fields():
    """LangGraph refuses a node name equal to a state key -- verified this
    the hard way while building the graph (financial_health/blocked both
    collided). Regression-guard it explicitly."""
    state_fields = set(AgentState.model_fields.keys())
    node_names = {
        NODE_CUSTOMER_ANALYZER, NODE_RISK_ANALYST, NODE_INFORMATION_REQUEST, NODE_FINANCIAL_HEALTH,
        NODE_REPROFILE, NODE_GOAL_ANALYST, NODE_MARKET_ANALYST, NODE_PORTFOLIO_MANAGER, NODE_SAVINGS_FIRST,
        NODE_COMPLIANCE_ANALYST, NODE_APPROVED, NODE_PENDING_INFORMATION, NODE_FAILED,
    }
    assert node_names.isdisjoint(state_fields)


def test_all_ten_phase10_nodes_are_registered():
    compiled = build_analysis_graph()
    graph_nodes = set(compiled.get_graph().nodes.keys())
    expected = {
        NODE_CUSTOMER_ANALYZER, NODE_RISK_ANALYST, NODE_INFORMATION_REQUEST, NODE_FINANCIAL_HEALTH,
        NODE_REPROFILE, NODE_GOAL_ANALYST, NODE_MARKET_ANALYST, NODE_PORTFOLIO_MANAGER, NODE_SAVINGS_FIRST,
        NODE_COMPLIANCE_ANALYST,
    }
    assert expected <= graph_nodes


def test_terminal_nodes_are_registered():
    compiled = build_analysis_graph()
    graph_nodes = set(compiled.get_graph().nodes.keys())
    assert {"approved", "rejected", NODE_PENDING_INFORMATION, NODE_FAILED} <= graph_nodes


def test_entry_point_is_customer_analyzer():
    compiled = build_analysis_graph()
    graph = compiled.get_graph()
    # LangGraph's synthetic "__start__" node has exactly one outgoing edge -- the entry point.
    start_edges = [e for e in graph.edges if e.source == "__start__"]
    assert len(start_edges) == 1
    assert start_edges[0].target == NODE_CUSTOMER_ANALYZER


def test_risk_confidence_threshold_is_the_approved_value():
    assert RISK_CONFIDENCE_THRESHOLD == 0.50


def test_no_cycle_back_to_financial_health_or_risk_analyst_from_reprofile():
    """Re-profile is a documented ONE-TIME branch (section 40) -- its only
    outgoing edge must go to goal_analyst, never back to financial_health
    or risk_analyst (which would create a real cycle)."""
    compiled = build_analysis_graph()
    graph = compiled.get_graph()
    reprofile_edges = [e for e in graph.edges if e.source == NODE_REPROFILE]
    assert len(reprofile_edges) == 1
    assert reprofile_edges[0].target == NODE_GOAL_ANALYST
