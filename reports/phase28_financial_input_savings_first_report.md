# Phase 28 — Financial Input & Savings-First Integration

> **Correction added in Phase 29 (this report's body is left intact as the
> historical record).** Phase 29's end-to-end validation found a defect in
> this phase's goal wiring: the Monte Carlo was fed the raw *daily*
> blended-return series but steps in *monthly* periods, so every goal
> showed a spurious 0.0% / "Not Feasible". Statements below that those
> results were "genuinely 'Not Feasible'", "honest", or "not tuned"
> (§9 area, the demo-persona goal descriptions, and the "Known Limitations"
> bullet on goal feasibility) are **superseded** — they described an
> artifact, not a real outcome. Everything else in this report (the
> `financial_inputs` contract, the API, the emergency-fund flow, the
> savings-first and compliance fixes, and the four persona terminal states)
> was re-verified live in Phase 29 and stands. Corrected results and the
> fix: `reports/phase29_final_integration_report.md`, `docs/DECISIONS.md`
> ADR-027.

## 1. Objective

Close the two documented architectural blockers that made a complete,
`approved` recommendation unreachable through the live API — a missing
financial-input data contract (`GoalAssumptions`/emergency-fund inputs
were never suppliable) and a compliance/savings-first interaction gap
(the compliance ruleset had no carve-out for a legitimate savings-first
proposal's absent weights) — using only real user-provided data and the
existing, unmodified Phase 7/8/9/10/14 engines. No financial formula was
invented; no ML model was retrained; no compliance rule, threshold, or
precedence was weakened.

## 2. Dependency Map

Built from a fresh, complete read of `core/goals.py`, `core/compliance.py`,
`core/recommendation.py`, `agents/nodes.py`, `agents/state.py`,
`agents/graph.py`, `api/services/analysis_service.py`, and
`api/schemas.py` — not assumed from memory of prior reports.

| Input | Meaning | Current source (before Phase 28) | Required by | Available? |
|---|---|---|---|---|
| `monthly_essential_expenses` | Monthly recurring essential spending | Nowhere | `core/goals.py::assess_emergency_fund` | **No** — new `financial_inputs.monthly_essential_expenses` |
| `current_liquid_assets` | Cash/cash-equivalent savings on hand | Nowhere | `core/goals.py::assess_emergency_fund` | **No** — new `financial_inputs.current_liquid_assets` |
| `contribution_amount` | Planned periodic investment contribution | Nowhere | `core/goals.py::GoalAssumptions` (no default) | **No** — new `financial_inputs.contribution_amount` |
| `annual_return_rate` | Assumed expected annual return | Nowhere | `core/goals.py::GoalAssumptions` (no default) | **No** — new `financial_inputs.annual_return_rate` |
| `annual_inflation_rate` | Assumed expected annual inflation | Nowhere | `core/goals.py::GoalAssumptions` (no default) | **No** — new `financial_inputs.annual_inflation_rate` |
| `contribution_periods_per_year` | Contribution frequency | Nowhere (Phase 7 itself defaults to 12) | `core/goals.py::GoalAssumptions` (has own default) | **No**, but Phase 7's own default (12) applies when omitted — new `financial_inputs.contribution_periods_per_year`, optional |
| `historical_returns` | Return series for Monte Carlo bootstrap | Real `market_data` table (Phase 6/8), never wired to Goal Analyst | `core/goals.py::run_goal_monte_carlo` | **Yes**, but unwired — now sourced via `agents/nodes.py::load_portfolio_returns` (existing function, renamed public), blended at equal weight across `ASSET_UNIVERSE`; no new data collected |
| `risk_category` | Customer's risk classification | Real, live (`risk_analyst_node` / `models/risk/rf_v1.pkl`) | `compliance.ComplianceProposal.risk_level`, `core/optimizer.py` bounds | Yes — unaffected by this phase |
| `portfolio weights` | Proposed allocation | Real, live IF `portfolio_manager_node` runs; `null` for a savings-first proposal by design | `core/compliance.py` weight-validation rules | Yes when produced; the four weight rules previously fail-closed REJECTed a legitimate `null` (see §8) |
| `is_savings_first_recommendation` | "This proposal is savings-first, not a normal allocation" | Already existed on `ComplianceProposal` (`bool`, default `False`), but not read by the 4 weight rules | `core/compliance.py::_check_emergency_fund_savings_first` (already used it); the 4 weight rules (did not) | Yes, already available — Phase 28 wires it into the 4 weight rules too (see §8) |
| Expense/income data for `expense_persona` | Kaggle-style expense clustering | FAR-Trans has none; Kaggle population is unlinked | `financial_health_node` | **No, and out of scope** — permanently structural, not a Phase 28 concern (financial health behaviour-drift detection is unaffected and unrelated to emergency-fund/goal assumptions) |

## 3. Missing Data Contract (before this phase)

Confirmed by direct inspection, not assumed: `db/models.py`, `api/schemas.py`
(`ProfileCreateRequest`, `GoalCreate`) had no field representing any row
in the table above except `historical_returns` (present as raw market
data, simply never wired to the Goal Analyst). Every one of the five
financial-input numbers was a genuine, previously undocumented-as-fixable
gap — no existing column could supply them without inventing a formula
(e.g. deriving expenses from income) or misusing an unrelated field (e.g.
treating a goal's own `current_savings` as total liquid assets), both
explicitly forbidden.

## 4. New Data Contract

A new table, `financial_inputs` (one row per customer, every field
independently nullable — `NULL` means "not yet provided", never `0`):

```
financial_inputs
  id                              PK
  customer_id                     FK -> customers.id, UNIQUE
  monthly_essential_expenses      NUMERIC(14,2) NULL
  current_liquid_assets           NUMERIC(14,2) NULL
  contribution_amount             NUMERIC(14,2) NULL
  annual_return_rate              NUMERIC(6,4)  NULL
  annual_inflation_rate           NUMERIC(6,4)  NULL
  contribution_periods_per_year   INTEGER       NULL
  created_at, updated_at
```

A dedicated table (not new columns on `customers`), matching the existing
`financial_goals`/`questionnaire_answers` pattern of one table per
Phase-23-style persistence concern.

## 5. Schema Changes

One Alembic migration, `8ef3f9affbe5_add_financial_inputs.py` (revises
`8fed3799c0c5`, the Phase 23 head): creates `financial_inputs` exactly as
above; `downgrade()` drops it. Applied to both `DATABASE_URL` (dev) and
`TEST_DATABASE_URL` (`ALEMBIC_TARGET=test alembic upgrade head`). No
other table or column was touched; `alembic revision --autogenerate`
detected exactly one new table and nothing else, confirming zero
accidental schema drift elsewhere.

## 6. API Changes

`GET /api/profiles/{id}/financial-inputs` — returns
`FinancialInputsResponse` (every field, `customer_id`, `updated_at`);
200 with every value `null` when no row exists yet (never a 404 — "not
yet provided" is a normal state, matching `GET .../questionnaire`'s own
empty-list convention for the same reason).

`PUT /api/profiles/{id}/financial-inputs` — accepts `FinancialInputsUpdate`
(every field optional; the same bounds `core/goals.py`'s own validators
enforce — `ge=0` for amounts, `gt=-1.0` for rates, `gt=0` for periods);
upserts, merging only the fields actually supplied (an omitted field
keeps its current stored value; an explicit `null` clears it) — the same
merge-not-replace semantics `POST .../questionnaire` already established.
404 (RFC 7807) for a nonexistent `profile_id` on both routes. Customer
isolation: every route is scoped by `profile_id` in the path exactly like
every other per-customer route in this API; one customer's financial
inputs are never readable or writable through another customer's id
(verified by test — §13).

A second, minimal, read-only addition was needed to let the frontend find
an already-seeded demo persona by name without hard-coding its id: `GET
/api/profiles/lookup?name=...` — but that was added in the immediately
preceding Live Analysis Flow phase, not this one; it is unchanged here.

## 7. Frontend Changes

One new card, `components/profile/financial-inputs-card.tsx`, added to
the existing Customer Profile page (`pages/profile-page.tsx`) — the
existing "customer-information flow", not a new page or a large new
dashboard. A single form with the six fields above, pre-filled from `GET
.../financial-inputs`, submitting only the fields the user actually typed
via `PUT .../financial-inputs`. React performs only required-field/
numeric-format/obvious-invalid-value validation (mirroring the API's own
bounds); every calculation (emergency-fund sufficiency, shortfall,
required contribution, feasibility, Monte Carlo probability) still
happens exclusively in `core/goals.py`, read back from the next
`GET`/`POST /api/analysis` response. Saving invalidates both the
financial-inputs query and the `["analysis", profileId]` query (see §16
of `reports/post_login_profile_flow_report.md`'s single-source-of-truth
pattern) so every other page reflects the change on next visit, never a
stale cached result.

## 8. Emergency-Fund Flow

`api/services/analysis_service.py`'s new `_build_graph_dependencies`
(replacing the previous bare `GraphDependencies(session=..., portfolio_strategy=...)`
construction) loads the customer's `financial_inputs` row and passes
`monthly_essential_expenses`/`current_liquid_assets` straight through —
each independently, exactly matching `goal_analyst_node`'s own
independent-null-check signature. `core/goals.py::assess_emergency_fund`
is completely unmodified; it still does the actual comparison. Verified
live (customer_id=2, a real FAR-Trans customer): supplying
`monthly_essential_expenses=1000, current_liquid_assets=50000` produces
`required=6000, current=50000, shortfall=0, sufficient=True`; supplying
`monthly_essential_expenses=5000, current_liquid_assets=1000` produces
`required=30000, shortfall=29000, sufficient=False` — the SAME formula,
now genuinely exercised for the first time through the live API.

## 9. Goal Flow

`_build_graph_dependencies` also constructs `core.goals.GoalAssumptions`
— but ONLY when `contribution_amount`, `annual_return_rate`, AND
`annual_inflation_rate` are ALL present (matching `GoalAssumptions`'
own "no field has a default" contract exactly; a partially-filled set
still correctly reports `unavailable_reason`, never a partially-guessed
assumption). `contribution_periods_per_year` is passed through only when
present, letting `GoalAssumptions`' own default (12) apply otherwise —
never re-implemented. `historical_returns` is sourced from the existing,
real `market_data` table via `agents/nodes.py::load_portfolio_returns`
(renamed from `_load_portfolio_returns` — now a second caller reuses it,
so it was made public rather than duplicated), blended at equal weight
across the approved `ASSET_UNIVERSE` (`core.optimizer.equal_weight_portfolio`)
to produce the single period-return series Monte Carlo bootstraps from.
This was the one genuinely judgment-requiring sub-decision in this phase
(no customer-specific portfolio strategy exists yet at the point
`goal_analyst` runs in the graph, so there is no "this customer's own
portfolio" series to use) — resolved by reusing only already-approved
Phase 8 building blocks (the equal-weight strategy and the exact return
matrix `portfolio_manager_node` itself reads), never a new formula.
`core/goals.py` itself — `analyze_goal_funding`, `run_goal_monte_carlo`,
`classify_feasibility` — was not modified at all.

## 10. Savings-First Flow

Two fixes, both narrowly scoped:

1. **`agents/nodes.py::savings_first_node`** previously treated
   `emergency_fund.sufficient is None` (assessment ran, but could not
   confirm sufficiency) as a `missing_data` error, inconsistent with
   `agents/graph.py::route_after_market`'s own already-approved routing
   comment ("`sufficient is None` treated the same, conservative way as
   `sufficient is False`"). Fixed to honor that same reading: `None` now
   produces a valid `PortfolioResult(strategy="savings_first", weights=None,
   ...)` with an honest message ("sufficiency could not be confirmed...
   given conservatively"), distinct from the known-insufficient message
   ("shortfall of $X"). Only `emergency_fund is None` (the node never ran
   at all) remains a genuine error.
2. **`core/compliance.py`**: the four weight-validation rules
   (`weights_sum_to_one`, `no_negative_weights`, `qqq_within_risk_band`,
   `single_asset_cap`) previously fail-closed REJECTed whenever
   `weights is None`, with no exception — including for a legitimate
   savings-first proposal, which by design never has weights. A shared
   `_missing_weights_outcome` helper now returns PASS for the
   `weights is None` case ONLY when `is_savings_first_recommendation` is
   `True`; every other "no weights" case still fails closed exactly as
   before. The moment `weights` IS non-`None`, every rule still validates
   it in full regardless of the flag (verified by test — §13) — a
   savings-first proposal that inconsistently supplied bogus weights
   would still be caught.

Neither fix touches `compliance_rules.yaml`, rule severities, rule ids, or
aggregation/precedence logic — all five rules still exist, unchanged.

## 11. Portfolio Behavior

Unchanged. `core/optimizer.py` and `agents/nodes.py::portfolio_manager_node`
were not modified. For a sufficient emergency fund, `route_after_market`
now genuinely reaches `portfolio_manager_node` (previously always
diverted to `savings_first_node`, since `sufficient` was always `None`)
— the SAME, unmodified MVO/HRP/1-N optimizer now runs for real, live,
for the first time. For an insufficient (or unknown) emergency fund,
`portfolio_manager_node` is correctly never reached — `savings_first_node`
runs instead, exactly as before.

## 12. Compliance Behavior

Preserved in full: all five rules, their severities, their ids, and
REJECT's strict-escalation aggregation (`decision = "REJECT"` the moment
any REJECT-severity rule triggers, never overridden). Fail-closed
behavior for genuinely missing data is completely unchanged — a customer
with NO financial inputs at all still REJECTs via
`emergency_fund_savings_first`, verified live (WealthPilot Demo —
Compliance, deliberately left without financial inputs, still REJECTs —
§13). The only behavioral change is the one described in §10: a
LEGITIMATE savings-first proposal's absent weights are recognized as
expected rather than invalid.

## 13. Recommendation Behavior

`agents/recommendation.py`/`core/recommendation.py` were not modified.
Phase 14's own precedence (Compliance > Savings-first > Risk > Goal >
Market) and four-layer strategy selection are untouched — verified live:
a sufficient-emergency-fund customer's `recommendation.status ==
"approved"` with `selected_strategy == "mvo"` (risk-conditioned, as
designed); an insufficient-but-known-emergency-fund customer's
`recommendation.status == "savings_first"`, `selected_strategy: null`,
with the pre-existing rationale text `"savings_first_required: emergency
fund insufficient or unavailable; normal investment recommendation
deferred (Phase 7/11 result reused, not recomputed)"` — Phase 14's own
already-approved savings-first handling, now genuinely exercised for the
first time.

## Gemini Behavior

`agents/explanation.py` was not modified. Explanation now genuinely runs
for an `approved` result (previously never reached for any customer);
`validation_passed: false` with a templated, non-generative fallback
summary was observed live for both newly-approved demo personas — Phase
13's own pre-existing fallback path (used whenever Gemini's own live
call does not produce a validated structured output, e.g. under quota
pressure), not something this phase added or needed to fix. Gemini
still never calculates a number, selects a strategy, or overrides
compliance — the explanation is a restatement of already-computed
values either way.

## SSE Behavior

Unchanged — `api/sse.py` shares the exact same `PipelineRun.events()`
generator `POST /api/analysis` uses (confirmed by reading the file; no
edit was needed). The event sequence for a now-`approved` run correctly
includes `portfolio_manager` (previously never emitted for any customer)
followed by `recommendation`/`explanation` events, exactly mirroring the
graph's own real execution — never a fabricated event.

## 14. Demo Customer Results (E2E Verification)

Every result below was read directly from a real `POST /api/analysis`
response (via `scripts/seed_demo_data.py setup`, run in-process against
the real dev database — see §17) after adding financial inputs through
the real `PUT /api/profiles/{id}/financial-inputs` endpoint. Full detail
in `reports/demo_dataset_catalog.md`.

| Persona | customer_id | Financial inputs | Status | Compliance | Recommendation |
|---|---|---|---|---|---|
| WealthPilot Demo — Complete | 29098 | Sufficient EF + full GoalAssumptions | **`approved`** | PASS, 0 rules triggered | `approved`, strategy `mvo`, real weights QQQ 55%/GLD 45% |
| WealthPilot Demo — Savings | 29099 | Known-insufficient EF + full GoalAssumptions | **`approved`** | PASS, 0 rules triggered | `savings_first`, weights `null` |
| WealthPilot Demo — Compliance | 29100 | None (deliberately preserved) | **`rejected`** | REJECT, 1 rule (`emergency_fund_savings_first`) | `null` (never computed) |
| WealthPilot Demo Customer | 29096 | Not applicable (no FAR-Trans linkage; graph halts before goal_analyst) | **`pending_information`** | not reached | not reached |

All four of section 26's target states (APPROVED, SAVINGS_FIRST,
BLOCKED_REJECTED, PENDING_INFORMATION) are now genuinely, honestly
represented by a real customer's real pipeline result — none forced,
none hard-coded, none manually inserted into the `recommendations`/
`portfolios` tables.

## 15. Tests

New: `tests/backend/agents/test_financial_inputs_integration.py` (7
tests) — real-data, real-graph verification of every scenario in §14's
table, run against `customer_id=2` (the same real FAR-Trans customer
`test_graph_execution.py` already uses), plus a direct
`core/compliance.py` unit test confirming the savings-first exemption's
boundary (a savings-first proposal that inconsistently supplies invalid
weights is still fully validated, never given a free pass). New:
8 tests in `tests/backend/api/test_profiles.py` for the
`GET`/`PUT /api/profiles/{id}/financial-inputs` endpoints — creation,
retrieval, partial-update-merges-not-replaces, explicit-null-clears,
negative/invalid-rate/invalid-period rejection (422), 404 for a
nonexistent customer, and cross-customer isolation. New: 2 tests in
`tests/backend/api/test_analysis.py` confirming `financial_inputs` is
part of the analysis cache key (`compute_profile_hash` changes when
financial inputs change; a second `POST /api/analysis` after a `PUT
.../financial-inputs` returns a fresh, not stale, `analysis_id`). One
pre-existing test's docstring
(`test_analysis.py`'s module docstring, and its historically-accurate
but now-outdated claim that a real customer could never reach `approved`)
was corrected for accuracy; no test assertion was changed, only prose.

## 16. Regression Tests

`pytest tests/ -v`, run in full isolation (no concurrent process against
either database): **748 passed, 3 skipped, 0 failed, 152 warnings in
939.91s (15:39)**. The 3 skips are the same, pre-existing, live-Gemini
-API-dependent tests (`test_debate_gemini_client.py`×2,
`test_explanation_gemini_client.py`×1) skipped consistently in every
prior phase this project has gone through — unrelated to this phase.

Two earlier, non-final attempts at this same full-suite run each showed
transient failures that did not reproduce: one run (with a concurrent
diagnostic script touching the same database at the time) showed 6
failures, all 6 confirmed to pass cleanly when re-run individually
immediately afterward; a second run showed "server closed the connection
unexpectedly" on 2 adjacent tests (one pre-existing, one new to this
phase), also confirmed clean in isolation. Both are consistent with the
transient, full-suite-duration connection-contention pattern already
documented twice earlier in this project
(`reports/phase25_final_ux_report.md`, `reports/
demo_data_completion_report.md`) — not a logic defect, and not present
in this final, clean, isolated run.

