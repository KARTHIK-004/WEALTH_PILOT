import { TermLabel } from "@/components/shell/help-tip"
import { TechnicalDetails } from "@/components/shell/technical-details"
import { Badge } from "@/components/ui/badge"
import { HELP, getAssetDisplayName, getStrategyInfo } from "@/lib/terminology"

/**
 * The selected portfolio strategy in plain words (`docs/DESIGN.md` section
 * 30): "Optimized Portfolio" for the API's `mvo`, with what it means, and the
 * real method name, the raw API value and the tickers in Technical details.
 * Display only -- `strategy` and `weights` are the API's own values.
 */
export function StrategySummary({
  strategy,
  riskCategory,
  weights,
}: {
  strategy: string | null | undefined
  riskCategory: string | null | undefined
  weights: Record<string, number> | null | undefined
}) {
  const info = getStrategyInfo(strategy)
  const tickers = Object.keys(weights ?? {})

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-muted-foreground text-xs">
          <TermLabel help={HELP.portfolioStrategy}>Investment strategy</TermLabel>
        </span>
        <Badge className="text-sm">{info?.label ?? "Not available"}</Badge>
      </div>
      <p className="text-muted-foreground text-sm">
        An allocation selected for {riskCategory ? `the ${riskCategory} risk profile` : "this risk profile"} using the
        available portfolio rules and constraints.
        {info?.help ? ` ${info.help}` : ""}
      </p>
      <TechnicalDetails
        items={[
          { label: "Optimization method", value: info?.technical },
          { label: "API value", value: strategy },
          {
            label: "Assets",
            value: tickers.length ? tickers.map((ticker) => `${ticker} (${getAssetDisplayName(ticker)})`).join(", ") : null,
          },
        ]}
      />
    </div>
  )
}
