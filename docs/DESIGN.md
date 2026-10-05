# WealthPilot AI — Frontend Design System

Documents the actual frontend visual/interaction system as implemented.
shadcn/ui is the sole primitive component system — no second one exists
or should be introduced.

## 1. Design Principles

Display-only, never computational (`docs/RULES.md` Rule 6). Honest about
missing data — an unavailable value is shown as unavailable, never as a
blank that could be mistaken for zero. Consistent shell across every
protected page (`components/shell/`). Minimal, targeted polish over
redesign — Phase 25's own audit found the codebase "already carefully,
consistently built phase-by-phase" and scoped its changes to a small
number of genuine gaps rather than a rewrite; that stays the default
posture for any future UI work.

## 2. Visual Language

Clean, data-dense financial-dashboard aesthetic: cards for grouped
content, badges for status/category labels, tables for tabular data,
muted secondary text, a single accent color for interactive elements and
current-state indicators.

## 3. Colors

Theme-token-driven via Tailwind + shadcn's CSS variables
(`frontend/src/index.css`) — light and dark both supported through the
same token set; no hard-coded hex color inside a component. Status colors
follow `StatusBadge`'s own mapping (`components/shell/status-badge.tsx`),
never re-derived ad hoc in a page.

There is no brand color token and no page-specific palette: every page —
dashboard, Login, and the public Home and About pages — uses the same `:root` /
`.dark` semantic tokens, whose `primary` is neutral (near-black in light mode,
near-white in dark). See section 32.

## 4. Typography

Geist Variable (`@fontsource-variable/geist`), loaded once globally. Page
titles use `PageContainer`'s own heading; card titles use `CardTitle`;
body/secondary text uses Tailwind's muted-foreground utility — never an
inline font-size override.

## 5. Spacing

Tailwind's default scale throughout; page-level vertical rhythm via
`space-y-4` on the page's outer container (established in every page
under `pages/`) — new pages should match this rather than inventing a
different rhythm.

## 6. Layout

`AppShell` (sidebar + header + content) wraps every protected,
non-onboarding page. The public Home page at `/` (section 29), `/login`,
`/create-user`, and the two
`/onboarding/*` pages are standalone (no sidebar) — a distinct, deliberate
visual language for the "not yet in the main app" flows, established in
Phase 20-22.

## 7. Sidebar

`AppSidebar` groups navigation into three labeled sections — **Overview**
(Dashboard), **Customer** (Profile, Risk Assessment, Financial Health,
Goals), **Analysis** (Portfolio, AI Recommendation, Why This
Recommendation, Agent Activity, Scenario Simulator) — Phase 25's own
grouping, the current standard. `nav-items.ts` exports `NAV_GROUPS` (the
source of truth) and derives a flat `NAV_ITEMS` list from it.

## 8. Header

