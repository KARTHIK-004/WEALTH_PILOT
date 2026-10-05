import { Check, Home, UserRound } from "lucide-react"

import { SectionHeading } from "@/components/home/section-heading"

const MODES = [
  {
    icon: UserRound,
    title: "Individual",
    description: "Your own complete analysis.",
    points: [
      "Risk profile and financial health",
      "Goal feasibility and required contributions",
      "Portfolio analysis and a compliance-checked recommendation",
      "A plain-language explanation of why",
    ],
  },
  {
    icon: Home,
    title: "Household",
    description: "Shared context for a family.",
    points: [
      "Members and their roles",
      "Household income, expenses, assets and liabilities",
      "A read-only household financial summary",
      "Shared household goals",
    ],
  },
] as const

/**
 * Individual vs household. Household data is context only: there is no
 * household risk score, recommendation or goal math, and no household
 * figure feeds an individual's analysis (ADR-033, ADR-035).
 */
export function HouseholdSection() {
  return (
    <section aria-labelledby="household-heading">
      <div className="mx-auto w-full max-w-6xl space-y-12 px-4 py-16 md:px-6 md:py-20">
        <SectionHeading
          id="household-heading"
          eyebrow="Individual + Household"
          title="Plan for yourself, see your family's picture"
          description="Your analysis stays your own. A household adds shared context alongside it."
        />
        <div className="grid gap-4 md:grid-cols-2">
          {MODES.map((mode) => (
            <article key={mode.title} className="bg-card flex flex-col gap-4 rounded-xl border p-6">
              <div className="flex items-center gap-3">
                <span className="bg-secondary text-primary flex size-10 items-center justify-center rounded-lg">
                  <mode.icon className="size-5" aria-hidden="true" />
                </span>
                <div>
                  <h3 className="font-semibold">{mode.title}</h3>
                  <p className="text-muted-foreground text-sm">{mode.description}</p>
                </div>
              </div>
              <ul className="space-y-2 text-sm">
                {mode.points.map((point) => (
                  <li key={point} className="flex items-start gap-2">
                    <Check className="text-primary mt-0.5 size-4 shrink-0" aria-hidden="true" />
                    {point}
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
        <p className="text-muted-foreground mx-auto max-w-2xl text-center text-sm">
          Household figures are context only — there is no household risk score or household recommendation,
          and they never change an individual&apos;s analysis.
        </p>
      </div>
    </section>
  )
}
