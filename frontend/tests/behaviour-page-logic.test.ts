/**
 * Pure tests for the Financial Behaviour page's logic (`src/lib/plain-sentiment.ts`, `investment-behaviour.ts`, `spending-pattern.ts`, `behaviour-overview.ts`, `demo-mode.ts`), run by `npm test`.
 * They prove the simple-English sentiment wording, that "unusual" is claimed only when the backend model said so, that the six spending situations stay apart, that the overview only selects the
 * backend's findings, and that no new file persists text, writes storage, calls a ledger or does arithmetic on a financial figure.
 */
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { test } from "node:test"

import { dateRange, missingDataNotes, monthLabel, OVERVIEW_EXPLANATION, overviewTrends, savingsRate } from "../src/lib/behaviour-overview.ts"
import type { Finding } from "../src/lib/behaviour-insights.ts"
import { behaviourLinkTarget, demoKind, demoRequest } from "../src/lib/demo-mode.ts"
import { investmentBehaviour, NOT_ENOUGH_HISTORY_DETAIL, STATUS_LABELS } from "../src/lib/investment-behaviour.ts"
import { plainSentiment, HEADLINES, MODEL_DISABLED_NOTE, NO_NOTE_HEADLINE, type UserSentiment } from "../src/lib/plain-sentiment.ts"
import { spendingPattern, type SpendingInput } from "../src/lib/spending-pattern.ts"

const read = (relative: string): string => readFileSync(new URL(`../${relative}`, import.meta.url), "utf8").replace(/\r\n/g, "\n")
const code = (relative: string): string => read(relative).replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1")

// ---------------------------------------------------------------------------------------------------------------------------------------- simple-English sentiment
const reading = (over: Partial<UserSentiment> = {}): UserSentiment =>
  ({ status: "analysed", sentiment: "neutral", abstained: false, interpretation_state: "valid", confidence: null, sentiment_intensity: null, ...over }) as UserSentiment

test("each reading is stated in the exact simple-English sentence", () => {
  assert.equal(plainSentiment(reading({ sentiment: "positive" })).headline, "Your note sounds generally positive.")
  assert.equal(plainSentiment(reading({ sentiment: "negative" })).headline, "Your note sounds concerned or negative.")
  assert.equal(plainSentiment(reading({ sentiment: "neutral" })).headline, "Your note sounds neutral.")
  assert.equal(plainSentiment(reading({ sentiment: "uncertain" })).headline, "Your note does not clearly show a current feeling.")
  assert.equal(plainSentiment(reading({ sentiment: "insufficient_evidence", abstained: true, interpretation_state: "abstained" })).headline, "There is not enough clear information to interpret this note.")
  assert.equal(plainSentiment(reading({ sentiment: "mixed" })).headline, HEADLINES.mixed)
  assert.equal(plainSentiment(reading({ status: "unavailable", sentiment: null, interpretation_state: "unavailable" })).headline, NO_NOTE_HEADLINE)
})

test("a weak reading (hypothetical, quoted, third-person or past-only text) is never described as the writer's current feeling", () => {
  for (const sentiment of ["positive", "negative", "neutral", "mixed", "uncertain"] as const) {
    const plain = plainSentiment(reading({ sentiment, interpretation_state: "weak" }))
    assert.equal(plain.kind, "uncertain", sentiment)
    assert.equal(plain.headline, "Your note does not clearly show a current feeling.")
  }
  for (const state of ["abstained"] as const) assert.equal(plainSentiment(reading({ sentiment: "neutral", interpretation_state: state })).kind, "abstained")
  assert.equal(plainSentiment(reading({ sentiment: "negative", abstained: true })).kind, "abstained") // an abstention wins over any label
})

test("the notes say what the reading is based on, that nothing changes, that the model is disabled and that confidence and intensity are unavailable", () => {
  const plain = plainSentiment(reading({ sentiment: "positive" }), "disabled")
  assert.deepEqual(plain.notes, [
    "This is based only on the words you chose to write.",
    "This does not change your risk profile, allocation or recommendations.",
    "The model-based sentiment feature is currently disabled.",
    "Confidence and intensity are not available.",
  ])
  assert.ok(!plainSentiment(reading({ sentiment: "positive" })).notes.includes(MODEL_DISABLED_NOTE)) // not stated unless the backend said so
  assert.ok(!plainSentiment(reading({ sentiment: "positive" }), "unavailable").notes.includes(MODEL_DISABLED_NOTE))
  assert.deepEqual(plainSentiment(reading({ status: "unavailable", sentiment: null }), "disabled").notes, [])
})

