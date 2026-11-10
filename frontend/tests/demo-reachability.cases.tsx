/**
 * Component cases for how a person REACHES the demonstration on the Financial Behaviour page (the 2026-11-02 diagnosis): a demo parameter that does not start a demonstration is announced instead of
 * silently showing the normal page, a profile with no records is pointed at the fictional examples on development builds only, a 404 from the demo route is explained as the flag or an older backend
 * (never "not created yet"), and the sidebar link keeps a demonstration. Rendered to static HTML with react-dom/server through Vite's SSR loader (`npm test`); no demo data is ever shown for a real profile.
 */
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import path from "node:path"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderToStaticMarkup } from "react-dom/server"
import { MemoryRouter } from "react-router"

import { DemoFamilyView } from "@/components/financial-health/demo-family-behaviour"
import { DemoFinancialBehaviourView } from "@/components/financial-health/demo-financial-behaviour"
import { DemoRequestNotice } from "@/components/financial-health/demo-request-notice"
import { FinancialBehaviourRealView, type FinancialBehaviourRealViewProps } from "@/components/financial-health/financial-behaviour-real"
import { ApiClientError, ApiUnreachableError } from "@/lib/api-client"
import { DEMO_EXAMPLES, DEMO_EXAMPLE_TEXT } from "@/lib/demo-mode"
import { FinancialBehaviourContent } from "@/pages/financial-behaviour-page"
import type { components } from "@/types/api"

type Insight = components["schemas"]["PersonalizedInsightResponse"]
type Family = components["schemas"]["DemoFamilyFinancialBehaviourResponse"]

const fixture = (...parts: string[]): unknown => JSON.parse(readFileSync(path.resolve(process.cwd(), "tests", "fixtures", ...parts), "utf8"))
const EMPTY = fixture("no-records-no-text.json") as Insight
const FAMILY = fixture("demo", "family-example-text.json") as Family
const noop = () => {}

function textOf(markup: string): string {
  return markup.replace(/<[^>]*>/g, " ").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#x27;|&#39;/g, "'").replace(/\s+/g, " ").trim()
}
const realProps = (over: Partial<FinancialBehaviourRealViewProps> = {}): FinancialBehaviourRealViewProps => ({
  insight: EMPTY, insightLoading: false, insightError: null, onRetryInsight: noop, records: [], recordsLoading: false, recordsError: null, onRetryRecords: noop,
  analysisLoading: false, analysisError: null, health: undefined, onRetryAnalysis: noop, householdName: null, note: <p>NOTE-SLOT</p>, ...over,
})
const real = (over: Partial<FinancialBehaviourRealViewProps> = {}): string => renderToStaticMarkup(<MemoryRouter><FinancialBehaviourRealView {...realProps(over)} /></MemoryRouter>)
const notFound = new ApiClientError({ type: "about:blank", title: "Not Found", status: 404, detail: "Not Found" })
const switchedOff = new ApiClientError({ type: "about:blank", title: "Demo mode is not enabled", status: 404, detail: "off" })
const familyHtml = (error: unknown): string =>
  renderToStaticMarkup(<MemoryRouter><DemoFamilyView data={undefined} loading={false} error={error} draft="" hasSubmittedText={false} stale={false} pending={false} examples={DEMO_EXAMPLES} onUseExample={noop} onDraftChange={noop} onSubmit={noop} onClear={noop} onRetry={noop} /></MemoryRouter>)
const individualHtml = (error: unknown): string =>
  renderToStaticMarkup(<MemoryRouter><DemoFinancialBehaviourView data={undefined} loading={false} error={error} draft="" hasSubmittedText={false} stale={false} pending={false} examples={DEMO_EXAMPLES} onUseExample={noop} onDraftChange={noop} onSubmit={noop} onClear={noop} onRetry={noop} /></MemoryRouter>)

