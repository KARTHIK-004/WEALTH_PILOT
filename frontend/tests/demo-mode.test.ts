/**
 * Pure tests for the demonstration-mode switch of the Financial Behaviour & Sentiment page (`src/lib/demo-mode.ts`), run by `npm test`. They prove that fictional data is requested only by the
 * exact query `?demo=true` AND only on a build that allows it, that a production build ignores the query, and that the page, the router and the login redirect keep production authentication.
 */
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { test } from "node:test"

import { DEMO_ADDRESS, DEMO_DISABLED_TITLE, DEMO_EXAMPLE_TEXT, DEMO_EXAMPLES, demoAllowed, destinationAfterLogin, isDemoDisabledProblem, isDemoRequested } from "../src/lib/demo-mode.ts"

const read = (relative: string): string => readFileSync(new URL(`../${relative}`, import.meta.url), "utf8").replace(/\r\n/g, "\n")
const code = (relative: string): string => read(relative).replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1")

test("a build allows demo mode only in development or when VITE_DEMO_MODE is exactly 'true'", () => {
  assert.equal(demoAllowed({ DEV: true }), true)
  assert.equal(demoAllowed({ DEV: false, VITE_DEMO_MODE: "true" }), true)
  for (const env of [{}, { DEV: false }, { DEV: false, VITE_DEMO_MODE: "1" }, { DEV: false, VITE_DEMO_MODE: "TRUE" }, { DEV: false, VITE_DEMO_MODE: "false" }, { DEV: false, VITE_DEMO_MODE: "" }]) {
    assert.equal(demoAllowed(env), false, JSON.stringify(env))
  }
})

test("demo mode is requested only by the exact query demo=true on a build that allows it", () => {
  assert.equal(isDemoRequested("?demo=true", true), true)
  assert.equal(isDemoRequested("demo=true", true), true)
  assert.equal(isDemoRequested("?x=1&demo=true", true), true)
  for (const search of ["", "?", "?demo", "?demo=", "?demo=1", "?demo=false", "?demo=TRUE", "?demo=true&demo=true", "?demo=true&demo=false", "?demos=true", "?Demo=true"]) {
    assert.equal(isDemoRequested(search, true), false, search)
  }
})

test("a production build (demo not allowed) ignores the query completely", () => {
  for (const search of ["?demo=true", "demo=true", "?x=1&demo=true"]) assert.equal(isDemoRequested(search, false), false, search)
})

test("the demo address and the disabled-problem title are the ones the backend and the page use", () => {
  assert.equal(DEMO_ADDRESS, "/financial-behaviour?demo=true")
  assert.equal(isDemoDisabledProblem(DEMO_DISABLED_TITLE), true)
  assert.equal(isDemoDisabledProblem("Service unavailable"), false)
  assert.equal(isDemoDisabledProblem(undefined), false)
  assert.match(read("../backend/wealthpilot/api/errors.py"), /title = "Demo mode is not enabled"/)
})

test("the example sentences are fictional, short and free of contact details, and the first one is the demo's own", () => {
  assert.equal(DEMO_EXAMPLES[0].text, DEMO_EXAMPLE_TEXT)
  assert.equal(new Set(DEMO_EXAMPLES.map((e) => e.label)).size, DEMO_EXAMPLES.length)
  for (const { text } of DEMO_EXAMPLES) assert.ok(text.length < 200 && !/@|https?:\/\/|\d{6,}/.test(text))
})

test("the demo route stays inside ProtectedRoute and AppShell: production authentication is not bypassed", () => {
  const app = code("src/App.tsx")
  const protectedAt = app.indexOf("<Route element={<ProtectedRoute />}>")
  assert.ok(protectedAt > -1 && app.indexOf('path="financial-behaviour"') > protectedAt)
  assert.doesNotMatch(app, /demo/i) // no public demo route exists
  assert.doesNotMatch(code("src/components/shell/protected-route.tsx"), /demo/i)
  assert.doesNotMatch(code("src/providers/auth-context.tsx"), /demo=|DEMO_MODE|isDemo/)
})

