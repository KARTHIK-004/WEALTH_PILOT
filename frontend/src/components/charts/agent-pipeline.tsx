import { Ban, CheckCircle2, CircleDot, Clock, Loader2, XCircle } from "lucide-react"

import { StatusBadge } from "@/components/shell/status-badge"
import { TechnicalDetails } from "@/components/shell/technical-details"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { StreamConnectionState } from "@/hooks/use-analysis-stream"
import { formatStatusLabel } from "@/lib/format"
import type { NodeProgressEvent } from "@/lib/sse-client"
import { getAnalysisStep } from "@/lib/terminology"

/**
 * A step-by-step view of ONLY the events `GET /api/analysis/stream` has
 * actually delivered, in the order they arrived. It does not know the
 * pipeline's topology: no step that has not been received is drawn, so a
 * savings-first run never shows a portfolio-optimisation step, a rejected
 * run never shows a recommendation or explanation step, and nothing is
 * marked complete before its event arrives. Only the five safe SSE fields
 * (`node`, `status`, `duration_ms`, `summary`, `model_version`) are read.
 *
 * Plain-language presentation (`docs/DESIGN.md` section 30): each step is
 * named for what it does ("Assessing risk", "Running compliance checks" --
 * `lib/terminology.ts`), not by its node id. The node id, where it runs
 * (LangGraph node or the post-graph step), the backend's own summary,
 * duration and model version are all kept, unchanged, in the Technical
 * details table below the timeline. Nothing is fabricated: one row per
 * event received.
 */
const OUTCOME_NODES = new Set(["approved", "rejected", "pending_information", "failed"])

const EVENT_STATUS_LABEL: Record<string, string> = {
  completed: "Done",
  started: "Started",
  failed: "Failed",
}

function StepIcon({ event }: { event: NodeProgressEvent }) {
  if (event.status === "failed" || event.node === "failed") {
    return <XCircle className="text-destructive size-5" aria-hidden="true" />
  }
  // A terminal "outcome" node reports status "completed" even when its
  // outcome is a rejection, so the icon follows the outcome named by the
  // node itself rather than implying success.
  if (event.node === "rejected") return <Ban className="text-destructive size-5" aria-hidden="true" />
  if (event.node === "pending_information") return <Clock className="text-muted-foreground size-5" aria-hidden="true" />
  if (event.status === "started") return <CircleDot className="text-muted-foreground size-5" aria-hidden="true" />
  return <CheckCircle2 className="text-primary size-5" aria-hidden="true" />
}

export function AgentPipeline({ events, state }: { events: NodeProgressEvent[]; state: StreamConnectionState }) {
  const waiting = state === "connecting" || state === "streaming"

  return (
    <div className="space-y-4">
      <ol className="space-y-0" aria-label="Analysis steps received so far">
        {events.map((event, index) => {
          const isLast = index === events.length - 1 && !waiting
          const isFinal = event.node === "analysis_completed"
          return (
            <li key={`${index}-${event.node}`} className="flex gap-3">
              <div className="flex flex-col items-center">
                <StepIcon event={event} />
                {!isLast ? <div className="bg-border my-1 w-px flex-1" aria-hidden="true" /> : null}
              </div>
              <div className={`min-w-0 flex-1 ${isLast ? "pb-0" : "pb-4"}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-medium">{getAnalysisStep(event.node).label}</p>
                  {isFinal || OUTCOME_NODES.has(event.node) ? (
                    <StatusBadge status={isFinal ? event.status : event.node} />
                  ) : (
                    <Badge variant="outline">{EVENT_STATUS_LABEL[event.status] ?? formatStatusLabel(event.status)}</Badge>
                  )}
                </div>
              </div>
            </li>
          )
        })}
        {waiting ? (
          <li className="text-muted-foreground flex items-center gap-3 text-sm">
            <Loader2 className="size-5 animate-spin" aria-hidden="true" />
            {state === "connecting" ? "Starting the analysis…" : "Working on the next step…"}
          </li>
        ) : null}
      </ol>

      {events.length > 0 ? (
        <TechnicalDetails>
          <p className="text-muted-foreground">
            Each step is a node of the LangGraph analysis pipeline (the recommendation and explanation steps run
            right after it). Only these progress fields are streamed — never a prompt or model reasoning.
          </p>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Step</TableHead>
                  <TableHead>Node</TableHead>
                  <TableHead>Runs as</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Duration</TableHead>
                  <TableHead>Model</TableHead>
                  <TableHead>Summary</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {events.map((event, index) => (
                  <TableRow key={`tech-${index}-${event.node}`}>
                    <TableCell>{getAnalysisStep(event.node).label}</TableCell>
                    <TableCell className="font-mono">{event.node}</TableCell>
                    <TableCell>{getAnalysisStep(event.node).framework}</TableCell>
                    <TableCell className="font-mono">{event.status}</TableCell>
                    <TableCell className="text-right">{event.duration_ms !== null ? `${event.duration_ms} ms` : "—"}</TableCell>
                    <TableCell>{event.model_version ?? "—"}</TableCell>
                    <TableCell className="min-w-48 whitespace-normal">{event.summary ?? "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TechnicalDetails>
      ) : null}
    </div>
  )
}
