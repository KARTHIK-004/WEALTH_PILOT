import { AlertTriangle } from "lucide-react"
import { Link } from "react-router"

import { GoalTargetChart } from "@/components/charts/goal-target-chart"
import { ErrorState } from "@/components/shell/error-state"
import { TermLabel } from "@/components/shell/help-tip"
import { LoadingState } from "@/components/shell/loading-state"
import { NoProfileSelected } from "@/components/shell/no-profile-selected"
import { PageContainer } from "@/components/shell/page-container"
import { SectionUnavailable } from "@/components/shell/section-unavailable"
import { StatusBadge } from "@/components/shell/status-badge"
import { TechnicalDetails } from "@/components/shell/technical-details"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { useAnalysisQuery } from "@/hooks/use-analysis"
import { useProfileQuery } from "@/hooks/use-profile"
import { formatCurrency, formatDate, formatPercent } from "@/lib/format"
import { HELP, getFeasibilityExplanation } from "@/lib/terminology"
import { useCustomer } from "@/providers/customer-context"

const TITLE = "Your Goals"
const DESCRIPTION = "See how your current financial information compares with the goals you have set."

function Figure({ label, help, children }: { label: string; help?: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-muted-foreground text-xs">{help ? <TermLabel help={help}>{label}</TermLabel> : label}</dt>
      <dd className="text-sm font-medium">{children}</dd>
    </div>
  )
}

/**
 * Reads `AnalysisResult.goals[]` (Phase 7's own output) only for the goal
 * cards themselves. Feasibility comes straight from the API's
 * `feasibility` field (section 23) — never recomputed; the progress bar
 * uses `monte_carlo_success_probability` directly (already an
 * authoritative [0,1] fraction from the API), never a ratio derived from
 * two other figures.
 *
 * Phase 25: also reads the existing `useProfileQuery` (`ProfileResponse.
 * goals`, the persisted goal list) to distinguish "no goal entered" from
 * "goal(s) exist but analysis hasn't evaluated them yet", and to show each
 * goal's own target date -- no new field, no new calculation.
 *
 * Plain-language presentation (`docs/DESIGN.md` section 30): each
 * feasibility status is explained in a sentence, the technical figures
 * (inflation-adjusted target, required contribution, contribution gap,
 * Monte Carlo probability) carry plain labels and help tips, and a
 * developer-facing "unavailable" reason moves to Technical details.
 */
