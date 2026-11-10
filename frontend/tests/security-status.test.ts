/**
 * Structural tests for the "Data Protection" page, run by `npm test`: routing, navigation, the client call, the query's no-cache setting and the rules this page must keep
 * (display only, no arithmetic, nothing written to browser storage, honest wording). The rendered behaviour is covered by tests/security-status-view.cases.tsx.
 */
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { test } from "node:test"

const read = (relative: string): string => readFileSync(new URL(`../${relative}`, import.meta.url), "utf8")

const NEW_FILES = [
  "src/components/security/security-status-card.tsx",
  "src/pages/security-status-page.tsx",
  "src/hooks/use-security-status.ts",
  "src/lib/security-status-labels.ts",
]

test("the page has its own route inside the protected app shell, before the catch-all", () => {
  const app = read("src/App.tsx")
  assert.match(app, /import \{ SecurityStatusPage \} from "@\/pages\/security-status-page"/)
  assert.match(app, /<Route path="security" element=\{<SecurityStatusPage \/>\} \/>/)
  const shell = app.slice(app.indexOf("<Route element={<AppShell />}>"))
  assert.ok(shell.indexOf('path="security"') > 0 && shell.indexOf('path="security"') < shell.indexOf('path="*"'))
})

test("the navigation lists the page once, with an icon, and every nav url has a route", () => {
  const nav = read("src/components/shell/nav-items.ts")
  assert.equal((nav.match(/url: "\/security"/g) ?? []).length, 1)
  assert.match(nav, /\{ title: "Data Protection", url: "\/security", icon: ShieldCheck \}/)
  const app = read("src/App.tsx")
  for (const [, url] of nav.matchAll(/url: "\/([a-z-]+)"/g)) assert.match(app, new RegExp(`path="${url}"`), url)
})

test("the client call is a GET of the profile's security-status with the asserted identity header, and nothing else", () => {
  const client = read("src/lib/api-client.ts")
  const call = /getSecurityStatus: \(profileId: number\) =>\s+request<Schemas\["SecurityStatusOut"\]>\(`\/api\/profiles\/\$\{profileId\}\/security-status`, \{\s+headers: asCustomer\(profileId\),\s+\}\),/
  assert.match(client, call)
  assert.doesNotMatch(client, /protected-notes/) // this page never reads or writes a note
})

test("the generated type exists and was not hand-written", () => {
  const types = read("src/types/api.ts")
  assert.match(types, /SecurityStatusOut: \{/)
  for (const file of NEW_FILES) assert.doesNotMatch(read(file), /interface SecurityStatus\b|type SecurityStatus = \{/)
})

test("the query never serves a stale or cached result and never retries silently", () => {
  const hook = read("src/hooks/use-security-status.ts")
  for (const setting of [/gcTime: 0/, /staleTime: 0/, /retry: false/, /refetchOnWindowFocus: false/, /queryKey: \["security-status", profileId\]/, /enabled: profileId !== null/]) assert.match(hook, setting)
})

test("the page is keyed by profile so a different profile never shows an earlier result", () => {
  assert.match(read("src/pages/security-status-page.tsx"), /<SecurityStatusCard key=\{profileId\} profileId=\{profileId\} \/>/)
})

test("display only: no arithmetic, no browser storage, no raw HTML, no secrets", () => {
  for (const file of NEW_FILES) {
    const source = read(file)
    assert.doesNotMatch(source, /\.reduce\(|toFixed\(|Math\.|parseFloat\(|\*\s*100|\/\s*100/, file)
    assert.doesNotMatch(source, /localStorage|sessionStorage|indexedDB|document\.cookie/, file)
    assert.doesNotMatch(source, /dangerouslySetInnerHTML|innerHTML/, file)
    assert.doesNotMatch(source, /crypto\.|subtle\.|encrypt\(|decrypt\(|createHash|sha256/i, file) // the browser neither encrypts nor verifies anything
  }
})

test("no unqualified blockchain, decentralization, immutability or production-readiness wording in the page source", () => {
  const source = NEW_FILES.map(read).join("\n")
  const stripped = source.replace(/not decentralized/g, "").replace(/no consensus/g, "").replace(/not independently tamper-proof/g, "")
  assert.doesNotMatch(stripped, /decentrali[sz]ed|consensus|immutable|production-ready|compliant|certified|tamper-proof\./i)
  assert.match(source, /prototype_notice/) // the exact label comes from the backend response
})

test("the page's own state is not persisted: no query persistence is configured", () => {
  const providers = read("src/lib/query-client.ts")
  assert.doesNotMatch(providers, /persist/i)
})