## Frontend Testing

`npx tsc -b`: 0 errors. `npx oxlint`: 0 errors, 8 warnings (identical set
to the pre-phase baseline — none new). `npm run build`: succeeds,
960.71 kB / gzip 295.32 kB (a modest, expected increase from the new
Financial Inputs card and its hook/API-client additions).

## Security

Grep of every new/modified file for API-key patterns, credentialed
database URLs, and similar: zero matches. No demo persona's financial
inputs contain a real email, phone number, government ID, or financial
account identifier — every number is a plausible but entirely fabricated
figure, the same category of synthetic data every other demo profile
field already is. The new endpoints enforce customer isolation exactly
like every other per-customer route in this prototype (path-scoped by
`profile_id`, no cross-customer read/write possible through any request
scoped to a different id) — consistent with, not weaker than, this
project's existing prototype-auth security posture (documented
limitations unchanged: no real session/token, see
`reports/post_login_profile_flow_report.md` §17).

## Model Integrity

`find models -type f -newer <pre-phase baseline>` → empty. No file under
`models/risk/`, `models/expense/`, `models/behaviour/`, `models/market/`,
or `models/portfolio/` was modified, retrained, or re-saved. No training
script was run.

## Dataset Integrity

No raw FAR-Trans file, Kaggle file, or `market_data` row was modified.
Synthetic financial-input data for the two demo personas was added
exclusively through the real, public `PUT /api/profiles/{id}/financial
-inputs` endpoint — never a direct database write (unlike
`risk_inputs.external_customer_id`, which genuinely has no API and still
required one, unchanged, pre-existing direct write per persona).

