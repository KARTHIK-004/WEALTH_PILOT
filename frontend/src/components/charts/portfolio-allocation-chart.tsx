import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts"

import { SLICE_COLORS, TOOLTIP_ITEM_STYLE, TOOLTIP_STYLE } from "@/components/charts/chart-theme"
import { SectionUnavailable } from "@/components/shell/section-unavailable"
import { formatPercent } from "@/lib/format"
import { getAssetDisplayName } from "@/lib/terminology"

/**
 * Renders ONLY the authoritative `weights` map an analysis/recommendation
 * response already contains — no weight is calculated, normalized, or
 * sorted by a derived metric. The key beneath the donut names every asset
 * with its own weight, so a slice is never identified by colour alone; the
 * page also keeps its `AllocationTable` next to this chart.
 *
 * `weights === null` means the backend produced no allocation (a
 * savings-first result, for instance). That is reported as unavailable —
 * it is never drawn as an empty or zero-weight donut. Callers pass the
 * status-specific explanation via `unavailableReason`.
 *
 * Investments are named in plain words (`lib/terminology.ts`) in the key,
 * the tooltip and the accessible label; the weights are untouched.
 */
export function PortfolioAllocationChart({
  weights,
  unavailableReason,
}: {
  weights: Record<string, number> | null | undefined
  unavailableReason?: string | null
}) {
  if (!weights) {
    return <SectionUnavailable reason={unavailableReason ?? "no allocation was returned"} />
  }

  const data = Object.entries(weights).map(([ticker, weight]) => ({ asset: getAssetDisplayName(ticker), ticker, weight }))

  return (
    <div className="space-y-3">
      <div
        className="h-56 w-full"
        role="img"
        aria-label={`Investment allocation: ${data.map((d) => `${d.asset} ${formatPercent(d.weight)}`).join(", ")}`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="weight"
              nameKey="asset"
              innerRadius={50}
              outerRadius={90}
              paddingAngle={2}
              stroke="var(--border)"
              isAnimationActive={false}
            >
              {data.map((entry, index) => (
                <Cell key={entry.ticker} fill={SLICE_COLORS[index % SLICE_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              itemStyle={TOOLTIP_ITEM_STYLE}
              formatter={(value, name) => [typeof value === "number" ? formatPercent(value) : String(value), name]}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="flex flex-wrap justify-center gap-x-4 gap-y-1 text-sm" aria-label="Investment allocation key">
        {data.map((entry, index) => (
          <li key={entry.ticker} className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="inline-block size-3 rounded-sm border"
              style={{ backgroundColor: SLICE_COLORS[index % SLICE_COLORS.length] }}
            />
            <span className="font-medium">{entry.asset}</span>
            <span className="text-muted-foreground">{formatPercent(entry.weight)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
