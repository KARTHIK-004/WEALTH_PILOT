import type { components } from "@/types/api"

/**
 * Wording and state selection for the research-only pretrained-model panel (ADR-053, role slots from ADR-055). DISPLAY ONLY: every label, status, reason and score arrives from the backend; this file
 * maps those fixed codes to words and picks which banner to show. It never computes, compares or infers a sentiment, a confidence or an agreement, and it never turns an unavailable result into a
 * label.
 */
export type TransformerResearch = components["schemas"]["TransformerResearchOut"]
export type ResearchModelResult = components["schemas"]["ResearchModelResultOut"]
type Comparison = components["schemas"]["ResearchComparisonOut"]

export const RESEARCH_TITLE = "Experimental pretrained models (research only)"
export const RESEARCH_INTRO =
  "A pretrained language-model classifier can be compared with the rules-based reading above. This is a research feature: it explains nothing about you on its own and changes nothing about your risk profile or recommendations."
export const NO_CONFIDENCE_TEXT =
  "Confidence is not available. The scores shown are each model's own raw output; they are not calibrated, are not a probability that the label is correct, and cannot be compared between models."
export const AUTHORITY_TEXT = "Your stored risk assessment remains the authoritative record. This reading is context only."

const LABELS: Record<string, string> = {
  positive: "Positive",
  negative: "Negative",
  neutral: "Neutral",
  mixed: "Mixed",
  uncertain: "Uncertain",
  insufficient_evidence: "Not enough evidence",
}

/** A label for display; a value the UI does not know is shown as unavailable, never as neutral. */
export function labelText(label: string | null | undefined): string {
  if (label === null || label === undefined) return "No reading"
  return LABELS[label] ?? "Unavailable"
}

const REASONS: Record<string, string> = {
  disabled: "The research models are switched off.",
  licence_not_verified: "Not permitted to run: its licence has not been verified for this project.",
  format_not_allowed: "Not permitted to run: its weights are not published in the safe file format this project requires.",
  dependencies_missing: "The required software packages are not installed.",
  weights_missing: "The model files have not been placed on this server.",
  manifest_invalid: "The model files are not accompanied by a valid record of what they are.",
  revision_mismatch: "The model files are not the exact version that was approved.",
  artifact_corrupt: "The model files failed their integrity check.",
  label_unsupported: "The model uses labels this system does not support.",
  load_failed: "The model could not be loaded.",
  timeout: "The model took too long to answer.",
  inference_failed: "The model could not read this text.",
  invalid_output: "The model returned an unusable answer.",
  invalid_configuration: "The research settings are incomplete.",
  input_not_eligible: "The text was not suitable for these models (for example too short, unrelated to money, or not in English).",
  loading: "The model is being prepared. Try again shortly.",
  internal_error: "The research model could not be used because of an unexpected problem. Your reading above is not affected.",
  no_candidate_approved: "No model has been approved for this role.",
  registration_pending: "A model has been approved for research, but it has not yet been registered for use.",
}

export function reasonText(reason: string | null | undefined): string {
  if (reason === null || reason === undefined) return "Unavailable."
  return REASONS[reason] ?? "Unavailable."
}

/** A slot with no registered candidate is not a failure: it is simply empty. */
export function isEmptySlot(model: ResearchModelResult): boolean {
  return model.availability === "unavailable" && (model.unavailable_reason === "no_candidate_approved" || model.unavailable_reason === "registration_pending")
}

const COMPARISON: Record<Comparison["status"], string> = {
  agreement: "The two models agree",
  disagreement: "The two models disagree",
  single_model: "One model answered",
  model_unavailable: "The model did not answer",
  one_model_unavailable: "Only one model answered",
  both_models_unavailable: "No model answered",
  no_model_configured: "No model is registered",
  uncertain: "The comparison is uncertain",
}

export function comparisonHeading(status: Comparison["status"]): string {
  return COMPARISON[status]
}

const UNCERTAINTY: Record<string, string> = {
  models_disagree: "The two models produced different labels, so no single sentiment is reported.",
  rules_disagree: "The model's label differs from the rules-based reading, so the result is shown as uncertain.",
  context_safeguard: "The wording (for example negation, a hypothetical, the past, or someone else's feelings) does not clearly show a current feeling, so the result is shown as uncertain.",
  transformers_unavailable: "The pretrained model did not answer, so the rules-based reading is shown instead.",
  one_model_unavailable: "Only one pretrained model answered, so the rules-based reading is shown instead.",
  input_not_eligible: "The text was not suitable for the pretrained model, so the rules-based reading is shown instead.",
  model_label_uncertain: "A model did not give a usable label, so the result is shown as uncertain.",
  no_model_registered: "No pretrained model is registered for research use, so only the rules-based reading is shown.",
}

