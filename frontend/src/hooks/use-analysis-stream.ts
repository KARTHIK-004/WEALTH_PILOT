import { useCallback, useEffect, useRef, useState } from "react"

import { subscribeToAnalysisStream, type NodeProgressEvent } from "@/lib/sse-client"

export type StreamConnectionState = "idle" | "connecting" | "streaming" | "completed" | "error"

/**
 * Owns the Agent Activity page's SSE lifecycle -- the one place this
 * component tree parses/accumulates stream events (section 24: "do not
 * duplicate SSE parsing across components"). Deliberately does NOT
 * auto-connect on mount: the stream triggers a real backend analysis run
 * (section 27's "do not accidentally create duplicate analysis
 * executions" -- React 18/19 StrictMode double-invokes effects in
 * development, which would silently start two real pipeline runs, one
 * of them abandoned, if this connected automatically). `start()` is
 * called explicitly from a button instead, and `start()` itself closes
 * any previous connection first, so at most one EventSource is ever open.
 */
export function useAnalysisStream() {
  const [events, setEvents] = useState<NodeProgressEvent[]>([])
  const [state, setState] = useState<StreamConnectionState>("idle")
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const unsubscribeRef = useRef<(() => void) | null>(null)

  const stop = useCallback(() => {
    unsubscribeRef.current?.()
    unsubscribeRef.current = null
  }, [])

  const start = useCallback(
    (profileId: number, portfolioStrategy?: string) => {
      stop()
      setEvents([])
      setErrorMessage(null)
      setState("connecting")

      unsubscribeRef.current = subscribeToAnalysisStream(
        profileId,
        {
          onOpen: () => setState("streaming"),
          onProgress: (event) => {
            setState("streaming")
            setEvents((prev) => [...prev, event])
            if (event.node === "analysis_completed") {
              setState("completed")
              stop()
            }
          },
          onError: (detail) => {
            setState("error")
            setErrorMessage(detail)
            stop()
          },
        },
        portfolioStrategy,
      )
    },
    [stop],
  )

  useEffect(() => stop, [stop])

  return { events, state, errorMessage, start, stop }
}
