import { cn } from "cn"
import { ArrowRight, CheckCircle2, ShieldCheck } from "lucide-react"
import { Link } from "react-router"

import { Badge } from "@/components/ui/badge"
import { buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"

/**
 * Fixed sample values for the hero preview. They are NOT computed, NOT read
 * from the API and NOT any real or demo customer's data -- every place they
 * appear is labelled "Illustrative". The allocation shares are literal
 * constants chosen to add up to 100; nothing in React derives them.
 */
const PREVIEW_ALLOCATION = [
  { label: "Equity", share: 50, className: "bg-primary" },
  { label: "Bonds", share: 30, className: "bg-primary/60" },
  { label: "Gold", share: 10, className: "bg-primary/35" },
  { label: "Cash", share: 10, className: "bg-muted-foreground/30" },
] as const

const PREVIEW_GOAL_PROGRESS = 64

const PREVIEW_PIPELINE = ["Risk", "Financial health", "Goals", "Portfolio", "Compliance", "Explanation"] as const

/**
 * Home page hero: headline, supporting copy, primary actions, and an
 * illustrative dashboard preview assembled from the app's own shadcn
 * primitives (`Card`, `Badge`, `Progress`, `Separator`). The preview is a
 * static picture of the layout -- no API call, no customer data, no
 * calculation.
 */
export function HeroSection() {
  return (
    <section id="home" tabIndex={-1} aria-labelledby="home-heading" className="scroll-mt-20 outline-none">
      <div className="mx-auto grid w-full max-w-6xl items-center gap-12 px-4 py-16 md:px-6 md:py-24 lg:grid-cols-2">
        <div className="space-y-6">
          <Badge variant="outline" className="text-muted-foreground">
            Educational decision-support prototype
          </Badge>
          <h1 id="home-heading" className="text-4xl font-semibold tracking-tight text-balance md:text-5xl">
            Understand Your Money. <span className="text-primary">Plan Your Future.</span>
          </h1>
          <p className="text-muted-foreground max-w-xl text-lg text-pretty">
            WealthPilot AI brings risk profiling, financial health, goal planning and portfolio analysis
            together in one place — then explains the result in plain language. It is a learning and
            research tool that supports your own decisions.
          </p>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Link
              to="/create-user"
              className={cn(buttonVariants({ size: "lg" }), "h-11 px-5")}
            >
              Get Started
              <ArrowRight data-icon="inline-end" aria-hidden="true" />
            </Link>
            <Link to="/login?demo=individual" className={cn(buttonVariants({ variant: "outline", size: "lg" }), "h-11 px-5")}>
              Explore Demo
            </Link>
          </div>
        </div>

        <IllustrativeDashboard />
      </div>
    </section>
  )
}

function IllustrativeDashboard() {
  return (
    <figure className="w-full min-w-0" aria-labelledby="hero-preview-caption">
      <Card className="shadow-sm">
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle>Dashboard preview</CardTitle>
            <Badge variant="secondary">Illustrative</Badge>
          </div>
          <CardDescription>Sample layout with fixed example values.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <dl className="grid grid-cols-2 gap-3">
            <div className="rounded-lg border p-3">
              <dt className="text-muted-foreground text-xs">Risk profile</dt>
              <dd className="mt-1 font-medium">Balanced</dd>
            </div>
            <div className="rounded-lg border p-3">
              <dt className="text-muted-foreground text-xs">Emergency fund</dt>
              <dd className="mt-1 font-medium">6 months</dd>
            </div>
          </dl>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium">Retirement goal</span>
              <span className="text-muted-foreground tabular-nums">{PREVIEW_GOAL_PROGRESS}% funded</span>
            </div>
            <Progress value={PREVIEW_GOAL_PROGRESS} aria-label="Illustrative retirement goal progress" />
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">Suggested allocation</p>
            <div className="flex h-2.5 w-full overflow-hidden rounded-full" aria-hidden="true">
              {PREVIEW_ALLOCATION.map((slice) => (
                <span key={slice.label} className={slice.className} style={{ width: `${slice.share}%` }} />
              ))}
            </div>
            <ul className="text-muted-foreground grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-4">
              {PREVIEW_ALLOCATION.map((slice) => (
                <li key={slice.label} className="flex items-center gap-1.5">
                  <span className={cn("size-2 shrink-0 rounded-full", slice.className)} aria-hidden="true" />
                  {slice.label} {slice.share}%
                </li>
              ))}
            </ul>
          </div>

          <Separator />

          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm">
              <ShieldCheck className="text-primary size-4" aria-hidden="true" />
              <span className="font-medium">Compliance check</span>
              <Badge variant="outline" className="ml-auto">
                Approved
              </Badge>
            </div>
            <ul className="flex flex-wrap gap-x-3 gap-y-1.5 text-xs">
              {PREVIEW_PIPELINE.map((step) => (
                <li key={step} className="text-muted-foreground flex items-center gap-1">
                  <CheckCircle2 className="text-primary size-3.5" aria-hidden="true" />
                  {step}
                </li>
              ))}
            </ul>
          </div>
        </CardContent>
      </Card>
      <figcaption id="hero-preview-caption" className="text-muted-foreground mt-3 text-center text-xs">
        Illustrative preview — example values, not real customer data or a real recommendation.
      </figcaption>
    </figure>
  )
}
