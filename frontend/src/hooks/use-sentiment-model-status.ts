import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api-client"

/** `GET /api/sentiment-model/status` -- whether a trained sentiment model is in use. It is `disabled` by default and the page only uses it to say so: a failed request simply leaves the
 * "model-based feature is disabled" sentence out (nothing is claimed that the backend did not say). Customer-independent and read-only; it carries no text. */
export function useSentimentModelStatusQuery() {
  return useQuery({
    queryKey: ["sentiment-model-status"],
    queryFn: () => api.getSentimentModelStatus(),
    retry: false,
    refetchOnWindowFocus: false,
  })
}
