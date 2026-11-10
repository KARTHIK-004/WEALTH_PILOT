import { FlaskConical, Info } from "lucide-react"

import { TechnicalDetails } from "@/components/shell/technical-details"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  AUTHORITY_TEXT,
  NO_CONFIDENCE_TEXT,
  RESEARCH_INTRO,
  RESEARCH_TITLE,
  STATE_BANNER,
  comparisonHeading,
  isEmptySlot,
  labelText,
  reasonText,
  researchState,
  rulesRelationText,
  scoreRows,
  uncertaintyText,
  type ResearchModelResult,
  type TransformerResearch,
} from "@/lib/transformer-research"

function ModelCard({ model }: { model: ResearchModelResult }) {
  if (isEmptySlot(model)) {
    return (
      <Card size="sm" aria-label={`${model.display_name} result`} data-slot={model.slot} data-availability="empty">
        <CardHeader>
          <CardTitle className="flex flex-wrap items-center gap-2 text-sm">
            {model.display_name}
            <Badge variant="outline">No model registered</Badge>
          </CardTitle>
          <CardDescription className="text-xs">This role is empty. It is not a failure and nothing is substituted.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p className="text-muted-foreground">{reasonText(model.unavailable_reason)}</p>
        </CardContent>
      </Card>
    )
  }
  const available = model.availability === "available"
  const badge = available ? "Answered" : model.availability === "loading" ? "Loading" : "Unavailable"
  return (
    <Card size="sm" aria-label={`${model.display_name} result`} data-slot={model.slot} data-availability={model.availability}>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2 text-sm">
          {model.display_name}
          <Badge variant={available ? "secondary" : "outline"}>{badge}</Badge>
        </CardTitle>
        <CardDescription className="text-xs">Independent result. Not combined or averaged with any other model.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {available ? (
          <>
            <p>
              Label: <span className="font-medium">{labelText(model.normalized_label)}</span>
            </p>
            <TechnicalDetails
              title="Raw model scores (not a confidence)"
              items={[
                { label: "Original label", value: model.native_label },
                { label: "Score kind", value: model.probability_kind === "raw_softmax_uncalibrated" ? "raw, uncalibrated" : "not provided" },
                ...scoreRows(model.probabilities).map((row) => ({ label: `Score: ${row.label}`, value: row.value })),
                { label: "Revision", value: model.revision },
                { label: "Model", value: model.model_id },
              ]}
            />
          </>
        ) : (
          <>
            <p className="text-muted-foreground">No result. {reasonText(model.unavailable_reason)}</p>
            <TechnicalDetails
              items={[
                { label: "Reason code", value: model.unavailable_reason },
                { label: "Revision", value: model.revision },
                { label: "Model", value: model.model_id },
              ]}
            />
          </>
        )}
      </CardContent>
    </Card>
  )
}

/**
 * The research-only pretrained-model panel: A, the rules baseline; B, one card per role slot; C, the comparison and the combined, still experimental, reading. Pure markup from the backend's
 * `transformer_research` object (ADR-053, role slots ADR-055). It displays; it never computes a label, an agreement or a confidence, and it never shows an unavailable or empty slot as a result.
 */
export function TransformerResearchPanel({ research }: { research: TransformerResearch | null | undefined }) {
  if (!research) return null
  const state = researchState(research)
  const banner = STATE_BANNER[state]
  const reason = uncertaintyText(research.uncertainty_reason)
  const fellBack = research.overall_source === "rules_baseline_fallback"
  return (
    <section aria-label="Experimental pretrained model comparison" className="space-y-4 rounded-xl border border-dashed p-4" data-research-state={state}>
      <div className="flex items-start gap-3">
        <FlaskConical className="text-muted-foreground mt-0.5 size-5 shrink-0" aria-hidden="true" />
        <div className="space-y-1">
          <h3 className="text-sm font-medium">{RESEARCH_TITLE}</h3>
          <p className="text-muted-foreground text-sm">{RESEARCH_INTRO}</p>
        </div>
      </div>

      <ul className="space-y-1 text-sm" aria-label="Important notices">
        {research.notices.map((notice) => (
          <li key={notice} className="flex items-start gap-2">
            <Info className="text-muted-foreground mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <span>{notice}</span>
          </li>
        ))}
      </ul>

      <Alert role="status" aria-label={banner.title}>
        <Info aria-hidden="true" />
        <AlertTitle>{banner.title}</AlertTitle>
        <AlertDescription>{banner.body}</AlertDescription>
      </Alert>

      <div className="space-y-2" role="group" aria-label="Rules-based baseline">
        <h4 className="text-sm font-medium">A. Rules-based reading</h4>
        <p className="text-sm">
          {research.rules_baseline ? (
            <>
              Label: <span className="font-medium">{labelText(research.rules_baseline.label)}</span>. This is the method in use.
            </>
          ) : (
            "No rules-based reading (no text was analysed)."
          )}
        </p>
      </div>

      <div className="space-y-2" role="group" aria-label="Pretrained model results">
        <h4 className="text-sm font-medium">B. Pretrained model results</h4>
        <div className="grid gap-3 md:grid-cols-2">
          {research.models.map((model) => (
            <ModelCard key={model.slot} model={model} />
          ))}
        </div>
      </div>

      <div className="space-y-2" role="group" aria-label="Comparison">
        <h4 className="text-sm font-medium">C. Comparison</h4>
        <p className="text-sm font-medium">{comparisonHeading(research.comparison.status)}</p>
        <p className="text-sm">{research.comparison.explanation}</p>
        {research.comparison.model_vs_rules.map((entry) => (
          <p key={entry.slot} className="text-sm" data-slot={entry.slot}>
            {research.models.find((m) => m.slot === entry.slot)?.display_name ?? entry.slot}: {labelText(entry.model_label)}. Rules-based reading: {labelText(entry.rules_label)}.
          </p>
        ))}
        <p className="text-sm">
          Combined reading: <span className="font-medium">{labelText(research.overall_sentiment)}</span>
          {fellBack ? " (the rules-based reading, used as the fallback)" : " (experimental)"}.
        </p>
        {reason ? <p className="text-muted-foreground text-sm">{reason}</p> : null}
        <p className="text-muted-foreground text-sm">{rulesRelationText(research.rules_relation)}</p>
      </div>

      <p className="text-muted-foreground text-xs">{NO_CONFIDENCE_TEXT}</p>
      <p className="text-muted-foreground text-xs">{AUTHORITY_TEXT}</p>
      <TechnicalDetails
        items={[
          { label: "Mode", value: research.mode },
          { label: "Validation", value: research.validation_status },
          { label: "Effect on decisions", value: research.production_effect },
          ...research.models.map((m) => ({ label: `${m.display_name} revision`, value: m.revision ?? "none registered" })),
          { label: "Processing time (ms)", value: String(research.processing_metadata.total_ms ?? "not measured") },
        ]}
      />
    </section>
  )
}
