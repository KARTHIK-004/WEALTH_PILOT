# Phase 20 — Login Page & Prototype Authentication Report

## 1. Objective

Add a dedicated, standalone entry point (`/login`) to WealthPilot AI's
React frontend so the application no longer opens directly into the
Dashboard with an already-selected `Profile #1`. This phase is scoped
strictly to the login/entry experience — no ML/AI logic, no backend
endpoint, no database schema, and no financial calculation of any kind was
touched, per the phase's own explicit boundary.

## 2. Login Page

A new route, `frontend/src/pages/login-page.tsx`, registered at `path="login"`
in `App.tsx` as a **sibling** of the protected route tree — not nested
inside `<AppShell>`. It therefore renders none of the Dashboard sidebar,
header, or navigation: no `AppSidebar`, no `Header`, no `CustomerSelector`,
no per-page nav links.

**Revised layout** (per direct user feedback with a reference screenshot of
shadcn's own `login-02` two-column block, requesting that exact structure
instead of the initial centered single-card composition): a full-height
`grid lg:grid-cols-2` split. The left column pins a small brand mark
("WealthPilot AI" + the same `GraduationCap` icon `AppSidebar` already
uses) top-left, then centers the bare login form in the remaining space,
with the educational disclaimer beneath it. The right column is a
decorative panel, `hidden` below the `lg` breakpoint exactly like the
reference — since no real cover-photo asset exists for this project, it is
a CSS-only gradient panel (no external image fetched or hosted) carrying a
large icon and the "Agentic AI-based decision-support prototype" tagline
plus a one-line description, rather than a stock photo. Forgot-password,
social login, and "Sign up" all remain absent, and the Demo Account panel
remains directly visible on the form side — unchanged from the requirement,
only the surrounding layout changed.

## 3. shadcn login-02

Added via `npx shadcn@latest add login-02` (the exact command the user
specified), which created `src/components/ui/field.tsx` (new),
`src/components/login-form.tsx` (new), and updated `src/components/ui/
separator.tsx` (a one-line, purely additive `"use client"` directive —
confirmed via `--diff` before accepting the overwrite; no behavioral
change in this Vite/CSR app). `button.tsx`/`input.tsx`/`label.tsx` were
reported identical and left untouched. The registry's own `cn` dependency
was already present in `package.json` (`"cn": "^0.3.0"`) — confirmed
unchanged before and after, so **no new dependency was actually added**.

The CLI only pulls `login-02`'s form COMPONENT into a Vite project — its
registry entry also defines a page-level `registry:page` file
(`blocks/login-02/page.tsx`, the actual two-column layout with a top-left
brand mark and a cover-image panel) that targets a Next.js `app/login/
page.tsx` path this project doesn't have, so the CLI silently skipped it.
`npx shadcn@latest view login-02` was used to retrieve that page-level
source directly from the registry so its layout could be reproduced by
hand in `pages/login-page.tsx` (the "Acme Inc." placeholder and stock photo
replaced with WealthPilot AI's own brand mark and an on-brand CSS panel, as
above) — this is still an adaptation of the official block, not a
from-scratch custom design.

`login-form.tsx` was then adapted in place (not left as a parallel unused
file, and no separate hand-built design was created instead — "adapt, don't
replace," per this phase's own instruction): the original template's
**"Forgot your password?" link, "Login with GitHub" social button, and
"Sign up" link were all removed**. It is now a bare `<form>` (no `Card`
wrapper), matching the reference screenshot's flatter, cardless look
directly on the panel background. The `Field`/`FieldGroup`/`FieldLabel`/
`FieldSeparator`/`FieldError`/`FieldTitle` primitives are the CLI-generated
ones, unmodified. The submit button was relabeled "Sign In" per this
phase's explicit copy requirement (the template's default was "Login").

## 4. Authentication Approach

