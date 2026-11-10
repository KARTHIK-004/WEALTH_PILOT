import { keepPreviousData, useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api-client"

/** `POST /api/demo/financial-behaviour` -- FICTIONAL demonstration months plus the rules-baseline reading of the optional text. The text goes in the request body (never a URL) and, like the
 * real insight hook, the cache entry whose key contains it is dropped as soon as nothing observes it (`gcTime: 0`). No customer id is involved and nothing is stored by the server. A failed
 * request is an error, never a substitute: demo data is shown only when the backend itself returned it. */
export function useDemoFinancialBehaviourQuery(text: string | null) {
  return useQuery({
    queryKey: ["demo-financial-behaviour", text],
    queryFn: () => api.createDemoFinancialBehaviour(text),
    gcTime: 0,
    placeholderData: keepPreviousData,       // the months stay on screen while a new sentence is analysed (the view says "Updating")
    staleTime: 0,
    retry: false,
    refetchOnWindowFocus: false,
  })
}

/** `POST /api/demo/family-financial-behaviour` -- the same rules as above for the FICTIONAL family: the text goes in the body, the cache entry holding it is dropped when unobserved, no retry, and a
 * failure is an error, never a substitute. */
export function useDemoFamilyQuery(text: string | null) {
  return useQuery({
    queryKey: ["demo-family-financial-behaviour", text],
    queryFn: () => api.createDemoFamilyFinancialBehaviour(text),
    gcTime: 0,
    placeholderData: keepPreviousData,
    staleTime: 0,
    retry: false,
    refetchOnWindowFocus: false,
  })
}
