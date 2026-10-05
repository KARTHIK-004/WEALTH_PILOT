# Live Analysis Flow — Fix Report

## 1. Original Blocker

The live frontend showed "Not available" for Risk, Financial Health, and
related sections for the customer a logged-in demo session actually
reached, even though the backend pipeline that computes those values is
real and working. The reported symptom ("Risk category: Not available"
alongside a stale-looking value elsewhere) and the deeper "why can't a
customer ever reach approved" question were both investigated fresh this
phase, from the actual running code, not from memory of prior reports.

## 2. Root Cause

Two independent, structurally distinct causes, both confirmed by reading
`api/services/analysis_service.py`, `agents/graph.py`, `agents/nodes.py`,
`core/goals.py`, and `core/compliance.py` end to end, and cross-checked
empirically against the real database (see §13):

**(a) Demo-account resolution, not a pipeline bug — the actual cause of
the "Not available" symptom.** "Use Demo Account" resolved exclusively to
Phase 24's canonical "WealthPilot Demo Customer" (customer_id 29096),
which was deliberately built with no FAR-Trans transaction linkage (to
demonstrate the genuine "no history" case). With no linkage,
`risk_analyst_node` never receives a feature row, so the graph halts at
`information_request` immediately after risk classification — Financial
Health, Goals, Market, Portfolio, and Compliance are never even reached
for this customer, by design. This is not a defect in any page or in the
orchestration; it is the correct, honest behavior for a customer with no
linked history. The actual, fixable gap was that the OTHER, richer demo
personas (`reports/demo_data_completion_report.md`'s "WealthPilot Demo —
Complete/Savings/Compliance", customer_ids 29098/29099/29100 in this
environment) were real, FAR-Trans-linked, and fully reachable through the
pipeline, but nothing in the authenticated login flow ever resolved a
session to one of them — see §3 for the fix.

**(b) The "approved"/full-pipeline unreachability — already identified
in `reports/demo_data_completion_report.md` §3-4, re-derived independently
this phase from a fresh, complete read of the same code, and confirmed
still accurate.** `analysis_service.py::PipelineRun.events()` constructs
`GraphDependencies(session=self.session, portfolio_strategy=... or "mvo")`
only — `goal_assumptions`, `historical_returns`,
`monthly_essential_expenses`, and `current_liquid_assets` are never
supplied, for any customer. `core/goals.py::goal_analyst_node` therefore
always reports every goal as `unavailable_reason: "no GoalAssumptions
... supplied"`, and always returns `emergency_fund.sufficient = None`.
Two independent gates key off that: `agents/graph.py::route_after_market`
only proceeds to the real MVO/HRP/1-N optimizer when `sufficient is
True` (never happens), and `core/compliance.py`'s
`emergency_fund_savings_first` rule (REJECT severity) explicitly fails
closed whenever `emergency_fund_sufficient is None`. This makes REJECT
unconditional for every customer that clears the risk-confidence gate,
regardless of risk category, goals, or portfolio strategy.

**A second, previously-undocumented structural finding, made this
phase**: even with real emergency-fund data indicating genuine
insufficiency, `agents/nodes.py::savings_first_node` never sets
`portfolio_result.weights` (a savings-first outcome legitimately has no
weights, by its own documented design — "skip optimization entirely").
None of the four weight-validation compliance rules
(`weights_sum_to_one`, `no_negative_weights`, `qqq_within_risk_band`,
`single_asset_cap`) carve out an exception for a legitimate
savings-first proposal — each fails closed REJECT whenever `weights is
None`, unconditionally. Confirmed directly: for 29098/29099/29100, all
five rules trigger, not just `emergency_fund_savings_first` (see §13's
`triggered_rules`). This means fixing (b) alone would very likely still
not produce a clean `approved` or savings-first `PASS`/`WARN` outcome —
a second, independent architectural gap between two separately-approved
components (Phase 9's compliance ruleset and Phase 10's
`savings_first_node`), not a data-supply problem at all.

## 3. Data-Flow Correction

