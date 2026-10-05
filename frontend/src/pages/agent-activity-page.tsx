import { Play, XCircle } from "lucide-react"

import { AgentPipeline } from "@/components/charts/agent-pipeline"
import { NoProfileSelected } from "@/components/shell/no-profile-selected"
import { PageContainer } from "@/components/shell/page-container"
import { TechnicalDetails } from "@/components/shell/technical-details"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useAnalysisStream } from "@/hooks/use-analysis-stream"
import { useCustomer } from "@/providers/customer-context"

/**
 * Shows WHAT NODE IS RUNNING, never what a model is "thinking" (section
 * 23). Every event rendered is a `NodeProgressEvent` exactly as
 * `GET /api/analysis/stream` sends it -- `node`/`status`/`duration_ms`/
 * `summary`/`model_version` only. There is no field anywhere in that
 * shape for a prompt, a reasoning trace, or an AutoGen transcript, so
 * none can appear here by construction, not by filtering. `AgentPipeline`
 * draws only the events actually received, in arrival order.
 *
 * Plain-language presentation (`docs/DESIGN.md` section 30): the page is
 * framed as "Analysis progress" with steps such as "Assessing risk"; the
 * node ids, LangGraph framing, durations and model versions remain in
 * Technical details for evaluation.
 */
export function AgentActivityPage() {
  const { profileId } = useCustomer()
  const { events, state, errorMessage, start } = useAnalysisStream()

  if (profileId === null) {
    return (
      <PageContainer title="Agent Activity" description="Follow each step of your analysis as it runs, from checking your profile to preparing the explanation.">
        <NoProfileSelected />
      </PageContainer>
    )
  }

  return (
    <PageContainer title="Agent Activity" description="Follow each step of your analysis as it runs, from checking your profile to preparing the explanation.">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <CardTitle>Analysis progress</CardTitle>
              <CardDescription>Starts a fresh analysis and shows each step as it finishes.</CardDescription>
            </div>
            <Button
              onClick={() => start(profileId)}
              disabled={state === "connecting" || state === "streaming"}
            >
              <Play />
              {state === "streaming" || state === "connecting" ? "Running…" : "Start analysis"}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {state === "error" ? (
            <Alert variant="destructive" className="mb-4">
              <XCircle />
              <AlertTitle>The analysis progress could not be shown</AlertTitle>
              <AlertDescription className="space-y-2">
                <p>We couldn't follow this analysis run. Please try again.</p>
                {errorMessage ? <TechnicalDetails items={[{ label: "Error", value: errorMessage }]} /> : null}
              </AlertDescription>
            </Alert>
          ) : null}

          {state === "idle" && events.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              Press "Start analysis" to watch each step of the analysis run for this profile.
            </p>
          ) : (
            <ScrollArea className="h-96 pr-4">
              <AgentPipeline events={events} state={state} />
            </ScrollArea>
          )}
        </CardContent>
      </Card>
    </PageContainer>
  )
}
