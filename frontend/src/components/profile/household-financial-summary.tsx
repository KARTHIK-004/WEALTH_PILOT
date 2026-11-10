import { Calculator } from "lucide-react"

import { ErrorState } from "@/components/shell/error-state"
import { LoadingState } from "@/components/shell/loading-state"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useHouseholdSummaryQuery, type HouseholdFinancialSummary } from "@/hooks/use-household-summary"
import { formatCurrency, formatStatusLabel } from "@/lib/format"

/**
 * Phase 34 — the household's read-only financial summary.
 *
 * Every figure shown here arrives already computed from
 * `GET /api/households/{id}/financial-summary`. **This component performs no
 * financial arithmetic at all**: it does not add, subtract, total, average,
 * score or rank anything, and it never derives one displayed number from
 * another. Its only number handling is `formatCurrency` on a value the API
 * returned (`docs/DECISIONS.md` ADR-033).
 *
 * `null` means "not known" and renders as "Not provided"; a stored `0` renders
 * as a formatted zero. The two must never look the same.
 *
 * It shows no score, no percentage, no ranking and no recommendation — the
 * emergency-fund status is the backend's own factual Sufficient / Insufficient
 * / Unknown vocabulary, not a rating of the household.
 */

/** `null` is "not provided" — never 0 (`docs/RULES.md` Rule 13). */
const money = (value: number | null | undefined): string =>
  value === null || value === undefined ? "Not provided" : formatCurrency(value)

function Figure({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="space-y-0.5">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className="text-sm font-medium">{value}</p>
      {note ? <p className="text-muted-foreground text-xs">{note}</p> : null}
    </div>
  )
}

function Unavailable({ reason }: { reason: string | null }) {
  return <p className="text-muted-foreground text-xs">{reason ?? "Not provided."}</p>
}

function MonthlyView({ summary }: { summary: HouseholdFinancialSummary }) {
  const { income, expenses, cash_flow: cashFlow } = summary
  return (
    <section aria-labelledby="household-monthly-heading" className="space-y-2">
      <h4 id="household-monthly-heading" className="text-sm font-medium">
        Recurring monthly view
      </h4>
      <p className="text-muted-foreground text-xs">
        Monthly amounts are used as recorded and yearly amounts are counted as one twelfth per month.
        One-time records are listed separately below and are never treated as recurring.
      </p>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Figure
          label="Recurring monthly income"
          value={money(income.recurring_monthly)}
          note={`${income.active_record_count} of ${income.record_count} income record(s) active`}
        />
        <Figure
          label="Recurring monthly expenses"
          value={money(expenses.recurring_monthly)}
          note={`Essential ${money(expenses.recurring_essential_monthly)} · Other ${money(expenses.recurring_nonessential_monthly)}`}
        />
        <Figure label="Monthly cash flow" value={money(cashFlow.monthly)} />
      </div>
      {cashFlow.available ? null : <Unavailable reason={cashFlow.unavailable_reason} />}
    </section>
  )
}

function OneTimeView({ summary }: { summary: HouseholdFinancialSummary }) {
  return (
    <section aria-labelledby="household-one-time-heading" className="space-y-2">
      <h4 id="household-one-time-heading" className="text-sm font-medium">
        One-time records
      </h4>
      <div className="grid gap-4 sm:grid-cols-2">
        <Figure label="One-time income" value={money(summary.income.one_time)} />
        <Figure label="One-time expenses" value={money(summary.expenses.one_time)} />
      </div>
    </section>
  )
}

function BalanceView({ summary }: { summary: HouseholdFinancialSummary }) {
  const { assets, liabilities, net_position: net } = summary
  return (
    <section aria-labelledby="household-balance-heading" className="space-y-2">
      <h4 id="household-balance-heading" className="text-sm font-medium">
        Assets and liabilities
      </h4>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Item</TableHead>
              <TableHead>Amount</TableHead>
              <TableHead>Records</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow>
              <TableCell className="font-medium">Total assets</TableCell>
              <TableCell>{money(assets.total)}</TableCell>
              <TableCell>{assets.record_count}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell className="font-medium">Of which liquid</TableCell>
              <TableCell>{money(assets.liquid)}</TableCell>
              <TableCell>{assets.liquid_record_count}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell className="font-medium">Outstanding liabilities</TableCell>
              <TableCell>{money(liabilities.outstanding)}</TableCell>
              <TableCell>{liabilities.record_count}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell className="font-medium">Recorded monthly liability payments</TableCell>
              <TableCell>{money(liabilities.monthly_payment)}</TableCell>
              <TableCell>—</TableCell>
            </TableRow>
            <TableRow>
              <TableCell className="font-medium">Net position</TableCell>
              <TableCell>{money(net.value)}</TableCell>
              <TableCell>—</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
      <p className="text-muted-foreground text-xs">
        Net position is total assets less outstanding liabilities. Income and expenses are not part of it.
      </p>
      {net.available ? null : <Unavailable reason={net.unavailable_reason} />}
    </section>
  )
}

