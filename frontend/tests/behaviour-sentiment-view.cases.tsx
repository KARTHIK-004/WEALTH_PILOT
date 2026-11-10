/**
 * Component cases for the "Financial behaviour & sentiment" section, rendered to static HTML with react-dom/server (already a dependency) through Vite's SSR loader, and executed by
 * tests/component.test.mjs under Node's built-in test runner (`npm test`). No browser, no DOM library and no new dependency.
 *
 * Every response rendered here is a REAL backend response captured by `scripts/export_insight_fixtures.py` from the actual route (synthetic figures, invented sentences), never a
 * hand-written mock; `tests/backend/api/test_insight_fixtures.py` fails if a fixture drifts from the backend. Assertions compare what is shown with the values IN the response, so a
 * renamed field, an invented label, a swallowed `null` or a result shown after a failure makes a case fail.
 *
 * Static rendering covers markup, states, labels and ARIA wiring; typing, focus movement and clicking are covered by the pure transition tests in tests/user-text-input.test.ts
 * (`submitDraft`, `clearAll`, `resultsAreStale`) because no DOM is available. That boundary is deliberate and is stated in the report.
 */
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import path from "node:path"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderToStaticMarkup } from "react-dom/server"
import { MemoryRouter } from "react-router"

import { BehaviourSentimentCard } from "@/components/financial-health/behaviour-sentiment"
import { BehaviourSummaryCard, BehaviourSummaryView, type BehaviourSummaryViewProps } from "@/components/financial-health/behaviour-summary-card"
import { BehaviourSentimentView, type BehaviourSentimentViewProps } from "@/components/financial-health/behaviour-sentiment-view"
import { CommitmentsView } from "@/components/financial-health/individual-finances"
import { SpendingFromRecordsView } from "@/components/financial-health/spending-from-records"
import { ApiClientError, ApiUnreachableError } from "@/lib/api-client"
import { selectInsightRows, selectSpendingRows } from "@/lib/behaviour-insights"
import { FinancialBehaviourContent, FinancialBehaviourPage } from "@/pages/financial-behaviour-page"
import { CustomerProvider } from "@/providers/customer-context"
import {
  ABSTAIN_MESSAGE,
  FALLBACK_MESSAGE,
  INFORMATIONAL_NOTICE,
  INTERPRETATION_NOTICE,
  MAX_USER_TEXT_CHARS,
  MODEL_UNAVAILABLE_LABEL,
  MODEL_UNAVAILABLE_MESSAGE,
  NO_TEXT_MESSAGE,
  RULES_FALLBACK_LABEL,
  VALIDATED_MODEL_LABEL,
  PREFERENCE_NOTICE,
  UNRELATED_MESSAGE,
  UNSUPPORTED_LANGUAGE_MESSAGE,
  preferenceLabel,
  topicLabel,
} from "@/lib/user-text-input"
import type { components } from "@/types/api"

type Insight = components["schemas"]["PersonalizedInsightResponse"]

function fixture(name: string): Insight {
  return JSON.parse(readFileSync(path.resolve(process.cwd(), "tests", "fixtures", `${name}.json`), "utf8")) as Insight
}