test("a confidence or intensity the backend does give is not hidden behind the 'not available' note", () => {
  assert.ok(!plainSentiment(reading({ sentiment: "positive", confidence: 0.8 }), "disabled").notes.includes("Confidence and intensity are not available."))
  assert.ok(!plainSentiment(reading({ sentiment: "positive", sentiment_intensity: 0.2 }), "disabled").notes.includes("Confidence and intensity are not available."))
})

test("the plain wording contains no technical label", () => {
  const all = [...Object.values(HEADLINES), NO_NOTE_HEADLINE, ...plainSentiment(reading({ sentiment: "positive" }), "disabled").notes].join(" ")
  assert.doesNotMatch(all, /user_text_rules_v1|rules_baseline|Transformer|probabilit|class_|validation_status|UNVALIDATED/i)
})

// ---------------------------------------------------------------------------------------------------------------------------------------- investment behaviour
const trend = (status: Finding["status"], direction: Finding["direction"], statement = "Investment contributions increased by Rs 500 compared with the previous month (10.0%)."): Finding =>
  ({ code: "investment_contribution_trend", category: "trend", status, statement, sources: ["investment_contribution_change.absolute_change"], direction, values: {} }) as Finding

test("investment status follows the backend trend: increasing, decreasing or consistent", () => {
  assert.equal(investmentBehaviour({ findings: [trend("observed", "increased")] }).status, "increasing")
  assert.equal(investmentBehaviour({ findings: [trend("observed", "decreased")] }).status, "decreasing")
  assert.equal(investmentBehaviour({ findings: [trend("observed", "unchanged")] }).status, "consistent")
  const up = investmentBehaviour({ findings: [trend("observed", "increased")] })
  assert.equal(up.label, "Increasing")
  assert.match(up.fromRecords ?? "", /Investment contributions increased/)
})

test("'unusual' is claimed only when the backend behaviour model flagged it", () => {
  assert.equal(investmentBehaviour({ findings: [], driftFlag: true }).status, "unusual")
  assert.equal(investmentBehaviour({ findings: [], anomalyFlag: true }).status, "unusual")
  assert.equal(investmentBehaviour({ findings: [trend("observed", "increased")], driftFlag: true }).status, "unusual") // the model's flag outranks a month-over-month direction
  for (const input of [{ findings: undefined }, { findings: [] }, { findings: [trend("unavailable", null)] }, { findings: [trend("observed", "increased")] }, { findings: [], driftFlag: false }, { findings: [], driftFlag: null, anomalyFlag: null }]) {
    assert.notEqual(investmentBehaviour(input).status, "unusual", JSON.stringify(input))
  }
})

test("with no comparison history the status is 'not enough history' and says so in simple English", () => {
  for (const input of [{ findings: undefined }, { findings: [] }, { findings: [trend("unavailable", null)] }, { findings: [trend("observed", null)] }]) {
    const result = investmentBehaviour(input)
    assert.equal(result.status, "not_enough_history", JSON.stringify(input))
    assert.equal(result.detail, "Not enough investment history to compare.")
    assert.equal(result.label, STATUS_LABELS.not_enough_history)
  }
  assert.equal(NOT_ENOUGH_HISTORY_DETAIL, "Not enough investment history to compare.")
  assert.match(investmentBehaviour({ findings: [trend("unavailable", null, "Investment contributions: no month-on-month change is available.")] }).fromRecords ?? "", /no month-on-month change/)
})

test("the model saying 'not unusual' counts as consistent only when both flags say so", () => {
  assert.equal(investmentBehaviour({ findings: [], driftFlag: false, anomalyFlag: false }).status, "consistent")
  assert.equal(investmentBehaviour({ findings: [], driftFlag: false, anomalyFlag: null }).status, "not_enough_history")
})

// ---------------------------------------------------------------------------------------------------------------------------------------- spending pattern
const spend = (over: Partial<SpendingInput> = {}): SpendingInput => ({ loading: false, error: null, persona: null, personaUnavailableReason: null, history: "multiple_months", ...over })

test("a spending pattern is shown only when the model returned one", () => {
  assert.deepEqual(spendingPattern(spend({ persona: "Balanced spender" })), { kind: "valid", pattern: "Balanced spender", reason: null })
  for (const input of [spend(), spend({ persona: null }), spend({ persona: "" }), spend({ persona: undefined })]) assert.notEqual(spendingPattern(input).kind, "valid")
})

