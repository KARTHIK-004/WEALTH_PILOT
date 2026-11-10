/**
 * Component cases for the research-only pretrained-model panel (ADR-053, role slots from ADR-055), rendered to static HTML with react-dom/server through Vite's SSR loader (`npm test`).
 *
 * The DISABLED case uses the real backend response saved in tests/fixtures/demo (the route's actual output: Horizon registered, research off). The other variants (a single model that agrees or differs
 * from the rules reading, two models, a failing model, loading, ...) are hand-built from that response with a typed spread: they exercise how the UI words each backend status, and are NOT
 * evidence about any real model. No label, agreement or confidence is ever derived in the UI, so these cases also check that nothing is.
 */
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import path from "node:path"

import { renderToStaticMarkup } from "react-dom/server"
import { MemoryRouter } from "react-router"

import { BehaviourSentimentView } from "@/components/financial-health/behaviour-sentiment-view"
import { TransformerResearchPanel } from "@/components/financial-health/transformer-research-panel"
import { isEmptySlot, labelText, reasonText, researchState, scoreRows, type ResearchModelResult, type TransformerResearch } from "@/lib/transformer-research"
import type { components } from "@/types/api"

type Insight = components["schemas"]["PersonalizedInsightResponse"]
type Demo = components["schemas"]["DemoFinancialBehaviourResponse"]
type Relation = components["schemas"]["ModelVsRulesOut"]["relation"]
type RulesLabel = components["schemas"]["ModelVsRulesOut"]["rules_label"]

const fixture = (...parts: string[]): unknown => JSON.parse(readFileSync(path.resolve(process.cwd(), "tests", "fixtures", ...parts), "utf8"))
const DEMO = fixture("demo", "demo-example-text.json") as Demo
const OFF = DEMO.insight.transformer_research as TransformerResearch
// an OLDER backend response: the real current fixture with the optional research object removed (the saved fixtures carry it)
const { transformer_research: _research, ...OLD_WITHOUT_RESEARCH } = fixture("no-records-no-text.json") as Insight
const OLD = OLD_WITHOUT_RESEARCH as Insight
const noop = () => {}

function textOf(markup: string): string {
  return markup.replace(/<[^>]*>/g, " ").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#x27;|&#39;/g, "'").replace(/\s+/g, " ").trim()
}
const panel = (research: TransformerResearch | null | undefined): string => renderToStaticMarkup(<TransformerResearchPanel research={research} />)

const EMPTY_FINANCIAL = OFF.models.find((m) => m.slot === "financial") as ResearchModelResult
const EMPTY_GENERAL = OFF.models.find((m) => m.slot === "general") as ResearchModelResult
const answered = (slot: "financial" | "general", label: "positive" | "negative" | "neutral", native: string, scores: Record<string, number>): ResearchModelResult => ({
  slot, display_name: slot === "financial" ? "Financial sentiment model" : "General sentiment model", model_id: slot === "financial" ? "example/financial-model" : "Horizon-Labs/multilingual-sentiment-small",
  revision: slot === "financial" ? "b".repeat(40) : "e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac", availability: "available", unavailable_reason: null, native_label: native, normalized_label: label,
  raw_scores: { [native]: 3.2, other: 0.1 }, probabilities: scores, probability_kind: "raw_softmax_uncalibrated", processing_ms: 12.5,
})
const failed = (base: ResearchModelResult, reason: ResearchModelResult["unavailable_reason"], availability: ResearchModelResult["availability"] = "unavailable"): ResearchModelResult => ({
  ...base, model_id: "Horizon-Labs/multilingual-sentiment-small", revision: "e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac", availability, unavailable_reason: reason,
})
const vs = (slot: "financial" | "general", model: "positive" | "negative" | "neutral", rules: RulesLabel, relation: Relation) => ({ slot, rules_label: rules, model_label: model, relation, explanation: "x" })
const on = (over: Partial<TransformerResearch>): TransformerResearch => ({ ...OFF, enabled: true, processing_metadata: { ...OFF.processing_metadata, input_eligible: true }, ...over })
const RULES_NEG = { label: "negative", method: "rules_baseline", model_version: "user_text_rules_v1" } as const

