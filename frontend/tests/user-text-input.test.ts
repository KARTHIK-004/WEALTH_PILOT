/**
 * Unit tests for the pure input rules and state transitions of the "Financial behaviour & sentiment" card (src/lib/user-text-input.ts), run with Node's built-in test runner:
 *
 *     npm test
 *
 * No dependency is added: Node 24 runs TypeScript directly, and the module under test has no React, DOM or browser API. The tests also read the BACKEND source and the card's source files
 * to keep the limit and the forbidden-character class in step with the backend and to enforce the privacy boundaries (no browser storage, no console, no URL, no mock results).
 */
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { test } from "node:test"

import {
  ABSTAIN_MESSAGE,
  CONFIDENCE_NOT_AVAILABLE,
  CONTROL_CHARACTERS,
  FALLBACK_MESSAGE,
  INFORMATIONAL_NOTICE,
  INITIAL_INPUT_STATE,
  INTERPRETATION_NOTICE,
  MAX_USER_TEXT_CHARS,
  MODEL_UNAVAILABLE_LABEL,
  MODEL_UNAVAILABLE_MESSAGE,
  NO_TEXT_MESSAGE,
  PREFERENCE_NOTICE,
  RULES_FALLBACK_LABEL,
  UNRELATED_MESSAGE,
  UNSUPPORTED_LANGUAGE_MESSAGE,
  VALIDATED_MODEL_LABEL,
  calibrationLabel,
  canSubmit,
  charactersRemaining,
  clearAll,
  countCharacters,
  describeConfidence,
  describeIntensity,
  describeMethodUsed,
  describeReadingStatus,
  describeSentiment,
  editDraft,
  fallbackReasonLabel,
  methodLabel,
  orderedProbabilities,
  preferenceLabel,
  relevanceLabel,
  resultsAreStale,
  submitDraft,
  toneLabel,
  topicLabel,
  validateUserText,
  validationLabel,
} from "../src/lib/user-text-input.ts"

const read = (relative: string): string => readFileSync(new URL(`../${relative}`, import.meta.url), "utf8")
const BACKEND = read("../backend/wealthpilot/core/user_text_sentiment.py")
const MARKER = "UNIQUE-PRIVATE-MARKER-4821"

// ------------------------------------------------------------------ the rules stay in step with the backend

test("the character limit equals the backend limit", () => {
  const match = /^MAX_TEXT_CHARS\s*=\s*(\d+)/m.exec(BACKEND)
  assert.ok(match, "MAX_TEXT_CHARS not found in the backend source")
  assert.equal(MAX_USER_TEXT_CHARS, Number(match[1]))
})

test("the forbidden control-character class is exactly the backend's, code point by code point", () => {
  const pattern = /_CONTROL\s*=\s*re\.compile\(r"\[([^\]]+)\]"\)/.exec(BACKEND)
  assert.ok(pattern, "_CONTROL not found in the backend source")
  const ranges = [...pattern[1].matchAll(/\\x([0-9a-f]{2})(?:-\\x([0-9a-f]{2}))?/gi)].map((m) => [parseInt(m[1], 16), parseInt(m[2] ?? m[1], 16)] as const)
  assert.ok(ranges.length >= 4)
  for (let code = 0; code < 0x100; code += 1) {
    const backendRejects = ranges.some(([low, high]) => code >= low && code <= high)
    assert.equal(CONTROL_CHARACTERS.test(String.fromCodePoint(code)), backendRejects, `code point 0x${code.toString(16)}`)
  }
  for (const allowed of ["\t", "\n", "\r", " ", "é", "₹", "😀"]) assert.equal(CONTROL_CHARACTERS.test(allowed), false)
})

// ------------------------------------------------------------------ counting and validation

test("characters are counted as code points, like Python's len, so an emoji is one", () => {
  assert.equal(countCharacters(""), 0)
  assert.equal(countCharacters("abc"), 3)
  assert.equal(countCharacters("😀😀"), 2)
  assert.equal("😀😀".length, 4) // the UTF-16 length that would have been wrong
  assert.equal(charactersRemaining("a".repeat(990)), 10)
  assert.equal(charactersRemaining("a".repeat(1001)), -1)
})

