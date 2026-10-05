import { ClipboardList, Cpu, MessageSquareText, ShieldCheck } from "lucide-react"

import { SectionHeading } from "@/components/home/section-heading"

const STEPS = [
  {
    icon: ClipboardList,
    title: "Tell us about yourself",
    description:
      "Create a profile, answer the risk questionnaire, and add your income, expenses and financial goals.",
  },
  {
    icon: Cpu,
    title: "The backend analyses it",
    description:
      "Trained models assess your risk profile and behaviour; deterministic code checks financial health and simulates goal feasibility.",
  },
  {
    icon: ShieldCheck,
    title: "A compliance-checked recommendation",
    description:
      "Portfolio strategies are compared, then every recommendation must pass a binding compliance check before it can be shown.",
  },
  {
    icon: MessageSquareText,
    title: "Understand the why",
    description:
      "A plain-language explanation restates the figures the backend already computed, in a simple or detailed view.",
  },
] as const

/** Four-step overview of the analysis pipeline, in the order it runs. */
export function HowItWorksSection() {
  return (
    <section
      id="how-it-works"
      tabIndex={-1}
      aria-labelledby="how-it-works-heading"
      className="bg-muted/40 scroll-mt-16 border-y outline-none"
    >
      <div className="mx-auto w-full max-w-6xl space-y-12 px-4 py-16 md:px-6 md:py-20">
        <SectionHeading
          id="how-it-works-heading"
          eyebrow="How It Works"
          title="From your details to an explained recommendation"
          description="One analysis pipeline, run step by step. You can follow each step on the Agent Activity page."
        />
        <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, index) => (
            <li key={step.title} className="bg-card flex flex-col gap-3 rounded-xl border p-5">
              <div className="flex items-center gap-3">
                <span className="bg-secondary text-primary flex size-10 items-center justify-center rounded-lg">
                  <step.icon className="size-5" aria-hidden="true" />
                </span>
                <span className="text-muted-foreground text-sm font-medium">Step {index + 1}</span>
              </div>
              <h3 className="font-semibold">{step.title}</h3>
              <p className="text-muted-foreground text-sm">{step.description}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}
