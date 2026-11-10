import { FlaskConical, Info } from "lucide-react"
import { Link } from "react-router"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { DEMO_ADDRESS, DEMO_FAMILY_ADDRESS, DEMO_PAGE_PATH, type DemoProblem } from "@/lib/demo-mode"

export const NOT_ACTIVE_TITLE = "Demonstration mode is not active"
export const NOT_ALLOWED_MESSAGE =
  "Fictional demonstration data is shown only by a development build (or one built with VITE_DEMO_MODE=true). This build does not provide it, so the page below shows your own information."
export const UNKNOWN_VALUE_MESSAGE =
  "The address asked for demonstration mode with a value this page does not know. Use ?demo=true (one fictional person) or ?demo=family (a fictional family). The page below shows your own information."

/** Shown above the NORMAL page when the address carries a `demo` parameter that did not start a demonstration, so the request is never silently ignored. It never shows demo data. */
export function DemoRequestNotice({ problem }: { problem: DemoProblem }) {
  return (
    <Alert role="status" aria-label="Demonstration mode is not active">
      <Info aria-hidden="true" />
      <AlertTitle>{NOT_ACTIVE_TITLE}</AlertTitle>
      <AlertDescription className="space-y-2">
        <p>{problem === "not_allowed" ? NOT_ALLOWED_MESSAGE : UNKNOWN_VALUE_MESSAGE}</p>
        <p>
          <Link to={DEMO_PAGE_PATH} className="text-primary underline underline-offset-2">
            Go to the normal page
          </Link>
        </p>
      </AlertDescription>
    </Alert>
  )
}

/** A developer-only pointer on the REAL page of a profile that has no monthly records (shown only by a build that allows demonstration mode): where the fictional examples are. It is a link, never data. */
export function DevDemoHint() {
  return (
    <Alert role="note" aria-label="Developer note: demonstration data is available">
      <FlaskConical aria-hidden="true" />
      <AlertTitle>Developer note: fictional examples are available</AlertTitle>
      <AlertDescription className="space-y-2">
        <p>
          This profile has no monthly records, so the page shows its empty state. To see what the page looks like with data, open a fictional example (development builds only; it is never used for a real
          profile):
        </p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <Link to={DEMO_FAMILY_ADDRESS} className="text-primary underline underline-offset-2">
              A fictional family (?demo=family)
            </Link>
          </li>
          <li>
            <Link to={DEMO_ADDRESS} className="text-primary underline underline-offset-2">
              One fictional person (?demo=true)
            </Link>
          </li>
        </ul>
        <p className="text-muted-foreground text-xs">The backend must have DEMO_MODE_ENABLED=true and be restarted after changing it.</p>
      </AlertDescription>
    </Alert>
  )
}