test("blank and whitespace-only input is sent as NO text, never as a neutral statement", () => {
  for (const blank of ["", " ", "   \t  ", "\n", " \r\n "]) assert.deepEqual(validateUserText(blank), { ok: true, text: null })
})

test("valid text is trimmed and otherwise kept as typed", () => {
  assert.deepEqual(validateUserText("  I want to invest safely  "), { ok: true, text: "I want to invest safely" })
  assert.deepEqual(validateUserText("tab\tand\nnewline are fine"), { ok: true, text: "tab\tand\nnewline are fine" })
})

test("exactly the limit is accepted; one more is refused with a count and without echoing the text", () => {
  assert.equal(validateUserText("a".repeat(1000)).ok, true)
  assert.equal(validateUserText("😀".repeat(1000)).ok, true) // 2000 UTF-16 units, 1000 characters
  const over = validateUserText(MARKER + "a".repeat(1000))
  assert.equal(over.ok, false)
  if (!over.ok) {
    assert.match(over.reason, /over the 1000-character limit/)
    assert.ok(!over.reason.includes(MARKER))
  }
  const one = validateUserText("a".repeat(1001))
  assert.ok(!one.ok && /1 character over/.test(one.reason))
})

test("control characters are refused with a generic reason that never contains the text", () => {
  for (const code of [0, 7, 8, 11, 12, 14, 27, 31, 127]) {
    const checked = validateUserText(`${MARKER} text${String.fromCodePoint(code)}more`)
    assert.equal(checked.ok, false, `code ${code}`)
    if (!checked.ok) assert.ok(!checked.reason.includes(MARKER))
  }
})

// ------------------------------------------------------------------ state transitions

test("editing the draft keeps the submitted text; typing makes the visible results stale", () => {
  const typed = editDraft(INITIAL_INPUT_STATE, "I want to save more")
  assert.equal(typed.submitted, null)
  assert.equal(resultsAreStale(INITIAL_INPUT_STATE), false)
  assert.equal(resultsAreStale(typed), true)
})

test("submitting a valid draft records it as the submitted text and makes the results current", () => {
  const outcome = submitDraft(editDraft(INITIAL_INPUT_STATE, "  I want to save more "), false)
  assert.equal(outcome.rejected, false)
  assert.equal(outcome.refetch, false)
  assert.equal(outcome.state.submitted, "I want to save more")
  assert.equal(resultsAreStale(outcome.state), false)
  assert.equal(resultsAreStale(editDraft(outcome.state, "I want to save more and more")), true)
})

test("submitting the same text again refetches explicitly, because the query key would not change", () => {
  const first = submitDraft(editDraft(INITIAL_INPUT_STATE, "same text"), false)
  const again = submitDraft(first.state, false)
  assert.equal(again.refetch, true)
  assert.equal(again.rejected, false)
})

test("a second submit while a request is pending is refused and changes nothing", () => {
  const state = editDraft(INITIAL_INPUT_STATE, "first")
  const refused = submitDraft(state, true)
  assert.equal(refused.rejected, true)
  assert.equal(refused.refetch, false)
  assert.deepEqual(refused.state, state)
  assert.equal(canSubmit(state, true), false)
  assert.equal(canSubmit(state, false), true)
})

test("an invalid draft is never submitted, and the previous submission is kept", () => {
  const sent = submitDraft(editDraft(INITIAL_INPUT_STATE, "good text"), false).state
  const bad = editDraft(sent, "bad\u0007text")
  const outcome = submitDraft(bad, false)
  assert.equal(outcome.rejected, true)
  assert.equal(outcome.state.submitted, "good text")
  assert.equal(canSubmit(bad, false), false)
  assert.equal(resultsAreStale(bad), true) // an invalid draft is never presented as the analysed text
  assert.equal(submitDraft(editDraft(INITIAL_INPUT_STATE, "x".repeat(1001)), false).rejected, true)
})

