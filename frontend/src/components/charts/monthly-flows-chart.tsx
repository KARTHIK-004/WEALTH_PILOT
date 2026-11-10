import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"

import { AXIS_TICK, SLICE_COLORS, TOOLTIP_ITEM_STYLE, TOOLTIP_STYLE } from "@/components/charts/chart-theme"
import { formatCurrency } from "@/lib/format"

export interface MonthlyFlowPoint {
  period: string
  income: number | null
  expenses: number | null
  savings: number | null
}

/**
 * Reported income, expenses and savings per month, plotted exactly as given (the figures are the reported amounts; nothing is derived here). It is DISPLAY ONLY and always sits beside a table
 * carrying the same values (`docs/DESIGN.md` section 16). Each line is also named in the legend and in the accessible description, never by colour alone; a month with no amount leaves a gap.
 */
export function MonthlyFlowsChart({ points }: { points: MonthlyFlowPoint[] }) {
  const summary = points.map((p) => `${p.period}: income ${formatCurrency(p.income)}, expenses ${formatCurrency(p.expenses)}, savings ${formatCurrency(p.savings)}`).join("; ")
  return (
    <div className="h-64 w-full" role="img" aria-label={`Line chart of reported income, expenses and savings by month. ${summary}`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="period" tick={AXIS_TICK} />
          <YAxis tick={AXIS_TICK} width={64} tickFormatter={(value: number) => formatCurrency(value)} />
          <Tooltip contentStyle={TOOLTIP_STYLE} itemStyle={TOOLTIP_ITEM_STYLE} formatter={(value) => (typeof value === "number" ? formatCurrency(value) : String(value))} />
          <Legend wrapperStyle={{ fontSize: 12 }} formatter={(value: string) => <span style={{ color: "var(--foreground)" }}>{value}</span>} />
          <Line type="monotone" dataKey="income" name="Income" stroke={SLICE_COLORS[0]} strokeWidth={2} dot isAnimationActive={false} connectNulls={false} />
          <Line type="monotone" dataKey="expenses" name="Expenses" stroke={SLICE_COLORS[2]} strokeWidth={2} strokeDasharray="6 3" dot isAnimationActive={false} connectNulls={false} />
          <Line type="monotone" dataKey="savings" name="Savings" stroke={SLICE_COLORS[4]} strokeWidth={2} strokeDasharray="2 3" dot isAnimationActive={false} connectNulls={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
