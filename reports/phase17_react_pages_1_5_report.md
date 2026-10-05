# Phase 17 — React Pages 1-5 Report

## 1. Pages implemented

Dashboard, Customer Profile, Risk Assessment, Financial Health, and
Goals — the exact five pages this phase's prompt names, in the order it
names them. **A genuine naming/ordering discrepancy was found and
resolved, not silently guessed**: `MASTER_PROMPT.md` section 4 /
`BUILD_PLAN.md` section 13 name nine pages in the order Dashboard,
Customer Profile, **Financial Health**, **Risk Assessment**, Portfolio
Analysis, AI Recommendation, Why This Recommendation, Agent Activity,
Scenario Simulator — no page called "Goals" exists there at all, and
Risk Assessment/Financial Health are in the opposite order from this
phase's own list. Per this phase's own section 1 ("if the authoritative
documents use slightly different names, follow the authoritative
terminology") and its explicit, detailed, unambiguous section 22-25
specification for a "Goals" page, the CURRENT prompt's own ordering and
addition were followed: `nav-items.ts` now lists Dashboard → Customer
Profile → Risk Assessment → Financial Health → **Goals** → Portfolio →
Recommendation → Why This Recommendation → Agent Activity → Scenario
Simulator, and a new `/goals` route was added (never renaming or
removing any of the nine existing routes — section 56). "Financial
Health" (Phase 5: expense persona + behaviour drift) and "Goals" (Phase
7: feasibility, Monte Carlo, contribution gap) are genuinely different
backend data domains, so a dedicated Goals page is a defensible reading
of the original 9-page list's gap, not an invented page.

## 2. API endpoints consumed

- `GET /api/profiles/{profile_id}` — Customer Profile page (demographics
  + goal entries).
- `POST /api/analysis` — Dashboard, Risk Assessment, Financial Health,
  and Goals pages (one shared query per profile, see section 5) — this
  is the correct endpoint per Phase 15's own design: it returns a cached
  result when the profile hash is unchanged, so it functions as
  "fetch the current analysis" even though it is a `POST`.

No other endpoint was called from these five pages; no new endpoint was
requested from or added to the backend (section 54 — nothing was
missing).

## 3. Components created

- `providers/customer-context.tsx` — the minimum profile-selection
  mechanism (section 9): one `profileId`, `localStorage`-persisted, no
  new backend endpoint (there is no "list customers" API, so this is
  manual entry, not a search/picker).
- `components/shell/customer-selector.tsx` — replaces Phase 16's inert
  header placeholder with a working `Dialog`-based profile-id entry,
  linking to Customer Profile for creating a new one.
- `components/shell/status-badge.tsx` — one
  consistent status→icon+label+variant mapping reused by every page,
  covering every status vocabulary the API actually returns (compliance
  PASS/WARN/REJECT, recommendation approved/savings_first/
  blocked_rejected/failed, goal Feasible/At Risk/Not Feasible, emergency
  fund sufficient/insufficient) — always icon + text together (section
  29).
- `components/shell/no-profile-selected.tsx` — the shared "select a
  profile" empty state all five pages show when `profileId` is `null`
  (and, per section 44, none of them fires an API call in this state).
- `components/shell/section-unavailable.tsx` — the shared field-level
  "not available" state, distinct from page-level loading/error
  (section 34).
- `hooks/use-profile.ts`, `hooks/use-analysis.ts` — the two typed
  TanStack Query hooks every page uses (section 8/43).
- `lib/format.ts` — centralized `formatCurrency`/`formatPercent`/
  `formatDate`/`formatStatusLabel` helpers; each transforms exactly ONE
  already-authoritative value, never combines two source fields into a
  new figure (section 26 — see section 12 below for the full audit).

## 4. shadcn/ui components used

Existing (Phase 0/16): `Card`, `Badge`, `Button`, `Input`, `Alert`,
`Skeleton`, `Separator`, `Avatar`, `Tooltip`, `Dialog` (added this phase
via the established `npx shadcn@latest add` workflow — not hand-built).
Newly added this phase, same workflow: `Progress`, `Table`, `Label`.
Every one of these components is used somewhere across the five pages;
none was added speculatively. No component was manually recreated —
`npx shadcn@latest add progress table label dialog` produced all four
new files.

## 5. TanStack Query usage

