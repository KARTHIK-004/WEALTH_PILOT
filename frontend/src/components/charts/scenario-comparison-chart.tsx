import { Bar, BarChart, CartesianGrid, Legend, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"

import { AXIS_TICK, SERIES_EMPHASIS, SERIES_MUTED, TOOLTIP_ITEM_STYLE, TOOLTIP_STYLE } from "@/components/charts/chart-theme"
import { SectionUnavailable } from "@/components/shell/section-unavailable"
import { formatPercent } from "@/lib/format"
import { METRICS, getStrategyDisplayName } from "@/lib/terminology"
import type { components } from "@/types/api"

type ScenarioSummary = components["schemas"]["ScenarioSummary"]

function scenarioName(scenario: ScenarioSummary): string {
  const strategy = getStrategyDisplayName(scenario.portfolio_strategy)
  return strategy ? `Scenario ${scenario.label}: ${strategy}` : `Scenario ${scenario.label}`
}

/**
 * Side-by-side bars of the two `ScenarioSummary` objects the API returned
 * (`expected_return`, `expected_volatility`, `sharpe_ratio`) — a comparison,
 * not a ranking: no scenario is scored, ordered or labelled better.
 * Return and volatility share one axis (both fractions); the Sharpe ratio
 * is a unitless number, so it gets its own axis. A value the API left
 * `null` is not drawn and is listed under the chart as unavailable — it is
 * never plotted as zero.
 */
export function ScenarioComparisonChart({ scenarioA, scenarioB }: { scenarioA: ScenarioSummary; scenarioB: ScenarioSummary }) {
  const nameA = scenarioName(scenarioA)
  const nameB = scenarioName(scenarioB)

  const percentRows = [
    { metric: METRICS.expectedReturn.label, a: scenarioA.expected_return, b: scenarioB.expected_return },
    { metric: METRICS.expectedVariability.label, a: scenarioA.expected_volatility, b: scenarioB.expected_volatility },
  ]
  const sharpeRows = [{ metric: METRICS.riskAdjusted.label, a: scenarioA.sharpe_ratio, b: scenarioB.sharpe_ratio }]

  const missing = [...percentRows, ...sharpeRows].flatMap((row) => [
    ...(row.a === null ? [`${nameA}: ${row.metric.toLowerCase()}`] : []),
    ...(row.b === null ? [`${nameB}: ${row.metric.toLowerCase()}`] : []),
  ])
  const hasAnyValue = [...percentRows, ...sharpeRows].some((row) => row.a !== null || row.b !== null)

  if (!hasAnyValue) {
    return (
      <SectionUnavailable reason="neither scenario returned portfolio metrics (a savings-first or blocked result has no portfolio)" />
    )
  }

  return (
    <div className="space-y-3">
      <div className="grid gap-4 lg:grid-cols-2">
        <MetricBars
          title="Expected return and expected variability"
          rows={percentRows}
          nameA={nameA}
          nameB={nameB}
          format={(value) => formatPercent(value, 1)}
          height="h-64"
        />
        <MetricBars
          title="Risk-adjusted performance"
          rows={sharpeRows}
          nameA={nameA}
          nameB={nameB}
          format={(value) => value.toFixed(2)}
          height="h-40"
        />
      </div>
      {missing.length > 0 ? (
        <p className="text-muted-foreground text-xs">Not available (not drawn): {missing.join("; ")}.</p>
      ) : null}
    </div>
  )
}

function MetricBars({
  title,
  rows,
  nameA,
  nameB,
  format,
  height,
}: {
  title: string
  rows: { metric: string; a: number | null; b: number | null }[]
  nameA: string
  nameB: string
  format: (value: number) => string
  height: string
}) {
  const summary = rows
    .map((row) => `${row.metric}: ${nameA} ${row.a === null ? "not available" : format(row.a)}, ${nameB} ${row.b === null ? "not available" : format(row.b)}`)
    .join("; ")

  return (
    <div>
      <h2 className="mb-1 text-sm font-medium">{title}</h2>
      <div className={`${height} w-full`} role="img" aria-label={`${title}. ${summary}`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 52, bottom: 4, left: 4 }}>
            <CartesianGrid horizontal={false} stroke="var(--border)" />
            <XAxis type="number" tick={AXIS_TICK} tickFormatter={(value: number) => format(value)} />
            <YAxis type="category" dataKey="metric" width={120} tick={AXIS_TICK} />
            <Tooltip
              cursor={{ fill: "var(--muted)" }}
              contentStyle={TOOLTIP_STYLE}
              itemStyle={TOOLTIP_ITEM_STYLE}
              formatter={(value) => (typeof value === "number" ? format(value) : "Not available")}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="a" name={nameA} fill={SERIES_EMPHASIS} radius={[0, 4, 4, 0]} isAnimationActive={false}>
              <LabelList
                dataKey="a"
                position="right"
                fill="var(--foreground)"
                fontSize={12}
                formatter={(value: unknown) => (typeof value === "number" ? format(value) : "")}
              />
            </Bar>
            <Bar dataKey="b" name={nameB} fill={SERIES_MUTED} radius={[0, 4, 4, 0]} isAnimationActive={false}>
              <LabelList
                dataKey="b"
                position="right"
                fill="var(--foreground)"
                fontSize={12}
                formatter={(value: unknown) => (typeof value === "number" ? format(value) : "")}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