const GENERAL_NEG = answered("general", "negative", "negative", { negative: 0.9512, neutral: 0.0188, positive: 0.03 })
const SINGLE_AGREES = on({
  models: [EMPTY_FINANCIAL, GENERAL_NEG],
  comparison: { status: "single_model", shared_label: "negative", explanation: "One pretrained model answered, and its label is compared with the rules-based reading.", model_vs_rules: [vs("general", "negative", "negative", "agrees")] },
  overall_sentiment: "negative", overall_source: "transformer_comparison", rules_relation: "agrees", uncertainty_reason: null, rules_baseline: RULES_NEG,
})
const SINGLE_DIFFERS = on({
  models: [EMPTY_FINANCIAL, answered("general", "positive", "positive", { negative: 0.1, neutral: 0.2, positive: 0.7 })],
  comparison: { status: "single_model", shared_label: "positive", explanation: "One pretrained model answered, and its label is compared with the rules-based reading.", model_vs_rules: [vs("general", "positive", "negative", "disagrees")] },
  overall_sentiment: "uncertain", overall_source: "transformer_comparison", rules_relation: "disagrees", uncertainty_reason: "rules_disagree", rules_baseline: RULES_NEG,
})
const SINGLE_ABSTAINED = on({
  models: [EMPTY_FINANCIAL, GENERAL_NEG],
  comparison: { status: "single_model", shared_label: "negative", explanation: "One pretrained model answered.", model_vs_rules: [vs("general", "negative", null, "rules_abstained")] },
  overall_sentiment: "negative", overall_source: "transformer_comparison", rules_relation: "rules_abstained", uncertainty_reason: null, rules_baseline: { ...RULES_NEG, label: "uncertain" },
})
const FIN_NEG = answered("financial", "negative", "Bearish", { Bearish: 0.9, Bullish: 0.05, Neutral: 0.05 })
const TWO_AGREE = on({
  models: [FIN_NEG, GENERAL_NEG], comparison: { status: "agreement", shared_label: "negative", explanation: "Both pretrained models produced the same label.", model_vs_rules: [vs("financial", "negative", "negative", "agrees"), vs("general", "negative", "negative", "agrees")] },
  overall_sentiment: "negative", overall_source: "transformer_comparison", rules_relation: "agrees", uncertainty_reason: null,
})
const TWO_SPLIT = on({
  models: [FIN_NEG, answered("general", "positive", "positive", { negative: 0.1, neutral: 0.2, positive: 0.7 })],
  comparison: { status: "disagreement", shared_label: null, explanation: "The two pretrained models produced different labels, so no single sentiment is reported.", model_vs_rules: [vs("financial", "negative", "negative", "agrees"), vs("general", "positive", "negative", "disagrees")] },
  overall_sentiment: "uncertain", overall_source: "transformer_comparison", rules_relation: "not_compared", uncertainty_reason: "models_disagree",
})
const ONE_DOWN = on({
  models: [FIN_NEG, failed(EMPTY_GENERAL, "timeout")], comparison: { status: "one_model_unavailable", shared_label: null, explanation: "Only one pretrained model produced a result.", model_vs_rules: [vs("financial", "negative", "negative", "agrees")] },
  overall_sentiment: "negative", overall_source: "rules_baseline_fallback", rules_relation: "not_compared", uncertainty_reason: "one_model_unavailable",
})
const MODEL_DOWN = on({
  models: [EMPTY_FINANCIAL, failed(EMPTY_GENERAL, "load_failed")], comparison: { status: "model_unavailable", shared_label: null, explanation: "The pretrained model produced no result.", model_vs_rules: [] },
  overall_source: "rules_baseline_fallback", rules_relation: "not_compared", uncertainty_reason: "transformers_unavailable",
})
const LOADING = on({
  models: [EMPTY_FINANCIAL, failed(EMPTY_GENERAL, "loading", "loading")], comparison: { status: "model_unavailable", shared_label: null, explanation: "The pretrained model produced no result.", model_vs_rules: [] },
  overall_source: "rules_baseline_fallback", rules_relation: "not_compared", uncertainty_reason: "transformers_unavailable",
})
const INTERNAL = on({
  models: [EMPTY_FINANCIAL, failed(EMPTY_GENERAL, "internal_error")], comparison: { status: "model_unavailable", shared_label: null, explanation: "The pretrained model produced no result.", model_vs_rules: [] },
  overall_source: "rules_baseline_fallback", rules_relation: "not_compared", uncertainty_reason: "transformers_unavailable",
})
const NOT_RUN = on({
  models: [EMPTY_FINANCIAL, failed(EMPTY_GENERAL, "input_not_eligible")], comparison: { status: "model_unavailable", shared_label: null, explanation: "x", model_vs_rules: [] },
  processing_metadata: { ...OFF.processing_metadata, input_eligible: false }, overall_source: "rules_baseline_fallback", uncertainty_reason: "input_not_eligible",
})
// The REAL current response has Horizon registered (R1, ADR-056): the general slot is "unavailable / disabled" while research is off. NONE_REGISTERED is hand-built, to keep the wording for a
// state with no registered candidate (for example an un-registered model) under test.
const REGISTRATION_PENDING_GENERAL: ResearchModelResult = { ...EMPTY_GENERAL, model_id: null, revision: null, unavailable_reason: "registration_pending" }
const NONE_REGISTERED = on({
  models: [EMPTY_FINANCIAL, REGISTRATION_PENDING_GENERAL],
  comparison: { status: "no_model_configured", shared_label: null, explanation: "No pretrained model is registered for research use, so only the rules-based reading is available.", model_vs_rules: [] },
  overall_source: "rules_baseline_fallback", uncertainty_reason: "no_model_registered", model_versions: {},
})

