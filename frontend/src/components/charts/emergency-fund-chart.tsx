import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"

import { AXIS_TICK, SERIES_EMPHASIS, SERIES_MUTED, TOOLTIP_ITEM_STYLE, TOOLTIP_STYLE } from "@/components/charts/chart-theme"
import { SectionUnavailable } from "@/components/shell/section-unavailable"
import { formatCurrency } from "@/lib/format"

/**
 * Required vs current emergency fund, plotted from the backend's own
 * `emergency_fund.required_amount` / `.current_amount`. The shortfall is
 * the backend's `.shortfall` value, shown as text beside the chart —
 * it is never computed here (`core/goals.py::assess_emergency_fund`
 * owns it). A missing amount makes the chart unavailable; it is never
 * drawn as a zero-length bar.
 */
export function EmergencyFundChart({
  required,
  current,
  shortfall,
  sufficient,
  unavailableReason,
}: {
  required: number | null | undefined
  current: number | null | undefined
  shortfall: number | null | undefined
  sufficient: boolean | null | undefined
  unavailableReason?: string | null
}) {
  if (required === null || required === undefined || current === null || current === undefined) {
    return <SectionUnavailable reason={unavailableReason ?? "the emergency-fund amounts were not returned"} />
  }

  const data = [
    { label: "Target", amount: required },
    { label: "Available now", amount: current },
  ]

  return (
    <div className="space-y-2">
      <div
        className="h-36 w-full"
        role="img"
        aria-label={`Emergency savings: recommended target ${formatCurrency(required)}, available now ${formatCurrency(current)}`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 72, bottom: 4, left: 4 }}>
            <CartesianGrid horizontal={false} stroke="var(--border)" />
            <XAxis type="number" tick={AXIS_TICK} tickFormatter={(value: number) => formatCurrency(value)} />
            <YAxis type="category" dataKey="label" width={96} tick={AXIS_TICK} />
            <Tooltip
              cursor={{ fill: "var(--muted)" }}
              contentStyle={TOOLTIP_STYLE}
              itemStyle={TOOLTIP_ITEM_STYLE}
              formatter={(value) => [typeof value === "number" ? formatCurrency(value) : String(value), "Amount"]}
            />
            <Bar dataKey="amount" radius={[0, 4, 4, 0]} isAnimationActive={false}>
              {data.map((entry) => (
                <Cell key={entry.label} fill={entry.label === "Available now" ? SERIES_EMPHASIS : SERIES_MUTED} />
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
      <p className="text-sm">
        <span className="text-muted-foreground">Shortfall: </span>
        <span className="font-medium">{formatCurrency(shortfall)}</span>
        {sufficient === true ? <span className="text-muted-foreground"> — your emergency savings meet the target.</span> : null}
        {sufficient === false ? <span className="text-muted-foreground"> — your emergency savings are below the target.</span> : null}
      </p>
    </div>
  )
}
