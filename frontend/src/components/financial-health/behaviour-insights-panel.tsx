import { Activity, Info, Minus, Percent, TrendingDown, TrendingUp } from "lucide-react"
import { Link } from "react-router"

import { SectionUnavailable } from "@/components/shell/section-unavailable"
import { TechnicalDetails } from "@/components/shell/technical-details"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { selectInsightRows, selectNotShown, type Finding, type InsightRow } from "@/lib/behaviour-insights"
import type { components } from "@/types/api"

type Behaviour = components["schemas"]["BehaviourFindingsOut"]

/** The icon only repeats what the row's words and direction label already say (it is hidden from screen readers). It carries no judgement: an increase is not marked good or bad. */
function RowIcon({ row }: { row: InsightRow }) {
  const props = { className: "size-4", "aria-hidden": true as const }
  if (row.direction === "increased") return <TrendingUp {...props} />
  if (row.direction === "decreased") return <TrendingDown {...props} />
  if (row.direction === "unchanged") return <Minus {...props} />
  if (row.category === "ratio") return <Percent {...props} />
  if (row.category === "activity") return <Activity {...props} />
  return <Info {...props} />
}

function InsightItem({ row }: { row: InsightRow }) {
  return (
    <li className="flex items-start gap-3 rounded-lg border p-3">
      <span className="bg-muted text-muted-foreground mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md">
        <RowIcon row={row} />
      </span>
      <div className="min-w-0 flex-1 space-y-1.5">
        <p className="text-sm leading-snug">{row.statement}</p>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <Badge variant="outline">{row.categoryLabel}</Badge>
          {row.directionLabel ? <Badge variant="secondary">{row.directionLabel}</Badge> : null}
          {row.sources.length > 0 ? <span className="text-muted-foreground text-xs [overflow-wrap:anywhere]">Based on: {row.sources.join(", ")}</span> : null}
        </div>
      </div>
    </li>
  )
}

function NotShown({ findings, notes }: { findings: Finding[]; notes: string[] }) {
  if (findings.length === 0 && notes.length === 0) return null
  return (
    <TechnicalDetails title="What is not shown, and why">
      <ul className="space-y-1 text-sm">
        {findings.map((finding) => (
          <li key={finding.code}>{finding.statement}</li>
        ))}
        {notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </TechnicalDetails>
  )
}

/**
 * "What your records show": the observed facts the backend produced from the months the customer reported, as a compact list. DISPLAY ONLY (ADR-043, ADR-048): every sentence, direction and
 * source field is the backend's; nothing here is calculated, ranked or judged. Fewer than two reported months, or none, is said plainly and nothing is assumed in its place.
 */
export function BehaviourInsightsPanel({ behaviour }: { behaviour: Behaviour }) {
  const rows = selectInsightRows(behaviour.findings)
  const notShown = selectNotShown(behaviour.findings).filter((f) => !(f.sources.length === 1 && f.sources[0] === "observation_count"))
  const months = behaviour.observation_count
  return (
    <Card role="region" aria-labelledby="insights-heading">
      <CardHeader>
        <CardTitle id="insights-heading" role="heading" aria-level={2} className="text-base">
          What your records show
        </CardTitle>
        <CardDescription>
          Facts from the months you reported, worked out by the system. They describe your numbers, not your feelings.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">
            {months} reported month{months === 1 ? "" : "s"}
          </Badge>
          {behaviour.latest_period ? <span className="text-muted-foreground text-xs">latest {behaviour.latest_period}</span> : null}
        </div>
        {months === 0 ? (
          <SectionUnavailable
            title="No monthly records yet"
            message="Add the months you can in your monthly records and the changes in your income, expenses and savings will appear here. Nothing is assumed in the meantime."
          />
        ) : rows.length === 0 ? (
          <SectionUnavailable title="Nothing to describe yet" message="The months reported so far do not give enough to describe a change or a ratio." />
        ) : (
          <ul className="space-y-2" aria-label="Observed from your records">
            {rows.map((row) => (
              <InsightItem key={row.code} row={row} />
            ))}
          </ul>
        )}
        {months === 0 ? (
          <p className="text-muted-foreground text-xs">
            Monthly records are added on the{" "}
            <Link to="/profile" className="text-primary underline underline-offset-2">
              Customer Profile
            </Link>{" "}
            page.
          </p>
        ) : null}
        <NotShown findings={notShown} notes={behaviour.data_quality_notes} />
      </CardContent>
    </Card>
  )
}
