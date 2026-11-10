import { Link } from "react-router"

import { ErrorState } from "@/components/shell/error-state"
import { LoadingState } from "@/components/shell/loading-state"
import { SectionUnavailable } from "@/components/shell/section-unavailable"
import { Badge } from "@/components/ui/badge"
import { usePersonalizedInsightQuery } from "@/hooks/use-personalized-insight"
import { selectSpendingRows } from "@/lib/behaviour-insights"
import type { components } from "@/types/api"

type Insight = components["schemas"]["PersonalizedInsightResponse"]

export interface SpendingFromRecordsViewProps {
  data: Insight | undefined
  loading: boolean
  error: unknown
  onRetry: () => void
}

/**
 * "What your reported months show" inside the Spending and expenses card. DISPLAY ONLY: the sentences are the backend's own behaviour findings (`GET`-equivalent of
 * `POST /api/profiles/{id}/personalized-insights`, the same response the behaviour summary uses); this view selects the spending ones and never calculates a change, a share or a total.
 * Every state is distinct: loading, a failed request (never hidden behind an empty message), no reported months, and findings.
 *
 * WealthPilot stores an individual's spending only as ONE monthly total, so there is no category breakdown for an individual: the view says so instead of inventing one.
 */
export function SpendingFromRecordsView({ data, loading, error, onRetry }: SpendingFromRecordsViewProps) {
  if (error) return <ErrorState error={error} onRetry={onRetry} />
  if (loading || !data) return <LoadingState label="Reading your reported months" />
  const rows = selectSpendingRows(data.behaviour.findings)
  return (
    <div className="space-y-2" role="group" aria-label="Spending in your reported months">
      <p className="text-muted-foreground text-xs">From your reported months</p>
      {rows.length === 0 ? (
        <SectionUnavailable
          title="No reported months yet"
          message="Your spending over time is shown from the months you report. None have been reported for this profile, so nothing is assumed."
        />
      ) : (
        <ul className="space-y-2">
          {rows.map((row) => (
            <li key={row.code} className="space-y-1">
              <p className="text-sm">{row.statement}</p>
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <Badge variant="outline">{row.categoryLabel}</Badge>
                {row.directionLabel ? <Badge variant="secondary">{row.directionLabel}</Badge> : null}
                <span className="text-muted-foreground text-xs [overflow-wrap:anywhere]">Based on: {row.sources.join(", ")}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
      <p className="text-muted-foreground text-xs">
        An individual's spending is recorded as one total each month, so there is no category breakdown here. A household records its spending by category on{" "}
        <Link to="/profile?household=open" className="text-primary underline underline-offset-2">
          Customer Profile → Household
        </Link>
        .
      </p>
    </div>
  )
}

export function SpendingFromRecords({ profileId }: { profileId: number }) {
  const insight = usePersonalizedInsightQuery(profileId, null)
  return <SpendingFromRecordsView data={insight.data} loading={insight.isLoading} error={insight.error} onRetry={() => void insight.refetch()} />
}
