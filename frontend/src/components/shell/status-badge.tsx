import { AlertTriangle, Ban, CheckCircle2, CircleAlert, CircleHelp, Clock, XCircle } from "lucide-react"
import type { ComponentProps } from "react"

import { Badge } from "@/components/ui/badge"
import { formatStatusLabel } from "@/lib/format"
import { getStatusLabel } from "@/lib/terminology"

type BadgeVariant = ComponentProps<typeof Badge>["variant"]

/**
 * One consistent status-badge mapping reused by every page (section 29:
 * "use text labels in addition to visual styling... do not communicate
 * important status using color alone"). Every badge always renders BOTH
 * an icon and the status's own text label — never color/icon alone.
 * Covers every status vocabulary the API actually returns: compliance
 * (PASS/WARN/REJECT), recommendation (approved/savings_first/
 * blocked_rejected/failed), goal feasibility (Feasible/At Risk/Not
 * Feasible), and the overall analysis status
 * (approved/rejected/pending_information/failed).
 *
 * The words shown come from `lib/terminology.ts` (plain labels such as
 * "Passed" for `PASS`, "Not approved" for `REJECT`/`rejected`); the status
 * value itself is never changed, and the variant/icon still follow the raw
 * value, so a rejection can never be styled or worded as an approval.
 */
const STATUS_MAP: Record<string, { variant: BadgeVariant; icon: typeof CheckCircle2 }> = {
  PASS: { variant: "default", icon: CheckCircle2 },
  WARN: { variant: "secondary", icon: AlertTriangle },
  REJECT: { variant: "destructive", icon: XCircle },
  approved: { variant: "default", icon: CheckCircle2 },
  savings_first: { variant: "secondary", icon: CircleAlert },
  blocked_rejected: { variant: "destructive", icon: Ban },
  rejected: { variant: "destructive", icon: Ban },
  failed: { variant: "destructive", icon: XCircle },
  pending_information: { variant: "secondary", icon: Clock },
  Feasible: { variant: "default", icon: CheckCircle2 },
  "At Risk": { variant: "secondary", icon: AlertTriangle },
  "Not Feasible": { variant: "destructive", icon: XCircle },
  sufficient: { variant: "default", icon: CheckCircle2 },
  insufficient: { variant: "secondary", icon: AlertTriangle },
}

export function StatusBadge({ status }: { status: string | null | undefined }) {
  if (!status) {
    return (
      <Badge variant="outline">
        <CircleHelp />
        Unavailable
      </Badge>
    )
  }
  const entry = STATUS_MAP[status] ?? { variant: "outline" as const, icon: CircleHelp }
  const Icon = entry.icon
  return (
    <Badge variant={entry.variant}>
      <Icon />
      {getStatusLabel(status) ?? formatStatusLabel(status)}
    </Badge>
  )
}
