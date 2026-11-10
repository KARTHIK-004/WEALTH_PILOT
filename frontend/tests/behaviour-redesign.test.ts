/**
 * Tests for the redesigned "Financial Behaviour & Sentiment" page (ADR-048), run by `npm test`: the pure insight selection, the submit shortcut, the inconclusive flag, and the rules the new
 * components must keep (display only, no arithmetic, nothing written to browser storage or a URL, no hand-written API types, the same query and the same backend contract).
 * Rendered behaviour is covered by tests/behaviour-sentiment-view.cases.tsx against real recorded backend responses.
 */
import assert from "node:assert/strict"
import { readFileSync, readdirSync } from "node:fs"
import { test } from "node:test"

import { CATEGORY_LABELS, DIRECTION_LABELS, selectInsightRows, selectNotShown, type Finding } from "../src/lib/behaviour-insights.ts"
import { describeSentiment, isSubmitShortcut, MAX_USER_TEXT_CHARS } from "../src/lib/user-text-input.ts"

const read = (relative: string): string => readFileSync(new URL(`../${relative}`, import.meta.url), "utf8")
/** Source with comments removed, so a rule about CODE is not tripped by a sentence that merely mentions the forbidden thing (a doc comment saying "no analytics"). */
const code = (relative: string): string => read(relative).replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1")
const fixtureNames = readdirSync(new URL("./fixtures/", import.meta.url))
  .filter((name) => name.endsWith(".json") && !name.startsWith("security-"))
  .map((name) => name.replace(/\.json$/, ""))
const fixture = (name: string): { behaviour: { findings: Finding[] }; statements: { kind: string; text: string; sources: string[] }[] } => JSON.parse(read(`tests/fixtures/${name}.json`))

const NEW_FILES = [
  "src/components/financial-health/behaviour-insights-panel.tsx",
  "src/components/financial-health/sentiment-input-panel.tsx",
  "src/components/financial-health/sentiment-results-panel.tsx",
  "src/components/financial-health/risk-assessment-panel.tsx",
  "src/components/financial-health/behaviour-sentiment-view.tsx",
  "src/components/financial-health/behaviour-sentiment.tsx",
  "src/lib/behaviour-insights.ts",
]

// ------------------------------------------------------------------------------- the submit shortcut

test("Ctrl+Enter and Cmd+Enter submit; a plain Enter stays a line break", () => {
  const base = { key: "Enter", ctrlKey: false, metaKey: false }
  assert.equal(isSubmitShortcut({ ...base, ctrlKey: true }), true)
  assert.equal(isSubmitShortcut({ ...base, metaKey: true }), true)
  assert.equal(isSubmitShortcut(base), false)
  assert.equal(isSubmitShortcut({ ...base, shiftKey: true }), false)
  assert.equal(isSubmitShortcut({ ...base, ctrlKey: true, shiftKey: true }), false)
  assert.equal(isSubmitShortcut({ ...base, ctrlKey: true, altKey: true }), false)
})

test("the shortcut never fires for other keys or while an input method is composing", () => {
  assert.equal(isSubmitShortcut({ key: "a", ctrlKey: true, metaKey: false }), false)
  assert.equal(isSubmitShortcut({ key: "Tab", ctrlKey: true, metaKey: false }), false)
  assert.equal(isSubmitShortcut({ key: "Enter", ctrlKey: true, metaKey: false, isComposing: true }), false)
})

test("the text area calls the same guarded submit as the button, so a duplicate or invalid text is still refused", () => {
  const panel = read("src/components/financial-health/sentiment-input-panel.tsx")
  assert.match(panel, /isSubmitShortcut\(event\.nativeEvent\)/)
  assert.match(panel, /event\.preventDefault\(\)\s+onSubmit\(\)/)
  const card = read("src/components/financial-health/behaviour-sentiment.tsx")
  assert.match(card, /const outcome = submitDraft\(input, pending\)/)
  assert.match(card, /if \(outcome\.rejected\) return/)
})

// ------------------------------------------------------------------------------- insight selection

