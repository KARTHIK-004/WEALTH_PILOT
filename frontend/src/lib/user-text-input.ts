/**
 * Input rules and input-state transitions for the optional text of the "Financial behaviour & sentiment" card (ADR-043, ADR-050), plus the plain-language wording of the backend's
 * interpretation states.
 *
 * Pure TypeScript with no React and no DOM, so it is unit-tested with Node's built-in test runner (`npm test`). It never calculates a financial figure and never infers
 * sentiment: it only decides whether a string may be SENT to the backend, what the input box should do next, and how a controlled backend value is worded. The backend
 * (`core/user_text_sentiment.py`) stays the authority and re-checks everything; the rules here are deliberately NEVER LOOSER than the backend's, so a text this module accepts cannot be
 * rejected for length or control characters:
 *
 *  - the limit counts the characters as typed (Unicode code points, like Python's `len`), while the backend counts after collapsing runs of whitespace, so the backend limit is never smaller;
 *  - the forbidden control-character class is identical to the backend's `_CONTROL` pattern (tab, line feed and carriage return are allowed there and are not control characters here either).
 *
 * `tests/` cross-checks these constants against the backend source so they cannot silently drift.
 */

export const MAX_USER_TEXT_CHARS = 1000

/** Same character class as the backend's `_CONTROL`: C0 controls except tab, line feed, carriage return (and form feed is rejected there too), plus DEL. */
// eslint-disable-next-line no-control-regex -- intentional: this is the backend's own forbidden-character class
export const CONTROL_CHARACTERS = /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/

export type TextValidation = { ok: true; text: string | null } | { ok: false; reason: string }

/** Characters as the backend counts them: Unicode code points, not UTF-16 units (an emoji is one). */
export function countCharacters(text: string): number {
  return Array.from(text).length
}

export function charactersRemaining(text: string): number {
  return MAX_USER_TEXT_CHARS - countCharacters(text)
}

/**
 * `ok: true, text: null` means "no text": blank or whitespace-only input is NOT a neutral statement, it is sent as no text at all, and the backend then reports the reading as unavailable.
 * The reasons are generic and never contain the text.
 */
export function validateUserText(raw: string): TextValidation {
  if (CONTROL_CHARACTERS.test(raw)) {
    return { ok: false, reason: "The text contains characters that cannot be analysed (for example hidden control characters). Please remove them." }
  }
  if (countCharacters(raw) > MAX_USER_TEXT_CHARS) {
    const over = countCharacters(raw) - MAX_USER_TEXT_CHARS
    return { ok: false, reason: `The text is ${over} character${over === 1 ? "" : "s"} over the ${MAX_USER_TEXT_CHARS}-character limit. Please shorten it.` }
  }
  const trimmed = raw.trim()
  return { ok: true, text: trimmed === "" ? null : trimmed }
}

/** `draft` is what is in the box; `submitted` is the text the CURRENT results were requested for (`null` = records only, no text). */
export interface InputState {
  draft: string
  submitted: string | null
}

export const INITIAL_INPUT_STATE: InputState = { draft: "", submitted: null }

export function editDraft(state: InputState, value: string): InputState {
  return { ...state, draft: value }
}

export interface SubmitOutcome {
  state: InputState
  /** True when the same text is submitted again: the query key does not change, so the caller must refetch explicitly. */
  refetch: boolean
  /** True when the draft was not accepted (pending request, or invalid); nothing is sent. */
  rejected: boolean
}

/** Pressing Analyse / Enter. A second submit while a request is pending, or an invalid draft, is a no-op, so a request is never duplicated and an invalid text is never sent. */
export function submitDraft(state: InputState, pending: boolean): SubmitOutcome {
  if (pending) return { state, refetch: false, rejected: true }
  const checked = validateUserText(state.draft)
  if (!checked.ok) return { state, refetch: false, rejected: true }
  return { state: { ...state, submitted: checked.text }, refetch: checked.text === state.submitted, rejected: false }
}

/** Clear removes the draft AND forgets the submitted text, so the results fall back to the records-only view. */
export function clearAll(): InputState {
  return INITIAL_INPUT_STATE
}

/**
 * True when the box no longer matches the text the visible results were produced for (typing after a submit, or text typed but not yet analysed). The view then says so, so
 * results are never presented as describing words they were not computed from. An invalid draft is also "not yet analysed".
 */
export function resultsAreStale(state: InputState): boolean {
  const checked = validateUserText(state.draft)
  const draftText = checked.ok ? checked.text : state.draft
  return draftText !== state.submitted
}