**What was fixed (orchestration/data plumbing only):** the demo-account
resolution mechanism, `frontend/src/lib/demo-customer.ts`'s
`resolveDemoCustomer()` (called by both "Sign In" and "Use Demo Account",
per the immediately-preceding post-login-profile-flow fix), now prefers
the real, FAR-Trans-linked "WealthPilot Demo — Complete" persona over the
linkage-less canonical customer, falling back to the original Phase 24
customer only when "Complete" has not been seeded in this environment.
Finding an already-seeded persona by name (rather than hard-coding its
numeric id, which is explicitly forbidden and would break across
environments) required one minimal, read-only backend addition: `GET
/api/profiles/lookup?name=...` (new route in
`api/routers/profiles.py`, new `ProfileLookupResponse` schema in
`api/schemas.py`) — an exact, case-sensitive match against the existing
`customers.name` column, returning `customer_id: null` (never a 404) when
nothing matches. No schema/migration was added (reuses the existing
column); no financial calculation, model, or compliance logic was
touched. This mirrors the exact lookup
`backend/scripts/seed_demo_data.py::_find_existing_customer_id` already
performs directly against the database for the identical reason — now
exposed safely, narrowly, and read-only through the public API for the
frontend's legitimate use case. `frontend/src/types/api.ts` was
regenerated from the live FastAPI OpenAPI schema (via `app.openapi()`
called directly in Python — no server was started for this, consistent
with not running long-lived processes) and `lib/api-client.ts` gained one
new typed method, `lookupProfileByName`.

