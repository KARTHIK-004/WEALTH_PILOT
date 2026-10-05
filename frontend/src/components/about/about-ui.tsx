import { ArrowDown, ArrowRight, Lightbulb, type LucideIcon } from "lucide-react"
import { Fragment, type ReactNode } from "react"

import { cn } from "cn"

/**
 * Presentation building blocks for the About This Project page. Layout only:
 * every fact shown through them is written in `pages/about-page.tsx`, sourced
 * from the project's own reports and `models/metrics.json` (cited there).
 */

export function AboutSection({
  id,
  number,
  title,
  intro,
  children,
  className,
}: {
  id: string
  number: number
  title: string
  intro?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section id={id} tabIndex={-1} aria-labelledby={`${id}-heading`} className={cn("scroll-mt-20 space-y-5 outline-none", className)}>
      <div className="space-y-2">
        <p className="text-primary text-sm font-medium">{String(number).padStart(2, "0")}</p>
        <h2 id={`${id}-heading`} className="text-2xl font-semibold tracking-tight text-balance">
          {title}
        </h2>
        {intro ? <div className="text-muted-foreground max-w-3xl text-pretty">{intro}</div> : null}
      </div>
      {children}
    </section>
  )
}

export function InfoCard({
  icon: Icon,
  title,
  children,
  className,
}: {
  icon?: LucideIcon
  title: string
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn("bg-card space-y-2 rounded-xl border p-5", className)}>
      <h3 className="flex items-center gap-2 font-semibold">
        {Icon ? (
          <span className="bg-secondary text-primary flex size-8 shrink-0 items-center justify-center rounded-lg">
            <Icon className="size-4" aria-hidden="true" />
          </span>
        ) : null}
        {title}
      </h3>
      <div className="text-muted-foreground space-y-2 text-sm">{children}</div>
    </div>
  )
}

/** A highlighted note (research-integrity points, Gemini's role). */
export function Callout({ title, icon: Icon, children }: { title: string; icon: LucideIcon; children: ReactNode }) {
  return (
    <div className="border-primary/30 bg-card space-y-2 rounded-xl border p-5">
      <h3 className="flex items-center gap-2 font-semibold">
        <Icon className="text-primary size-5 shrink-0" aria-hidden="true" />
        {title}
      </h3>
      <div className="space-y-2 text-sm">{children}</div>
    </div>
  )
}

/**
 * A labelled sequence of steps drawn as cards with arrows: vertical on narrow
 * screens, a wrapping row from `lg` up. Rendered as an ordered list so the
 * order is announced, with the arrows hidden from assistive technology.
 *
 * A step with an `icon` and/or `text` renders as a larger, left-aligned card
 * (icon badge + title + one-line plain-language explanation) instead of the
 * compact centered chip the simpler `title`/`detail` steps use elsewhere on
 * this page — one component, two densities, so a richer process diagram
 * (e.g. "How WealthPilot Works") never needs a visually separate system.
 */