/** Ctrl+Enter or Cmd+Enter submits from inside the text area; a plain Enter must stay a line break. Pure, so it is unit-tested without a DOM. */
export function isSubmitShortcut(event: { key: string; ctrlKey: boolean; metaKey: boolean; shiftKey?: boolean; altKey?: boolean; isComposing?: boolean }): boolean {
  return event.key === "Enter" && (event.ctrlKey || event.metaKey) && !event.shiftKey && !event.altKey && !event.isComposing
}

/** A request may be started from the current state: no request pending and the draft is valid. */
export function canSubmit(state: InputState, pending: boolean): boolean {
  return !pending && validateUserText(state.draft).ok
}

// ------------------------------------------------------------------ the messages the page must show, word for word (ADR-050)

/** Shown with every reading: the interpretation never reaches the risk profile, the portfolio, the recommendation or the compliance decision. */
export const INFORMATIONAL_NOTICE =
  "Sentiment analysis is informational only. It does not change your risk profile, portfolio, recommendation, or compliance decision."
/** Shown with every possible preference. */
export const PREFERENCE_NOTICE = "This is an unconfirmed interpretation of your text."
/** The text could not be interpreted reliably (too short, vague, ambiguous, or nothing usable in it). */
export const ABSTAIN_MESSAGE = "There is not enough reliable financial context to interpret this text."
/** The text is about something other than personal finance. */
export const UNRELATED_MESSAGE = "This text does not contain enough personal-finance context for a financial insight."
/** The text is not in a language the analysis supports. */
export const UNSUPPORTED_LANGUAGE_MESSAGE = "The text does not appear to be in English, the only language this analysis supports, so it was not interpreted."
/** A model reading was attempted and failed; the rules baseline answered. */
export const FALLBACK_MESSAGE = "The validated sentiment model was unavailable. The result uses the rules baseline."
/** No text was provided. */
export const NO_TEXT_MESSAGE = "No sentiment is inferred."
/** A trained model is switched on but cannot be used and fallback to the rules baseline is switched off. */
export const MODEL_UNAVAILABLE_MESSAGE = "The sentiment model was unavailable and fallback to the rules baseline is switched off, so this text was not interpreted."

/** The method of a reading, in the words the page must use (ADR-052). */
export const VALIDATED_MODEL_LABEL = "Validated model analysis"
export const RULES_FALLBACK_LABEL = "Rules baseline fallback"
export const MODEL_UNAVAILABLE_LABEL = "Model unavailable"
export const CONFIDENCE_NOT_AVAILABLE = "Confidence not available"
/** Said once more beside the method, whatever it is. */
export const INTERPRETATION_NOTICE =
  "This interpretation is informational only and does not change your risk profile, portfolio, recommendation, or compliance decision."

export interface SentimentPresentation {
  /** Shown as text next to the icon, so meaning never depends on colour alone. */
  label: string
  explanation: string
  icon: "positive" | "negative" | "neutral" | "mixed" | "uncertain" | "unknown"
  /** True when the reading did not find a tone (`uncertain`, `insufficient_evidence`) or the value is not one the UI knows. The page shows these differently from a reading that found one, and never as neutral. */
  inconclusive: boolean
}

/** Readable wording for the backend's controlled sentiment labels. `uncertain` and `insufficient_evidence` are never presented as `neutral`; an unrecognised value is shown as received, not mapped to anything. */
export function describeSentiment(value: string | null | undefined): SentimentPresentation {
  switch (value) {
    case "positive":
      return { label: "Positive", explanation: "Your wording leans positive about your finances.", icon: "positive", inconclusive: false }
    case "negative":
      return { label: "Negative", explanation: "Your wording leans negative or worried about your finances.", icon: "negative", inconclusive: false }
    case "neutral":
      return { label: "Neutral", explanation: "Finance topics or wishes were named, but no positive or negative wording was found.", icon: "neutral", inconclusive: false }
    case "mixed":
      return { label: "Mixed", explanation: "Both positive and negative wording was found.", icon: "mixed", inconclusive: false }
    case "uncertain":
      return {
        label: "Uncertain",
        explanation: "Something was said, but it cannot be read reliably (for example only a negated expression such as 'not worried'). This is not the same as neutral.",
        icon: "uncertain",
        inconclusive: true,
      }
    case "insufficient_evidence":
      return { label: "Not enough evidence", explanation: "The text did not give enough reliable evidence to read a sentiment. This is not the same as neutral.", icon: "uncertain", inconclusive: true }
    default:
      return { label: value ? `Unrecognised (${value})` : "Not available", explanation: "No reading is available for this text.", icon: "unknown", inconclusive: true }
  }
}

