import { HandCoins, Home, Landmark } from "lucide-react"
import { Link } from "react-router"

import { ErrorState } from "@/components/shell/error-state"
import { TermLabel } from "@/components/shell/help-tip"
import { LoadingState } from "@/components/shell/loading-state"
import { SectionUnavailable } from "@/components/shell/section-unavailable"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useFinancialInputsQuery } from "@/hooks/use-financial-inputs"
import { useProfileHouseholdQuery } from "@/hooks/use-household"
import { useProfileQuery } from "@/hooks/use-profile"
import { formatCurrency } from "@/lib/format"
import { HELP } from "@/lib/terminology"

function stored(value: number | null | undefined): string {
  return value === null || value === undefined ? "Not provided" : formatCurrency(value)
}

/**
 * The individual's own stored income, expense and savings figures on
 * Financial Health -- display only. Every value is read as-is from
 * `GET /api/profiles/{id}` (`income`, annual) and
 * `GET /api/profiles/{id}/financial-inputs` (`monthly_essential_expenses`,
 * `current_liquid_assets`); nothing is converted, totalled or compared, and
 * an absent value reads "Not provided", never 0.
 *
 * WealthPilot stores no individual debts and no full individual spending,
 * and the backend computes no individual cash flow or net position (those
 * exist only for a household, from its own records -- ADR-033). This card
 * says so instead of deriving one.
 */
export function IndividualFinancesCard({ profileId }: { profileId: number }) {
  const profile = useProfileQuery(profileId)
  const inputs = useFinancialInputsQuery(profileId)
  const missing =
    inputs.data?.monthly_essential_expenses === null || inputs.data?.current_liquid_assets === null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <HandCoins className="text-muted-foreground size-4" aria-hidden="true" /> Financial snapshot
        </CardTitle>
        <CardDescription>The figures stored for this profile, shown exactly as recorded.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {profile.isLoading || inputs.isLoading ? (
          <LoadingState label="Loading your financial information" />
        ) : profile.error || inputs.error ? (
          <ErrorState
            error={profile.error ?? inputs.error}
            onRetry={() => {
              profile.refetch()
              inputs.refetch()
            }}
          />
        ) : (
          <>
            <dl className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-0.5">
                <dt className="text-muted-foreground text-xs">Annual income</dt>
                <dd className="text-sm font-medium">{stored(profile.data?.income)}</dd>
              </div>
              <div className="space-y-0.5">
                <dt className="text-muted-foreground text-xs">Essential spending (per month)</dt>
                <dd className="text-sm font-medium">{stored(inputs.data?.monthly_essential_expenses)}</dd>
              </div>
              <div className="space-y-0.5">
                <dt className="text-muted-foreground text-xs">
                  <TermLabel help={HELP.emergencySavings}>Easy-access savings</TermLabel>
                </dt>
                <dd className="text-sm font-medium">{stored(inputs.data?.current_liquid_assets)}</dd>
              </div>
            </dl>
            {missing ? (
              <p className="text-muted-foreground text-sm">
                Some figures have not been provided. You can add them under{" "}
                <Link to="/profile" className="text-primary underline underline-offset-2">
                  Customer Profile → Your financial information
                </Link>
                .
              </p>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  )
}

/**
 * Debt and commitments for an INDIVIDUAL: WealthPilot has no individual debt or EMI record (ADR-033: loans and EMIs exist only as a household's own liabilities), so this is a
 * feature the application does not have, not a value that is missing. It says so plainly instead of showing an invented or zero value. A member of a household is pointed to the
 * household's own liabilities, which are NOT shown here, so individual and household figures stay apart.
 */
export function CommitmentsView({ householdName }: { householdName: string | null }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Landmark className="text-muted-foreground size-4" aria-hidden="true" /> Debt &amp; Commitments
        </CardTitle>
        <CardDescription>Loans, EMIs and other regular financial obligations.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <SectionUnavailable
          title="Not recorded for an individual"
          message="WealthPilot does not record loans or EMIs for an individual, so none are shown and none are assumed."
        />
        {householdName ? (
          <p className="text-sm">
            The “{householdName}” household records its own loans and EMIs (liabilities, with their monthly payments). They are listed on{" "}
            <Link to="/profile?household=open" className="text-primary underline underline-offset-2">
              Customer Profile → Household → Liabilities
            </Link>{" "}
            and are not part of this individual view.
          </p>
        ) : null}
      </CardContent>
    </Card>
  )
}

export function CommitmentsCard({ profileId }: { profileId: number }) {
  const household = useProfileHouseholdQuery(profileId)
  return <CommitmentsView householdName={household.data?.household?.name ?? null} />
}

/**
 * For a household member: points to the household's own financial summary
 * (Customer Profile → Household) without showing any household figure here,
 * so individual and household values are never mixed on this page.
 */
export function HouseholdFinancesPointer({ profileId }: { profileId: number }) {
  const query = useProfileHouseholdQuery(profileId)
  const household = query.data?.household
  if (!household) return null
  return (
    <Alert>
      <Home />
      <AlertTitle>Household finances are shown separately</AlertTitle>
      <AlertDescription className="space-y-1">
        <p>
          You belong to the “{household.name}” household. Its income, spending, cash flow, emergency savings, assets,
          liabilities and net position come from the household's own records and are summarised on Customer Profile —
          they are not part of this individual view.
        </p>
        <Link to="/profile?household=open" className="text-primary text-sm underline underline-offset-2">
          View the household financial summary
        </Link>
      </AlertDescription>
    </Alert>
  )
}
