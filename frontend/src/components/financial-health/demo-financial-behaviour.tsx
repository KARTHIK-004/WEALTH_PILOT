import { FlaskConical } from "lucide-react"
import { Link } from "react-router"

import { MonthlyFlowsChart } from "@/components/charts/monthly-flows-chart"
import { BehaviourSentimentView, type BehaviourSentimentViewProps } from "@/components/financial-health/behaviour-sentiment-view"
import { ErrorState } from "@/components/shell/error-state"
import { LoadingState } from "@/components/shell/loading-state"
import { TechnicalDetails } from "@/components/shell/technical-details"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ApiClientError } from "@/lib/api-client"
import { DEMO_PAGE_PATH, isDemoDisabledProblem } from "@/lib/demo-mode"
import { formatCurrency, formatPercent } from "@/lib/format"
import type { components } from "@/types/api"

type Demo = components["schemas"]["DemoFinancialBehaviourResponse"]
type Month = components["schemas"]["DemoMonthOut"]
type Feature = components["schemas"]["FeatureValueOut"]

export const DEMO_BANNER_TITLE = "Demonstration mode: fictional data"
export const DEMO_BANNER_FALLBACK =
  "Every month, amount and sentence on this page is fictional and fixed. It is not a customer's record, nothing is stored, and it does not affect any risk profile, allocation or recommendation."
export const DEMO_PAGE_DESCRIPTION =
  "A walk-through of what this view summarizes: months of reported income, expenses and savings, the changes and ratios worked out from them, and an optional reading of a sentence the user chose to write. This only explains: it changes nothing about a risk profile, an allocation or a recommendation."
export const DEMO_DISABLED_MESSAGE =
  "The backend answered 404 for the demonstration data: DEMO_MODE_ENABLED is not true for the running backend, or it is an older backend without the demonstration route. In development, set DEMO_MODE_ENABLED=true in the backend environment and restart the backend (it reads the setting once, at start-up), or leave demonstration mode by removing the demo parameter from the address."

const NOT_AVAILABLE = "Not available"

/** A calculated number, or "Not available" with the backend's reason kept for assistive technology and the hover title. Never a zero. */
function Calculated({ feature, kind, signed = false }: { feature: Feature; kind: "percent" | "currency"; signed?: boolean }) {
  if (feature.value === null || feature.value === undefined) {
    return (
      <span title={feature.unavailable_reason ?? undefined}>
        {NOT_AVAILABLE}
        {feature.unavailable_reason ? <span className="sr-only"> ({feature.unavailable_reason})</span> : null}
      </span>
    )
  }
  const text = kind === "percent" ? formatPercent(feature.value, 1) : formatCurrency(feature.value)
  return <span>{signed && feature.value > 0 ? `+${text}` : text}</span>
}

export function DemoBanner({ notice }: { notice?: string }) {
  return (
    <Alert role="status" aria-label="Demonstration mode is active" className="border-primary/40">
      <FlaskConical aria-hidden="true" />
      <AlertTitle className="flex flex-wrap items-center gap-2">
        {DEMO_BANNER_TITLE} <Badge variant="outline">Demo</Badge>
      </AlertTitle>
      <AlertDescription className="space-y-2">
        <p>{notice ?? DEMO_BANNER_FALLBACK}</p>
        <p>
          <Link to={DEMO_PAGE_PATH} className="text-primary underline underline-offset-2">
            Leave demonstration mode
          </Link>
        </p>
      </AlertDescription>
    </Alert>
  )
}

function SummaryTile({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <div className="space-y-1 rounded-xl border p-3">
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd className="text-lg font-semibold">{children}</dd>
      {hint ? <p className="text-muted-foreground text-xs">{hint}</p> : null}
    </div>
  )
}

/** The headline figures, each taken from the backend's response: the month count and the latest month's own calculated ratios and changes. Income is shown as the first and latest REPORTED
 * amounts; no income trend is calculated here or by the existing behaviour logic. */
