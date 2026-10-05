import { CircleSlash } from "lucide-react"

import { TechnicalDetails } from "@/components/shell/technical-details"

/**
 * One consistent "not available" block. With a plain-language `message`
 * (`docs/DESIGN.md` section 30) the backend's own `reason` -- often written
 * for developers -- moves into Technical details instead of being hidden.
 * Without one, the reason is shown directly, exactly as before, so an
 * unanticipated reason is never lost. Unavailable is never shown as 0.
 */
export function SectionUnavailable({
  reason,
  title,
  message,
}: {
  reason?: string | null
  title?: string
  message?: string
}) {
  if (message) {
    return (
      <div className="text-muted-foreground space-y-2 rounded-md border border-dashed p-3 text-sm">
        <div className="flex items-start gap-2">
          <CircleSlash className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <div className="space-y-0.5">
            <p className="text-foreground font-medium">{title ?? "Not available"}</p>
            <p>{message}</p>
          </div>
        </div>
        {reason ? <TechnicalDetails items={[{ label: "Reason from the analysis", value: reason }]} /> : null}
      </div>
    )
  }
  return (
    <div className="text-muted-foreground flex items-start gap-2 rounded-md border border-dashed p-3 text-sm">
      <CircleSlash className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <span>{reason ? `Not available: ${reason}` : "Not available for this profile."}</span>
    </div>
  )
}
