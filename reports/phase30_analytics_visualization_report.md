# Phase 30 — Analytics Graphs & Visualization Report

## 1. Status

**COMPLETE.** Every completion criterion in the Phase 30 prompt is met, with
one qualification stated up front: the frontend was verified at **source
level, by API verification, by a server-side render of the real components
against real API data, and by build checks — not in a browser** (none is
available). The final isolated backend run: 763 passed, 3 skipped, 0
failed (§12).

## 2. Objective

Add analytics graphs to the WealthPilot AI frontend that visualize
**existing, authoritative API data** — no new financial calculation, no
backend change, no new library (Recharts was already approved and in use).
The Phase 29 verified baseline (corrected Monte Carlo frequency, compliance
breakdown, deterministic lookup, cache-versioned analyses, the four demo
outcomes) was taken as given and not modified.

## 3. Graphs Added

### 3.1 Risk Probability

`RiskProbabilityChart` on the **Risk Assessment** page: a horizontal bar
chart of `risk.class_probabilities`, in the API's own order and with its
own labels (`Aggressive, Balanced, Conservative, Income` — the API returns
them alphabetically, so that is the order shown; nothing is re-ranked). The
probability axis is fixed to 0–100% (a presentation scale). The bar for the
API's own `risk.risk_category` is drawn darker and the card text says so.
The existing probability table stays beside the chart (one decimal in both,
so a small probability such as 0.12% no longer shows as "0%"). If
`class_probabilities` is `null` the chart is replaced by an unavailable
state.

### 3.2 Emergency Fund

`EmergencyFundChart` on **Financial Health** (and on Portfolio and
Dashboard for a savings-first result): two bars, Required and Current,
from `emergency_fund.required_amount` / `.current_amount`. The shortfall is
the backend's `.shortfall` value printed as text under the chart — it is not
computed as `required - current` — together with the backend's
`.sufficient` state. If either amount is `null` the chart is unavailable
with the backend's `unavailable_reason`.

### 3.3 Goals

On the **Goals** page each goal card gets a `GoalTargetChart`: target vs
inflation-adjusted target (`nominal_target_amount`,
`inflation_adjusted_target_amount`; both currency, so one axis is honest).
The monthly contribution and gap stay as text (different unit). The Monte
Carlo probability keeps its progress-bar indicator and now shows one
decimal (94.1%, not 94%), with the backend's `feasibility` string as the
badge — feasibility is never inferred from the probability. When the
adjusted target is `null` the chart is replaced by the goal's own
`unavailable_reason`. When `contribution_gap` is negative the value is shown
unchanged and the note "Contribution exceeds the calculated requirement."
appears under it (see §6 for why this is presentation only).

### 3.4 Portfolio Allocation

`PortfolioAllocationChart` (donut) replaces the old
`components/portfolio/allocation-chart.tsx`. It plots
`recommendation.weights` unchanged and adds a key naming every asset with
its own weight, so a slice is never identified by colour alone. Used on
**Portfolio**, **Recommendation** (approved result) and **Dashboard**
(approved result). Status handling: approved → donut + `AllocationTable` +
metrics; `savings_first` → "Savings-first: portfolio allocation deferred."
plus the emergency-fund chart, no donut; rejected → no allocation and the
Phase 29 compliance breakdown (newly shown on the Portfolio page too);
`pending_information` → the existing incomplete notice.

### 3.5 Portfolio Risk/Return

Not implemented because authoritative API data was not available. The API
exposes one portfolio point (`expected_return`, `expected_volatility`,
`sharpe_ratio`) but no efficient-frontier data, and drawing a frontier —
or a single dot with nothing to compare to — would mean inventing points in
the frontend or adding a decorative chart. The three metrics remain
displayed by `PortfolioMetrics`, and the Scenario Simulator (§3.8) charts
them for two scenarios, which is where a comparison exists.

### 3.6 Recommendation

No numeric chart was added, deliberately (this is a design decision, not a
missing-data omission): the prompt forbids a recommendation score or
ranking, and the authoritative content — status, selected strategy,
deterministic reasons, provenance, compliance state — is categorical and
stays as cards and badges. The only visual change on this page is that the
approved allocation donut is the shared `PortfolioAllocationChart`; the
Phase 29 compliance breakdown remains visible, including for a rejected
analysis.

### 3.7 Agent Activity