`useAnalysisQuery(profileId)` (`queryKey: ["analysis", profileId]`) is
the SINGLE shared query Dashboard/Risk/FinancialHealth/Goals all call —
navigating between them for the same customer reuses one cached result
rather than re-issuing `POST /api/analysis` per page (section 43/45:
"the Dashboard must not independently calculate summary values... that
value must come from the same authoritative API data used by the Risk
Assessment page" — satisfied structurally, since they are literally the
same query-cache entry, not merely two calls that happen to agree).
`useProfileQuery(profileId)` similarly backs Customer Profile (and
Dashboard's profile card). No polling, no Redux/Zustand.

## 6. Recharts usage

None. Every numeric visualization in these five pages uses shadcn's
`Progress` (risk `confidence`, a goal's `monte_carlo_success_probability`
— both already authoritative `[0,1]` fractions from the API, the same
class of value the project's own "0.55 → 55%" formatting example covers)
or `Table` (risk `class_probabilities`). No Recharts chart was needed to
"materially improve understanding" for any value these five pages
actually have (section 37) — a full chart library render for a single
progress fraction would be decorative, not meaningful, so none was
added. Recharts remains available, unused, for a page where it earns its
place (e.g. Portfolio's efficient frontier, Phase 18).

## 7. Loading states

Every page uses the shared `LoadingState`/`PageLoadingState`
(`Skeleton`-based, from Phase 16) while its query is `isLoading` — never
a placeholder number.

## 8. Error states

Every page uses the shared `ErrorState` (RFC 7807-aware, from Phase 16)
with a `Try again` action wired to the query's own `refetch()`, for both
`useProfileQuery` and `useAnalysisQuery` failures.

## 9. Empty/unavailable states

Explicitly distinguished throughout (section 34), never collapsed into
one generic message:
- **No profile selected** → `NoProfileSelected` (a distinct state from
  "loading" or "error" — no query even fires).
- **Section genuinely unavailable** (API returned the field as `null`,
  usually with `unavailable_reason`) → `SectionUnavailable`, showing the
  API's own reason text verbatim when present (e.g. "FAR-Trans has no
  expense/liquid-asset data -- never fabricated" for a real customer,
  confirmed against the live API — section 18).
- **Genuinely empty** (a real, successful result with nothing to show,
  e.g. zero goals) → its own plain "No goals have been recorded"
  message, not conflated with "unavailable."

## 10. Accessibility

Preserved every Phase 16 standard (semantic `<h1>` per page via
`PageContainer`, focus-visible rings from unmodified shadcn primitives,
keyboard-navigable native controls). Added this phase: `Progress`
instances always carry an `aria-label` describing exactly what they
represent ("Model confidence", "`{goal}` success probability"); no
status is ever color-only (`StatusBadge` always pairs an icon with the
status's own text label); the `Table` in Risk Assessment uses real
`<th>`/`<td>` semantics via shadcn's `Table` primitives, so screen
readers can navigate it as a table, not a generic grid of `div`s.

## 11. Responsive behaviour

All five pages use the existing `PageContainer` (max-width, responsive
padding) and Tailwind responsive grid classes (`sm:grid-cols-2`,
`lg:grid-cols-3` on Dashboard; `sm:grid-cols-2`/`sm:grid-cols-3` on
Profile/Goals field grids) so content reflows to a single column below
the `sm` breakpoint — no desktop-only layout. See section 17 for the
same visual-verification disclosure as Phase 16 (no headless-browser
tool available).

## 12. Numerical authority

**Full audit of every arithmetic operation in the five pages' code**:
exactly two multiplications exist anywhere (`risk.confidence * 100` in
Risk Assessment, `goal.monte_carlo_success_probability * 100` in Goals)
— both single already-authoritative `[0,1]` API values scaled for a
`Progress` bar's 0-100 range, identical in kind to the project's own
explicitly-approved `0.55 → 55%` formatting example (section 26). **No
other arithmetic exists anywhere** — verified directly by grepping every
hand-written `.ts`/`.tsx` file for `calculateRisk`/`calculateReturn`/
`calculateSharpe`/`calculateGoalProbability`/`calculateAllocation` (zero
matches) and for any expression combining two DIFFERENT API fields
(e.g. `current_amount`/`required_amount` are both rendered via
`formatCurrency` as independent, un-related text values — never divided
against each other for an emergency-fund "percent funded" bar, which
would have been a genuinely new derived ratio, not formatting). Risk
category, goal feasibility, compliance decision, and recommendation
status are all rendered EXACTLY as the API returns them via
`StatusBadge`/direct string display — never classified, computed, or
altered in React.

## 13. Mock-data verification

**NONE FOUND.** Every value rendered across all five pages traces to a
`useProfileQuery`/`useAnalysisQuery` field. Verified directly: grepped
all Phase 17 source files for hard-coded financial-looking literals —
no match outside the two authoritative `* 100` scalings already audited
in section 12. Every genuinely missing/unavailable field renders
`SectionUnavailable`/"Not available" — confirmed against a REAL live
backend response for two real FAR-Trans customers (section 17) showing
`financial_health.expense_persona: null` with its real
`unavailable_reason` string, which the Financial Health page renders
verbatim rather than substituting a 0 or a sample persona.

## 14. Security verification

Grepped every Phase 17 source file for `gemini`/`api_key`/`database_url`/
`postgresql://`/`secret`/`password` — no match beyond pre-existing
documentation comments already present from Phase 16 (which themselves
describe the "never expose a secret" principle, not a secret itself). No
Gemini call exists anywhere in the frontend (section 39) — all
explanation content is Phase 13's, reached only through
`AnalysisResult.explanation` on a later page. No direct database or ML
artifact access (sections 40/41) — every page goes through `api-client.ts`
only.

## 15. TypeScript/build results

```text
npx tsc -b            0 errors
npm run build          succeeds (dist/ produced; ~538 KB JS / ~76 KB CSS,
                        gzipped ~172 KB / ~13 KB — a chunk-size advisory
                        warning only, not an error; no code-splitting
                        was introduced, out of this phase's scope)
npm run lint (oxlint)  0 errors, 6 warnings (all the same pre-existing
                        shadcn-generated-file / colocated-hook patterns
                        already accepted in Phase 16, plus one new
                        instance of the identical pattern in
                        customer-context.tsx)
```

## 16. Tests

No frontend test runner exists in this project (confirmed again this
phase) and `CLAUDE.md`'s approved stack does not name one — per section
47's own instruction ("if none exists, do NOT introduce a new test
framework without asking"), none was added. The same TypeScript/build/
lint bar as Phase 16 was used instead, plus the additional real-data
verification in section 17 below.

**Backend regression** (section 58, required even though this phase
touches no backend code): full project suite re-run after all frontend
changes: `697 passed, 3 skipped, 0 failed` — identical to Phase 16's
count, confirming zero backend impact from this phase.

## 17. Browser verification

**No headless-browser/screenshot tool is available in this environment**
(same disclosed limitation as Phase 16) — literal in-browser visual
inspection (section 42's "If a browser is available, manually inspect
all five pages") could not be performed, and is disclosed here rather
than claimed.

What WAS verified, beyond Phase 16's HTTP-routing smoke test (all ten
routes, including the new `/goals`, correctly serve the SPA shell):
a REAL FastAPI backend was started locally and called directly (not
through the frontend, since no browser automation exists) for two real
FAR-Trans customers, and the exact JSON field names/shapes returned were
checked one-by-one against every field access in the five pages' code —
`risk.{risk_category,confidence,class_probabilities,model_version,
data_source,unavailable_reason}`, `profile.{customer_id,name,age,income,
employment_status,customer_type,investment_capacity,goals,data_source,
created_at}`, and a REJECT-status customer's populated-but-null
`financial_health`/`emergency_fund`/`compliance` objects (confirming the
`SectionUnavailable`/`StatusBadge` code paths receive exactly the shape
they expect) all matched precisely, with zero field-name mismatches
found. This is real-data verification of the data-binding logic, not a
substitute for seeing the rendered page, and is disclosed as exactly
that distinction.

## 18. Known limitations

- No in-browser visual verification (section 17).
- No frontend test runner (section 16).
- "Goals" required adding a page/route beyond the original nine named in
  `MASTER_PROMPT.md`/`BUILD_PLAN.md` — documented and justified in
  section 1, not silently done.
- Recharts remains unused (section 6) — correctly deferred, not a gap.
- The customer selector is manual-id-entry only (no customer search/list
  UI), since no such backend endpoint exists and adding one was out of
  this phase's scope (section 9/54).

## 19. Phase 18 boundary

Portfolio Analysis, AI Recommendation, Why This Recommendation, Agent
Activity, and Scenario Simulator all remain EXACTLY their Phase 16
`PagePlaceholder` implementations — confirmed unmodified by direct
diff/read of each file. No Recharts chart, no detailed
recommendation/portfolio visualization, no Q&A interface, and no
scenario-comparison UI exist anywhere in this phase's code.

## Next phase

Phase 18 — React Pages 6-9.

Do not begin Phase 18.
