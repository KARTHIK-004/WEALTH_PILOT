import { getStrategyDisplayName } from "@/lib/terminology"
import type { components } from "@/types/api"

type Recommendation = components["schemas"]["RecommendationSection"]

/** The backend's structured rationale fields, each put into one plain
 * sentence. Only fields the API returned are used; a missing field is
 * simply not described. Strategy values are named via `lib/terminology.ts`. */
export function RationaleInPlainWords({ recommendation }: { recommendation: Recommendation }) {
  const r = recommendation.rationale
  const name = (value: string | null | undefined) => getStrategyDisplayName(value) ?? "a different approach"
  const sentences: string[] = []
  if (r.risk_based_strategy) {
    sentences.push(
      `Your risk profile${recommendation.risk_category ? ` (${recommendation.risk_category})` : ""} points to the ${name(r.risk_based_strategy)} approach.`,
    )
  }
  if (r.goal_preference) {
    sentences.push(
      `Your goals${r.goal_feasibility_used ? ` (overall outlook: ${r.goal_feasibility_used})` : ""} favour the ${name(r.goal_preference)} approach${
        r.goal_preference_aligned ? ", which matches." : ", but your risk profile takes priority."
      }`,
    )
  }
  if (r.market_preference) {
    sentences.push(
      `Current market conditions${r.market_regime_used ? ` (${r.market_regime_used})` : ""} favour the ${name(r.market_preference)} approach${
        r.market_preference_aligned ? ", which matches." : ", but your risk profile takes priority."
      }`,
    )
  }
  if (sentences.length === 0) {
    return <p className="text-muted-foreground text-sm">No reasons were recorded for this recommendation.</p>
  }
  return (
    <ul className="list-disc space-y-1 pl-5 text-sm">
      {sentences.map((sentence) => (
        <li key={sentence}>{sentence}</li>
      ))}
    </ul>
  )
}
