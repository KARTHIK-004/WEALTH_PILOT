/**
 * Component cases for the Financial Behaviour page: the real-records view, the simple-English sentiment wording, the investment and spending cards, the individual loan / EMI wording and the
 * fictional FAMILY demonstration. Rendered to static HTML with react-dom/server through Vite's SSR loader and executed by tests/component.test.mjs under Node's test runner (`npm test`). No browser,
 * no DOM library and no new dependency.
 *
 * Every insight rendered here is a REAL backend response (tests/fixtures/*.json from `scripts/export_insight_fixtures.py`, tests/fixtures/demo/*.json from `scripts/export_demo_fixtures.py`);
 * the monthly-record rows are the fictional family member's own months from the same fixture. Assertions compare what is SHOWN with values IN those responses, so an invented number, a swallowed
 * `null`, demo data on the real page or a technical label outside the optional details makes a case fail.
 */
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import path from "node:path"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderToStaticMarkup } from "react-dom/server"
import { MemoryRouter } from "react-router"

import { InvestmentBehaviourView, SpendingPatternView } from "@/components/financial-health/behaviour-sections"
import { BehaviourSentimentView, type BehaviourSentimentViewProps } from "@/components/financial-health/behaviour-sentiment-view"
import { DemoFamilyView, type DemoFamilyViewProps } from "@/components/financial-health/demo-family-behaviour"
import { FinancialBehaviourRealView, type FinancialBehaviourRealViewProps } from "@/components/financial-health/financial-behaviour-real"
import { CommitmentsView } from "@/components/financial-health/individual-finances"
import { ApiClientError, ApiUnreachableError } from "@/lib/api-client"
import { DEMO_EXAMPLES, DEMO_EXAMPLE_TEXT } from "@/lib/demo-mode"
import { formatCurrency, formatPercent } from "@/lib/format"
import { investmentBehaviour } from "@/lib/investment-behaviour"
import { HEADLINES, NO_NOTE_HEADLINE, plainSentiment } from "@/lib/plain-sentiment"
import { spendingPattern } from "@/lib/spending-pattern"
import { FinancialBehaviourContent, FinancialBehaviourPage } from "@/pages/financial-behaviour-page"
import { CustomerProvider } from "@/providers/customer-context"
import type { components } from "@/types/api"

type Insight = components["schemas"]["PersonalizedInsightResponse"]
type Family = components["schemas"]["DemoFamilyFinancialBehaviourResponse"]
type MonthRecord = components["schemas"]["MonthlyRecordResponse"]

const read = (...parts: string[]): string => readFileSync(path.resolve(process.cwd(), "tests", "fixtures", ...parts), "utf8")
const insightFixture = (name: string): Insight => JSON.parse(read(`${name}.json`)) as Insight
const familyFixture = (name: string): Family => JSON.parse(read("demo", `${name}.json`)) as Family

const noop = () => {}
const FAMILY = familyFixture("family-example-text")
const PRIMARY = FAMILY.members[0]
const RECORDS: MonthRecord[] = PRIMARY.months
  .map((m) => ({ customer_id: 7, period: m.period, income: m.income, expenses: m.expenses, savings: m.savings, investment_contribution: m.investment_contribution ?? null, income_basis: "net" as const, updated_at: "2026-01-01T00:00:00Z" }))
  .reverse() // the API returns the newest month first

const HEALTH = { expense_persona: null, expense_persona_unavailable_reason: "The expense model is not applied to this profile.", savings_rate: null, behaviour_drift_flag: false, isolation_forest_anomaly: false } as never

function realProps(over: Partial<FinancialBehaviourRealViewProps> = {}): FinancialBehaviourRealViewProps {
  return {
    insight: PRIMARY.insight, insightLoading: false, insightError: null, onRetryInsight: noop, records: RECORDS, recordsLoading: false, recordsError: null, onRetryRecords: noop,
    analysisLoading: false, analysisError: null, health: HEALTH, onRetryAnalysis: noop, householdName: null, note: <p>NOTE-SLOT</p>, ...over,
  }
}
const withRouter = (node: React.ReactNode, entry = "/financial-behaviour") => (
  <MemoryRouter initialEntries={[entry]}>
    <QueryClientProvider client={new QueryClient()}>
      <CustomerProvider>{node}</CustomerProvider>
    </QueryClientProvider>
  </MemoryRouter>
)
const realHtml = (over: Partial<FinancialBehaviourRealViewProps> = {}): string => renderToStaticMarkup(withRouter(<FinancialBehaviourRealView {...realProps(over)} />))

