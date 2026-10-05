import { Calculator, EyeOff, MonitorSmartphone, Sparkles } from "lucide-react"

import { SectionHeading } from "@/components/home/section-heading"

const LAYERS = [
  {
    icon: Calculator,
    title: "Backend",
    role: "Calculates",
    description:
      "Every number — risk profile, financial health, goal feasibility, portfolio weights — and the compliance decision comes from deterministic code and trained models.",
  },
  {
    icon: Sparkles,
    title: "Gemini",
    role: "Explains",
    description:
      "Rewrites the already-computed result in plain language. It never calculates a number; its output is checked against the backend's figures, with a templated fallback.",
  },
  {
    icon: MonitorSmartphone,
    title: "Frontend",
    role: "Displays",
    description: "Shows and formats what the backend returned. The browser performs no financial calculation.",
  },
] as const

/** Who does what: the backend is the only numerical authority. */
export function AiExplanationSection() {
  return (
    <section aria-labelledby="ai-heading" className="bg-muted/40 border-y">
      <div className="mx-auto w-full max-w-6xl space-y-12 px-4 py-16 md:px-6 md:py-20">
        <SectionHeading
          id="ai-heading"
          eyebrow="Explainable by design"
          title="AI that explains, never invents"
          description="Calculation, explanation and display are kept strictly apart, so every figure you see can be traced to one source."
        />
        <ul className="grid gap-4 md:grid-cols-3">
          {LAYERS.map((layer) => (
            <li key={layer.title} className="bg-card flex flex-col gap-3 rounded-xl border p-5">
              <div className="flex items-center gap-3">
                <span className="bg-secondary text-primary flex size-10 items-center justify-center rounded-lg">
                  <layer.icon className="size-5" aria-hidden="true" />
                </span>
                <div>
                  <h3 className="font-semibold">{layer.title}</h3>
                  <p className="text-muted-foreground text-xs">{layer.role}</p>
                </div>
              </div>
              <p className="text-muted-foreground text-sm">{layer.description}</p>
            </li>
          ))}
        </ul>
        <p className="text-muted-foreground mx-auto flex max-w-2xl items-start justify-center gap-2 text-center text-sm">
          <EyeOff className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          The app shows each analysis step&apos;s name, status and duration — never the model&apos;s internal
          reasoning, prompts or chain-of-thought.
        </p>
      </div>
    </section>
  )
}
