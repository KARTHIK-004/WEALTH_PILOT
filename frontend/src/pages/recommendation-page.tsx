import { AlertTriangle, Ban, CircleSlash, Lightbulb } from "lucide-react"
import { Link } from "react-router"

import { PortfolioAllocationChart } from "@/components/charts/portfolio-allocation-chart"
import { AllocationTable } from "@/components/portfolio/allocation-table"
import { PortfolioMetrics } from "@/components/portfolio/portfolio-metrics"
import { RationaleInPlainWords } from "@/components/portfolio/rationale-in-plain-words"
import { StrategySummary } from "@/components/portfolio/strategy-summary"
import { AnalysisIncompleteNotice } from "@/components/shell/analysis-incomplete-notice"
import { ComplianceBreakdown } from "@/components/shell/compliance-breakdown"
import { ErrorState } from "@/components/shell/error-state"
import { LoadingState } from "@/components/shell/loading-state"
import { NoProfileSelected } from "@/components/shell/no-profile-selected"
import { PageContainer } from "@/components/shell/page-container"
import { TermLabel } from "@/components/shell/help-tip"
import { StatusBadge } from "@/components/shell/status-badge"
import { TechnicalDetails } from "@/components/shell/technical-details"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useAnalysisQuery } from "@/hooks/use-analysis"
import { formatDate } from "@/lib/format"
import { HELP } from "@/lib/terminology"
import { useCustomer } from "@/providers/customer-context"

/**
 * The deterministic Phase 14 recommendation, exactly as `AnalysisResult.
 * recommendation` returns it (section 13). `blocked_rejected` never
 * renders an approved strategy/allocation/action button anywhere on this
 * page (section 15) — the branch below returns entirely before reaching
 * any of that JSX, structurally, not just by a hidden style.
 *
 * Plain-language presentation (`docs/DESIGN.md` section 30): the page reads
 * as "Your recommendation" with What we found / Why / Your investment
 * allocation / Important points / What to consider next. The "why" is the
 * backend's own structured `rationale` fields put into words
 * (`RationaleInPlainWords`) -- nothing is re-decided or recomputed -- and
 * the backend's verbatim reason strings, versions and method names are in
 * Technical details. Gemini is not involved in anything on this page.
 */