function noteProps(over: Partial<BehaviourSentimentViewProps> = {}): BehaviourSentimentViewProps {
  return { draft: "", hasSubmittedText: false, stale: false, pending: false, loading: false, error: null, data: undefined, onDraftChange: noop, onSubmit: noop, onClear: noop, onRetry: noop, plainLanguage: true, noteOnly: true, modelState: "disabled", ...over }
}
const noteHtml = (over: Partial<BehaviourSentimentViewProps> = {}): string => renderToStaticMarkup(<MemoryRouter><BehaviourSentimentView {...noteProps(over)} /></MemoryRouter>)

function familyProps(over: Partial<DemoFamilyViewProps> = {}): DemoFamilyViewProps {
  return { data: FAMILY, loading: false, error: null, draft: DEMO_EXAMPLE_TEXT, hasSubmittedText: true, stale: false, pending: false, examples: DEMO_EXAMPLES, onUseExample: noop, onDraftChange: noop, onSubmit: noop, onClear: noop, onRetry: noop, ...over }
}
const familyHtml = (over: Partial<DemoFamilyViewProps> = {}): string => renderToStaticMarkup(<MemoryRouter><DemoFamilyView {...familyProps(over)} /></MemoryRouter>)

/** Visible text: tags and React's text-boundary comments removed, common entities decoded, whitespace collapsed. */
function textOf(markup: string): string {
  return markup.replace(/<[^>]*>/g, " ").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#x27;|&#39;/g, "'").replace(/\s+/g, " ").trim()
}
/** The markup without anything inside a (possibly nested) <details> disclosure: what an ordinary user sees without opening one. */
function outsideDetails(markup: string): string {
  let depth = 0
  let out = ""
  let last = 0
  for (const m of markup.matchAll(/<details\b|<\/details>/g)) {
    const at = m.index ?? 0
    if (depth === 0) out += markup.slice(last, at)
    depth += m[0] === "</details>" ? -1 : 1
    if (depth === 0) last = at + m[0].length
  }
  return out + (depth === 0 ? markup.slice(last) : "")
}
/** One fictional member's own section (the nth <article>), without the household totals or the note that follow it. */
const memberSection = (markup: string, index: number): string => (markup.split("<article")[index + 1] ?? "").split("</article>")[0]
const occurrences = (haystack: string, needle: string): number => haystack.split(needle).length - 1
const ids = (markup: string): string[] => [...markup.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1])

