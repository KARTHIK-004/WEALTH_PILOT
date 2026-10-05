import { AlertTriangle, Ban, CircleSlash } from "lucide-react"

import { EmergencyFundChart } from "@/components/charts/emergency-fund-chart"
import { PortfolioAllocationChart } from "@/components/charts/portfolio-allocation-chart"
import { AllocationTable } from "@/components/portfolio/allocation-table"
import { PortfolioMetrics } from "@/components/portfolio/portfolio-metrics"
import { StrategySummary } from "@/components/portfolio/strategy-summary"
import { AnalysisIncompleteNotice } from "@/components/shell/analysis-incomplete-notice"
import { ComplianceBreakdown } from "@/components/shell/compliance-breakdown"
import { ErrorState } from "@/components/shell/error-state"
import { LoadingState } from "@/components/shell/loading-state"
import { NoProfileSelected } from "@/components/shell/no-profile-selected"
import { PageContainer } from "@/components/shell/page-container"
import { TermLabel } from "@/components/shell/help-tip"
import { StatusBadge } from "@/components/shell/status-badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useAnalysisQuery } from "@/hooks/use-analysis"
import { HELP } from "@/lib/terminology"
import { useCustomer } from "@/providers/customer-context"

/**
 * Reads `AnalysisResult.recommendation` — the SAME field the
 * Recommendation page reads (section 46: both pages "must display the
 * same authoritative recommendation/portfolio data... use the same
 * values") — rather than the raw `AnalysisResult.portfolio` field, which
 * can reflect a DIFFERENT (pre-Phase-14, not-yet-risk-conditioned)
 * strategy than the one Phase 14 finally selected (`reports/
 * phase14_recommendation_engine_report.md` section 12: the orchestration
 * layer may recompute a candidate for a different strategy than whatever
 * the graph's own `portfolio_result` already held). Showing `portfolio`
 * directly here could silently disagree with the Recommendation page —
 * `recommendation` is always Phase 14's own final, authoritative pick.
 *
 * Plain-language presentation (`docs/DESIGN.md` section 30): the strategy
 * is named "Optimized Portfolio" rather than MVO, investments by name
 * rather than ticker, and volatility/Sharpe as "Expected variability"/
 * "Risk-adjusted performance" -- the numbers and API values are unchanged,
 * and the technical names are in Technical details.
 */
export function PortfolioPage() {
  const { profileId } = useCustomer()
  const query = useAnalysisQuery(profileId)

  if (profileId === null) {
    return (
      <PageContainer title="Portfolio Analysis" description="How the proposed plan splits money between investments, and why this approach was chosen.">
        <NoProfileSelected />
      </PageContainer>
    )
  }

  const recommendation = query.data?.recommendation

  return (
    <PageContainer title="Portfolio Analysis" description="How the proposed plan splits money between investments, and why this approach was chosen.">
      {query.isLoading ? (
        <LoadingState label="Loading your investment plan" />
      ) : query.error ? (
        <ErrorState error={query.error} onRetry={() => query.refetch()} />
      ) : !recommendation ? (
        <div className="space-y-4">
          <AnalysisIncompleteNotice status={query.data?.status} subject="portfolio information" />
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
      ) : recommendation.status === "blocked_rejected" ? (
        <Alert variant="destructive">
          <Ban />
          <AlertTitle>Recommendation not approved by the compliance check</AlertTitle>
          <AlertDescription>
            No investment plan can be shown for this profile, because the compliance check blocks any
            recommendation. See the AI Recommendation page for details.
          </AlertDescription>
        </Alert>
      ) : recommendation.status === "savings_first" ? (
        <div className="space-y-4">
          <Alert>
            <AlertTriangle />
            <AlertTitle>Savings first: no investment allocation yet</AlertTitle>
            <AlertDescription>
              Building emergency savings comes before investing. No investment plan is proposed until your
              emergency savings reach the target.
            </AlertDescription>
          </Alert>
          <Card>
            <CardHeader>
              <CardTitle>
                <TermLabel help={HELP.emergencySavings}>Emergency savings</TermLabel>
              </CardTitle>
              <CardDescription>Why investing is on hold: your savings compared with the recommended target.</CardDescription>
            </CardHeader>
            <CardContent>
              <EmergencyFundChart
                required={query.data?.emergency_fund?.required_amount}
                current={query.data?.emergency_fund?.current_amount}
                shortfall={query.data?.emergency_fund?.shortfall}
                sufficient={query.data?.emergency_fund?.sufficient}
                unavailableReason={query.data?.emergency_fund?.unavailable_reason}
              />
            </CardContent>
          </Card>
        </div>
      ) : recommendation.status === "failed" ? (
        <Alert variant="destructive">
          <CircleSlash />
          <AlertTitle>Portfolio unavailable</AlertTitle>
          <AlertDescription>
            {recommendation.blocking_reason ?? "A portfolio could not be determined for this profile."}
          </AlertDescription>
        </Alert>
      ) : !recommendation.weights ? (
        <Alert>
          <CircleSlash />
          <AlertTitle>Allocation not available</AlertTitle>
          <AlertDescription>No investment allocation was returned for this profile.</AlertDescription>
        </Alert>
      ) : (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <CardTitle>Selected investment strategy</CardTitle>
                  <CardDescription>
                    Chosen for the {recommendation.risk_category ?? "(not available)"} risk profile.
                  </CardDescription>
                </div>
                <StatusBadge status={recommendation.status} />
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <StrategySummary
                strategy={recommendation.selected_strategy}
                riskCategory={recommendation.risk_category}
                weights={recommendation.weights}
              />
              <PortfolioMetrics
                expectedReturn={recommendation.expected_return}
                expectedVolatility={recommendation.expected_volatility}
                sharpeRatio={recommendation.sharpe_ratio}
              />
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>
                  <TermLabel help={HELP.investmentAllocation}>Your investment allocation</TermLabel>
                </CardTitle>
                <CardDescription>The share of the plan in each investment.</CardDescription>
              </CardHeader>
              <CardContent>
                <PortfolioAllocationChart weights={recommendation.weights} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Allocation details</CardTitle>
                <CardDescription>The same allocation as a table.</CardDescription>
              </CardHeader>
              <CardContent>
                <AllocationTable weights={recommendation.weights} />
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </PageContainer>
  )
}
