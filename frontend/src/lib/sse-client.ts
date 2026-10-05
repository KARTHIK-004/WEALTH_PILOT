/**
 * SSE client FOUNDATION for `GET /api/analysis/stream` — Phase 16 scope
 * only (section 26): a small, reusable, typed subscription helper. No
 * streaming UI is built on top of it yet; that is Phase 17/18's job
 * (the Agent Activity page).
 *
 * The event shape mirrors `backend/wealthpilot/api/sse.py`'s own
 * `NodeEvent`/`_format_event` exactly — `node`, `status`, `duration_ms`,
 * `summary`, `model_version` only. There is no OpenAPI-generated type for
 * this (SSE isn't representable in a REST response schema), so it is
 * hand-written here, same justification as `types/problem-details.ts`.
 * `summary` is always the backend's own short, already-safe sentence —
 * this client never receives, stores, or renders a prompt, a reasoning
 * trace, or a debate transcript, because the backend never sends one.
 */
import { API_BASE_URL } from "@/lib/api-client"

export interface NodeProgressEvent {
  node: string
  status: string
  duration_ms: number | null
  summary: string | null
  model_version: string | null
}

export interface AnalysisStreamHandlers {
  onProgress: (event: NodeProgressEvent) => void
  onError?: (detail: string) => void
  onOpen?: () => void
}

export function subscribeToAnalysisStream(
  profileId: number,
  handlers: AnalysisStreamHandlers,
  portfolioStrategy?: string,
): () => void {
  const params = new URLSearchParams({ profile_id: String(profileId) })
  if (portfolioStrategy) params.set("portfolio_strategy", portfolioStrategy)

  const source = new EventSource(`${API_BASE_URL}/api/analysis/stream?${params.toString()}`)

  source.addEventListener("node_progress", (event) => {
    try {
      const data = JSON.parse((event as MessageEvent<string>).data) as NodeProgressEvent
      handlers.onProgress(data)
    } catch {
      handlers.onError?.("Received a malformed progress event.")
    }
  })

  source.addEventListener("error", (event) => {
    const messageEvent = event as MessageEvent<string> | undefined
    if (messageEvent?.data) {
      try {
        const data = JSON.parse(messageEvent.data) as { detail?: string }
        handlers.onError?.(data.detail ?? "The analysis stream failed.")
        return
      } catch {
        // fall through to the generic message below
      }
    }
    handlers.onError?.("The analysis stream connection failed.")
  })

  source.addEventListener("open", () => handlers.onOpen?.())

  return () => source.close()
}
