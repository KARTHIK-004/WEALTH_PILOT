import type { LucideIcon } from "lucide-react"
import {
  Activity,
  ArrowRight,
  Gauge,
  HeartPulse,
  Landmark,
  Lightbulb,
  PiggyBank,
  PieChart,
  ShieldCheck,
  Target,
  Wallet,
} from "lucide-react"
import { Link } from "react-router"

import { EmergencyFundChart } from "@/components/charts/emergency-fund-chart"
import { PortfolioAllocationChart } from "@/components/charts/portfolio-allocation-chart"
import { ErrorState } from "@/components/shell/error-state"
import { NoProfileSelected } from "@/components/shell/no-profile-selected"
import { PageContainer } from "@/components/shell/page-container"
import { PageLoadingState } from "@/components/shell/loading-state"
import { SectionUnavailable } from "@/components/shell/section-unavailable"
import { TermLabel } from "@/components/shell/help-tip"
import { StatusBadge } from "@/components/shell/status-badge"
import { TechnicalDetails } from "@/components/shell/technical-details"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { useAnalysisQuery } from "@/hooks/use-analysis"
import { useFinancialInputsQuery } from "@/hooks/use-financial-inputs"
import { formatCurrency } from "@/lib/format"
import {
  HELP,
  getCapacityDisplayName,
  getCustomerTypeDisplayName,
  getFeasibilityExplanation,
  getPlainRecommendationReasons,
  getRiskCategoryDescription,
  getStrategyDisplayName,
  getStrategyInfo,
} from "@/lib/terminology"
import { useProfileQuery } from "@/hooks/use-profile"
import { useCustomer } from "@/providers/customer-context"

/**
 * Plain-language "what should I do next" sentence per
 * `AnalysisResult.status` (section 9 — user-facing wording only; the raw
 * API status is still shown verbatim via `StatusBadge` right below it,
 * never replaced). Every entry links to the existing page that already
 * has the full detail for that state — no new page, no new API call.
 */
const NEXT_STEP: Record<string, { text: string; href: string; linkLabel: string }> = {
  approved: {
    text: "A plan is ready for you.",
    href: "/recommendation",
    linkLabel: "View my plan",
  },
  rejected: {
    text: "Your profile needs attention before a plan can be provided — see what's required below.",
    href: "/recommendation",
    linkLabel: "See what's required",
  },
  pending_information: {
    text: "A few more details are needed before WealthPilot can assess your profile.",
    href: "/risk-assessment",
    linkLabel: "See what's needed",
  },
  failed: {
    text: "Something went wrong while preparing your analysis.",
    href: "/agent-activity",
    linkLabel: "See what happened",
  },
  // Keyed off `AnalysisResult.recommendation.status` (not the overall
  // `status`, which is "approved" for a savings-first result too) so an
  // approved savings-first outcome is never described as if an investment
  // plan were active.
  savings_first: {
    text: "Focus on building your savings first — no investment plan is active yet.",
    href: "/recommendation",
    linkLabel: "View the details",
  },
}

/** One plain sentence per compliance decision — the decision code itself
 * (PASS/WARN/REJECT) is never changed, only explained. */
const COMPLIANCE_EXPLANATION: Record<string, string> = {
  PASS: "Your profile passed the required checks.",
  WARN: "Your profile passed, with some items noted.",
  REJECT: "Your profile needs attention before a plan can be provided.",
}

/** One real, backend-sourced number per card — never a derived or
 * fabricated figure (no "Net worth" tile: WealthPilot computes no
 * individual net position; that exists only at household level, Phase
 * 34). Each card renders "Not available" rather than 0 when the backend
 * has not been given the value yet. */
function KpiCard({
  icon: Icon,
  label,
  value,
  description,
  help,
}: {
  icon: LucideIcon
  label: string
  value: string | null
  description?: string
  help?: string
}) {
  return (
    <Card size="sm" className="gap-2">
      <CardHeader className="gap-0">
        <CardDescription className="flex items-center gap-1.5">
          <Icon className="size-3.5" aria-hidden="true" />
          {help ? <TermLabel help={help}>{label}</TermLabel> : label}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className={value ? "text-2xl font-semibold tracking-tight" : "text-muted-foreground text-sm"}>
          {value ?? "Not available"}
        </p>
        {value && description ? <p className="text-muted-foreground mt-0.5 text-xs">{description}</p> : null}
      </CardContent>
    </Card>
  )
}

