# Phase 16 — React Shell Report

## 1. Objective

Build the production-style React application shell: routing foundation,
global layout, navigation, responsive structure, theme foundation,
reusable shell components, a typed API client, TanStack Query, generated
API type integration, loading/error boundaries, and basic accessibility.
No dashboard, analysis page, chart, questionnaire, scenario UI, or Q&A
interface was implemented — every one of the nine required pages is a
clean, honest placeholder. No financial calculation and no mock financial
data exist anywhere in this phase's code.

**shadcn/ui was used as the primary UI component system.**

## 2. Frontend architecture

Built on the EXISTING Phase 0 scaffold — React 19, Vite 8, TypeScript 6
(strict), Tailwind CSS 4, shadcn/ui (the project's `base-nova` / Base UI
style, `components.json`), `lucide-react`. Two dependencies were added,
both explicitly pre-approved by `CLAUDE.md`'s own stack list (not new,
unapproved packages — see section 8's dependency note): `react-router`
(v8, the current unified package superseding `react-router-dom`) and
`@tanstack/react-query` (v5). `recharts` was deliberately NOT installed —
section 30 permits configuring it "only if already required," and no
chart exists in this phase.

File layout (new):

```text
frontend/src/
  App.tsx                        route definitions
  main.tsx                       provider composition + root render
  vite-env.d.ts                  typed import.meta.env
  types/problem-details.ts       hand-written RFC 7807 type (section 9)
  lib/
    api-client.ts                the one centralized typed fetch layer
    sse-client.ts                SSE subscription foundation (section 26)
    query-client.ts              QueryClient instance + defaults
  providers/theme-provider.tsx   light/dark/system theme context
  components/
    error-boundary.tsx           top-level React error boundary
    shell/
      app-shell.tsx              SidebarProvider + Sidebar + Header + Outlet
      app-sidebar.tsx            primary navigation (shadcn Sidebar)
      header.tsx                 top bar: trigger, page label, theme, profile placeholder
      nav-items.ts                the 9 pages, in the documented order
      page-container.tsx         per-page heading + content wrapper
      page-placeholder.tsx       shared empty-state for all 9 pages
      disclaimer.tsx             the exact approved disclaimer text
      theme-toggle.tsx           light/dark/system switch
      loading-state.tsx          Skeleton-based loading placeholders
      error-state.tsx            RFC 7807-aware error display
    ui/                          shadcn primitives (existing 4 + 9 added this phase)
  pages/                          one file per required page (+ NotFoundPage)
```

`frontend/src/types/api.ts` was regenerated (not hand-edited) against the
current Phase 15 OpenAPI schema, via the pre-existing `npm run
generate-types` script — this file is the sole source of truth for every
request/response type the API client uses.

## 3. Routes established

The exact nine pages `MASTER_PROMPT.md` section 4 / `BUILD_PLAN.md`
section 13 both require, in their documented order — no additional route,
none renamed, none removed:

| # | Page (as named in the docs) | Route |
|---|---|---|
| 1 | Home / Dashboard | `/` |
| 2 | Customer Profile | `/profile` |
| 3 | Financial Health | `/financial-health` |
| 4 | Risk Assessment | `/risk-assessment` |
| 5 | Portfolio Analysis | `/portfolio` |
| 6 | AI Recommendation | `/recommendation` |
| 7 | Why This Recommendation? | `/why-this-recommendation` |
| 8 | Agent Activity | `/agent-activity` |
| 9 | Scenario Simulator | `/scenarios` |

Plus a catch-all `*` route rendering `NotFoundPage`. URL slugs themselves
are this phase's own reasonable, low-risk routing choice — the
authoritative documents name pages, not literal paths, so there was
nothing ambiguous to stop-and-ask about; page CONTENT for all nine
remains entirely Phase 17/18's responsibility.

## 4. Shell components

