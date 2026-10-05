# Post-Login Profile Flow Fix — Completion Report

## 1. Problem

After a successful login, the authenticated user was shown a manual
"Select customer profile" dialog (`CustomerSelector`) asking them to type
in a numeric customer/profile id before any protected page would load.
This existed because a regular Sign In never actually resolved a
customer — only "Use Demo Account" did (Phase 24) — so `profileId` stayed
unset after a normal sign-in, and the manual dialog was the only way to
give the app a customer to show. This is not how an authenticated
application should behave: a logged-in user should never have to know or
type an internal database id, and the same account should reach the same
customer automatically every time.

## 2. Previous Flow

`LOGIN → AUTHENTICATED (no customer resolved) → "Select customer profile"
dialog → user types a numeric id → protected pages`. The dialog
(`components/shell/customer-selector.tsx`) rendered a `Dialog` with a
numeric `Input`, the copy "Select customer profile" / "Enter the numeric
id of an existing profile. All five pages will use this same profile.",
and a "Don't have a profile yet? Create a new profile" link. It lived in
the app header, visible on every authenticated page.

## 3. New Flow

`LOGIN → AUTHENTICATED USER → RESOLVE USER'S CUSTOMER PROFILE (automatic)
→ DASHBOARD → ALL PROTECTED PAGES USE THAT SAME PROFILE`. No selection
screen exists anywhere in the authenticated app. Both "Sign In" and "Use
Demo Account" now go through one shared `completeLogin()` function
(`components/login-form.tsx`) that resolves the account's customer and
sets it as the active profile before navigating — the user lands directly
on the Dashboard every time.

## 4. Authentication-To-Customer Mapping

