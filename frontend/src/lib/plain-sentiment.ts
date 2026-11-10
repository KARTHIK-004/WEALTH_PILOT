/**
 * The reading of the user's optional note in SIMPLE ENGLISH. Pure TypeScript with no React or DOM, unit-tested by `npm test`.
 *
 * It only RESTATES what the backend's rules-baseline reading (`user_text_rules_v1`) returned, in everyday words: it never decides a sentiment, never turns an uncertain, weak or abstained reading
 * into a feeling, and never shows a confidence or intensity (both are unavailable and stay unavailable). A hypothetical, quoted, third-person or past-only note comes back from the backend as an
 * abstention or a "weak" reading, and is described as "does not clearly show a current feeling" (or "not enough clear information"), never as the writer's current feeling.
 */
import type { components } from "@/types/api"

export type UserSentiment = components["schemas"]["UserSentimentOut"]
export type ModelState = components["schemas"]["SentimentModelStatusOut"]["state"]

export type PlainKind = "none" | "positive" | "negative" | "neutral" | "mixed" | "uncertain" | "abstained"

export interface PlainSentiment {
  kind: PlainKind
  /** One sentence in everyday words. */
  headline: string
  /** Short, always-true explanations that belong under the headline. */
  notes: string[]
}

export const OPTIONAL_NOTE_STATEMENT = "Your written note is optional. This section describes how your words read; it is not a fact about you."
export const NO_NOTE_HEADLINE = "You have not written a note, so there is no reading to show."
export const BASED_ON_WORDS_NOTE = "This is based only on the words you chose to write."
export const NO_EFFECT_NOTE = "This does not change your risk profile, allocation or recommendations."
export const MODEL_DISABLED_NOTE = "The model-based sentiment feature is currently disabled."
export const UNAVAILABLE_VALUES_NOTE = "Confidence and intensity are not available."

export const HEADLINES: Record<Exclude<PlainKind, "none">, string> = {
  positive: "Your note sounds generally positive.",
  negative: "Your note sounds concerned or negative.",
  neutral: "Your note sounds neutral.",
  mixed: "Your note sounds mixed: it has both positive and concerned wording.",
  uncertain: "Your note does not clearly show a current feeling.",
  abstained: "There is not enough clear information to interpret this note.",
}

function kindOf(reading: UserSentiment): PlainKind {
  if (reading.status === "unavailable" || reading.sentiment === null) return "none"
  if (reading.abstained || reading.sentiment === "insufficient_evidence" || reading.interpretation_state === "abstained") return "abstained"
  // a "weak" reading (for example a hypothetical or past-only note) is not a current feeling, whatever label it carries
  if (reading.interpretation_state === "weak" || reading.sentiment === "uncertain") return "uncertain"
  return reading.sentiment
}

/** `modelState` is the backend's own model status (`disabled`, `ready`, `unavailable`) or undefined while it is not known: the "disabled" note is added only when the backend said so. */
export function plainSentiment(reading: UserSentiment, modelState?: ModelState): PlainSentiment {
  const kind = kindOf(reading)
  if (kind === "none") return { kind, headline: NO_NOTE_HEADLINE, notes: [] }
  const notes = [BASED_ON_WORDS_NOTE, NO_EFFECT_NOTE]
  if (modelState === "disabled") notes.push(MODEL_DISABLED_NOTE)
  if ((reading.confidence === null || reading.confidence === undefined) && (reading.sentiment_intensity === null || reading.sentiment_intensity === undefined)) notes.push(UNAVAILABLE_VALUES_NOTE)
  return { kind, headline: HEADLINES[kind], notes }
}