test("an empty or blank draft submits as records-only (no text) and is not stale against it", () => {
  const sent = submitDraft(editDraft(INITIAL_INPUT_STATE, "some text"), false).state
  const blank = submitDraft(editDraft(sent, "   "), false)
  assert.equal(blank.rejected, false)
  assert.equal(blank.state.submitted, null)
  assert.equal(resultsAreStale(blank.state), false)
  assert.equal(resultsAreStale(editDraft(INITIAL_INPUT_STATE, "   ")), false)
})

test("clear removes the draft and forgets the submitted text", () => {
  const sent = submitDraft(editDraft(INITIAL_INPUT_STATE, "private words"), false).state
  const cleared = clearAll()
  assert.deepEqual(cleared, { draft: "", submitted: null })
  assert.ok(!JSON.stringify(cleared).includes("private"))
  assert.notDeepEqual(sent, cleared)
})

// ------------------------------------------------------------------ wording of the backend's controlled labels

test("every backend sentiment label has distinct wording, and uncertain / insufficient evidence are never presented as neutral", () => {
  const labels = ["positive", "negative", "neutral", "mixed", "uncertain", "insufficient_evidence"].map((value) => describeSentiment(value))
  assert.equal(new Set(labels.map((l) => l.label)).size, 6)
  assert.equal(new Set(labels.slice(0, 5).map((l) => l.icon)).size, 5)
  const uncertain = describeSentiment("uncertain")
  assert.equal(uncertain.label, "Uncertain")
  assert.notEqual(uncertain.label, describeSentiment("neutral").label)
  assert.match(uncertain.explanation, /not the same as neutral/)
  const abstained = describeSentiment("insufficient_evidence")
  assert.equal(abstained.label, "Not enough evidence")
  assert.equal(abstained.inconclusive, true)
  assert.match(abstained.explanation, /not the same as neutral/)
  assert.deepEqual(["positive", "negative", "neutral", "mixed"].map((value) => describeSentiment(value).inconclusive), [false, false, false, false])
})

test("a missing or unrecognised sentiment is shown as unavailable or as received, never mapped to a label", () => {
  assert.equal(describeSentiment(null).label, "Not available")
  assert.equal(describeSentiment(undefined).icon, "unknown")
  assert.equal(describeSentiment("ecstatic").label, "Unrecognised (ecstatic)")
})

test("confidence is 'Not available' when absent (and the band is ignored), never zero, and shown as returned otherwise", () => {
  assert.equal(describeConfidence(null), "Not available")
  assert.equal(describeConfidence(undefined), "Not available")
  assert.equal(describeConfidence(null, "high"), "Not available") // a band without a number is not shown
  assert.ok(!/^0/.test(describeConfidence(null)))
  assert.equal(describeConfidence(0), "0 (as returned by the analysis)")
  assert.equal(describeConfidence(0.82), "0.82 (as returned by the analysis)")
  assert.equal(describeConfidence(0.82, "unavailable"), "0.82 (as returned by the analysis)")
  assert.equal(describeConfidence(0.82, "high"), "0.82 (as returned by the analysis), band: high")
})

test("the required messages are word for word as specified, and the backend's copies of the shared ones are identical", () => {
  assert.equal(PREFERENCE_NOTICE, "This is an unconfirmed interpretation of your text.")
  assert.equal(ABSTAIN_MESSAGE, "There is not enough reliable financial context to interpret this text.")
  assert.equal(UNRELATED_MESSAGE, "This text does not contain enough personal-finance context for a financial insight.")
  assert.equal(FALLBACK_MESSAGE, "The validated sentiment model was unavailable. The result uses the rules baseline.")
  assert.equal(NO_TEXT_MESSAGE, "No sentiment is inferred.")
  assert.equal(INFORMATIONAL_NOTICE, "Sentiment analysis is informational only. It does not change your risk profile, portfolio, recommendation, or compliance decision.")
  for (const message of [ABSTAIN_MESSAGE, UNRELATED_MESSAGE, UNSUPPORTED_LANGUAGE_MESSAGE]) assert.ok(BACKEND.includes(message), message) // the backend's own caveat says the same thing
  assert.ok(read("../backend/wealthpilot/core/personalized_insight.py").includes(FALLBACK_MESSAGE))
})

