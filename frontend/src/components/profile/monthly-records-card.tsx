import { CalendarDays, CheckCircle2, Trash2 } from "lucide-react"
import { useState } from "react"

import { ErrorState } from "@/components/shell/error-state"
import { LoadingState } from "@/components/shell/loading-state"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useDeleteMonthlyRecord, useMonthlyRecordsQuery, useSaveMonthlyRecord } from "@/hooks/use-monthly-records"
import { formatCurrency } from "@/lib/format"
import type { components } from "@/types/api"

type MonthlyRecord = components["schemas"]["MonthlyRecordResponse"]
type MonthlyRecordUpdate = components["schemas"]["MonthlyRecordUpdate"]
type AmountField = "income" | "expenses" | "savings" | "investment_contribution"
type Basis = "net" | "gross" | null

const AMOUNT_FIELDS: { key: AmountField; label: string; help: string }[] = [
  { key: "income", label: "Income this month", help: "Money received in the month." },
  {
    key: "expenses",
    label: "Spending this month",
    help: "Living costs only. Leave out money you moved to savings or investments.",
  },
  { key: "savings", label: "New savings this month", help: "Money newly set aside. A transfer out of savings is not new savings." },
  {
    key: "investment_contribution",
    label: "New investments this month",
    help: "Money newly invested. Moving existing savings into an investment does not count as new income.",
  },
]

/** A text-field value (kept as a string so blank and "0" stay distinguishable).
 * `null` from the API is shown blank, never as "0". */
function toField(value: number | null | undefined): string {
  return value === null || value === undefined ? "" : String(value)
}

/** The current calendar month as `YYYY-MM` — formatting a date for the month
 * picker only, no financial value is derived. */