const TONE_LABELS: Record<string, string> = { concerned: "Concerned", hopeful: "Hopeful", frustrated: "Frustrated", calm: "Calm", neutral: "Neutral", unknown: "Unknown" }
const TOPIC_LABELS: Record<string, string> = {
  investment_risk: "Investing and risk",
  saving: "Saving",
  debt: "Debt and loans",
  goals: "Goals",
  liquidity: "Cash and access",
  market: "The market",
  retirement: "Retirement",
  emergency_fund: "Emergency fund",
}
const PREFERENCE_LABELS: Record<string, string> = {
  capital_preservation: "Keeping capital safe",
  growth_seeking: "Seeking growth",
  liquidity_access: "Keeping money accessible",
  debt_reduction: "Reducing debt",
  balanced_growth: "Balancing growth and safety",
}
const RELEVANCE_LABELS: Record<string, string> = {
  relevant: "Relevant: the text is about your personal finances",
  unrelated: "Unrelated: the text is about something other than personal finance",
  ambiguous: "Ambiguous: not enough to tell whether the text is about your finances",
}
const METHOD_LABELS: Record<string, string> = {
  rules_baseline: "Rules baseline (a small fixed set of rules, not a trained model)",
  trained_model: "Trained model",
  hybrid: "Model reading combined with the rules baseline",
  unavailable: "Not run (no text)",
}
const VALIDATION_LABELS: Record<string, string> = {
  UNVALIDATED_BASELINE: "Unvalidated baseline: no accuracy has been measured for these rules",
}

function fallbackLabel(code: string): string {
  return code.replace(/_/g, " ")
}

export const toneLabel = (code: string): string => TONE_LABELS[code] ?? fallbackLabel(code)
export const topicLabel = (code: string): string => TOPIC_LABELS[code] ?? fallbackLabel(code)
export const preferenceLabel = (code: string): string => PREFERENCE_LABELS[code] ?? fallbackLabel(code)
export const relevanceLabel = (value: string | null | undefined): string => (value ? (RELEVANCE_LABELS[value] ?? fallbackLabel(value)) : "Not assessed (no text)")
export const methodLabel = (value: string): string => METHOD_LABELS[value] ?? fallbackLabel(value)
export const validationLabel = (value: string): string => VALIDATION_LABELS[value] ?? fallbackLabel(value)

/**
 * The confidence line: shown only as the backend provides it. A missing confidence is "Not available", never 0, and a number is shown exactly as returned (with the band the backend
 * assigned, when it assigned one).
 */
export function describeConfidence(confidence: number | null | undefined, band?: string | null): string {
  if (confidence === null || confidence === undefined) return "Not available"
  return `${confidence} (as returned by the analysis)${band && band !== "unavailable" ? `, band: ${band}` : ""}`
}

/** What the page says about a missing confidence, beside "Not available". */
export const NO_CONFIDENCE_EXPLANATION = "These fixed rules are not calibrated, so no confidence level is claimed."

export type ReadingKind = "no_text" | "abstained" | "weak" | "valid"

export interface ReadingStatus {
  kind: ReadingKind
  /** A short label shown as text (never colour alone). */
  label: string
  message: string
  /** True when a model reading was attempted and failed, so the rules baseline answered. Independent of `kind`. */
  fallback: boolean
}

/** The structural part of the backend's `UserSentimentOut` that decides how the reading is presented. */
export interface ReadingLike {
  status: string
  abstained: boolean
  abstain_reason: string | null
  interpretation_state: string
  fallback_used: boolean
}

/**
 * Which of the five presentations a reading gets: valid interpretation, weak interpretation, abstained, unavailable analysis (no text), plus the fallback flag. Decided only from the
 * backend's own fields; an abstention is never shown as a sentiment, and a weak reading is never shown as a valid one.
 */