const READING = { status: "analysed", abstained: false, abstain_reason: null, interpretation_state: "valid", fallback_used: false }

test("a reading is presented as exactly one of: no text, abstained, weak, valid; the fallback flag is independent", () => {
  assert.deepEqual(describeReadingStatus(READING), { kind: "valid", label: "Valid interpretation", message: describeReadingStatus(READING).message, fallback: false })
  assert.match(describeReadingStatus(READING).message, /does not make the method validated/)
  assert.equal(describeReadingStatus({ ...READING, interpretation_state: "weak" }).kind, "weak")
  assert.equal(describeReadingStatus({ ...READING, interpretation_state: "something-new" }).kind, "weak") // an unknown state is never promoted to valid
  const none = describeReadingStatus({ ...READING, status: "unavailable", interpretation_state: "unavailable" })
  assert.deepEqual([none.kind, none.message], ["no_text", NO_TEXT_MESSAGE])
  const fallback = describeReadingStatus({ ...READING, fallback_used: true })
  assert.deepEqual([fallback.kind, fallback.fallback], ["valid", true])
  assert.equal(describeReadingStatus({ ...READING, interpretation_state: "weak", fallback_used: true }).fallback, true)
})

test("every backend abstain reason is presented as an abstention with a stated message, and unrelated / unsupported language have their own", () => {
  const reasons = [...(/^ABSTAIN_REASONS\s*=\s*\(([^)]*)\)/m.exec(BACKEND)?.[1] ?? "").matchAll(/"([a-z_]+)"/g)].map((m) => m[1])
  assert.ok(reasons.length >= 7)
  for (const reason of reasons) {
    const status = describeReadingStatus({ ...READING, abstained: true, abstain_reason: reason, interpretation_state: "abstained" })
    assert.equal(status.kind, "abstained", reason)
    assert.ok(status.message.length > 20, reason)
  }
  const message = (reason: string | null): string => describeReadingStatus({ ...READING, abstained: true, abstain_reason: reason, interpretation_state: "abstained" }).message
  assert.equal(message("unrelated_text"), UNRELATED_MESSAGE)
  assert.equal(message("unsupported_language"), UNSUPPORTED_LANGUAGE_MESSAGE)
  for (const generic of ["too_short", "low_quality_text", "ambiguous_context", "no_usable_evidence", null]) assert.equal(message(generic), ABSTAIN_MESSAGE, String(generic))
})

test("the method, validation and relevance wording never promotes the rules baseline", () => {
  assert.match(methodLabel("rules_baseline"), /not a trained model/)
  assert.match(validationLabel("UNVALIDATED_BASELINE"), /no accuracy has been measured/)
  assert.equal(methodLabel("brand_new"), "brand new")
  assert.match(relevanceLabel("unrelated"), /something other than personal finance/)
  assert.match(relevanceLabel(null), /Not assessed/)
})

test("tone, topic and preference codes get readable labels, and unknown codes fall back to readable text", () => {
  assert.equal(toneLabel("concerned"), "Concerned")
  assert.equal(topicLabel("investment_risk"), "Investing and risk")
  assert.equal(preferenceLabel("capital_preservation"), "Keeping capital safe")
  assert.equal(topicLabel("new_topic_code"), "new topic code")
})

test("the labels cover exactly the backend's controlled taxonomies", () => {
  const taxonomy = (name: string): string[] => {
    const match = new RegExp(`^${name}\\s*=\\s*\\(([^)]*)\\)`, "m").exec(BACKEND)
    assert.ok(match, `${name} not found`)
    return [...match[1].matchAll(/"([a-z_]+)"/g)].map((m) => m[1])
  }
  for (const code of taxonomy("SENTIMENTS")) assert.notEqual(describeSentiment(code).icon, "unknown", code)
  for (const code of taxonomy("EMOTIONS")) assert.notEqual(toneLabel(code), code.replace(/_/g, " "), code)
  for (const code of taxonomy("TOPICS")) assert.notEqual(topicLabel(code), code.replace(/_/g, " "), code)
  for (const code of taxonomy("PREFERENCES")) assert.notEqual(preferenceLabel(code), code.replace(/_/g, " "), code)
})