/**
 * A summary only — every value below is read directly from the SAME
 * `AnalysisResult`/`ProfileResponse` the other pages use (via the shared
 * `useAnalysisQuery`/`useProfileQuery`/`useFinancialInputsQuery` cache),
 * never recomputed or independently derived here.
 *
 * Presentation is deliberately two-layered for a reader with no finance
 * background (unrelated redesign task): the primary UI uses plain
 * sentences built only from already-computed backend fields (status
 * codes, category labels, alignment booleans, `terminology.ts`'s
 * existing plain-language maps), and every underlying technical value
 * (risk/strategy/goal/market codes, rule ids, provenance ids) stays
 * available, verbatim, in the collapsed "Analysis details" sections —
 * never removed, only moved out of the primary presentation layer.
 */
export function DashboardPage() {
  const { profileId } = useCustomer()
  const profileQuery = useProfileQuery(profileId)
  const analysisQuery = useAnalysisQuery(profileId)
  const financialInputsQuery = useFinancialInputsQuery(profileId)

  if (profileId === null) {
    return (
      <PageContainer title="Dashboard" description="See where you stand and what WealthPilot recommends.">
        <NoProfileSelected />
      </PageContainer>
    )
  }

  const isLoading = profileQuery.isLoading || analysisQuery.isLoading || financialInputsQuery.isLoading
  const error = profileQuery.error ?? analysisQuery.error
  const analysis = analysisQuery.data
  const nextStepKey = analysis?.recommendation?.status === "savings_first" ? "savings_first" : analysis?.status
  const nextStep = nextStepKey ? NEXT_STEP[nextStepKey] : undefined

  const strategyInfo = getStrategyInfo(analysis?.recommendation?.selected_strategy)
  const plainReasons = getPlainRecommendationReasons({
    riskCategory: analysis?.risk?.risk_category,
    riskBasedStrategy: analysis?.recommendation?.rationale?.risk_based_strategy,
    goalFeasibilityUsed: analysis?.recommendation?.rationale?.goal_feasibility_used,
    goalPreferenceAligned: analysis?.recommendation?.rationale?.goal_preference_aligned,
    marketRegimeUsed: analysis?.recommendation?.rationale?.market_regime_used,
    marketPreferenceAligned: analysis?.recommendation?.rationale?.market_preference_aligned,
  })

  // Merge the two independent goal sources (never computed here): the
  // analysis's own evaluated goals (feasibility, target) with the
  // profile's own stored goals (current_savings) by goal id.
  const goalsWithProgress = (analysis?.goals ?? []).map((goal) => ({
    ...goal,
    currentSavings: profileQuery.data?.goals.find((g) => g.id === goal.goal_id)?.current_savings,
  }))

  return (
    <PageContainer title="Dashboard" description="See where you stand and what WealthPilot recommends.">
      {isLoading ? (
        <PageLoadingState />
      ) : error ? (
        <ErrorState error={error} onRetry={() => { profileQuery.refetch(); analysisQuery.refetch() }} />
      ) : (
        <div className="space-y-6">
          {/* 1 — your personalized plan: the single most prominent element. */}
          <Card className="ring-primary/15 bg-primary/5">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Lightbulb className="text-primary size-5" aria-hidden="true" />
                Your personalized plan
              </CardTitle>
              <CardDescription>
                {analysis?.recommendation?.status === "approved" && strategyInfo
                  ? `${strategyInfo.label} is recommended for you. ${strategyInfo.help}`
                  : (nextStep?.text ?? "No plan is available for this profile yet.")}
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex flex-wrap items-center gap-3">
                <div className="space-y-0.5">
                  <StatusBadge status={analysis?.recommendation?.status ?? analysis?.status} />
                  {analysis?.compliance?.decision ? (
                    <p className="text-muted-foreground text-xs">{COMPLIANCE_EXPLANATION[analysis.compliance.decision]}</p>
                  ) : null}
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {nextStep ? (
                  <Button size="sm" render={<Link to={nextStep.href} />}>
                    {analysis?.recommendation?.status === "approved" ? "View my plan" : nextStep.linkLabel}{" "}
                    <ArrowRight className="size-4" />
                  </Button>
                ) : null}
                <Button variant="outline" size="sm" render={<Link to="/why-this-recommendation" />}>
                  Why am I seeing this?
                </Button>
              </div>
            </CardContent>
            {plainReasons.length > 0 ? (
              <CardContent className="border-t pt-4">
                <p className="text-muted-foreground mb-1.5 text-xs font-medium tracking-wide uppercase">
                  Why this is recommended
                </p>
                <ul className="text-sm space-y-1">
                  {plainReasons.map((reason, index) => (
                    <li key={index} className="flex gap-2">
                      <span className="text-muted-foreground">•</span>
                      <span>{reason}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            ) : null}
            {analysis?.recommendation || analysis?.risk ? (
              <CardContent className="border-t pt-3">
                <TechnicalDetails
                  title="Analysis details"
                  items={[
                    { label: "Risk category", value: analysis?.risk?.risk_category },
                    { label: "Strategy", value: strategyInfo?.technical },
                    { label: "Goal status used", value: analysis?.recommendation?.rationale?.goal_feasibility_used },
                    { label: "Market condition used", value: analysis?.recommendation?.rationale?.market_regime_used },
                    { label: "Compliance decision", value: analysis?.compliance?.decision },
                    { label: "Compliance rules version", value: analysis?.compliance?.rules_version },
                    { label: "Customer ID", value: profileQuery.data?.customer_id },
                    { label: "Analysis ID", value: analysis?.analysis_id },
                  ]}
                />
              </CardContent>
            ) : null}
          </Card>

          {/* 2 — your important numbers: only real, individual-level fields
              (no fabricated "Net worth" — that exists only at household
              level, Phase 34). */}
          <div className="grid gap-3 sm:grid-cols-3">
            <KpiCard
              icon={Wallet}
              label="Annual income"
              value={profileQuery.data?.income != null ? formatCurrency(profileQuery.data.income) : null}
              description="Your income for the year"
            />
            <KpiCard
              icon={Landmark}
              label="Essential spending"
              value={
                financialInputsQuery.data?.monthly_essential_expenses != null
                  ? formatCurrency(financialInputsQuery.data.monthly_essential_expenses)
                  : null
              }
              description="Regular essential costs each month"
            />
            <KpiCard
              icon={PiggyBank}
              label="Easy-access savings"
              value={
                financialInputsQuery.data?.current_liquid_assets != null
                  ? formatCurrency(financialInputsQuery.data.current_liquid_assets)
                  : null
              }
              description="Savings available when needed"
              help={HELP.emergencySavings}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            {/* LEFT COLUMN — financial health, then goals */}
            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <HeartPulse className="text-muted-foreground size-4" aria-hidden="true" /> Financial health
                  </CardTitle>
                  <CardDescription>
                    {analysis?.emergency_fund?.sufficient === true
                      ? "Your safety-net savings meet the target."
                      : analysis?.emergency_fund?.sufficient === false
                        ? "Your safety-net savings are below target."
                        : "Your safety-net savings status isn't available yet."}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {analysis?.emergency_fund?.sufficient === true ? (
                    <p className="text-muted-foreground text-sm">
                      If something unexpected happens, you currently have enough set aside to cover it.
                    </p>
                  ) : analysis?.emergency_fund?.sufficient === false ? (
                    <p className="text-muted-foreground text-sm">
                      You don't yet have enough set aside to cover an unexpected cost — building this up comes first.
                    </p>
                  ) : (
                    <SectionUnavailable reason={analysis?.emergency_fund?.unavailable_reason} />
                  )}
                  <p className="text-muted-foreground text-sm">
                    Your income, spending and savings together give WealthPilot a clear picture of your financial
                    position.
                  </p>
                  <Link to="/financial-health" className="text-primary text-sm underline underline-offset-2">
                    View financial health
                  </Link>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Target className="text-muted-foreground size-4" aria-hidden="true" /> Goals
                  </CardTitle>
                  <CardDescription>
                    {analysis?.goals?.length
                      ? "What you're working toward"
                      : profileQuery.data?.goals.length
                        ? `${profileQuery.data.goals.length} ${profileQuery.data.goals.length === 1 ? "goal" : "goals"} recorded — not yet evaluated`
                        : "No goals recorded"}
                  </CardDescription>
                </CardHeader>
                {goalsWithProgress.length > 0 ? (
                  <CardContent className="space-y-0">
                    <ul className="divide-border -mx-1 divide-y">
                      {goalsWithProgress.slice(0, 4).map((goal) => (
                        <li key={goal.goal_id} className="flex items-center justify-between gap-3 px-1 py-2.5">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium">{goal.goal_type}</p>
                            <p className="text-muted-foreground text-xs">
                              {goal.currentSavings != null
                                ? `${formatCurrency(goal.currentSavings)} of ${formatCurrency(goal.nominal_target_amount)}`
                                : formatCurrency(goal.nominal_target_amount)}
                              {goal.feasibility ? ` · ${getFeasibilityExplanation(goal.feasibility) ?? ""}` : ""}
                            </p>
                          </div>
                          {goal.feasibility ? <StatusBadge status={goal.feasibility} /> : null}
                        </li>
                      ))}
                    </ul>
                    <Separator className="my-2" />
                    <Link to="/goals" className="text-primary text-sm underline underline-offset-2">
                      View all goals
                    </Link>
                  </CardContent>
                ) : (
                  <CardContent>
                    <Link to="/goals" className="text-primary text-sm underline underline-offset-2">
                      View goals
                    </Link>
                  </CardContent>
                )}
              </Card>
            </div>

            {/* RIGHT COLUMN — investment comfort level, then investment mix */}
            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Gauge className="text-muted-foreground size-4" aria-hidden="true" />
                    <TermLabel help={HELP.riskProfile}>Your investment comfort level</TermLabel>
                  </CardTitle>
                  <CardDescription className="text-foreground font-medium">
                    {analysis?.risk?.risk_category ?? "Not available yet"}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  {analysis?.risk?.risk_category ? (
                    <p className="text-muted-foreground text-sm">
                      {getRiskCategoryDescription(analysis.risk.risk_category) ?? ""}
                    </p>
                  ) : (
                    <SectionUnavailable reason={analysis?.risk?.unavailable_reason} />
                  )}
                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    {profileQuery.data?.customer_type ? (
                      <Badge variant="outline">{getCustomerTypeDisplayName(profileQuery.data.customer_type)}</Badge>
                    ) : null}
                    {profileQuery.data?.investment_capacity ? (
                      <span className="inline-flex items-center gap-1 text-sm">
                        <TermLabel help={HELP.capacityBand}>Capacity band:</TermLabel>
                        <span className="font-medium">{getCapacityDisplayName(profileQuery.data.investment_capacity)}</span>
                      </span>
                    ) : null}
                  </div>
                  <Link to="/risk-assessment" className="text-primary text-sm underline underline-offset-2">
                    How is this determined?
                  </Link>
                </CardContent>
              </Card>

              {analysis?.recommendation?.status === "approved" && analysis.recommendation.weights ? (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <PieChart className="text-muted-foreground size-4" aria-hidden="true" />
                      <TermLabel help={HELP.investmentAllocation}>Your investment mix</TermLabel>
                    </CardTitle>
                    <CardDescription>
                      How your {getStrategyDisplayName(analysis.recommendation.selected_strategy) ?? "investments"}{" "}
                      plan is divided.{" "}
                      <Link to="/portfolio" className="text-primary underline underline-offset-2">
                        View portfolio detail
                      </Link>
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <PortfolioAllocationChart weights={analysis.recommendation.weights} />
                  </CardContent>
                </Card>
              ) : analysis?.recommendation?.status === "savings_first" ? (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <PiggyBank className="text-muted-foreground size-4" aria-hidden="true" />
                      <TermLabel help={HELP.emergencySavings}>Building your safety net</TermLabel>
                    </CardTitle>
                    <CardDescription>
                      Building up your easy-access savings comes before investing, so no investment plan is active
                      yet.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <EmergencyFundChart
                      required={analysis.emergency_fund?.required_amount}
                      current={analysis.emergency_fund?.current_amount}
                      shortfall={analysis.emergency_fund?.shortfall}
                      sufficient={analysis.emergency_fund?.sufficient}
                      unavailableReason={analysis.emergency_fund?.unavailable_reason}
                    />
                  </CardContent>
                </Card>
              ) : null}
            </div>
          </div>

          {/* Compliance + overall analysis status — a quiet footer row;
              never hidden, since a rejection must stay visible. */}
          <Card>
            <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
              <div className="flex flex-wrap items-center gap-4">
                <span className="flex items-center gap-2 text-sm">
                  <ShieldCheck className="text-muted-foreground size-4" aria-hidden="true" />
                  <TermLabel help={HELP.complianceCheck}>Safety checks:</TermLabel>
                  <StatusBadge status={analysis?.compliance?.decision} />
                </span>
                <span className="flex items-center gap-2 text-sm">
                  <Activity className="text-muted-foreground size-4" aria-hidden="true" />
                  Analysis:
                  <StatusBadge status={analysis?.status} />
                </span>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </PageContainer>
  )
}