const viewProps = { draft: "", hasSubmittedText: false, stale: false, pending: false, loading: false, error: undefined, onDraftChange: noop, onSubmit: noop, onClear: noop, onRetry: noop }
const view = (data: Insight, plain: boolean): string => renderToStaticMarkup(<MemoryRouter><BehaviourSentimentView {...viewProps} data={data} plainLanguage={plain} noteOnly={plain} /></MemoryRouter>)

export const cases: Record<string, () => void | Promise<void>> = {
  "the real backend response (research off, Horizon registered) shows the switched-off state, all three notices, an empty financial slot, an unavailable general slot and no invented result"() {
    const markup = panel(OFF)
    const text = textOf(markup)
    assert.equal(researchState(OFF), "switched_off")
    assert.match(text, /Research models are switched off/)
    assert.match(text, /Experimental pretrained model output — not human validated\./)
    assert.match(text, /Model predictions are not financial advice\./)
    assert.match(text, /Sentiment does not modify your financial risk profile or investment recommendations\./)
    assert.match(text, /A\. Rules-based reading/)
    assert.match(text, /B\. Pretrained model results/)
    assert.match(text, /C\. Comparison/)
    assert.equal((markup.match(/data-availability="empty"/g) ?? []).length, 1) // only the financial slot is empty
    assert.match(text, /Financial sentiment model No model registered/)
    assert.match(text, /No model has been approved for this role\./)
    assert.match(text, /General sentiment model Unavailable/) // Horizon is registered but research is off
    assert.match(text, /The research models are switched off\./)
    assert.doesNotMatch(text, /General sentiment model No model registered/)
    assert.doesNotMatch(text, /Answered/)
    assert.doesNotMatch(text, /Independent result\. Not combined or averaged with any other model\. Label:/) // no model card shows a label (the rules-based reading in section A may)
    assert.match(text, /Confidence is not available/)
    assert.match(text, /Your stored risk assessment remains the authoritative record/)
  },

  "research switched on with nothing registered (hand-built state) says so, and an empty slot is a plain empty card, never a failure or a substituted model"() {
    const text = textOf(panel(NONE_REGISTERED))
    assert.equal(researchState(NONE_REGISTERED), "no_model_registered")
    assert.match(text, /No research model is registered/)
    assert.match(text, /only the rules-based reading is shown/i)
    assert.ok(isEmptySlot(EMPTY_FINANCIAL) && isEmptySlot(REGISTRATION_PENDING_GENERAL) && !isEmptySlot(EMPTY_GENERAL))
    assert.ok(!isEmptySlot(failed(EMPTY_GENERAL, "load_failed"))) // a candidate that failed is not an empty slot
    assert.doesNotMatch(text, /No result\./)
  },

  "a single model that agrees with the rules reading shows its label, the raw scores only inside a 'not a confidence' disclosure, and says it is not human validated"() {
    const markup = panel(SINGLE_AGREES)
    const text = textOf(markup)
    assert.equal(researchState(SINGLE_AGREES), "single_agrees")
    assert.match(text, /Model and rules agree/)
    assert.match(text, /One model answered/)
    assert.match(text, /General sentiment model Answered Independent result/)
    assert.match(text, /Financial sentiment model No model registered/) // the empty financial slot stays visibly empty
    assert.match(text, /Label: Negative/)
    assert.match(text, /Raw model scores \(not a confidence\)/)
    assert.match(text, /Score kind raw, uncalibrated/)
    assert.match(text, /Score: negative 0\.9512 /)
    assert.match(text, /General sentiment model: Negative\. Rules-based reading: Negative\./)
    assert.match(text, /Combined reading: Negative \(experimental\)/)
    assert.match(text, /Agreement between two classifiers does not show that either is right/)
    assert.match(text, /not human validated/)
    assert.doesNotMatch(text, /%|confidence of|accuracy|\bintensity\b/i)
  },

  "a single model that differs from the rules reading gives an Uncertain combined reading, with both readings shown"() {
    const text = textOf(panel(SINGLE_DIFFERS))
    assert.equal(researchState(SINGLE_DIFFERS), "single_differs")
    assert.match(text, /Model and rules differ/)
    assert.match(text, /General sentiment model: Positive\. Rules-based reading: Negative\./)
    assert.match(text, /Combined reading: Uncertain \(experimental\)/)
    assert.match(text, /differs from the rules-based reading, so the result is shown as uncertain/)
    assert.match(text, /The rules-based reading differs from the model/)
  },

  "when the rules reading did not commit, the model's label is shown with that stated and nothing to compare"() {
    const text = textOf(panel(SINGLE_ABSTAINED))
    assert.equal(researchState(SINGLE_ABSTAINED), "single_rules_abstained")
    assert.match(text, /Model answered; rules did not commit/)
    assert.match(text, /did not commit to a label, so there is nothing to compare with/)
  },

  "two registered models agree or disagree, each shown separately, with a Model disagreement state and an Uncertain combined reading"() {
    const agree = textOf(panel(TWO_AGREE))
    assert.equal(researchState(TWO_AGREE), "models_agree")
    assert.match(agree, /Models agree/)
    assert.match(agree, /The two models agree/)
    assert.match(agree, /Financial sentiment model Answered/)
    assert.match(agree, /General sentiment model Answered/)
    const split = textOf(panel(TWO_SPLIT))
    assert.equal(researchState(TWO_SPLIT), "models_disagree")
    assert.match(split, /Model disagreement/)
    assert.match(split, /Label: Negative/)
    assert.match(split, /Label: Positive/)
    assert.match(split, /Combined reading: Uncertain \(experimental\)/)
    assert.match(split, /The two models produced different labels, so no single sentiment is reported/)
  },

  "one unavailable model among two is announced, its reason explained, the other shown alone, and the rules reading labelled as the fallback"() {
    const text = textOf(panel(ONE_DOWN))
    assert.equal(researchState(ONE_DOWN), "one_model_unavailable")
    assert.match(text, /One model unavailable/)
    assert.match(text, /The model took too long to answer\./)
    assert.match(text, /\(the rules-based reading, used as the fallback\)/)
    assert.match(text, /Only one pretrained model answered, so the rules-based reading is shown instead/)
  },

  "a model that could not load, is still loading, or hit an unexpected problem is shown as such, never as a result, with the rules reading as the fallback"() {
    const down = textOf(panel(MODEL_DOWN))
    assert.equal(researchState(MODEL_DOWN), "models_unavailable")
    assert.match(down, /Model unavailable/)
    assert.match(down, /The model could not be loaded\./)
    assert.match(down, /\(the rules-based reading, used as the fallback\)/)
    const loading = textOf(panel(LOADING))
    assert.equal(researchState(LOADING), "loading")
    assert.match(loading, /Model is being prepared/)
    assert.match(loading, /General sentiment model Loading/)
    assert.match(loading, /The model is being prepared\. Try again shortly\./)
    const internal = textOf(panel(INTERNAL))
    assert.match(internal, /The research model could not be used because of an unexpected problem\. Your reading above is not affected\./)
    for (const t of [down, loading, internal]) assert.doesNotMatch(t, /Raw model scores|Independent result\. Not combined or averaged with any other model\. Label:/)
  },

  "text that was not suitable (for example not in English) is 'Not run for this text', with the reason, and no model result"() {
    const text = textOf(panel(NOT_RUN))
    assert.equal(researchState(NOT_RUN), "not_run")
    assert.match(text, /Not run for this text/)
    assert.match(text, /not suitable for these models \(for example too short, unrelated to money, or not in English\)/)
  },

  "an absent research object renders nothing at all (an older response, or no text), and the rest of the view is unchanged"() {
    assert.equal(panel(undefined), "")
    assert.equal(panel(null), "")
    for (const plain of [false, true]) {
      assert.doesNotMatch(textOf(view(OLD, plain)), /Experimental pretrained models/)
    }
  },

  "an unknown label or reason code is shown as unavailable, never as neutral"() {
    assert.equal(labelText("something_new"), "Unavailable")
    assert.equal(labelText(null), "No reading")
    assert.equal(reasonText("something_new"), "Unavailable.")
    assert.equal(labelText("neutral"), "Neutral")
    assert.deepEqual(scoreRows(null), [])
    assert.deepEqual(scoreRows({ positive: 0.5 }), [{ label: "positive", value: "0.5" }])
  },

  "the panel appears with the real page's results in both the plain-language and the full view, after the reading, and the existing reading is untouched"() {
    for (const plain of [true, false]) {
      const markup = view(DEMO.insight, plain)
      const text = textOf(markup)
      assert.match(text, /Experimental pretrained models \(research only\)/, String(plain))
      assert.ok(markup.indexOf("Sentiment results") < markup.indexOf("Experimental pretrained model comparison"), String(plain))
      assert.equal((markup.match(/aria-label="Experimental pretrained model comparison"/g) ?? []).length, 1)
    }
    const agreeing = view({ ...DEMO.insight, transformer_research: SINGLE_AGREES }, true)
    assert.match(textOf(agreeing), /Model and rules agree/)
    assert.match(textOf(agreeing), /Detailed reading \(technical\)/) // the existing disclosure is still there
  },

  "accessibility and layout: a labelled section, a status banner, one labelled card per role slot, a two-column grid from the md breakpoint, and a single stack below it"() {
    const markup = panel(SINGLE_AGREES)
    assert.match(markup, /<section[^>]*aria-label="Experimental pretrained model comparison"/)
    assert.match(markup, /role="status"[^>]*aria-label="Model and rules agree"/)
    assert.match(markup, /aria-label="Financial sentiment model result"/)
    assert.match(markup, /aria-label="General sentiment model result"/)
    assert.match(markup, /class="grid gap-3 md:grid-cols-2"/)
    assert.match(markup, /<ul[^>]*aria-label="Important notices"/)
    assert.equal((markup.match(/<h3\b/g) ?? []).length, 1)
    assert.equal((markup.match(/<h1\b/g) ?? []).length, 0)
  },

  "the research library and panel compute nothing and store nothing (source rules)"() {
    const src = (file: string) => readFileSync(path.resolve(process.cwd(), file), "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "")
    for (const file of ["src/lib/transformer-research.ts", "src/components/financial-health/transformer-research-panel.tsx"]) {
      const code = src(file)
      assert.doesNotMatch(code, /Math\.|\.reduce\(|\.sort\(|localStorage|sessionStorage|indexedDB|document\.cookie|console\.|fetch\(|XMLHttpRequest|location\./, file)
      assert.doesNotMatch(code, /\b(score|probabilit\w*|value)\s*[<>]=?\s*\d/, file) // no threshold on a score
    }
  },
}
