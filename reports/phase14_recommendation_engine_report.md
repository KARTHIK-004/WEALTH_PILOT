# Phase 14 — Recommendation Engine Report

## 1. Status

**COMPLETE.**

## 2. Exact four-layer rule

Neither `PROJECT_PLAN.md` nor `MASTER_PROMPT.md` nor `BUILD_PLAN.md`
specifies a numeric combination rule for the four layers —
`BUILD_PLAN.md` flags this explicitly, twice, as a deliberate open item
("this must be confirmed with the user at the start of Phase 14 rather
than decided here"; "not specified in any source document... to be
resolved with the user immediately before Phase 14 begins"). Per this
project's standing rule (CLAUDE.md: "if the spec is silent... ask; never
invent financial logic"), implementation was gated behind an explicit
stop-and-ask before any code was written. The user approved the exact
decision contract below on 2026-09-14 and reconfirmed it in the Final
Implementation Prompt; it is implemented **verbatim**, with no invented
weighting, scoring, or formula of any kind:

```text
Layer 1 — Compliance Gate
    Compliance REJECT -> blocked_rejected. No recommendation row.
    No lower layer can override REJECT.

Layer 2 — Emergency Fund / Savings-First
    Emergency fund insufficient OR unavailable -> savings_first.
    Skip normal investment recommendation. Reuse the approved Phase 7/11
    savings-first result. No portfolio re-optimization.

Layer 3 — Risk-Conditioned Base Strategy
    Conservative -> HRP   Income -> HRP
    Balanced     -> 1/N   Aggressive -> MVO
    Selects among already-computed Phase 8 strategies. Does NOT calculate
    new portfolio weights.

Layer 4 — Goal + Market Tactical Preferences
    Goal:   Feasible -> 1/N, At Risk -> MVO, Not Feasible -> MVO
    Market: Trending -> MVO, Range-bound -> 1/N, Volatile -> HRP
    Preferences only. Cannot override the risk-conditioned base strategy.

PRECEDENCE: Compliance > Savings-first > Risk suitability > Goal preference
> Market preference. Risk suitability always wins on conflict.

TIE-BREAKER: risk-conditioned base strategy (no random selection, no LLM
voting, no weighted scoring, no arbitrary percentage weights).

STATUS VOCABULARY: approved / savings_first / blocked_rejected / failed.
```

A direct, structural consequence the implementation makes explicit rather
than leaves implicit: because `RISK_BASE_STRATEGY` is a **total** mapping
(every one of the four risk categories maps to exactly one strategy) and
Layer 4 can never override Layer 3, **the final selected strategy is
always exactly `RISK_BASE_STRATEGY[risk_category]`** — Layer 4 only ever
changes whether the structured rationale records "aligned" or "risk
suitability overrides a conflicting preference," never the strategy
itself. All four worked examples in the Final Implementation Prompt's
section 10 (A-D) and all seven critical examples in section 39 were
verified directly against the implementation before this report was
written, and are now permanent, individually-named regression tests
(`test_critical_example_tests_from_the_prompt`, parametrized over all
seven; the four section-10 examples are duplicates of/subsumed by the
same seven cases and the exhaustive sweep below).

## 3. Compliance precedence

Layer 1, checked **first**, unconditionally, before any other layer —
including when the emergency fund is *also* insufficient at the same time
(`test_reject_wins_over_insufficient_emergency_fund_too` and
`test_reject_and_emergency_fund_states_terminate_before_strategy_selection`
confirm REJECT wins over savings-first). Uses
`core.compliance.ComplianceResult.decision` (Phase 9's own already-computed
verdict) directly — never recomputed, never re-derived. `RecommendationInput`
has **no field of any kind** for an AutoGen debate verdict or
Gemini-generated prose (`test_recommendation_input_has_no_autogen_or_gemini_field`
asserts this structurally) — the same "no schema slot for it to occupy"
safety pattern `agents/debate.py`'s `DebateArgument` and
`agents/explanation.py`'s `ExplanationOutput` already use. A test
constructing the input with extraneous `autogen_verdict="APPROVE_OVERRIDE..."`
/`gemini_says="safe to proceed..."` kwargs confirms Pydantic silently drops
them and the authoritative weights pass through completely unaffected
(section 22's compliance-REJECT test scenario, and safety invariant 7).

## 4. Savings-first precedence

Layer 2, checked immediately after Layer 1. Reuses `state.emergency_fund.
sufficient` (Phase 7's own output, surfaced through Phase 10/11's
`savings_first_node`/`route_after_market`) directly — `is not True` (i.e.
`False` or `None`/unavailable) triggers savings-first, matching
`agents/graph.py::route_after_market`'s already-approved Phase 11 routing
exactly ("covers both False and None/unavailable"). Never recomputed, no
new threshold. No portfolio-optimization call is made at all for a
savings-first case: `build_recommendation_input` only attempts to obtain a
portfolio candidate when compliance is not REJECT **and** the emergency
fund is sufficient **and** the risk category resolves to a known strategy
— verified by `test_build_recommendation_input_skips_portfolio_lookup_when_savings_first`,
which monkeypatches `portfolio_manager_node` to raise if called at all.

## 5. Risk mapping

```text
Conservative -> HRP
Income       -> HRP
Balanced     -> 1/N   ("equal_weight" in this codebase's naming)
Aggressive   -> MVO
```

`RISK_BASE_STRATEGY` in `core/recommendation.py`, copied verbatim from the
approved contract. Uses `state.risk_assessment.risk_category` (Phase 4's
deterministic classification) unmodified. `RISK_LEVEL_QQQ_BANDS`, the 70%
general single-asset cap, and the four risk-category definitions
themselves are never touched — they live in `core.optimizer` and are only
ever consumed (via the existing, unmodified `portfolio_manager_node`) when
a candidate needs to be obtained for a strategy not already in state
(section 12). Verified for all four categories by
`test_each_risk_category_selects_its_approved_base_strategy` and the
exhaustive sweep (section 19).

## 6. Goal mapping

```text
Feasible     -> 1/N
At Risk      -> MVO
Not Feasible -> MVO
```

`GOAL_STRATEGY_PREFERENCE`, copied verbatim. Every available goal's
`feasibility` label (Phase 7's own value, unmodified — the 0.80/0.50
thresholds are never touched) is collected via `[g.feasibility for g in
state.goal_results]`. Because a customer can have multiple goals and the
approved rule only ever speaks of a single "goal feasibility," an
aggregation policy was needed and is documented as exactly that — a
**plumbing** decision, not a financial-logic one, since goal preference
can never change the selected strategy anyway: the **worst (most
conservative)** feasibility across all goals wins, the same
"most-severe-signal-dominates" convention `training/market/regime.py`
already uses (Volatile is checked first because "high volatility...
should dominate the label"). No goal contribution amount, inflation
adjustment, or Monte Carlo probability is recalculated anywhere in this
module. "Not Feasible" never increases risk — proven directly by the
Conservative + Not Feasible + Trending example still resolving to HRP,
not MVO.

## 7. Market mapping

```text
Trending    -> MVO
Range-bound -> 1/N
Volatile    -> HRP
```

`MARKET_STRATEGY_PREFERENCE`, copied verbatim. Uses the **QQQ-specific**
regime label from `state.market_analysis.instruments`
(`_primary_market_regime`, `agents/recommendation.py`) — QQQ is the asset
`RISK_LEVEL_QQQ_BANDS` already privileges as the risk-defining instrument
throughout Phase 8/9, so this reuses an already-established convention
rather than inventing a new cross-instrument blending rule. Only the three
allowed regime labels (`Trending`/`Volatile`/`Range-bound`, confirmed
verbatim against `training/market/regime.py`'s own classifier) are ever
looked up; no new regime is invented, no new forecast is created, and
Phase 6's own finding ("no statistically significant model beat the naive
baseline") is neither claimed against nor overridden — the regime is used
purely as a categorical preference-table lookup.

## 8. Conflict resolution

When goal and/or market preference disagrees with the risk-conditioned
base strategy, the base strategy always wins — goal and market are
"preferences only," structurally incapable of changing
`rationale.risk_based_strategy`, which is the only value ever assigned to
`selected_strategy`. Proven exhaustively: for all 4 risk categories × all
3 goal states × all 3 market regimes (36 combinations,
`test_exhaustive_decision_table_risk_base_always_wins`), plus a wider
4×4×4 sweep including "no signal at all"
(`test_goal_and_market_preferences_can_never_change_the_selected_strategy`),
the selected strategy is always exactly `RISK_BASE_STRATEGY[risk_category]`.

## 9. Tie-breaker

The risk-conditioned base strategy. This is not a runtime "tie-break
algorithm" invoked conditionally — `RISK_BASE_STRATEGY` is a **total**
function of `risk_category` (every category maps to exactly one
strategy), so there is structurally never a tie to break; goal/market
preferences are informational annotations on the rationale, never
candidates in a vote. No random selection, no LLM/AutoGen/Gemini voting,
no weighted scoring, no arbitrary priority score exists anywhere in
`core/recommendation.py` — confirmed by direct code inspection (no `random`
import, no numeric weighting of any preference, no LLM call of any kind in
the module).

## 10. Recommendation status vocabulary

Exactly `approved` / `savings_first` / `blocked_rejected` / `failed` —
`RECOMMENDATION_STATUSES = ("approved", "savings_first", "blocked_rejected",
"failed")`, and `Recommendation.status` is typed as a `Literal` of exactly
these four strings (Pydantic itself rejects any other value). No
alternative status name is used anywhere in the codebase.

## 11. Recommendation schema

`core.recommendation.Recommendation` (Pydantic): `status`, `selected_strategy`,
`weights`, `expected_return`, `expected_volatility`, `sharpe_ratio`,
`risk_category`, `compliance_decision`, `rationale` (structured
`RecommendationRationale`: `risk_based_strategy`, `goal_feasibility_used`,
`goal_preference`, `goal_preference_aligned`, `market_regime_used`,
`market_preference`, `market_preference_aligned`, plain-sentence `reasons`
— this is where goal feasibility / market regime / savings-first framing
are surfaced, per the prompt's "including where applicable" phrasing),
`blocking_reason`, `provenance` (`RecommendationProvenance`:
`phase14_version`, `risk_model_version`, `market_model_version`,
`portfolio_config_version`, `compliance_rules_version`), `data_sources`,
`evaluated_at`. The existing `db.models.Recommendation` SQLAlchemy model
was inspected first and used exactly as-is (section 17) — no duplicate
database model was created; `core.recommendation.Recommendation` is the
in-memory/API-facing Pydantic result, mapped onto the existing SQLAlchemy
row only for the fields that table already has. **No `confidence`
field** — the approved rule defines no confidence score and none is
invented (`test_recommendation_has_no_confidence_field`).

## 12. Portfolio source

`core.recommendation.build_recommendation` **never** calls
`core.optimizer` and never computes a weight — it only ever reads
`candidate.weights`/`expected_return`/`expected_volatility`/`sharpe_ratio`
from the already-supplied `PortfolioCandidate` and assigns them directly,
unchanged, to the result. The orchestration layer
(`agents/recommendation.py::_obtain_portfolio_candidate`) obtains the
already-computed Phase 8 result for the strategy Layer 3 selects by:

1. Reusing `state.portfolio_result` directly when its `strategy` already
   matches — zero further computation, zero DB access.
2. Otherwise, calling the exact same, unmodified
   `agents.nodes.portfolio_manager_node` function again with the correct
   `strategy` argument — the identical mechanism `agents/graph.py`'s own
   `_portfolio_manager` wrapper already uses, with the identical
   unmodified `core.optimizer` formulas, bounds, and risk bands. This is
   necessary because `portfolio_manager_node` defaults to `strategy="mvo"`
   for every customer (Phase 10) — Phase 14's risk-conditioned selection
   is new, so a Conservative/Income/Balanced customer's existing
   `state.portfolio_result` may not already be for the strategy Layer 3
   requires. No new expected-return formula, no new covariance estimate,
   no new bound, and no modified weight is introduced anywhere. Nothing
   is silently substituted: if no already-computed result for the
   selected strategy can be obtained, the engine returns `status="failed"`
   with an explicit `blocking_reason` rather than fabricating one or
   substituting a different strategy (section 15/16).

Verified directly: `test_obtain_portfolio_candidate_reuses_state_result_without_recomputation`
(monkeypatches `portfolio_manager_node` to raise if called — proves the
fast path never touches it) and
`test_obtain_portfolio_candidate_recomputes_for_a_different_strategy`
(against the real dev database's `market_data`, proves the recompute path
returns the correct, different strategy's real weights, not the stale
default). Safety invariant 6 and 12 (section 19) further confirm no
recalculation or re-derivation of return/volatility/Sharpe ever occurs.

## 13. AutoGen role

None in the decision. `RecommendationInput` has no field for a debate
verdict at all (section 3). Phase 12's `agents/debate.py` is untouched by
this phase. If a Phase 12 structured debate result exists elsewhere in the
system, this module simply never reads it — there is no code path by
which it could reach the decision logic, so "AutoGen disagrees ->
deterministic output wins" is true by construction, not by a runtime
comparison.

## 14. Gemini role

None in the decision. Phase 13's `agents/explanation.py` is untouched by
this phase. The Recommendation Engine's decision logic is 100% Python —
no LLM call of any kind exists in `core/recommendation.py` or
`agents/recommendation.py`. The persisted `recommendation` text column
holds a JSON serialization of the structured decision, never hand-written
prose, keeping "Recommendation Engine: structured decision" and "Gemini:
explanation language" strictly separate (Final Implementation Prompt
section 21). Gemini can explain the already-created recommendation later
(a future integration point, not built here).

## 15. Numerical authority

Portfolio weights/return/volatility/Sharpe pass through
`build_recommendation` completely unchanged — the function only ever
reads `candidate.weights` and assigns it directly to
`Recommendation.weights`, with no arithmetic performed on it anywhere.
Verified by `test_authoritative_weights_pass_through_unchanged_no_recalculation`
and the CRITICAL example in the prompt (QQQ=0.55/AGG=0.30/GLD=0.15 in,
byte-identical out even when a fabricated `autogen_verdict`/`gemini_says`
kwarg claiming QQQ=0.80 is attached to the input — Pydantic drops the
unrecognized field and `build_recommendation` never reads it regardless;
`test_an_attempted_autogen_override_field_is_silently_ignored_and_has_zero_effect`,
safety invariant 7).

## 16. Missing-data handling

- Missing/unavailable risk category → `status="failed"`, never guessed
  (`test_missing_risk_category_fails_safely`,
  `test_unknown_risk_category_fails_safely`).
- Missing/unavailable emergency fund → treated as insufficient →
  `savings_first`, never a false PASS
  (`test_unavailable_emergency_fund_is_treated_as_insufficient`, safety
  invariant 4).
- No goal data → aggregation returns `None`; the recommendation still
  proceeds on risk alone since goal preference can never change the
  outcome (`test_missing_goal_and_market_signals_still_resolves_via_risk_alone`).
- No market data → same as above.
- No already-computed portfolio candidate for the selected strategy →
  `status="failed"` with an explicit `blocking_reason`, never a
  recommendation built from a mismatched or fabricated candidate
  (`test_missing_portfolio_candidate_fails_rather_than_guessing`,
  `test_mismatched_portfolio_candidate_strategy_fails_rather_than_using_the_wrong_one`
  — this last one is the direct "unavailable strategy: do not silently
  substitute" behavior from section 15 of the prompt; no ambiguity was
  found requiring a stop-and-ask here since "fail cleanly, never
  substitute" is exactly what section 15 itself specifies as the safe
  default).
- No compliance result at all (state never reached that stage) →
  `recommendation_engine_node` returns `status="failed"` immediately,
  without touching the database
  (`test_recommendation_engine_node_missing_compliance_result_fails`).

## 17. Persistence

The existing `recommendations` table (SQLAlchemy `Recommendation` in
`db/models.py`, built at Phase 0/1 with this exact phase in mind — its own
docstring already says "model_version is added wherever a row is the
direct output of... the recommendation engine") was inspected first and is
used **exactly as-is** — no migration, no new column:

- `approved` → persisted.
- `savings_first` → persisted only when representable with the existing
  schema (a known `risk_category` — required since the column is `NOT
  NULL`; `portfolio_allocation` set to `{}`, valid JSON, accurately
  representing "no portfolio was computed"). If `risk_category` is
  unavailable, the savings-first result is still returned to the caller
  but **not** persisted, rather than writing a fabricated value into a
  `NOT NULL` column (`test_persist_recommendation_skips_when_risk_category_not_representable`).
- `blocked_rejected` → never persisted, no row at all.
- `failed` → never persisted, no row at all.
- `confidence` → always `NULL` (section 11/29 — never invented).
- `recommendation` (`Text`) → a JSON serialization of the structured
  `Recommendation` object (section 14).
- `model_version` → `"v1"` (`PHASE14_VERSION`). `data_source` → the
  underlying portfolio/goal data source string(s) (section 18).
- No idempotency key was invented (none specified); a plain
  `session.add()` + `session.flush()` per call, no new uniqueness
  constraint added.
- `persist_recommendation` flushes but never commits — the caller owns the
  transaction boundary, matching every other DB-touching function in this
  project.

The existing model already correctly represents both `approved` and
`savings_first` results with no gaps, so no schema-change stop-and-ask was
triggered.

Verified with a rollback-safe `TEST_DATABASE_URL` session
(`tests/backend/conftest.py`'s existing `db_session` fixture — the same
one `tests/backend/db/test_models.py` already uses) across all status
outcomes; confirmed directly after the full test run that zero rows were
left behind in either `TEST_DATABASE_URL` or the real dev `DATABASE_URL`.

## 18. Provenance

Every `Recommendation` carries `provenance.phase14_version`,
`risk_model_version` (from `state.risk_assessment.model_version`),
`market_model_version` (from `state.market_analysis.model_version`),
`portfolio_config_version` (from the portfolio candidate's
`config_version`), and `compliance_rules_version` (from
`state.compliance_result.rules_version`) — the underlying Phase 4/6/8/9
provenance is preserved, never replaced with a bare "Recommendation
Engine" label. Verified by
`test_provenance_preserves_underlying_component_versions`.

## 19. Safety invariants

Twelve numbered invariant tests, one per item in the Final Implementation
Prompt's section 40, each individually named for direct traceability:

1. REJECT ⇒ no recommendation — `test_invariant_1_reject_implies_no_recommendation`.
2. REJECT ⇒ no persistence — `test_invariant_2_reject_implies_no_persistable_status`
   (status-level proof here; the DB-level proof is
   `test_recommendation_engine_node_rejected_does_not_persist_and_cannot_be_overridden`
   in the node test file).
3. Insufficient EF ⇒ no normal investment recommendation —
   `test_invariant_3_insufficient_ef_implies_no_normal_investment_recommendation`.
4. Unavailable EF ⇒ savings-first —
   `test_invariant_4_unavailable_ef_implies_savings_first`.
5. Final strategy ∈ {MVO, HRP, 1/N} —
   `test_invariant_5_final_strategy_is_always_one_of_the_three_approved_strategies`.
6. Portfolio weights come from Phase 8 —
   `test_invariant_6_portfolio_weights_come_from_the_supplied_phase_8_candidate`.
7. Weights are not changed by AutoGen/Gemini —
   `test_invariant_7_weights_are_not_changed_by_an_attempted_autogen_or_gemini_claim`.
8. Risk category comes from Phase 4 —
   `test_invariant_8_risk_category_comes_from_the_supplied_phase_4_value`.
9. Goal feasibility comes from Phase 7 —
   `test_invariant_9_goal_feasibility_used_comes_from_the_supplied_phase_7_values`.
10. Market regime comes from Phase 6 —
    `test_invariant_10_market_regime_used_comes_from_the_supplied_phase_6_value`.
11. Final decision is deterministic —
    `test_invariant_11_final_decision_is_deterministic` (5× identical
    output from identical input).
12. No new financial calculations occur —
    `test_invariant_12_no_new_financial_calculations_occur` (a
    deliberately internally-inconsistent candidate — weights not summing
    to a sane portfolio, mismatched return/volatility/Sharpe — passes
    through completely unvalidated/unrecomputed, proving nothing is
    re-derived from the weights).

## 20. Tests

**95 tests** in `tests/backend/core/test_recommendation.py` (pure engine
logic — no DB, no LLM) plus **20 tests** in
`tests/backend/agents/test_recommendation_node.py` (orchestration/
persistence), **115 new tests total**, all passing:

- Status vocabulary and no-confidence-field structural checks.
- Layer 1: REJECT blocks everything, REJECT beats simultaneous
  savings-first, PASS/WARN both proceed normally.
- Layer 2: insufficient/unavailable EF → `savings_first`, never touches
  the portfolio candidate.
- Layer 3: all four risk categories individually, unknown/missing risk
  category fails safely.
- Layer 4: the exact approved worked example, strongest alignment,
  weakest alignment/all-conflict, mixed signals, missing goal/market
  signals, per-table parametrized sweeps of every goal/market preference
  value.
- The exhaustive 4×3×3 = 36-combination decision table
  (`test_exhaustive_decision_table_risk_base_always_wins`) plus a wider
  4×4×4 sweep including "no signal."
- REJECT / insufficient-EF / unavailable-EF all individually proven to
  terminate before Layer 3/4 even runs, alongside a fully valid
  risk/goal/market/portfolio-candidate combination supplied at the same
  time.
- All seven critical example tests from the prompt, parametrized,
  verbatim.
- Twelve individually-named safety-invariant tests (section 19).
- Missing/mismatched portfolio candidate → `failed`, never fabricated or
  substituted.
- The CRITICAL numerical-integrity test (authoritative weights unchanged;
  structural AutoGen/Gemini field absence; an attempted override field
  silently ignored with zero effect).
- The CRITICAL determinism test (5× identical output).
- Provenance preservation.
- Orchestration: QQQ-specific regime extraction (including "QQQ absent"
  and "no market analysis" edge cases), portfolio-candidate
  reuse-vs-recompute (one test against the real dev database's live
  `market_data`, proving the recompute path is genuine and correct),
  `build_recommendation_input`'s real-state extraction and its
  skip-the-optimizer-call behavior for REJECT/savings-first cases, DB
  persistence for all status outcomes (approved/savings_first persisted,
  blocked_rejected/failed never persisted, unrepresentable risk_category
  never persisted), full `recommendation_engine_node` end-to-end
  (type-checking, missing-compliance-result failure,
  approved/savings_first persistence, REJECT-cannot-be-overridden-even-
  with-a-valid-candidate, non-mutation of the input state).

Full-suite results:

```text
tests/backend/core/test_recommendation.py                                 95 passed
tests/backend/agents/test_recommendation_node.py                          20 passed
tests/  (entire project, all phases)                                     656 passed, 3 skipped, 0 failed
```

The 3 skips are the pre-existing, quota-exhaustion-tolerant Phase 12/13
live-Gemini tests (unrelated to this phase). Zero regressions across
Phases 0-13.

**A pre-existing Phase 12/13 test flake was found and fixed during this
phase's own full-suite verification, not silently worked around**: the
first full-suite run after implementing Phase 14 showed `1 failed, 656
passed, 2 skipped` — `tests/backend/agents/test_explanation_gemini_client.py::
test_call_gemini_returns_a_valid_structured_output` failed rather than
skipped. Investigated by re-running the live-Gemini test files in
isolation immediately after (which skipped cleanly) and by inspecting the
`google.genai.errors` module directly: Phase 13's quota-exhaustion skip
guard (added while fixing the same class of issue in the previous
session) only caught `google.genai.errors.ClientError` with `code == 429`
— but the SDK also raises `ServerError` (5xx, e.g. a transient "model
overloaded" response) and `ClientError` with other 4xx codes through the
same `APIError` base class, none of which the narrower check caught. This
is a genuine, previously-undiscovered gap in Phase 13's own fix (not a
Phase 14 defect), surfaced only by this phase's heavier volume of
full-suite runs. Fixed by widening both `test_debate_gemini_client.py`'s
and `test_explanation_gemini_client.py`'s `_skip_on_quota_exhaustion`
helper to catch any `google.genai.errors.APIError`, not just a 429
`ClientError` — re-verified with another full-suite run afterward (656
passed, 3 skipped, 0 failed, confirmed above). A genuine code-side
exception (an assertion failure, a `TypeError`/`ValidationError` from this
project's own code) is not a `google.genai.errors.APIError` and still
fails the suite normally; only the external-API-had-a-bad-moment class of
failure is now skipped.

## 21. Manual verification

Completed against the Final Implementation Prompt's 32-item checklist:

- [x] Exact approved four-layer rule implemented (section 2).
- [x] No invented scoring formula (section 9 — no weighting/voting/random
  code exists anywhere in the module).
- [x] Compliance is absolute gate (section 3).
- [x] REJECT produces `blocked_rejected` (invariant 1).
- [x] REJECT does not produce a recommendation (invariant 1).
- [x] REJECT is not persisted (invariant 2, and the node-level DB test).
- [x] Savings-first works (section 4, invariant 3).
- [x] EF unavailable → savings-first (invariant 4).
- [x] Risk mapping exact (section 5, copied verbatim).
- [x] Goal mapping exact (section 6, copied verbatim).
- [x] Market mapping exact (section 7, copied verbatim).
- [x] Risk wins conflicts (section 8, exhaustive 36-combination proof).
- [x] Risk is tie-breaker (section 9).
- [x] Only existing Phase 8 strategies selected (section 12 — candidate
  supplied by the caller, never computed inline).
- [x] No new portfolio weights (invariant 6, invariant 12).
- [x] No optimization rerun beyond the one explicitly-justified reuse of
  the existing, unmodified `portfolio_manager_node` (section 12).
- [x] No new financial calculations (invariant 12).
- [x] AutoGen cannot override (section 13, structurally — no field
  exists).
- [x] Gemini cannot override (section 14, structurally — no field
  exists).
- [x] Missing data handled safely (section 16).
- [x] No fabricated FAR-Trans data anywhere in this module.
- [x] No Kaggle/FAR-Trans linkage — this phase does not touch behaviour
  data at all.
- [x] No confidence invented (section 11 — the field does not exist on
  the Pydantic model at all).
- [x] Provenance preserved (section 18).
- [x] Persistence follows the approved rules exactly (section 17).
- [x] No trade execution anywhere in this module.
- [x] No FastAPI (`backend/wealthpilot/api/` unchanged — only the
  pre-existing Phase 0 skeleton exists).
- [x] No React (`frontend/src/` has no files touched this phase).
- [x] Previous Phase 0-13 tests pass (zero regressions — see section 20).
- [x] Full project test suite passes (656 passed, 3 pre-existing skips, 0
  failed).
- [x] Database integrity verified — no schema change, no migration; zero
  test rows left in either `TEST_DATABASE_URL` or the real dev
  `DATABASE_URL`; `models/metrics.json`'s existing 6 top-level keys and
  every `models/<phase>/` directory unchanged; raw dataset file mtimes
  unchanged.
- [x] Phase 15 not started (no FastAPI route, no SSE endpoint, no
  frontend-facing schema exists anywhere in this change).

## 22. Known limitations

- The goal-feasibility aggregation policy (worst-case across a customer's
  goals) is a plumbing choice this phase had to make because the approved
  rule speaks of a single "goal feasibility" while real customers can have
  several goals; it is disclosed as exactly that (not part of the approved
  financial rule) and, because goal preference can never override the
  risk-based strategy, it has zero effect on the actual recommendation —
  only on the rationale text.
- The market-regime signal is QQQ-specific by design (matching the
  project's own existing QQQ-as-risk-defining-asset convention); a
  customer-facing product might reasonably want a blended cross-instrument
  regime signal instead, but that would itself be an invented combination
  formula this phase deliberately avoided introducing without
  specification.
- `agents/recommendation.py` is standalone, not yet wired into
  `agents/graph.py` — consistent with Phase 12/13's precedent (the prompt's
  own section 33 permits staying standalone when the exact integration
  point is not specified, which it was not), but means a full LangGraph
  run does not yet automatically produce a persisted recommendation;
  Phase 15 (or a future graph-integration decision) must call it
  explicitly.
- The persisted `recommendation` column holds structured JSON, not
  human-readable prose — a deliberate choice to avoid this phase
  encroaching on Gemini's explanation role (section 14), but it means
  anything reading that column directly (rather than through Phase 13's
  explanation layer) needs to parse JSON rather than read plain text.

## 23. Phase 15 boundary

No FastAPI routes, SSE endpoint, authentication, REST recommendation
endpoint, RFC 7807 error handling, or frontend-facing schema were
implemented. `backend/wealthpilot/api/` contains only the pre-existing
Phase 0 skeleton (`main.py`, the health router) — nothing from this phase
touches it. No React code was modified. `core.recommendation.build_recommendation`
and `agents.recommendation.recommendation_engine_node` are clean Python
functions Phase 15 can call directly.

## 24. Next phase

Phase 15 — FastAPI. Do not begin Phase 15.

---

## PHASE 14 COMPLETION REPORT

**Status:** COMPLETE

**Exact four-layer rule:** Compliance gate (REJECT → `blocked_rejected`,
final) → Emergency fund/savings-first (insufficient or unavailable →
`savings_first`, final) → Risk-conditioned base strategy (Conservative/
Income → HRP, Balanced → 1/N, Aggressive → MVO) → Goal/market tactical
preferences (informational only, can never override the base strategy).
Implemented verbatim from the approved decision contract; no formula was
invented.

**Compliance:** Checked first, unconditionally; wins over a simultaneous
savings-first trigger; structurally unreachable by AutoGen or Gemini (no
such field exists on the input schema at all).

**Savings-first:** Reuses Phase 7/11's own result; never recomputed; no
portfolio-optimization call is made for a savings-first case.

**Risk mapping:** Conservative → HRP, Income → HRP, Balanced → 1/N,
Aggressive → MVO — copied verbatim; Phase 4's classification and Phase 8's
risk bands/cap are read, never modified.

**Goal mapping:** Feasible → 1/N, At Risk → MVO, Not Feasible → MVO —
copied verbatim; preference only, worst-case aggregated across a
customer's goals when multiple exist.

**Market mapping:** Trending → MVO, Range-bound → 1/N, Volatile → HRP —
copied verbatim; QQQ-specific regime, preference only.

**Conflict resolution:** Risk-conditioned base strategy always wins;
proven exhaustively across all 36 risk×goal×market combinations.

**Tie-breaker:** The risk-conditioned base strategy — structurally the
only possible outcome, since `RISK_BASE_STRATEGY` is a total mapping; no
random/LLM/AutoGen/Gemini tie-breaking exists anywhere.

**Selected strategies:** Always one of `mvo`/`hrp`/`equal_weight`, sourced
from an already-computed Phase 8 result — never recalculated.

**Recommendation status:** Exactly `approved` / `savings_first` /
`blocked_rejected` / `failed` (Pydantic `Literal`-enforced).

**Persistence:** `approved`/`savings_first` only, using the existing
`recommendations` table exactly as-is (no migration, no new column,
`confidence` left `NULL`); `blocked_rejected`/`failed` never persisted.

**AutoGen:** No role in the decision; no field exists for it.

**Gemini:** No role in the decision; no field exists for it; persisted
record is structured JSON, not generated prose.

**Numerical authority:** Portfolio weights/return/volatility/Sharpe pass
through unchanged from the already-computed Phase 8 candidate; a
fabricated/tampered input field has zero effect (verified directly).

**Missing data:** Every genuinely-missing input (risk category, portfolio
candidate, compliance result) produces `status="failed"` with an explicit
`blocking_reason`, never a guess, a silent default, or a false PASS.

**Provenance:** Every result carries the phase-14 version plus the
underlying risk/market/portfolio/compliance component versions — never a
bare "Recommendation Engine" label.

**Files created/modified:** Created `backend/wealthpilot/core/recommendation.py`,
`backend/wealthpilot/agents/recommendation.py`,
`tests/backend/core/test_recommendation.py`,
`tests/backend/agents/test_recommendation_node.py`,
`reports/phase14_recommendation_engine_report.md`. Modified
`tests/backend/agents/test_debate_gemini_client.py` and
`tests/backend/agents/test_explanation_gemini_client.py` (widened their
pre-existing Phase 12/13 quota-exhaustion skip guard from a 429-only
`ClientError` check to any `google.genai.errors.APIError` — see section
20's flake writeup; no other Phase 0-13 file touched).

**Database changes:** None — the existing `recommendations` table is used
as-is.

**Tests:** 115 new tests (95 pure engine + 20 orchestration/persistence),
all passing. Full project suite: 656 passed, 3 pre-existing skips
(unrelated Phase 12/13 quota exhaustion), 0 failed — zero regressions
across Phases 0-13.

**Manual verification:** All 32 items completed (section 21 above).

**Known limitations:** Goal-feasibility aggregation and QQQ-specific
market-regime selection are disclosed plumbing choices, not part of the
approved financial rule, and have no effect on the actual decision.
Standalone (not yet LangGraph-wired). Persisted record is structured
JSON, not prose.

**Phase 15 boundary:** No API routes, no SSE, no frontend-facing schema,
no React changes. Clean Python functions ready for Phase 15 to call.

Next Phase: Phase 15 — FastAPI. Do not begin Phase 15.