Fixed, sticky top bar: sidebar trigger, current page title (a
non-heading location label, not a second `<h1>`), theme toggle,
`AccountIdentity` (read-only — shows "Demo Account" or the real
customer's name, never a raw id, never an editable control), sign-out.
No customer-switching control exists here or anywhere (Phase
post-login-fix; `docs/DECISIONS.md` ADR-021).

## 9. Cards

`Card`/`CardHeader`/`CardTitle`/`CardDescription`/`CardContent` is the
default content container for any grouped result. An icon (lucide-react)
in the title is the established convention for "what this card is about"
at a glance.

## 10. Tables

`Table`/`TableHeader`/`TableBody`/`TableRow`/`TableCell` for tabular data
(class-probability breakdowns, allocation tables) — never a hand-rolled
`<div>` grid pretending to be a table.

## 11. Forms

`Field`/`FieldGroup`/`FieldLabel`/`FieldDescription`/`FieldError` (the
shadcn Field primitives) for every form — established consistently across
Login, Create User, onboarding Goals, and the Phase 28 Financial Inputs
card. Client-side validation is limited to required/numeric-format/
obviously-invalid-value checks (`docs/RULES.md` Rule 6) — never a
financial calculation performed to validate a field.

## 12. Buttons

`Button` with `variant="outline"` for a secondary/form-submit action,
default variant for the primary action on a page, `variant="destructive"`
reserved for genuinely destructive actions (none currently exist in the
authenticated app). A pending mutation disables its triggering button and
shows a distinct in-progress label (e.g. "Saving…", "Signing in…") rather
than a spinner-only state.

## 13. Alerts

`Alert`/`AlertTitle`/`AlertDescription`, with an icon, for both
informational callouts (e.g. Dashboard's "Next step" guidance) and
destructive/error states (`variant="destructive"`) — always paired with a
lucide icon, never color alone conveying meaning.

## 14. Badges

`Badge` for compact status/category labels (risk category, compliance
decision via `StatusBadge`, "Demo Account" indicator). Status meaning is
never conveyed by color alone — an icon or text label always accompanies
it.

## 15. Progress Indicators

`Progress` for a bounded [0,1] value already computed by the backend
(model confidence, Monte Carlo probability) — the bar's fill is the exact
API value, never re-derived.

## 16. Charts

Recharts only (no other chart library), in `components/charts/` — a
display-only layer (`docs/DECISIONS.md` ADR-029). Every chart component
takes typed props, makes no API call and contains no financial, ML,
recommendation or compliance logic; it plots the API value unchanged.
Shared presentation constants (axis text, tooltip, series and slice colours
from the theme tokens, so light/dark both work) live in
`components/charts/chart-theme.ts`.

| Chart component | Where it appears | API field(s) plotted | Backend source |
|---|---|---|---|
| `RiskProbabilityChart` | Risk Assessment | `risk.class_probabilities` (API order; `risk.risk_category` only picks the darker bar) | Risk Analyst (`models/risk`) |
| `EmergencyFundChart` | Financial Health; Portfolio and Dashboard on a savings-first result | `emergency_fund.required_amount`, `.current_amount` (bars); `.shortfall`, `.sufficient` (text) | Phase 28 financial inputs + `core/goals.py::assess_emergency_fund` |
| `GoalTargetChart` | Goals (one per goal) | `goals[].nominal_target_amount`, `.inflation_adjusted_target_amount` | Goal Analyst / `core/goals.py` |
| `PortfolioAllocationChart` | Portfolio, Recommendation, Dashboard (approved only) | `recommendation.weights` | Recommendation engine (Phase 14) over the optimizer (Phase 8) |
| `ScenarioComparisonChart` | Scenario Simulator | `ScenarioSummary.expected_return`, `.expected_volatility`, `.sharpe_ratio` | Portfolio section of each scenario's analysis |
| `AgentPipeline` | Agent Activity | SSE `node`, `status`, `duration_ms`, `summary`, `model_version` | `GET /api/analysis/stream` |

Rules every chart follows:

- **Unavailable, never zero.** A `null` input renders `SectionUnavailable`
  with the API's own reason. There is no zero-length bar, empty donut or
  0% placeholder. A savings-first result has no allocation, so the donut is
  replaced by "Savings-first: portfolio allocation deferred." and the
  emergency-fund chart; a rejected or pending result shows no chart at all
  (a rejected one shows the compliance breakdown, section 25).
- **Not the only representation.** Each chart sits beside an existing table
  or text carrying the same values, and has a `role="img"` `aria-label`
  listing them. Series are named (axis category, legend or key), never
  distinguished by colour alone; the darker/lighter pair means "selected /
  other" and is explained in text.
- **One axis, one unit.** Goal amounts, monthly contributions and
  probabilities are never combined; return/volatility and the unitless
  Sharpe ratio are separate charts. The risk chart's 0–100% axis is a
  fixed presentation scale.
- **No ranking.** Nothing is scored, sorted by a derived metric, or labelled
  best/winner/recommended. The scenario chart compares; it does not decide.
- **Responsive.** Charts sit in `ResponsiveContainer` inside a fixed-height
  block; layouts stack under Tailwind's `lg:` breakpoint.
- **Not built (no authoritative data):** a portfolio risk/return or
  efficient-frontier chart — the API exposes one portfolio point, not
  frontier data.

Recommendation page: no numeric chart was added. Its authoritative content
is status, strategy, rationale, provenance and compliance, which stay as
cards and badges; only the allocation donut (now the shared
`PortfolioAllocationChart`) appears there for an approved result.

Goals page: the Monte Carlo probability is shown with one decimal (94.1%,
not 94%) beside the existing progress bar, and the feasibility badge is the
backend's `feasibility` string. When `contribution_gap` is negative the
value is shown unchanged with the note "Contribution exceeds the calculated
requirement." (`core/goals.py` defines the gap as required minus planned
contribution, so negative means ahead of plan).

Dashboard: at most one chart — the approved allocation, or the emergency
fund on a savings-first result — and none otherwise.

## 17. Loading States

`LoadingState`/`PageLoadingState` (`components/shell/loading-state.tsx`)
— consistent skeleton/spinner treatment, never a blank screen during a
fetch.

## 18. Empty States

`NoProfileSelected` (protected pages when no customer is associated —
copy distinguishes "genuinely missing association" from "not yet
chosen," since there is no chooser) and `OnboardingNoProfile` (the
standalone onboarding-page equivalent, since `AppShell`'s header is not
present there).

## 19. Unavailable States

`SectionUnavailable` — shown whenever a specific result is `null` with an
`unavailable_reason`, rendering that reason's text plainly rather than
hiding the section or showing a fabricated placeholder.

## 20. Error States

`ErrorState` — renders `ApiClientError.problem.title`/`.detail` (never a
stack trace or raw exception) with a retry action wired to the query's
own `refetch()`.

## 21. Responsive Design

Tailwind responsive utilities throughout (`sm:`/`md:`/`lg:` breakpoints on
grid/flex layouts); the sidebar collapses on narrow viewports via
shadcn's own `Sidebar` primitive behavior. No page-specific breakpoint
system exists outside this.

## 22. Accessibility

Real heading hierarchy per page (a page-level `<h1>`, never duplicated by
the header's location label); `aria-label`/`aria-current` on navigation
and status indicators already established; accessible form errors
(`FieldError`, associated via `aria-invalid`); keyboard navigation
preserved through shadcn's own primitive behavior — never overridden with
a custom, less-accessible control. See `docs/RULES.md` Rule 24: a UI
change must not regress an existing accessibility property.

## 23. Financial Information Presentation

Every currency value formatted via `lib/format.ts::formatCurrency`, every
percentage via `formatPercent` — the same two functions everywhere,
never an inline `.toFixed()`/string-template computation that could
silently diverge in rounding behavior from the canonical formatter.
Raw, unrounded API values are what these functions receive — no
pre-rounding happens before the API response reaches the component
(CLAUDE.md rule 2, and Phase 14's "exact weights, unmodified" contract).

## 24. AI Explanation Presentation

Why This Recommendation page renders Gemini's (or the fallback's)
per-section prose next to the already-shown structured result it
explains — never as a replacement for the structured data, always
alongside it, with the standard educational-prototype disclaimer always
visible.

The two sources are labelled apart (Phase 31). The prose card is titled
"Explanation (wording only)", says the AI only writes wording and never
calculates or decides, and carries a badge: "AI-written wording, checked
against the computed numbers" when `validation_passed` is true, or "Template
restatement of the computed results" when it is false. The false case also
shows an alert saying an AI-written explanation was not used — the service
was unavailable or out of quota, or its wording did not pass validation —
and that no number in the text was produced by AI (the old alert blamed
numerical validation alone, which was wrong for a quota failure). The
"Deterministic factors" card says these are computed by the backend's models
and rules, not by the AI; for a savings-first result it states that no
investment strategy is selected rather than "Not available".

**Simple / Detailed** (ADR-037). The page opens on a `Tabs` control labelled
"Explanation style": **Simple** (default) and **Detailed** (the two cards
above, unchanged). The Simple view is written for someone with no financial
background, as a column of cards:

1. **Your financial summary** — a status badge and one sentence chosen by the
   outcome: plan proposed; savings first; stopped by a safety check; more
   information needed; or could not be completed. It also states the risk
   profile.
2. **Emergency fund** — *Available now*, *Calculated requirement* and
   *Shortfall* as large figures (all from the API), plus one sentence keyed on
   `sufficient`. It is shown only when there are figures or a backend reason
   they are missing.
3. **Your goals** — per goal: target, target date (joined from the profile by
   id), the calculated probability and its feasibility badge, and "It is an
   estimate, not a promise."
4. **Investment plan** — every weight in a table, then one sentence naming only
   the holdings that display above 0%. A weight of 1e-16 is not called an
   investment; the table still shows it as 0%.
5. **Why this result?** — the factors actually present, "made by WealthPilot's
   own models and rules; the AI only writes the wording", and for a rejection
   the rule that stopped the plan.
6. **Important points** — one statement per backend status, never a comparison
   between two values.
7. **Next steps** — neutral: complete missing information, keep building
   savings (savings-first only), keep information and goals up to date.
8. **Words explained** — only the terms this analysis involves (for example
   Monte Carlo simulation, diversification, volatility, Sharpe ratio, savings
   first).
9. The disclaimer: the analysis's own canonical disclaimer, or the prototype
   disclaimer when there is no explanation.

Developer-worded backend reasons never appear as the sentence itself, only as
a small "Technical detail:" line.

## 25. Compliance Presentation

The Recommendation page renders `components/shell/compliance-breakdown.tsx`
(`ComplianceBreakdown`, added in Phase 29) for every analysis result that
reached compliance: the overall decision badge, the rules version, and
each rule's `description`, a triggered/passed indicator (icon + text,
never color alone), and — for a triggered rule — the backend's own
`reason` string, verbatim. This appears in the Compliance card for an
approved result and, for a REJECT (where the API returns no
recommendation), in its own Compliance card beneath the generic
"blocked by a compliance rule" notice, so the exact triggered rule(s) and
reason(s) are visible rather than hidden behind a generic message. **Before
Phase 29 this was NOT the case** — the API always supplied
`compliance.rule_results`, but no page rendered it; earlier phase reports
and demo material that described a rule breakdown "on the Recommendation
page" were describing intent, not what the UI actually showed. The Why
This Recommendation page states plainly when no explanation exists
because compliance rejected the profile (or because more information is
required).

## 26. Household Presentation (Phase 32)

The Customer Profile page has a **Household** card
(`components/profile/household-card.tsx`), placed after Goals and before
Financial Inputs. Phase 32 gave it identity and membership; Phase 33 added the
household's own financial records (section 26a). The frontend performs no
arithmetic on any of it — the member count is the API's `member_count`, and
every currency figure is one stored record's own value.

- **No household:** "No household created yet." with a labelled "Household
  name" input (placeholder "Not created yet", never a pre-filled value) and a
  "Create Household" button that stays disabled until a name is typed. Opening
  the page never creates a household.
- **Household exists:** four read-only stats — Household (name), Your role,
  Relationship, Members — and a "View Household" toggle
  (`aria-expanded`) that reveals the member table.
- **Member table:** Name, Relationship, Role (formatted from the API's
  values), a "You" badge on the caller's own row, and — for the primary member
  only — an Actions column. Non-primary rows have "Remove" (a two-step
  Confirm / Cancel; the button's accessible name includes the member's name);
  the primary row says "Cannot be removed". A non-primary member sees no
  Actions column and no add form, only "Only the household's primary member can
  add or remove members."
- **Add member (primary only):** an info alert titled "Prototype association"
  says the form adds an existing customer by profile ID and "does not let you
  view, edit or switch into their account"; fields are "Existing profile ID"
  (whole number > 0, form-shape validation only), Relationship (spouse, parent,
  child, sibling, other — `self` is reserved) and Role (member, dependent —
  `primary` cannot be assigned). This is a labelled prototype association, not
  a customer selector: the authenticated customer remains the active user.
- **States:** loading uses `LoadingState`; an RFC 7807 error (for example a 403
  or 409) uses `ErrorState` with the problem's own title and detail and a
  retry; the member table's own error keeps the summary visible.

## 27. Household Financial Records (Phase 33)

"View Household" now opens a `Tabs` control (`aria-label="Household sections"`)
whose first tab is the Phase 32 **Members** table, followed by **Income**,
**Expenses**, **Assets** and **Liabilities**. All four render the same
config-driven component,
`components/profile/household-finance-section.tsx`.

- **Framing first.** Each tab opens with a one-line note in muted text stating
  what is *not* happening — "No total is calculated", "Nothing is totalled, and
  essential expenses are not summed", "they are not market prices and are never
  revalued or optimised", "No debt ratio, schedule or interest is calculated".
  There is no summary row, no totals row, no chart and no derived figure
  anywhere in this card, and none may be added (`docs/DECISIONS.md` ADR-032).
- **Tables** carry only the record's own stored columns: Income
  (Source, Amount, Frequency, Active); Expenses (Category, Description, Amount,
  Frequency, Essential, Active); Assets (Name, Type, Current value, Liquid);
  Liabilities (Name, Type, Outstanding, Monthly payment). Controlled values are
  displayed through `formatStatusLabel`, money through `formatCurrency`, and
  booleans as Yes/No.
- **Null is never zero.** A value the API returns as `null` renders as
  "Not provided" — a liability with no recorded monthly payment reads
  "Not provided", while a liability whose outstanding amount really is zero
  reads as a formatted 0. The same distinction is carried into the form: an
  optional money field is placeholdered "Not provided" and an empty one is
  submitted as `null`, never as `0` or `""`.
- **Primary member:** an "Add <record type>" button and per-row Edit and Delete
  buttons whose accessible names include the record ("Edit Home loan",
  "Delete Home loan"); Delete is a two-step Confirm / Cancel, matching the
  member table. Add and Edit open the same `Dialog`, titled "Add …"/"Edit …"
  and described as "Stored for the household exactly as entered. Nothing is
  calculated from it."
- **Any other member:** the identical tables with no Actions column and no
  dialog, plus "Only the household's primary member can add, edit or delete
  financial records."
- **Form shape only.** The dialog validates required fields, numeric input and
  sign (amount > 0; value/outstanding ≥ 0) and shows one destructive `Alert` —
  a mirror of the API's rules, never the enforcement point. A rejected request
  surfaces through `ErrorState` as the RFC 7807 problem's own title and detail.
  `is_essential` and `is_liquid` deliberately start **unselected**: they are the
  household's judgement and are never pre-guessed.
- **States:** `LoadingState` while the list loads, `ErrorState` with retry on
  failure, and a plain sentence for empty ("No income has been recorded for
  this household yet.") — the empty state is never an implied zero.

**Phase 35 metadata.** Each record dialog gained an optional **Notes** field
(all four types), assets and liabilities an optional **Description**, and
liabilities an optional **Interest rate** — entered as a decimal with the
helper text "0.0425 means 4.25%", exactly as the Phase 28 financial-inputs form
treats rates. The tables show the new columns; an absent value reads "Not
provided", a recorded 0% rate reads "0.00%", and the liabilities tab's lead
note states that the rate is recorded for reference only and nothing is
calculated from it. Notes use the existing single-line `Input` (no textarea
primitive exists in the project).

**Phase 36 goals.** A sixth tab, **Goals**, uses the same config-driven table
and dialog: Name, Goal type, Target amount, Current amount, Target date,
Active, Notes. A new `date` field kind uses the native date input and sends the
ISO string unchanged. An unrecorded current amount reads "Not provided"; a
recorded 0 reads "€0". Goals are listed in the order they were added, with no
ranking, priority or feasibility wording. Above the table, one muted line
restates the financial summary's *calculated* emergency-fund requirement for
reference and says that a goal's own target does not change it — a displayed
API value, never a calculation.

## 27a. Household Financial Summary (Phase 34)

Expanding "View Household" now shows a bordered **Financial summary** block
above the tabs (`components/profile/household-financial-summary.tsx`). It is
read-only and display-only: every figure arrives already computed from the API,
and the component performs no arithmetic at all.

- **Framing.** A lead paragraph states that the backend calculated the figures
  from the household's own records, that nothing is scored or ranked, that no
  recommendation follows, and that "Not provided" means not recorded rather
  than zero.
- **Recurring monthly view:** recurring monthly income, recurring monthly
  expenses (with essential and other beneath it) and monthly cash flow, over a
  note explaining that yearly amounts count as one twelfth per month and that
  one-time records are never treated as recurring.
- **One-time records** are shown in their own labelled block, so they can never
  be mistaken for part of the monthly view.
- **Assets and liabilities** are a table — total assets, of which liquid,
  outstanding liabilities, recorded monthly liability payments, net position —
  with a note that net position is assets less liabilities and excludes income
  and expenses.
- **Emergency fund:** required, current liquid assets, shortfall and a status
  `Badge` reading Sufficient, Insufficient or Unknown. The target is stated in
  words ("6 months of the household's recurring essential expenses"), and the
  block says explicitly that no advice or action follows from it.
- **What is recorded:** one neutral badge per area (Income, Expenses, Assets,
  Liabilities, Emergency fund) reading Available or Unavailable — never a
  percentage or a completeness score.
- **Null versus zero** is preserved exactly as in section 27: `null` renders as
  "Not provided" and a stored `0` renders as a formatted zero.
- **No ranking.** No score, percentage, rating, progress bar or good/bad colour
  coding appears. The emergency-fund badge uses the neutral `outline` variant
  for every status, so the status is read from its text, never from colour
  alone.
- **States:** `LoadingState` while the summary loads, `ErrorState` with retry on
  failure, and for any section the backend marks unavailable, its own
  `unavailable_reason` sentence in muted text instead of a number.
- **Structure:** each block is a `<section>` with its own `<h4>` and
  `aria-labelledby`, nested under the card's existing heading level.

## 28. Demo Experience

The header's "Demo Account" badge (icon + text, never color alone) is the
only demo-specific UI treatment — no separate demo visual theme, no demo
-only component variant. The demo customer's data renders through the
exact same components every real customer's data does.

## 29. Public Home Page

`/` renders `pages/home-page.tsx` — public (outside `ProtectedRoute`),
standalone (outside `AppShell`), and static: no API call, no customer context,
no calculation. The Dashboard lives at `/dashboard` and is the default
post-login destination. Sections, in order, from `components/home/`: navbar
(`home-navbar.tsx` — brand, in-page links Home / How It Works / Features,
Login / Get Started; below `md` a shadcn `Sheet` menu; a signed-in session sees
"Open Dashboard" instead), hero with an illustrative dashboard preview, How It
Works (four steps), Features, the backend / Gemini / frontend explainability
split, Individual + Household, the demo call-to-action, and the footer. (The
public pages carry no separate disclaimer section, removed 2026-10-02 at the
user's request; the dashboard keeps its own.)

- **Numbers.** The only figures are the hero preview's fixed sample values,
  each labelled "Illustrative"; they are constants, never computed and never a
  real or demo customer's data. No usage, savings, accuracy or return claims.
- **Features.** Only capabilities that exist as pages in the app. Expense
  segmentation is not advertised (unavailable for analysed customers, ADR-010);
  household copy states there is no household risk score or recommendation.
- **Demo entry.** "Explore Demo", "Individual Demo" and "Family Demo" link to
  `/login?demo=individual|family`; the hint only focuses and highlights the
  matching existing demo button. Signing in still happens through the Login
  page's own actions — no new account, credential or seed.
- **In-page links** are real `<a href="#id">` anchors enhanced by
  `section-nav.ts::scrollToSection` (smooth unless reduced motion is preferred,
  then focus moves to the section; `scroll-mt-16` clears the sticky navbar).
- **Style.** The dashboard's own semantic tokens only (sections 3 and 32); no
  gradients, glass effects, decorative animation or new fonts. Skip link to
  `#main-content`; semantic `header` / `nav` / `main` / `section` / `footer`.

## 30. User-Facing Terminology

WealthPilot separates user-facing terminology from technical/model
terminology. Backend/API values remain unchanged while the frontend presents
plain-language labels to improve accessibility for non-finance users.
Technical details remain available for transparency and project evaluation.

- **One mapping.** `frontend/src/lib/terminology.ts` is the only place a raw
  value becomes a label: investments (`QQQ` → "Nasdaq-100 / US Growth",
  `AGG` → "US Bond Market", `GLD` → "Gold"), strategies (`risk_conditioned` →
  "Risk-Based Strategy", `mvo` → "Optimized Portfolio", `hrp` →
  "Risk-Balanced Portfolio", `equal_weight`/`1/N` → "Equal Allocation"),
  capacity codes (`CAP_80K_300K` → "Capacity band: €80K–€300K" — a
  classification, never called wealth), metrics ("Expected variability" for
  volatility, "Risk-adjusted performance" for the Sharpe ratio), statuses
  (`PASS` → "Passed", `REJECT`/`rejected` → "Not approved"), compliance rules
  (by rule id) and analysis steps (node id → "Assessing risk"). Lookups only —
  no calculation; an unknown value falls back to the raw value, never hidden.
  Pages never keep their own translation tables.
- **Technical details.** `components/shell/technical-details.tsx` — a native
  `<details>`, collapsed by default, keyboard operable — holds the raw API
  value, method name, ticker, rule id, rules/model version and artifact path
  (`models/risk`) behind each plain label. Items render as a definition list,
  so values never run together.
- **Help.** `components/shell/help-tip.tsx` — the shadcn Tooltip behind a "?"
  button (hover, focus or tap; Escape closes), with the same text linked by
  `aria-describedby`. Short, factual, never promotional; nothing essential
  lives only in a tooltip.
- **Unavailable.** `SectionUnavailable` takes a plain `message` ("Expense
  insights unavailable — this analysis needs linked income and expense
  information…"); the backend's developer-facing reason moves to Technical
  details, never removed, and unavailable is never shown as 0.
- **Errors.** `ErrorState` shows plain wording by HTTP status class; the
  problem body's status/title/detail stay in Technical details.
- **Numbers.** Unchanged: every figure is the API's value through the existing
  `lib/format.ts` formatters; no demo value is hard-coded anywhere.
- **Wording.** No "guaranteed", "safe", "best", "risk-free" or "you will
  earn"; estimates are called estimates. A rejected or blocked result is
  never worded or styled as an approval.


## 31. About This Project Page

`/about` renders `pages/about-page.tsx` — public, static, outside `AppShell`,
sharing the Home page's navbar (an "About" link) and footer; the app sidebar
links to it from a "Project" group. It explains the project to non-finance
readers and evaluators in 21 numbered sections, each a plain explanation with
technical detail in collapsed `TechnicalDetails`. Layout primitives live in
`components/about/about-ui.tsx` (`AboutSection`, `InfoCard`, `Callout`,
`FlowSteps`, `DataTable`).

- **Every figure is a documented project result**, copied from its source and
  cited on the page: `models/metrics.json`, `reports/phase2_data_quality_report.md`,
  `reports/phase3_leakage_audit.md`, `core/goals.py`, `agents/graph.py`. Nothing
  is computed in React; no chart is drawn for a metric; no customer id appears.
- Methods are described as "selected for this implementation", never as
  universally best; AutoGen is stated as built but not invoked live; the market
  result is stated as "no significant improvement over the naive baseline".
- Tables have captions and scoped headers and scroll inside themselves on narrow
  screens; diagrams are ordered lists with decorative arrows hidden from
  assistive technology.

## 32. Public-Page Color Tokens

Public pages must consume semantic theme tokens rather than page-specific
hard-coded colors. The dashboard's theme is the reference: Home (`/`), About
(`/about`), their shared navbar, footer and mobile menu resolve exactly the same
`:root` / `.dark` tokens as the dashboard — there is no public-only override,
no brand token, no hex/rgb/hsl value and no Tailwind palette class
(`bg-blue-*`, `text-slate-*` …) in public-page files.

| Role | Token | Used for on public pages |
|---|---|---|
| Primary | `primary` / `primary-foreground` (neutral) | Primary buttons, brand mark, accent text and icons |
| Secondary | `secondary` / `secondary-foreground` | Icon tiles, the demo panel |
| Surfaces | `background`, `card`, `muted` | Page, cards and callouts, banded sections |
| Text | `foreground`, `muted-foreground` | Body and descriptions |
| Lines | `border`, `border-primary/30` | Card borders, separators, highlighted callouts |
| Status | `destructive` | Compliance REJECT step only |

- Muted text is kept on `background`/`card`, not on `secondary`/`muted`
  surfaces, where it measures below 4.5:1 in light mode (4.35:1); text on the
  secondary demo panel uses `secondary-foreground`. Measured across every muted,
  primary and destructive text element on Home and About: minimum 4.58:1 light,
  6.94:1 dark.