// ------------------------------------------------------------------ privacy and honesty boundaries in the source

const CARD_FILES = [
  "src/components/financial-health/behaviour-sentiment.tsx",
  "src/components/financial-health/behaviour-sentiment-view.tsx",
  "src/components/financial-health/behaviour-summary-card.tsx",
  "src/components/financial-health/sentiment-input-panel.tsx",
  "src/components/financial-health/sentiment-results-panel.tsx",
  "src/components/financial-health/risk-assessment-panel.tsx",
  "src/pages/financial-behaviour-page.tsx",
  "src/hooks/use-personalized-insight.ts",
  "src/lib/user-text-input.ts",
  "src/lib/behaviour-summary.ts",
]

test("the card never touches browser storage, cookies, the URL, the console, beacons or env flags", () => {
  const forbidden = /localStorage|sessionStorage|indexedDB|document\.cookie|location\.(search|hash|href)|history\.(push|replace)State|console\.|sendBeacon|navigator\.|import\.meta\.env|window\.name/
  for (const file of CARD_FILES) assert.doesNotMatch(read(file), forbidden, file)
})

test("the card shows no mock or hard-coded result and does no financial arithmetic", () => {
  for (const file of CARD_FILES) {
    const source = read(file)
    assert.doesNotMatch(source, /\bmock\b|\bfake\b|\bsample(Data|Response)\b|lorem|placeholderData|initialData/i, file)
    assert.doesNotMatch(source, /\.reduce\(|toFixed\(|Math\.(round|floor|ceil|sum|pow)|parseFloat\(/, file)
  }
})

test("the query is not retained: no cache time, no staleness, no retry, text only in the in-memory key", () => {
  const hook = read("src/hooks/use-personalized-insight.ts")
  assert.match(hook, /gcTime:\s*0/)
  assert.match(hook, /staleTime:\s*0/)
  assert.match(hook, /retry:\s*false/)
  assert.match(hook, /queryKey:\s*\["personalized-insight",\s*profileId,\s*text\]/)
  assert.doesNotMatch(hook, /persist|storage|placeholderData|keepPreviousData/i)
})

test("the API call uses the existing route and sends exactly the schema's one optional field in the body", () => {
  const client = read("src/lib/api-client.ts")
  const call = /createPersonalizedInsight:[\s\S]*?\n {2}\),?\n|createPersonalizedInsight:[\s\S]*?\}\),/.exec(client)
  assert.ok(call, "createPersonalizedInsight not found")
  assert.match(call[0], /`\/api\/profiles\/\$\{profileId\}\/personalized-insights`/)
  assert.match(call[0], /method:\s*"POST"/)
  assert.match(call[0], /body:\s*JSON\.stringify\(\{ text \}\)/)
  assert.doesNotMatch(call[0], /\?text=|URLSearchParams|searchParams/) // the text never travels in a URL
  assert.match(call[0], /Schemas\["PersonalizedInsightResponse"\]/)
})

test("the page keys the card by profile so switching profile discards the typed text and the response", () => {
  assert.match(read("src/pages/financial-behaviour-page.tsx"), /<FinancialBehaviourReal key=\{profileId\} profileId=\{profileId\}/)
  assert.match(read("src/components/financial-health/financial-behaviour-real.tsx"), /<BehaviourSentimentCard key=\{profileId\} profileId=\{profileId\}/)
})

// ------------------------------------------------------------------ the method and the trained model (ADR-052)

const METHOD = { status: "analysed", method: "rules_baseline", validation_status: "UNVALIDATED_BASELINE", fallback_used: false, abstained: false }

