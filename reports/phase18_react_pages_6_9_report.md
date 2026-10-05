# Phase 18 — React Pages 6-9 Report

## 0. Page-count resolution (section 1's own gate)

This phase's own section 1 frames the remaining work as "four pages,"
tentatively suggesting Recommendation and Why This Recommendation might
be combined, but makes that conditional: "If the authoritative documents
clarify that these are four pages with Recommendation + Why This
Recommendation combined, follow the exact documented route/page
structure... If the authoritative documents conflict about the four
pages: STOP AND ASK ME." Checked directly: `MASTER_PROMPT.md` section 24
("AI RECOMMENDATION PAGE" — Recommendation, Why?, Supporting evidence,
Risk considerations, Goal impact, Market context, Compliance status,
Disclaimer) and section 25 ("WHY THIS RECOMMENDATION PAGE" — Risk model
factors, SHAP feature importance, Expense behaviour, Goal probability,
Portfolio optimization factors, Market regime, Compliance checks) are two
separate, differently-scoped numbered sections; `BUILD_PLAN.md`'s own
page table (section 13) lists them as two separate rows. Neither document
combines them, so the prompt's own conditional does not trigger — no
conflict exists to stop-and-ask about, since the documents agree with
each other (just not with the "four pages" framing). This phase therefore
implements the five real pages Phase 16 already scaffolded as five
separate routes (Portfolio, Recommendation, Why This Recommendation,
Agent Activity, Scenario Simulator) — no page was invented, none was
merged, and this phase's own sections 7-35 in fact give five distinct,
fully-detailed specifications anyway, consistent with this reading.

## 1. Pages implemented

Portfolio Analysis, AI Recommendation, Why This Recommendation?, Agent
Activity, Scenario Simulator — all five, replacing their Phase 16
placeholders with real, API-backed implementations. No route was added,
renamed, or removed; no Phase 17 page was modified.

## 2. API endpoints consumed

- `POST /api/analysis` (via the existing `useAnalysisQuery`, Phase 17) —
  Portfolio, Recommendation, Why This Recommendation.
- `GET /api/analysis/stream` — Agent Activity (a NEW `EventSource`
  connection per explicit "Start analysis" click, via Phase 16's
  `lib/sse-client.ts`, unmodified).
- `POST /api/scenarios/compare` — Scenario Simulator (a NEW
  `useScenarioCompare` mutation hook).

No new endpoint was requested or added (section 50 — nothing was
missing).

## 3. Portfolio implementation

Reads `AnalysisResult.recommendation` — **not** the raw
`AnalysisResult.portfolio` field — and this is a deliberate, documented
choice, not an oversight: `portfolio` reflects whatever strategy the
Phase 11 graph happened to run (defaults to `"mvo"` for every customer,
per Phase 10/11), while `recommendation` is Phase 14's own final,
risk-conditioned pick, which can genuinely differ. Showing `portfolio`
directly here could silently disagree with the Recommendation page,
violating section 46's "the Recommendation page and Portfolio page must
display the same authoritative recommendation/portfolio data... use the
same values" — satisfied structurally by both pages reading the identical
field from the identical cached query. Displays: selected strategy badge
(`MVO`/`HRP`/`EQUAL_WEIGHT`, exact API string, upper-cased for display
only — the underlying value is never altered), expected return/volatility/
Sharpe (`PortfolioMetrics`), and the allocation (chart + table, see
section 9). `blocked_rejected`/`savings_first`/`failed` each render their
own distinct `Alert` — never an approved allocation (section 12).

## 4. Recommendation implementation

The same `recommendation` object, in more detail: full status-specific
branches for all four states (section 14), the structured
`rationale.reasons` list rendered verbatim as an unordered list (never
paraphrased or regenerated), goal/market preference alignment shown as
plain text, and a provenance footer (`phase14_version`,
`risk_model_version`, `compliance_rules_version`, `evaluated_at`). The
`blocked_rejected` branch is a separate, standalone `Alert` block placed
*before* any allocation/metrics JSX in the component tree — structurally
impossible for it to also render an approved strategy underneath, not
merely hidden by a condition (section 15).

## 5. Why This Recommendation implementation

Two clearly separated sources, per section 19/21:
1. **Gemini's prose** (`AnalysisResult.explanation`'s nine fields,
   Phase 13's own validated output) — rendered verbatim via a shared
   `ProseSection` renderer, never regenerated, never re-derived.