test("every sign-in button returns to the page that was asked for, query included (so ?demo=true and ?demo=family survive signing in)", () => {
  const login = code("src/components/login-form.tsx")
  assert.match(login, /destinationAfterLogin\("demo", from\)/)
  assert.match(login, /navigate\(destinationAfterLogin\("family", from\), \{ replace: true \}\)/)
  assert.doesNotMatch(login, /navigate\("\/profile\?household=open"/) // the family button no longer discards the requested address
  const asked = { pathname: "/financial-behaviour", search: "?demo=family" }
  for (const action of ["signin", "demo", "family", "pipeline"] as const) assert.equal(destinationAfterLogin(action, asked), "/financial-behaviour?demo=family", action)
  assert.equal(destinationAfterLogin("demo", { pathname: "/goals" }), "/goals")
  // opened directly (nothing asked for): each button keeps its own default
  assert.equal(destinationAfterLogin("family", undefined), "/profile?household=open")
  for (const action of ["signin", "demo", "pipeline"] as const) assert.equal(destinationAfterLogin(action, undefined), "/dashboard", action)
})

test("the normal path of the page is untouched: the profile guard and the real card are still reached when demo is not requested", () => {
  const page = code("src/pages/financial-behaviour-page.tsx")
  assert.match(page, /const \{ kind, problem \} = demoRequest\(search, allowDemo\)/)
  assert.match(page, /if \(kind === "individual"\) return <FinancialBehaviourDemoContent \/>/)
  assert.match(page, /if \(kind === "family"\) return <FinancialBehaviourFamilyDemoContent \/>/)
  assert.match(page, /if \(profileId === null\) \{/)
  assert.match(page, /return <FinancialBehaviourContent profileId=\{profileId\} demoProblem=\{problem\} demoHint=\{allowDemo\} \/>/)
  assert.match(page, /import \{ DEMO_MODE_ALLOWED \} from "@\/lib\/demo-build"/)
  assert.match(code("src/lib/demo-build.ts"), /import\.meta\.env\.DEV/)
  assert.doesNotMatch(page, /import\.meta/) // the page itself reads no environment flag
})

test("demo data comes only from the demo route: no hard-coded months or amounts exist in the frontend source", () => {
  for (const file of ["src/components/financial-health/demo-financial-behaviour.tsx", "src/components/financial-health/demo-financial-behaviour-card.tsx", "src/hooks/use-demo-financial-behaviour.ts", "src/lib/demo-mode.ts", "src/pages/financial-behaviour-page.tsx"]) {
    const source = code(file)
    assert.doesNotMatch(source, /2026-0\d|\b\d{2},\d{3}\b|\b6[0-9]{4}\b/, file) // no month label or rupee figure written into the source
  }
  assert.match(code("src/lib/api-client.ts"), /createDemoFinancialBehaviour[\s\S]*?\/api\/demo\/financial-behaviour/)
})

test("the demo adds no persistence, no ledger or sentiment call and no calculation to the frontend", () => {
  for (const file of ["src/components/financial-health/demo-financial-behaviour.tsx", "src/components/financial-health/demo-financial-behaviour-card.tsx", "src/hooks/use-demo-financial-behaviour.ts"]) {
    const source = code(file)
    assert.doesNotMatch(source, /ledger|blockchain|anchor|localStorage|sessionStorage|console\./i, file)
    assert.doesNotMatch(source, /\*\s*100\b|\/\s*\d+\s*\*|Math\.(round|floor|ceil)/, file) // formatting helpers do the only arithmetic-looking work
  }
})

test("the demo query keeps no copy of the typed text once nothing observes it, never retries, and sends the text in the body", () => {
  const hook = code("src/hooks/use-demo-financial-behaviour.ts")
  assert.match(hook, /gcTime: 0/)
  assert.match(hook, /staleTime: 0/)
  assert.match(hook, /retry: false/)
  assert.match(code("src/lib/api-client.ts"), /createDemoFinancialBehaviour:[\s\S]*?body: JSON\.stringify\(\{ text \}\)/)
})
