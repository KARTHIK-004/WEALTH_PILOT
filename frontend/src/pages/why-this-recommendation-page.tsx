import { CircleSlash, ShieldQuestion } from "lucide-react"

import { PlainLanguageExplanation } from "@/components/explanation/plain-language-explanation"

import { ErrorState } from "@/components/shell/error-state"
import { LoadingState } from "@/components/shell/loading-state"
import { NoProfileSelected } from "@/components/shell/no-profile-selected"
import { PageContainer } from "@/components/shell/page-container"
import { SectionUnavailable } from "@/components/shell/section-unavailable"
import { TermLabel } from "@/components/shell/help-tip"
import { StatusBadge } from "@/components/shell/status-badge"
import { TechnicalDetails } from "@/components/shell/technical-details"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useAnalysisQuery } from "@/hooks/use-analysis"
import { useProfileQuery } from "@/hooks/use-profile"
import { HELP, getAssetDisplayName, getMarketRegimeExplanation, getStrategyInfo } from "@/lib/terminology"
import { useCustomer } from "@/providers/customer-context"

function ProseSection({ title, text }: { title: string; text: string | null }) {
  if (!text) return null
  return (
    <div className="space-y-1">
      <p className="text-sm font-medium">{title}</p>
      <p className="text-muted-foreground text-sm leading-relaxed">{text}</p>
    </div>
  )
}

/**
 * Two clearly separated sources, never blended (section 20/21):
 * (1) Gemini's already-validated prose (`AnalysisResult.explanation`,
 * Phase 13's own structured-output-plus-numeric-validation result,
 * displayed verbatim -- never regenerated, never parsed for a number);
 * (2) the SAME structured deterministic factors (risk/goals/market/
 * compliance) the Risk Assessment/Financial Health/Goals pages already
 * show, from the SAME `AnalysisResult` object -- MASTER_PROMPT.md
 * section 25's "risk model factors... goal probability... market
 * regime... compliance checks" list, using only fields the API actually
 * returns, never an independently-inferred "the model chose X because."
 *
 * Two views of that same single analysis response (no extra AI call to
 * switch): **Simple** (the default) is `PlainLanguageExplanation`, the
 * results explained for a reader with no financial background; **Detailed**
 * is the two cards above.
 *
 * Plain-language presentation (`docs/DESIGN.md` section 30): the page
 * answers "Why did WealthPilot give me this result?"; the Detailed tab is
 * labelled as the technical view, names markets and the strategy in plain
 * words first, and keeps tickers/method names beside them.
 */
