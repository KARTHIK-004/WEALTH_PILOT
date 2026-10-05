import { cn } from "cn"
import { Check } from "lucide-react"

const STEPS = [
  { key: "profile", label: "Create Profile" },
  { key: "questionnaire", label: "Questionnaire" },
  { key: "goals", label: "Goals" },
  { key: "dashboard", label: "Dashboard" },
] as const

type StepKey = (typeof STEPS)[number]["key"]

/**
 * A small, static step indicator (section 7: "Do not create a large
 * wizard framework... a simple step indicator is acceptable") shared by
 * the four onboarding-adjacent pages (`create-user-page.tsx`,
 * `onboarding-questionnaire-page.tsx`, `onboarding-goals-page.tsx`, and
 * implicitly the Dashboard itself). Purely presentational -- no routing
 * logic, no persisted "current step" state anywhere.
 */
export function OnboardingSteps({ current }: { current: StepKey }) {
  const currentIndex = STEPS.findIndex((step) => step.key === current)

  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm" aria-label="Onboarding progress">
      {STEPS.map((step, index) => {
        const isDone = index < currentIndex
        const isCurrent = index === currentIndex
        return (
          <li key={step.key} className="flex items-center gap-2">
            {index > 0 ? <span className="text-muted-foreground" aria-hidden="true">→</span> : null}
            <span
              className={cn(
                "flex items-center gap-1.5 rounded-full px-2.5 py-1",
                isCurrent && "bg-primary text-primary-foreground font-medium",
                isDone && "text-muted-foreground",
                !isCurrent && !isDone && "text-muted-foreground",
              )}
              aria-current={isCurrent ? "step" : undefined}
            >
              {isDone ? <Check className="size-3.5" aria-hidden="true" /> : null}
              {index + 1}. {step.label}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
