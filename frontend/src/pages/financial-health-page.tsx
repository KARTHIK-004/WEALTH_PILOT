import { Activity, AlertTriangle, LineChart, CircleCheck, ListChecks, PiggyBank, ShieldCheck, Wallet } from "lucide-react"
import type { ReactNode } from "react"

import { EmergencyFundChart } from "@/components/charts/emergency-fund-chart"
import { BehaviourSummaryCard } from "@/components/financial-health/behaviour-summary-card"
import { SpendingFromRecords } from "@/components/financial-health/spending-from-records"
import {
  CommitmentsCard,
  HouseholdFinancesPointer,
  IndividualFinancesCard,
} from "@/components/financial-health/individual-finances"
import { ErrorState } from "@/components/shell/error-state"
import { TermLabel } from "@/components/shell/help-tip"
import { NoProfileSelected } from "@/components/shell/no-profile-selected"
import { PageContainer } from "@/components/shell/page-container"
import { SectionUnavailable } from "@/components/shell/section-unavailable"
import { StatusBadge } from "@/components/shell/status-badge"
import { TechnicalDetails } from "@/components/shell/technical-details"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { useAnalysisQuery } from "@/hooks/use-analysis"
import { formatCurrency } from "@/lib/format"
import { HELP } from "@/lib/terminology"
import { useCustomer } from "@/providers/customer-context"

const DESCRIPTION =
  "Understand your current financial position and the factors affecting your financial decisions."

/** Skeleton shaped like the final layout. */
function FinancialHealthSkeleton() {
  return (
    <div className="space-y-4" role="status" aria-live="polite">
      <span className="sr-only">Reviewing your financial information…</span>
      <Skeleton className="h-40 w-full" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-36 w-full" />
        <Skeleton className="h-36 w-full" />
      </div>
      <Skeleton className="h-52 w-full" />
    </div>
  )
}

/** One row in a good / needs-attention list: icon plus text, never icon alone. */
function Point({ children, positive }: { children: ReactNode; positive: boolean }) {
  const Icon = positive ? CircleCheck : AlertTriangle
  return (
    <li className="flex items-start gap-2 text-sm">
      <Icon className={positive ? "mt-0.5 size-4 shrink-0" : "text-muted-foreground mt-0.5 size-4 shrink-0"} aria-hidden="true" />
      <span>{children}</span>
    </li>
  )
}

/** One health factor: a title, a status in words, and a short explanation.
 * `value` null/undefined is "Not available" -- never shown as "no". */
function Factor({
  icon: Icon,
  title,
  status,
  children,
}: {
  icon: typeof Activity
  title: string
  status: ReactNode
  children: ReactNode
}) {
  return (
    <div className="space-y-2 rounded-md border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-2 text-sm font-medium">
          <Icon className="text-muted-foreground size-4" aria-hidden="true" /> {title}
        </p>
        {status}
      </div>
      <div className="text-muted-foreground text-sm">{children}</div>
    </div>
  )
}

function FlagStatus({ value, yes, no }: { value: boolean | null | undefined; yes: string; no: string }) {
  if (value === null || value === undefined) return <Badge variant="outline">Not available</Badge>
  return <Badge variant={value ? "secondary" : "outline"}>{value ? yes : no}</Badge>
}

/**
 * Presentation only. Reads `AnalysisResult.financial_health` /
 * `.emergency_fund` / `.explanation` / `.recommendation.status` and the
 * profile's stored figures; nothing is calculated, totalled or compared in
 * React, no score or threshold is created, and an unavailable value reads
 * "Not available" with the reason in Technical details. FAR-Trans has no
 * expense data and the expense model is never applied to a FAR-Trans
 * profile (ADR-010), so an unavailable spending pattern is expected.
 */