export const cases: Record<string, () => void | Promise<void>> = {
  "a profile with no records is pointed at the fictional examples (links, never data) on a build that allows demonstration mode"() {
    const markup = real({ demoHint: true })
    const text = textOf(markup)
    assert.match(text, /Developer note: fictional examples are available/)
    assert.match(markup, /<a[^>]*href="\/financial-behaviour\?demo=family"[^>]*>A fictional family \(\?demo=family\)<\/a>/)
    assert.match(markup, /<a[^>]*href="\/financial-behaviour\?demo=true"[^>]*>One fictional person \(\?demo=true\)<\/a>/)
    assert.match(text, /DEMO_MODE_ENABLED=true and be restarted/)
    assert.match(text, /No monthly records yet/) // the normal empty state is still there
    assert.doesNotMatch(text, /Demo data — fictional family example|Primary member|₹/)
  },

  "the developer pointer is absent on a build that does not allow demonstration mode, and when the profile has records"() {
    assert.doesNotMatch(textOf(real({ demoHint: false })), /Developer note|fictional/)
    assert.doesNotMatch(textOf(real()), /Developer note/) // the default is off
    const withRecords = textOf(real({ demoHint: true, insight: FAMILY.members[0].insight }))
    assert.doesNotMatch(withRecords, /Developer note/)
    assert.match(withRecords, /Reported months 6/)
    assert.doesNotMatch(textOf(real({ demoHint: true, insight: undefined, insightLoading: true })), /Developer note/) // not while loading
    assert.doesNotMatch(textOf(real({ demoHint: true, insight: undefined, insightError: new ApiUnreachableError(new Error("down")) })), /Developer note/) // not on an outage
  },

  "a demo parameter that did not start a demonstration is announced above the REAL page, which is unchanged beneath it"() {
    for (const problem of ["not_allowed", "unknown_value"] as const) {
      const markup = renderToStaticMarkup(
        <MemoryRouter initialEntries={["/financial-behaviour?demo=family"]}>
          <QueryClientProvider client={new QueryClient()}>
            <FinancialBehaviourContent profileId={7} demoProblem={problem} />
          </QueryClientProvider>
        </MemoryRouter>,
      )
      const text = textOf(markup)
      assert.match(markup, /role="status"[^>]*aria-label="Demonstration mode is not active"/, problem)
      assert.match(text, /Demonstration mode is not active/, problem)
      assert.match(text, problem === "not_allowed" ? /shown only by a development build/ : /Use \?demo=true \(one fictional person\) or \?demo=family \(a fictional family\)/, problem)
      assert.match(markup, /<a[^>]*href="\/financial-behaviour"[^>]*>Go to the normal page<\/a>/, problem)
      assert.match(text, /Financial behaviour overview/, problem) // the real page is still there
      assert.doesNotMatch(text, /Demo data — fictional family example|Primary member|Demonstration mode: fictional data/, problem)
      assert.equal((markup.match(/<h1\b/g) ?? []).length, 1)
    }
    assert.doesNotMatch(textOf(renderToStaticMarkup(<MemoryRouter><QueryClientProvider client={new QueryClient()}><FinancialBehaviourContent profileId={7} /></QueryClientProvider></MemoryRouter>)), /Demonstration mode is not active/) // no parameter, no notice
    const standalone = textOf(renderToStaticMarkup(<MemoryRouter><DemoRequestNotice problem="not_allowed" /></MemoryRouter>))
    assert.doesNotMatch(standalone, /₹|reported months/)
  },

  "a 404 from the demonstration route is explained as the flag or an older backend, for both demonstrations, never as 'not created yet'"() {
    for (const render of [familyHtml, individualHtml]) {
      for (const error of [notFound, switchedOff]) {
        const text = textOf(render(error))
        assert.match(text, /Demonstration mode is switched off on the server/)
        assert.match(text, /The backend answered 404 for the demonstration data/)
        assert.match(text, /DEMO_MODE_ENABLED=true/)
        assert.match(text, /restart the backend/)
        assert.doesNotMatch(text, /may not have been created yet|Information not found|Service unavailable|₹|Primary member/)
      }
    }
  },

  "an outage and a server error are still different from a switched-off demonstration"() {
    for (const render of [familyHtml, individualHtml]) {
      const down = textOf(render(new ApiUnreachableError(new Error("down"))))
      assert.match(down, /Service unavailable/)
      assert.doesNotMatch(down, /switched off on the server|DEMO_MODE_ENABLED/)
      const broken = textOf(render(new ApiClientError({ type: "about:blank", title: "Internal server error", status: 500, detail: "x" })))
      assert.match(broken, /We couldn't complete this analysis/)
      assert.doesNotMatch(broken, /switched off on the server|Service unavailable/)
    }
  },

  "the sidebar link and the sign-in keep the demonstration (source rules)"() {
    const sidebar = readFileSync(path.resolve(process.cwd(), "src/components/shell/app-sidebar.tsx"), "utf8")
    assert.match(sidebar, /behaviourLinkTarget\(location\.pathname, location\.search, DEMO_MODE_ALLOWED\)/)
    const login = readFileSync(path.resolve(process.cwd(), "src/components/login-form.tsx"), "utf8")
    assert.doesNotMatch(login.replace(/\/\*[\s\S]*?\*\//g, ""), /navigate\("\/profile\?household=open"/)
    assert.ok(DEMO_EXAMPLE_TEXT.length > 10)
  },
}