export const cases: Record<string, () => void | Promise<void>> = {
  // ------------------------------------------------------------------------------------------------------------------------------ the real overview
  "real records: heading, the exact explanation, reported months, date range, savings rate, and the three trends are the backend's findings"() {
    const markup = realHtml()
    const text = textOf(markup)
    assert.match(text, /Financial behaviour overview/)
    assert.ok(text.includes("Your financial behaviour is calculated from the monthly records you provide. It describes your numbers and does not change your risk profile, investments or recommendations."))
    assert.match(text, new RegExp(`Reported months ${PRIMARY.insight.behaviour.observation_count}`))
    assert.match(text, /Date range Mar 2026 to Aug 2026/)
    const ratio = PRIMARY.insight.behaviour.findings.find((f) => f.code === "savings_to_income_ratio")?.values?.ratio
    assert.ok(typeof ratio === "number" && text.includes(`Savings rate ${formatPercent(ratio, 1)}`))
    for (const code of ["income_trend", "expenses_trend", "savings_trend"]) {
      const finding = PRIMARY.insight.behaviour.findings.find((f) => f.code === code)
      assert.ok(finding && text.includes(finding.statement), code)
    }
    assert.match(text, /Income Unchanged|Income Increased|Income Decreased/)
    assert.match(text, /Spending Decreased/)
    assert.match(text, /Savings Increased/)
    assert.match(text, /Trends and month-over-month changes/)
  },

  "real records: the table is oldest month first with the chart beside it, and a missing amount says 'Not provided', never zero"() {
    const sparse: MonthRecord[] = [{ ...RECORDS[0], income: null, savings: null }, ...RECORDS.slice(1)] // the newest month (Aug) has no income or savings reported
    const markup = realHtml({ records: sparse })
    const rows = [...markup.matchAll(/<th[^>]*scope="row"[^>]*>([^<]*)<\/th>/g)].map((m) => m[1])
    assert.deepEqual(rows, ["Mar 2026", "Apr 2026", "May 2026", "Jun 2026", "Jul 2026", "Aug 2026"])
    assert.match(markup, /role="img"[^>]*aria-label="Line chart of reported income, expenses and savings by month\./)
    assert.match(markup, /<caption[^>]*>Your reported months\./)
    const march = /<tr[^>]*>(?:(?!<\/tr>).)*Mar 2026(?:(?!<\/tr>).)*<\/tr>/s.exec(markup)
    assert.ok(march)
    assert.ok(textOf(march[0]).includes(formatCurrency(PRIMARY.months[0].income)))
    const aug = textOf(/<tr[^>]*>(?:(?!<\/tr>).)*Aug 2026(?:(?!<\/tr>).)*<\/tr>/s.exec(markup)?.[0] ?? "")
    assert.match(aug, /Not provided/)
    assert.doesNotMatch(aug, /₹ ?0\b/)
    assert.match(markup, /<a[^>]*href="\/profile"[^>]*>Add or edit your monthly records \(Customer Profile\)<\/a>/)
  },

  "no records: the existing empty state, a link to add records, and no value, chart, trend or invented status"() {
    const empty = insightFixture("no-records-no-text")
    const markup = realHtml({ insight: empty, records: [], health: undefined })
    const text = textOf(markup)
    assert.match(text, /No monthly records yet/)
    assert.match(text, /Add your monthly income, spending and savings to see your behaviour here\. Nothing is assumed until you do\./)
    assert.match(markup, /<a[^>]*href="\/profile"/)
    assert.doesNotMatch(text, /Reported months \d|Date range|Savings rate|Trends and month-over-month|Your monthly records/)
    assert.doesNotMatch(markup, /role="img"/)
    assert.match(text, /Not enough investment history to compare\./)
    assert.doesNotMatch(text, /Unusual/)
    assert.match(markup, /data-state="no_records"/)
  },

  "loading, and an overview error: skeletons with no values, and 'Service unavailable' with a retry and no values"() {
    const loading = realHtml({ insight: undefined, insightLoading: true, records: undefined, recordsLoading: true, analysisLoading: true, health: undefined })
    assert.match(loading, /aria-busy="true"/)
    assert.match(loading, /role="status"/)
    assert.doesNotMatch(textOf(loading), /Reported months \d|₹|Savings rate/)
    const failed = textOf(realHtml({ insight: undefined, insightError: new ApiUnreachableError(new Error("down")), records: undefined, recordsError: new ApiUnreachableError(new Error("down")), health: undefined }))
    assert.match(failed, /Service unavailable/)
    assert.match(failed, /Try again/)
    assert.doesNotMatch(failed, /Reported months \d|₹|Savings rate|Fictional|Demo/)
  },

  // ------------------------------------------------------------------------------------------------------------------------------ investment behaviour
  "investment behaviour: increasing from the backend trend, unusual only from the model flag, and not enough history otherwise"() {
    const increasing = textOf(realHtml())
    assert.match(increasing, /Investment behaviour/)
    assert.match(increasing, /How your recent investing activity compares with your own history\./)
    assert.match(increasing, /Behaviour status Increasing/)
    assert.match(increasing, /Your latest monthly investment is higher than the month before\./)
    const unusual = textOf(realHtml({ health: { ...(HEALTH as object), behaviour_drift_flag: true } as never }))
    assert.match(unusual, /Behaviour status Unusual/)
    const none = textOf(realHtml({ insight: PRIMARY.insight, records: RECORDS, health: undefined }))
    assert.doesNotMatch(none, /Behaviour status Unusual/)
    const dependent = FAMILY.members[2].insight
    const noHistory = textOf(realHtml({ insight: dependent, health: undefined }))
    assert.match(noHistory, /Behaviour status Not enough history/)
    assert.match(noHistory, /Not enough investment history to compare\./)
    assert.doesNotMatch(noHistory, /Behaviour status Unusual/)
  },

  "investment behaviour: every status renders with its own words and the view marks the status for tests and assistive wiring"() {
    const cases: [Parameters<typeof investmentBehaviour>[0], string][] = [
      [{ findings: PRIMARY.insight.behaviour.findings }, "increasing"],
      [{ findings: [], driftFlag: true }, "unusual"],
      [{ findings: [], driftFlag: false, anomalyFlag: false }, "consistent"],
      [{ findings: undefined }, "not_enough_history"],
    ]
    for (const [input, status] of cases) {
      const markup = renderToStaticMarkup(<InvestmentBehaviourView behaviour={investmentBehaviour(input)} loading={false} />)
      assert.match(markup, new RegExp(`data-status="${status}"`))
      assert.match(markup, /aria-labelledby="investment-heading"/)
      assert.match(markup, /id="investment-heading"/)
    }
    const decreasing = FAMILY.members[1].insight.behaviour.findings.map((f) => (f.code === "investment_contribution_trend" ? { ...f, direction: "decreased" as const } : f))
    assert.equal(investmentBehaviour({ findings: decreasing }).status, "decreasing")
  },

  // ------------------------------------------------------------------------------------------------------------------------------ spending pattern
  "spending pattern: a valid model result is shown as returned"() {
    const state = spendingPattern({ loading: false, error: null, persona: "Balanced spender", personaUnavailableReason: null, history: "multiple_months" })
    const markup = renderToStaticMarkup(<SpendingPatternView state={state} />)
    assert.match(textOf(markup), /Spending pattern Your spending pattern Balanced spender/)
    assert.match(markup, /data-state="valid"/)
    assert.doesNotMatch(textOf(markup), /Not available/)
  },

  "spending pattern: unavailable says exactly 'Not available' and why the pattern is only shown when the model can be applied, for each situation"() {
    const base = { loading: false, error: null, persona: null, personaUnavailableReason: "The expense model is not applied to this profile.", history: "multiple_months" as const }
    const states: [Parameters<typeof spendingPattern>[0], string, RegExp][] = [
      [{ ...base, history: "none" }, "no_records", /No records No monthly records have been added yet\./],
      [{ ...base, history: "single_month" }, "insufficient_records", /Not enough records Only one month has been recorded\./],
      [base, "model_unavailable", /Model not available The expense model is not applied to this profile\./],
      [{ ...base, error: { unreachable: false } }, "model_unavailable", /Model not available The analysis could not be completed/],
      [{ ...base, error: { unreachable: true } }, "backend_unavailable", /Service unavailable The service could not be reached/],
    ]
    for (const [input, kind, reason] of states) {
      const markup = renderToStaticMarkup(<SpendingPatternView state={spendingPattern(input)} onRetry={noop} />)
      const text = textOf(markup)
      assert.match(markup, new RegExp(`data-state="${kind}"`), kind)
      assert.match(text, /Spending pattern Not available A spending pattern is shown only when the spending model can be applied to this profile\./, kind)
      assert.match(text, reason, kind)
    }
    const unreachable = renderToStaticMarkup(<SpendingPatternView state={spendingPattern({ ...base, error: { unreachable: true } })} onRetry={noop} />)
    assert.match(unreachable, /role="alert"/)
    assert.match(textOf(unreachable), /Try again/)
    assert.match(renderToStaticMarkup(<SpendingPatternView state={spendingPattern({ ...base, loading: true })} />), /role="status"/)
  },

  "spending pattern on the real page comes from the stored analysis and never from the records"() {
    const valid = textOf(realHtml({ health: { ...(HEALTH as object), expense_persona: "Balanced spender" } as never }))
    assert.match(valid, /Your spending pattern Balanced spender/)
    const missing = textOf(realHtml())
    assert.match(missing, /Spending pattern Not available/)
    assert.doesNotMatch(missing, /Balanced spender/)
    const down = realHtml({ health: undefined, analysisError: new ApiUnreachableError(new Error("down")) })
    assert.match(down, /data-state="backend_unavailable"/)
    assert.match(textOf(down), /Reported months \d/) // the records still show: only the spending card reports the outage
  },

  // ------------------------------------------------------------------------------------------------------------------------------ loans and EMIs
  "individual loan and EMI wording is exact and no zero, unknown or estimated figure is shown"() {
    const text = textOf(renderToStaticMarkup(<MemoryRouter><CommitmentsView householdName={null} /></MemoryRouter>))
    assert.match(text, /Not recorded for an individual/)
    assert.ok(text.includes("WealthPilot does not record loans or EMIs for an individual, so none are shown and none are assumed."))
    assert.doesNotMatch(text, /₹|\b0\b|unknown|estimated|inferred|Not provided/i)
    const real = textOf(realHtml())
    assert.ok(real.includes("WealthPilot does not record loans or EMIs for an individual, so none are shown and none are assumed."))
    const member = textOf(realHtml({ householdName: "Sharma household" }))
    assert.match(member, /The “Sharma household” household records its own loans and EMIs/)
    assert.match(member, /not part of this individual view/)
  },

  // ------------------------------------------------------------------------------------------------------------------------------ sentiment in simple English
  "sentiment: each fixture reading is said in the exact simple-English sentence with its short explanations"() {
    const expectations: [string, string][] = [
      ["no-records-with-text", HEADLINES.positive],
      ["conflict", HEADLINES.negative],
      ["capital-preservation", HEADLINES.neutral],
      ["mixed-growth-conflict", HEADLINES.mixed],
      ["negated", HEADLINES.uncertain],
      ["weak-neutral", HEADLINES.uncertain],
      ["unrelated", HEADLINES.abstained],
      ["too-short", HEADLINES.abstained],
      ["ambiguous", HEADLINES.abstained],
      ["records-only", NO_NOTE_HEADLINE],
    ]
    for (const [name, headline] of expectations) {
      const markup = noteHtml({ data: insightFixture(name), draft: "x", hasSubmittedText: true })
      const text = textOf(outsideDetails(markup))
      assert.ok(text.includes(headline), `${name}: ${headline}`)
      assert.match(markup, /aria-labelledby="plain-sentiment-heading"/)
      if (name !== "records-only") {
        assert.ok(text.includes("This is based only on the words you chose to write."), name)
        assert.ok(text.includes("This does not change your risk profile, allocation or recommendations."), name)
        assert.ok(text.includes("The model-based sentiment feature is currently disabled."), name)
        assert.ok(text.includes("Confidence and intensity are not available."), name)
      }
    }
  },

  "sentiment: the technical labels are only inside the optional detailed reading, with method, model status, confidence and intensity"() {
    const markup = noteHtml({ data: insightFixture("conflict"), draft: "x", hasSubmittedText: true })
    const visible = textOf(outsideDetails(markup))
    assert.doesNotMatch(visible, /user_text_rules_v1|rules_baseline|UNVALIDATED|Class probabilities|validation_status|Transformer/i)
    assert.match(markup, /<summary[^>]*>[\s\S]*?Detailed reading \(technical\)/)
    const details = textOf(markup.slice(markup.indexOf("Detailed reading (technical)")))
    assert.match(details, /Method user_text_rules_v1/)
    assert.match(details, /Reading method rules_baseline/)
    assert.match(details, /Model status disabled/)
    assert.match(details, /Confidence unavailable/)
    assert.match(details, /Intensity unavailable \(null\)/)
  },

  "sentiment: the optional-note statement is shown, and the note-only view has no records column"() {
    const text = textOf(noteHtml({ data: insightFixture("conflict"), draft: "x", hasSubmittedText: true }))
    assert.ok(text.includes("Your written note is optional. This section describes how your words read; it is not a fact about you."))
    assert.doesNotMatch(text, /Observed from your records|What your records show|Expressed in your own words/)
    assert.match(textOf(noteHtml({ data: undefined })), /Your written note is optional\./)
  },

  "sentiment: without the model status the 'disabled' sentence is left out (nothing is claimed that the backend did not say)"() {
    const markup = noteHtml({ data: insightFixture("conflict"), draft: "x", hasSubmittedText: true, modelState: undefined })
    assert.ok(!textOf(outsideDetails(markup)).includes("The model-based sentiment feature is currently disabled."))
    assert.ok(textOf(outsideDetails(markup)).includes("Confidence and intensity are not available."))
  },

  "sentiment: the default view (not plain language) is unchanged by the new option"() {
    const markup = renderToStaticMarkup(<MemoryRouter><BehaviourSentimentView {...noteProps({ data: insightFixture("conflict"), plainLanguage: false, noteOnly: false, draft: "x", hasSubmittedText: true })} /></MemoryRouter>)
    assert.doesNotMatch(markup, /plain-sentiment-heading|Detailed reading \(technical\)/)
    assert.match(textOf(markup), /Observed from your records/)
  },

  // ------------------------------------------------------------------------------------------------------------------------------ accessibility on the real view
  "real view: named sections, unique ids, one table caption, and the note slot, for assistive technology"() {
    const markup = realHtml()
    const all = ids(markup)
    assert.equal(new Set(all).size, all.length, "ids are unique")
    for (const target of [...markup.matchAll(/aria-labelledby="([^"]+)"/g)].map((m) => m[1])) assert.ok(all.includes(target), `aria-labelledby target ${target} exists`)
    assert.ok(occurrences(markup, "<h2") >= 5)
    assert.match(markup, /class="[^"]*overflow-x-auto[^"]*"[^>]*role="region"[^>]*tabindex="0"/)
    assert.match(markup, /grid-cols-1[^"]*sm:grid-cols-2[^"]*lg:grid-cols-3/)
    assert.match(markup, /md:grid-cols-2/)
    assert.match(markup, /id="note-heading"/)
    assert.match(textOf(markup), /Your optional written note NOTE-SLOT/)
  },

  // ------------------------------------------------------------------------------------------------------------------------------ the container with seeded queries
  "the page container reads the records, the insight, the analysis, the household and the model status for the profile and renders them"() {
    const client = new QueryClient()
    client.setQueryData(["personalized-insight", 7, null], insightFixture("conflict"))
    client.setQueryData(["monthly-records", 7], { customer_id: 7, records: RECORDS })
    client.setQueryData(["analysis", 7], { financial_health: HEALTH })
    client.setQueryData(["household", 7], { household: null, membership: null })
    client.setQueryData(["sentiment-model-status"], { enabled: false, state: "disabled", reason: null, method_when_used: "rules_baseline" })
    const markup = renderToStaticMarkup(
      <MemoryRouter>
        <QueryClientProvider client={client}>
          <FinancialBehaviourContent profileId={7} />
        </QueryClientProvider>
      </MemoryRouter>,
    )
    const text = textOf(markup)
    assert.match(text, /Financial behaviour overview/)
    assert.match(text, /Date range Mar 2026 to Aug 2026/)
    assert.match(text, /Your monthly records/)
    assert.match(text, /Investment behaviour/)
    assert.match(text, /Spending pattern Not available/)
    assert.match(text, /Not recorded for an individual/)
    assert.match(text, /Your optional written note/)
    assert.ok(textOf(outsideDetails(markup)).includes(HEADLINES.negative))
    assert.ok(textOf(outsideDetails(markup)).includes("The model-based sentiment feature is currently disabled."))
    assert.doesNotMatch(textOf(outsideDetails(markup)), /Demo|fictional|user_text_rules_v1/i)
    assert.equal(occurrences(markup, "<h1"), 1)
  },

  "the page container with nothing seeded shows loading states and no values, never demo data"() {
    const markup = renderToStaticMarkup(<MemoryRouter><QueryClientProvider client={new QueryClient()}><FinancialBehaviourContent profileId={7} /></QueryClientProvider></MemoryRouter>)
    const text = textOf(markup)
    assert.match(text, /Reading your monthly records…/)
    assert.doesNotMatch(text, /Reported months \d|Demo|fictional|₹/i)
  },

  // ------------------------------------------------------------------------------------------------------------------------------ the family demonstration
  "family demo: the exact label, three fictional members with roles, and a section for each"() {
    const markup = familyHtml()
    const text = textOf(markup)
    assert.match(markup, /role="status"[^>]*aria-label="Family demonstration mode is active"/)
    assert.match(text, /Demo data — fictional family example/)
    assert.ok(text.includes(FAMILY.notice))
    assert.match(text, /The Demo family \(fictional\): 3 members/)
    for (const member of FAMILY.members) {
      assert.ok(text.includes(member.label) && text.includes(member.role), member.label)
      assert.match(markup, new RegExp(`<h2 id="member-\\d-title"[^>]*>${member.label.replace(/[()]/g, "\\$&")}</h2>`))
    }
    assert.equal(occurrences(markup, "<article"), 3)
    assert.match(text, /Optional written note \(Primary member \(demo\)\)/)
    assert.doesNotMatch(text, /Service unavailable/)
  },

  "family demo: each member's months, calculated changes and investing status come from the response"() {
    const markup = familyHtml()
    assert.equal(occurrences(markup, 'scope="row"'), 6 + 6 + 3) // one row header per fictional month
    const status = (index: number): string => {
      return /data-status="([a-z_]+)"/.exec(memberSection(markup, index))?.[1] ?? ""
    }
    assert.deepEqual([0, 1, 2].map(status), ["increasing", "increasing", "not_enough_history"])
    const dependent = textOf(memberSection(markup, 2))
    assert.match(dependent, /Not enough investment history to compare\./)
    assert.match(dependent, /Not provided/) // income and savings were not reported
    assert.match(dependent, /Not available/)
    assert.doesNotMatch(dependent, /Unusual/)
  },

  "family demo: missing data is explained in the backend's words, never shown as zero"() {
    const dependent = FAMILY.members[2]
    const text = textOf(memberSection(familyHtml(), 2))
    const incomeTrend = dependent.insight.behaviour.findings.find((f) => f.code === "income_trend")
    assert.ok(incomeTrend && text.includes(incomeTrend.statement))
    assert.match(text, /Why some values are not shown/)
    const zero = /(?<![\d.])0\.0%|₹ ?0(?![\d,])/.exec(text) // no zero amount and no zero change (10.0% is not zero)
    assert.equal(zero, null, zero ? text.slice(Math.max(0, zero.index - 80), zero.index + 40) : "")
    const partner = textOf(memberSection(familyHtml(), 1))
    assert.match(partner, /Behaviour status Increasing/)
  },

  "family demo: every member says 'Not recorded for an individual' and the household's own loans and EMIs are shown from its records"() {
    const markup = familyHtml()
    const text = textOf(markup)
    assert.equal(occurrences(text, "Not recorded for an individual"), 3)
    assert.equal(occurrences(text, "WealthPilot does not record loans or EMIs for an individual, so none are shown and none are assumed."), 3)
    assert.match(text, /Household totals \(fictional\)/)
    assert.match(text, /Outstanding liabilities/)
    assert.match(text, /Recorded monthly liability payments/)
    const summary = FAMILY.household_summary
    assert.ok(text.includes(formatCurrency(summary.liabilities.outstanding as number)))
    assert.ok(text.includes(formatCurrency(summary.liabilities.monthly_payment as number)))
    assert.match(text, /A loan with no stated payment is shown as not provided, never as zero\./)
    assert.match(text, /not the members' months added together/)
  },

  "family demo: the spending pattern is 'Not available' for each fictional member, with the rule sentence"() {
    const markup = familyHtml()
    assert.equal(occurrences(markup, 'data-state="model_unavailable"'), 3)
    const text = textOf(markup)
    assert.equal(occurrences(text, "A spending pattern is shown only when the spending model can be applied to this profile."), 3)
    assert.match(text, /This is fictional demo data, so the spending model is not applied to it\./)
    assert.doesNotMatch(text, /Your spending pattern [A-Z]/)
  },

  "family demo: the primary member's note is read in simple English, technical labels only inside the details"() {
    const markup = familyHtml()
    const visible = textOf(outsideDetails(markup))
    const primary = FAMILY.members[0].insight.user_sentiment
    assert.equal(primary.method, "rules_baseline")
    assert.equal(primary.confidence, null)
    assert.equal(primary.sentiment_intensity, null)
    assert.equal(FAMILY.sentiment_model.state, "disabled")
    assert.ok(visible.includes(plainSentiment(primary, "disabled").headline))
    assert.ok(visible.includes("The model-based sentiment feature is currently disabled."))
    assert.doesNotMatch(visible, /user_text_rules_v1|rules_baseline/)
    assert.match(textOf(markup), /Method user_text_rules_v1/)
    for (const name of ["family-records-only", "family-quoted"]) {
      const text = textOf(outsideDetails(familyHtml({ data: familyFixture(name) })))
      assert.ok(text.includes(name === "family-records-only" ? NO_NOTE_HEADLINE : HEADLINES.abstained), name)
    }
  },

  "family demo: unique ids, named regions, scrollable tables and a responsive layout"() {
    const markup = familyHtml()
    const all = ids(markup)
    assert.equal(new Set(all).size, all.length, "ids are unique across the members")
    for (const target of [...markup.matchAll(/aria-labelledby="([^"]+)"/g)].map((m) => m[1])) assert.ok(all.includes(target), `aria-labelledby target ${target} exists`)
    assert.ok(occurrences(markup, "<h2") >= 3 + 3 * 3 + 2)
    assert.equal(occurrences(markup, 'role="region"') >= 3, true)
    assert.equal(occurrences(markup, "overflow-x-auto") >= 3, true)
    assert.equal(occurrences(markup, "<caption") >= 3, true)
    assert.match(markup, /<a[^>]*href="\/financial-behaviour"[^>]*>Leave demonstration mode<\/a>/)
    assert.match(markup, /md:grid-cols-2/)
    assert.doesNotMatch(markup, /<button(?![^>]*type="(?:button|submit)")/)
  },

  "family demo: loading, a backend outage and a server with demo mode off are three different, honest states"() {
    const loading = familyHtml({ data: undefined, loading: true })
    assert.match(loading, /aria-busy="true"/)
    assert.doesNotMatch(textOf(loading), /₹|Primary member/)
    const down = textOf(familyHtml({ data: undefined, error: new ApiUnreachableError(new Error("down")) }))
    assert.match(down, /Service unavailable/)
    assert.match(down, /Demo data — fictional family example/)
    assert.doesNotMatch(down, /₹|Primary member|Household totals/)
    const off = textOf(familyHtml({ data: undefined, error: new ApiClientError({ type: "about:blank", title: "Demo mode is not enabled", status: 404, detail: "off" }) }))
    assert.match(off, /Demonstration mode is switched off on the server/)
    assert.doesNotMatch(off, /Service unavailable|₹|Primary member/)
    const other = textOf(familyHtml({ data: undefined, error: new ApiClientError({ type: "about:blank", title: "Internal server error", status: 500, detail: "x" }) }))
    assert.match(other, /We couldn't complete this analysis/)
    assert.doesNotMatch(other, /₹|Primary member/)
  },

  "family demo fixtures: fictional, labelled, model disabled, no confidence or intensity, customer zero"() {
    for (const name of ["family-records-only", "family-example-text", "family-quoted"]) {
      const data = familyFixture(name)
      assert.equal(data.demo, true, name)
      assert.equal(data.scenario, "family", name)
      assert.equal(data.data_source, "demo_fixture", name)
      assert.equal(data.example_text, DEMO_EXAMPLE_TEXT, name)
      assert.ok(data.notice.startsWith("Demo data — fictional family example"), name)
      assert.equal(data.sentiment_model.enabled, false, name)
      assert.equal(data.sentiment_model.state, "disabled", name)
      assert.equal(data.household_summary.household_id, 0, name)
      for (const member of data.members) {
        assert.ok(member.label.endsWith("(demo)"), name)
        assert.equal(member.insight.customer_id, 0, name)
        assert.equal(member.insight.user_sentiment.confidence, null, name)
        assert.equal(member.insight.user_sentiment.sentiment_intensity, null, name)
        assert.equal(member.insight.user_sentiment.intensity_available, false, name)
        assert.ok(member.insight.user_sentiment.method === "rules_baseline" || member.insight.user_sentiment.method === "unavailable", name)
      }
    }
  },

  // ------------------------------------------------------------------------------------------------------------------------------ the page and ?demo=family
  "the page: ?demo=family on a build that allows it shows the fictional family and needs no profile"() {
    const client = new QueryClient()
    client.setQueryData(["demo-family-financial-behaviour", DEMO_EXAMPLE_TEXT], FAMILY)
    const markup = renderToStaticMarkup(
      <MemoryRouter initialEntries={["/financial-behaviour?demo=family"]}>
        <QueryClientProvider client={client}>
          <CustomerProvider>
            <FinancialBehaviourPage allowDemo />
          </CustomerProvider>
        </QueryClientProvider>
      </MemoryRouter>,
    )
    const text = textOf(markup)
    assert.match(text, /Demo data — fictional family example/)
    assert.match(text, /Primary member \(demo\)/)
    assert.doesNotMatch(text, /Create Profile/)
    assert.equal(occurrences(markup, "<h1"), 1)
  },

  "the page: ?demo=family is ignored on a build that does not allow it, and every other value is the normal page"() {
    const client = new QueryClient()
    client.setQueryData(["demo-family-financial-behaviour", DEMO_EXAMPLE_TEXT], FAMILY)
    const html = (entry: string, allow: boolean) =>
      textOf(renderToStaticMarkup(<MemoryRouter initialEntries={[entry]}><QueryClientProvider client={client}><CustomerProvider><FinancialBehaviourPage allowDemo={allow} /></CustomerProvider></QueryClientProvider></MemoryRouter>))
    const blocked = html("/financial-behaviour?demo=family", false)
    assert.match(blocked, /Create Profile/)
    assert.match(blocked, /Demonstration mode is not active/) // the request is announced, never silently dropped
    assert.doesNotMatch(blocked, /Demo data — fictional family example|Primary member/)
    for (const query of ["?demo=Family", "?demo=families", "?demo=family&demo=true", "?demo="]) {
      const text = html(`/financial-behaviour${query}`, true)
      assert.match(text, /Create Profile/, query)
      assert.match(text, /Demonstration mode is not active/, query)
      assert.doesNotMatch(text, /Demo data — fictional family example|Primary member/, query)
    }
    for (const query of ["", "?mode=family"]) { // no demo parameter at all: the plain normal page, with no notice
      const text = html(`/financial-behaviour${query}`, true)
      assert.match(text, /Create Profile/, query)
      assert.doesNotMatch(text, /Demonstration mode|Primary member/, query)
    }
  },

  "the page: ?demo=true still shows the individual demonstration, now in simple English"() {
    const client = new QueryClient()
    client.setQueryData(["demo-financial-behaviour", DEMO_EXAMPLE_TEXT], JSON.parse(read("demo", "demo-example-text.json")))
    const markup = renderToStaticMarkup(
      <MemoryRouter initialEntries={["/financial-behaviour?demo=true"]}>
        <QueryClientProvider client={client}>
          <CustomerProvider>
            <FinancialBehaviourPage allowDemo />
          </CustomerProvider>
        </QueryClientProvider>
      </MemoryRouter>,
    )
    const text = textOf(markup)
    assert.match(text, /Demonstration mode: fictional data/)
    assert.match(text, /Monthly records \(fictional demo months\)/)
    assert.match(text, /How your note reads/)
    assert.ok(textOf(outsideDetails(markup)).includes("The model-based sentiment feature is currently disabled."))
    assert.doesNotMatch(textOf(outsideDetails(markup)), /Active method user_text_rules_v1/)
    assert.match(text, /Active method user_text_rules_v1/) // inside the technical details
  },
}