export function WhyThisRecommendationPage() {
  const { profileId } = useCustomer()
  const query = useAnalysisQuery(profileId)
  const profileQuery = useProfileQuery(profileId)

  if (profileId === null) {
    return (
      <PageContainer title="Why This Recommendation?" description="Why did WealthPilot give me this result? The explanation in plain words, with the technical detail one tab away.">
        <NoProfileSelected />
      </PageContainer>
    )
  }

  const data = query.data
  const explanation = data?.explanation

  return (
    <PageContainer title="Why This Recommendation?" description="Why did WealthPilot give me this result? The explanation in plain words, with the technical detail one tab away.">
      {query.isLoading ? (
        <LoadingState label="Preparing your explanation" />
      ) : query.error ? (
        <ErrorState error={query.error} onRetry={() => query.refetch()} />
      ) : !data ? (
        <Card>
          <CardContent className="text-muted-foreground pt-6 text-sm">
            No analysis is available yet for this profile.
          </CardContent>
        </Card>
      ) : (
        <Tabs defaultValue="simple" className="space-y-4">
          <TabsList aria-label="Explanation style">
            <TabsTrigger value="simple">Simple</TabsTrigger>
            <TabsTrigger value="detailed">Detailed (technical)</TabsTrigger>
          </TabsList>
          <TabsContent value="simple">
            <PlainLanguageExplanation data={data} profileGoals={profileQuery.data?.goals} />
          </TabsContent>
          <TabsContent value="detailed" className="space-y-4">
            <Card>
              <CardHeader>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <CardTitle className="flex items-center gap-2">
                    <ShieldQuestion className="text-muted-foreground size-4" /> Written explanation
                  </CardTitle>
                  {explanation?.status === "completed" ? (
                    <Badge variant={explanation.validation_passed ? "default" : "secondary"}>
                      {explanation.validation_passed
                        ? "AI-written wording, checked against the computed numbers"
                        : "Template restatement of the computed results"}
                    </Badge>
                  ) : null}
                </div>
                <CardDescription>
                  The AI (Gemini) only writes wording. Every number comes from the deterministic
                  results in the next card — the AI never calculates or decides anything.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {!explanation || explanation.status !== "completed" ? (
                  <SectionUnavailable
                    reason={
                      explanation?.status === "skipped_rejected" || data.status === "rejected"
                        ? "not generated — compliance rejected this profile's proposal"
                        : data.status === "pending_information"
                          ? "not generated — additional customer information is required before analysis can continue"
                          : (explanation?.failure_reason ?? undefined)
                    }
                  />
                ) : (
                  <>
                    <ProseSection title="Summary" text={explanation.summary} />
                    <ProseSection title="Risk" text={explanation.risk_explanation} />
                    <ProseSection title="Financial health" text={explanation.financial_health_explanation} />
                    <ProseSection title="Goals" text={explanation.goal_explanation} />
                    <ProseSection title="Portfolio" text={explanation.portfolio_explanation} />
                    <ProseSection title="Market conditions" text={explanation.market_explanation} />
                    <ProseSection title="Compliance" text={explanation.compliance_explanation} />
                    <ProseSection title="Limitations" text={explanation.limitations} />
                    {!explanation.validation_passed ? (
                      <Alert>
                        <CircleSlash />
                        <AlertTitle>Template explanation shown</AlertTitle>
                        <AlertDescription>
                          An AI-written explanation was not used for this run — the AI service was
                          unavailable or out of quota, or its wording did not pass validation
                          against the computed numbers. The text above is a direct template-based
                          restatement of the computed results; no number in it was produced by AI.
                        </AlertDescription>
                      </Alert>
                    ) : null}
                  </>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Calculated results</CardTitle>
                <CardDescription>
                  Computed by WealthPilot's own models and rules (deterministic) — not by the AI. The recommendation
                  is grounded in these results.
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <div>
                  <p className="text-muted-foreground text-xs">
                    <TermLabel help={HELP.riskProfile}>Risk profile</TermLabel>
                  </p>
                  <Badge variant="outline">{data.risk?.risk_category ?? "Not available"}</Badge>
                </div>
                <div>
                  <p className="text-muted-foreground text-xs">
                    <TermLabel help={HELP.complianceCheck}>Compliance check</TermLabel>
                  </p>
                  <StatusBadge status={data.compliance?.decision} />
                </div>
                <div>
                  <p className="text-muted-foreground text-xs">Goal outlook</p>
                  <div className="flex flex-wrap gap-1">
                    {data.goals.length === 0 ? (
                      <span className="text-muted-foreground text-sm">No goals recorded</span>
                    ) : (
                      data.goals.map((g) => <StatusBadge key={g.goal_id} status={g.feasibility} />)
                    )}
                  </div>
                </div>
                <div>
                  <p className="text-muted-foreground text-xs">
                    <TermLabel help={HELP.marketCondition}>Market conditions</TermLabel>
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {data.market?.instruments.length ? (
                      data.market.instruments.map((instrument) => (
                        <Badge
                          key={instrument.ticker}
                          variant="outline"
                          title={getMarketRegimeExplanation(instrument.latest_regime)}
                        >
                          {getAssetDisplayName(instrument.ticker)}: {instrument.latest_regime ?? "not available"}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-muted-foreground text-sm">Not available</span>
                    )}
                  </div>
                </div>
              </CardContent>
              <Separator />
              <CardContent className="space-y-3 pt-4">
                <p className="text-muted-foreground text-xs">
                  {data.recommendation?.status === "savings_first"
                    ? "Savings first: no investment strategy is selected while emergency savings are built up."
                    : `Selected strategy: ${getStrategyInfo(data.recommendation?.selected_strategy)?.label ?? "Not available"}`}
                </p>
                <TechnicalDetails
                  items={[
                    { label: "Selected strategy (API value)", value: data.recommendation?.selected_strategy },
                    { label: "Method", value: getStrategyInfo(data.recommendation?.selected_strategy)?.technical },
                    { label: "Market tickers", value: data.market?.instruments.map((instrument) => instrument.ticker).join(", ") },
                    { label: "Market model version", value: data.market?.model_version },
                    { label: "Market data source", value: data.market?.data_source },
                    { label: "Compliance rules version", value: data.compliance?.rules_version },
                    { label: "Explanation status", value: explanation?.status },
                  ]}
                />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      )}
    </PageContainer>
  )
}