export function describeReadingStatus(reading: ReadingLike): ReadingStatus {
  const fallback = reading.fallback_used
  if (reading.status === "unavailable" || reading.interpretation_state === "unavailable") {
    return { kind: "no_text", label: "No text", message: NO_TEXT_MESSAGE, fallback }
  }
  if (reading.abstained || reading.interpretation_state === "abstained") {
    const message =
      reading.abstain_reason === "unrelated_text"
        ? UNRELATED_MESSAGE
        : reading.abstain_reason === "unsupported_language"
          ? UNSUPPORTED_LANGUAGE_MESSAGE
          : reading.abstain_reason === "model_confidence_below_threshold"
            ? "The sentiment model was not confident enough to interpret this text."
            : reading.abstain_reason === "model_unavailable"
              ? MODEL_UNAVAILABLE_MESSAGE
              : ABSTAIN_MESSAGE
    return { kind: "abstained", label: "Not interpreted", message, fallback }
  }
  if (reading.interpretation_state !== "valid") {
    // "weak", and any state this UI does not know: never presented as a valid interpretation
    return { kind: "weak", label: "Weak interpretation", message: "The text gave little explicit evidence, so treat this reading with extra caution.", fallback }
  }
  return {
    kind: "valid",
    label: "Valid interpretation",
    message: "The text gave enough explicit evidence for this reading. That does not make the method validated.",
    fallback,
  }
}

// ------------------------------------------------------------------ the method and the trained model (ADR-052)

/** Why a configured trained model did not answer: the backend's own fixed codes, in plain words. */
const FALLBACK_REASON_LABELS: Record<string, string> = {
  dependencies_missing: "the model software is not installed",
  artifact_missing: "no model files were found",
  artifact_corrupt: "the model files failed an integrity check",
  artifact_incompatible: "the model files are not compatible with this application",
  path_not_allowed: "the model location is not an approved one",
  not_validated: "the model has not been validated",
  version_mismatch: "the model version does not match the configuration",
  load_failed: "the model could not be loaded",
  inference_failed: "the model failed while reading this text",
  timeout: "the model took too long",
  invalid_output: "the model returned an invalid result",
  invalid_configuration: "the model configuration is invalid",
  below_threshold: "the model was not confident enough",
}
export const fallbackReasonLabel = (code: string | null | undefined): string => (code ? (FALLBACK_REASON_LABELS[code] ?? code.replace(/_/g, " ")) : "not applicable")

export type MethodKind = "no_text" | "validated_model" | "unvalidated_model" | "rules_baseline" | "rules_fallback" | "model_unavailable"

export interface MethodUsed {
  kind: MethodKind
  /** The words the page shows for the method. */
  label: string
  /** True when the reading did not come from the validated model although one is configured. */
  fallback: boolean
}

/** The structural part of the backend's `UserSentimentOut` that decides which method is described. */
export interface MethodLike {
  status: string
  method: string
  validation_status: string
  fallback_used: boolean
  abstained: boolean
}

/**
 * Which method produced the reading, from the backend's own fields only: a validated model, the rules baseline (the default, no model configured), the rules baseline as a FALLBACK (a
 * model is configured but could not answer: never hidden), or "Model unavailable" (it could not answer and fallback is off, so nothing was interpreted). A model that is not validated
 * is never called validated.
 */
export function describeMethodUsed(reading: MethodLike): MethodUsed {
  if (reading.status === "unavailable") return { kind: "no_text", label: "No text", fallback: false }
  if (reading.fallback_used && reading.abstained) return { kind: "model_unavailable", label: MODEL_UNAVAILABLE_LABEL, fallback: true }
  if (reading.fallback_used) return { kind: "rules_fallback", label: RULES_FALLBACK_LABEL, fallback: true }
  if (reading.method === "hybrid" || reading.method === "trained_model") {
    return reading.validation_status === "validated"
      ? { kind: "validated_model", label: VALIDATED_MODEL_LABEL, fallback: false }
      : { kind: "unvalidated_model", label: "Model analysis (not validated)", fallback: false }
  }
  return { kind: "rules_baseline", label: "Rules baseline", fallback: false }
}

const CALIBRATION_LABELS: Record<string, string> = {
  calibrated: "calibrated",
  uncalibrated: "not calibrated: the probabilities are the model's raw output",
  not_applicable: "no model probabilities",
}
export const calibrationLabel = (value: string): string => CALIBRATION_LABELS[value] ?? value.replace(/_/g, " ")

/** The model's class probabilities as received, in the fixed order of the classes. Never rounded, summed or normalised here. */
export function orderedProbabilities(probabilities: Record<string, number> | null | undefined): { code: string; label: string; value: number }[] {
  if (!probabilities) return []
  return ["positive", "negative", "neutral"].filter((code) => code in probabilities).map((code) => ({ code, label: code[0].toUpperCase() + code.slice(1), value: probabilities[code] }))
}

/** The intensity line: "Not available" unless the backend returned a value from a validated regression head; a number is shown exactly as returned. */
export function describeIntensity(value: number | null | undefined): string {
  return value === null || value === undefined ? "Not available: no validated intensity model" : `${value} (from -1, most negative, to +1, most positive)`
}
