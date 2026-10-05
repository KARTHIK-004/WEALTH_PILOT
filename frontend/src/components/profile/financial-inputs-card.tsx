import { CheckCircle2, HandCoins } from "lucide-react"
import { useEffect, useState } from "react"

import { ErrorState } from "@/components/shell/error-state"
import { LoadingState } from "@/components/shell/loading-state"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { useFinancialInputsQuery, useUpdateFinancialInputs } from "@/hooks/use-financial-inputs"

/** Numeric text-input state: kept as a string (never a parsed number) so
 * an empty field, a partially-typed value, and "0" are all distinguishable
 * on screen -- parsing happens only at submit time. `null`/missing from
 * the API becomes `""` (an unfilled field), never `"0"` (section 5/29 of
 * the Phase 28 prompt: never silently substitute zero for unknown). */
function toFieldValue(n: number | null | undefined): string {
  return n === null || n === undefined ? "" : String(n)
}

/** Phase 28 — the financial-input data contract's ONE frontend surface
 * (section 7: "add them to the appropriate existing... customer
 * -information flow" -- this card lives on the existing Customer Profile
 * page, `pages/profile-page.tsx`, not a new page or a large new
 * dashboard). Every field maps 1:1 to `core/goals.py`'s own required
 * parameters (`assess_emergency_fund`'s `monthly_essential_expenses`/
 * `current_liquid_assets`, `GoalAssumptions`'s `contribution_amount`/
 * `annual_return_rate`/`annual_inflation_rate`/
 * `contribution_periods_per_year`) -- nothing here is calculated in
 * React (section 29): this form only collects and validates raw numbers
 * (required-field/numeric-format/obvious-invalid-value checks only,
 * mirroring the exact bounds `FinancialInputsUpdate` itself enforces
 * server-side), then submits them verbatim via `PUT
 * /api/profiles/{id}/financial-inputs`. Every downstream calculation
 * (emergency-fund sufficiency, shortfall, required contribution,
 * feasibility) still happens exclusively in `core/goals.py`, read back
 * from the next `GET`/`POST /api/analysis` response like any other
 * result.
 *
 * A partial submission is a valid, supported state: any field left blank
 * is omitted from the `PUT` body entirely (not sent as `0`), so it stays
 * whatever it already was -- matching the endpoint's own merge-not-replace
 * semantics (see `FinancialInputsUpdate`'s own docstring).
 */
