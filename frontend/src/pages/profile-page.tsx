import { ClipboardList, Gauge, HandCoins, Target } from "lucide-react"
import { Link } from "react-router"

import { FinancialInputsCard } from "@/components/profile/financial-inputs-card"
import { HouseholdCard } from "@/components/profile/household-card"
import { ErrorState } from "@/components/shell/error-state"
import { LoadingState } from "@/components/shell/loading-state"
import { NoProfileSelected } from "@/components/shell/no-profile-selected"
import { SectionUnavailable } from "@/components/shell/section-unavailable"
import { TermLabel } from "@/components/shell/help-tip"
import { PageContainer } from "@/components/shell/page-container"
import { StatusBadge } from "@/components/shell/status-badge"
import { TechnicalDetails } from "@/components/shell/technical-details"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { useAnalysisQuery } from "@/hooks/use-analysis"
import { useFinancialInputsQuery } from "@/hooks/use-financial-inputs"
import { useProfileQuery } from "@/hooks/use-profile"
import { useQuestionnaireAnswersQuery } from "@/hooks/use-questionnaire"
import { formatCurrency, formatDate } from "@/lib/format"
import { HELP, getCapacityDisplayName, getCustomerTypeDisplayName, getRiskCategoryDescription } from "@/lib/terminology"
import { useCustomer } from "@/providers/customer-context"

function Field({ label, value, help }: { label: string; value: string | number | null | undefined; help?: string }) {
  return (
    <div className="space-y-0.5">
      <p className="text-muted-foreground text-xs">{help ? <TermLabel help={help}>{label}</TermLabel> : label}</p>
      <p className="text-sm font-medium">{value === null || value === undefined || value === "" ? "Not available" : value}</p>
    </div>
  )
}

/** Phase 31 — the one in-app way to reach the questionnaire after account
 * creation (previously `/onboarding/questionnaire` was reachable only from
 * the create-user flow). Shows only how many answers the API says are saved
 * (`GET /api/profiles/{id}/questionnaire`) and links to the existing page,
 * which preselects and can update them. Nothing is scored or inferred. */