function EmergencyFundView({ summary }: { summary: HouseholdFinancialSummary }) {
  const fund = summary.emergency_fund
  return (
    <section aria-labelledby="household-emergency-heading" className="space-y-2">
      <h4 id="household-emergency-heading" className="text-sm font-medium">
        Emergency fund
      </h4>
      <p className="text-muted-foreground text-xs">
        The target is {fund.target_months} months of the household's recurring essential expenses — the same
        rule the individual assessment uses. This is a statement of position only: no advice, action or
        recommendation follows from it here.
      </p>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Figure label="Required" value={money(fund.required)} />
        <Figure label="Current liquid assets" value={money(fund.current_liquid_assets)} />
        <Figure label="Shortfall" value={money(fund.shortfall)} />
        <div className="space-y-0.5">
          <p className="text-muted-foreground text-xs">Status</p>
          <Badge variant="outline">{formatStatusLabel(fund.status)}</Badge>
        </div>
      </div>
      {fund.available ? null : <Unavailable reason={fund.unavailable_reason} />}
    </section>
  )
}

function CompletenessView({ summary }: { summary: HouseholdFinancialSummary }) {
  const entries: [string, string][] = [
    ["Income", summary.data_completeness.income],
    ["Expenses", summary.data_completeness.expenses],
    ["Assets", summary.data_completeness.assets],
    ["Liabilities", summary.data_completeness.liabilities],
    ["Emergency fund", summary.data_completeness.emergency_fund],
  ]
  return (
    <section aria-labelledby="household-completeness-heading" className="space-y-2">
      <h4 id="household-completeness-heading" className="text-sm font-medium">
        What is recorded
      </h4>
      <p className="text-muted-foreground text-xs">
        Whether each area has information recorded at all. Nothing that is not recorded is assumed to be zero.
      </p>
      <ul className="flex flex-wrap gap-2">
        {entries.map(([label, state]) => (
          <li key={label}>
            <Badge variant="outline">{`${label}: ${formatStatusLabel(state)}`}</Badge>
          </li>
        ))}
      </ul>
    </section>
  )
}

/**
 * Phase 36 -- shown above the household's goals. It restates the emergency-fund
 * requirement the financial summary ALREADY computed, so that an
 * `emergency_fund` goal's stated target is never mistaken for the calculated
 * figure. It reads the same cached summary query; nothing is computed here, and
 * the goal never feeds back into the calculation (ADR-035).
 */
export function HouseholdGoalsEmergencyFundReference({
  householdId,
  profileId,
}: {
  householdId: number
  profileId: number
}) {
  const query = useHouseholdSummaryQuery(householdId, profileId)
  const fund = query.data?.emergency_fund
  if (!fund) return null
  return (
    <p className="text-muted-foreground text-xs">
      For reference, the household's calculated emergency-fund requirement is{" "}
      <span className="text-foreground font-medium">{money(fund.required)}</span> ({fund.target_months} months of
      recurring essential expenses, from the financial summary). An emergency-fund goal's target amount is your own
      stated target and does not change that calculation.
      {fund.required === null ? ` ${fund.unavailable_reason ?? ""}` : ""}
    </p>
  )
}

export function HouseholdFinancialSummarySection({
  householdId,
  profileId,
}: {
  householdId: number
  profileId: number
}) {
  const query = useHouseholdSummaryQuery(householdId, profileId)

  if (query.isLoading) return <LoadingState label="Loading household financial summary" />
  if (query.error) return <ErrorState error={query.error} onRetry={() => query.refetch()} />
  if (!query.data) return null

  return <HouseholdFinancialSummaryView summary={query.data} />
}

/** The summary as pure markup for a response the backend already computed (the stored-records route, or the fictional family demo's engine output). Performs no arithmetic. */
export function HouseholdFinancialSummaryView({ summary }: { summary: HouseholdFinancialSummary }) {
  return (
    <div className="flex flex-col gap-4 rounded-lg border p-4">
      <div className="space-y-1">
        <h3 className="flex items-center gap-2 text-sm font-medium">
          <Calculator className="text-muted-foreground size-4" /> Financial summary
        </h3>
        <p className="text-muted-foreground text-xs">
          Calculated by the backend from this household's own records, and shown exactly as returned. There is
          no score, rating or ranking here, and no recommendation is made from it. Figures shown as "Not
          provided" are not recorded — they are not zero.
        </p>
      </div>
      <MonthlyView summary={summary} />
      <OneTimeView summary={summary} />
      <BalanceView summary={summary} />
      <EmergencyFundView summary={summary} />
      <CompletenessView summary={summary} />
    </div>
  )
}