## Architecture Diagram

```
User Financial Inputs (Profile page form)
        |
   PUT /api/profiles/{id}/financial-inputs
        |
   financial_inputs table (customer_id, expenses, liquid assets,
                            contribution/return/inflation, periods)
        |
   analysis_service.py::_build_graph_dependencies
        |
        +---------------------+---------------------+
        |                     |                      |
  monthly_essential_    GoalAssumptions        historical_returns
  expenses/                (only if all 3           (market_data,
  current_liquid_assets   required fields            equal-weight
                           present)                   blend)
        |                     |                      |
        v                     v                      v
  assess_emergency_fund   goal_analyst_node (Phase 7, unmodified)
  (Phase 7, unmodified)        |
        |                 goal_results (real feasibility/contribution)
        v
  emergency_fund.sufficient (True / False / None)
        |
   route_after_market (agents/graph.py, unmodified)
        |
 +------+-------+
 |              |
sufficient=True sufficient=False or None
 |              |
portfolio_      savings_first_node (Phase 28 fix: None no
manager_node    longer errors -- produces a valid,
(Phase 8,       honestly-labeled savings-first result)
unmodified,          |
now reached     portfolio_result.weights = null,
live)           strategy = "savings_first"
 |                   |
 +-------+-----------+
         |
   compliance_analyst_node
         |
   core/compliance.py (Phase 9, unmodified rules; Phase 28 fix:
   weight rules recognize a legitimate savings-first "no weights"
   as PASS, not REJECT -- fail-closed preserved for every other case)
         |
   decision: PASS / REJECT (REJECT still wins, unconditionally)
         |
   overall_status: approved (PASS) / rejected (REJECT)
         |
   [only if approved] recommendation_engine_node (Phase 14, unmodified)
         |
   recommendation.status: "approved" (real strategy+weights) or
                           "savings_first" (weights null, by design)
         |
   [only if approved] explanation_node (Phase 13, unmodified) -> Gemini
                       or its existing templated fallback
```

