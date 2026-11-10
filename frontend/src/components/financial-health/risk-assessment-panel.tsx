import { ShieldCheck } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { components } from "@/types/api"

type Insight = components["schemas"]["PersonalizedInsightResponse"]

/**
 * "Your risk assessment on file": the stored assessment, shown on its own and apart from the reading of the customer's words. DISPLAY ONLY: the category and sentence are the backend's.
 * Nothing on this page, including a reading of the user's text, changes this assessment, and it stays the authority when the words differ from it.
 */
export function RiskAssessmentPanel({ data }: { data: Insight }) {
  const statement = data.statements.find((s) => s.kind === "risk_assessment")
  return (
    <Card role="region" aria-labelledby="risk-heading">
      <CardHeader>
        <CardTitle id="risk-heading" role="heading" aria-level={2} className="flex items-center gap-2 text-base">
          <ShieldCheck className="text-muted-foreground size-4" aria-hidden="true" /> Your risk assessment on file
        </CardTitle>
        <CardDescription>Kept separate from the reading of your words. Your words never change it.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {data.risk_profile ? (
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary">{data.risk_profile.category}</Badge>
            {data.risk_profile.remains_authoritative ? <Badge variant="outline">Remains authoritative</Badge> : null}
          </div>
        ) : null}
        {data.risk_profile ? (
          <p className="text-muted-foreground text-xs">
            Source: {data.risk_profile.source}. A reading of your words is informational only and ranks below this assessment, your compliance checks, your savings priority and your goals.
          </p>
        ) : null}
        {statement ? (
          <p className="text-sm">{statement.text}</p>
        ) : (
          <p className="text-muted-foreground text-sm">No risk assessment is on file for this profile yet. Nothing is assumed in its place.</p>
        )}
      </CardContent>
    </Card>
  )
}
