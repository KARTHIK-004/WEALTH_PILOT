import { LineChart, Wallet } from "lucide-react"
import type { ReactNode } from "react"
import { Link } from "react-router"

import { MonthlyFlowsChart } from "@/components/charts/monthly-flows-chart"
import { ErrorState } from "@/components/shell/error-state"
import { LoadingState } from "@/components/shell/loading-state"
import { SectionUnavailable } from "@/components/shell/section-unavailable"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { dateRange, missingDataNotes, monthLabel, OVERVIEW_EXPLANATION, OVERVIEW_TITLE, overviewTrends, savingsRate } from "@/lib/behaviour-overview"
import { formatCurrency, formatPercent } from "@/lib/format"
import type { InvestmentBehaviour } from "@/lib/investment-behaviour"
import { plainSentiment, type ModelState, type UserSentiment } from "@/lib/plain-sentiment"
import { NOT_AVAILABLE, SPENDING_NOT_AVAILABLE_MESSAGE, SPENDING_TITLE, type SpendingPatternState } from "@/lib/spending-pattern"
import type { components } from "@/types/api"

type Insight = components["schemas"]["PersonalizedInsightResponse"]
type MonthlyRecord = components["schemas"]["MonthlyRecordResponse"]

export const NO_RECORDS_TITLE = "No monthly records yet"
export const NO_RECORDS_MESSAGE = "Add your monthly income, spending and savings to see your behaviour here. Nothing is assumed until you do."
export const ADD_RECORDS_LABEL = "Add or edit your monthly records"
export const RECORDS_PATH = "/profile"
const NOT_PROVIDED = "Not provided"
const money = (value: number | null | undefined): string => (value === null || value === undefined ? NOT_PROVIDED : formatCurrency(value))

function Tile({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="space-y-1 rounded-xl border p-3">
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd className="text-lg font-semibold">{children}</dd>
      {hint ? <p className="text-muted-foreground text-xs">{hint}</p> : null}
    </div>
  )
}

export function AddRecordsLink() {
  return (
    <Link to={RECORDS_PATH} className="text-primary text-sm underline underline-offset-2">
      {ADD_RECORDS_LABEL} (Customer Profile)
    </Link>
  )
}

export interface BehaviourOverviewViewProps {
  insight: Insight | undefined
  /** The reported months (YYYY-MM), for the date range. */
  periods: readonly string[]
  loading: boolean
  error: unknown
  onRetry: () => void
  /** A unique id prefix when several overviews are on one page (one per family member). */
  idPrefix?: string
  /** Replaces the title (for example a member's name). */
  heading?: string
}

/**
 * "Financial behaviour overview": the explanation, the number of reported months, the date range, the income, spending and savings trends, the savings rate, the month-over-month changes and
 * the reasons for anything that could not be calculated. DISPLAY ONLY: every figure and sentence is the backend's finding, shown unchanged; zero records show the empty state and nothing is
 * invented; a failed request shows the error and no values.
 */