const noop = () => {}
function propsFor(over: Partial<BehaviourSentimentViewProps> = {}): BehaviourSentimentViewProps {
  return { draft: "", hasSubmittedText: false, stale: false, pending: false, loading: false, error: null, data: undefined, onDraftChange: noop, onSubmit: noop, onClear: noop, onRetry: noop, ...over }
}
const html = (over: Partial<BehaviourSentimentViewProps> = {}): string =>
  renderToStaticMarkup(
    <MemoryRouter>
      <BehaviourSentimentView {...propsFor(over)} />
    </MemoryRouter>,
  )

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
/** True only for a real `disabled` attribute on the tag (the Tailwind class `disabled:opacity-50` is on every button and must not count). */
const isDisabled = (tag: string): boolean => /(?:^|\s)disabled(?:=""|(?=[\s>]))/.test(tag.slice(0, tag.indexOf(">")).replace(/class="[^"]*"/, "")) || /aria-disabled="true"/.test(tag)
const buttonTag = (markup: string, label: string): string => {
  const match = new RegExp(`<button[^>]*>(?:(?!</button>).)*${label}(?:(?!</button>).)*</button>`, "s").exec(markup)
  assert.ok(match, `button "${label}" not found`)
  return match[0]
}


const summaryProps = (over: Partial<BehaviourSummaryViewProps> = {}): BehaviourSummaryViewProps => ({ data: undefined, loading: false, error: null, onRetry: noop, ...over })
const summaryHtml = (over: Partial<BehaviourSummaryViewProps> = {}): string =>
  renderToStaticMarkup(
    <MemoryRouter>
      <BehaviourSummaryView {...summaryProps(over)} />
    </MemoryRouter>,
  )
const seededClient = (profileId: number, name: string): QueryClient => {
  const client = new QueryClient()
  client.setQueryData(["personalized-insight", profileId, null], fixture(name))
  return client
}

export const cases: Record<string, () => void | Promise<void>> = {
  "initial state: records only, an empty text area, a counter, the privacy note, and nothing fabricated"() {
    const data = fixture("records-only")
    const markup = html({ data })
    const text = textOf(markup)
    assert.match(text, /Describe your financial concerns, goals or feelings \(optional\)/)
    assert.match(text, new RegExp(`0 / ${MAX_USER_TEXT_CHARS} characters \\(${MAX_USER_TEXT_CHARS} left\\)`))
    assert.match(text, /not used to change your stored risk assessment/)
    assert.match(text, /not saved on the server or in your browser's storage/)
    assert.equal(isDisabled(buttonTag(markup, "Analyse")), false)
    assert.equal(isDisabled(buttonTag(markup, "Clear")), true) // nothing to clear yet
    assert.match(text, /No reading shown/)
    assert.match(text, /You have not written anything\. No sentiment is inferred\./)
    assert.ok(text.includes(NO_TEXT_MESSAGE))
    assert.ok(text.includes(INFORMATIONAL_NOTICE), "the informational-only notice is shown with every result")
    assert.doesNotMatch(text, /Sentiment:/) // a missing text is never rendered as a tone, least of all neutral
    assert.match(text, new RegExp(data.user_sentiment.unavailable_reason ?? "NO-REASON")) // the backend's own reason is kept in the technical details
  },

  "the intro states the difference between what is observed and what is expressed, and the page makes no stronger claim"() {
    const text = textOf(html({ data: fixture("records-only") }))
    assert.match(text, /Observed from your records Changes and ratios in the months you reported, worked out by the system\. These describe your numbers\./)
    assert.match(text, /Expressed in your own words \(optional\) An automatic suggestion about how text you choose to write reads\. It is a suggestion, not a fact about you\./)
  },

  "the text box is a text area with a visible label, room for several lines, and no hard length cap that would hide an over-long paste"() {
    const markup = html({ data: fixture("records-only") })
    assert.match(markup, /<textarea[^>]*id="insight-text"/)
    assert.doesNotMatch(markup, /<input[^>]*id="insight-text"/)
    assert.match(markup, /<textarea[^>]*rows="5"/)
    assert.doesNotMatch(markup, /<textarea[^>]*maxlength/i) // the counter and the validation message report an over-long text; the browser must not silently cut it
    assert.match(markup, /<textarea[^>]*spellCheck="false"/i)
    assert.match(markup, /<textarea[^>]*autoComplete="off"/i)
    assert.match(textOf(markup), /Press Analyse, or Ctrl\+Enter, to read it\./)
  },

  "observed facts are the backend's findings: sentence, source fields, category and direction, each shown once"() {
    const data = fixture("records-only")
    const markup = html({ data })
    const text = textOf(markup)
    const rows = selectInsightRows(data.behaviour.findings)
    assert.ok(rows.length >= 3)
    for (const row of rows) {
      assert.equal(occurrences(text, row.statement), 1, `statement shown exactly once: ${row.statement}`)
      assert.match(text, new RegExp(`Based on: ${row.sources.map((s) => s.replace(/[.]/g, "\\.")).join(", ")}`))
      assert.match(text, new RegExp(row.categoryLabel))
      if (row.directionLabel) assert.match(text, new RegExp(row.directionLabel))
    }
    assert.match(markup, /aria-label="Observed from your records"/)
    assert.match(text, /2 reported months latest 2026-02/)
    assert.equal(occurrences(text, "2 months have been reported."), 0, "the bare month count is the badge, not a repeated row")
  },

  "every shown insight sentence is a sentence the backend returned as a behaviour fact, in the backend's order"() {
    for (const name of ["records-only", "conflict", "conservative-growth", "no-assessment"]) {
      const data = fixture(name)
      const shown = selectInsightRows(data.behaviour.findings).map((r) => r.statement)
      const facts = data.statements.filter((s) => s.kind === "behaviour_fact" && !(s.sources.length === 1 && s.sources[0] === "observation_count")).map((s) => s.text)
      assert.deepEqual(shown, facts, name)
    }
  },

  "unavailable debt/EMI and goal progress stay unavailable with the backend's reason, and are not shown as zero"() {
    const data = fixture("records-only")
    const text = textOf(html({ data }))
    const notShown = data.behaviour.findings.filter((f) => f.status !== "observed")
    assert.ok(notShown.some((f) => f.code === "debt_burden") && notShown.some((f) => f.code === "goal_progress"))
    assert.match(text, /What is not shown, and why/)
    for (const finding of notShown) assert.match(text, new RegExp(finding.statement.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").slice(0, 60)))
    assert.doesNotMatch(text, /Debt[^.]*: ?0\b|₹ ?0\b/)
  },

  "a conflict is reported next to the reading, and the stored assessment is stated to stay in force"() {
    const data = fixture("conflict")
    const text = textOf(html({ data, draft: "I'm worried about losing my savings, and I want to invest more safely.", stale: false }))
    assert.match(text, /Your words and your risk assessment differ/)
    assert.match(text, new RegExp(data.conflicts[0].detail.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")))
    assert.match(text, /Your existing risk assessment stays the authority\. Your words do not change it\./)
    const risk = data.statements.find((s) => s.kind === "risk_assessment")
    assert.ok(risk)
    assert.match(text, new RegExp(risk.text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")))
    assert.match(text, /Aggressive/)
    assert.match(text, /Sentiment: Negative/)
    assert.match(text, /Concerned/)
    assert.match(text, /not a measure of how much risk you can take/)
    for (const topic of data.user_sentiment.topics) assert.match(text, new RegExp(topicLabel(topic)))
    for (const item of data.user_sentiment.evidence) assert.match(text, new RegExp(item.phrase.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")))
    for (const preference of data.user_sentiment.preferences) {
      assert.match(text, new RegExp(preferenceLabel(preference.code)))
      assert.match(text, new RegExp(preference.evidence.phrase.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")))
    }
    assert.match(text, /Unconfirmed/)
    assert.match(text, new RegExp(data.preference_confirmation.slice(0, 40)))
    assert.doesNotMatch(text, /your risk (tolerance|profile) is (now )?(conservative|moderate|balanced)/i) // the UI never restates a changed profile
  },

  "the stored risk assessment has its own panel, apart from the reading of the words, and it is never presented as updated by them"() {
    const markup = html({ data: fixture("conflict") })
    const risk = markup.indexOf('id="risk-heading"')
    const reading = markup.indexOf('id="reading-heading"')
    const input = markup.indexOf('id="input-heading"')
    assert.ok(risk > 0 && reading > 0 && input > 0)
    assert.ok(risk < input && input < reading, "assessment, then the text box, then the reading: three separate regions")
    const riskRegion = markup.slice(risk, input)
    assert.match(textOf(riskRegion), /Kept separate from the reading of your words\. Your words never change it\./)
    assert.doesNotMatch(textOf(markup), /updated|recalculated|adjusted your risk|changed your risk (profile|tolerance|category)/i)
  },

  "no stored assessment is stated explicitly in the assessment panel while the rest is shown"() {
    const data = fixture("no-assessment")
    assert.equal(data.risk_profile, null)
    const text = textOf(html({ data }))
    assert.match(text, /No risk assessment is on file for this profile yet\. Nothing is assumed in its place\./)
    assert.match(text, /What your records show/)
  },

  "confidence, method and honesty: no invented score, and the rules baseline is not presented as a trained or validated model"() {
    const data = fixture("conflict")
    const text = textOf(html({ data }))
    assert.equal(data.user_sentiment.confidence, null)
    assert.match(text, /Confidence Not available . These fixed rules are not calibrated, so no confidence level is claimed\./)
    assert.match(text, /Method used Rules baseline . Rules baseline \(a small fixed set of rules, not a trained model\) \(user_text_rules_v1\)/)
    assert.match(text, /Validation status Unvalidated baseline: no accuracy has been measured for these rules/)
    assert.match(text, /A simple automatic reading, not a validated model/)
    assert.match(text, /not a trained or validated model, it reports no confidence level, and it is a suggestion, not a fact about you/)
    assert.match(text, new RegExp(data.user_sentiment.method))
    assert.match(text, new RegExp(data.user_sentiment.validation_status))
    assert.match(text, new RegExp(data.model_version.replace(/[|]/g, "\\|")))
    assert.match(text, new RegExp(data.data_source.replace(/[+]/g, "\\+")))
    assert.doesNotMatch(text, /\b\d{1,3}(\.\d+)? ?% (confident|confidence|accurate)/i)
    assert.doesNotMatch(text, /\baccuracy of\b|\bprecision of\b|\brecall of\b|\bvalidated by\b|\btrained on\b/i) // no performance or provenance claim about the rules
    for (const limit of data.user_sentiment.limitations) assert.ok(text.includes(limit.slice(0, 50)), limit) // each backend limitation is shown (compared as plain text)
  },

  "uncertain is shown as Uncertain, visually marked as inconclusive, weak, and never turned into neutral"() {
    const data = fixture("negated")
    assert.equal(data.user_sentiment.sentiment, "uncertain")
    const markup = html({ data })
    const text = textOf(markup)
    assert.match(text, /Sentiment: Uncertain/)
    assert.match(text, /This is not the same as neutral\./)
    assert.match(text, /Not a confirmed reading\./)
    const headline = /<div data-reading="inconclusive" class="([^"]*)"/.exec(markup)
    assert.ok(headline, "the reading headline is marked inconclusive")
    assert.match(headline[1], /border-dashed/)
    assert.match(headline[1], /text-muted-foreground/)
    assert.doesNotMatch(headline[1], /bg-muted\/40/) // not styled like a found reading
    assert.doesNotMatch(text, /Sentiment: Neutral/)
    assert.match(markup, /data-state="weak"/)
    assert.match(text, /Weak interpretation/)
    assert.match(text, /Possible preferences None inferred\./) // no preference was stated, so none is invented
    assert.match(text, /Emotional tone Unknown/)
    assert.match(text, /not read as its opposite/) // the backend's own note about the negated expression
  },

  "a reading that found a tone is marked as found, not as inconclusive"() {
    for (const name of ["conflict", "no-records-with-text", "conservative-growth"]) {
      const markup = html({ data: fixture(name) })
      const headline = /<div data-reading="found" class="([^"]*)"/.exec(markup)
      assert.ok(headline, name)
      assert.match(headline[1], /bg-muted\/40/, name)
      assert.doesNotMatch(headline[1], /border-dashed/, name)
      assert.doesNotMatch(markup, /data-reading="inconclusive"/, name)
      assert.doesNotMatch(textOf(markup), /Not a confirmed reading\./, name)
    }
  },

  "preferences are shown as unconfirmed suggestions with a dashed marker, never as settings"() {
    const markup = html({ data: fixture("conflict") })
    assert.match(markup, /<[^>]*border-dashed[^>]*>Unconfirmed</)
    assert.doesNotMatch(textOf(markup), /Your (risk )?(preference|setting)s? (is|are|has been) (now )?(set|saved|applied)/i)
  },

  "text in another language is declined by the backend: the page states it was not interpreted and shows no sentiment, tone, topic or preference"() {
    const data = fixture("mixed-language-cue")
    const s = data.user_sentiment
    assert.deepEqual([s.sentiment, s.abstained, s.abstain_reason, s.interpretation_state], ["insufficient_evidence", true, "unsupported_language", "abstained"])
    const markup = html({ data })
    const text = textOf(markup)
    assert.ok(text.includes(UNSUPPORTED_LANGUAGE_MESSAGE))
    assert.match(markup, /data-state="abstained"/)
    assert.match(text, /Not interpreted/)
    assert.match(text, /Sentiment: Not enough evidence/)
    assert.match(text, /Possible preferences None inferred\./)
    assert.doesNotMatch(text, /Sentiment: (Positive|Negative|Mixed|Neutral)|Unconfirmed/)
    assert.doesNotMatch(text, /language (was )?detected|detected language|translated/i) // no language-detection or translation claim
    assert.match(text, /English only/) // the backend's own limitation is shown
  },

  "an unrelated text says it has no personal-finance context, shows no sentiment, and never offers a preference"() {
    const data = fixture("unrelated")
    assert.deepEqual([data.user_sentiment.financial_relevance, data.user_sentiment.abstain_reason], ["unrelated", "unrelated_text"])
    const markup = html({ data })
    const text = textOf(markup)
    assert.ok(text.includes(UNRELATED_MESSAGE))
    assert.match(text, /Financial relevance Unrelated: the text is about something other than personal finance/)
    assert.match(text, /Emotional tone Unknown/)
    assert.doesNotMatch(text, /Sentiment: (Positive|Negative|Mixed|Neutral|Uncertain)|Unconfirmed|Evidence: the words/)
    assert.match(markup, /data-reading="inconclusive"/)
  },

  "an ambiguous or very short text is declined with the general message, and is not shown as neutral"() {
    for (const name of ["ambiguous", "too-short"]) {
      const data = fixture(name)
      assert.equal(data.user_sentiment.abstained, true, name)
      const text = textOf(html({ data }))
      assert.ok(text.includes(ABSTAIN_MESSAGE), name)
      assert.match(text, /Sentiment: Not enough evidence/, name)
      assert.match(text, /Financial relevance Ambiguous/, name)
      assert.doesNotMatch(text, /Sentiment: Neutral|Unconfirmed/, name)
      assert.equal(data.status, "behaviour_only", name) // an abstained reading does not make the insight complete
    }
  },

  "a weak interpretation is labelled weak and a valid one is labelled valid; neither claims the method is validated"() {
    const weak = html({ data: fixture("weak-neutral") })
    assert.match(weak, /data-state="weak"/)
    assert.match(textOf(weak), /Weak interpretation The text gave little explicit evidence/)
    const valid = html({ data: fixture("conflict") })
    assert.match(valid, /data-state="valid"/)
    assert.match(textOf(valid), /Valid interpretation The text gave enough explicit evidence for this reading\. That does not make the method validated\./)
    assert.doesNotMatch(valid, /data-state="(weak|abstained)"/)
  },

  "a fallback to the rules baseline is announced word for word, and only when the backend says it happened"() {
    const data = fixture("fallback-rules")
    assert.equal(data.user_sentiment.fallback_used, true)
    const markup = html({ data })
    assert.ok(textOf(markup).includes(FALLBACK_MESSAGE))
    assert.match(markup, /data-fallback="rules"/)
    assert.match(textOf(markup), /Sentiment: Negative/) // the rules baseline still answered
    assert.doesNotMatch(html({ data: fixture("conflict") }), /data-fallback/)
    assert.ok(!textOf(html({ data: fixture("conflict") })).includes(FALLBACK_MESSAGE))
  },

  "a mixed reading with a growth preference against a Conservative assessment shows both readings, an unconfirmed preference, and the stored assessment as authoritative"() {
    const data = fixture("mixed-growth-conflict")
    assert.deepEqual([data.user_sentiment.sentiment, data.user_sentiment.emotional_tone], ["mixed", "concerned"])
    const markup = html({ data })
    const text = textOf(markup)
    assert.match(text, /Sentiment: Mixed/)
    assert.match(text, /Emotional tone Concerned/)
    assert.match(text, /Seeking growth/)
    assert.match(text, /Unconfirmed/)
    assert.ok(text.includes(PREFERENCE_NOTICE))
    const conflict = data.conflicts[0]
    assert.deepEqual([conflict.inferred_preference, conflict.stored_category, conflict.preference_status, conflict.action], ["growth_seeking", "Conservative", "unconfirmed", "confirm_or_correct"])
    assert.match(markup, /data-conflict="true"/)
    assert.match(text, /Suggested by your words Seeking growth \(unconfirmed\)/)
    assert.match(text, /Stored assessment Conservative \(remains authoritative; source: stored risk assessment of the latest analysis\)/)
    assert.match(text, /What you can do Confirm or correct this interpretation\. Until then it changes nothing\./)
    assert.match(text, /Your existing risk assessment stays the authority\. Your words do not change it\./)
    assert.match(text, /Remains authoritative/) // also in the risk panel
    assert.match(text, /If this is not what you meant, change your text and press Analyse again\./)
    assert.match(text, new RegExp(data.preference_confirmation.slice(0, 40)))
  },

  "a preference that agrees with the stored assessment still says it is unconfirmed, and no conflict is shown"() {
    const data = fixture("capital-preservation")
    assert.deepEqual(data.conflicts, [])
    const markup = html({ data })
    const text = textOf(markup)
    assert.match(text, /Keeping capital safe/)
    assert.match(text, /Unconfirmed/)
    assert.ok(text.includes(PREFERENCE_NOTICE))
    assert.doesNotMatch(markup, /data-conflict/)
    assert.match(text, /Sentiment: Neutral/) // a stated want with no feeling word: neutral, found
  },

  "the informational-only notice, the method, the validation status and the limitations are shown with every analysed reading, and confidence is hidden when null"() {
    for (const name of ["conflict", "negated", "unrelated", "fallback-rules", "weak-neutral", "capital-preservation"]) {
      const data = fixture(name)
      const text = textOf(html({ data }))
      assert.ok(text.includes(INFORMATIONAL_NOTICE), name)
      assert.match(text, /Method used Rules baseline/, name)
      assert.match(text, /Validation status Unvalidated baseline/, name)
      assert.match(text, /Limits of this reading|rules baseline, not validated/, name)
      assert.equal(data.user_sentiment.confidence, null, name)
      assert.match(text, /Confidence Not available/, name)
      assert.doesNotMatch(text, /\d+(\.\d+)? \(as returned by the analysis\)|\d+ ?% (confident|confidence)/, name) // no number is invented
    }
  },

  "emotional tone stays apart from risk tolerance: a nervous reading never offers a conservative preference"() {
    const data = fixture("fallback-rules") // "I am nervous about the market."
    assert.equal(data.user_sentiment.emotional_tone, "concerned")
    assert.deepEqual(data.user_sentiment.preferences, [])
    const text = textOf(html({ data }))
    assert.match(text, /Emotional tone Concerned \(from explicit words in your text; this is not a measure of how much risk you can take\)/)
    assert.doesNotMatch(text, /Keeping capital safe|Unconfirmed/)
  },

  "the stored assessment panel states that it remains authoritative, and that a reading of the words ranks below it"() {
    const text = textOf(html({ data: fixture("conflict") }))
    assert.match(text, /Aggressive Remains authoritative/)
    assert.match(text, /Source: stored risk assessment of the latest analysis\. A reading of your words is informational only and ranks below this assessment/)
  },

  "no records and no text: every section says so, points to where records are added, and nothing is shown as zero or as a default"() {
    const data = fixture("nothing-available")
    assert.equal(data.status, "unavailable")
    const markup = html({ data })
    const text = textOf(markup)
    assert.match(text, /No monthly records yet/)
    assert.match(text, /No risk assessment is on file for this profile yet\. Nothing is assumed in its place\./)
    assert.match(text, /No reading shown/)
    assert.match(text, /0 reported months/)
    assert.match(markup, /<a[^>]*href="\/profile"[^>]*>Customer Profile<\/a>/)
    assert.doesNotMatch(text, /Based on:/)
  },

  "one month of records is described without inventing a change"() {
    const data = structuredClone(fixture("records-only"))
    data.behaviour.observation_count = 1
    data.behaviour.findings = data.behaviour.findings.filter((f) => f.status !== "observed" || f.sources[0] === "observation_count")
    const text = textOf(html({ data }))
    assert.match(text, /1 reported month\b/)
    assert.doesNotMatch(text, /1 reported months/)
    assert.match(text, /Nothing to describe yet/)
    assert.match(text, /do not give enough to describe a change or a ratio/)
  },

  "no records but a stored assessment and a text: only the words and the assessment are shown"() {
    const data = fixture("no-records-with-text")
    assert.equal(data.status, "profile_only")
    const text = textOf(html({ data }))
    assert.match(text, /No monthly records yet/)
    assert.match(text, /Sentiment: Positive/)
    assert.match(text, /Conservative/)
  },

  "a growth wish against a Conservative assessment is reported as a conflict, not applied"() {
    const data = fixture("conservative-growth")
    const text = textOf(html({ data }))
    assert.deepEqual(data.conflicts.map((c) => c.code), ["growth_seeking"])
    assert.match(text, /Your words and your risk assessment differ/)
    assert.match(text, /Seeking growth/)
    assert.match(text, /Conservative/)
    assert.match(text, /Your existing risk assessment stays the authority/)
  },

  "loading shows a status region with skeletons, no numbers, and marks the results region busy"() {
    const markup = html({ loading: true, pending: true })
    const text = textOf(markup)
    assert.match(markup, /role="status"/)
    assert.match(text, /Reading your information…/)
    assert.match(markup, /aria-busy="true"/)
    assert.doesNotMatch(text, /What your records show|Sentiment:|\d+ reported months?/)
    assert.equal(isDisabled(buttonTag(markup, "Analysing…")), true) // no duplicate submission while a request is pending
  },

  "an error replaces every result: stale data from an earlier success is NOT shown next to a failure"() {
    const earlier = fixture("conflict")
    const failure = new ApiClientError({ type: "about:blank", title: "Invalid request", status: 400, detail: "The text cannot be analysed: text is longer than 1000 characters." })
    const text = textOf(html({ data: earlier, error: failure, stale: true }))
    assert.match(text, /We couldn't complete this request/)
    assert.match(text, /Some of the information could not be accepted\. Please check it and try again\./)
    assert.match(text, /Try again/)
    assert.match(text, /Your records and your risk assessment are not shown because the request failed\./)
    assert.doesNotMatch(text, /What your records show|Sentiment:|Your words and your risk assessment differ|Your risk assessment on file/)
    assert.doesNotMatch(text, /These results are not for the text in the box/)
    assert.doesNotMatch(text, new RegExp("worried about losing")) // none of the earlier reading's wording survives
  },

  "an unreachable service and a server error are described plainly, without exposing internals"() {
    const unreachable = textOf(html({ error: new ApiUnreachableError(new Error("socket hang up secret-host")) }))
    assert.match(unreachable, /Service unavailable/)
    assert.doesNotMatch(unreachable, /socket hang up|secret-host/)
    const server = textOf(html({ error: new ApiClientError({ type: "about:blank", title: "Internal Server Error", status: 500, detail: "An unexpected error occurred." }) }))
    assert.match(server, /Something went wrong on our side\. Please try again\./)
    assert.doesNotMatch(server, /Traceback|File "/)
  },

  "the input stays usable after an error so the user can retry or change the text"() {
    const markup = html({ error: new ApiUnreachableError(new Error("down")), draft: "I want to save more" })
    assert.equal(isDisabled(buttonTag(markup, "Analyse")), false)
    assert.match(markup, /<textarea[^>]*id="insight-text"/)
    assert.match(textOf(markup), /Try again/)
  },

  "results that no longer match the box are labelled; a refresh in progress is announced"() {
    const data = fixture("conflict")
    const stale = textOf(html({ data, stale: true, draft: "something new" }))
    assert.match(stale, /These results are not for the text in the box/)
    assert.match(stale, /Press Analyse to update them/)
    assert.doesNotMatch(textOf(html({ data, stale: false })), /These results are not for the text in the box/)
    const updating = html({ data, pending: true })
    assert.match(textOf(updating), /Updating…/)
    assert.equal(isDisabled(buttonTag(updating, "Clear")), true)
  },

  "the counter, the limit and the validation messages follow the backend's rules and never echo the text"() {
    const secret = "PRIVATE-MARKER-9137"
    const ok = html({ draft: `${secret} I want to save` })
    assert.equal(occurrences(ok, secret), 1, "the typed text appears only inside the text area")
    assert.match(textOf(ok), /\d+ \/ 1000 characters \(\d+ left\)/)
    assert.equal(isDisabled(buttonTag(ok, "Analyse")), false)
    assert.doesNotMatch(ok, /role="alert"/)

    const exact = html({ draft: "a".repeat(MAX_USER_TEXT_CHARS) })
    assert.match(textOf(exact), /1000 \/ 1000 characters \(0 left\)/)
    assert.equal(isDisabled(buttonTag(exact, "Analyse")), false)

    const over = html({ draft: `${secret}${"a".repeat(MAX_USER_TEXT_CHARS)}` })
    assert.match(textOf(over), /characters \(\d+ over\)/)
    assert.match(textOf(over), /over the 1000-character limit\. Please shorten it\./)
    assert.match(over, /role="alert"/)
    assert.equal(isDisabled(buttonTag(over, "Analyse")), true)
    assert.match(over, /aria-invalid="true"/)
    assert.equal(occurrences(over, secret), 1, "an over-long text is echoed only inside the text area, never in the message")

    const control = html({ draft: `${secret} bad\u0007text` })
    assert.match(textOf(control), /characters that cannot be analysed/)
    assert.equal(isDisabled(buttonTag(control, "Analyse")), true)
    assert.equal(occurrences(control, secret), 1)
  },

  "line breaks are allowed in the text (the backend collapses whitespace) and are counted like any character"() {
    const markup = html({ draft: "I want to save more.\nI also worry about debt.\n\tAnd about inflation." })
    assert.equal(isDisabled(buttonTag(markup, "Analyse")), false)
    assert.doesNotMatch(markup, /role="alert"/)
    assert.match(textOf(markup), /\d+ \/ 1000 characters/)
  },

  "clear is available once there is something to clear, and sends no text"() {
    assert.equal(isDisabled(buttonTag(html({ draft: "" }), "Clear")), true)
    assert.equal(isDisabled(buttonTag(html({ draft: "x" }), "Clear")), false)
    assert.equal(isDisabled(buttonTag(html({ data: fixture("records-only"), stale: false }), "Clear")), true) // records-only results: no text was submitted, so there is nothing to forget
    assert.equal(isDisabled(buttonTag(html({ data: fixture("conflict"), hasSubmittedText: true }), "Clear")), false) // results for a submitted text: Clear forgets it
    assert.equal(isDisabled(buttonTag(html({ data: fixture("conflict"), hasSubmittedText: true, pending: true }), "Clear")), true)
  },

  "accessibility wiring: label, descriptions, live region, four named regions with level-two headings, icons hidden, state conveyed by text"() {
    const markup = html({ data: fixture("conflict"), draft: "x".repeat(MAX_USER_TEXT_CHARS + 3) })
    assert.match(markup, /<label[^>]*for="insight-text"/)
    assert.match(markup, /<textarea[^>]*id="insight-text"/)
    const describedBy = /aria-describedby="([^"]+)"/.exec(markup)
    assert.ok(describedBy)
    for (const id of describedBy[1].split(" ")) assert.match(markup, new RegExp(`id="${id}"`), `aria-describedby target ${id} exists`)
    assert.match(markup, /aria-live="polite"/)
    assert.match(markup, /aria-label="Optional text about your finances"/)
    assert.match(markup, /role="region"[^>]*aria-label="Sentiment results"|aria-label="Sentiment results"[^>]*role="region"/)
    for (const heading of ["insights-heading", "risk-heading", "input-heading", "reading-heading"]) {
      assert.match(markup, new RegExp(`aria-labelledby="${heading}"`))
      assert.match(markup, new RegExp(`id="${heading}"[^>]*role="heading"[^>]*aria-level="2"`))
    }
    const svgs = markup.match(/<svg[^>]*>/g) ?? []
    assert.ok(svgs.length > 0)
    for (const svg of svgs) assert.match(svg, /aria-hidden="true"/, "decorative icons are hidden from screen readers")
    assert.match(textOf(markup), /Sentiment: Negative/) // the sentiment is in text, not only in an icon or a colour
    assert.match(markup, /<summary[^>]*>/) // technical details are a native, keyboard-operable <details>
  },

  "the direction and category of an insight are words, not only an icon"() {
    const markup = html({ data: fixture("records-only") })
    assert.match(markup, />Increased</)
    assert.match(markup, />Unchanged</)
    assert.match(markup, />Change over time</)
    assert.match(markup, />Share of income</)
  },

  "responsive layout: stacked by default, two columns from the large breakpoint, records first, long text may wrap"() {
    const markup = html({ data: fixture("conflict") })
    assert.match(markup, /grid gap-6 lg:grid-cols-12/)
    const left = markup.indexOf("lg:col-span-5")
    const right = markup.indexOf("lg:col-span-7")
    assert.ok(left > 0 && right > left, "the records column comes first in reading order, so a phone shows it first")
    assert.ok(markup.indexOf('id="insights-heading"') > left && markup.indexOf('id="insights-heading"') < right)
    assert.ok(markup.indexOf('id="input-heading"') > right)
    assert.match(markup, /md:grid-cols-2/) // the intro uses two columns from the tablet width
    assert.match(markup, /\[overflow-wrap:anywhere\]/)
    assert.match(markup, /flex-wrap/)
    assert.doesNotMatch(markup, /overflow-x-(scroll|auto)|w-\[\d+px\]|min-w-\[\d+px\]/) // no fixed width that could force a horizontal scroll
  },

  "unusual and hostile text is escaped and cannot break the layout"() {
    const data = structuredClone(fixture("conflict"))
    const hostile = "<script>alert(1)</script> & \"quotes\" " + "x".repeat(95)
    data.user_sentiment.evidence = [{ label: "negative_cue", phrase: hostile }]
    data.user_sentiment.preferences = [{ ...data.user_sentiment.preferences[0], evidence: { label: "capital_preservation", phrase: hostile } }]
    const markup = html({ data })
    assert.doesNotMatch(markup, /<script>/)
    assert.match(markup, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/)
    const quotes = markup.match(/<p class="[^"]*">“/g) ?? []
    assert.ok(quotes.length >= 2, "an evidence quote and a preference quote")
    for (const quote of quotes) assert.match(quote, /\[overflow-wrap:anywhere\]/) // every quoted phrase may wrap, so a long word cannot push the layout wider
    assert.match(textOf(markup), /<script>alert\(1\)<\/script>/) // shown as text, decoded only for reading
  },

  "an unrecognised sentiment value from the backend is shown as received, marked inconclusive, not mapped to a label"() {
    const data = structuredClone(fixture("conflict"))
    ;(data.user_sentiment as { sentiment: string | null }).sentiment = "ecstatic"
    const markup = html({ data })
    const text = textOf(markup)
    assert.match(text, /Sentiment: Unrecognised \(ecstatic\)/)
    assert.match(markup, /data-reading="inconclusive"/)
    assert.doesNotMatch(text, /Sentiment: (Positive|Neutral)/)
  },

  "a confidence the backend does provide is shown exactly as returned"() {
    const data = structuredClone(fixture("conflict"))
    ;(data.user_sentiment as { confidence: number | null }).confidence = 0.82
    assert.match(textOf(html({ data })), /0\.82 \(as returned by the analysis\)/)
  },

  "the card wires the cached backend response into the view and shows a loading state, never a result, before data arrives"() {
    const seeded = new QueryClient()
    seeded.setQueryData(["personalized-insight", 1, null], fixture("records-only"))
    const wrap = (client: QueryClient) =>
      textOf(
        renderToStaticMarkup(
          <MemoryRouter>
            <QueryClientProvider client={client}>
              <BehaviourSentimentCard profileId={1} />
            </QueryClientProvider>
          </MemoryRouter>,
        ),
      )
    const withData = wrap(seeded)
    assert.match(withData, /What your records show/)
    assert.match(withData, /Expenses increased/)
    const empty = wrap(new QueryClient())
    assert.match(empty, /Reading your information…/)
    assert.doesNotMatch(empty, /What your records show|Sentiment:|\d+ reported months?/)
  },

  // ---------------------------------------------------------------- the trained-model states (ADR-052). The model-* fixtures come from the real route with a TEST DOUBLE, not a real model.

  "a validated model's reading is labelled as such, shows its probabilities, calibrated confidence and intensity as returned, and keeps the rules reading beside it"() {
    const data = fixture("model-validated-double")
    const s = data.user_sentiment
    assert.deepEqual([s.method, s.validation_status, s.fallback_used, s.disagreement, s.confidence_calibration_status], ["hybrid", "validated", false, false, "calibrated"])
    const markup = html({ data })
    const text = textOf(markup)
    assert.match(markup, /data-method="validated_model"/)
    assert.match(text, new RegExp(`Method used ${VALIDATED_MODEL_LABEL}`))
    assert.match(text, /model test_double_not_a_real_model \(sentiment-double-1\)/)
    assert.match(text, /Class probabilities Positive 0\.04 Negative 0\.88 Neutral 0\.08/)
    assert.match(text, /Confidence 0\.88 \(as returned by the analysis\), band: high \(calibrated\)/)
    assert.match(text, /Sentiment intensity -0\.72 \(from -1, most negative, to \+1, most positive\)/)
    assert.match(text, /Rules baseline reading Negative \(user_text_rules_v1, kept for comparison\)/)
    assert.doesNotMatch(markup, /data-fallback|data-disagreement/)
    assert.ok(text.includes(INTERPRETATION_NOTICE) && text.includes(INFORMATIONAL_NOTICE))
    assert.match(text, /An automatic reading, not a fact about you/) // the baseline's "not a trained or validated model" wording is not used for a model reading
    assert.doesNotMatch(text, /not a trained or validated model/)
  },

  "a model that is not validated is never called validated"() {
    const data = structuredClone(fixture("model-validated-double"))
    data.user_sentiment.validation_status = "unvalidated"
    const markup = html({ data })
    assert.match(markup, /data-method="unvalidated_model"/)
    assert.match(textOf(markup), /Model analysis \(not validated\)/)
    assert.ok(!textOf(markup).includes(VALIDATED_MODEL_LABEL))
  },

  "a disagreement between the model and the rules is shown with both readings, no confidence and no chosen winner"() {
    const data = fixture("model-disagreement-double")
    assert.deepEqual([data.user_sentiment.sentiment, data.user_sentiment.disagreement, data.user_sentiment.confidence], ["uncertain", true, null])
    const markup = html({ data })
    const text = textOf(markup)
    assert.match(markup, /data-disagreement="true"/)
    assert.match(text, /The model and the rules baseline read this text differently/)
    assert.match(text, /Sentiment: Uncertain/)
    assert.match(text, /Class probabilities Positive 0\.93/)
    assert.match(text, /Rules baseline reading Negative/)
    assert.match(text, /Confidence Not available/)
    assert.match(markup, /data-state="weak"/)
  },

  "when a configured model cannot answer, the rules baseline fallback is labelled, explained by a reason, and the model's fields are empty"() {
    for (const [name, reason] of [["model-below-threshold", "the model was not confident enough"], ["model-unavailable-fallback", "the model software is not installed"]] as const) {
      const data = fixture(name)
      assert.equal(data.user_sentiment.fallback_used, true, name)
      const markup = html({ data })
      const text = textOf(markup)
      assert.match(markup, /data-method="rules_fallback"/, name)
      assert.match(text, new RegExp(`Method used ${RULES_FALLBACK_LABEL}`), name)
      assert.ok(text.includes(FALLBACK_MESSAGE), name)
      assert.ok(text.includes(`(${reason}.)`), name)
      assert.match(text, new RegExp(`Why the rules answered ${reason}`), name)
      assert.doesNotMatch(text, /Class probabilities/, name)
      assert.ok(!text.includes(VALIDATED_MODEL_LABEL), name)
      assert.match(text, /Sentiment: Negative/, name) // the rules baseline still answered
    }
  },

  "with the model unavailable and fallback off, nothing is interpreted and the page says the model was unavailable"() {
    const data = fixture("model-unavailable-no-fallback")
    assert.deepEqual([data.user_sentiment.abstained, data.user_sentiment.abstain_reason, data.user_sentiment.fallback_used], [true, "model_unavailable", true])
    const markup = html({ data })
    const text = textOf(markup)
    assert.match(markup, /data-method="model_unavailable"/)
    assert.match(text, new RegExp(`Method used ${MODEL_UNAVAILABLE_LABEL}`))
    assert.ok(text.includes(MODEL_UNAVAILABLE_MESSAGE))
    assert.match(text, /Sentiment: Not enough evidence/)
    assert.doesNotMatch(text, /Sentiment: (Positive|Negative|Mixed|Neutral)|Unconfirmed/)
  },

  "without a validated regression head the intensity reads 'Not available', never 0, and a missing confidence is stated as not available"() {
    for (const name of ["conflict", "records-only", "model-disagreement-double", "model-below-threshold"]) {
      const data = fixture(name)
      assert.equal(data.user_sentiment.sentiment_intensity, null, name)
      assert.equal(data.user_sentiment.intensity_available, false, name)
      const text = textOf(html({ data }))
      if (data.user_sentiment.status === "analysed") assert.match(text, /Sentiment intensity Not available: no validated intensity model/, name)
      assert.doesNotMatch(text, /Sentiment intensity 0\b|Sentiment intensity -?\d/, name)
    }
    assert.match(textOf(html({ data: fixture("conflict") })), /Confidence Not available/)
    assert.match(html({ data: fixture("conflict") }), /aria-label="Confidence not available"/)
  },

  "a model reading is shown only for the profile it was computed for, and nothing about it is stored in the browser"() {
    const client = seededClient(2, "model-validated-double")
    const render = (id: number) =>
      textOf(
        renderToStaticMarkup(
          <MemoryRouter>
            <QueryClientProvider client={client}>
              <FinancialBehaviourContent profileId={id} />
            </QueryClientProvider>
          </MemoryRouter>,
        ),
      )
    assert.match(render(2), /Validated model analysis/)
    const other = render(3)
    assert.match(other, /Reading your monthly records…/)
    assert.doesNotMatch(other, /Validated model analysis|Class probabilities|test_double_not_a_real_model/)
    assert.match(readFileSync(path.resolve(process.cwd(), "src/pages/financial-behaviour-page.tsx"), "utf8"), /<FinancialBehaviourReal key=\{profileId\} profileId=\{profileId\}/)
    assert.match(readFileSync(path.resolve(process.cwd(), "src/components/financial-health/financial-behaviour-real.tsx"), "utf8"), /<BehaviourSentimentCard key=\{profileId\} profileId=\{profileId\}/)
  },

  // ---------------------------------------------------------------- Financial Health: spending from reported months, and debt & commitments (ADR-051)

  "spending: the backend's expense findings are shown once each with their sources, and the card says an individual has no category breakdown"() {
    const data = fixture("records-only")
    const markup = renderToStaticMarkup(
      <MemoryRouter>
        <SpendingFromRecordsView data={data} loading={false} error={null} onRetry={noop} />
      </MemoryRouter>,
    )
    const text = textOf(markup)
    const rows = selectSpendingRows(data.behaviour.findings)
    assert.deepEqual(rows.map((r) => r.code), ["expenses_trend", "expense_to_income_ratio"])
    for (const row of rows) {
      assert.equal(occurrences(text, row.statement), 1, row.statement)
      assert.match(text, new RegExp(`Based on: ${row.sources.map((s) => s.replace(/[.]/g, "\\.")).join(", ")}`))
    }
    assert.doesNotMatch(text, /Savings (increased|decreased)|Investment contributions/) // only spending findings belong here
    assert.match(text, /From your reported months/)
    assert.match(text, /recorded as one total each month, so there is no category breakdown here/)
    assert.match(markup, /<a[^>]*href="\/profile\?household=open"[^>]*>Customer Profile → Household<\/a>/)
    assert.doesNotMatch(text, /No reported months yet/)
  },

  "spending: no reported months says so and assumes nothing; loading and a failed request are their own states, never an empty message"() {
    const view = (props: { data?: Insight; loading?: boolean; error?: unknown }) =>
      textOf(
        renderToStaticMarkup(
          <MemoryRouter>
            <SpendingFromRecordsView data={props.data} loading={props.loading ?? false} error={props.error ?? null} onRetry={noop} />
          </MemoryRouter>,
        ),
      )
    const empty = view({ data: fixture("nothing-available") })
    assert.match(empty, /No reported months yet/)
    assert.match(empty, /None have been reported for this profile, so nothing is assumed\./)
    assert.doesNotMatch(empty, /Based on:|₹ ?\d|\d+(\.\d+)?%/)
    const loading = view({ loading: true })
    assert.match(loading, /Reading your reported months…/)
    assert.doesNotMatch(loading, /No reported months yet|Based on:/)
    const failed = view({ data: fixture("records-only"), error: new ApiUnreachableError(new Error("down")) })
    assert.match(failed, /Service unavailable/)
    assert.match(failed, /Try again/)
    assert.doesNotMatch(failed, /No reported months yet|Expenses increased|Based on:/) // a failure is not rendered as "empty", and no earlier data stays beside it
  },

  "debt & commitments: an individual has none recorded, stated as not recorded rather than as a value, and a household member is pointed to the household's own liabilities"() {
    const render = (householdName: string | null) =>
      renderToStaticMarkup(
        <MemoryRouter>
          <CommitmentsView householdName={householdName} />
        </MemoryRouter>,
      )
    const alone = render(null)
    assert.match(textOf(alone), /Debt & Commitments/)
    assert.match(textOf(alone), /Not recorded for an individual/)
    assert.match(textOf(alone), /WealthPilot does not record loans or EMIs for an individual, so none are shown and none are assumed\./)
    assert.doesNotMatch(alone, /<a /)
    assert.doesNotMatch(textOf(alone), /₹|\bNot available\b/)
    const member = render("The Test Household")
    assert.match(textOf(member), /The “The Test Household” household records its own loans and EMIs/)
    assert.match(member, /<a[^>]*href="\/profile\?household=open"[^>]*>Customer Profile → Household → Liabilities<\/a>/)
    assert.doesNotMatch(textOf(member), /₹ ?\d/) // no household figure is shown on the individual page
  },

  // ---------------------------------------------------------------- the compact summary on Financial Health

  "summary: shows the month count, at most three backend facts, the assessment sentence and a link to the page; no text box and no reading"() {
    const data = fixture("records-only")
    const markup = summaryHtml({ data })
    const text = textOf(markup)
    assert.match(text, /Financial behaviour & sentiment/)
    assert.match(text, /2 reported months/)
    assert.match(text, /latest 2026-02/)
    const facts = data.statements.filter((s) => s.kind === "behaviour_fact" && s.sources[0] !== "observation_count")
    for (const fact of facts.slice(0, 3)) assert.equal(occurrences(text, fact.text), 1, fact.text)
    for (const fact of facts.slice(3)) assert.doesNotMatch(text, new RegExp(fact.text.slice(0, 40).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")))
    assert.doesNotMatch(text, /2 months have been reported\./) // the bare count is the badge, not a repeated line
    assert.match(text, /More findings are on the full page\./)
    const risk = data.statements.find((s) => s.kind === "risk_assessment")
    assert.ok(risk)
    assert.match(text, new RegExp(risk.text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")))
    assert.doesNotMatch(markup, /<input|<textarea/)
    assert.doesNotMatch(text, /Sentiment:|Describe your financial concerns|characters/)
  },

  "summary: the link opens the dedicated page, has descriptive text, and its icon is hidden from screen readers"() {
    const markup = summaryHtml({ data: fixture("records-only") })
    const link = /<a[^>]*href="\/financial-behaviour"[^>]*>(.*?)<\/a>/s.exec(markup)
    assert.ok(link, "link to /financial-behaviour not found")
    assert.match(textOf(link[1]), /Open Financial Behaviour & Sentiment/)
    assert.match(link[1], /<svg[^>]*aria-hidden="true"/)
    assert.doesNotMatch(link[0], /<button|role="button"|data-slot="button"/) // a real link: assistive technology must not be told it is a button
  },

  "summary: no records says so, and no figure or default is shown"() {
    const text = textOf(summaryHtml({ data: fixture("no-records-no-text") }))
    assert.match(text, /0 reported months/)
    assert.match(text, /No monthly records yet/)
    assert.match(text, /Nothing is assumed in the meantime\./)
    assert.doesNotMatch(text, /Based on:|₹ ?\d/)
    assert.match(text, /risk assessment/)
  },

  "summary: neither records nor an assessment is stated explicitly for both"() {
    const text = textOf(summaryHtml({ data: fixture("nothing-available") }))
    assert.match(text, /No monthly records yet/)
    assert.match(text, /No risk assessment is on file for this profile yet\./)
  },

  "summary: loading shows a status skeleton and marks the region busy, with no facts"() {
    const markup = summaryHtml({ loading: true })
    assert.match(markup, /role="status"/)
    assert.match(markup, /aria-busy="true"/)
    assert.match(textOf(markup), /Summarising your reported months…/)
    assert.doesNotMatch(textOf(markup), /reported months?\b.*latest|Observed/)
  },

  "summary: an error replaces the facts, offers a retry, and never shows earlier data beside it"() {
    const text = textOf(summaryHtml({ data: fixture("records-only"), error: new ApiUnreachableError(new Error("down")) }))
    assert.match(text, /Service unavailable/)
    assert.match(text, /Try again/)
    assert.doesNotMatch(text, /Expenses increased|Savings (increased|decreased)|\d+ reported months?/)
    assert.match(text, /Open Financial Behaviour & Sentiment/) // the page link stays available
  },

  "summary card: renders the cached backend response, and shows loading, never a result, before data arrives"() {
    const wrap = (client: QueryClient) =>
      textOf(
        renderToStaticMarkup(
          <MemoryRouter>
            <QueryClientProvider client={client}>
              <BehaviourSummaryCard profileId={2} />
            </QueryClientProvider>
          </MemoryRouter>,
        ),
      )
    const withData = wrap(seededClient(2, "records-only"))
    assert.match(withData, /2 reported months/)
    assert.match(withData, /Expenses increased/)
    const empty = wrap(new QueryClient())
    assert.match(empty, /Summarising your reported months…/)
    assert.doesNotMatch(empty, /Expenses|\d+ reported months?/)
  },

  // ---------------------------------------------------------------- the dedicated page

  "page: one level-one heading, the explanation once, the input and results, and a link back; the card does not repeat the title"() {
    const markup = renderToStaticMarkup(
      <MemoryRouter>
        <QueryClientProvider client={seededClient(2, "conflict")}>
          <FinancialBehaviourContent profileId={2} />
        </QueryClientProvider>
      </MemoryRouter>,
    )
    const text = textOf(markup)
    assert.equal((markup.match(/<h1\b/g) ?? []).length, 1)
    assert.match(/<h1[^>]*>(.*?)<\/h1>/s.exec(markup)?.[1] ?? "", /Financial Behaviour &amp; Sentiment/)
    assert.equal(occurrences(text, "changes nothing about your risk profile, your allocation or your recommendations"), 1)
    assert.doesNotMatch(markup, /data-slot="card-title"[^>]*>[^<]*Financial behaviour/) // no second title inside the card
    assert.match(text, /Describe your financial concerns, goals or feelings \(optional\)/)
    assert.match(text, /\d+ \/ 1000 characters/)
    assert.match(text, /Financial behaviour overview/)
    assert.match(text, /Your financial behaviour is calculated from the monthly records you provide\. It describes your numbers and does not change your risk profile, investments or recommendations\./)
    assert.match(text, /A simple automatic reading, not a validated model/)
    assert.match(markup, /<a[^>]*href="\/financial-health"[^>]*>Financial Health<\/a>/)
    assert.match(text, /risk assessment stays the authority/)
  },

  "page: results shown are the backend response for that profile and nothing from another profile's cache"() {
    const client = seededClient(2, "records-only")
    client.setQueryData(["personalized-insight", 3, null], fixture("nothing-available"))
    const render = (id: number) =>
      textOf(
        renderToStaticMarkup(
          <MemoryRouter>
            <QueryClientProvider client={client}>
              <FinancialBehaviourContent profileId={id} />
            </QueryClientProvider>
          </MemoryRouter>,
        ),
      )
    assert.match(render(2), /Reported months 2/)
    const other = render(3)
    assert.match(other, /No monthly records yet/)
    assert.doesNotMatch(other, /Expenses increased|Reported months \d/)
    const unknown = render(9)
    assert.match(unknown, /Reading your monthly records…/)
    assert.doesNotMatch(unknown, /Expenses increased|Reported months \d|No monthly records yet/)
  },

  "page: without a profile it shows the standard no-profile prompt and no input"() {
    const markup = renderToStaticMarkup(
      <MemoryRouter>
        <QueryClientProvider client={new QueryClient()}>
          <CustomerProvider>
            <FinancialBehaviourPage />
          </CustomerProvider>
        </QueryClientProvider>
      </MemoryRouter>,
    )
    const text = textOf(markup)
    assert.match(text, /Financial Behaviour & Sentiment/)
    assert.match(text, /Create Profile/)
    assert.doesNotMatch(markup, /<input|<textarea/)
    assert.doesNotMatch(text, /Observed from your records|Sentiment:/)
  },
}
