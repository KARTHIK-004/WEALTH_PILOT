import { TermLabel } from "@/components/shell/help-tip"
import { TechnicalDetails } from "@/components/shell/technical-details"
import { formatPercent } from "@/lib/format"
import { METRICS } from "@/lib/terminology"

function formatSharpe(value: number | null | undefined): string {
  return value === null || value === undefined ? "Not available" : value.toFixed(2)
}

/** Three already-authoritative figures, each rendered independently —
 * `sharpeRatio` is shown as a plain decimal (matching the same
 * convention `core.recommendation`'s own validation uses for it, never
 * treated as a fraction to be "%"-formatted, unlike return/volatility).
 *
 * Plain-language labels (`docs/DESIGN.md` section 30): "Expected
 * variability" for volatility and "Risk-adjusted performance" for the
 * Sharpe ratio, each with a help tip. The numbers are unchanged; the
 * technical names are kept in Technical details. */
export function PortfolioMetrics({
  expectedReturn,
  expectedVolatility,
  sharpeRatio,
  showTechnical = true,
}: {
  expectedReturn: number | null
  expectedVolatility: number | null
  sharpeRatio: number | null
  showTechnical?: boolean
}) {
  return (
    <div className="space-y-3">
      <dl className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div>
          <dt className="text-muted-foreground text-xs">
            <TermLabel help={METRICS.expectedReturn.help}>{METRICS.expectedReturn.label}</TermLabel>
          </dt>
          <dd className="text-sm font-medium">{formatPercent(expectedReturn)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">
            <TermLabel help={METRICS.expectedVariability.help}>{METRICS.expectedVariability.label}</TermLabel>
          </dt>
          <dd className="text-sm font-medium">{formatPercent(expectedVolatility)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">
            <TermLabel help={METRICS.riskAdjusted.help}>{METRICS.riskAdjusted.label}</TermLabel>
          </dt>
          <dd className="text-sm font-medium">{formatSharpe(sharpeRatio)}</dd>
        </div>
      </dl>
      {showTechnical ? (
        <TechnicalDetails
          items={[
            { label: METRICS.expectedReturn.technical, value: formatPercent(expectedReturn, 1) },
            { label: METRICS.expectedVariability.technical, value: formatPercent(expectedVolatility, 1) },
            { label: METRICS.riskAdjusted.technical, value: formatSharpe(sharpeRatio) },
          ]}
        />
      ) : null}
    </div>
  )
}
