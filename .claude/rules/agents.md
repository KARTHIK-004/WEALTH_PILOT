# Agent Rules

Quick-reference for `backend/wealthpilot/agents/`. Full detail:
`docs/RULES.md` Rules 14-17, `docs/ARCHITECTURE.md` §10-12,
`docs/DECISIONS.md` ADR-011/012/013/015/016/018.

- `agents/nodes.py` functions are pure `(AgentState, ...explicit deps) ->
  AgentStateDelta`. No node mutates `state` in place, trains/retrains a
  model, calls an LLM directly, or implements graph routing itself.
- `agents/state.py::apply_delta` is the ONLY sanctioned way to combine a
  state with a node's delta — always returns a new `AgentState`, never
  mutates the original. `blocked`/`block_reason` are derived from
  `compliance_result`, never independently settable by a node.
- `agents/graph.py` wires nodes together and routes between them; it
  contains no financial/ML logic of its own. Per-run dependencies (DB
  session, `GoalAssumptions`, `historical_returns`, portfolio strategy)
  are threaded through `GraphDependencies`, never bolted onto
  `AgentState`.
- `_safe_call` converts any unexpected node exception into a structured
  `processing_failure` — never let the graph continue silently as if a
  failed node had succeeded.
- Gemini (`agents/explanation.py`) and AutoGen (`agents/debate.py`) never
  calculate a number, select a strategy, or override compliance. Both
  receive already-computed data and have their structured output
  validated against it, falling back to a templated restatement on any
  mismatch or failure — never a fabricated number.
- No chain-of-thought, prompt, or transcript is ever added to
  `NodeEvent`/the SSE stream — there is no field for it; do not add one.
- Compliance is a veto no agent can override: `enforce_gate` raises on
  REJECT, and nothing catches it. `agents/recommendation.py`/
  `agents/explanation.py` are only invoked when
  `overall_status == "approved"`.
- Recommendation precedence — Compliance > Savings-first > Risk > Goal >
  Market — is fixed; no agent or node reorders it.