This diagram matches the actual, verified implementation (§14) — not an
intended design.

## Known Limitations

- **Historical-returns sourcing for Monte Carlo** (§9) required one
  genuinely judgment-based decision (which asset blend to bootstrap
  from) that no authoritative document specifies exactly, since no
  customer-specific portfolio exists yet at the point Goal Analyst runs.
  Resolved using only already-approved building blocks (equal-weight
  blend of the approved asset universe), documented plainly rather than
  silently chosen — a reasonable implementer's decision, not a new
  financial methodology, but flagged here for visibility.
- **Goal feasibility results are genuinely "Not Feasible" for the demo
  personas** at their current synthetic contribution/income levels
  against their (also synthetic) large goal targets — an honest,
  unflattering, real Monte Carlo result. This was not adjusted to look
  more successful; changing it would mean picking numbers to produce a
  desired outcome, which this project's own rules forbid.
- **The other two preserved personas (29100, 29096) remain reachable only
  via the backend API**, not the authenticated UI, per the immediately
  preceding UX phase's own deliberate, unreversed design (no
  customer-switching control exists).
- **Gemini's own live call may fall back to Phase 13's existing templated
  explanation** under quota pressure — observed during this phase's own
  live verification, a pre-existing behavior, not a new limitation Phase
  28 introduces.
- No browser-based visual/interactive verification was performed in this
  environment (the same disclosed, pre-existing limitation every prior
  frontend phase in this project has carried).