function QuestionnaireCard({ profileId }: { profileId: number }) {
  const answersQuery = useQuestionnaireAnswersQuery(profileId)
  const savedCount = answersQuery.data?.answers.length

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ClipboardList className="text-muted-foreground size-4" /> Questionnaire
        </CardTitle>
        <CardDescription>
          Your investment-preference answers are stored with this profile. They do not change
          your risk category, which comes from the risk model.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center justify-between gap-3">
        {answersQuery.isLoading ? (
          <LoadingState label="Loading questionnaire answers" />
        ) : answersQuery.error ? (
          <ErrorState error={answersQuery.error} onRetry={() => answersQuery.refetch()} />
        ) : (
          <>
            <p className="text-sm">
              {savedCount ? `${savedCount} answer(s) saved.` : "No answers have been saved yet."}
            </p>
            <Button variant="outline" render={<Link to="/onboarding/questionnaire" state={{ from: "/profile" }} />}>
              {savedCount ? "Review or update answers" : "Answer the questionnaire"}
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  )
}

/** Displays ONLY fields the `GET /api/profiles/{id}` response actually
 * returns (section 12) — no inferred age-from-date, no fabricated field,
 * no internal-only column exposed. Reads `useAnalysisQuery`/
 * `useFinancialInputsQuery` too (unrelated redesign task), but only to
 * SHOW their already-computed values here — nothing is derived, and
 * Risk Assessment/Financial Health/Goals/Portfolio stay the pages that
 * own that detail; this page links out to them rather than duplicating
 * them. */
export function ProfilePage() {
  const { profileId } = useCustomer()
  const query = useProfileQuery(profileId)
  const analysisQuery = useAnalysisQuery(profileId)
  const financialInputsQuery = useFinancialInputsQuery(profileId)

  if (profileId === null) {
    return (
      <PageContainer title="Customer Profile" description="Your personal and financial information used by WealthPilot.">
        <NoProfileSelected />
      </PageContainer>
    )
  }

  const initial = query.data?.name?.trim()?.charAt(0)?.toUpperCase()

  return (
    <PageContainer title="Customer Profile" description="Your personal and financial information used by WealthPilot.">
      {query.isLoading ? (
        <LoadingState label="Loading profile" />
      ) : query.error ? (
        <ErrorState error={query.error} onRetry={() => query.refetch()} />
      ) : !query.data ? (
        <Card>
          <CardContent className="text-muted-foreground pt-6 text-sm">
            This profile is not available.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {/* Profile summary — identity and classification only; financial
              figures move to their own section below, so this card reads
              as "who you are" rather than one flat record. */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-3">
                <div
                  className="bg-primary text-primary-foreground flex size-11 shrink-0 items-center justify-center rounded-full text-base font-semibold"
                  aria-hidden="true"
                >
                  {initial ?? "?"}
                </div>
                <div>
                  <CardTitle className="text-base">{query.data.name}</CardTitle>
                  <CardDescription>Your WealthPilot profile</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Field label="Age" value={query.data.age} />
              <Field label="Employment status" value={query.data.employment_status} />
              <Field label="Customer type" value={getCustomerTypeDisplayName(query.data.customer_type)} help={HELP.customerType} />
              <Field label="Profile created" value={formatDate(query.data.created_at)} />
            </CardContent>
            <CardContent>
              <TechnicalDetails
                title="Profile details"
                items={[
                  { label: "Customer ID", value: query.data.customer_id },
                  { label: "Customer type code", value: query.data.customer_type },
                  { label: "Investment capacity code", value: query.data.investment_capacity },
                ]}
              />
            </CardContent>
          </Card>

          {/* Financial snapshot — a compact, read-only overview; the
              editable form with the same underlying values stays below
              (FinancialInputsCard), and the full picture stays on
              Financial Health, linked rather than duplicated. */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <HandCoins className="text-muted-foreground size-4" aria-hidden="true" /> Financial snapshot
              </CardTitle>
              <CardDescription>The income, spending and savings WealthPilot uses for your plan.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Field label="Annual income" value={query.data.income != null ? formatCurrency(query.data.income) : null} />
              <Field
                label="Essential spending"
                value={
                  financialInputsQuery.data?.monthly_essential_expenses != null
                    ? `${formatCurrency(financialInputsQuery.data.monthly_essential_expenses)} / month`
                    : null
                }
              />
              <Field
                label="Easy-access savings"
                value={
                  financialInputsQuery.data?.current_liquid_assets != null
                    ? formatCurrency(financialInputsQuery.data.current_liquid_assets)
                    : null
                }
                help={HELP.emergencySavings}
              />
              <div className="space-y-0.5">
                <p className="text-muted-foreground text-xs">
                  <TermLabel help="Whether your easy-access savings currently meet WealthPilot's emergency-fund target.">
                    Emergency savings
                  </TermLabel>
                </p>
                {analysisQuery.data?.emergency_fund?.sufficient === true ||
                analysisQuery.data?.emergency_fund?.sufficient === false ? (
                  <StatusBadge status={analysisQuery.data.emergency_fund.sufficient ? "sufficient" : "insufficient"} />
                ) : (
                  <p className="text-sm font-medium">Not available</p>
                )}
              </div>
            </CardContent>
            <CardContent>
              <Link to="/financial-health" className="text-primary text-sm underline underline-offset-2">
                View financial health
              </Link>
            </CardContent>
          </Card>

          {/* Investment comfort — a one-line summary; the full assessment
              stays on Risk Assessment, linked rather than duplicated. */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Gauge className="text-muted-foreground size-4" aria-hidden="true" />
                <TermLabel help={HELP.riskProfile}>Investment comfort level</TermLabel>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {analysisQuery.data?.risk?.risk_category ? (
                <>
                  <Badge>{analysisQuery.data.risk.risk_category}</Badge>
                  <p className="text-muted-foreground text-sm">
                    {getRiskCategoryDescription(analysisQuery.data.risk.risk_category) ?? ""}
                  </p>
                </>
              ) : (
                <SectionUnavailable reason={analysisQuery.data?.risk?.unavailable_reason} message="Not available yet" />
              )}
              {query.data.investment_capacity ? (
                <p className="flex items-center gap-1 text-sm">
                  <TermLabel help={HELP.capacityBand}>Capacity band:</TermLabel>
                  <span className="font-medium">{getCapacityDisplayName(query.data.investment_capacity)}</span>
                </p>
              ) : null}
              <Link to="/risk-assessment" className="text-primary block text-sm underline underline-offset-2">
                See your investment comfort level
              </Link>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="text-muted-foreground size-4" aria-hidden="true" /> Your goals
              </CardTitle>
              <CardDescription>
                {query.data.goals.length} {query.data.goals.length === 1 ? "goal" : "goals"} recorded for this profile.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {query.data.goals.length === 0 ? (
                <p className="text-muted-foreground text-sm">Goals haven't been added yet.</p>
              ) : (
                <ul className="space-y-3">
                  {query.data.goals.slice(0, 3).map((goal, index) => (
                    <li key={goal.id}>
                      {index > 0 ? <Separator className="mb-3" /> : null}
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div>
                          <p className="text-sm font-medium">{goal.goal_type}</p>
                          <p className="text-muted-foreground text-xs">
                            Target date {formatDate(goal.target_date)}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">Target {formatCurrency(goal.target_amount)}</Badge>
                          <Badge variant="outline">Saved so far {formatCurrency(goal.current_savings)}</Badge>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
            <CardContent>
              <Link to="/goals" className="text-primary text-sm underline underline-offset-2">
                View all goals
              </Link>
            </CardContent>
          </Card>

          <HouseholdCard profileId={query.data.customer_id} />

          <FinancialInputsCard profileId={query.data.customer_id} />

          <QuestionnaireCard profileId={query.data.customer_id} />
        </div>
      )}
    </PageContainer>
  )
}