export function RecommendationPage() {
  const { profileId } = useCustomer()
  const query = useAnalysisQuery(profileId)

  if (profileId === null) {
    return (
      <PageContainer title="AI Recommendation" description="What WealthPilot proposes for this profile, why, and whether it passed the compliance check.">
        <NoProfileSelected />
      </PageContainer>
    )
  }

  const recommendation = query.data?.recommendation

  return (
    <PageContainer title="AI Recommendation" description="What WealthPilot proposes for this profile, why, and whether it passed the compliance check.">
      {query.isLoading ? (
        <LoadingState label="Loading your recommendation" />
      ) : query.error ? (
        <ErrorState error={query.error} onRetry={() => query.refetch()} />
      ) : !recommendation ? (
        <div className="space-y-4">
          <AnalysisIncompleteNotice status={query.data?.status} subject="recommendation" />
          {query.data?.compliance ? (
            <Card>
              <CardHeader>
                <CardTitle>Compliance check</CardTitle>
                <CardDescription>The safety rules this profile was checked against, and the result of each.</CardDescription>
              </CardHeader>
              <CardContent>
                <ComplianceBreakdown compliance={query.data.compliance} />
              </CardContent>
            </Card>
          ) : null}
        </div>
      ) : (
        <div className="space-y-4">
          {recommendation.status === "blocked_rejected" ? (
            <Alert variant="destructive">
              <Ban />
              <AlertTitle>Recommendation not approved by the compliance check</AlertTitle>
              <AlertDescription>
                {recommendation.blocking_reason ?? "The compliance check blocks any recommendation for this profile."}
                {" "}No strategy, allocation, or investment action is available.
              </AlertDescription>
            </Alert>
          ) : recommendation.status === "savings_first" ? (
            <Alert>
              <AlertTriangle />
              <AlertTitle>Savings first</AlertTitle>
              <AlertDescription>
                Your recommendation is to build up your emergency savings before investing. This is not an
                investment strategy — no investment allocation is active.
              </AlertDescription>
            </Alert>
          ) : recommendation.status === "failed" ? (
            <Alert variant="destructive">
              <CircleSlash />
              <AlertTitle>Recommendation unavailable</AlertTitle>
              <AlertDescription>
                {recommendation.blocking_reason ?? "A recommendation could not be determined for this profile."}
              </AlertDescription>
            </Alert>
          ) : (
            <Card>
              <CardHeader>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <CardTitle className="flex items-center gap-2">
                    <Lightbulb className="text-muted-foreground size-4" /> Your recommendation
                  </CardTitle>
                  <StatusBadge status={recommendation.status} />
                </div>
                <CardDescription>
                  Based on the available financial information, goals, risk profile and portfolio constraints, the
                  system produced the following recommendation.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <StrategySummary
                  strategy={recommendation.selected_strategy}
                  riskCategory={recommendation.risk_category}
                  weights={recommendation.weights}
                />
                {recommendation.weights ? (
                  <>
                    <h2 className="text-sm font-medium">
                      <TermLabel help={HELP.investmentAllocation}>Your investment allocation</TermLabel>
                    </h2>
                    <PortfolioMetrics
                      expectedReturn={recommendation.expected_return}
                      expectedVolatility={recommendation.expected_volatility}
                      sharpeRatio={recommendation.sharpe_ratio}
                    />
                    <div className="grid gap-4 lg:grid-cols-2">
                      <PortfolioAllocationChart weights={recommendation.weights} />
                      <AllocationTable weights={recommendation.weights} />
                    </div>
                  </>
                ) : null}
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>What we found</CardTitle>
              <CardDescription>The main results this recommendation is based on.</CardDescription>
            </CardHeader>
            <CardContent>
              <dl className="grid gap-4 text-sm sm:grid-cols-3">
                <div>
                  <dt className="text-muted-foreground text-xs">
                    <TermLabel help={HELP.riskProfile}>Risk profile</TermLabel>
                  </dt>
                  <dd className="font-medium">{query.data?.risk?.risk_category ?? "Not available"}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground text-xs">
                    <TermLabel help={HELP.emergencySavings}>Emergency savings</TermLabel>
                  </dt>
                  <dd>
                    <StatusBadge
                      status={
                        query.data?.emergency_fund?.sufficient === true
                          ? "sufficient"
                          : query.data?.emergency_fund?.sufficient === false
                            ? "insufficient"
                            : null
                      }
                    />
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground text-xs">Goals</dt>
                  <dd className="flex flex-wrap gap-1">
                    {query.data?.goals.length ? (
                      query.data.goals.map((goal) => (
                        <span key={goal.goal_id} className="inline-flex items-center gap-1">
                          <span>{goal.goal_type}:</span>
                          <StatusBadge status={goal.feasibility} />
                        </span>
                      ))
                    ) : (
                      <span className="text-muted-foreground">No goals evaluated</span>
                    )}
                  </dd>
                </div>
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Why this recommendation was produced</CardTitle>
              <CardDescription>
                The reasons recorded by the recommendation engine, in plain words. Risk suitability always takes
                priority over goal and market preferences.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <RationaleInPlainWords recommendation={recommendation} />
              <TechnicalDetails
                items={[
                  ...recommendation.rationale.reasons.map((reason, index) => ({ label: `Reason ${index + 1}`, value: reason })),
                  { label: "Risk-based strategy", value: recommendation.rationale.risk_based_strategy },
                  { label: "Goal preference", value: recommendation.rationale.goal_preference },
                  { label: "Market preference", value: recommendation.rationale.market_preference },
                ]}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Compliance check</CardTitle>
              <CardDescription>The safety rules the proposal was checked against, and the result of each.</CardDescription>
            </CardHeader>
            <CardContent>
              {query.data?.compliance ? (
                <ComplianceBreakdown compliance={query.data.compliance} />
              ) : (
                <StatusBadge status={recommendation.compliance_decision} />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Important points</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="list-disc space-y-1 pl-5 text-sm">
                <li>This is a model-based proposal built from the information available, not a guarantee of future returns.</li>
                <li>Expected figures are estimates from past market data; actual results can be higher or lower.</li>
                <li>
                  The compliance check is binding: a proposal that does not pass it is never shown as a recommendation.
                </li>
              </ul>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>What to consider next</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="list-disc space-y-1 pl-5 text-sm">
                <li>
                  Read the plain-language explanation on{" "}
                  <Link to="/why-this-recommendation" className="text-primary underline underline-offset-2">
                    Why This Recommendation?
                  </Link>
                </li>
                <li>
                  Compare other ways of building a portfolio in the{" "}
                  <Link to="/scenarios" className="text-primary underline underline-offset-2">
                    Scenario Simulator
                  </Link>
                  .
                </li>
                <li>Keep your financial information and goals up to date so the analysis reflects your situation.</li>
              </ul>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Analysis information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <dl className="grid gap-3 sm:grid-cols-3">
                <div>
                  <dt className="text-muted-foreground text-xs">Evaluated</dt>
                  <dd>{formatDate(recommendation.evaluated_at)}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground text-xs">Risk model version</dt>
                  <dd>{recommendation.provenance.risk_model_version ?? "Not provided"}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground text-xs">Compliance rules version</dt>
                  <dd>{recommendation.provenance.compliance_rules_version ?? "Not provided"}</dd>
                </div>
              </dl>
              <TechnicalDetails
                items={[
                  { label: "Recommendation engine (Phase 14) version", value: recommendation.provenance.phase14_version },
                  { label: "Risk model version", value: recommendation.provenance.risk_model_version },
                  { label: "Market model version", value: recommendation.provenance.market_model_version },
                  { label: "Portfolio config version", value: recommendation.provenance.portfolio_config_version },
                  { label: "Compliance rules version", value: recommendation.provenance.compliance_rules_version },
                  { label: "Selected strategy (API value)", value: recommendation.selected_strategy },
                ]}
              />
            </CardContent>
          </Card>
        </div>
      )}
    </PageContainer>
  )
}