export function FinancialInputsCard({ profileId }: { profileId: number }) {
  const query = useFinancialInputsQuery(profileId)
  const mutation = useUpdateFinancialInputs(profileId)

  const [monthlyExpenses, setMonthlyExpenses] = useState("")
  const [liquidAssets, setLiquidAssets] = useState("")
  const [contributionAmount, setContributionAmount] = useState("")
  const [returnRate, setReturnRate] = useState("")
  const [inflationRate, setInflationRate] = useState("")
  const [periodsPerYear, setPeriodsPerYear] = useState("")
  const [formError, setFormError] = useState<string | null>(null)

  // Seed the form from the server's current values once loaded -- never
  // overwrites values the user is actively editing on a background
  // refetch (only runs when the query transitions into `success`).
  useEffect(() => {
    if (!query.data) return
    setMonthlyExpenses(toFieldValue(query.data.monthly_essential_expenses))
    setLiquidAssets(toFieldValue(query.data.current_liquid_assets))
    setContributionAmount(toFieldValue(query.data.contribution_amount))
    setReturnRate(toFieldValue(query.data.annual_return_rate))
    setInflationRate(toFieldValue(query.data.annual_inflation_rate))
    setPeriodsPerYear(toFieldValue(query.data.contribution_periods_per_year))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.data?.updated_at])

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    setFormError(null)
    mutation.reset()

    const parseOptional = (raw: string): number | undefined => {
      if (raw.trim() === "") return undefined
      return Number(raw)
    }

    const monthly = parseOptional(monthlyExpenses)
    const liquid = parseOptional(liquidAssets)
    const contribution = parseOptional(contributionAmount)
    const annualReturn = parseOptional(returnRate)
    const annualInflation = parseOptional(inflationRate)
    const periods = parseOptional(periodsPerYear)

    for (const [label, value] of [
      ["Monthly essential expenses", monthly],
      ["Current liquid assets", liquid],
      ["Contribution amount", contribution],
    ] as const) {
      if (value !== undefined && (!Number.isFinite(value) || value < 0)) {
        setFormError(`${label} must be a number that is 0 or greater.`)
        return
      }
    }
    for (const [label, value] of [
      ["Expected annual return", annualReturn],
      ["Expected annual inflation", annualInflation],
    ] as const) {
      if (value !== undefined && (!Number.isFinite(value) || value <= -1)) {
        setFormError(`${label} must be a number greater than -100%.`)
        return
      }
    }
    if (periods !== undefined && (!Number.isInteger(periods) || periods <= 0)) {
      setFormError("Contribution periods per year must be a whole number greater than 0.")
      return
    }

    mutation.mutate({
      ...(monthly !== undefined ? { monthly_essential_expenses: monthly } : {}),
      ...(liquid !== undefined ? { current_liquid_assets: liquid } : {}),
      ...(contribution !== undefined ? { contribution_amount: contribution } : {}),
      ...(annualReturn !== undefined ? { annual_return_rate: annualReturn } : {}),
      ...(annualInflation !== undefined ? { annual_inflation_rate: annualInflation } : {}),
      ...(periods !== undefined ? { contribution_periods_per_year: periods } : {}),
    })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <HandCoins className="text-muted-foreground size-4" /> Your financial information
        </CardTitle>
        <CardDescription>
          Used to check your emergency savings (Financial Health) and your goals. Leave a field
          blank if you don't know it yet — the analysis will show that result as not available
          rather than guessing.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {query.isLoading ? (
          <LoadingState label="Loading financial inputs" />
        ) : query.error ? (
          <ErrorState error={query.error} onRetry={() => query.refetch()} />
        ) : (
          <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
            {formError ? (
              <Alert variant="destructive">
                <AlertDescription>{formError}</AlertDescription>
              </Alert>
            ) : null}
            {mutation.isError ? <ErrorState error={mutation.error} onRetry={() => mutation.reset()} /> : null}
            {mutation.isSuccess ? (
              <Alert>
                <CheckCircle2 />
                <AlertTitle>Financial information saved</AlertTitle>
                <AlertDescription>
                  Your next analysis will use these values.
                </AlertDescription>
              </Alert>
            ) : null}

            <FieldGroup>
              <Field className="@md/field-group:flex-row @md/field-group:*:flex-1" orientation="responsive">
                <Field>
                  <FieldLabel htmlFor="fi-monthly-expenses">Monthly essential expenses</FieldLabel>
                  <Input
                    id="fi-monthly-expenses"
                    placeholder="Not provided"
                    type="number"
                    inputMode="decimal"
                    min={0}
                    step="0.01"
                    value={monthlyExpenses}
                    onChange={(event) => setMonthlyExpenses(event.target.value)}
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="fi-liquid-assets">Savings you can access quickly</FieldLabel>
                  <Input
                    id="fi-liquid-assets"
                    placeholder="Not provided"
                    type="number"
                    inputMode="decimal"
                    min={0}
                    step="0.01"
                    value={liquidAssets}
                    onChange={(event) => setLiquidAssets(event.target.value)}
                  />
                  <FieldDescription>Cash and cash-equivalent savings, not invested assets.</FieldDescription>
                </Field>
              </Field>

              <Field className="@md/field-group:flex-row @md/field-group:*:flex-1" orientation="responsive">
                <Field>
                  <FieldLabel htmlFor="fi-contribution">Monthly contribution amount</FieldLabel>
                  <Input
                    id="fi-contribution"
                    placeholder="Not provided"
                    type="number"
                    inputMode="decimal"
                    min={0}
                    step="0.01"
                    value={contributionAmount}
                    onChange={(event) => setContributionAmount(event.target.value)}
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="fi-periods">Contribution periods per year</FieldLabel>
                  <Input
                    id="fi-periods"
                    placeholder="Not provided"
                    type="number"
                    inputMode="numeric"
                    min={1}
                    step={1}
                    value={periodsPerYear}
                    onChange={(event) => setPeriodsPerYear(event.target.value)}
                  />
                  <FieldDescription>Defaults to 12 (monthly) if left blank.</FieldDescription>
                </Field>
              </Field>

              <Field className="@md/field-group:flex-row @md/field-group:*:flex-1" orientation="responsive">
                <Field>
                  <FieldLabel htmlFor="fi-return-rate">Expected annual return</FieldLabel>
                  <Input
                    id="fi-return-rate"
                    placeholder="Not provided"
                    type="number"
                    inputMode="decimal"
                    step="0.01"
                    value={returnRate}
                    onChange={(event) => setReturnRate(event.target.value)}
                  />
                  <FieldDescription>As a decimal — 0.07 means 7%.</FieldDescription>
                </Field>
                <Field>
                  <FieldLabel htmlFor="fi-inflation-rate">Expected annual inflation</FieldLabel>
                  <Input
                    id="fi-inflation-rate"
                    placeholder="Not provided"
                    type="number"
                    inputMode="decimal"
                    step="0.01"
                    value={inflationRate}
                    onChange={(event) => setInflationRate(event.target.value)}
                  />
                  <FieldDescription>As a decimal — 0.03 means 3%.</FieldDescription>
                </Field>
              </Field>
            </FieldGroup>

            <Button type="submit" variant="outline" className="self-start" disabled={mutation.isPending}>
              {mutation.isPending ? "Saving…" : "Save financial information"}
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  )
}
