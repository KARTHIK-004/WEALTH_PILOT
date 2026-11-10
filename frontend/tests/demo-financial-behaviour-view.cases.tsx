/**
 * Component cases for the demonstration mode of "Financial Behaviour & Sentiment" (`?demo=true`, development only), rendered to static HTML with react-dom/server through Vite's SSR loader and
 * executed by tests/component.test.mjs under Node's built-in test runner (`npm test`). No browser, no DOM library and no new dependency.
 *
 * Every response rendered here is a REAL response of the backend's demo route, captured by `scripts/export_demo_fixtures.py` (fictional months, invented sentences);
 * `tests/backend/api/test_demo_financial_behaviour.py` fails if a fixture drifts. Assertions compare what is SHOWN with the values IN the response, so an invented number, a swallowed `null`, demo
 * data shown after a failure, or demo mode leaking into the normal page makes a case fail. Typing, focus and clicking are covered by the pure transition tests in tests/user-text-input.test.ts.
 */
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import path from "node:path"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderToStaticMarkup } from "react-dom/server"
import { MemoryRouter } from "react-router"

import { BehaviourSentimentView } from "@/components/financial-health/behaviour-sentiment-view"
import { DemoFinancialBehaviourView, type DemoFinancialBehaviourViewProps } from "@/components/financial-health/demo-financial-behaviour"
import { ApiClientError, ApiUnreachableError } from "@/lib/api-client"
import { DEMO_EXAMPLES, DEMO_EXAMPLE_TEXT } from "@/lib/demo-mode"
import { formatCurrency, formatPercent } from "@/lib/format"
import { ABSTAIN_MESSAGE, NO_TEXT_MESSAGE, UNRELATED_MESSAGE, VALIDATED_MODEL_LABEL } from "@/lib/user-text-input"
import { FinancialBehaviourPage } from "@/pages/financial-behaviour-page"
import { CustomerProvider } from "@/providers/customer-context"
import type { components } from "@/types/api"

type Demo = components["schemas"]["DemoFinancialBehaviourResponse"]

function fixture(name: string): Demo {
  return JSON.parse(readFileSync(path.resolve(process.cwd(), "tests", "fixtures", "demo", `${name}.json`), "utf8")) as Demo
}

const noop = () => {}
function propsFor(over: Partial<DemoFinancialBehaviourViewProps> = {}): DemoFinancialBehaviourViewProps {
  return {
    data: undefined,
    loading: false,
    error: null,
    draft: "",
    hasSubmittedText: false,
    stale: false,
    pending: false,
    examples: DEMO_EXAMPLES,
    onUseExample: noop,
    onDraftChange: noop,
    onSubmit: noop,
    onClear: noop,
    onRetry: noop,
    ...over,
  }
}
const html = (over: Partial<DemoFinancialBehaviourViewProps> = {}): string =>
  renderToStaticMarkup(
    <MemoryRouter>
      <DemoFinancialBehaviourView {...propsFor(over)} />
    </MemoryRouter>,
  )
const pageHtml = (entry: string, allowDemo: boolean, client = new QueryClient()): string =>
  renderToStaticMarkup(
    <MemoryRouter initialEntries={[entry]}>
      <QueryClientProvider client={client}>
        <CustomerProvider>
          <FinancialBehaviourPage allowDemo={allowDemo} />
        </CustomerProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  )
const seeded = (name: string): QueryClient => {
  const client = new QueryClient()
  client.setQueryData(["demo-financial-behaviour", DEMO_EXAMPLE_TEXT], fixture(name))
  return client
}

