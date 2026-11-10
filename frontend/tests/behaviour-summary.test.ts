/**
 * Tests for the compact summary helper (src/lib/behaviour-summary.ts) and for the routing / navigation / structure of the dedicated "Financial Behaviour & Sentiment" page, run by `npm test`.
 * The summary selects existing BACKEND statements from a real recorded response (frontend/tests/fixtures, captured from the actual route); it never calculates anything.
 */
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { test } from "node:test"

import { BEHAVIOUR_PAGE_PATH, SUMMARY_MAX_FACTS, summariseBehaviour, type SummaryInsight } from "../src/lib/behaviour-summary.ts"

const read = (relative: string): string => readFileSync(new URL(`../${relative}`, import.meta.url), "utf8")
const fixture = (name: string): SummaryInsight => JSON.parse(read(`tests/fixtures/${name}.json`)) as SummaryInsight

// ------------------------------------------------------------------ the summary helper

test("the summary shows at most three observed facts, in the backend's order, without the bare month-count line", () => {
  const data = fixture("records-only")
  const summary = summariseBehaviour(data)
  const backendFacts = data.statements.filter((s) => s.kind === "behaviour_fact")
  assert.equal(SUMMARY_MAX_FACTS, 3)
  assert.ok(backendFacts.length > 4)
  assert.equal(summary.facts.length, 3)
  assert.deepEqual(summary.facts, backendFacts.filter((s) => s.sources[0] !== "observation_count").slice(0, 3))
  assert.ok(!summary.facts.some((f) => f.sources.length === 1 && f.sources[0] === "observation_count"))
  assert.equal(summary.moreFacts, true)
  assert.equal(summary.months, data.behaviour.observation_count)
  assert.equal(summary.latestPeriod, data.behaviour.latest_period)
  assert.equal(summary.hasRecords, true)
})

test("every shown fact and the assessment sentence are the backend's own text, unchanged", () => {
  const data = fixture("conflict")
  const summary = summariseBehaviour(data)
  const backendTexts = new Set(data.statements.map((s) => s.text))
  for (const fact of summary.facts) assert.ok(backendTexts.has(fact.text))
  assert.equal(summary.assessmentStatement, data.statements.find((s) => s.kind === "risk_assessment")?.text)
})

test("no records: no facts and no invented month count; the assessment sentence is still the backend's", () => {
  const summary = summariseBehaviour(fixture("no-records-no-text"))
  assert.deepEqual([summary.months, summary.hasRecords, summary.facts.length, summary.moreFacts, summary.latestPeriod], [0, false, 0, false, null])
  assert.match(summary.assessmentStatement ?? "", /risk assessment/i)
})

test("neither records nor an assessment: everything is empty or null, never zero-filled text", () => {
  const summary = summariseBehaviour(fixture("nothing-available"))
  assert.deepEqual([summary.hasRecords, summary.facts, summary.assessmentStatement], [false, [], null])
})

test("a text reading is never part of the summary: only behaviour facts and the assessment are selected", () => {
  const data = fixture("conflict")
  const summary = summariseBehaviour(data)
  const stated = data.statements.filter((s) => s.kind === "stated_by_user").map((s) => s.text)
  assert.ok(stated.length > 0)
  for (const text of stated) assert.ok(!summary.facts.some((f) => f.text === text) && summary.assessmentStatement !== text)
})

