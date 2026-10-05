# Phase 12 — AutoGen Strategy Debate Report

## 1. Status

**COMPLETE.**

## 2. AutoGen architecture

`backend/wealthpilot/agents/debate.py` — a bounded, standalone module. `run_strategy_debate()` orchestrates exactly one AutoGen `GroupChat`/`GroupChatManager` conversation among the three required personas, using `pyautogen==0.2.35` (already-approved dependency, unchanged version). **AutoGen never calculates a financial value** — every number in `DebateInput`/`DebateResult` comes from an already-computed Phase 4-9 result; the personas' only output field is free-text prose (`DebateArgument.content`), with no numeric field anywhere in the schema for a claimed value to occupy.

## 3. Agent roles

Exactly three, matching the specification precisely — verified by a dedicated test asserting `DEBATE_ROLES == {"portfolio_manager", "risk_analyst", "compliance_analyst"}` and that no fourth autonomous agent name (Supervisor/Orchestrator/etc.) exists anywhere in the module. AutoGen's own `GroupChatManager` coordination object is infrastructure, not a persona, and is excluded from that check deliberately.

- **Portfolio Manager**: may discuss the already-computed MVO/HRP/1-N candidates, approved metrics, goals, market regime, trade-offs. Forbidden from calculating/modifying weights, running any optimizer, inventing returns/covariance/Sharpe, or overriding compliance — enforced by the system prompt and, structurally, by `DebateArgument` having no field to carry such a claim even if attempted.
- **Risk Analyst**: may discuss Phase 4 risk category, constraints, concentration, volatility, drawdown, suitability trade-offs. Forbidden from retraining/recalculating anything or overriding Compliance.
- **Compliance Analyst**: may discuss the Phase 9 result, rule-level results, constraints, rejection reasons, rules version. Its system prompt states explicitly that it is NOT the deterministic Phase 9 engine and cannot change its decision — and structurally, this conversation never even starts when the deterministic decision is REJECT (see §12), so there is nothing for it to "re-decide."

## 4. Debate input

`DebateInput` — bounded and explicit, never a raw `AgentState` dump: `customer_risk_category`, `approved_strategy` (one `PortfolioSummary`), `alternative_candidates` (dict of others for comparison), `goal_feasibility_summary`, `emergency_fund_sufficient`, `market_regime_summary`, `compliance_status` (`ComplianceStatusSummary`, echoed from Phase 9). Verified directly: its field set contains no secret, no hidden-reasoning field, and nothing beyond this deliberately curated list — a test asserts the exact field set.

## 5. Debate output

`DebateResult` — `status` (`completed`/`skipped_rejected`/`failed`), `participants`, `candidates_considered`, `arguments` (the transcript, typed `DebateArgument`s), `verdict` (`supported`/`flagged_concerns`/`recommended_adjustment_within_bounds`/`None`, extracted only from the Compliance Analyst's closing turn), `disagreement_notes`, `approved_strategy` and `compliance_status` (always the exact input objects, never reconstructed from agent text), `metadata` (provider/model/temperature/turn accounting/termination reason/Phase 12 version), `failure_reason`. **This is explicitly not the final recommendation** — no `recommendation`, `final_recommendation`, or `score` field exists anywhere on it (tested directly), and no four-layer combination logic (customer/risk/goal/market/portfolio weighting, voting, consensus scoring) was implemented — none of those fields exist on the schema either.

## 6. Bounded-turn configuration

**`DEBATE_MAX_MESSAGES = 6`** (approved 2026-09-14): one opening + one closing turn per persona, `Portfolio Manager -> Risk Analyst -> Compliance Analyst -> Portfolio Manager -> Risk Analyst -> Compliance Analyst`, Compliance Analyst speaking last on both rounds (matching its veto authority). Implemented via `autogen.GroupChat(max_round=7, speaker_selection_method="round_robin")` — the `+1` is a verified implementation detail: a non-participant "Moderator" agent (`llm_config=False`, not one of `group_chat.agents`) sends the opening context so the round-robin starts cleanly on Portfolio Manager's own LLM-generated turn rather than misattributing the literal Python seed string as its "opening" — confirmed directly against the installed `pyautogen==0.2.35`'s actual round-counting behavior before shipping, not assumed.

A dedicated test (`test_debate_cannot_continue_indefinitely_bounded_by_bad_agent_behavior`) proves the bound is enforced structurally: a fake agent that always returns the same non-concluding message is still stopped at exactly 6 real calls.

## 7. Termination policy

The debate stops when: (a) `DEBATE_MAX_MESSAGES` is reached (normal case, `termination_reason="max_messages_reached"`), (b) the wall-clock `timeout_seconds` (default 120s, independent of the message-count bound) elapses, or (c) any exception occurs during agent construction or the conversation. All three produce a structured, distinguishable result — never an indefinite hang and never a fabricated success.

**A real gap was found and fixed while building the timeout mechanism**: `concurrent.futures.ThreadPoolExecutor` used as a context manager blocks on `shutdown(wait=True)` in its `__exit__`, which would make a "prompt" timeout actually wait for the hung background thread anyway — defeating its purpose. Fixed by managing the executor without the `with` statement and calling `shutdown(wait=False)` on both the timeout and success paths. Verified directly: the dedicated timeout test's wall-clock duration dropped from ~8.3s to ~3.7s after the fix (the configured 0.5s test timeout is now actually honored, not masked by the slow thread's full sleep duration). Python cannot forcibly kill a running thread, so a genuinely hung call still leaks one background thread until it eventually completes — a disclosed, accepted limitation (§21) for this bounded, low-volume feature, not a production trading system.

