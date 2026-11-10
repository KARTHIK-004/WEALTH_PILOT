import { AlertTriangle, Database, KeyRound, Link2, ShieldAlert } from "lucide-react"

import { ErrorState } from "@/components/shell/error-state"
import { LoadingState } from "@/components/shell/loading-state"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useSecurityStatusQuery } from "@/hooks/use-security-status"
import { ApiClientError } from "@/lib/api-client"
import { ANCHOR_LABELS, ENCRYPTION_LABELS, LEDGER_LABELS } from "@/lib/security-status-labels"
import type { components } from "@/types/api"

type SecurityStatus = components["schemas"]["SecurityStatusOut"]

export interface SecurityStatusViewProps {
  data: SecurityStatus | undefined
  loading: boolean
  error: unknown
  onRetry: () => void
}

/**
 * DISPLAY ONLY. Every state shown here is a value the backend computed from a real check (an encryption round trip with a random probe, a full walk of the audit chain);
 * the page maps those values to words and never decides, estimates or fills in a result. While loading or after an error nothing is shown as verified.
 */
export function SecurityStatusView({ data, loading, error, onRetry }: SecurityStatusViewProps) {
  if (error instanceof ApiClientError && error.problem.status === 503) {
    // The backend answers 503 with a fixed, non-sensitive sentence (for example, the protected-storage migration has not been applied). Show it as sent: the generic
    // message says "analysis", which would mislead on this page.
    return (
      <Alert variant="destructive">
        <AlertTriangle aria-hidden="true" />
        <AlertTitle>Protection status is not available</AlertTitle>
        <AlertDescription className="space-y-3">
          <p>{error.problem.detail}</p>
          <Button variant="outline" size="sm" onClick={onRetry}>
            Try again
          </Button>
        </AlertDescription>
      </Alert>
    )
  }
  if (error) return <ErrorState error={error} onRetry={onRetry} />
  if (loading && !data) return <LoadingState label="Running the security checks" />
  if (!data) return null

  const { encryption, ledger, external_anchor: anchor, existing_data: existing } = data
  return (
    <div className="space-y-4">
      <Alert>
        <ShieldAlert aria-hidden="true" />
        <AlertTitle>{data.prototype_notice}</AlertTitle>
        <AlertDescription>
          The audit trail is a hash-linked log kept in the same private database. It is not decentralized, has no consensus, and is not independently tamper-proof.
        </AlertDescription>
      </Alert>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="text-muted-foreground size-4" aria-hidden="true" /> Where protected notes live
            </CardTitle>
            <CardDescription>Off-chain, in the private application database.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p>
              Protected notes saved for this profile: <span className="font-medium">{data.protected_note_count}</span>
            </p>
            <p className="text-muted-foreground">The note text is never written to the audit trail, a log or the browser&apos;s storage.</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <KeyRound className="text-muted-foreground size-4" aria-hidden="true" /> Encryption
            </CardTitle>
            <CardDescription>{encryption.algorithm}, checked by the backend on this request.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Badge variant={encryption.status === "failed" ? "destructive" : encryption.status === "operational" ? "secondary" : "outline"}>{ENCRYPTION_LABELS[encryption.status]}</Badge>
            {encryption.self_test_passed === null ? null : <p>Self-test: {encryption.self_test_passed ? "passed" : "failed"}</p>}
            {encryption.unavailable_reason ? <p className="text-muted-foreground">{encryption.unavailable_reason}</p> : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Link2 className="text-muted-foreground size-4" aria-hidden="true" /> Local audit chain
            </CardTitle>
            <CardDescription>A hash-linked record of who touched which protected note, without any content.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Badge variant={ledger.verification === "invalid" ? "destructive" : ledger.verification === "valid" ? "secondary" : "outline"}>{LEDGER_LABELS[ledger.verification]}</Badge>
            <p>Events checked: {ledger.events_checked}</p>
            {ledger.first_invalid_sequence !== null ? <p>First failing event: #{ledger.first_invalid_sequence}</p> : null}
            {ledger.reason ? <p>{ledger.reason}</p> : null}
            <p className="text-muted-foreground">{ledger.note}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>External ledger</CardTitle>
            <CardDescription>A separate system that could independently confirm the chain.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Badge variant="outline">{ANCHOR_LABELS[anchor.state]}</Badge>
            <p className="text-muted-foreground">{anchor.detail}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Existing data is not encrypted</CardTitle>
          <CardDescription>{existing.note}</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="list-disc space-y-1 pl-5 text-sm" aria-label="Data stored without encryption">
            {existing.unprotected_categories.map((category) => (
              <li key={category}>{category}</li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Limitations of this prototype</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="list-disc space-y-1 pl-5 text-sm" aria-label="Limitations">
            {data.limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  )
}

export function SecurityStatusCard({ profileId }: { profileId: number }) {
  const status = useSecurityStatusQuery(profileId)
  return <SecurityStatusView data={status.data} loading={status.isLoading} error={status.error} onRetry={() => void status.refetch()} />
}