`AgentPipeline` replaces the plain event list: a connected, step-by-step
view built **only** from SSE events actually received, in arrival order.
Each step shows the title-cased `node`, a status badge, `duration_ms`,
`model_version` and the backend's own `summary`. It holds no model of the
pipeline topology, so nothing not received is drawn: a savings-first run
shows a "Savings First" step and no "Portfolio Manager"; a rejected run
shows no "Recommendation" or "Explanation"; a partial run shows a "Waiting
for the next step…" row rather than future steps. The terminal
`approved`/`rejected`/`pending_information`/`failed` events are titled
"Analysis outcome" with the outcome as a badge, and `rejected` gets a ban
icon (the old list showed a success check for it, because that event's
status is `completed`). Only the five safe SSE fields are read.

### 3.8 Scenario Simulator

`ScenarioComparisonChart`: grouped bars for `expected_return` and
`expected_volatility` (same unit) and a separate chart for `sharpe_ratio`
(unitless), Scenario A vs Scenario B, named from the API (`label` +
`portfolio_strategy`). The existing comparison table stays. Nothing is
ranked or called best/winner/recommended. A `null` metric is not drawn and
is listed as "Not available (not drawn)"; if every metric is `null` (a
savings-first or blocked scenario) the whole chart is an unavailable state.
The API's `ScenarioSummary` carries no weights, so no weights are charted.

### 3.9 Dashboard

At most one chart, keeping the page a summary: the approved allocation
donut for an approved result, or the emergency-fund chart for a
savings-first result; none for rejected, pending or failed.

## 4. Data Sources

| Graph | React component | API field(s) | Backend source |
|---|---|---|---|
| Risk probabilities | `RiskProbabilityChart` | `AnalysisResult.risk.class_probabilities` (+ `risk.risk_category` to pick the darker bar) | Risk Analyst (`models/risk/rf_v1.pkl`, Phase 4) |
| Emergency fund | `EmergencyFundChart` | `emergency_fund.required_amount`, `.current_amount` (bars); `.shortfall`, `.sufficient`, `.unavailable_reason` (text) | Phase 28 financial-input integration + `core/goals.py::assess_emergency_fund` |
| Goal targets | `GoalTargetChart` | `goals[].nominal_target_amount`, `.inflation_adjusted_target_amount`, `.unavailable_reason` | Goal Analyst / `core/goals.py` |
| Goal probability + feasibility | existing `Progress` + `StatusBadge` on `GoalsPage` | `goals[].monte_carlo_success_probability`, `.feasibility` | `core/goals.py::run_goal_monte_carlo` (Phase 29 period-frequency fix, ADR-027) |
| Portfolio allocation | `PortfolioAllocationChart` | `recommendation.weights` | Recommendation engine (Phase 14) over the optimizer (Phase 8, `core/optimizer.py`) |
| Compliance breakdown | `ComplianceBreakdown` (Phase 29, unchanged) | `compliance.rule_results[]`, `.decision`, `.rules_version` | `core/compliance.py` (Phase 9) |
| Scenario comparison | `ScenarioComparisonChart` | `ScenarioSummary.expected_return`, `.expected_volatility`, `.sharpe_ratio`, `.label`, `.portfolio_strategy` | Portfolio section of each scenario's analysis (`POST /api/scenarios/compare`) |
| Agent pipeline | `AgentPipeline` | SSE `node`, `status`, `duration_ms`, `summary`, `model_version` | `GET /api/analysis/stream` (`api/sse.py`, `PipelineRun.events()`) |

No parallel source exists: each chart reads the same shared
`useAnalysisQuery`/`useScenarioCompare`/`useAnalysisStream` data its page
already reads.

## 5. Frontend Architecture

- `frontend/src/components/charts/` (new): `risk-probability-chart.tsx`,
  `emergency-fund-chart.tsx`, `goal-target-chart.tsx`,
  `portfolio-allocation-chart.tsx`, `scenario-comparison-chart.tsx`,
  `agent-pipeline.tsx`, and `chart-theme.ts` (axis/tooltip/series constants
  from the theme tokens, so light and dark both work).
- Chart components receive typed props, make no API call and contain no
  financial, ML, recommendation or compliance logic. Only
  `ScenarioComparisonChart` imports a generated API type
  (`components["schemas"]["ScenarioSummary"]`); `AgentPipeline` imports the
  existing `NodeProgressEvent`. No API type was hand-written.