export function DemoSummary({ data }: { data: Demo }) {
  const first = data.months[0]
  const latest = data.months[data.months.length - 1]
  if (!latest || !first) return null
  return (
    <section aria-labelledby="demo-summary-heading" className="space-y-3">
      <h2 id="demo-summary-heading" className="text-lg font-semibold">
        Behaviour summary
      </h2>
      <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <SummaryTile label="Reported months">{data.insight.behaviour.observation_count}</SummaryTile>
        <SummaryTile label={`Savings rate, ${latest.period}`} hint="Savings as a share of that month's income">
          <Calculated feature={latest.savings_to_income} kind="percent" />
        </SummaryTile>
        <SummaryTile label={`Spending change, ${latest.period}`} hint="Expenses compared with the previous month">
          <Calculated feature={latest.expenses_change.relative_change} kind="percent" signed />
        </SummaryTile>
        <SummaryTile label={`Savings change, ${latest.period}`} hint="Savings compared with the previous month">
          <Calculated feature={latest.savings_change.relative_change} kind="percent" signed />
        </SummaryTile>
        <SummaryTile label={`Expenses as a share of income, ${latest.period}`}>
          <Calculated feature={latest.expense_to_income} kind="percent" />
        </SummaryTile>
        <SummaryTile label="Income, first to latest reported month" hint="The reported amounts, side by side">
          {formatCurrency(first.income)} to {formatCurrency(latest.income)}
        </SummaryTile>
      </dl>
    </section>
  )
}

function MonthRow({ month }: { month: Month }) {
  return (
    <TableRow>
      <TableHead scope="row" className="whitespace-nowrap">
        {month.period}
      </TableHead>
      <TableCell className="text-right">{formatCurrency(month.income)}</TableCell>
      <TableCell className="text-right">{formatCurrency(month.expenses)}</TableCell>
      <TableCell className="text-right">{formatCurrency(month.savings)}</TableCell>
      <TableCell className="text-right">
        <Calculated feature={month.expense_to_income} kind="percent" />
      </TableCell>
      <TableCell className="text-right">
        <Calculated feature={month.savings_to_income} kind="percent" />
      </TableCell>
      <TableCell className="text-right">
        <Calculated feature={month.expenses_change.relative_change} kind="percent" signed />
      </TableCell>
      <TableCell className="text-right">
        <Calculated feature={month.savings_change.relative_change} kind="percent" signed />
      </TableCell>
    </TableRow>
  )
}

