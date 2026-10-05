import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"

import { AXIS_TICK, SERIES_EMPHASIS, SERIES_MUTED, TOOLTIP_ITEM_STYLE, TOOLTIP_STYLE } from "@/components/charts/chart-theme"
import { SectionUnavailable } from "@/components/shell/section-unavailable"
import { formatCurrency } from "@/lib/format"

/**
 * One goal's target amount next to its inflation-adjusted target, both as
 * returned by `AnalysisResult.goals[]` (`nominal_target_amount`,
 * `inflation_adjusted_target_amount`). Two amounts in the same unit, so
 * one axis is honest; the monthly contribution and the Monte Carlo
 * probability are different units and are deliberately not plotted here.
 * When the adjusted target is unavailable (`null`) the chart is replaced
 * by the reason — it never plots a single bar as if it were a comparison.
 */
export function GoalTargetChart({
  goalType,
  nominalTarget,
  inflationAdjustedTarget,
  unavailableReason,
}: {
  goalType: string
  nominalTarget: number
  inflationAdjustedTarget: number | null | undefined
  unavailableReason?: string | null
}) {
  if (inflationAdjustedTarget === null || inflationAdjustedTarget === undefined) {
    return (
      <SectionUnavailable
        reason={unavailableReason ?? "the target after inflation was not returned, so there is nothing to compare"}
      />
    )
  }

  const data = [
    { label: "Target", amount: nominalTarget },
    { label: "After inflation", amount: inflationAdjustedTarget },
  ]

  return (
    <div
      className="h-32 w-full"
      role="img"
      aria-label={`${goalType}: target ${formatCurrency(nominalTarget)}, target after inflation ${formatCurrency(inflationAdjustedTarget)}`}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 76, bottom: 4, left: 4 }}>
          <CartesianGrid horizontal={false} stroke="var(--border)" />
          <XAxis type="number" tick={AXIS_TICK} tickFormatter={(value: number) => formatCurrency(value)} />
          <YAxis type="category" dataKey="label" width={112} tick={AXIS_TICK} />
          <Tooltip
            cursor={{ fill: "var(--muted)" }}
            contentStyle={TOOLTIP_STYLE}
            itemStyle={TOOLTIP_ITEM_STYLE}
            formatter={(value) => [typeof value === "number" ? formatCurrency(value) : String(value), "Amount"]}
          />
          <Bar dataKey="amount" radius={[0, 4, 4, 0]} isAnimationActive={false}>
            {data.map((entry) => (
              <Cell key={entry.label} fill={entry.label === "Target" ? SERIES_MUTED : SERIES_EMPHASIS} />
            ))}
            <LabelList
              dataKey="amount"
              position="right"
              fill="var(--foreground)"
              fontSize={12}
              formatter={(value: unknown) => (typeof value === "number" ? formatCurrency(value) : "")}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