test("the required method wording is exact", () => {
  assert.equal(VALIDATED_MODEL_LABEL, "Validated model analysis")
  assert.equal(RULES_FALLBACK_LABEL, "Rules baseline fallback")
  assert.equal(MODEL_UNAVAILABLE_LABEL, "Model unavailable")
  assert.equal(CONFIDENCE_NOT_AVAILABLE, "Confidence not available")
  assert.equal(INTERPRETATION_NOTICE, "This interpretation is informational only and does not change your risk profile, portfolio, recommendation, or compliance decision.")
  assert.ok(BACKEND.includes(MODEL_UNAVAILABLE_MESSAGE)) // the backend's own caveat says the same thing
})

test("the method is derived only from the backend's fields, and a model that is not validated is never called validated", () => {
  assert.deepEqual(describeMethodUsed(METHOD), { kind: "rules_baseline", label: "Rules baseline", fallback: false })
  assert.equal(describeMethodUsed({ ...METHOD, status: "unavailable", method: "unavailable" }).kind, "no_text")
  assert.deepEqual(describeMethodUsed({ ...METHOD, method: "hybrid", validation_status: "validated" }), { kind: "validated_model", label: VALIDATED_MODEL_LABEL, fallback: false })
  assert.equal(describeMethodUsed({ ...METHOD, method: "trained_model", validation_status: "validated" }).kind, "validated_model")
  for (const status of ["unvalidated", "UNVALIDATED_BASELINE", "", "Validated"]) {
    const used = describeMethodUsed({ ...METHOD, method: "hybrid", validation_status: status })
    assert.equal(used.kind, "unvalidated_model", status)
    assert.ok(used.label !== VALIDATED_MODEL_LABEL, status)
  }
  assert.deepEqual(describeMethodUsed({ ...METHOD, fallback_used: true }), { kind: "rules_fallback", label: RULES_FALLBACK_LABEL, fallback: true })
  assert.deepEqual(describeMethodUsed({ ...METHOD, fallback_used: true, abstained: true }), { kind: "model_unavailable", label: MODEL_UNAVAILABLE_LABEL, fallback: true })
  assert.equal(describeMethodUsed({ ...METHOD, method: "hybrid", validation_status: "validated", fallback_used: true }).kind, "rules_fallback") // a fallback is never presented as a model answer
})

test("every fallback reason the backend can send has plain wording", () => {
  const reasons = [...(/^FALLBACK_REASONS\s*=\s*\(([^)]*)\)/m.exec(BACKEND)?.[1] ?? "").matchAll(/"([a-z_]+)"/g)].map((m) => m[1])
  assert.ok(reasons.length >= 13)
  for (const reason of reasons) assert.notEqual(fallbackReasonLabel(reason), reason.replace(/_/g, " "), reason)
  assert.equal(fallbackReasonLabel(null), "not applicable")
  assert.equal(fallbackReasonLabel("brand_new_code"), "brand new code")
})

test("class probabilities are shown in the fixed class order exactly as received, never computed, and intensity is 'Not available' without a value", () => {
  assert.deepEqual(orderedProbabilities({ neutral: 0.08, positive: 0.04, negative: 0.88 }), [
    { code: "positive", label: "Positive", value: 0.04 },
    { code: "negative", label: "Negative", value: 0.88 },
    { code: "neutral", label: "Neutral", value: 0.08 },
  ])
  assert.deepEqual(orderedProbabilities(null), [])
  assert.deepEqual(orderedProbabilities({ negative: 1 }).map((p) => p.code), ["negative"]) // a class the backend did not send is not invented
  assert.match(describeIntensity(null), /^Not available/)
  assert.ok(!/^0/.test(describeIntensity(undefined)))
  assert.match(describeIntensity(-0.72), /^-0\.72 /)
  assert.match(describeIntensity(0), /^0 /) // a real zero from a validated head is shown as zero
  assert.equal(calibrationLabel("calibrated"), "calibrated")
  assert.match(calibrationLabel("uncalibrated"), /raw output/)
})

test("the panel never rounds, sums or normalises a model number", () => {
  const source = read("src/components/financial-health/sentiment-results-panel.tsx") + read("src/lib/user-text-input.ts")
  assert.doesNotMatch(source, /toFixed\(|Math\.(round|floor|ceil|sum|pow|abs)|\.reduce\(|parseFloat\(|\* ?100/)
})