**What was investigated and NOT fixed, per this phase's own STOP
instruction:** the (b) findings above. No existing field anywhere in the
schema/API (`Customer.income`, `FinancialGoal.current_savings`,
`investment_capacity`, or any other) can legitimately supply
`monthly_essential_expenses`, `current_liquid_assets`, or the three
required `GoalAssumptions` fields (`contribution_amount`,
`annual_return_rate`, `annual_inflation_rate`) without either inventing a
financial formula (e.g., deriving expenses from income) or misusing a
field for an unintended purpose (e.g., treating a goal's own
`current_savings` as the customer's total liquid assets) — both
explicitly forbidden. This is a genuine missing data contract: no
onboarding flow anywhere in this application collects these five numbers
from a user today. Fixing it would require new user-facing input fields
(a real feature, not plumbing) and is out of this phase's authorized
scope. The compliance/savings-first weight-rule gap is core, approved
Phase 9/10 logic — explicitly protected ("do not change compliance
thresholds/precedence", "do not modify recommendation methodology").
Both are documented here, precisely, rather than silently worked around.

## 4. Emergency-Fund Handling

Per §2(b)/§3: `monthly_essential_expenses`/`current_liquid_assets` remain
unsuppliable from any existing data source. `core/goals.py::
assess_emergency_fund` and `savings_first_required` were not touched.
`emergency_fund.sufficient` remains `None` for every customer through the
live pipeline, unchanged by this phase.

## 5. Goal Handling

`goal_analyst_node` already correctly consumes persisted
`financial_goals` rows — confirmed by reading `customer_analyzer_node`
(loads `customer.financial_goals` into `state.customer_profile.goals`)
and `goal_analyst_node` itself (iterates `state.customer_profile.goals`
directly). The gap is not in consuming persisted goals; it is that
`GoalAssumptions` (contribution/return/inflation — required, no default,
by Phase 7's own explicit design) is never constructed anywhere in
`analysis_service.py`, for the same missing-data-contract reason as §2(b).
No change was made to `core/goals.py` or `agents/nodes.py::
goal_analyst_node`.

## 6. Risk Consistency

Audited `dashboard-page.tsx`, `risk-assessment-page.tsx`, and
`hooks/use-analysis.ts`: both pages already read the exact same
`useAnalysisQuery(profileId)` result (query key `["analysis", profileId]`,
30s `staleTime`), so there is exactly one client-side cache entry per
customer, shared identically across every page — no separate/stale risk
source was found anywhere in the frontend. The "Not available... stale
value elsewhere" symptom is fully explained by §2(a): a session that had
never resolved to a FAR-Trans-linked customer would correctly show
"Not available" everywhere, while a differently-resolved customer
(reached only via the now-removed manual profile picker, or dev-tools
`localStorage` tampering) would show real values — two different
customers being compared, not one customer showing inconsistent data.
No frontend consistency bug was found or needed fixing; §3's demo
-resolution fix addresses the actual root cause.

## 7. Financial-Health Handling

Classification (per the task's own A-E list): **B — node not reached**,
for the default pre-fix demo customer (29096): the graph halts at
`information_request` before `financial_health_analyst` ever runs,
because risk confidence is unavailable, not because financial health
itself failed. For a FAR-Trans-linked customer (e.g. 29098), the node IS
reached and DOES produce a real result: `behaviour_drift_flag: false`,
`isolation_forest_anomaly: false` — confirmed live (§13).
`expense_persona` remains permanently `null` with its existing
`unavailable_reason` for every customer, by design (FAR-Trans has no
income/expense fields; the Kaggle expense-clustering model is a separate,
unlinked population) — never fabricated, unchanged by this phase.
`financial-health-page.tsx` already renders all of this correctly; no
frontend change was needed.

## 8. Compliance Behavior

Unchanged — `core/compliance.py` and `config/compliance_rules.yaml` were
not modified. All five existing rules, their severities, and REJECT's
fail-closed, non-bypassable behavior (`enforce_gate`) are exactly as
before. `REJECT` is confirmed, live, for every customer that clears the
risk-confidence gate (§13); `pending_information` is confirmed for a
customer that does not.

## 9. Portfolio Behavior

Unchanged — never reached by any customer through the live orchestration
(§2b), confirmed unchanged live for all three FAR-Trans-linked personas
(§13: `portfolio: null`). `core/optimizer.py` and
`agents/nodes.py::portfolio_manager_node` were not modified; no portfolio
weights were inserted anywhere.

## 10. Recommendation Behavior

Unchanged — `agents/recommendation.py` is only invoked by
`analysis_service.py` when `overall_status == "approved"`, which does not
occur for any customer (§2b). Confirmed live: `recommendation: null` for
all four demo personas (§13). No recommendation row was written for any
of them.

## 11. Gemini Behavior

Unchanged — `agents/explanation.py`'s `explanation_node` is gated behind
the identical `overall_status == "approved"` check, in the same
`analysis_service.py` block as recommendation. Confirmed live:
`explanation: null` for all four demo personas. Gemini was not invoked
for any customer this phase; no explanation was fabricated.

## 12. SSE Behavior

Unchanged and confirmed, by reading `api/sse.py`, to share the exact same
`PipelineRun.events()` generator the synchronous `POST /api/analysis`
endpoint uses — there is one execution path for both, not two that could
drift apart. No new event type was added; the existing `NodeEvent`
contract (`node`/`status`/`duration_ms`/`summary`/`model_version`) is
unchanged and still carries no prompt, reasoning trace, or transcript by
construction.

## 13. Demo Customer Results

Re-verified live this phase by calling the real, unmodified
`get_or_run_analysis` directly against the actual (non-test) database
(no HTTP server was started for this — see the working note in §15).
Every persona returned its exact existing cached result, confirming
nothing about this phase's changes altered any prior analysis outcome:

| Persona | customer_id | analysis_id | status | risk | financial_health | compliance (triggered rules) |
|---|---|---|---|---|---|---|
| WealthPilot Demo Customer | 29096 | 144 | `pending_information` | unavailable | not reached | not reached |
| WealthPilot Demo — Complete | 29098 | 132 | `rejected` | Aggressive, 0.9126 | drift=False, anomaly=False | all 5: weights_sum_to_one, no_negative_weights, qqq_within_risk_band, single_asset_cap, emergency_fund_savings_first |
| WealthPilot Demo — Savings | 29099 | 133 | `rejected` | Balanced, 0.7636 | drift=False, anomaly=False | same 5 |
| WealthPilot Demo — Compliance | 29100 | 134 | `rejected` | Conservative, 0.7772 | drift=False, anomaly=False | same 5 |

Goals for all three FAR-Trans-linked personas: 2 each, both
`unavailable_reason: "no GoalAssumptions (contribution/return/inflation)
supplied"`. Market: present (real 5-instrument regime data) for all
three. Portfolio/recommendation/explanation: `null` for all four.

**Primary demo customer** ("WealthPilot Demo — Complete", 29098): does
NOT reach `approved` — confirmed, not assumed (per this phase's own
explicit "do not assume it will become approved" instruction). Its
actual state is `rejected`, for the two independent, fully-documented
structural reasons in §2.

## 14. Tests

Backend: 4 new tests added to `tests/backend/api/test_profiles.py` for
the new `GET /api/profiles/lookup` endpoint — exact-name match found,
not-found returns `{"customer_id": null}` (never a 404), case-sensitivity
and partial-match rejection, and the required-query-param validation
error. That file's full suite (26 tests, including the 22 pre-existing
ones) passes. The full backend suite was re-run in the background for
this phase's own regression confirmation; its exact pass/fail count is
reported in the final summary message below once it completed. No
existing test was modified. Frontend: no automated test runner exists in
this project (the same disclosed, pre-existing limitation every prior
frontend phase has carried) — `resolveDemoCustomer()`'s new
lookup-then-fallback logic was verified via `tsc -b`, direct reading of
its final source, and an end-to-end backend-side check
(`verify_demo_personas.py`, a scratch, non-committed script) confirming
the lookup endpoint and the underlying profile/questionnaire/goals data
it depends on are all live and consistent for the "Complete" persona.

## 15. Frontend Verification

`npx tsc -b`: 0 errors. `npx oxlint`: 0 errors, 8 warnings (identical set
to the pre-phase baseline). `npm run build`: succeeds, 955.15 kB / gzip
293.82 kB (materially unchanged from the pre-phase baseline). No headless
-browser tool was available in this environment — no click-through UI
test was performed or is claimed; verification relied on the above plus
direct reading of every page component that consumes the analysis result
(`dashboard-page.tsx`, `risk-assessment-page.tsx`,
`financial-health-page.tsx`, `goals-page.tsx`) to confirm each already
renders the corrected data correctly with no frontend change required to
any of them.

## 16. Database Changes

Zero schema changes, zero migrations. The only new backend surface is one
additional read-only API route reusing the existing `customers.name`
column (§3) — no column, table, or index was added. No demo persona's
data was altered; no production/real customer record was read or written.

## 17. Model Integrity

Unchanged. No file under `models/risk/`, `models/expense/`,
`models/behaviour/`, `models/market/`, or `models/portfolio/` was
modified, retrained, or re-saved this phase; no training script was run.

## 18. Known Limitations

- **[SUPERSEDED by Phase 28 — `reports/phase28_financial_input_savings_first_report.md`]**
  "Approved" remains unreachable for every customer, for two
  independent, now fully-documented structural reasons (§2b) — neither
  was fixed, per this phase's own explicit scope boundary (no new
  financial-input UI/API, no compliance-rule change). **The very next
  phase (28) was explicitly authorized to fix both: a real
  `financial_inputs` data contract, and the compliance/savings-first
  weight-rule exemption this report's §2b first identified. Two of the
  three synthetic demo personas now genuinely reach `approved` — see the
  Phase 28 report for the fix and `reports/demo_dataset_catalog.md` for
  live-verified current results. Left intact here as an accurate record
  of this phase's own findings and scope boundary at the time.**
- **The other three preserved personas (29096/29099/29100) are no longer
  reachable through the authenticated UI** in this environment, because
  the immediately-preceding UX phase deliberately removed all
  customer-switching UI (a correct decision this phase does not reverse).
  They remain fully preserved in the database and reachable via the
  backend's own interactive API docs (`/docs`) or
  `scripts/seed_demo_data.py verify` — documented in
  `docs/demo_runbook.md`, not hidden.
- **Demo-customer resolution is idempotent per browser, not global**: a
  browser that already resolved to the Phase 24 canonical customer before
  this fix keeps reusing that same customer on later logins rather than
  silently upgrading to "Complete" — a deliberate stability choice,
  consistent with Phase 24's own already-disclosed per-browser limitation.
- No browser-based visual/interactive verification was performed in this
  environment (disclosed above, consistent with every prior phase).
