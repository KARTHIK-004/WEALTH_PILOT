import { AlertTriangle } from "lucide-react"

import { EmergencyFundChart } from "@/components/charts/emergency-fund-chart"
import { HouseholdFinancesPointer, IndividualFinancesCard } from "@/components/financial-health/individual-finances"
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
import { useAnalysisQuery } from "@/hooks/use-analysis"
import { formatCurrency } from "@/lib/format"
import { HELP } from "@/lib/terminology"
import { useCustomer } from "@/providers/customer-context"

const DESCRIPTION = "A simple view of your spending, savings, emergency fund, and financial position."

/** One labelled yes/no signal from the backend, worded plainly. `null`
 * stays "Not available" -- never shown as "no". */
function Signal({ label, value, yes, no }: { label: string; value: boolean | null | undefined; yes: string; no: string }) {
  return (
    <div className="space-y-1">
      <p className="text-muted-foreground text-xs">{label}</p>
      {value === null || value === undefined ? (
        <Badge variant="outline">Not available</Badge>
      ) : (
        <Badge variant={value ? "secondary" : "outline"}>{value ? yes : no}</Badge>
      )}
    </div>
  )
}

/**
 * Reads only `AnalysisResult.financial_health`/`.emergency_fund`/
 * `.recommendation.status` — never fabricates income/expense/savings for
 * a FAR-Trans customer (section 18: FAR-Trans has no such fields at all,
 * and the API itself never invents them either).
 *
 * Plain-language presentation (`docs/DESIGN.md` section 30): "Spending
 * pattern", "Recent behaviour changes" and "Unusual activity" instead of
 * expense clustering, behaviour drift and the isolation-forest anomaly flag;
 * "Emergency savings" instead of emergency-fund jargon. An unavailable
 * spending pattern says so in plain words, and the backend's own
 * (developer-facing) reason moves to Technical details -- it is never
 * hidden, and no segment is ever invented. The reason is ADR-010: the
 * expense model's Kaggle population is never applied to a FAR-Trans-linked
 * profile, even one whose own income/expense inputs are stored.
 *
 * `IndividualFinancesCard` shows the profile's own stored income, expense and
 * savings figures; `HouseholdFinancesPointer` links a household member to the
 * household's separate summary without mixing any household figure in here.
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

  const health = query.data?.financial_health
  const emergencyFund = query.data?.emergency_fund
  const isSavingsFirst = query.data?.recommendation?.status === "savings_first"

  return (
    <PageContainer title="Financial Health" description={DESCRIPTION}>
      {query.isLoading ? (
        <LoadingState label="Reviewing your financial information" />
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

          <IndividualFinancesCard profileId={profileId} />

          <Card>
            <CardHeader>
              <CardTitle>Spending and behaviour</CardTitle>
              <CardDescription>Your spending pattern and any recent changes in your financial behaviour.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {!health || Object.keys(health).length === 0 ? (
                <SectionUnavailable
                  message="This part of the analysis has not run for this profile yet, so there is nothing to show. No values are assumed."
                  reason={query.data?.status ? `Analysis status: ${query.data.status}` : undefined}
                />
              ) : (
                <>
                  <div className="space-y-1">
                    <p className="text-muted-foreground text-xs">Spending pattern</p>
                    {health.expense_persona ? (
                      <Badge variant="outline">{health.expense_persona}</Badge>
                    ) : (
                      <SectionUnavailable
                        title="Expense insights unavailable"
                        message="The spending-pattern model was built from a separate dataset and, by design, is not applied to this profile's records. No spending pattern is assumed."
                        reason={health.expense_persona_unavailable_reason}
                      />
                    )}
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Signal
                      label="Recent behaviour changes"
                      value={health.behaviour_drift_flag}
                      yes="A significant change was detected"
                      no="No significant change detected"
                    />
                    <Signal
                      label="Unusual activity"
                      value={health.isolation_forest_anomaly}
                      yes="Unusual activity detected"
                      no="No unusual activity detected"
                    />
                  </div>
                  <TechnicalDetails
                    items={[
                      { label: "Behaviour drift detection (flag)", value: String(health.behaviour_drift_flag ?? "null") },
                      { label: "Isolation-forest anomaly (flag)", value: String(health.isolation_forest_anomaly ?? "null") },
                      { label: "Expense persona (clustering)", value: health.expense_persona ?? "null (unavailable)" },
                      { label: "Model version", value: health.model_version },
                      { label: "Model artifact (data source)", value: health.data_source },
                    ]}
                  />
                </>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>
                <TermLabel help={HELP.emergencySavings}>Emergency savings</TermLabel>
              </CardTitle>
              <CardDescription>
                Money set aside to help cover essential expenses during unexpected situations.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {!emergencyFund || emergencyFund.sufficient === null || emergencyFund.sufficient === undefined ? (
                <SectionUnavailable
                  title="Emergency savings not checked"
                  message="Your emergency savings could not be checked, because your essential monthly expenses and available savings have not been provided. No amounts are assumed."
                  reason={emergencyFund?.unavailable_reason}
                />
              ) : (
                <>
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge status={emergencyFund.sufficient ? "sufficient" : "insufficient"} />
                    <p className="text-sm">
                      {emergencyFund.sufficient
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
        </div>
      )}
    </PageContainer>
  )
}
