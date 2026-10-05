import { CheckCircle2, XCircle } from "lucide-react"

import { TermLabel } from "@/components/shell/help-tip"
import { StatusBadge } from "@/components/shell/status-badge"
import { TechnicalDetails } from "@/components/shell/technical-details"
import { HELP, getComplianceRuleName } from "@/lib/terminology"
import type { components } from "@/types/api"

type ComplianceSection = components["schemas"]["ComplianceSection"]

/** One plain sentence per decision -- chosen by the backend's own decision
 * value, never inferred. A REJECT is never worded as an approval. */
const DECISION_TEXT: Record<string, string> = {
  PASS: "The proposal passed every compliance rule.",
  WARN: "The proposal passed, with a warning to review.",
  REJECT: "The proposal did not pass the compliance check, so no investment plan is shown.",
}

/**
 * Phase 29 — display-only rendering of `AnalysisResult.compliance`: the
 * overall decision plus every rule's result exactly as the API returns it.
 * Nothing here is calculated or inferred: a rule is shown as not met only
 * because the backend said `triggered: true`. Status is conveyed by icon +
 * text, never color alone.
 *
 * Plain-language presentation (`docs/DESIGN.md` section 30): each rule is
 * named in everyday words (`lib/terminology.ts`, keyed by the rule's id);
 * for a rule that was not met, the backend's own message and reason stay
 * visible because they explain the outcome. The rules version, rule ids,
 * severities and the backend's full rule descriptions are kept, unchanged,
 * in Technical details.
 */
export function ComplianceBreakdown({ compliance }: { compliance: ComplianceSection }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <TermLabel help={HELP.complianceCheck}>Compliance check</TermLabel>
        <StatusBadge status={compliance.decision} />
      </div>
      {DECISION_TEXT[compliance.decision] ? (
        <p className="text-muted-foreground text-sm">{DECISION_TEXT[compliance.decision]}</p>
      ) : null}
      <ul className="space-y-2" aria-label="Compliance rules">
        {compliance.rule_results.map((rule) => (
          <li key={rule.rule_id} className="flex items-start gap-2 text-sm">
            {rule.triggered ? (
              <XCircle className="text-destructive mt-0.5 size-4 shrink-0" aria-hidden="true" />
            ) : (
              <CheckCircle2 className="text-primary mt-0.5 size-4 shrink-0" aria-hidden="true" />
            )}
            <div className="min-w-0">
              <p>
                {getComplianceRuleName(rule.rule_id, rule.description)}{" "}
                <span className="text-muted-foreground text-xs">({rule.triggered ? "not met" : "met"})</span>
              </p>
              {rule.triggered ? (
                <div className="text-muted-foreground space-y-0.5 text-xs">
                  <p>{rule.message}</p>
                  {rule.reason ? <p>Reason: {rule.reason}</p> : null}
                </div>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
      <TechnicalDetails
        items={[
          { label: "Decision", value: compliance.decision },
          { label: "Compliance rules version", value: compliance.rules_version },
          ...compliance.rule_results.map((rule) => ({
            label: `${rule.rule_id} (${rule.severity})`,
            value: `${rule.triggered ? "triggered" : "passed"} — ${rule.description.trim()}`,
          })),
        ]}
      />
    </div>
  )
}
