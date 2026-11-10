import { CircleCheck, CircleDashed, ClipboardList, Gauge, HandCoins, ListChecks, Target, UserRound } from "lucide-react"
import { Link } from "react-router"

import { FinancialInputsCard } from "@/components/profile/financial-inputs-card"
import { HouseholdCard } from "@/components/profile/household-card"
import { MonthlyRecordsCard } from "@/components/profile/monthly-records-card"
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
import { Skeleton } from "@/components/ui/skeleton"
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

/** Skeleton shaped like the final layout (summary card, then a two-column grid). */
function ProfileSkeleton() {
  return (
    <div className="space-y-4" role="status" aria-live="polite">
      <span className="sr-only">Loading profile…</span>
      <Skeleton className="h-28 w-full" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Skeleton className="h-44 w-full" />
        <Skeleton className="h-44 w-full" />
        <Skeleton className="h-44 w-full" />
        <Skeleton className="h-44 w-full" />
      </div>
    </div>
  )
}

/** One row of "Information used for your analysis": always an icon AND a
 * text label, so status is never carried by the icon alone. */
function AvailabilityRow({ label, available, detail }: { label: string; available: boolean; detail?: string }) {
  const Icon = available ? CircleCheck : CircleDashed
  return (
    <li className="flex items-start gap-2 text-sm">
      <Icon className={available ? "text-foreground mt-0.5 size-4 shrink-0" : "text-muted-foreground mt-0.5 size-4 shrink-0"} aria-hidden="true" />
      <span>
        <span className="font-medium">{label}</span>
        <span className="text-muted-foreground"> — {available ? (detail ?? "Available") : "Not available yet"}</span>
      </span>
    </li>
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
            <Button variant="outline" nativeButton={false} render={<Link to="/onboarding/questionnaire" state={{ from: "/profile" }} />}>
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
  const answersQuery = useQuestionnaireAnswersQuery(profileId)

  if (profileId === null) {
    return (
      <PageContainer title="Customer Profile" description="Review the information WealthPilot is using for your analysis.">
        <NoProfileSelected />
      </PageContainer>
    )
  }

  const initial = query.data?.name?.trim()?.charAt(0)?.toUpperCase()

  return (
    <PageContainer title="Customer Profile" description="Review the information WealthPilot is using for your analysis.">
      {query.isLoading ? (
        <ProfileSkeleton />
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
          {/* Profile summary — who this profile is, in one glance. Only
              fields the profile/analysis APIs return; nothing invented. */}
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center gap-3">
                <div
                  className="bg-primary text-primary-foreground flex size-11 shrink-0 items-center justify-center rounded-full text-base font-semibold"
                  aria-hidden="true"
                >
                  {initial ?? "?"}
                </div>
                <div className="min-w-48 flex-1 basis-48">
                  <CardTitle className="text-base">{query.data.name}</CardTitle>
                  <CardDescription>
                    {getCustomerTypeDisplayName(query.data.customer_type)
                      ? `${getCustomerTypeDisplayName(query.data.customer_type)} customer profile`
                      : "Your WealthPilot profile"}
                    {query.data.created_at ? ` · Customer since ${formatDate(query.data.created_at)}` : ""}
                  </CardDescription>
                </div>
                {analysisQuery.data?.status ? (
                  <div className="flex w-full flex-col items-start gap-1 sm:w-auto sm:items-end">
                    <StatusBadge status={analysisQuery.data.status} />
                    <span className="text-muted-foreground text-xs">Latest analysis</span>
                  </div>
                ) : null}
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground text-sm">
                This is the information WealthPilot currently holds about you. Anything marked “Not available”
                has not been provided yet, and nothing is assumed in its place.
              </p>
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
          {/* Personal information */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <UserRound className="text-muted-foreground size-4" aria-hidden="true" /> Personal information
              </CardTitle>
              <CardDescription>The basics on your profile.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <Field label="Name" value={query.data.name} />
              <Field label="Age" value={query.data.age} />
              <Field label="Employment status" value={query.data.employment_status} />
              <Field label="Customer type" value={getCustomerTypeDisplayName(query.data.customer_type)} help={HELP.customerType} />
              <Field label="Profile created" value={formatDate(query.data.created_at)} />
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
            <CardContent className="grid gap-4 sm:grid-cols-2">
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
                <SectionUnavailable
                  title="Risk profile not available yet"
                  message="The risk assessment needs investment-history information that is not available for this profile yet. No risk profile is assumed."
                  reason={analysisQuery.data?.risk?.unavailable_reason}
                />
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

          {/* Information used for the analysis — which areas have data, from
              what the APIs actually returned. No score, no percentage. */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ListChecks className="text-muted-foreground size-4" aria-hidden="true" /> Information used for your analysis
              </CardTitle>
              <CardDescription>What WealthPilot has on file for each area.</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2">
                <AvailabilityRow label="Profile information" available />
                <AvailabilityRow
                  label="Financial information"
                  available={
                    financialInputsQuery.data != null &&
                    (financialInputsQuery.data.monthly_essential_expenses != null ||
                      financialInputsQuery.data.current_liquid_assets != null)
                  }
                  detail="Spending or savings provided"
                />
                <AvailabilityRow
                  label="Goals"
                  available={query.data.goals.length > 0}
                  detail={`${query.data.goals.length} recorded`}
                />
                <AvailabilityRow
                  label="Questionnaire answers"
                  available={(answersQuery.data?.answers.length ?? 0) > 0}
                  detail={`${answersQuery.data?.answers.length ?? 0} saved`}
                />
                <AvailabilityRow label="Risk information" available={Boolean(analysisQuery.data?.risk?.risk_category)} />
              </ul>
            </CardContent>
          </Card>
          </div>

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

          <MonthlyRecordsCard profileId={query.data.customer_id} />

          <QuestionnaireCard profileId={query.data.customer_id} />

          <TechnicalDetails
            title="Technical details"
            items={[
              { label: "Customer ID", value: query.data.customer_id },
              { label: "Customer type code", value: query.data.customer_type },
              { label: "Investment capacity code", value: query.data.investment_capacity },
              { label: "Profile data source", value: query.data.data_source },
              { label: "Latest analysis ID", value: analysisQuery.data?.analysis_id },
              { label: "Risk category", value: analysisQuery.data?.risk?.risk_category },
              { label: "Risk model version", value: analysisQuery.data?.risk?.model_version },
              { label: "Risk data source", value: analysisQuery.data?.risk?.data_source },
            ]}
          />
        </div>
      )}
    </PageContainer>
  )
}
