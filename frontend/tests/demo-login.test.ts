/**
 * Structural tests for the "Use Full Pipeline Demo" sign-in (ADR-021 / ADR-036 pattern), run by `npm test`: the persona's name equals the backend package's own, the lookup is
 * find-only, the entry is a login choice and not a customer switcher, and an unseeded environment gets a clear message.
 */
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { test } from "node:test"

const read = (relative: string): string => readFileSync(new URL(`../${relative}`, import.meta.url), "utf8").replace(/\r\n/g, "\n")
const code = (relative: string): string => read(relative).replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1")

test("the frontend's persona name is exactly the backend demo package's name for WPDEMO-E", () => {
  const persona = JSON.parse(readFileSync(new URL("../../demo_data/profiles/persona_e_full_pipeline.json", import.meta.url), "utf8"))
  assert.equal(persona.demo_key, "WPDEMO-E")
  assert.match(read("src/lib/demo-customer.ts"), new RegExp(`export const FULL_PIPELINE_DEMO_NAME = ${JSON.stringify(persona.customer_name).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`))
})

test("the lookup is find-only: no profile, goal, questionnaire or storage write, and an unseeded environment throws its own error", () => {
  const source = read("src/lib/demo-customer.ts")
  const start = source.indexOf("export async function resolveFullPipelineDemoCustomer")
  const body = source.slice(start, source.indexOf("\n}\n", start) + 3)
  assert.match(body, /api\.lookupProfileByName\(FULL_PIPELINE_DEMO_NAME\)/)
  assert.match(body, /if \(customer_id === null\) throw new FullPipelineDemoNotSeededError\(\)/)
  assert.doesNotMatch(body, /createProfile|submitQuestionnaire|createGoal|localStorage|sessionStorage|fetch\(/)
})

test("the sign-in offers the entry beside the others, with a description and its own pending label", () => {
  const form = read("src/components/login-form.tsx")
  assert.match(form, /Use Full Pipeline Demo/)
  assert.match(form, /Opening full-pipeline demo…/)
  assert.match(form, /resolveFullPipelineDemoCustomer\(\)/)
  assert.match(form, /onClick=\{handlePipelineDemoLogin\}\s+disabled=\{pendingAction !== null\}/) // no double submit while any sign-in resolves
  assert.match(form, /risk, goals, behaviour, portfolio,\s+recommendation and explanation all show computed results/)
})

test("it signs in through the same credential gate and activates exactly one customer; it is not an in-app switcher", () => {
  const form = code("src/components/login-form.tsx")
  assert.match(form, /await attemptLogin\(DEMO_EMAIL, DEMO_PASSWORD, "pipeline"\)/)
  assert.equal((form.match(/setProfileId\(/g) ?? []).length, 3) // the individual, family and full-pipeline paths: each sets the one active profile
  for (const file of ["src/components/shell/app-sidebar.tsx", "src/components/shell/header.tsx", "src/pages/security-status-page.tsx", "src/pages/financial-behaviour-page.tsx"]) {
    assert.doesNotMatch(code(file), /resolveFullPipelineDemoCustomer|FULL_PIPELINE_DEMO_NAME/, file)
  }
})

test("an unseeded environment is explained, with the command that seeds it", () => {
  assert.match(read("src/components/login-form.tsx"), /The full-pipeline demo has not been set up in this environment yet \(seed_demo_data\.py setup\)\./)
})

test("the home-page hint can focus the new entry and nothing signs in by itself", () => {
  const form = code("src/components/login-form.tsx")
  assert.match(form, /if \(demoHint === "pipeline"\) pipelineDemoRef\.current\?\.focus\(\)/)
  assert.doesNotMatch(form, /useEffect\(\(\) => \{[^}]*attemptLogin/s)
})