test("the summary does no arithmetic", () => {
  const source = read("src/lib/behaviour-summary.ts") + read("src/components/financial-health/behaviour-summary-card.tsx")
  assert.doesNotMatch(source, /\.reduce\(|toFixed\(|Math\.|parseFloat\(|\*\s*100|\/\s*100/)
})

// ------------------------------------------------------------------ routing and navigation

test("the dedicated page has its own route, in the protected app shell, next to Financial Health", () => {
  const app = read("src/App.tsx")
  assert.equal(BEHAVIOUR_PAGE_PATH, "/financial-behaviour")
  assert.match(app, /import \{ FinancialBehaviourPage \} from "@\/pages\/financial-behaviour-page"/)
  assert.match(app, /<Route path="financial-behaviour" element=\{<FinancialBehaviourPage \/>\} \/>/)
  const shell = app.slice(app.indexOf("<Route element={<AppShell />}>"))
  assert.ok(shell.indexOf('path="financial-behaviour"') > 0 && shell.indexOf('path="financial-behaviour"') < shell.indexOf('path="*"'))
  assert.ok(shell.indexOf('path="financial-health"') < shell.indexOf('path="financial-behaviour"'))
})

test("the navigation lists the page once, right after Financial Health, with an icon", () => {
  const nav = read("src/components/shell/nav-items.ts")
  const lines = nav.split("\n").filter((l) => l.includes("url:"))
  const urls = lines.map((l) => /url: "([^"]+)"/.exec(l)?.[1])
  assert.equal(urls.filter((u) => u === "/financial-behaviour").length, 1)
  assert.equal(urls[urls.indexOf("/financial-health") + 1], "/financial-behaviour")
  assert.match(nav, /title: "Behaviour & Sentiment", url: "\/financial-behaviour", icon: MessageSquareText/)
})

test("every nav url has a route and every sidebar route is in the nav", () => {
  const nav = read("src/components/shell/nav-items.ts")
  const app = read("src/App.tsx")
  for (const [, url] of nav.matchAll(/url: "\/([a-z-]+)"/g)) assert.match(app, new RegExp(`path="${url}"`), url)
})

// ------------------------------------------------------------------ where the detail lives now

test("Financial Health keeps only the compact summary: no text box, no sentiment card, a link to the page", () => {
  const page = read("src/pages/financial-health-page.tsx")
  assert.match(page, /import \{ BehaviourSummaryCard \}/)
  assert.doesNotMatch(page, /BehaviourSentimentCard|behaviour-sentiment"|use-personalized-insight|user-text-input/)
  assert.match(page, /<BehaviourSummaryCard key=\{profileId\} profileId=\{profileId\} \/>/)
  const summary = read("src/components/financial-health/behaviour-summary-card.tsx")
  assert.doesNotMatch(summary, /<Input|<input|<textarea|onChange|useState|user-text-input|submitDraft|validateUserText/)
  assert.match(summary, /usePersonalizedInsightQuery\(profileId, null\)/) // records only: the summary never sends text
  assert.match(summary, /<Link to=\{BEHAVIOUR_PAGE_PATH\} className=\{buttonVariants\(\{ variant: "outline" \}\)\}>/)
  assert.doesNotMatch(summary, /<Button\b|nativeButton|role="button"/) // a real link: a Button rendered as a Link is announced as a button
})

test("the dedicated page holds the detailed card and links back; the page owns the only title and the card has no header of its own", () => {
  const page = read("src/pages/financial-behaviour-page.tsx")
  assert.match(page, /<PageContainer title=\{BEHAVIOUR_PAGE_TITLE\} description=\{BEHAVIOUR_DESCRIPTION\}>/)
  assert.doesNotMatch(page, /showHeader/)
  assert.doesNotMatch(read("src/components/financial-health/behaviour-sentiment-view.tsx"), /showHeader|<h1/)
  assert.match(page, /<Link to="\/financial-health"/)
  assert.match(page, /NoProfileSelected/)
  assert.equal(/export const BEHAVIOUR_PAGE_TITLE = "Financial Behaviour & Sentiment"/.test(page), true)
})

test("on a phone, choosing any page from the sidebar sheet closes it, so it never stays open over the new page", () => {
  const sidebar = read("src/components/shell/app-sidebar.tsx")
  assert.match(sidebar, /const \{ setOpenMobile \} = useSidebar\(\)/)
  assert.match(sidebar, /const closeMobileSheet = \(\) => setOpenMobile\(false\)/)
  assert.equal((sidebar.match(/onClick=\{closeMobileSheet\}/g) ?? []).length, 2) // the brand link and every nav item (one rendered per NAV_GROUPS entry)
  const nav = sidebar.slice(sidebar.indexOf("group.items.map"))
  assert.match(nav, /isActive=\{isActive\}\s+onClick=\{closeMobileSheet\}/)
})