There is exactly one supported prototype credential
(`lib/prototype-auth.ts` defines no other), so both authentication paths
resolve through the same deterministic function,
`resolveDemoCustomer()` (`lib/demo-customer.ts`): find a locally-remembered,
re-verified customer id, or find-or-create the canonical demo customer via
the real `POST /api/profiles` / questionnaire / goals APIs. This is a
name-based, idempotent-per-browser mapping, not a new authentication
table — no database schema changed for this task, consistent with
"preserve the existing prototype-auth architecture unless a minimal
change is required." The two existing sibling React contexts
(`AuthProvider` for `isAuthenticated`, `CustomerProvider` for `profileId`)
were kept exactly as they were; they are composed together at the three
places an account's customer association is actually established
(`login-form.tsx`, `create-user-page.tsx`, and `header.tsx`'s sign-out),
rather than merged into one context — the lower-risk, smaller-diff option
that still gives every protected page one single, shared `profileId`.

## 5. Demo Account Behavior

Unchanged in outcome from Phase 24, now reached through the same shared
`completeLogin()` path as regular sign-in rather than its own separate
code path: clicking "Use Demo Account" resolves the canonical demo
customer and lands on the Dashboard with no id screen, exactly as before.

## 6. Create-User Behavior

Unchanged — already correct before this task.
`pages/create-user-page.tsx`'s `handleContinue` already called
`setProfileId(mutation.data.customer_id)` and
`grantSessionAfterProfileCreation()` before navigating straight to
onboarding, with no selection screen. Verified by reading the current
file; no edit was needed here.

## 7. Logout Behavior

`components/shell/header.tsx`'s `handleSignOut` now clears both the
authentication flag (`logout()`) AND the active customer association
(`setProfileId(null)`) before redirecting to `/login`. Previously only the
auth flag was cleared, leaving a stale profile id in `localStorage` until
the next login silently overwrote it. A subsequent login re-resolves the
correct association from scratch — never a leftover id from a prior
session.

## 8. Protected-Route Behavior

Unchanged — already correct. `components/shell/protected-route.tsx`
redirects an unauthenticated visitor to `/login` (preserving the
originally requested location in router state) and otherwise renders the
protected subtree. No route in this app ever took a customer id as a URL
parameter, so "use their associated customer with no id route parameter"
was already true before this task; what changed is that `profileId` is
now always correctly populated for an authenticated session by the time a
protected page renders.

## 9. Header Identity Behavior

The header now renders `components/shell/account-identity.tsx` (new, pure
read-only display, no input of any kind) in place of the removed
`CustomerSelector`. It shows a "Demo Account" badge (icon + text) when the
active profile is the recognized demo customer, or the real customer's
own name (from the same `useProfileQuery` every page already reads)
otherwise — never a raw "Profile #<id>" placeholder and never a hard-coded
label.

## 10. Customer Isolation

All ten protected pages (Dashboard, Customer Profile, Risk Assessment,
Financial Health, Goals, Portfolio, Recommendation, Why This
Recommendation, Agent Activity, Scenario Simulator) read `profileId` from
the same `useCustomer()` context — confirmed unchanged by this task, and
re-confirmed by a source-wide audit finding no page-level or
component-level customer-id state anywhere outside `customer-context.tsx`.

## 11. Files Changed

- `frontend/src/components/login-form.tsx` — modified: unified
  `attemptLogin`/`handleDemoLogin` through a shared `completeLogin(action)`
  that resolves and activates the customer before navigating.
- `frontend/src/components/shell/account-identity.tsx` — new: read-only
  header identity indicator, replaces `customer-selector.tsx`.
- `frontend/src/components/shell/customer-selector.tsx` — deleted.
- `frontend/src/components/shell/header.tsx` — modified: renders
  `AccountIdentity`; sign-out now also clears `profileId`.
- `frontend/src/components/shell/no-profile-selected.tsx` — modified:
  copy/actions rewritten for "no association exists" rather than "nothing
  chosen yet" (no numeric-id prompt).
- `frontend/src/components/shell/onboarding-no-profile.tsx` — modified:
  same copy correction, standalone-page variant.
- `frontend/src/providers/customer-context.tsx` — modified: docstring
  only, documenting that `setProfileId` is no longer exposed through any
  UI control.
- `frontend/src/App.tsx` — modified: docstring only, removing a stale
  reference to a "selected" profile.

No backend file was modified for this task.

## 12. Tests

No frontend automated test runner exists in this project (established in
every prior frontend phase this session) — automated frontend tests for
this change were not added, consistent with that disclosed limitation. No
new backend code was added or needed for this task, so no new backend
test was required. Verification instead relied on: a full TypeScript
compile, a full source-string audit (below), and re-reading every changed
file's final content directly.

**Source audit** for the required string list (`grep`, whole
`frontend/src`): "Select customer profile", "Enter the numeric id", and
"Don't have a profile yet" — zero UI occurrences (the only remaining hits
are inside `account-identity.tsx`'s own docstring, explaining what was
removed and why, not rendered UI text). `CustomerSelector` — zero
occurrences of the component itself; the name appears only in historical
docstring references explaining the removal. `selectedProfile` /
`selectedCustomer` — zero occurrences anywhere. Hard-coded numeric
customer ids in `pages/`/`components/` — none found. The one remaining
`Profile #{id}` occurrence is on the dedicated Customer Profile page
(`profile-page.tsx`), as a secondary `CardDescription` beneath the
customer's own name (the primary `CardTitle`) — a legitimate,
non-selection reference to the customer's own record on their own detail
page, not a header placeholder and not something a user can act on.

## 13. TypeScript

`npx tsc -b` — 0 errors.

## 14. Build

`npx vite build` — succeeds; 954.88 kB / gzip 293.74 kB, slightly smaller
than the pre-task baseline (958.90 kB), consistent with removing the
Dialog-heavy `CustomerSelector` and adding nothing larger in its place.

## 15. Lint

`npx oxlint` — 0 errors, 8 warnings, identical set to the pre-task
baseline (all pre-existing `react(only-export-components)`/
`react(set-state-in-effect)` warnings in shadcn/ui primitives and provider
files, none introduced by this task).

## 16. Browser Verification Status

Not performed — no headless-browser tool was available in this
environment when this task was carried out. Verification relied on
TypeScript compilation, the source-string audit above, and direct
line-by-line reading of every changed file's final state (login flow,
header, empty states, provider docstrings) to trace the exact runtime
behavior by hand. This is the same disclosed limitation every prior
frontend phase in this project has carried.