test("the six situations stay apart", () => {
  assert.equal(spendingPattern(spend({ loading: true })).kind, "loading")
  assert.equal(spendingPattern(spend({ error: { unreachable: true } })).kind, "backend_unavailable")
  assert.equal(spendingPattern(spend({ error: { unreachable: false } })).kind, "model_unavailable")
  assert.equal(spendingPattern(spend({ history: "none" })).kind, "no_records")
  assert.equal(spendingPattern(spend({ history: "single_month" })).kind, "insufficient_records")
  assert.equal(spendingPattern(spend({ history: "multiple_months", personaUnavailableReason: "The expense model is not applied to this profile." })).kind, "model_unavailable")
  assert.equal(spendingPattern(spend({ history: "multiple_months", personaUnavailableReason: "The expense model is not applied to this profile." })).reason, "The expense model is not applied to this profile.")
  assert.equal(spendingPattern(spend({ history: undefined })).kind, "model_unavailable")
})

test("a failure is never turned into a pattern, even when a persona is also present", () => {
  assert.equal(spendingPattern(spend({ error: { unreachable: true }, persona: "Balanced spender" })).kind, "backend_unavailable")
  assert.equal(spendingPattern(spend({ loading: true, persona: "Balanced spender" })).kind, "loading")
})

// ---------------------------------------------------------------------------------------------------------------------------------------- the overview
const finding = (code: string, status: Finding["status"], statement: string, direction: Finding["direction"] = null, values: Record<string, number> = {}, category: Finding["category"] = "trend"): Finding =>
  ({ code, category, status, statement, sources: [code], direction, values }) as Finding

test("month labels and the date range are formatting only", () => {
  assert.equal(monthLabel("2026-03"), "Mar 2026")
  assert.equal(monthLabel("2026-12"), "Dec 2026")
  assert.equal(monthLabel("not-a-month"), "not-a-month")
  assert.equal(dateRange(["2026-05", "2026-03", "2026-04"]), "Mar 2026 to May 2026")
  assert.equal(dateRange(["2026-03"]), "Mar 2026")
  assert.equal(dateRange([]), null)
  assert.equal(dateRange(["2025-12", "2026-01"]), "Dec 2025 to Jan 2026")
})

test("the overview selects the income, spending and savings trend findings, the savings rate and the reasons for what is missing", () => {
  const findings = [
    finding("income_trend", "observed", "Income increased by Rs 1,000 compared with the previous month (2.0%).", "increased"),
    finding("expenses_trend", "observed", "Expenses decreased by Rs 500 compared with the previous month (1.0%).", "decreased"),
    finding("savings_trend", "unavailable", "Savings: no month-on-month change is available. Savings was not reported in both months."),
    finding("savings_to_income_ratio", "observed", "In 2026-08, savings were 16.2% of that month's reported income.", null, { ratio: 0.162 }, "ratio"),
    finding("expense_to_income_ratio", "unavailable", "Expenses as a share of income: Income was not reported for this month.", null, {}, "ratio"),
    finding("investment_contribution_trend", "unavailable", "Investment contributions: no month-on-month change is available."),
    finding("data_quality_1", "observed", "Income was reported on different bases (net and gross) in different months.", null, {}, "data_quality"),
  ]
  const trends = overviewTrends(findings)
  assert.deepEqual(trends.map((t) => [t.label, t.directionLabel, t.available]), [["Income", "Increased", true], ["Spending", "Decreased", true], ["Savings", null, false]])
  assert.equal(trends[0].statement, findings[0].statement) // the backend's sentence, unchanged
  assert.deepEqual(savingsRate(findings), { ratio: 0.162, statement: findings[3].statement })
  assert.deepEqual(missingDataNotes(findings), [findings[2].statement, findings[4].statement, findings[6].statement]) // not the investment finding: it has its own card
})

test("an unavailable savings rate is null, never zero, and a missing finding is absent", () => {
  assert.equal(savingsRate([finding("savings_to_income_ratio", "unavailable", "Savings as a share of income: Savings was not reported for this month.", null, {}, "ratio")])?.ratio, null)
  assert.equal(savingsRate([]), null)
  assert.deepEqual(overviewTrends([]), [])
})

test("the overview explanation is the exact approved sentence", () => {
  assert.equal(OVERVIEW_EXPLANATION, "Your financial behaviour is calculated from the monthly records you provide. It describes your numbers and does not change your risk profile, investments or recommendations.")
})

// ---------------------------------------------------------------------------------------------------------------------------------------- demo kinds
test("?demo=family selects the family demonstration only on a build that allows it, and only exactly", () => {
  assert.equal(demoKind("?demo=family", true), "family")
  assert.equal(demoKind("?demo=true", true), "individual")
  assert.equal(demoKind("?demo=family", false), null)
  for (const search of ["", "?demo", "?demo=", "?demo=Family", "?demo=families", "?demo=family&demo=true", "?demo=true&demo=true", "?demo=true&demo=family", "?demos=family"]) assert.equal(demoKind(search, true), null, search)
})