export function FinancialHealthPage() {
  const { profileId } = useCustomer()
  const query = useAnalysisQuery(profileId)

  if (profileId === null) {
    return (
      <PageContainer title="Financial Health" description={DESCRIPTION}>
        <NoProfileSelected />
      </PageContainer>
    )
  }

  const analysis = query.data
  const health = analysis?.financial_health
  const emergencyFund = analysis?.emergency_fund
  const sufficient = emergencyFund?.sufficient
  const hasEmergency = sufficient === true || sufficient === false
  const isSavingsFirst = analysis?.recommendation?.status === "savings_first"
  const drift = health?.behaviour_drift_flag
  const anomaly = health?.isolation_forest_anomaly

  const positives: string[] = []
  const attention: string[] = []
  if (sufficient === true) positives.push("Your easy-access savings meet the emergency target.")
  if (sufficient === false) attention.push("Your easy-access savings are below the emergency target.")
  if (drift === false) positives.push("No significant recent change in your financial behaviour.")
  if (drift === true) attention.push("A significant recent change in your financial behaviour was detected.")
  if (anomaly === false) positives.push("No unusual activity was detected.")
  if (anomaly === true) attention.push("Unusual activity was detected.")

  const meaning = analysis?.explanation?.financial_health_explanation
  const fallbackMeaning =
    sufficient === true
      ? "Your easy-access savings currently meet the emergency target, which gives your plan a reasonable foundation."
      : sufficient === false
        ? "Your easy-access savings are currently below the emergency target, so building them up comes before a normal investment plan."
        : "Your emergency savings could not be checked yet, because some information has not been provided. Nothing is assumed in its place."

  return (
    <PageContainer title="Financial Health" description={DESCRIPTION}>
      {query.isLoading ? (
        <FinancialHealthSkeleton />
      ) : query.error ? (
        <ErrorState error={query.error} onRetry={() => query.refetch()} />
      ) : (
        <div className="space-y-4">
          <HouseholdFinancesPointer profileId={profileId} />
          {isSavingsFirst ? (
            <Alert>
              <AlertTriangle />
              <AlertTitle>Savings first</AlertTitle>
              <AlertDescription>
                Building your emergency savings takes priority over a normal investment recommendation right now.
              </AlertDescription>
            </Alert>
          ) : null}

          {/* Summary — headline from the existing emergency-savings result and
              plain restatements of existing flags; no new score. */}
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-48 flex-1 basis-48 space-y-1">
                  <CardTitle className="flex items-center gap-2">
                    <ShieldCheck className="text-muted-foreground size-4" aria-hidden="true" /> Your financial health summary
                  </CardTitle>
                  <CardDescription>
                    {hasEmergency
                      ? sufficient
                        ? "Your emergency savings meet the current target."
                        : "Your emergency savings are below the current target."
                      : "Your emergency savings could not be checked yet."}
                  </CardDescription>
                </div>
                <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
                  {hasEmergency ? (
                    <StatusBadge status={sufficient ? "sufficient" : "insufficient"} />
                  ) : (
                    <Badge variant="outline">Emergency savings: Not available</Badge>
                  )}
                  {analysis?.status ? <StatusBadge status={analysis.status} /> : null}
                </div>
              </div>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <h2 className="text-sm font-medium">What looks good</h2>
                {positives.length ? (
                  <ul className="space-y-1.5">
                    {positives.map((t) => (
                      <Point key={t} positive>
                        {t}
                      </Point>
                    ))}
                  </ul>
                ) : (
                  <p className="text-muted-foreground text-sm">Nothing to highlight yet.</p>
                )}
              </div>
              <div className="space-y-2">
                <h2 className="text-sm font-medium">What needs attention</h2>
                {attention.length ? (
                  <ul className="space-y-1.5">
                    {attention.map((t) => (
                      <Point key={t} positive={false}>
                        {t}
                      </Point>
                    ))}
                  </ul>
                ) : (
                  <p className="text-muted-foreground text-sm">Nothing needs attention right now.</p>
                )}
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <IndividualFinancesCard profileId={profileId} />

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <PiggyBank className="text-muted-foreground size-4" aria-hidden="true" />
                  <TermLabel help={HELP.emergencySavings}>Emergency savings</TermLabel>
                </CardTitle>
                <CardDescription>
                  Money set aside to help cover essential expenses during unexpected situations.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {!emergencyFund || !hasEmergency ? (
                  <SectionUnavailable
                    title="Emergency savings not checked"
                    message="Your emergency savings could not be checked, because your essential monthly expenses and available savings have not been provided. No amounts are assumed."
                    reason={emergencyFund?.unavailable_reason}
                  />
                ) : (
                  <>
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusBadge status={sufficient ? "sufficient" : "insufficient"} />
                      <p className="text-sm">
                        {sufficient
                          ? "Your emergency savings currently meet the target."
                          : "Your emergency savings are below the current target."}
                      </p>
                    </div>
                    <EmergencyFundChart
                      required={emergencyFund.required_amount}
                      current={emergencyFund.current_amount}
                      shortfall={emergencyFund.shortfall}
                      sufficient={emergencyFund.sufficient}
                      unavailableReason={emergencyFund.unavailable_reason}
                    />
                    <dl className="grid gap-3 sm:grid-cols-3">
                      <div>
                        <dt className="text-muted-foreground text-xs">Recommended target</dt>
                        <dd className="text-sm font-medium">{formatCurrency(emergencyFund.required_amount)}</dd>
                      </div>
                      <div>
                        <dt className="text-muted-foreground text-xs">Available now</dt>
                        <dd className="text-sm font-medium">{formatCurrency(emergencyFund.current_amount)}</dd>
                      </div>
                      <div>
                        <dt className="text-muted-foreground text-xs">Shortfall</dt>
                        <dd className="text-sm font-medium">{formatCurrency(emergencyFund.shortfall)}</dd>
                      </div>
                    </dl>
                  </>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Wallet className="text-muted-foreground size-4" aria-hidden="true" /> Spending and expenses
                </CardTitle>
                <CardDescription>Your spending pattern, where one is available, and what your reported months show.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {!health || Object.keys(health).length === 0 ? (
                  <SectionUnavailable
                    message="This part of the analysis has not run for this profile yet, so there is nothing to show. No values are assumed."
                    reason={analysis?.status ? `Analysis status: ${analysis.status}` : undefined}
                  />
                ) : health.expense_persona ? (
                  <div className="space-y-1">
                    <p className="text-muted-foreground text-xs">Spending pattern</p>
                    <Badge variant="outline">{health.expense_persona}</Badge>
                  </div>
                ) : (
                  <SectionUnavailable
                    title="Spending pattern not available"
                    message="A spending pattern is not available for this profile, so none is assumed."
                    reason={health.expense_persona_unavailable_reason}
                  />
                )}
                <Separator />
                <SpendingFromRecords key={profileId} profileId={profileId} />
              </CardContent>
            </Card>

            <CommitmentsCard key={profileId} profileId={profileId} />
          </div>

          <BehaviourSummaryCard key={profileId} profileId={profileId} />

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <LineChart className="text-muted-foreground size-4" aria-hidden="true" /> Investment behaviour
              </CardTitle>
              <CardDescription>How your recent investing activity compares with your own history.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              {!health || drift === null || drift === undefined ? (
                <SectionUnavailable
                  title="Behaviour analysis not available"
                  message="Investment behaviour could not be assessed for this profile, so nothing is assumed."
                />
              ) : (
                <>
                  <div className="space-y-1">
                    <p className="text-muted-foreground text-xs">Behaviour status</p>
                    <p className="text-sm font-medium">
                      {drift ? "Unusual behaviour detected" : "No unusual behaviour detected"}
                    </p>
                    <p className="text-muted-foreground text-sm">
                      {drift
                        ? "Your recent investing pattern has changed significantly compared with your earlier history."
                        : "Your recent investing pattern is consistent with your earlier history."}
                    </p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-muted-foreground text-xs">Unusual activity</p>
                    <p className="text-sm font-medium">
                      {anomaly === null || anomaly === undefined
                        ? "Not available"
                        : anomaly
                          ? "Unusual activity detected"
                          : "No unusual activity detected"}
                    </p>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ListChecks className="text-muted-foreground size-4" aria-hidden="true" /> Financial health factors
              </CardTitle>
              <CardDescription>The results behind this page, in plain language.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <Factor
                icon={PiggyBank}
                title="Emergency preparedness"
                status={
                  hasEmergency ? (
                    <StatusBadge status={sufficient ? "sufficient" : "insufficient"} />
                  ) : (
                    <Badge variant="outline">Not available</Badge>
                  )
                }
              >
                {hasEmergency
                  ? sufficient
                    ? "Easy-access savings are at or above the emergency target."
                    : "Easy-access savings are below the emergency target."
                  : "Needs your essential monthly spending and easy-access savings."}
              </Factor>
              <Factor
                icon={Wallet}
                title="Spending pattern"
                status={
                  health?.expense_persona ? (
                    <Badge variant="outline">{health.expense_persona}</Badge>
                  ) : (
                    <Badge variant="outline">Not available</Badge>
                  )
                }
              >
                A spending pattern is shown only when the spending model can be applied to this profile.
              </Factor>
              <Factor
                icon={Activity}
                title="Recent behaviour changes"
                status={<FlagStatus value={drift} yes="Change detected" no="No change detected" />}
              >
                Whether your investing behaviour has shifted significantly over time.
              </Factor>
              <Factor
                icon={AlertTriangle}
                title="Unusual activity"
                status={<FlagStatus value={anomaly} yes="Detected" no="None detected" />}
              >
                Whether anything in your activity looks unusual compared with typical patterns.
              </Factor>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>What this means</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm">{meaning ?? fallbackMeaning}</p>
              <Separator />
              <p className="text-muted-foreground text-xs">
                This restates results WealthPilot has already calculated. It is decision support, not licensed
                financial advice.
              </p>
            </CardContent>
          </Card>

          <TechnicalDetails
            items={[
              { label: "Analysis ID", value: analysis?.analysis_id },
              { label: "Analysis status", value: analysis?.status },
              { label: "Behaviour drift flag", value: health ? String(health.behaviour_drift_flag ?? "null") : undefined },
              { label: "Anomaly flag", value: health ? String(health.isolation_forest_anomaly ?? "null") : undefined },
              { label: "Expense persona", value: health ? (health.expense_persona ?? "null (unavailable)") : undefined },
              { label: "Model version", value: health?.model_version },
              { label: "Data source", value: health?.data_source },
              { label: "Evaluated at", value: analysis?.evaluated_at },
              { label: "Spending data note", value: "Expense clustering is trained on the Kaggle finance dataset; FAR-Trans is a separate, unlinked population used for risk and behaviour." },
            ]}
          />
        </div>
      )}
    </PageContainer>
  )
}

