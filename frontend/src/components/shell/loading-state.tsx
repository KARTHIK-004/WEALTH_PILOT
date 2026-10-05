import { Skeleton } from "@/components/ui/skeleton"

/**
 * Reusable "data is loading" state (section 18). Renders structural
 * skeleton placeholders only — never a fake number, percentage, or
 * portfolio weight standing in for real data while it loads.
 */
export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div className="space-y-3" role="status" aria-live="polite">
      <span className="sr-only">{label}…</span>
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-4 w-2/3" />
    </div>
  )
}

export function PageLoadingState() {
  return (
    <div className="space-y-6" role="status" aria-live="polite">
      <span className="sr-only">Loading page…</span>
      <Skeleton className="h-8 w-48" />
      <div className="grid gap-4 sm:grid-cols-2">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
      <Skeleton className="h-64 w-full" />
    </div>
  )
}
