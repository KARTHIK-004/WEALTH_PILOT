import {
  Activity,
  Gauge,
  HeartPulse,
  MessageSquareText,
  PieChart,
  ShieldCheck,
  SlidersHorizontal,
  Target,
} from "lucide-react"

import { SectionHeading } from "@/components/home/section-heading"

/**
 * Only capabilities the app actually has -- each maps to an existing page.
 * Expense segmentation is deliberately absent: it is structurally
 * unavailable for the customers this app analyses (ADR-010).
 */
const FEATURES = [
  {
    icon: Gauge,
    title: "Risk Assessment",
    description: "A machine-learning risk profile built from your questionnaire answers and investment behaviour.",
  },
  {
    icon: HeartPulse,
    title: "Financial Health",
    description: "Emergency-fund status, savings and debt indicators, and detection of changes in your behaviour.",
  },
  {
    icon: Target,
    title: "Goal Planning",
    description: "Monte Carlo simulation of how likely each goal is to be met, and the contribution it needs.",
  },
  {
    icon: PieChart,
    title: "Portfolio Analysis",
    description: "Mean-variance, hierarchical risk parity and equal-weight portfolios, matched to your risk profile.",
  },
  {
    icon: ShieldCheck,
    title: "Compliance-Checked Recommendation",
    description: "A binding compliance gate that blocks any recommendation which breaks a rule, with no override.",
  },
  {
    icon: MessageSquareText,
    title: "Why This Recommendation",
    description: "A plain-language explanation of the result, including market context, in a simple or detailed view.",
  },
  {
    icon: Activity,
    title: "Agent Activity",
    description: "Step-by-step progress of every stage of the analysis, with each step's status and duration.",
  },
  {
    icon: SlidersHorizontal,
    title: "Scenario Simulator",
    description: "Compare portfolio strategies side by side for the same profile before you decide.",
  },
] as const

export function FeaturesSection() {
  return (
    <section id="features" tabIndex={-1} aria-labelledby="features-heading" className="scroll-mt-16 outline-none">
      <div className="mx-auto w-full max-w-6xl space-y-12 px-4 py-16 md:px-6 md:py-20">
        <SectionHeading
          id="features-heading"
          eyebrow="Features"
          title="Everything in one analysis"
          description="Each feature below is a page in the app, backed by the same analysis run."
        />
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((feature) => (
            <li key={feature.title} className="bg-card flex flex-col gap-3 rounded-xl border p-5">
              <feature.icon className="text-primary size-5" aria-hidden="true" />
              <h3 className="font-semibold">{feature.title}</h3>
              <p className="text-muted-foreground text-sm">{feature.description}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