## 17. Prototype-Auth Limitation

This remains prototype authentication only, unchanged in kind by this
task: `lib/prototype-auth.ts` performs a client-side credential check
against one hard-coded demo credential, with no real backend session, no
token, and no server-side authorization check on any `/api/profiles/*`
route. `localStorage` (three keys:
`wealthpilot-prototype-authenticated`, `wealthpilot-profile-id`,
`wealthpilot-demo-customer-id`) is fully visible and editable via browser
devtools — a determined user could still hand-edit `wealthpilot-profile-id`
to an arbitrary number outside this UI entirely. What this task removed
was the in-app, first-class UI control that invited exactly that action;
it was never possible, and is still not possible, to make client-side
storage tamper-proof without real server-side sessions, which is
explicitly out of this task's scope. This is disclosed here plainly, not
hidden, exactly as MASTER_PROMPT's "prototype, not production-grade"
framing requires.

---

# POST-LOGIN PROFILE FLOW FIX COMPLETE

1. **Previous flow**: Authenticated users hit a manual "Select customer
   profile" dialog and had to type a numeric id before seeing any page.
2. **New flow**: Login (Sign In or Use Demo Account) automatically
   resolves the account's associated customer and lands directly on the
   Dashboard — no selection screen exists anywhere in the app.
3. **Demo login result**: Unchanged outcome from Phase 24 (resolves the
   canonical demo customer, idempotent per browser), now reached through
   the same shared resolution path as regular sign-in.
4. **Create-user result**: Unchanged — already auto-associated and
   auto-navigated correctly before this task; verified, not modified.
5. **Header result**: New `AccountIdentity` component shows "Demo Account"
   or the real customer's name — never a raw id, never editable.
6. **Customer association mechanism**: One shared `completeLogin()` /
   `resolveDemoCustomer()` function, composing the existing `AuthProvider`
   and `CustomerProvider` contexts at their three legitimate write sites
   (login, create-user, sign-out) — no context merge, no new auth table.
7. **Protected-route result**: Unchanged and already correct — redirects
   unauthenticated direct access to `/login`; no route ever took a
   customer id as a URL parameter.
8. **Logout result**: Now clears both the auth flag and the active
   customer association; a later login re-resolves cleanly.
9. **Tests**: No frontend test runner exists in this project (disclosed,
   pre-existing limitation); verification relied on TypeScript, a
   source-string audit, and direct file review. No backend change was
   needed, so no backend test was added.
10. **TypeScript/build/lint**: `tsc -b` 0 errors; `vite build` succeeds
    (954.88 kB, smaller than baseline); `oxlint` 0 errors, same 8
    pre-existing warnings.
11. **Backend regression result**: No backend file was modified by this
    task.
12. **Browser verification status**: Not performed — no headless-browser
    tool was available in this environment; verification was
    source-level only.
13. **Exact files changed**: `login-form.tsx` (modified),
    `account-identity.tsx` (new), `customer-selector.tsx` (deleted),
    `header.tsx` (modified), `no-profile-selected.tsx` (modified),
    `onboarding-no-profile.tsx` (modified), `customer-context.tsx`
    (docstring only), `App.tsx` (docstring only). No backend files.
14. **Confirmation of zero financial/ML/backend-core changes**: Confirmed
    — this task touched only frontend authentication/session-association
    UI and wiring; no model, compliance rule, agent node, or API route was
    added or modified.
15. **Known prototype-auth limitations**: Client-side-only credential
    check, no server session/token, `localStorage` remains devtools
    -editable (a determined user can still hand-edit `wealthpilot-profile-id`
    outside the UI, though the in-app control that invited doing so is
    gone), single shared demo account, per-browser-only demo-customer
    idempotency — all pre-existing and unchanged in kind by this task.