**Prototype authentication only — not production-grade identity/security
infrastructure.** Before writing any code, `backend/wealthpilot` was
searched for a `User` model, password hashing, token/session
infrastructure, and any `/api/auth`-style route or reference to
`login`/`password`/`jwt`/`OAuth2` outside of Gemini's own unrelated
`max_output_tokens` parameter — none exist. Per the phase's own explicit
instruction for this exact situation ("If there is NO real authentication
system: DO NOT invent a production-grade authentication backend... implement
a small isolated prototype authentication layer on the frontend ONLY"), no
backend endpoint, database table, password hash, JWT, or session store was
created. This did not require a STOP-and-ask, since the phase's own text
gives the fallback instruction directly for the "no existing auth system"
case that inspection confirmed applies here.

The implementation is three small frontend files:

- `frontend/src/lib/prototype-auth.ts` — the single demo credential
  (`DEMO_EMAIL`/`DEMO_PASSWORD`) as an explicitly-documented, isolated
  constant, plus `isValidPrototypeCredential(email, password)`, a plain
  client-side string comparison. The file's own header comment states
  plainly that this is not secure and must never be described as
  production authentication.
- `frontend/src/providers/auth-context.tsx` — `AuthProvider`/`useAuth()`,
  holding one boolean, `isAuthenticated`, backed by a `localStorage` flag
  (`wealthpilot-prototype-authenticated`) — the same persistence mechanism
  `customer-context.tsx` already uses for the active profile id, chosen for
  consistency rather than introducing a new pattern. No token, no expiry,
  no server round-trip.
- `frontend/src/components/shell/protected-route.tsx` — a route-guard
  component (`<Navigate to="/login" state={{from: location}} replace />`
  when unauthenticated, `<Outlet />` otherwise).

No authentication library was added — no Redux, Zustand, Auth0, Firebase
Auth, Clerk, or Supabase Auth. `useState` + `localStorage` + React Context,
matching the project's existing `customer-context.tsx` pattern exactly.

## 5. Demo Account

Displayed directly and legibly on the login page (never hidden) inside a
bordered "Demo Account" panel:

```text
Demo Account
Email: demo@wealthpilot.ai
Password: WealthPilotDemo@2026
[ Use Demo Account ]
```

Clicking "Use Demo Account" fills both fields and immediately submits the
same `login()` call the manual form uses — no separate, parallel code path
— then navigates to the originally requested route (or `/` if none). Since
this credential is intentionally public/displayed on-screen, it is
documented as non-sensitive by design; no real personal credential was
used anywhere.

## 6. Protected Routes

Every existing application route is now nested under `ProtectedRoute` in
`App.tsx`: `/` (Dashboard), `/profile`, `/risk-assessment`,
`/financial-health`, `/goals`, `/portfolio`, `/recommendation`,
`/why-this-recommendation`, `/agent-activity`, `/scenarios`, and the `*`
(404) route — the **actual route paths discovered in `App.tsx`**, not the
illustrative `/risk`/`/dashboard`-style names the phase prompt used as
examples. Only `/login` sits outside the guard. The guard is a real router
redirect (`<Navigate>`), not merely a hidden sidebar link, so direct URL
navigation to any protected path while unauthenticated is redirected to
`/login`, and the originally requested path is preserved in router state so
a successful login returns the user there rather than always to `/`.

## 7. Logout

Added a "Sign out" button to the existing header (`components/shell/
header.tsx`), next to the existing `CustomerSelector` control — the header
itself was not redesigned; one button was added. Clicking it calls
`logout()` (clears the `localStorage` auth flag only) and navigates to
`/login`. It does not touch `customer-context.tsx`'s stored profile id, any
database row, any `analysis_runs`/`agent_logs` record, or any customer
record — logout ends only the prototype login session, exactly as
specified.

## 8. Accessibility

- Email and Password each have a real `<label>` via `FieldLabel` (built on
  the existing `Label` primitive) with a matching `htmlFor`/`id` pair.
- Both inputs use semantic `type="email"` / `type="password"` and
  `autoComplete="username"` / `"current-password"`.
- "Sign In" and "Use Demo Account" are both plain `<button>` elements —
  keyboard-reachable and activatable by default, no custom click-only
  handling.
- The invalid-login message renders through `FieldError`, which carries
  `role="alert"` (screen-reader-announced) and is plain text, not a
  color-only cue; both inputs also receive `aria-invalid` when an error is
  present (applied to both fields identically, never singling out which
  one was "wrong," consistent with never revealing which credential
  failed).
- Existing focus-visible ring styling (already baked into the shared
  `Input`/`Button` primitives, unchanged) applies unmodified.
- Exactly one `<h1>` on the page ("Sign in") — the brand block above it
  uses non-heading `<p>` tags, mirroring the same one-h1-per-page
  convention `Header.tsx` documents for the rest of the app.

No headless-browser tool is available in this environment (established
and disclosed repeatedly across Phases 16-19); the above is a source-level
accessibility review, not a rendered/assistive-technology verification —
see §9 and §11 for the same honest caveat.

## 9. Responsive Design

The layout uses a single centered column (`max-w-sm`) with `p-6 md:p-10`
outer padding and no fixed-width elements, matching the responsive
conventions already used by the rest of the app (e.g.
`scenario-simulator-page.tsx`'s `sm:grid-cols-2`). This is a structural
review, not a rendered check: **browser visual verification unavailable in
this environment.** No claim of visually-confirmed mobile/tablet/desktop
behavior is made.

## 10. Security

A targeted grep of every file this phase touched, for API-key patterns,
`forgot`/`reset password`/social-provider names/`oauth`, found **zero**
matches beyond the one intentionally-displayed demo credential. The demo
password is a client-side constant, not a secret — it is displayed on the
page itself by design. No JWT secret, no session-database credential, no
Gemini/database credential was added or touched by this phase (that logic
lives entirely in `backend/`, which this phase did not modify — confirmed
by an mtime check against every file under `backend/`, `models/`,
`datasets/`, and `config/`, none of which changed during this phase).

## 11. Tests

No new automated frontend test file was added — this repository has no
existing frontend test runner (Vitest/Jest/Playwright) wired up in
`package.json` (`scripts` contains only `dev`/`build`/`lint`/`preview`/
`generate-types`); consistent with Phases 16-18's own disclosed limitation,
no new one was introduced in this phase either. The 9 manual test cases in
the phase brief were instead verified by source-level review of the exact
control flow (`ProtectedRoute`, `AuthProvider.login`/`logout`,
`LoginForm`'s submit/demo handlers) rather than by interactive browser
execution, which this environment cannot perform — see §9's disclosure.

## 12. TypeScript

`npx tsc -b` — **0 errors**, re-run after every file change in this phase.

## 13. Build

`npx vite build` — succeeds. Output grew from 915.88 kB (Phase 19 baseline)
to 924.79 kB (gzip 285.57 kB) for the added login/auth code and the
two-column layout revision — still a single JS chunk (the pre-existing,
previously-documented Phase 19 finding that the app has no route-level
code-splitting; not something this phase's scope authorized changing).

## 14. Lint

`npx oxlint` — **0 errors**, 8 warnings (was 7 before this phase). The one
new warning is `auth-context.tsx:50` — `react(only-export-components)`,
because the file exports both the `AuthProvider` component and the
`useAuth` hook from one file. This is the exact same, pre-existing pattern
`customer-context.tsx:47` already has (same warning, same cause) — not a
new class of issue introduced by this phase.

## 15. Backend Regression

Command run: full `pytest` suite (background task `b41jn1zau`). Result:
**698 passed, 2 skipped, 0 failed** (1148.38s) — differs from Phase 19's
baseline of 697 passed / 3 skipped by exactly one test moving from
"skipped" to "passed." **0 failures either way; the total is 700 tests in
both runs — nothing was added, removed, or broken.**

Investigated per this phase's own instruction to investigate rather than
assume a discrepancy is benign: a targeted re-run of the Gemini-touching
tests (`-k "gemini or qa or explanation or debate"`) immediately afterward
reproduced 3 skips, all from the same documented quota-skip guard (Phase
14), all with the identical cause —

```text
Gemini API error for this run (code=429): 429 RESOURCE_EXHAUSTED ...
quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier, quotaValue: 20
```

— i.e. these 3 tests make real, live Gemini API calls and skip
(deliberately, not fail) whenever the shared free-tier daily quota
(20 requests/day/model) is already exhausted at the moment each one runs.
Phase 19's own regression and this session's extensive live E2E API testing
(Phase 19 §28, this phase's own manual verification) both consume that same
quota. Which of the 3 quota-gated tests happens to run before the quota is
exhausted is timing-dependent and not reproducible run-to-run — exactly
matching the observed 697/3 vs. 698/2 split (one test got lucky on timing
in the full-suite run; all 3 skipped again in the immediate, smaller,
Gemini-only re-run). This is a pre-existing property of this test suite's
handling of a real external rate limit, not a regression, and not caused by
this phase — **zero backend files were modified this phase** (§16/§17).
**0 failures, confirmed in both runs.**

## 16. Files Created

- `frontend/src/lib/prototype-auth.ts`
- `frontend/src/providers/auth-context.tsx`
- `frontend/src/components/shell/protected-route.tsx`
- `frontend/src/pages/login-page.tsx`
- `frontend/src/components/login-form.tsx` (created by the shadcn CLI, then
  adapted — see §3/§4)
- `frontend/src/components/ui/field.tsx` (created by the shadcn CLI,
  unmodified)
- `reports/phase20_login_report.md` (this file)

## 17. Files Modified

- `frontend/src/App.tsx` — added the `/login` route and wrapped the
  existing route tree in `ProtectedRoute`; every existing route path and
  its nesting under `AppShell` is otherwise byte-for-byte unchanged.
- `frontend/src/main.tsx` — added `AuthProvider` to the provider tree.
- `frontend/src/components/shell/header.tsx` — added one "Sign out" button
  next to the existing `CustomerSelector`; nothing else in the header was
  redesigned.
- `frontend/src/components/ui/separator.tsx` — shadcn CLI's one-line
  `"use client"` addition (see §3).

No other file, in `frontend/` or elsewhere, was modified.

## 18. Dependencies

**None added.** The shadcn `login-02` registry entry lists `cn` as a
dependency, but `cn@^0.3.0` was already present in `package.json` before
this phase (confirmed by diffing `package.json` before/after) — net
dependency change is zero.

## 19. Limitations

- **This is prototype authentication, not production authentication.**
  There is no password hashing, no server-side session, no token, no
  expiry, and no backend validation of any kind. Anyone with browser
  devtools can set the `localStorage` flag directly and bypass the gate —
  this is an accepted, disclosed property of a frontend-only demo gate, not
  an oversight.
- **A single, shared demo account, not per-user accounts.** There is no
  "Create New User" flow in this phase (explicitly out of scope, reserved
  for a later phase).
- **No interactive browser verification was performed** (no headless
  browser tool available in this environment) — all 9 manual test
  scenarios in the phase brief were verified by source-level control-flow
  review, not by clicking through a running instance. This should be
  visually re-verified by the user (or in a future phase with such
  tooling) before a live demo.
- **No frontend automated test runner exists in this repository**
  (pre-existing, not introduced or resolved by this phase).
- The single ~924 kB JS bundle / no-code-splitting finding from Phase 19
  is unchanged in kind, only slightly larger in size.

## 20. Phase 21 Boundary

This phase implements login/logout/route-protection only. It explicitly
does **not** implement: Create New User, Questionnaire onboarding, Goal
creation, customer switching/profile-selection redesign, or demo customer
data population. `Profile #1` (or whatever profile id is currently stored
in `localStorage`) continues to display after login exactly as before —
unchanged, per this phase's own instruction that this is acceptable for
Phase 20. Per the phase's own stop condition, Phase 21 is not started here.