// ---------------------------------------------------------------------------------------------------------------------------------------- source rules
const NEW_FILES = [
  "src/lib/plain-sentiment.ts",
  "src/lib/investment-behaviour.ts",
  "src/lib/spending-pattern.ts",
  "src/lib/behaviour-overview.ts",
  "src/components/financial-health/behaviour-sections.tsx",
  "src/components/financial-health/financial-behaviour-real.tsx",
  "src/components/financial-health/demo-family-behaviour.tsx",
  "src/components/financial-health/demo-family-behaviour-card.tsx",
  "src/hooks/use-sentiment-model-status.ts",
]

test("the new files never use browser storage, cookies, the console, beacons or a ledger", () => {
  for (const file of NEW_FILES) assert.doesNotMatch(code(file), /localStorage|sessionStorage|indexedDB|document\.cookie|console\.|sendBeacon|window\.location|ledger|blockchain|anchor/i, file)
})

test("the new logic and views do no arithmetic on a financial figure", () => {
  for (const file of NEW_FILES) assert.doesNotMatch(code(file), /\*\s*100\b|\.reduce\(|Math\.(round|floor|ceil|abs|max|min)|\bsum\(/, file)
})

test("the new files hard-code no month, rupee amount or fictional figure", () => {
  for (const file of NEW_FILES.filter((f) => !f.endsWith("demo-family-behaviour.tsx"))) assert.doesNotMatch(code(file), /2026-\d\d|\b\d{2},\d{3}\b|\b[1-9]\d{4,}\b/, file)
})

test("the real page never substitutes demo data: the real container reads no demo hook", () => {
  const real = code("src/components/financial-health/financial-behaviour-real.tsx")
  assert.doesNotMatch(real, /useDemo|createDemo|demo-financial|DemoFamily|DemoFinancial|fictional/) // no demo hook, API call or demo view; the dev-only hint is a link component, never data
  assert.match(real, /usePersonalizedInsightQuery\(profileId, null\)/)
  assert.match(real, /useMonthlyRecordsQuery\(profileId\)/)
  assert.match(real, /useAnalysisQuery\(profileId\)/)
})

test("the family route is behind the same guard as the individual demonstration and the backend names", () => {
  assert.match(code("src/lib/api-client.ts"), /createDemoFamilyFinancialBehaviour[\s\S]*?\/api\/demo\/family-financial-behaviour/)
  assert.match(code("src/hooks/use-demo-financial-behaviour.ts"), /gcTime: 0/)
  assert.match(read("../backend/wealthpilot/api/routers/demo.py"), /\/api\/demo\/family-financial-behaviour/)
})

// ---------------------------------------------------------------------------------------------------------------------------------------- reaching the demonstration
test("a demo parameter that does not start a demonstration is reported as a PROBLEM, never silently ignored", () => {
  assert.deepEqual(demoRequest("?demo=family", true), { kind: "family", problem: null })
  assert.deepEqual(demoRequest("?demo=true", true), { kind: "individual", problem: null })
  assert.deepEqual(demoRequest("?demo=family", false), { kind: null, problem: "not_allowed" })
  assert.deepEqual(demoRequest("?demo=true", false), { kind: null, problem: "not_allowed" })
  for (const search of ["?demo=", "?demo=Family", "?demo=1", "?demo=families", "?demo=family&demo=true", "?demo=true&demo=true"]) assert.deepEqual(demoRequest(search, true), { kind: null, problem: "unknown_value" }, search)
  for (const search of ["", "?", "?x=1", "?demos=family", "?mode=family"]) assert.deepEqual(demoRequest(search, true), { kind: null, problem: null }, search) // no demo parameter: the normal page, no problem
  assert.deepEqual(demoRequest("", false), { kind: null, problem: null })
})

test("the Financial Behaviour sidebar link keeps a demonstration only inside it and only on a build that allows it", () => {
  assert.equal(behaviourLinkTarget("/financial-behaviour", "?demo=family", true), "/financial-behaviour?demo=family")
  assert.equal(behaviourLinkTarget("/financial-behaviour", "?demo=true", true), "/financial-behaviour?demo=true")
  assert.equal(behaviourLinkTarget("/financial-behaviour", "?demo=family", false), "/financial-behaviour") // a production build never carries it
  assert.equal(behaviourLinkTarget("/financial-behaviour", "", true), "/financial-behaviour")
  assert.equal(behaviourLinkTarget("/financial-behaviour", "?demo=bogus", true), "/financial-behaviour")
  assert.equal(behaviourLinkTarget("/dashboard", "?demo=family", true), "/financial-behaviour") // from any other page the link is the plain path
})