test("the insight rows are the backend's observed findings in its order, without the month-count sentence", () => {
  assert.ok(fixtureNames.length >= 9)
  for (const name of fixtureNames) {
    const { behaviour } = fixture(name)
    const rows = selectInsightRows(behaviour.findings)
    const expected = behaviour.findings.filter((f) => f.status === "observed" && !(f.sources.length === 1 && f.sources[0] === "observation_count"))
    assert.deepEqual(rows.map((r) => r.statement), expected.map((f) => f.statement), name)
    assert.deepEqual(rows.map((r) => r.sources), expected.map((f) => f.sources), name)
    assert.deepEqual(rows.map((r) => r.direction), expected.map((f) => f.direction ?? null), name)
  }
})

test("the wording, sources and direction are passed through unchanged and nothing is computed", () => {
  const finding: Finding = {
    code: "expenses_trend",
    category: "trend",
    status: "observed",
    statement: "Expenses increased by ₹1,000 compared with the previous month (25.0%).",
    sources: ["expenses_change.absolute_change", "expenses_change.relative_change"],
    direction: "increased",
    values: { absolute_change: 1000, relative_change: 0.25 },
  }
  const [row] = selectInsightRows([finding])
  assert.equal(row.statement, finding.statement)
  assert.deepEqual(row.sources, finding.sources)
  assert.equal(row.direction, "increased")
  assert.equal(row.directionLabel, "Increased")
  assert.equal(row.categoryLabel, CATEGORY_LABELS.trend)
  assert.deepEqual(Object.keys(row).sort(), ["category", "categoryLabel", "code", "direction", "directionLabel", "sources", "statement"])
})

test("unavailable and not-included findings are never shown as insights; they are listed, with the backend's own reason, as not shown", () => {
  const base: Finding = { code: "x", category: "ratio", status: "observed", statement: "S", sources: ["a"], direction: null, values: {} }
  const findings: Finding[] = [base, { ...base, code: "u", status: "unavailable", statement: "U" }, { ...base, code: "n", status: "not_included", statement: "N" }]
  assert.deepEqual(selectInsightRows(findings).map((r) => r.code), ["x"])
  assert.deepEqual(selectNotShown(findings).map((f) => f.statement), ["U", "N"])
})

test("a finding without a direction has no direction label, and the labels are plain words", () => {
  const [row] = selectInsightRows([{ code: "r", category: "ratio", status: "observed", statement: "S", sources: ["a"], direction: null, values: {} }])
  assert.equal(row.direction, null)
  assert.equal(row.directionLabel, null)
  assert.deepEqual(Object.values(DIRECTION_LABELS).sort(), ["Decreased", "Increased", "Unchanged"])
  for (const label of Object.values(CATEGORY_LABELS)) assert.doesNotMatch(label, /good|bad|better|worse|risky|healthy/i)
})

test("selecting rows does not mutate the response", () => {
  const { behaviour } = fixture("records-only")
  const before = JSON.stringify(behaviour)
  selectInsightRows(behaviour.findings)
  selectNotShown(behaviour.findings)
  assert.equal(JSON.stringify(behaviour), before)
})

// ------------------------------------------------------------------------------- inconclusive readings

test("only an uncertain or unrecognised reading is flagged inconclusive; a found tone never is, and uncertain is never neutral", () => {
  for (const value of ["positive", "negative", "neutral", "mixed"]) assert.equal(describeSentiment(value).inconclusive, false, value)
  for (const value of ["uncertain", "ecstatic", null, undefined, ""]) assert.equal(describeSentiment(value).inconclusive, true, String(value))
  assert.notEqual(describeSentiment("uncertain").label, describeSentiment("neutral").label)
  assert.equal(describeSentiment("neutral").inconclusive, false)
})

// ------------------------------------------------------------------------------- what the new files may not do