export function GoalsPage() {
  const { profileId } = useCustomer()
  const query = useAnalysisQuery(profileId)
  const profileQuery = useProfileQuery(profileId)

  if (profileId === null) {
    return (
      <PageContainer title={TITLE} description={DESCRIPTION}>
        <NoProfileSelected />
      </PageContainer>
    )
  }

  const goals = query.data?.goals ?? []
  const enteredGoalCount = profileQuery.data?.goals.length ?? 0
  const targetDate = (goalId: number) => profileQuery.data?.goals.find((goal) => goal.id === goalId)?.target_date
  const isSavingsFirst = query.data?.recommendation?.status === "savings_first"

  return (
    <PageContainer title={TITLE} description={DESCRIPTION}>
      {query.isLoading ? (
        <LoadingState label="Checking your goals" />
      ) : query.error ? (
        <ErrorState error={query.error} onRetry={() => query.refetch()} />
      ) : goals.length === 0 ? (
        <Card>
          <CardContent className="text-muted-foreground space-y-2 pt-6 text-sm">
            <p>
              {enteredGoalCount > 0
                ? `${enteredGoalCount} ${enteredGoalCount === 1 ? "goal is" : "goals are"} recorded for this profile, but the analysis has not reviewed ${enteredGoalCount === 1 ? "it" : "them"} yet.`
                : "No financial goals have been recorded for this profile yet."}
            </p>
            <Link to="/profile" className="text-primary underline underline-offset-2">
              View recorded goals on Customer Profile
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {isSavingsFirst ? (
            <Alert>
              <AlertTriangle />
              <AlertTitle>Emergency savings come first</AlertTitle>
              <AlertDescription>
                Current savings are not sufficient for the recommended emergency savings target yet, so building
                them up is the priority before investing towards other goals.
              </AlertDescription>
            </Alert>
          ) : null}
          <div className="grid gap-4 sm:grid-cols-2">
            {goals.map((goal) => {
              const date = targetDate(goal.goal_id)
              const feasibilityText = getFeasibilityExplanation(goal.feasibility)
              return (
                <Card key={goal.goal_id}>
                  <CardHeader>
                    <div className="flex items-start justify-between gap-2">
                      <CardTitle>{goal.goal_type}</CardTitle>
                      <StatusBadge status={goal.feasibility} />
                    </div>
                    {feasibilityText ? <CardDescription>{feasibilityText}</CardDescription> : null}
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <dl className="grid grid-cols-2 gap-3">
                      <Figure label="Target amount">{formatCurrency(goal.nominal_target_amount)}</Figure>
                      <Figure label="Target date">{date ? formatDate(date) : "Not available"}</Figure>
                      <Figure label="Target after inflation" help={HELP.inflationAdjusted}>
                        {formatCurrency(goal.inflation_adjusted_target_amount)}
                      </Figure>
                      <Figure label="Required regular contribution" help={HELP.requiredContribution}>
                        {formatCurrency(goal.required_periodic_contribution)}
                      </Figure>
                      <div className="col-span-2">
                        <Figure label="Difference from your planned contribution" help={HELP.contributionGap}>
                          {formatCurrency(goal.contribution_gap)}
                        </Figure>
                        {/* Presentation only: `core/goals.py` defines the gap as required minus
                            planned contribution, so a negative gap means the plan is ahead. The
                            backend value above is shown unchanged; only its sign picks this note. */}
                        {goal.contribution_gap !== null && goal.contribution_gap < 0 ? (
                          <p className="text-muted-foreground mt-0.5 text-xs">
                            Your planned contribution is more than the calculated requirement.
                          </p>
                        ) : null}
                      </div>
                    </dl>

                    {goal.unavailable_reason ? (
                      <SectionUnavailable
                        title="Some results for this goal are not available"
                        message={
                          goal.unavailable_reason.includes("GoalAssumptions")
                            ? "They could not be calculated because goal planning assumptions (monthly contribution, expected return and inflation) have not been added under Customer Profile → Financial Inputs. No values are assumed."
                            : "They could not be calculated with the information available. No values are assumed."
                        }
                        reason={goal.unavailable_reason}
                      />
                    ) : null}
                    {!goal.unavailable_reason || goal.inflation_adjusted_target_amount !== null ? (
                      <GoalTargetChart
                        goalType={goal.goal_type}
                        nominalTarget={goal.nominal_target_amount}
                        inflationAdjustedTarget={goal.inflation_adjusted_target_amount}
                      />
                    ) : null}

                    {goal.monte_carlo_success_probability !== null &&
                    goal.monte_carlo_success_probability !== undefined ? (
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between gap-2 text-sm">
                          <span className="text-muted-foreground">
                            <TermLabel help={HELP.goalChance}>Estimated chance of reaching this goal</TermLabel>
                          </span>
                          <span className="font-medium">
                            {formatPercent(goal.monte_carlo_success_probability, 1)}
                          </span>
                        </div>
                        <Progress
                          value={goal.monte_carlo_success_probability * 100}
                          aria-label={`${goal.goal_type}: estimated chance of reaching the goal`}
                        />
                      </div>
                    ) : null}

                    {goal.already_achieved ? <Badge variant="default">Already achieved</Badge> : null}

                    <TechnicalDetails
                      items={[
                        { label: "Feasibility (API value)", value: goal.feasibility },
                        { label: "Monte Carlo success probability", value: goal.monte_carlo_success_probability },
                        { label: "Inflation-adjusted target", value: goal.inflation_adjusted_target_amount },
                        { label: "Required periodic contribution", value: goal.required_periodic_contribution },
                        { label: "Contribution gap", value: goal.contribution_gap },
                        { label: "Goal id", value: goal.goal_id },
                      ]}
                    />
                  </CardContent>
                </Card>
              )
            })}
          </div>
        </div>
      )}
    </PageContainer>
  )
}
