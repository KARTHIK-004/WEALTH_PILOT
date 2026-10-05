import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"

import { AXIS_TICK, SERIES_EMPHASIS, SERIES_MUTED, TOOLTIP_ITEM_STYLE, TOOLTIP_STYLE } from "@/components/charts/chart-theme"
import { SectionUnavailable } from "@/components/shell/section-unavailable"
import { formatPercent } from "@/lib/format"

/**
 * Plots `AnalysisResult.risk.class_probabilities` exactly as the API
 * returned it — same labels, same values, same order. Nothing is
 * classified, normalised, ranked or re-sorted here. `selectedCategory`
 * (the API's own `risk.risk_category`) only chooses which bar is drawn
 * darker; the chart never decides a category itself.
 *
 * The x-axis is fixed to 0–100% because every value is a probability;
 * that is a presentation scale, not a calculation.
 */
export function RiskProbabilityChart({
  probabilities,
  selectedCategory,
  unavailableReason,
}: {
  probabilities: Record<string, number> | null | undefined
  selectedCategory?: string | null
  unavailableReason?: string | null
}) {
  if (!probabilities) {
    return <SectionUnavailable reason={unavailableReason ?? "class probabilities were not returned"} />
  }

  const data = Object.entries(probabilities).map(([category, probability]) => ({ category, probability }))

  return (
    <div
      className="h-56 w-full"
      role="img"
      aria-label={`Estimated risk profile (model confidence, not money): ${data.map((d) => `${d.category} ${formatPercent(d.probability, 1)}`).join(", ")}`}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 52, bottom: 4, left: 4 }}>
          <CartesianGrid horizontal={false} stroke="var(--border)" />
          <XAxis type="number" domain={[0, 1]} tick={AXIS_TICK} tickFormatter={(value: number) => formatPercent(value)} />
          <YAxis type="category" dataKey="category" width={96} tick={AXIS_TICK} />
          <Tooltip
            cursor={{ fill: "var(--muted)" }}
            contentStyle={TOOLTIP_STYLE}
            itemStyle={TOOLTIP_ITEM_STYLE}
            formatter={(value) => [typeof value === "number" ? formatPercent(value, 1) : String(value), "Probability"]}
          />
          <Bar dataKey="probability" radius={[0, 4, 4, 0]} isAnimationActive={false}>
            {data.map((entry) => (
              <Cell key={entry.category} fill={entry.category === selectedCategory ? SERIES_EMPHASIS : SERIES_MUTED} />
            ))}
            <LabelList
              dataKey="probability"
              position="right"
              fill="var(--foreground)"
              fontSize={12}
              formatter={(value: unknown) => (typeof value === "number" ? formatPercent(value, 1) : "")}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