function currentMonth(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`
}

function monthLabel(period: string): string {
  const [year, month] = period.split("-").map(Number)
  return new Date(year, month - 1, 1).toLocaleDateString("en-IN", { month: "short", year: "numeric" })
}

function amountCell(value: number | null): string {
  return value === null ? "Not provided" : formatCurrency(value)
}

/** Optional monthly financial records (Research Enhancement Track B1). Every
 * field is optional: a blank field is "not provided", never zero, and a blank
 * field on a month that already has a value clears it. Nothing is calculated
 * here — values are sent as typed and read back from the API. These records
 * are not used by the analysis. */
export function MonthlyRecordsCard({ profileId }: { profileId: number }) {
  const query = useMonthlyRecordsQuery(profileId)
  const save = useSaveMonthlyRecord(profileId)
  const remove = useDeleteMonthlyRecord(profileId)

  const [period, setPeriod] = useState(currentMonth())
  const [values, setValues] = useState<Record<AmountField, string>>({
    income: "",
    expenses: "",
    savings: "",
    investment_contribution: "",
  })
  const [basis, setBasis] = useState<Basis>(null)
  const [formError, setFormError] = useState<string | null>(null)

  const existing: MonthlyRecord | undefined = query.data?.records.find((r) => r.period === period)

  const loadMonth = (nextPeriod: string, records: MonthlyRecord[] | undefined) => {
    setPeriod(nextPeriod)
    const found = records?.find((r) => r.period === nextPeriod)
    setValues({
      income: toField(found?.income),
      expenses: toField(found?.expenses),
      savings: toField(found?.savings),
      investment_contribution: toField(found?.investment_contribution),
    })
    setBasis(found?.income_basis ?? null)
    setFormError(null)
    save.reset()
  }

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    setFormError(null)
    save.reset()

    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(period)) {
      setFormError("Choose the month this record is for.")
      return
    }
    const body: MonthlyRecordUpdate = {}
    for (const { key, label } of AMOUNT_FIELDS) {
      const raw = values[key].trim()
      if (raw === "") {
        // Blank on a month that already holds a value means "clear it".
        if (existing && existing[key] !== null) body[key] = null
        continue
      }
      const amount = Number(raw)
      if (!Number.isFinite(amount) || amount < 0) {
        setFormError(`${label} must be a number that is 0 or greater.`)
        return
      }
      body[key] = amount
    }
    const hasIncome = values.income.trim() !== ""
    if (basis !== null && !hasIncome) {
      setFormError("Choose net or gross only when you enter an income.")
      return
    }
    if (hasIncome) body.income_basis = basis
    else if (existing?.income_basis) body.income_basis = null

    const providesAnAmount = AMOUNT_FIELDS.some(({ key }) => values[key].trim() !== "")
    if (!providesAnAmount) {
      setFormError("Enter at least one amount for the month.")
      return
    }
    save.mutate({ period, body })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CalendarDays className="text-muted-foreground size-4" aria-hidden="true" /> Monthly record (optional)
        </CardTitle>
        <CardDescription>
          Add what you earned, spent, saved and invested in a particular month. Every field is optional: a blank field
          is “not provided”, never zero. These records are stored with your profile and are not used by your current
          analysis.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {query.isLoading ? (
          <LoadingState label="Loading monthly records" />
        ) : query.error ? (
          <ErrorState error={query.error} onRetry={() => query.refetch()} />
        ) : (
          <>
            <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
              {formError ? (
                <Alert variant="destructive">
                  <AlertDescription>{formError}</AlertDescription>
                </Alert>
              ) : null}
              {save.isError ? <ErrorState error={save.error} onRetry={() => save.reset()} /> : null}
              {save.isSuccess ? (
                <Alert>
                  <CheckCircle2 />
                  <AlertTitle>Monthly record saved</AlertTitle>
                  <AlertDescription>{monthLabel(period)} has been saved.</AlertDescription>
                </Alert>
              ) : null}

              <FieldGroup>
                <Field>
                  <FieldLabel htmlFor="mr-period">Month</FieldLabel>
                  <Input
                    id="mr-period"
                    type="month"
                    max={currentMonth()}
                    value={period}
                    onChange={(event) => loadMonth(event.target.value, query.data?.records)}
                  />
                  <FieldDescription>
                    {existing ? "This month already has a record; saving will update it." : "No record for this month yet."}
                  </FieldDescription>
                </Field>

                <div className="grid gap-4 sm:grid-cols-2">
                  {AMOUNT_FIELDS.map(({ key, label, help }) => (
                    <Field key={key}>
                      <FieldLabel htmlFor={`mr-${key}`}>{label}</FieldLabel>
                      <Input
                        id={`mr-${key}`}
                        type="number"
                        inputMode="decimal"
                        min={0}
                        step="0.01"
                        placeholder="Not provided"
                        value={values[key]}
                        onChange={(event) => setValues((current) => ({ ...current, [key]: event.target.value }))}
                      />
                      <FieldDescription>{help}</FieldDescription>
                    </Field>
                  ))}
                </div>

                <Field>
                  <FieldLabel id="mr-basis-label">Is that income net or gross?</FieldLabel>
                  <div role="group" aria-labelledby="mr-basis-label" className="flex flex-wrap gap-2">
                    {([null, "net", "gross"] as const).map((option) => (
                      <Button
                        key={option ?? "unstated"}
                        type="button"
                        size="sm"
                        variant={basis === option ? "default" : "outline"}
                        aria-pressed={basis === option}
                        onClick={() => setBasis(option)}
                      >
                        {option === null ? "Not stated" : option === "net" ? "Net (after tax)" : "Gross (before tax)"}
                      </Button>
                    ))}
                  </div>
                  <FieldDescription>Only used together with an income. Leave as “Not stated” if unsure.</FieldDescription>
                </Field>
              </FieldGroup>

              <div>
                <Button type="submit" disabled={save.isPending}>
                  {save.isPending ? "Saving…" : existing ? "Update month" : "Save month"}
                </Button>
              </div>
            </form>

            <div className="space-y-2">
              <h3 className="text-sm font-medium">Months you have recorded</h3>
              {query.data && query.data.records.length > 0 ? (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Month</TableHead>
                        <TableHead>Income</TableHead>
                        <TableHead>Spending</TableHead>
                        <TableHead>Savings</TableHead>
                        <TableHead>Investments</TableHead>
                        <TableHead>Basis</TableHead>
                        <TableHead>
                          <span className="sr-only">Actions</span>
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {query.data.records.map((record) => (
                        <TableRow key={record.period}>
                          <TableCell className="font-medium whitespace-nowrap">{monthLabel(record.period)}</TableCell>
                          <TableCell className="whitespace-nowrap">{amountCell(record.income)}</TableCell>
                          <TableCell className="whitespace-nowrap">{amountCell(record.expenses)}</TableCell>
                          <TableCell className="whitespace-nowrap">{amountCell(record.savings)}</TableCell>
                          <TableCell className="whitespace-nowrap">{amountCell(record.investment_contribution)}</TableCell>
                          <TableCell className="whitespace-nowrap">
                            {record.income_basis === "net" ? "Net" : record.income_basis === "gross" ? "Gross" : "Not stated"}
                          </TableCell>
                          <TableCell>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              disabled={remove.isPending}
                              aria-label={`Delete the record for ${monthLabel(record.period)}`}
                              onClick={() => remove.mutate(record.period)}
                            >
                              <Trash2 aria-hidden="true" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <p className="text-muted-foreground text-sm">No months recorded yet.</p>
              )}
              {remove.isError ? <ErrorState error={remove.error} onRetry={() => remove.reset()} /> : null}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
