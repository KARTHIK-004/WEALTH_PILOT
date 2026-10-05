import { AlertTriangle, WifiOff } from "lucide-react"

import { TechnicalDetails } from "@/components/shell/technical-details"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { ApiClientError, ApiUnreachableError } from "@/lib/api-client"

/** Plain wording by HTTP status class -- the problem body's own title and
 * detail (often written for developers, e.g. a validation message) are
 * kept, unchanged, in Technical details for debugging. */
function friendlyMessage(status: number | undefined): { title: string; detail: string } {
  if (status === 404) return { title: "Information not found", detail: "We couldn't find this information. It may not have been created yet." }
  if (status === 422 || status === 400)
    return { title: "We couldn't complete this request", detail: "Some of the information could not be accepted. Please check it and try again." }
  if (status !== undefined && status >= 500)
    return { title: "We couldn't complete this analysis", detail: "Something went wrong on our side. Please try again." }
  return { title: "Something went wrong", detail: "We couldn't complete this request. Please try again." }
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const isUnreachable = error instanceof ApiUnreachableError
  const problem = error instanceof ApiClientError ? error.problem : null
  const friendly = isUnreachable
    ? {
        title: "Service unavailable",
        detail: "WealthPilot could not be reached. It may be starting up or temporarily offline. Please try again shortly.",
      }
    : friendlyMessage(problem?.status)

  return (
    <Alert variant="destructive">
      {isUnreachable ? <WifiOff /> : <AlertTriangle />}
      <AlertTitle>{friendly.title}</AlertTitle>
      <AlertDescription className="space-y-3">
        <p>{friendly.detail}</p>
        {onRetry ? (
          <Button variant="outline" size="sm" onClick={onRetry}>
            Try again
          </Button>
        ) : null}
        {problem ? (
          <TechnicalDetails
            className="text-foreground"
            items={[
              { label: "Status", value: problem.status },
              { label: "Title", value: problem.title },
              { label: "Detail", value: problem.detail },
            ]}
          />
        ) : null}
      </AlertDescription>
    </Alert>
  )
}