/** The monthly records section: a chart of the reported amounts and, beside it, the table that carries the same values plus the backend's calculated ratios and changes. */
export function DemoMonthsSection({ data }: { data: Demo }) {
  return (
    <section aria-labelledby="demo-months-heading" className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="demo-months-heading" className="text-lg font-semibold">
          Monthly records (fictional demo months)
        </h2>
        <Badge variant="secondary">{data.months.length} reported months</Badge>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Income, expenses and savings by month</CardTitle>
          <CardDescription>Reported amounts in rupees. The table below gives the same values and the changes and ratios worked out from them.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <MonthlyFlowsChart points={data.months.map((m) => ({ period: m.period, income: m.income, expenses: m.expenses, savings: m.savings }))} />
          <div className="overflow-x-auto" role="region" aria-label="Monthly records table (scrolls sideways on a narrow screen)" tabIndex={0}>
            <Table>
              <TableCaption>Fictional monthly records with calculated ratios and month-over-month changes. The first month has no change because there is no earlier month.</TableCaption>
              <TableHeader>
                <TableRow>
                  <TableHead scope="col">Month</TableHead>
                  <TableHead scope="col" className="text-right">
                    Income
                  </TableHead>
                  <TableHead scope="col" className="text-right">
                    Expenses
                  </TableHead>
                  <TableHead scope="col" className="text-right">
                    Savings
                  </TableHead>
                  <TableHead scope="col" className="text-right">
                    Expenses / income
                  </TableHead>
                  <TableHead scope="col" className="text-right">
                    Savings / income
                  </TableHead>
                  <TableHead scope="col" className="text-right">
                    Spending change
                  </TableHead>
                  <TableHead scope="col" className="text-right">
                    Savings change
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.months.map((month) => (
                  <MonthRow key={month.period} month={month} />
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </section>
  )
}

/** How the reading was made, straight from the response: the active method, the model state and the values that are unavailable. Unavailable is never shown as a number. */
export function DemoMethodPanel({ data }: { data: Demo }) {
  const sentiment = data.insight.user_sentiment
  const model = data.sentiment_model
  const modelState = model.state === "disabled" ? "Disabled" : model.state === "ready" ? "Ready" : "Unavailable"
  return (
    <section aria-labelledby="demo-method-heading" className="space-y-3">
      <h2 id="demo-method-heading" className="text-lg font-semibold">
        How the reading was made
      </h2>
      <Card>
        <CardContent>
          <TechnicalDetails title="Technical details: method, model status, confidence and intensity">
          <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
            <div>
              <dt className="text-muted-foreground text-xs">Active method</dt>
              <dd className="font-mono text-sm">{sentiment.model_version}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground text-xs">Reading method</dt>
              <dd className="text-sm">{sentiment.method === "rules_baseline" ? "Rules baseline (fixed rules, no trained model)" : sentiment.method}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground text-xs">Transformer / trained model</dt>
              <dd className="text-sm">
                {modelState} <span className="text-muted-foreground">(rules baseline answers)</span>
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground text-xs">Confidence</dt>
              <dd className="text-sm">{sentiment.confidence === null || sentiment.confidence === undefined ? NOT_AVAILABLE : formatPercent(sentiment.confidence, 0)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground text-xs">Intensity</dt>
              <dd className="text-sm">{sentiment.sentiment_intensity === null || sentiment.sentiment_intensity === undefined ? NOT_AVAILABLE : String(sentiment.sentiment_intensity)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground text-xs">Validation status</dt>
              <dd className="text-sm">{sentiment.validation_status}</dd>
            </div>
          </dl>
          </TechnicalDetails>
          <p className="mt-4 text-sm font-medium">Informational only. {data.insight.purpose}</p>
        </CardContent>
      </Card>
    </section>
  )
}

/** The three distinct failure states of demo mode: the backend switched demo off (a clear instruction), the backend unreachable ("Service unavailable"), any other error. Never demo data. */
export function DemoErrorState({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  if (error instanceof ApiClientError && (isDemoDisabledProblem(error.problem.title) || error.problem.status === 404)) {
    return (
      <Alert variant="destructive" role="alert">
        <AlertTitle>Demonstration mode is switched off on the server</AlertTitle>
        <AlertDescription>
          <p>{DEMO_DISABLED_MESSAGE}</p>
        </AlertDescription>
      </Alert>
    )
  }
  return <ErrorState error={error} onRetry={onRetry} />
}

export interface DemoExample {
  label: string
  text: string
}

export interface DemoFinancialBehaviourViewProps extends Omit<BehaviourSentimentViewProps, "data" | "error" | "loading"> {
  data: Demo | undefined
  loading: boolean
  error: unknown
  /** Fictional sentences that fill the text box (they are analysed only when Analyse is pressed). */
  examples: readonly DemoExample[]
  onUseExample: (text: string) => void
}

/** Buttons that put a fictional sentence in the box, so the abstention behaviour (quoted, third-person, hypothetical, unrelated) can be tried without typing. */
export function DemoExamples({ examples, onUseExample }: { examples: readonly DemoExample[]; onUseExample: (text: string) => void }) {
  return (
    <section aria-labelledby="demo-examples-heading" className="space-y-2">
      <h3 id="demo-examples-heading" className="text-sm font-medium">
        Try a fictional sentence
      </h3>
      <ul className="flex flex-wrap gap-2">
        {examples.map((example) => (
          <li key={example.label}>
            <Button type="button" variant="outline" size="sm" onClick={() => onUseExample(example.text)}>
              {example.label}
            </Button>
          </li>
        ))}
      </ul>
      <p className="text-muted-foreground text-xs">A button only fills the text box; press Analyse to read it.</p>
    </section>
  )
}

/**
 * The demonstration page body as pure markup (every state is decided by props, so it renders identically in the app and in the Node component tests). DISPLAY ONLY: every figure and sentence in
 * `data` is calculated by the backend; this component renders it. Layout: the banner first, then the month records (chart and table), the behaviour summary, the existing behaviour &
 * sentiment view (observed facts left, the text box and its reading right; stacked on a narrow screen) and the method panel.
 */
export function DemoFinancialBehaviourView({ data, loading, error, examples, onUseExample, ...view }: DemoFinancialBehaviourViewProps) {
  if (error) {
    return (
      <div className="space-y-6">
        <DemoBanner />
        <DemoErrorState error={error} onRetry={view.onRetry} />
      </div>
    )
  }
  if (loading && !data) {
    return (
      <div className="space-y-6" aria-busy="true">
        <DemoBanner />
        <LoadingState label="Loading the demonstration data" />
      </div>
    )
  }
  if (!data) return <DemoBanner />
  return (
    <div className="space-y-8">
      <DemoBanner notice={data.notice} />
      <DemoMonthsSection data={data} />
      <DemoSummary data={data} />
      <section aria-labelledby="demo-behaviour-heading" className="space-y-3">
        <h2 id="demo-behaviour-heading" className="text-lg font-semibold">
          Financial Behaviour &amp; Sentiment
        </h2>
        <DemoExamples examples={examples} onUseExample={onUseExample} />
        <BehaviourSentimentView {...view} loading={false} error={undefined} data={data.insight} plainLanguage modelState={data.sentiment_model.state} />
      </section>
      <DemoMethodPanel data={data} />
    </div>
  )
}