- Pages own data fetching and status-based selection (which chart, which
  message) and pass fields down. Existing shell components
  (`SectionUnavailable`, `StatusBadge`, `ComplianceBreakdown`) are reused;
  shadcn/ui `Card`, `Table`, `Alert`, `Badge`, `Progress` remain the primitive
  system. No shadcn component was added and no dependency was added.
- `components/portfolio/allocation-chart.tsx` was deleted (all references
  moved to the new component); `allocation-table.tsx` and
  `portfolio-metrics.tsx` are unchanged.
- Decision record: `docs/DECISIONS.md` ADR-029; design rules and the field
  mapping: `docs/DESIGN.md` section 16.

## 6. Financial Calculation Audit

Searched `frontend/src/components/charts/` and the whole of `frontend/src`
(excluding generated `types/api.ts`) for `Math.`, `reduce(`, `.sort(`,
`* 100`, `/ 100`, `Number(`, `parseFloat`, `toFixed`, and arithmetic
operators, then inspected every hit.

**`components/charts/` — every hit, none financial:**

- `.toFixed(2)` in `scenario-comparison-chart.tsx` — formats the API's
  Sharpe ratio for display (the same convention `PortfolioMetrics` already
  uses).
- `events.length - 1` in `agent-pipeline.tsx` — list position, to omit the
  connector line under the last step.
- `index % SLICE_COLORS.length` (two places) in `portfolio-allocation-chart.tsx`
  — cycles the colour palette.
- `.map` / `.flatMap` / `.some` / `.join` — rendering only: turning the API
  object into chart rows, building the `aria-label`, and listing which
  metrics were `null`. No value is combined with another.
- No `Math.`, `reduce`, `.sort`, division, multiplication or addition of any
  API number exists in the directory. The remaining `-`/`/`/`+` matches are
  prose in comments.

**Rest of `frontend/src` — new or changed:**

- `formatPercent(x, 1)` (`lib/format.ts`, unchanged) multiplies by 100 for
  display; the Goals page and the Risk table now pass one decimal.