export function BehaviourOverviewView({ insight, periods, loading, error, onRetry, idPrefix = "overview", heading = OVERVIEW_TITLE }: BehaviourOverviewViewProps) {
  const id = `${idPrefix}-heading`
  let body: ReactNode
  if (error) {
    body = <ErrorState error={error} onRetry={onRetry} />
  } else if (!insight) {
    body = loading ? <LoadingState label="Reading your monthly records" /> : null
  } else if (insight.behaviour.observation_count === 0) {
    body = (
      <div className="space-y-2">
        <SectionUnavailable title={NO_RECORDS_TITLE} message={NO_RECORDS_MESSAGE} />
        <AddRecordsLink />
      </div>
    )
  } else {
    const findings = insight.behaviour.findings
    const trends = overviewTrends(findings)
    const rate = savingsRate(findings)
    const notes = missingDataNotes(findings)
    const latest = insight.behaviour.latest_period
    const range = dateRange(periods) ?? (latest ? monthLabel(latest) : null)
    body = (
      <div className="space-y-4">
        <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Tile label="Reported months">{insight.behaviour.observation_count}</Tile>
          <Tile label="Date range">{range ?? NOT_AVAILABLE}</Tile>
          <Tile label="Savings rate" hint={latest ? `Savings as a share of income in ${monthLabel(latest)}` : undefined}>
            {rate && rate.ratio !== null ? formatPercent(rate.ratio, 1) : NOT_AVAILABLE}
          </Tile>
        </dl>
        <div className="space-y-2">
          <h3 className="text-sm font-medium">Trends and month-over-month changes</h3>
          <ul className="space-y-2">
            {trends.map((row) => (
              <li key={row.code} className="flex flex-col gap-1 rounded-lg border p-3 sm:flex-row sm:items-start sm:gap-3">
                <span className="flex items-center gap-2 sm:w-40 sm:shrink-0">
                  <span className="text-sm font-medium">{row.label}</span>
                  <Badge variant={row.available ? "secondary" : "outline"}>{row.directionLabel ?? NOT_AVAILABLE}</Badge>
                </span>
                <span className="text-sm">{row.statement}</span>
              </li>
            ))}
          </ul>
        </div>
        {notes.length > 0 ? (
          <div className="space-y-1 rounded-lg border border-dashed p-3" role="note" aria-label="Why some values are not shown">
            <p className="text-sm font-medium">Why some values are not shown</p>
            <ul className="text-muted-foreground list-disc space-y-1 pl-5 text-sm">
              {notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    )
  }
  return (
    <section aria-labelledby={id} className="space-y-3" aria-busy={loading && !insight}>
      <div className="space-y-1">
        <h2 id={id} className="text-lg font-semibold">
          {heading}
        </h2>
        <p className="text-muted-foreground text-sm">{OVERVIEW_EXPLANATION}</p>
      </div>
      {body}
    </section>
  )
}

export interface RecordedMonthsSectionProps {
  /** The customer's own records, newest first as the API returns them. */
  records: readonly MonthlyRecord[] | undefined
  loading: boolean
  error: unknown
  onRetry: () => void
}

/** The customer's own reported months as a chart and the table that carries the same values, oldest first. Zero records show nothing here (the overview already shows the empty state). */
export function RecordedMonthsSection({ records, loading, error, onRetry }: RecordedMonthsSectionProps) {
  if (error) return <ErrorState error={error} onRetry={onRetry} />
  if (loading && !records) return <LoadingState label="Loading your monthly records" />
  if (!records || records.length === 0) return null
  const chronological = [...records].sort((a, b) => (a.period < b.period ? -1 : a.period > b.period ? 1 : 0))
  return (
    <section aria-labelledby="recorded-months-heading" className="space-y-3">
      <h2 id="recorded-months-heading" className="text-lg font-semibold">
        Your monthly records
      </h2>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Income, spending and savings by month</CardTitle>
          <CardDescription>The amounts you reported, oldest month first. The table gives the same values.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <MonthlyFlowsChart points={chronological.map((r) => ({ period: r.period, income: r.income, expenses: r.expenses, savings: r.savings }))} />
          <div className="overflow-x-auto" role="region" aria-label="Your monthly records table (scrolls sideways on a narrow screen)" tabIndex={0}>
            <Table>
              <TableCaption>Your reported months. A blank amount was not provided; it is not zero.</TableCaption>
              <TableHeader>
                <TableRow>
                  <TableHead scope="col">Month</TableHead>
                  <TableHead scope="col" className="text-right">
                    Income
                  </TableHead>
                  <TableHead scope="col" className="text-right">
                    Spending
                  </TableHead>
                  <TableHead scope="col" className="text-right">
                    Savings
                  </TableHead>
                  <TableHead scope="col" className="text-right">
                    Investments
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {chronological.map((record) => (
                  <TableRow key={record.period}>
                    <TableHead scope="row" className="whitespace-nowrap">
                      {monthLabel(record.period)}
                    </TableHead>
                    <TableCell className="text-right">{money(record.income)}</TableCell>
                    <TableCell className="text-right">{money(record.expenses)}</TableCell>
                    <TableCell className="text-right">{money(record.savings)}</TableCell>
                    <TableCell className="text-right">{money(record.investment_contribution)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <AddRecordsLink />
        </CardContent>
      </Card>
    </section>
  )
}

/** "Investment behaviour": the status, one plain sentence, and the backend's own sentence behind it. */
export function InvestmentBehaviourView({ behaviour, loading, idPrefix = "investment", heading = "Investment behaviour" }: { behaviour: InvestmentBehaviour | undefined; loading: boolean; idPrefix?: string; heading?: string }) {
  const id = `${idPrefix}-heading`
  return (
    <section aria-labelledby={id}>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <LineChart className="text-muted-foreground size-4" aria-hidden="true" />
            <h2 id={id} className="text-base font-semibold">
              {heading}
            </h2>
          </CardTitle>
          <CardDescription>How your recent investing activity compares with your own history.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {loading && !behaviour ? (
            <LoadingState label="Checking your investing history" />
          ) : behaviour ? (
            <div className="space-y-2" data-status={behaviour.status}>
              <p className="text-muted-foreground text-xs">Behaviour status</p>
              <Badge variant={behaviour.status === "unusual" ? "secondary" : "outline"}>{behaviour.label}</Badge>
              <p className="text-sm">{behaviour.detail}</p>
              {behaviour.fromRecords ? <p className="text-muted-foreground text-xs">From your records: {behaviour.fromRecords}</p> : null}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </section>
  )
}

const SPENDING_KIND_LABEL: Record<SpendingPatternState["kind"], string> = {
  loading: "Checking",
  backend_unavailable: "Service unavailable",
  no_records: "No records",
  insufficient_records: "Not enough records",
  model_unavailable: "Model not available",
  valid: "Result",
}

/** "Spending pattern": the model's result when there is one; otherwise "Not available" with the one-sentence rule and the specific reason. Never a guessed pattern. */
export function SpendingPatternView({ state, onRetry, idPrefix = "spending", heading = SPENDING_TITLE }: { state: SpendingPatternState; onRetry?: () => void; idPrefix?: string; heading?: string }) {
  const id = `${idPrefix}-heading`
  return (
    <section aria-labelledby={id}>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Wallet className="text-muted-foreground size-4" aria-hidden="true" />
            <h2 id={id} className="text-base font-semibold">
              {heading}
            </h2>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2" data-state={state.kind}>
          {state.kind === "loading" ? (
            <LoadingState label="Checking the spending model" />
          ) : state.kind === "valid" ? (
            <div className="space-y-1">
              <p className="text-muted-foreground text-xs">Your spending pattern</p>
              <Badge variant="outline">{state.pattern}</Badge>
            </div>
          ) : (
            <div className="space-y-2" role={state.kind === "backend_unavailable" ? "alert" : "status"}>
              <p className="text-sm font-medium">{NOT_AVAILABLE}</p>
              <p className="text-muted-foreground text-sm">{SPENDING_NOT_AVAILABLE_MESSAGE}</p>
              <p className="flex flex-wrap items-center gap-2 text-sm">
                <Badge variant="outline">{SPENDING_KIND_LABEL[state.kind]}</Badge>
                <span>{state.reason}</span>
              </p>
              {state.kind === "backend_unavailable" && onRetry ? (
                <Button variant="outline" size="sm" onClick={onRetry}>
                  Try again
                </Button>
              ) : null}
            </div>
          )}
        </CardContent>
      </Card>
    </section>
  )
}

/** The note's reading in simple English: one sentence, then short true explanations. The method, model status, confidence and intensity are not here: they sit in the optional technical details. */
export function PlainSentimentSummary({ reading, modelState }: { reading: UserSentiment; modelState?: ModelState }) {
  const plain = plainSentiment(reading, modelState)
  return (
    <section aria-labelledby="plain-sentiment-heading" className="space-y-2 rounded-xl border p-4" data-kind={plain.kind}>
      <h3 id="plain-sentiment-heading" className="text-muted-foreground text-xs">
        How your note reads
      </h3>
      <p className="text-base font-medium">{plain.headline}</p>
      {plain.notes.length > 0 ? (
        <ul className="text-muted-foreground list-disc space-y-1 pl-5 text-sm">
          {plain.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}