export function uncertaintyText(reason: string | null | undefined): string | null {
  if (reason === null || reason === undefined) return null
  return UNCERTAINTY[reason] ?? "The result is uncertain."
}

export function rulesRelationText(relation: TransformerResearch["rules_relation"]): string {
  switch (relation) {
    case "agrees":
      return "The model and the rules-based reading agree. Agreement between two classifiers does not show that either is right."
    case "disagrees":
      return "The rules-based reading differs from the model."
    case "rules_abstained":
      return "The rules-based reading did not commit to a label, so there is nothing to compare with."
    default:
      return "No comparison with the rules-based reading was made."
  }
}

export type ResearchState =
  | "switched_off"
  | "not_run"
  | "no_model_registered"
  | "loading"
  | "models_unavailable"
  | "one_model_unavailable"
  | "models_disagree"
  | "models_agree"
  | "models_uncertain"
  | "single_agrees"
  | "single_differs"
  | "single_rules_abstained"

/** Which banner to show. Chosen only from the backend's own statuses. */
export function researchState(research: TransformerResearch): ResearchState {
  if (!research.enabled) return "switched_off"
  if (research.processing_metadata.input_eligible === false) return "not_run"
  if (research.models.some((m) => m.availability === "loading")) return "loading"
  switch (research.comparison.status) {
    case "no_model_configured":
      return "no_model_registered"
    case "model_unavailable":
    case "both_models_unavailable":
      return "models_unavailable"
    case "one_model_unavailable":
      return "one_model_unavailable"
    case "disagreement":
      return "models_disagree"
    case "uncertain":
      return "models_uncertain"
    case "single_model": {
      const relation = research.comparison.model_vs_rules[0]?.relation
      return relation === "agrees" ? "single_agrees" : relation === "disagrees" ? "single_differs" : "single_rules_abstained"
    }
    default:
      return "models_agree"
  }
}

export const STATE_BANNER: Record<ResearchState, { title: string; body: string }> = {
  switched_off: { title: "Research models are switched off", body: "Only the rules-based reading is in use. Nothing was sent to any model." },
  not_run: { title: "Not run for this text", body: "The text was not suitable for the pretrained model. The rules-based reading stands, and no model result is invented." },
  no_model_registered: { title: "No research model is registered", body: "Research is switched on, but no pretrained model is registered for use yet. Only the rules-based reading is shown." },
  loading: { title: "Model is being prepared", body: "The pretrained model is loading. The rules-based reading is shown meanwhile; try again shortly." },
  models_unavailable: { title: "Model unavailable", body: "The pretrained model could not answer. The rules-based reading is shown as the fallback." },
  one_model_unavailable: { title: "One model unavailable", body: "Only one pretrained model answered, so no comparison between models is possible. Its result is shown on its own; the rules-based reading is the fallback." },
  models_disagree: { title: "Model disagreement", body: "The two models produced different labels. Both results are shown and the combined result is uncertain." },
  models_uncertain: { title: "Uncertain comparison", body: "At least one model did not give a usable label." },
  models_agree: { title: "Models agree", body: "Both models produced the same label. This is model output, not a human-checked finding." },
  single_agrees: { title: "Model and rules agree", body: "One pretrained model answered and its label matches the rules-based reading. This is model output, not a human-checked finding." },
  single_differs: { title: "Model and rules differ", body: "One pretrained model answered and its label differs from the rules-based reading, so the combined result is uncertain. Both readings are shown." },
  single_rules_abstained: { title: "Model answered; rules did not commit", body: "One pretrained model answered. The rules-based reading did not commit to a label, so there is nothing to compare with." },
}

/** Raw model scores for display only, in the model's own label order, exactly as the backend sent them (already rounded there). Never rounded, summed or normalised here. */
export function scoreRows(scores: Record<string, number> | null | undefined): { label: string; value: string }[] {
  if (!scores) return []
  return Object.entries(scores).map(([label, value]) => ({ label, value: String(value) }))
}