`AppShell` (SidebarProvider + Sidebar + Header + `<Outlet />` + footer
disclaimer), `AppSidebar` (primary navigation, built entirely from
shadcn's `Sidebar`/`SidebarMenu`/`SidebarMenuButton` primitives), `Header`
(sidebar trigger, current-page label, theme toggle, a minimal
"no profile selected" placeholder), `PageContainer` (the per-page `<h1>` +
description + content wrapper every page uses), `PagePlaceholder` (the
shared empty-state card all nine pages render), `Disclaimer`,
`ThemeToggle`, `LoadingState`/`PageLoadingState`, `ErrorState`,
`ErrorBoundary`. Each is small and focused (section 28) — no monolithic
`App.tsx`; `App.tsx` itself is 33 lines of route definitions only.

## 5. Navigation

`AppSidebar` renders the nine pages via `NAV_ITEMS` (one shared source of
truth also used to derive the header's current-page label), each with a
`lucide-react` icon — no emoji. The active route is identified via
`SidebarMenuButton`'s `isActive` prop (driven by `useLocation()`) and
carries `aria-current="page"` on the underlying link for assistive
technology, in addition to shadcn's own active-state styling — state is
never communicated by color alone. Every nav item is a real `<Link>`
(via base-ui's `render` prop), so keyboard Tab/Enter navigation works
natively; icon-only controls (the sidebar trigger, the theme toggle) both
carry an explicit `aria-label`.

## 6. Responsive behaviour

Entirely from shadcn's `Sidebar` primitives, unmodified: below the 768px
breakpoint (`use-mobile.ts`, shadcn's own generated hook, untouched), the
sidebar automatically becomes a `Sheet`-based off-canvas panel opened via
the header's trigger — no separate mobile navigation system was built
(section 13: "Do not build a completely separate custom sidebar system if
the shadcn Sidebar component is available"). `PageContainer` and the
placeholder cards use responsive Tailwind classes (`max-w-6xl`, `sm:`
breakpoints) so content reflows rather than overflowing at tablet/mobile
widths.

**Disclosed limitation**: this environment has no headless-browser/
screenshot tool available, so responsive behaviour was verified
structurally (the breakpoint value, the Sheet-based mobile path being
shadcn's own unmodified, already-shipped mechanism, `npx tsc --noEmit
--strict` catching any prop misuse) and via an HTTP-level SPA-routing
smoke test (every route, including a 404, correctly serves the shell), NOT
by visually opening the app in a browser at each viewport width. Section
42's "manually inspect the application in a browser" instruction could not
be fully carried out — disclosed here rather than silently skipped or
claimed as done.

## 7. Theme/design system

Preserved the existing Tailwind + shadcn token setup in `src/index.css`
completely unmodified (light/dark CSS variables, sidebar-specific tokens,
chart tokens, radii) — no new visual identity, no gradient, no
glassmorphism, no decorative financial imagery. The only addition is the
runtime SWITCH itself (`ThemeProvider`, `useTheme`, `ThemeToggle`):
light/dark/system, persisted to `localStorage`, listening for OS
preference changes while in `system` mode. No new dependency (no
`next-themes`) — a ~50-line context/hook using only `localStorage` and
`matchMedia`.

## 8. API client

`lib/api-client.ts` is the SOLE place any `fetch()` call to the backend
exists (section 8: "do not scatter raw fetch() calls throughout
components"). Every request/response type is imported from the generated
`types/api.ts`'s `components["schemas"]` — never a hand-duplicated
interface (section 7/38). Base URL comes from `VITE_API_BASE_URL`
(`.env.example` provided, default `http://localhost:8000` for local dev
only — section 24: not hard-coded elsewhere in the codebase, verified by
direct grep). Every non-2xx response is parsed as an RFC 7807 body and
thrown as a typed `ApiClientError`; a network-level failure (backend
unreachable) is distinguished as `ApiUnreachableError` so `ErrorState` can
show the right message for each case (section 20).

**Dependency note**: `react-router` and `@tanstack/react-query` were
installed. Both are explicitly named in `CLAUDE.md`'s own approved stack
("React Router · TanStack Query · Recharts") from the very start of this
project — installing them completes an already-approved stack rather than
introducing a new one, so this did not require a stop-and-ask (section 35
gates a package NOT already approved). `--legacy-peer-deps` was needed
for the `npm install` step due to a PRE-EXISTING Phase 0 peer-dependency
mismatch (`typescript ~6.0.2` vs. `openapi-typescript@7.13.0`'s `^5.x`
peer requirement) — not introduced by this phase's packages, not
resolved by downgrading TypeScript (a Phase 0 configuration decision
outside this phase's scope), and not something that affects `tsc`'s own
actual compilation, which passes cleanly.

## 9. TanStack Query

`lib/query-client.ts` exports one `QueryClient` (created in `main.tsx`,
provided via `QueryClientProvider`), with sensible, non-aggressive
defaults (`staleTime: 30s`, `refetchOnWindowFocus: false`, no polling of
any kind) and a retry policy that treats a 4xx `ApiClientError` as
deterministic (never retried) and anything else as possibly transient (up
to 2 retries) — no Redux, no Zustand, no other global state library.

## 10. Generated API types

`frontend/src/types/api.ts` was regenerated against the live Phase 15
OpenAPI schema (the file previously on disk was a stale Phase 0
placeholder with only `/api/health`) using the EXISTING `npm run
generate-types` script — not created new, not hand-edited. All 9
`components["schemas"]` entries and 9 `operations` entries are present
and used directly by `api-client.ts`.

## 11. Error handling

- `ErrorBoundary` — a class component catching any unexpected render-time
  error, showing a fixed, safe message and a "Return to dashboard"
  action; the actual error is only ever `console.error`'d (local
  debugging), never rendered (section 19).
- `ErrorState` — the reusable, RFC-7807-aware display used for a failed
  API call; shows only `problem.title`/`problem.detail` (safe by
  construction — Phase 15's own contract guarantees no stack trace/secret
  ever appears there) or a fixed "service unavailable" message when the
  backend cannot be reached at all.
- `types/problem-details.ts` — the hand-written `ProblemDetails` type
  (justified: FastAPI's OpenAPI export has no way to describe a
  hand-raised domain exception's response shape, so nothing was generated
  for it — section 9).

## 12. Accessibility

- Semantic HTML: `<header>`, `<main id="main-content">`, `<footer>`, one
  `<h1>` per page (`PageContainer`), a "Skip to main content" link that
  is visually hidden until focused.
- Every icon-only interactive control has an `aria-label` (the sidebar
  trigger, the theme toggle) or an accessible tooltip (the customer-
  context placeholder).
- Keyboard navigation: every nav item and action is a real `<a>`/
  `<button>` element underneath (base-ui's `render` composition, not a
  `<div onClick>`), so Tab/Enter/Space work natively; no keyboard trap was
  introduced.
- Focus states: shadcn's existing `focus-visible:ring-*` utility classes
  are used throughout (unmodified from the generated components) — never
  overridden or removed.
- The active nav item is marked with `aria-current="page"` in addition to
  its visual style — state is never conveyed by color alone.
- Loading states use `role="status"`/`aria-live="polite"` with a visually
  hidden label, so a screen reader announces "Loading…" without needing
  to see the skeleton shapes.

**Disclosed limitation**: no `jsx-a11y`-equivalent lint plugin is
configured in this project's `.oxlintrc.json` (a pre-existing Phase 0
choice — oxlint's bundled `react`/`typescript`/`oxc` plugins don't include
one), so accessibility here was applied by hand/review rather than
lint-enforced; adding such a plugin was not done without asking, since it
is a linting-configuration change beyond a shell phase's obvious scope.

## 13. Loading states

`LoadingState`/`PageLoadingState` render shadcn `Skeleton` blocks only —
never a fake number, percentage, or allocation standing in for real data.
Nothing in this phase's code currently triggers them (no page fetches
data yet — that begins in Phase 17/18), but they exist as the shared
primitive those later pages will use, matching section 18's "create
reusable loading/fallback components" scope.

## 14. Security

- No API key, database URL, or other backend secret exists anywhere in
  `frontend/` — verified by direct grep across all hand-written source
  files (only comments describing the "never a secret" principle
  matched).
- `VITE_API_BASE_URL` is the only environment variable exposed to client
  code — a public base URL, not a credential (`.env.example` documents
  this distinction explicitly).
- No hard-coded `localhost:8000` outside the single, centralized
  `api-client.ts` fallback default (verified by grep).
- No stack trace, chain-of-thought, prompt, or AutoGen transcript is ever
  rendered — `ErrorBoundary`/`ErrorState` both show only fixed, safe text
  or the RFC-7807 `title`/`detail` Phase 15 already guarantees is safe.
- No authentication was added or assumed (matches the documented "local
  prototype, no auth" scope carried over from Phase 15).

## 15. Testing

No frontend test runner (Vitest, Testing Library, etc.) exists in this
project yet, and `CLAUDE.md`'s approved stack does not name one — adding
one would be a genuinely new dependency, which section 35 gates behind a
stop-and-ask, and section 32 itself only asks to "use the project's
existing frontend testing setup IF PRESENT." None is present, so none was
added. Verification instead relied on the minimum bar section 34 itself
specifies: `npx tsc -b` (strict TypeScript compilation), `npm run build`
(production build), and the already-configured `npm run lint` (oxlint) —
all three pass cleanly (sections 16/18 below). This is disclosed as a
deliberate scoping decision, not an oversight.

## 16. Build verification

```text
npx tsc -b            0 errors
npm run build          succeeds (dist/ produced, ~495 KB JS / ~73 KB CSS, gzipped ~160 KB / ~13 KB)
npm run lint (oxlint)  0 errors, 5 warnings (all pre-existing shadcn-generated-file patterns
                        or an equivalent colocated-hook pattern already used by sidebar.tsx itself)
```

An HTTP-level SPA-routing smoke test against the production build
(`vite preview`) confirmed every one of the nine routes, plus an unknown
path, returns 200 with the SPA shell (`<div id="root">`, correct
`<title>`) — client-side routing and the 404 fallback both work at the
serving level.

**Backend regression** (section 39/45 — required even though this phase
touches no backend code): full project suite re-run after all frontend
changes: `697 passed, 3 skipped, 0 failed` — identical to the count at
the end of Phase 15, confirming zero backend impact from this phase.

## 17. Known limitations

- No literal in-browser visual inspection was performed (no
  headless-browser tool available in this environment) — see section 6's
  disclosure. Structural/compile-time/HTTP-level verification was
  performed instead.
- No frontend test runner exists; verification relies on strict
  TypeScript, production build, and lint only (section 15).
- The customer-context header placeholder is inert (no real profile
  selection yet) — intentionally, per section 23's "create only the
  required shell placeholder now."
- `Avatar`/`Tooltip`/`DropdownMenu`/`Sheet`/`ScrollArea` are all
  installed and at least one is used; `ScrollArea` currently has no
  call site (kept available, per the user's own "components to prefer"
  list, for a later phase's longer content areas).
- `--legacy-peer-deps` was required for `npm install` due to a
  pre-existing Phase 0 TypeScript/openapi-typescript peer-dependency
  mismatch, unrelated to and not resolved by this phase.

## 18. Phase 17 boundary

No dashboard logic, financial chart, questionnaire form, scenario
comparison UI, Q&A interface, or detailed recommendation visualization
was implemented — all nine pages are the shared, honest `PagePlaceholder`
empty-state. No financial calculation utility (`calculateSharpe`,
`calculateReturn`, etc.) exists anywhere, and none was found to already
exist from an earlier phase either (nothing to flag/ask about).

## Next phase

Phase 17 — React Pages 1-5.

Do not begin Phase 17.
