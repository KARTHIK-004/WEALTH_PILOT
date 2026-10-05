import { GraduationCap } from "lucide-react"

/** The WealthPilot AI wordmark, matching the Login page and sidebar header. */
export function BrandMark() {
  return (
    <span className="flex items-center gap-2 font-semibold">
      <span className="bg-primary text-primary-foreground flex size-7 items-center justify-center rounded-md">
        <GraduationCap className="size-4" aria-hidden="true" />
      </span>
      WealthPilot AI
    </span>
  )
}