test("display only: no arithmetic, no sentiment inference, no new fetching in the redesigned components", () => {
  for (const file of NEW_FILES) {
    const source = code(file)
    assert.doesNotMatch(source, /\.reduce\(|toFixed\(|Math\.|parseFloat\(|\*\s*100|\/\s*100/, file)
    assert.doesNotMatch(source, /\bfetch\(|axios|XMLHttpRequest|sendBeacon|@\/lib\/api-client/, file)
    assert.doesNotMatch(source, /\.sentiment\s*=|sentiment\s*===?\s*"(positive|negative)"\s*\?/, file) // a label is looked up from the backend's value, never decided here
  }
})

test("the user's text is never written to browser storage, a URL, the history, the console or any analytics", () => {
  for (const file of [...NEW_FILES, "src/hooks/use-personalized-insight.ts", "src/lib/user-text-input.ts", "src/pages/financial-behaviour-page.tsx"]) {
    const source = code(file)
    assert.doesNotMatch(source, /localStorage|sessionStorage|indexedDB|document\.cookie|caches\./, file)
    assert.doesNotMatch(source, /URLSearchParams|location\.(search|hash|href)|history\.(push|replace)State|navigate\(|useSearchParams|setSearchParams/, file)
    assert.doesNotMatch(source, /console\.|analytics|gtag|dataLayer|posthog|sentry/i, file)
  }
})

test("the text is kept only in component state and an in-memory query that is dropped when unused", () => {
  const hook = read("src/hooks/use-personalized-insight.ts")
  for (const setting of [/gcTime: 0/, /staleTime: 0/, /retry: false/, /refetchOnWindowFocus: false/]) assert.match(hook, setting)
  assert.match(read("src/components/financial-health/behaviour-sentiment.tsx"), /onClear=\{\(\) => setInput\(clearAll\(\)\)\}/)
  assert.doesNotMatch(read("src/lib/query-client.ts"), /persist/i)
})

test("the text area has no hard length attribute: an over-long paste is reported by the counter and the message, never silently cut", () => {
  assert.doesNotMatch(read("src/components/financial-health/sentiment-input-panel.tsx"), /maxLength|maxlength/)
  assert.equal(MAX_USER_TEXT_CHARS, 1000)
  assert.match(read("src/components/financial-health/sentiment-input-panel.tsx"), /MAX_USER_TEXT_CHARS/)
})

test("the text area is the shadcn primitive added with the CLI, not a hand-written one, and no dependency was added", () => {
  const panel = read("src/components/financial-health/sentiment-input-panel.tsx")
  assert.match(panel, /import \{ Textarea \} from "@\/components\/ui\/textarea"/)
  assert.doesNotMatch(panel, /<textarea/) // the raw element is only inside the primitive
  assert.match(read("src/components/ui/textarea.tsx"), /data-slot="textarea"/)
  const dependencies = Object.keys(JSON.parse(read("package.json")).dependencies).sort()
  assert.ok(!dependencies.some((name) => /textarea|autosize|markdown|editor|form|zod|chart\.js|framer|motion/i.test(name)), dependencies.join(", "))
})

test("types come from the generated API schema; the new files declare no interface that mirrors a response", () => {
  for (const file of NEW_FILES) {
    const source = read(file)
    assert.doesNotMatch(source, /interface \w*(Insight|Sentiment|Behaviour|Risk)\w*Response\b/, file)
  }
  assert.match(read("src/lib/behaviour-insights.ts"), /components\["schemas"\]\["BehaviourFindingOut"\]/)
  assert.match(read("src/components/financial-health/sentiment-results-panel.tsx"), /components\["schemas"\]\["UserSentimentOut"\]/)
})

test("the page keeps one title; the panels use level-two headings and no panel has an h1", () => {
  for (const file of NEW_FILES) assert.doesNotMatch(read(file), /<h1\b/, file)
  for (const file of NEW_FILES.slice(0, 4)) assert.match(read(file), /role="heading"\s+aria-level=\{2\}/, file)
})

test("the card, hook, endpoint and generated schema are unchanged by the redesign", () => {
  assert.match(read("src/hooks/use-personalized-insight.ts"), /api\.createPersonalizedInsight\(profileId as number, text\)/)
  assert.match(read("src/lib/api-client.ts"), /createPersonalizedInsight/)
  assert.match(read("src/components/financial-health/behaviour-sentiment.tsx"), /usePersonalizedInsightQuery\(profileId, input\.submitted\)/)
})
