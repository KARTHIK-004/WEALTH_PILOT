import { cn } from "cn"
import { Home, UserRound } from "lucide-react"
import { Link } from "react-router"

import { buttonVariants } from "@/components/ui/button"

/**
 * Demo entry points. Both buttons open the EXISTING Login page with a
 * `?demo=` hint that only moves focus to the matching demo button there --
 * signing in still happens through the Login page's own "Use Individual
 * Demo" / "Use Family Demo" actions. No new account, credential or seed.
 */
export function DemoCtaSection() {
  return (
    <section aria-labelledby="demo-heading" className="px-4 pb-16 md:px-6 md:pb-20">
      <div className="bg-secondary text-secondary-foreground mx-auto flex w-full max-w-6xl flex-col items-center gap-6 rounded-2xl border px-6 py-12 text-center md:py-16">
        <div className="max-w-xl space-y-3">
          <h2 id="demo-heading" className="text-3xl font-semibold tracking-tight text-balance">
            See WealthPilot AI in action
          </h2>
          <p className="text-secondary-foreground text-pretty">
            Explore a complete individual analysis, or a family household, using synthetic demo data.
          </p>
        </div>
        <div className="flex w-full flex-col justify-center gap-3 sm:w-auto sm:flex-row">
          <Link
            to="/login?demo=individual"
            className={cn(buttonVariants({ size: "lg" }), "h-11 px-5")}
          >
            <UserRound data-icon="inline-start" aria-hidden="true" />
            Individual Demo
          </Link>
          <Link
            to="/login?demo=family"
            className={cn(
              buttonVariants({ variant: "outline", size: "lg" }),
              "h-11 px-5",
            )}
          >
            <Home data-icon="inline-start" aria-hidden="true" />
            Family Demo
          </Link>
        </div>
      </div>
    </section>
  )
}