2. **The same deterministic structured factors** the Risk Assessment/
   Financial Health/Goals pages already show — risk category, compliance
   decision, every goal's feasibility, market regime per instrument, and
   the selected strategy — read from the SAME cached `AnalysisResult`,
   using `StatusBadge`/plain badges, never independently inferred prose
   like "the model chose HRP because..." (section 19's explicit
   prohibition). When `explanation.validation_passed` is `false` (Phase
   13's own templated-fallback path), a small `Alert` discloses that a
   simplified, source-derived explanation is shown instead of a
   generated one — itself read directly from the API's own
   `validation_passed` field, not inferred.

## 6. Agent Activity implementation

A single "Start analysis" `Button` (no auto-connect on mount — see
section 7 for why), a vertical timeline (`ScrollArea` + an ordered list)
of `NodeProgressEvent`s, each showing node name, a status icon
(`CheckCircle2`/`XCircle`/`CircleAlert`, never color alone —
`aria-label`led), duration in ms, and the backend's own short `summary`
string. Nothing else is rendered — there is no field in
`NodeProgressEvent` for a prompt or a reasoning trace to occupy (section
23), verified directly against a REAL stream (section 17).

## 7. SSE implementation

Reuses Phase 16's `lib/sse-client.ts` completely unmodified — no SSE
parsing was duplicated (section 24). A new `hooks/use-analysis-stream.ts`
owns the connection lifecycle: `start()` always closes any previous
`EventSource` first (at most one connection open at a time — section 27),
does not auto-connect on mount (React 18/19 StrictMode double-invokes
effects in development, which would otherwise silently start two real
backend pipeline runs), and stops listening the moment an
`analysis_completed` event arrives. No automatic reconnection exists at
all — a failed/finished stream simply stays finished until the user
clicks "Start analysis" again, the simplest safe strategy the section
27's "bounded and safe... do not accidentally create duplicate analysis
executions" allows.

**REJECT terminal behaviour (CRITICAL, section 26)** — inherited
unmodified from Phase 15's own backend contract (`agents/recommendation.
py`/`api/services/analysis_service.py`'s `PipelineRun.events()` only
emits `recommendation`/`explanation` progress events when the run's
overall status is `approved`): confirmed directly against a real stream
(section 17) that the events end at `analysis_completed` with no
`recommendation`/`explanation` event when the run does not reach
`approved` — the frontend renders exactly what arrives, so this
guarantee is enforced entirely server-side and simply passed through
faithfully here.

## 8. Scenario Simulator implementation

A form (two `Select`s, one per scenario, values `mvo`/`hrp`/
`equal_weight`/"risk-conditioned default") submits a
`ScenarioCompareRequest` built from the CURRENT customer context's
`profileId` for BOTH scenarios (section 38 — never a different/
hard-coded customer; the exact generated `components["schemas"]
["ScenarioCompareRequest"]`/`ScenarioParameters` types are used, no
hand-written duplicate interface). A `useMutation`-based
`useScenarioCompare` hook calls `POST /api/scenarios/compare` — nothing
is computed locally; the result `Table` renders every `ScenarioSummary`
field (`risk_category`, `portfolio_strategy`, `expected_return`,
`expected_volatility`, `sharpe_ratio`, `compliance_decision`,
`recommendation_status`, `goal_feasibility`) directly, side by side, with
no ranking, "best scenario" label, or derived comparison metric of any
kind (section 32).

## 9. shadcn/ui components used

Existing (Phase 0/16/17): `Card`, `Badge`, `Alert`, `Button`, `Separator`,
`ScrollArea`. Newly added this phase, via the established
`npx shadcn@latest add` workflow: `Tabs` (installed for the "prefer"
list's coverage but not ultimately needed by any of the five pages'
final layout — left available, unused, matching the same precedent
Phase 16 set with `ScrollArea` before this phase found a real use for
it), `Select` (Scenario Simulator's strategy pickers). Already-added-but-
now-actually-used-for-the-first-time: `Progress` is not used this phase
(Recharts covers Portfolio's visualization instead); `Table` is used in
both `AllocationTable` and the Scenario comparison. No component was
manually recreated.

## 10. Recharts usage

`AllocationChart` — one donut `PieChart` per allocation, fed directly
from `recommendation.weights` with **zero** local normalization,
sorting, or synthetic data (section 45): the `data` array is built with
a single `Object.entries(weights).map(...)`, nothing else. Always
rendered alongside `AllocationTable` (the same weights, as an accessible
`<table>`) — the chart is never the sole representation (section 9). A
`role="img"` + full `aria-label` listing every asset/percentage covers
screen readers that can't parse the SVG. The `Tooltip` formatter only
calls the existing `formatPercent` helper — no new arithmetic.

## 11. TanStack Query usage

`useAnalysisQuery` (Phase 17, unmodified) backs Portfolio/Recommendation/
Why This Recommendation — the same cache entry per profile all three
share, so they can never independently disagree (section 46). A new
`useScenarioCompare` uses `useMutation` (an explicit user-triggered
action, correctly not a passive query — section 37). No polling anywhere;
Agent Activity's SSE stream is deliberately NOT modeled as a TanStack
Query (a genuinely different kind of state — a long-lived push
connection, not a request/response the library's cache model fits) —
its own small `useAnalysisStream` hook is the appropriate tool instead,
per section 24's "React state/query patterns appropriate for a streaming
process."

## 12. Loading states

Portfolio/Recommendation/Why This Recommendation reuse the Phase 16/17
`LoadingState`. Scenario Simulator's submit button shows "Comparing…"
and disables itself while `mutation.isPending` (preventing duplicate
submissions). Agent Activity shows an inline "Connecting…" row with a
spinning icon while the stream is opening. No page fabricates a value
while loading.

## 13. Error states

Portfolio/Recommendation/Why This Recommendation reuse the Phase 16
`ErrorState` with `refetch()`. Scenario Simulator shows `ErrorState` for
a failed mutation with a `reset()`-based retry. Agent Activity shows a
dedicated `Alert` for a stream-level error (section 34's distinct
"we couldn't load..." vs "not available" vs "loading" categories are
preserved throughout, not collapsed).

## 14. Unavailable states

`blocked_rejected`/`savings_first`/`failed`/missing-weights are each
their own distinct message, never conflated (sections 12/15/16/17): a
blocked recommendation says so explicitly and shows nothing that looks
approved; a savings-first state says investment optimization is
deferred, never showing a "stale" allocation as if active; a failed
state shows the API's own `blocking_reason` text, never a fabricated
strategy.

## 15. Accessibility

Preserved every Phase 16/17 standard. Additions this phase: the pie
chart carries a full text `aria-label` (never chart-only information —
section 40's "for portfolio charts: provide equivalent textual/table
information," satisfied by the always-present `AllocationTable`); status
icons in Agent Activity are `aria-label`led, never color-only; the
Scenario form's `Select`s each have an associated `Label` via `htmlFor`/
`id`; the "Start analysis" button's label changes to "Running…" while
active so its state is announced, not just visually indicated.

## 16. Responsive behaviour

All five pages use the existing `PageContainer` plus responsive grid
classes (`sm:grid-cols-2`, `lg:grid-cols-2` for Portfolio's chart/table
pair, `sm:grid-cols-2` for the Scenario form) so content stacks to one
column on narrow viewports; the Recharts `ResponsiveContainer` makes the
pie chart itself resize with its parent rather than overflowing. See
section 22 for the same visual-verification disclosure as Phases 16/17.

## 17. Numerical authority

**Full audit performed, identical rigor to Phase 17**: grepped every new
`.tsx`/`.ts` file for `calculateRisk`/`calculateReturn`/`calculateSharpe`/
`calculateGoalProbability`/`calculateAllocation`/`calculatePortfolio`/
`monteCarlo(` — zero matches. Grepped for any arithmetic operator
(`*`/`/`) across every new page/component file with a pattern narrow
enough to exclude import paths and prose — the ONLY matches were import
statements, JSDoc comments, and JSX text; **zero actual arithmetic
expressions exist anywhere in Phase 18's code** (the pie chart's
percentages are computed by Recharts itself from the raw `weight`
values, and `formatPercent`'s own `× 100` scaling is Phase 17's
already-audited, unmodified helper — not new code this phase). No weight
is normalized, re-summed, or sorted by a derived metric (section 45); no
"best scenario" score exists (section 32); no new expected-return/
volatility/Sharpe formula exists anywhere (section 5).

**Verified against a REAL live backend, not just static inspection**
(section 22): a real `GET /api/analysis/stream` transcript and a real
`POST /api/scenarios/compare` response were fetched for an actual
FAR-Trans customer and checked field-by-field against every place this
phase's code reads those shapes — `NodeProgressEvent`'s five fields and
`ScenarioSummary`'s nine fields both matched exactly, confirming the
unavailable-state code paths (null `expected_return`, null
`compliance_decision`, etc.) receive precisely the shape they were
written to expect.

## 18. Mock-data audit

**NONE FOUND.** Grepped for hard-coded sample-looking values
(`0.55`/`0.30`/`0.15`/bare `55`/`30`/`15` and equivalents) across every
new page and `components/portfolio/` file — zero matches. Every number
any of the five pages can render traces to a field on
`AnalysisResult`/`ScenarioCompareResponse`/`NodeProgressEvent`.

## 19. Security audit

Grepped every Phase 18 source file for `gemini`/`api_key`/`database_url`/
`postgresql://`/`secret`/`password` — zero matches (not even in a
comment this time, since none of these files needed to discuss the
principle directly). No direct Gemini call, no direct database access,
no `.pkl`/`.keras`/dataset load anywhere — every one of the five pages
goes through `api-client.ts`/`sse-client.ts` only.

## 20. TypeScript/build/lint

```text
npx tsc -b            0 errors
npm run build          succeeds (dist/ produced; ~916 KB JS / ~85 KB CSS,
                        gzipped ~283 KB / ~14 KB — a chunk-size advisory
                        only, from adding Recharts; no code-splitting
                        was introduced, out of this phase's scope)
npm run lint (oxlint)  0 errors, 7 warnings (the same pre-existing
                        shadcn-generated-file / colocated-hook patterns
                        already accepted in Phase 16/17, plus one new
                        instance in the freshly-generated tabs.tsx)
```

One real, transient build failure was found and fixed during this
phase's own development: Recharts declares `react-is` as a required peer
dependency, which the project's existing `--legacy-peer-deps` npm
install policy (needed for a pre-existing, unrelated Phase 0 TypeScript/
openapi-typescript version conflict — see `reports/phase16_react_shell_
report.md` section 8) silently skipped, causing `vite build` to fail
resolving `"react-is"` from inside `recharts/es6/util/ReactUtils.js`.
Fixed by installing `react-is` explicitly — a required transitive
dependency of the already-approved `recharts` package, not a new
top-level library choice.

## 21. Tests

No frontend test runner exists in this project (confirmed again this
phase) — none was added without asking, per section 54. The same
TypeScript/build/lint bar as Phases 16-17 was used, plus the real-backend
field-shape verification in sections 17/22.

**Backend regression** (section 69, required even though this phase
touches no backend code): full project suite re-run after all frontend
changes: `697 passed, 3 skipped, 0 failed` — identical to Phase 17's
count, confirming zero backend impact from this phase.

## 22. Browser verification

**No headless-browser/screenshot tool is available in this environment**
(the same disclosed limitation as Phases 16-17) — section 61's "if a
browser is available, manually inspect all Phase 18 pages" could not be
carried out, and is disclosed here rather than claimed.

What WAS verified, beyond the HTTP-level routing smoke test (all ten
routes still correctly serve the SPA shell after this phase's changes):
a real FastAPI backend was started and called directly for
`GET /api/analysis/stream` and `POST /api/scenarios/compare` against a
real FAR-Trans customer, with the exact response shapes checked against
every field this phase's code reads (section 17) — this is real-data
verification of the data-binding and SSE-parsing logic, not a substitute
for seeing the rendered page, and is disclosed as exactly that
distinction, matching Phase 17's own precedent.

## 23. Known limitations

- No in-browser visual verification (section 22).
- No frontend test runner (section 21).
- Neither live-verification customer used in this phase's development
  reaches an `approved` recommendation status (the same disclosed
  FAR-Trans emergency-fund-data-gap characteristic `reports/
  phase17_react_pages_1_5_report.md` and `reports/phase15_fastapi_
  report.md` already document) — the `approved` rendering branches of
  Portfolio/Recommendation (allocation chart, metrics, rationale
  alignment text) and a populated Agent Activity `recommendation`/
  `explanation` event were verified by careful code review and exact
  API-field-name matching against the generated types, but not against a
  live `approved` response, since none exists among the customers
  available to test with in this environment.
- `Tabs` remains installed but unused (available for a future page).

## 24. Phase 19 boundary

No evaluation, accuracy review, performance review, or final
documentation/reporting work was performed — this phase implemented UI
pages only, exactly as scoped.

## Next phase

Phase 19 — Final Evaluation / Verification.

Do not begin Phase 19.
