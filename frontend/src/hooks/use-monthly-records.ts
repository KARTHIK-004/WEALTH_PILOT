import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api-client"
import type { components } from "@/types/api"

type MonthlyRecordUpdate = components["schemas"]["MonthlyRecordUpdate"]

/** `GET /api/profiles/{id}/monthly-financial-records` — the customer's own
 * optional monthly records, newest first. An empty list is a normal state. */
export function useMonthlyRecordsQuery(profileId: number | null) {
  return useQuery({
    queryKey: ["monthly-records", profileId],
    queryFn: () => api.listMonthlyRecords(profileId as number),
    enabled: profileId !== null,
  })
}

/** What a changed month makes stale: the month list, the behaviour features, and the behaviour / spending findings shown on Financial Health and Financial Behaviour & Sentiment
 * (`personalized-insight`, keyed by profile and text). The analysis does not read these records, so it is not refreshed. */
function invalidateMonthlyViews(queryClient: ReturnType<typeof useQueryClient>, profileId: number | null) {
  queryClient.invalidateQueries({ queryKey: ["monthly-records", profileId] })
  queryClient.invalidateQueries({ queryKey: ["behaviour-features", profileId] })
  queryClient.invalidateQueries({ queryKey: ["personalized-insight", profileId] })
}

/** `PUT .../monthly-financial-records/{YYYY-MM}` — creates or corrects one month. */
export function useSaveMonthlyRecord(profileId: number | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ period, body }: { period: string; body: MonthlyRecordUpdate }) =>
      api.saveMonthlyRecord(profileId as number, period, body),
    onSuccess: () => invalidateMonthlyViews(queryClient, profileId),
  })
}

export function useDeleteMonthlyRecord(profileId: number | null) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (period: string) => api.deleteMonthlyRecord(profileId as number, period),
    onSuccess: () => invalidateMonthlyViews(queryClient, profileId),
  })
}