export function FlowSteps({
  steps,
  label,
  vertical = false,
}: {
  /** `tone: "destructive"` marks a rejection/stop step (theme `destructive` token). */
  steps: { title: string; detail?: string; tone?: "destructive"; icon?: LucideIcon; text?: string }[]
  label: string
  /** Always stack top-to-bottom (layered diagrams such as the architecture). */
  vertical?: boolean
}) {
  return (
    <ol
      aria-label={label}
      className={cn(
        "flex flex-col items-stretch gap-2",
        !vertical && "lg:flex-row lg:flex-wrap lg:content-start lg:items-stretch",
      )}
    >
      {steps.map((step, index) => {
        const Icon = step.icon
        const rich = Boolean(Icon || step.text)
        return (
          <li key={step.title} className={cn("flex flex-col items-center gap-2", !vertical && "lg:flex-row lg:items-center")}>
            <div
              className={cn(
                "bg-card w-full rounded-lg border px-4 py-3",
                rich ? "text-left" : "text-center",
                step.tone === "destructive" && "border-destructive/50 text-destructive",
                !vertical && (rich ? "lg:w-56" : "lg:w-auto lg:min-w-36"),
              )}
            >
              {rich ? (
                <div className="flex items-start gap-2.5">
                  {Icon ? (
                    <span className="bg-secondary text-primary flex size-8 shrink-0 items-center justify-center rounded-lg">
                      <Icon className="size-4" aria-hidden="true" />
                    </span>
                  ) : null}
                  <div className="space-y-0.5">
                    <p className="text-sm font-medium">{step.title}</p>
                    {step.text ? <p className="text-muted-foreground text-xs">{step.text}</p> : null}
                  </div>
                </div>
              ) : (
                <>
                  <p className="text-sm font-medium">{step.title}</p>
                  {step.detail ? <p className="text-muted-foreground text-xs">{step.detail}</p> : null}
                </>
              )}
            </div>
            {index < steps.length - 1 ? (
              <>
                <ArrowDown className={cn("text-muted-foreground size-4 shrink-0", !vertical && "lg:hidden")} aria-hidden="true" />
                {!vertical ? <ArrowRight className="text-muted-foreground hidden size-4 shrink-0 lg:block" aria-hidden="true" /> : null}
              </>
            ) : null}
          </li>
        )
      })}
    </ol>
  )
}

/**
 * A one-sentence summary for a presenter, right under the section it
 * summarises -- the "what to say" version of the section above. Purely a
 * presentation aid; it restates a fact already given in full nearby, never a
 * new claim.
 */
export function Takeaway({ children }: { children: ReactNode }) {
  return (
    <p className="border-primary/30 bg-secondary text-secondary-foreground flex items-start gap-2 rounded-lg border px-4 py-3 text-sm">
      <Lightbulb className="text-primary mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <span>
        <span className="font-semibold">Presentation takeaway: </span>
        {children}
      </span>
    </p>
  )
}

/**
 * "A + B + C = Result" as a row of pills (the Problem Statement's "these
 * combine into one analysis" visual). The whole row carries one `aria-label`
 * stating the equation in words, rather than relying on how different screen
 * readers announce "+"/"=" individually.
 */
export function EquationRow({ parts, result }: { parts: string[]; result: string }) {
  return (
    <div
      role="img"
      aria-label={`${parts.join(" plus ")} equals ${result}`}
      className="flex flex-wrap items-center justify-center gap-2 text-sm"
    >
      <div aria-hidden="true" className="contents">
        {parts.map((part, index) => (
          <Fragment key={part}>
            <span className="bg-card rounded-lg border px-3 py-2 font-medium">{part}</span>
            {index < parts.length - 1 ? <span className="text-muted-foreground">+</span> : null}
          </Fragment>
        ))}
        <span className="text-muted-foreground">=</span>
        <span className="bg-primary text-primary-foreground rounded-lg px-3 py-2 font-semibold">{result}</span>
      </div>
    </div>
  )
}

/** A responsive table wrapper: scrolls sideways inside itself on narrow screens. */
export function DataTable({
  caption,
  head,
  rows,
}: {
  caption: string
  head: string[]
  rows: ReactNode[][]
}) {
  return (
    <div className="bg-card overflow-x-auto rounded-xl border">
      <table className="w-full min-w-[34rem] text-sm">
        <caption className="text-muted-foreground px-4 pt-3 text-left text-xs">{caption}</caption>
        <thead>
          <tr className="border-b">
            {head.map((cell) => (
              <th key={cell} scope="col" className="px-4 py-2 text-left font-medium">
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b last:border-0">
              {row.map((cell, j) =>
                j === 0 ? (
                  <th key={j} scope="row" className="px-4 py-2 text-left align-top font-medium">
                    {cell}
                  </th>
                ) : (
                  <td key={j} className="text-muted-foreground px-4 py-2 align-top">
                    {cell}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