- `goals-page.tsx`: `goal.contribution_gap !== null && goal.contribution_gap
  < 0` — the **only** new logic beyond formatting. It is a sign test that
  selects the text "Contribution exceeds the calculated requirement."; the
  value is displayed unchanged. `core/goals.py` documents `contribution_gap`
  as *required periodic contribution minus the planned contribution*
  ("positive means the current contribution plan falls short, zero or
  negative means on track or ahead"), so the note restates the backend's own
  definition; no requirement, gap or feasibility is recomputed. This was
  judged a presentation interpretation rather than new financial logic
  because no extra backend field was needed and nothing is derived from two
  values.
- Pre-existing and unchanged: `* 100` for the two `Progress` bars
  (`risk-assessment-page.tsx` confidence, `goals-page.tsx` probability).
  Other hits (`> 0` checks, `Math.floor` in `lib/demo-customer.ts`, the
  sidebar skeleton's `Math.random`) are unrelated to this phase.

Checked and **absent**: `shortfall = required - current`, any probability,
feasibility, weight normalisation, expected return / volatility / Sharpe,
future value, or Monte Carlo in React.

## 7. NULL / Unavailable Handling

Each chart takes `null | undefined` and renders `SectionUnavailable` (with
the API's own `unavailable_reason` when it has one) instead of a chart:

- `class_probabilities = null` → unavailable state.
- `emergency_fund.required_amount` or `.current_amount = null` → unavailable
  state; the shortfall is text, printed via `formatCurrency` (`null` → "Not
  available").
- `inflation_adjusted_target_amount = null` → the goal's unavailable reason
  instead of a one-bar "comparison".
- `weights = null` → "no allocation was returned" state at component level;
  pages choose the status-specific message (savings-first: "Savings-first:
  portfolio allocation deferred."). A donut is never drawn for `null`.
- A scenario metric `null` → passed through as `null` (not drawn, listed as
  "Not available"), never `0`.
- `monte_carlo_success_probability = null` → no probability indicator is
  rendered at all (verified for 29100: no "success probability" text).
- Legitimate backend zeros are shown as zeros: 29099's Emergency Fund goal
  has a real `0.0` probability and `Not Feasible`; 29098's shortfall is a real
  `0`.

## 8. Status-Safe Rendering

| Analysis state | What renders |
|---|---|
| `approved`, MVO | Allocation donut (Portfolio, Recommendation, Dashboard), metrics, allocation table |
| `approved` with `recommendation.status = savings_first` | No donut and no weights anywhere; "Savings-first: portfolio allocation deferred." + emergency-fund chart (Portfolio), emergency-fund chart (Dashboard, Financial Health) |
| `rejected` | No chart on Portfolio/Recommendation/Dashboard/Financial Health/Goals; the Phase 29 `ComplianceBreakdown` (rule, triggered/passed, backend reason) on Portfolio and Recommendation; no explanation |
| `pending_information` | No chart on any page; existing incomplete/unavailable notices |

The Agent Activity view follows the same principle from the other side —
it draws only events received (§3.7). The Dashboard picks its single chart
from `recommendation.status`, so a savings-first result can never show an
allocation donut.

## 9. Accessibility

- Every chart is wrapped in `role="img"` with an `aria-label` listing every
  plotted value (e.g. "Risk class probabilities: Aggressive 91.3%, Balanced
  7.2%, …"), and every chart sits beside an existing table or text with the
  same values: risk → probability table; emergency fund → the Required /
  Current / Shortfall stat cells; goals → the target/inflation-adjusted stat
  cells; allocation → `AllocationTable` and the donut's key; scenarios → the
  comparison table. No existing table was removed.
- No series is identified by colour alone: bars are labelled on the axis and
  with their value, the donut has a text key, scenario series are named in
  the legend and labels, and the "darker bar = selected" pair is explained
  in text.
- The pipeline is an ordered list (`<ol aria-label>`); status is a text badge
  as well as an icon (icons are `aria-hidden`).
- Headings: each chart lives in a card with a `CardTitle`; the scenario
  chart's two sub-charts have `<h3>` headings.
- Not verified: screen-reader announcement, keyboard behaviour of the
  Recharts tooltips, and contrast of the grey donut palette in dark mode —
  all need a browser (§16).

## 10. Responsive Design

Source-level only. Charts sit in `ResponsiveContainer` inside fixed-height
blocks (`h-56`, `h-36`, `h-32`, `h-64`, `h-40`) so they resize to the card
width; page layouts use Tailwind `lg:grid-cols-2` and stack below `lg`; the
Y-axis label widths (72–112 px) and right margins (52–76 px, for the value
labels) were chosen to leave a usable plot at a ~340 px card. The key under
the donut wraps (`flex-wrap`). The pipeline is a vertical list and wraps its
badges. **This was not checked in a browser**; label collisions and tiny text
on real narrow screens remain unverified.

## 11. Demo Validation

Method: the real `POST /api/analysis`, `GET /api/analysis/stream`,
`GET /api/profiles/{id}` and `POST /api/scenarios/compare` responses were
captured in-process (`TestClient(app)`, no server started) for the four
demo personas — analysis ids unchanged (165–168), i.e. cache hits, no demo
data changed. The **real** page components were then server-side-rendered
with those responses and asserted on (65 checks, all passing). Recharts 3
draws no `<svg>` during a server render, so its primitives were replaced by
data-capturing stubs: the checks prove the exact data handed to each chart,
the surrounding text/tables, and status-safe rendering — **not** how the
charts look. The harness is a scratch script (not committed); the temporary
files it needed under `frontend/` were deleted afterwards.

### 29098

Approved, MVO. Verified from the API responses and the rendered pages:
- Risk chart data equals `risk.class_probabilities` exactly, in API order
  (Aggressive 91.3%, Balanced 7.2%, Conservative 0.1%, Income 1.5%); only the
  Aggressive bar is emphasised.
- Emergency-fund chart data = Required €18,000 / Current €40,000; shortfall
  text €0 (backend value), "sufficient".
- Goals show the corrected Monte Carlo values — Retirement 94.1% Feasible,
  House Purchase 50.3% At Risk — not the pre-Phase-29 0%; target charts use
  €400,000 → €796,059 and €90,000 → €103,400; the negative-gap note appears
  once (Retirement, gap −€113); House Purchase (+€147) has none.
- Portfolio/Recommendation donut data equals `recommendation.weights`
  exactly (QQQ 0.55, AGG 1.67e-16, GLD 0.45 — unnormalised; AGG's
  floating-point residue displays as 0%), the same values as
  `portfolio.weights`; metrics 17% / 16% / 1.06.
- Dashboard shows exactly one chart, the allocation.

### 29099

`savings_first`, weights `null`, shortfall €11,000. Portfolio shows
"Savings-first: portfolio allocation deferred." and the emergency-fund chart
(Required €15,000 / Current €4,000, shortfall €11,000, insufficient) — no
donut, no allocation key/table, no QQQ/AGG/GLD anywhere. Dashboard: exactly
one chart, the emergency fund. Goals use the corrected values (Emergency
Fund 0.0% Not Feasible, Retirement 88.6% Feasible); no negative-gap note
(both gaps positive).

### 29100

`rejected`, one rule. Portfolio and Recommendation render the compliance
breakdown: REJECT, exactly one rule triggered (with the backend's own
reason "required data unavailable: emergency-fund status was not provided")
and four passed; no allocation, emergency-fund or goal chart on any page
(asserted on Portfolio, Recommendation, Financial Health, Goals and
Dashboard — the Risk page correctly still shows the real class-probability
chart: Conservative 77.7%); no allocation UI; no strategy badge. Emergency fund and goals show the
backend's unavailable reasons; no probability text (null is not 0%). The API
response has `recommendation: null` and `explanation: null`, so no page has
anything to render — no Gemini explanation.

### 29096

`pending_information`. All six pages render **no chart** (asserted on every
one), risk shows its unavailable reason, the Portfolio page shows the
incomplete notice and no compliance card, Financial Health shows "Not
available". Nothing is fabricated.

**Agent Activity (real SSE captures):** 29098 → 12 steps including Portfolio
Manager, Recommendation and Explanation; 29099 → "Savings First" and **no**
Portfolio Manager, summary "…optimization skipped"; 29100 → 10 steps, **no**
Recommendation or Explanation, outcome "Rejected" with a ban icon; 29096 →
halts at Information Request; a 5-event partial run shows five steps and a
waiting row. The captured events contain only the five safe fields, and no
prompt/transcript/reasoning text is rendered. The SSE captures for 29098/
29099 persisted one `recommendations` row each, which were removed
afterwards (counts restored: 2 and 2).

## 12. Backend Regression

No backend, test, migration, model or dataset file was changed in Phase 30,
so this run is a regression confirmation that the frontend work disturbed
nothing (in particular the Phase 29 baseline).

`pytest tests/ -v --tb=short`, run in isolation (no other process touched
either database; the DB-free reachability probe beforehand showed 15/15
connections OK on both databases, no errors):

**763 passed, 3 skipped, 0 failed, 152 warnings, 978.19 s (0:16:18).**

The output file contains 763 `PASSED` lines and no `FAILED`/`ERROR` line.
The 3 skips are the same live-Gemini tests as in Phase 29
(`test_debate_gemini_client.py` ×2, `test_explanation_gemini_client.py` ×1),
skipped because Gemini's quota is exhausted. The count equals Phase 29's
final result exactly (763 / 3 / 0). No test was weakened, deleted or
skipped.

## 13. Frontend Validation

- `npx tsc -b`: **0 errors**.
- `npx oxlint`: **0 errors, 8 warnings** — the identical pre-existing set
  (shadcn primitives and provider files); none in any new file.
- `npm run build`: succeeds, 2,984 modules — `index-*.js` **1,046.81 kB**
  (gzip 315.78 kB), CSS 97.70 kB (gzip 15.87 kB). The JS bundle grew by
  84.36 kB from Phase 29's 962.45 kB (Recharts bar/axis/legend modules; the
  single-chunk build with Vite's >500 kB warning is the known, accepted
  characteristic).
- API contract: `frontend/src/types/api.ts` was compared with a fresh
  `openapi-typescript` generation from `app.openapi()` (called in a short
  process, no server). It differed by **one comment** (§17); it was
  regenerated with the same process and is now byte-identical to a fresh
  generation. The routes list is unchanged (13).
- Server-side render check: 65/65 (see §11); not a browser test.
- **No browser or headless-browser tool is available; no visual, interaction
  or responsive verification was performed.**

## 14. Documentation Updates

`docs/DESIGN.md` (section 16 rewritten: components, field mapping, rules),
`docs/ARCHITECTURE.md` (repository structure + an analytics-layer paragraph
in section 4), `docs/DECISIONS.md` (ADR-029), `docs/PRD.md` (14.15),
`docs/MEMORY.md` (current phase, frontend state, API state, notes, test
status), `docs/TEST_PLAN.md` (the SSR data-binding check),
`CLAUDE.md` (layout line), `README.md` (status line),
`.claude/rules/frontend.md` (chart rule), `TASKS.md` (Phase 30 entry). Historical reports were not rewritten; a short
superseded note was added to the Phase 29 report (§17 limitation about the
negative gap, §8 types claim).

## 15. Files Changed

**New**
- `frontend/src/components/charts/{agent-pipeline,emergency-fund-chart,goal-target-chart,portfolio-allocation-chart,risk-probability-chart,scenario-comparison-chart}.tsx`, `chart-theme.ts`
- `reports/phase30_analytics_visualization_report.md`

**Modified (frontend)**
- `pages/risk-assessment-page.tsx` — probability chart beside the table (one decimal).
- `pages/financial-health-page.tsx` — emergency-fund chart.
- `pages/goals-page.tsx` — target chart, one-decimal probability, negative-gap note.
- `pages/portfolio-page.tsx` — new donut, savings-first message + emergency-fund chart, compliance breakdown for a rejected result.
- `pages/recommendation-page.tsx` — uses the shared donut.
- `pages/agent-activity-page.tsx` — `AgentPipeline`.
- `pages/scenario-simulator-page.tsx` — comparison chart card.
- `pages/dashboard-page.tsx` — one conditional chart card.
- `types/api.ts` — regenerated (comment-only difference).

**Deleted**
- `frontend/src/components/portfolio/allocation-chart.tsx` (superseded by `components/charts/portfolio-allocation-chart.tsx`; no remaining reference).

**Modified (docs/config)**
- `CLAUDE.md`, `README.md` (status line), `.claude/rules/frontend.md`, `TASKS.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/DESIGN.md`, `docs/MEMORY.md`, `docs/PRD.md`, `docs/TEST_PLAN.md` (a paragraph on the chart data-binding check), `reports/phase29_final_integration_report.md` (superseded note only).

**Not changed:** anything under `backend/`, `tests/`, `models/`, `datasets/`,
`config/`, `training/`, `scripts/`, migrations, `package.json`. No dependency
was added. `git status` has no baseline (0 commits); the list above comes from
a modification-time audit against the Phase 29 sign-off.

## 16. Known Limitations

- **No browser verification.** Chart drawing, label collisions, tooltip
  behaviour, dark-mode contrast of the grey donut palette, keyboard/screen-
  reader behaviour and real narrow-screen layout are unverified.
- **Recharts is not exercised by the SSR check** (it draws no SVG on the
  server); the check proves what data each chart receives, not what it draws.
- The scenario chart was verified against the real default-vs-default
  response (A and B identical); distinct-value and `null` cases use clearly
  labelled synthetic props, because obtaining a real MVO-vs-HRP response
  would have created new cached analysis rows.
- The donut palette is the project's grey `--chart-*` tokens; the key
  beneath it carries the identification. Slices for near-zero weights (AGG,
  1.7e-16) are invisible but listed.
- The Risk chart shows the API's alphabetical order, not
  Conservative → Aggressive, because the prompt (and ADR-029) forbids
  re-ordering.
- `ScenarioSummary` takes its return/volatility/Sharpe from the analysis
  `portfolio` section, whereas the Portfolio/Recommendation pages read
  `recommendation` (Phase 14's final pick). They agree for 29098; the
  scenario metrics are unchanged by this phase.
- The JS bundle is one 1,046.81 kB chunk (not code-split).
- Gemini's quota is still exhausted, so approved analyses still show the
  templated explanation fallback (unchanged from Phase 29).
- Monte Carlo probabilities now display with one decimal (previously
  none) — a display change only.

## 17. Unexpected Findings

1. **`types/api.ts` was stale by one comment.** After Phase 29's regeneration
   I edited the `lookup` endpoint's docstring; the OpenAPI description
   changed but the generated file did not. The Phase 29 report's statement
   that it was byte-identical to a fresh generation was true when checked
   but stopped being true. Regenerated via the established process
   (comment-only diff); the report now carries a superseded note.
2. **The old Agent Activity list showed a success tick for a rejected
   outcome** — the terminal `rejected` event has status `completed`. The new
   view keys the icon off the outcome named by the node.
3. **Probability rounding hid information**: at 0 decimals Conservative
   0.12% displayed as "0%", and House Purchase's 50.28% displayed as "50%",
   right at the At Risk boundary. Both now show one decimal.
4. **Recharts 3 draws no SVG in `renderToString`.** My first harness had a
   check ("SVG bar labels show the API values") that passed only because the
   same numbers appear in the table — I caught it, removed it, and replaced
   the Recharts primitives with data-capturing stubs. The first run's other
   three failures were mistakes in my assertions (wrong capitalisation of
   "triggered", used twice; a "no weights" regex that matched compliance rule
   text mentioning QQQ), not application defects.
5. Vite 8's dev SSR loader kept inlining `react`; the harness was moved to a
   Vite SSR build with a temporary entry under `frontend/` (deleted after
   each run; verified none left).
6. The optimizer returns AGG = 1.665e-16 (floating-point residue, not exactly
   0). Compliance still passes and the UI shows 0%; the backend value was not
   touched.
7. The SSE captures needed for the Agent Activity checks persisted and then
   removed `recommendations` rows for 29098 and 29099; analysis ids and
   recommendation counts are unchanged afterwards.
8. Customer 29101 (Phase 29) and the externally-edited
   `backend/wealthpilot/config/settings.py` are unchanged; nothing in
   Phase 30 touched them.

## 18. Final Assessment

Completion criteria from the Phase 30 prompt:

| Criterion | Met | Evidence |
|---|---|---|
| Risk probability graph | Yes | §3.1, §11 (29098/29099/29100 data == API) |
| Emergency-fund graph | Yes | §3.2, §11 |
| Goals visualization; corrected Monte Carlo shown from the API | Yes | §3.3, §11 (94.1% / 50.3% / 88.6% / real 0.0%) |
| Portfolio allocation graph | Yes | §3.4, §11 (29098 weights unnormalised) |
| Savings-first shows no weights | Yes | §8, §11 (29099) |
| Rejected shows no approved allocation; compliance breakdown visible | Yes | §8, §11 (29100) |
| Pending-information works, no fabricated graph | Yes | §11 (29096, all six pages) |
| Scenario visualization (numeric data exists) | Yes | §3.8 |
| Agent Activity uses actual SSE data | Yes | §3.7, §11 (real captured events for all four personas) |
| Dashboard uncluttered | Yes | §3.9 (at most one chart) |
| No financial calculation added to React | Yes | §6 — one sign test, documented and judged presentation-only |
| No mock financial data added | Yes | none in the codebase; the harness's few synthetic scenario props are scratch-only and labelled |
| NULL never converted to zero | Yes | §7 |
| API types generated/authoritative | Yes | §13 (regenerated; identical to a fresh generation) |
| Recharts used; shadcn remains primary | Yes | §5 |
| Accessibility preserved | Source level only | §9 |
| Responsive layout preserved | Source level only | §10 |
| Backend tests pass | Yes | 763 / 3 skipped / 0 failed (§12) |
| tsc, oxlint (no new errors), build | Yes | §13 |
| 29098 / 29099 / 29100 / 29096 verified | Yes, via real API data and SSR data-binding — not in a browser | §11 |
| Documentation updated; report created | Yes | §14, this file |
| Git status audited; no unexplained changes | Yes | §15, §19 |

The two "source level only" rows and the untested chart *drawing* are the
honest ceiling of what this environment can show (no browser tool exists),
and they are what a reviewer should still look at by running the app once:
Risk (bars and labels), Financial Health / Goals (label room at narrow
widths), Portfolio (donut and key), Scenario Simulator (two series), and
Agent Activity during a live run. Nothing else was found wanting. The phase
changed no calculation and no backend behaviour; the only logic added beyond
formatting is one sign test that chooses a note.

## 19. Git Status

`git status --short` lists every top-level path as `??` (untracked): the
repository still has **0 commits**, so there is no staged state and no diff
baseline. Nothing was committed. The file classification in §15 was
reconstructed from modification times against the Phase 29 sign-off; every
changed file is expected (charts, pages, generated types, documentation, this
report). No file under `models/` or `datasets/` changed, no backend file
changed, and no unexplained file was found.
