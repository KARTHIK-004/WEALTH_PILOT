import { Card, CardContent } from "@/components/ui/card"

/**
 * Phase 25 — shared by `PortfolioPage`/`RecommendationPage` for the exact
 * same situation (`AnalysisResult.recommendation` is `null`): rather than
 * a single generic "run an analysis" message regardless of why, this
 * reflects the REAL `AnalysisResult.status` (section 9: user-friendly
 * wording, the raw API value is never altered) when one is already known
 * — e.g. a `pending_information`/`rejected` result means analysis DID
 * run, it just never reached the recommendation stage, which is a
 * different situation from "no analysis has been attempted yet."
 */
const REASON_BY_STATUS: Record<string, string> = {
  pending_information: "Additional customer information is required before analysis can continue.",
  rejected: "This profile was blocked by a compliance rule, so no recommendation was generated.",
  failed: "The analysis could not complete for this profile.",
}

export function AnalysisIncompleteNotice({ status, subject }: { status: string | null | undefined; subject: string }) {
  const reason = status ? REASON_BY_STATUS[status] : undefined
  return (
    <Card>
      <CardContent className="text-muted-foreground pt-6 text-sm">
        {reason ?? `No ${subject} is available yet — run an analysis for this profile.`}
      </CardContent>
    </Card>
  )
}