/** Visible text: tags and React's text-boundary comments removed, common entities decoded, whitespace collapsed. */
function textOf(markup: string): string {
  return markup
    .replace(/<[^>]*>/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#x27;|&#39;/g, "'")
    .replace(/\s+/g, " ")
    .trim()
}
const occurrences = (haystack: string, needle: string): number => haystack.split(needle).length - 1
const signed = (value: number | null, digits = 1): string => (value === null ? "Not available" : `${value > 0 ? "+" : ""}${formatPercent(value, digits)}`)
const rowFor = (markup: string, period: string): string => {
  const match = new RegExp(`<tr[^>]*>(?:(?!</tr>).)*>${period}</th>(?:(?!</tr>).)*</tr>`, "s").exec(markup)
  assert.ok(match, `row for ${period} not found`)
  return textOf(match[0])
}

export const cases: Record<string, () => void | Promise<void>> = {
  "demo view: banner, headings, and six fictional months in a captioned table with the chart beside it"() {
    const data = fixture("demo-example-text")
    const markup = html({ data, draft: DEMO_EXAMPLE_TEXT, hasSubmittedText: true })
    const text = textOf(markup)
    assert.match(markup, /role="status"[^>]*aria-label="Demonstration mode is active"/)
    assert.match(text, /Demonstration mode: fictional data/)
    assert.ok(text.includes(data.notice))
    assert.match(text, /Monthly records \(fictional demo months\)/)
    assert.match(text, /6 reported months/)
    assert.equal(data.months.length, 6)
    assert.equal(occurrences(markup, 'scope="row"'), 6) // one row header per month
    assert.match(markup, /<caption[^>]*>Fictional monthly records with calculated ratios/)
    assert.equal(occurrences(markup, 'scope="col"'), 8)
    for (const month of data.months) {
      const row = rowFor(markup, month.period)
      assert.ok(row.includes(formatCurrency(month.income)) && row.includes(formatCurrency(month.expenses)) && row.includes(formatCurrency(month.savings)), month.period)
    }
    assert.match(markup, /role="img"[^>]*aria-label="Line chart of reported income, expenses and savings by month\./) // the chart is named and has the table beside it
  },

  "every ratio and change shown is the backend's own value; a missing one is 'Not available' with its reason, never zero"() {
    const data = fixture("demo-example-text")
    const markup = html({ data })
    for (const month of data.months) {
      const row = rowFor(markup, month.period)
      const ratios = [formatPercent(month.expense_to_income.value, 1), formatPercent(month.savings_to_income.value, 1)]
      assert.ok(ratios.every((r) => row.includes(r)), `${month.period} ratios`)
      assert.ok(row.includes(signed(month.expenses_change.relative_change.value)) && row.includes(signed(month.savings_change.relative_change.value)), `${month.period} changes`)
    }
    const first = rowFor(markup, data.months[0].period)
    assert.match(first, /Not available \(No record for the month before 2026-03, so no change can be measured\.\)/)
    assert.ok(!/ 0\.0% /.test(first) && !/\+0\.0%/.test(first)) // an unavailable change is never rendered as zero
  },

  "the behaviour summary shows the month count and the latest month's own savings rate and changes"() {
    const data = fixture("demo-example-text")
    const latest = data.months[data.months.length - 1]
    const text = textOf(html({ data }))
    assert.match(text, /Behaviour summary/)
    assert.match(text, new RegExp(`Reported months ${data.insight.behaviour.observation_count}`))
    assert.ok(text.includes(`Savings rate, ${latest.period} ${formatPercent(latest.savings_to_income.value, 1)}`))
    assert.ok(text.includes(`Spending change, ${latest.period} ${signed(latest.expenses_change.relative_change.value)}`))
    assert.ok(text.includes(`Savings change, ${latest.period} ${signed(latest.savings_change.relative_change.value)}`))
    assert.ok(text.includes(`${formatCurrency(data.months[0].income)} to ${formatCurrency(latest.income)}`)) // income: the first and latest REPORTED amounts, no calculated trend
  },

  "behaviour facts come from the response and the reading is a suggestion that is informational only"() {
    const data = fixture("demo-example-text")
    const text = textOf(html({ data, draft: DEMO_EXAMPLE_TEXT, hasSubmittedText: true }))
    // the month-count sentence is shown separately ("6 reported months"), as on the real page; every other observed fact is listed
    for (const statement of data.insight.statements.filter((s) => s.kind === "behaviour_fact" && !(s.sources.length === 1 && s.sources[0] === "observation_count"))) assert.ok(text.includes(statement.text), statement.text)
    assert.match(text, /Observed from your records/)
    assert.match(text, /Expressed in your own words \(optional\)/)
    assert.match(text, /suggestion, not a fact about you/)
    assert.match(text, /Informational only./)
    assert.ok(text.includes(data.insight.purpose))
  },

  "method panel: user_text_rules_v1 is active, the model is disabled, confidence and intensity are unavailable"() {
    const data = fixture("demo-example-text")
    assert.equal(data.insight.user_sentiment.model_version, "user_text_rules_v1")
    assert.equal(data.insight.user_sentiment.method, "rules_baseline")
    assert.equal(data.sentiment_model.enabled, false)
    assert.equal(data.insight.user_sentiment.confidence, null)
    assert.equal(data.insight.user_sentiment.sentiment_intensity, null)
    const markup = html({ data })
    const text = textOf(markup)
    assert.match(text, /How the reading was made/)
    // scoped to the method panel itself: the results panel above also prints "Confidence Not available", which would otherwise hide a fault in this panel
    const panel = textOf(markup.slice(markup.indexOf('id="demo-method-heading"')))
    assert.match(panel, /Active method user_text_rules_v1/)
    assert.match(panel, /Reading method Rules baseline/)
    assert.match(panel, /Transformer \/ trained model Disabled/)
    assert.match(panel, /Confidence Not available/)
    assert.match(panel, /Intensity Not available/)
    assert.doesNotMatch(panel, /Confidence 0|Intensity 0/)
    assert.ok(!text.includes(VALIDATED_MODEL_LABEL))
    assert.ok(!/\d+% confident/.test(text))
  },

  "the example sentence is read through the rules baseline (the response, not a hand-written result)"() {
    const data = fixture("demo-example-text")
    assert.equal(data.example_text, DEMO_EXAMPLE_TEXT)
    const sentiment = data.insight.user_sentiment
    assert.equal(sentiment.status, "analysed")
    assert.ok(sentiment.sentiment === "positive" || sentiment.sentiment === "negative" || sentiment.sentiment === "neutral" || sentiment.sentiment === "uncertain")
    assert.equal(sentiment.fallback_used, false)
    assert.equal(sentiment.intensity_available, false)
    const text = textOf(html({ data, draft: DEMO_EXAMPLE_TEXT, hasSubmittedText: true }))
    assert.ok(text.toLowerCase().includes(String(sentiment.sentiment)))
  },

  "quoted, third-person and unrelated sentences abstain in demo mode; hypothetical text is not shown as a current sentiment"() {
    for (const name of ["demo-quoted", "demo-third-person", "demo-unrelated"]) {
      const data = fixture(name)
      assert.equal(data.insight.user_sentiment.abstained, true, name)
      const text = textOf(html({ data, draft: "x", hasSubmittedText: true }))
      assert.ok(text.includes(name === "demo-unrelated" ? UNRELATED_MESSAGE : ABSTAIN_MESSAGE), name)
      assert.doesNotMatch(text, /overall tone reads as (positive|negative)/, name)
    }
    const hypothetical = fixture("demo-hypothetical")
    assert.equal(hypothetical.insight.user_sentiment.interpretation_state, "weak")
    assert.deepEqual(hypothetical.insight.user_sentiment.evidence, [])
    assert.doesNotMatch(textOf(html({ data: hypothetical, draft: "x", hasSubmittedText: true })), /overall tone reads as (positive|negative)/)
  },

  "records only (no sentence): the months are shown and no sentiment is inferred"() {
    const data = fixture("demo-records-only")
    const text = textOf(html({ data }))
    assert.ok(text.includes(NO_TEXT_MESSAGE))
    assert.match(text, /6 reported months/)
    assert.equal(data.insight.user_sentiment.sentiment, null)
  },

  "loading state: a status region, nothing invented"() {
    const markup = html({ loading: true })
    assert.match(markup, /aria-busy="true"/)
    assert.match(markup, /role="status"/)
    const text = textOf(markup)
    assert.match(text, /Loading the demonstration data/)
    assert.match(text, /Demonstration mode: fictional data/)
    assert.doesNotMatch(text, /₹|reported months/)
  },

  "backend unreachable: 'Service unavailable', the demo banner, and NO demo figures"() {
    const text = textOf(html({ error: new ApiUnreachableError(new Error("down")) }))
    assert.match(text, /Service unavailable/)
    assert.match(text, /could not be reached/)
    assert.match(text, /Try again/)
    assert.match(text, /Demonstration mode: fictional data/)
    assert.doesNotMatch(text, /₹|reported months|Monthly records/)
  },

  "demo switched off on the server: a clear instruction, not 'Service unavailable' and not demo data"() {
    const error = new ApiClientError({ type: "about:blank", title: "Demo mode is not enabled", status: 404, detail: "The demonstration data is switched off on this server." })
    const text = textOf(html({ error }))
    assert.match(text, /Demonstration mode is switched off on the server/)
    assert.match(text, /DEMO_MODE_ENABLED=true/)
    assert.doesNotMatch(text, /Service unavailable|₹|reported months/)
  },

  "any other API error uses the shared error state and shows no demo figures"() {
    const error = new ApiClientError({ type: "about:blank", title: "Internal server error", status: 500, detail: "boom" })
    const text = textOf(html({ error }))
    assert.match(text, /We couldn't complete this analysis/)
    assert.doesNotMatch(text, /₹|reported months/)
  },

  "accessibility and mobile: named regions, scrollable focusable table, stacked grids, real buttons and links"() {
    const data = fixture("demo-example-text")
    const markup = html({ data, draft: DEMO_EXAMPLE_TEXT, hasSubmittedText: true })
    assert.ok(occurrences(markup, "<h2") >= 4)
    for (const id of ["demo-months-heading", "demo-summary-heading", "demo-behaviour-heading", "demo-method-heading"]) {
      assert.match(markup, new RegExp(`aria-labelledby="${id}"`))
      assert.match(markup, new RegExp(`id="${id}"`))
    }
    assert.match(markup, /class="[^"]*overflow-x-auto[^"]*"[^>]*role="region"[^>]*aria-label="Monthly records table \(scrolls sideways on a narrow screen\)"[^>]*tabindex="0"/)
    assert.match(markup, /grid-cols-1[^"]*sm:grid-cols-2[^"]*lg:grid-cols-3/) // one column on a phone, more on wider screens
    assert.match(markup, /<a[^>]*href="\/financial-behaviour"[^>]*>Leave demonstration mode<\/a>/)
    assert.doesNotMatch(markup, /<button(?![^>]*type="(?:button|submit)")/) // no button without an explicit type
    for (const example of DEMO_EXAMPLES) assert.ok(markup.includes(`>${example.label}</button>`), example.label)
    assert.match(markup, /<textarea[^>]*id="[^"]+"/)
    assert.match(markup, /<label[^>]*for="[^"]+"/)
    assert.match(markup, /lg:grid-cols-12/) // the two-column layout collapses on a narrow screen
  },

  "the page: ?demo=true on a build that allows it shows the fictional demonstration and needs no profile"() {
    const markup = pageHtml("/financial-behaviour?demo=true", true, seeded("demo-example-text"))
    const text = textOf(markup)
    assert.match(text, /Financial Behaviour & Sentiment/)
    assert.match(text, /Demonstration mode: fictional data/)
    assert.match(text, /6 reported months/)
    assert.doesNotMatch(text, /Create Profile/)
  },

  "the page: without the query the normal page is unchanged (no profile selected), whatever the build allows"() {
    for (const allow of [true, false]) {
      const text = textOf(pageHtml("/financial-behaviour", allow))
      assert.match(text, /Financial Behaviour & Sentiment/)
      assert.match(text, /Create Profile/)
      assert.doesNotMatch(text, /Demonstration mode|fictional/)
    }
  },

  "the page: on a build that does not allow demo mode (production) ?demo=true shows the normal page and SAYS demonstration mode is not active"() {
    const text = textOf(pageHtml("/financial-behaviour?demo=true", false, seeded("demo-example-text")))
    assert.match(text, /Create Profile/)
    assert.match(text, /Demonstration mode is not active/)
    assert.match(text, /shown only by a development build/)
    assert.doesNotMatch(text, /Demonstration mode: fictional data|6 reported months|Monthly records \(fictional demo months\)/) // no demo data
  },

  "the page: only the exact query demo=true counts; any other value shows the normal page with a notice that names the right values"() {
    for (const query of ["?demo=1", "?demo=false", "?demo=TRUE", "?demo=", "?demo=true&demo=true"]) {
      const text = textOf(pageHtml(`/financial-behaviour${query}`, true, seeded("demo-example-text")))
      assert.match(text, /Create Profile/, query)
      assert.match(text, /Demonstration mode is not active/, query)
      assert.match(text, /Use \?demo=true \(one fictional person\) or \?demo=family \(a fictional family\)/, query)
      assert.doesNotMatch(text, /Demonstration mode: fictional data|Monthly records \(fictional demo months\)/, query)
    }
    const unrelated = textOf(pageHtml("/financial-behaviour?demos=true", true, seeded("demo-example-text"))) // a different parameter is simply not a demo request
    assert.match(unrelated, /Create Profile/)
    assert.doesNotMatch(unrelated, /Demonstration mode/)
  },

  "normal mode with a profile and no records still shows the empty state (demo data never substitutes for it)"() {
    const empty = JSON.parse(readFileSync(path.resolve(process.cwd(), "tests", "fixtures", "no-records-no-text.json"), "utf8")) as components["schemas"]["PersonalizedInsightResponse"]
    const markup = renderToStaticMarkup(
      <MemoryRouter initialEntries={["/financial-behaviour"]}>
        <QueryClientProvider client={new QueryClient()}>
          <CustomerProvider>
            <BehaviourSentimentView draft="" hasSubmittedText={false} stale={false} pending={false} loading={false} error={null} data={empty} onDraftChange={noop} onSubmit={noop} onClear={noop} onRetry={noop} />
          </CustomerProvider>
        </QueryClientProvider>
      </MemoryRouter>,
    )
    const text = textOf(markup)
    assert.match(text, /No monthly records yet/)
    assert.doesNotMatch(text, /Demonstration mode|fictional|₹/)
  },

  "the demo and example constants match the backend response, and every example is a plain fictional sentence"() {
    for (const name of ["demo-records-only", "demo-example-text", "demo-quoted", "demo-third-person", "demo-hypothetical", "demo-unrelated"]) {
      const data = fixture(name)
      assert.equal(data.example_text, DEMO_EXAMPLE_TEXT, name)
      assert.equal(data.demo, true, name)
      assert.equal(data.data_source, "demo_fixture", name)
      assert.equal(data.insight.customer_id, 0, name)
      assert.equal(data.insight.user_sentiment.sentiment_intensity, null, name)
      assert.equal(data.insight.user_sentiment.confidence, null, name)
      assert.equal(data.sentiment_model.enabled, false, name)
      assert.equal(data.sentiment_model.state, "disabled", name)
      assert.deepEqual(data.months.map((m) => m.period), ["2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"], name)
    }
    assert.ok(DEMO_EXAMPLES.some((e) => e.text === DEMO_EXAMPLE_TEXT))
    for (const example of DEMO_EXAMPLES) assert.ok(example.text.length > 10 && example.text.length < 200 && !/@|https?:\/\/|\d{6,}/.test(example.text))
  },

  "the demo source never uses browser storage, the console, cookies or a URL for text"() {
    for (const file of [
      "src/components/financial-health/demo-financial-behaviour.tsx",
      "src/components/financial-health/demo-financial-behaviour-card.tsx",
      "src/hooks/use-demo-financial-behaviour.ts",
      "src/lib/demo-mode.ts",
      "src/components/charts/monthly-flows-chart.tsx",
    ]) {
      const source = readFileSync(path.resolve(process.cwd(), file), "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1")
      assert.doesNotMatch(source, /localStorage|sessionStorage|indexedDB|document\.cookie|console\.|navigator\.sendBeacon|window\.location|history\.(push|replace)State/, file)
    }
  },
}

