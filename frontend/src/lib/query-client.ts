import { QueryClient } from "@tanstack/react-query"

import { ApiClientError } from "@/lib/api-client"

/**
 * Sensible, non-aggressive defaults (section 10: "do not invent
 * aggressive polling"). A validation/not-found error (4xx) is a
 * deterministic outcome of the request itself — retrying it changes
 * nothing, so those never retry; a transient/server-side failure gets a
 * small bounded number of retries.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        if (error instanceof ApiClientError && error.problem.status < 500) {
          return false
        }
        return failureCount < 2
      },
    },
    mutations: {
      retry: false,
    },
  },
})