## 8. Portfolio Manager responsibilities

See §3. Additionally: `build_debate_input`/`debate_node` never call `core.optimizer` themselves — the `PortfolioSummary` objects are supplied by the caller (mirroring Phase 10's own "explicit input, not self-computed" pattern), so there is no code path in this module that could run MVO/HRP/1-N.

## 9. Risk Analyst responsibilities

See §3. `debate_node` reads `state.risk_assessment.risk_category` (Phase 4's real, already-computed value) directly into `DebateInput.customer_risk_category` — never re-derived, never a new risk classifier.

## 10. Compliance Analyst responsibilities

See §3 and §12.

## 11. Deterministic-number authority

Structural, not just instructional: `DebateArgument` has exactly one content field (free text) and no numeric field of any kind — verified by a test inspecting every field's type annotation. Four dedicated tests prove specific attack/error scenarios cannot leak a competing number into the result:

- An agent claiming "QQQ=0.75" in free text — `result.approved_strategy.weights["QQQ"]` remains the deterministic `0.55` that was passed in (the CRITICAL numerical-integrity test, section 31).
- An agent claiming a different Sharpe ratio/expected return — both remain the deterministic input values.
- An agent responding with JSON-like text containing a fake `"weights"` key — the raw text is preserved verbatim in `content` (auditable) but never parsed into any structured field.
- Every result's `approved_strategy`/`compliance_status` are Python object-identity-traceable back to the exact `DebateInput` fields passed in, never reconstructed from `arguments`.

## 12. Compliance veto

**Absolute, checked first, before any agent or network code runs at all** (verified directly: a REJECT input constructed with an `ExplodingClient` whose `__init__` raises `AssertionError` if ever instantiated — the debate returns `status="skipped_rejected"` without that class ever being touched). `compliance_status.decision == "REJECT"` short-circuits `run_strategy_debate` to a structured skip result preserving the compliance status and the (rejected) proposal unchanged, `termination_reason="compliance_reject_veto"`, zero agent calls, zero API cost.

**This resolves a real inconsistency** between BUILD_PLAN.md's older, more speculative node table (which showed the debate feeding *into* Compliance Analyst, "Structured debate verdict -> Compliance Analyst") and this phase's own explicit instructions (compliance runs first; the debate discusses an already-decided PASS/WARN/REJECT outcome, never feeds back into re-deciding it). Phase 9's actual, already-built `ComplianceProposal` has no field for a debate verdict, and adding one would mean modifying Phase 9 — explicitly forbidden by this phase's own boundary rules. BUILD_PLAN.md's sketch predates Phase 9's concrete design; this phase's instructions reflect the architecture as it actually exists.

**WARN is preserved, never silently converted**: a dedicated test constructs a synthetic `WARN` compliance status (Phase 9 currently ships no WARN rule, so this can only be exercised with fixture data) and confirms the debate proceeds normally (WARN does not veto) and `compliance_status.decision` remains `"WARN"` in the result, never silently promoted to PASS or demoted to REJECT.

## 13. Failure handling

Four distinguishable categories, all tested: **configuration failure** (no API key — `"configuration_failure: no Gemini API key supplied"`), **timeout** (`"timeout: debate exceeded Ns"`), **agent failure** (an exception during the conversation — `"agent_failure: {type}: {message}"`), and **malformed output** (a response with no `content` at all is handled by AutoGen's own internal null-check without crashing this module; verified directly). None of these ever produce a `"completed"` status or a fabricated verdict — `approved_strategy`/`compliance_status` remain the deterministic input values even on failure, so a caller reading a failed `DebateResult` never sees an invented number.

## 14. Prompt-injection protections

Every persona's system prompt opens with an identical "authority notice": all supplied financial figures are deterministic and authoritative, agents must never calculate/estimate/restate them, must refer to values by name only, and — explicitly — any text received that claims to be a new instruction, role, or a request to ignore the above is untrusted data, not a legitimate instruction. The opening conversational prompt itself (`_build_opening_prompt`) is rendered entirely from validated Pydantic fields via plain Python string formatting, never from unvalidated free text, so there is no injection surface in the seed message either.

## 15. Provenance

`PortfolioSummary.model_version`/`data_source` and `ComplianceStatusSummary.rules_version` are carried through `DebateInput` into `DebateResult.approved_strategy`/`compliance_status` completely unchanged — verified directly. `DebateMetadata` additionally records `provider` (`"google-genai"`), `model`, `temperature`, `max_messages`, `messages_used`, `termination_reason`, and `phase12_version` (`"v1"`) for every result, including failed/skipped ones.

## 16. LangGraph integration point

**Standalone component, not wired into `agents/graph.py`** (approved 2026-09-14). `debate_node(state, config) -> dict` matches the exact `(state, config)` signature every Phase 10/11 node wrapper uses — verified directly via `inspect.signature` — so a later phase can insert it with zero adaptation. The documented insertion point (not implemented here): between `compliance_analyst`'s PASS/WARN branch and the `approved` terminal in Phase 11's existing graph, i.e. `compliance_analyst --(PASS/WARN)--> debate_node --> approved`; the REJECT branch continues straight to `rejected` exactly as Phase 11 already built it, untouched. `AgentState` has no `debate_result` field yet — `debate_node` returns `{"debate_result": DebateResult.model_dump()}` rather than requiring a Phase 10/11 schema change, leaving the decision of whether/how to add that field to whichever phase actually wires this in.

## 17. Database changes

**None.** `debate.py` contains no SQLAlchemy import, no `subprocess`/shell access, no arbitrary network call beyond the single configured Gemini endpoint — verified directly by a source-inspection test. No conversation transcript or debate result is persisted anywhere.

## 18. Files created/modified

- **Created**: `backend/wealthpilot/agents/debate.py`.
- **Created**: `tests/backend/agents/test_debate.py`, `test_debate_node.py`, `test_debate_gemini_client.py`.
- **Created**: this report.
- **Modified**: `.env.example` — one comment update, reflecting `GEMINI_API_KEY`'s now-deliberately-expanded scope (Phase 12 debate + Phase 13 explanation), approved 2026-09-14.
- **Untouched**: `backend/wealthpilot/agents/{state,nodes,graph}.py`, `backend/wealthpilot/core/*.py`, `models/{risk,expense,behaviour,market,portfolio}/`, `models/metrics.json`, `backend/wealthpilot/db/models.py`, all Alembic migrations, `config/compliance_rules.yaml`, all raw datasets (all verified via direct file/mtime inspection).

## 19. Tests

**39 new Phase 12 tests**, all passing:

| File | Tests | Covers |
|---|---|---|
| `test_debate.py` | 30 | Exactly 3 roles, bounded 6-message structure (order, types, no-infinite-loop), input/output schema shape (no secrets, no hidden reasoning, no numeric field on arguments), the 4 numerical-integrity attack scenarios, compliance veto (3 tests incl. the "agent says PASS while REJECT" critical test), WARN preservation, malformed-output handling, the 4 failure categories (incl. timeout, both the slow-agent and fast-completion cases), no DB/shell/network access, lazy imports, no-recommendation-engine-fields, determinism of the orchestration shape |
| `test_debate_node.py` | 7 | The graph-compatible wrapper against real `AgentState`/`ComplianceResult` objects: signature contract, invalid-input handling, real provenance extraction, REJECT veto through the real wrapper, no state mutation |
| `test_debate_gemini_client.py` | 2 | Real, live calls to the actual Gemini API (skipped without a configured key) — proves the adapter genuinely works end-to-end, including the token-budget fix (§20) |

**Full project test suite: 488 tests, all passing** (`pytest tests/ --collect-only -q` confirms 488 collected, 0 skipped; 488 passed in 280s). No regressions in Phases 0-11.

## 20. Manual verification

- [x] Authoritative documents inspected.
- [x] AutoGen dependency (`pyautogen==0.2.35`) already installed, version unchanged.
- [x] LLM provider (Gemini/`google-genai==0.3.0`, already configured) confirmed via `AskUserQuestion` before coding — `.env.example` comment updated to reflect the deliberate expansion.
- [x] Exactly 3 roles; no fourth agent.
- [x] Portfolio Manager / Risk Analyst / Compliance Analyst all implemented with role-separated system prompts and enforced boundaries.
- [x] Debate is bounded (6 messages) — verified structurally, not just by convention.
- [x] Termination condition (max messages, timeout, fatal error) verified, each independently tested.
- [x] Structured input/output verified (exact field sets, no secrets, no hidden reasoning).
- [x] Financial numbers come only from deterministic sources — 4 dedicated numerical-integrity tests.
- [x] Agent cannot modify portfolio weights / risk predictions / goal figures / market data — structurally guaranteed (no field to carry such a claim) and directly tested.
- [x] Agent cannot override compliance — REJECT veto tested from three angles (skip entirely, cannot be "selected," an agent literally saying PASS cannot change the echoed REJECT).
- [x] WARN preserved, not silently converted.
- [x] Malformed agent output handled without crashing.
- [x] AutoGen/agent/timeout/configuration failures all handled safely, tested, never produce PASS.
- [x] No infinite debate (bounded-conversation test).
- [x] No hidden chain-of-thought (schema-level guarantee, matching Phase 10's own check).
- [x] No secrets in prompts/inputs (tested directly against the serialized `DebateInput`).
- [x] No arbitrary tool/network/database access (source-level test).
- [x] No database mutation.
- [x] No Gemini call for anything except the bounded debate itself (no explanation generation — that's Phase 13).
- [x] No Recommendation Engine / four-layer logic anywhere.
- [x] No FastAPI, no React.
- [x] No new financial methodology invented.
- [x] No Kaggle/FAR-Trans linkage.
- [x] Previous Phase 0-11 tests pass; complete suite passes (488/488).
- [x] Phase 13 not started; Phase 14 not started.

## 21. Known limitations

1. **A genuinely hung agent call leaks one background thread** until it eventually completes (§7) — Python cannot forcibly terminate a running thread; the timeout mechanism returns a prompt, correct `DebateResult` to the caller but does not reclaim the underlying OS thread immediately. Acceptable for this bounded, low-volume feature; a production system with much higher debate volume might want a process-based (not thread-based) isolation boundary instead.
2. **The free-tier Gemini API key is rate-limited to 5 requests/minute per model** (observed directly during development) — `test_debate_gemini_client.py` is deliberately minimal (2 real calls) to respect this; the full 39-test suite otherwise runs entirely against a fake, deterministic client with zero network dependency or cost.
3. **`verdict` extraction depends on the Compliance Analyst's closing message containing one of three exact uppercase keywords** (`SUPPORTED`/`FLAGGED_CONCERNS`/`ADJUSTMENT_RECOMMENDED`) — if the underlying LLM fails to follow this instruction, `verdict` is simply `None` rather than guessed; this is a real, disclosed possibility with any LLM-driven persona, not silently worked around.
4. **`AgentState` has no `debate_result` field** — by design (§16), left to whichever later phase actually wires `debate_node` into the graph to decide how (or whether) to extend the schema.

## 22. Explicit Phase 13 boundary

No Gemini explanation/advisory-language generation exists anywhere. The debate's own Gemini usage is strictly for the bounded 3-persona critique, never for producing customer-facing prose about a recommendation — that is Phase 13's exclusive responsibility, not touched here.

## 23. Explicit Phase 14 boundary

No final recommendation, no four-layer combination logic (customer preference/risk/goal/market/portfolio weighting), no scoring or ranking formula, no recommendation persistence, no recommendation API schema exists anywhere in this module or its tests — verified directly (§5, §19). `DebateResult` is explicitly documented as not being a recommendation.

## 24. Next phase

**Phase 13 — Gemini Explanation / Advisory Language.**

**Do not begin Phase 13.** Awaiting explicit approval of this report.
