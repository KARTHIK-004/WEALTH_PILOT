import { GraduationCap, PieChart } from "lucide-react"
import { Link } from "react-router"

import { LoginForm } from "@/components/login-form"

/**
 * The application's public entry point (Phase 20). Deliberately rendered
 * OUTSIDE `AppShell` -- registered as a sibling of the protected route
 * tree in `App.tsx`, not nested inside it -- so there is no sidebar, no
 * customer-navigation menu, and no header on this route at all.
 *
 * Layout follows shadcn/ui's own `login-02` BLOCK page (as opposed to just
 * its `login-form.tsx` component, which is all `npx shadcn add login-02`
 * pulls into a Vite project -- the block's `page.tsx` targets a Next.js
 * `app/login/page.tsx` path that doesn't exist here, so the CLI silently
 * skipped it; its two-column structure -- `grid lg:grid-cols-2`, a brand
 * mark pinned top-left, the form centered in the remaining space, a
 * decorative panel hidden below `lg` -- is reproduced here by hand). The
 * reference's "Acme Inc." placeholder and stock cover photo are replaced
 * with WealthPilot AI's own brand mark and an on-brand decorative panel
 * (no photo asset exists for this project, so a CSS-only panel is used
 * instead of an `<img>`) -- still no forgot-password link, no social
 * login, and the Demo Account panel remains directly visible on the form
 * side, exactly as before.
 *
 * Phase 21 adds one secondary action below the form: "Create your profile"
 * to `/create-user`, a public route reachable without logging in first
 * (see `pages/create-user-page.tsx`'s own docstring for why).
 */
export function LoginPage() {
  return (
    <main id="main-content" className="grid min-h-svh lg:grid-cols-2">
      <div className="flex flex-col gap-4 p-6 md:p-10">
        <div className="flex justify-center gap-2 md:justify-start">
          <span className="flex items-center gap-2 font-medium">
            <div className="bg-primary text-primary-foreground flex size-6 items-center justify-center rounded-md">
              <GraduationCap className="size-4" />
            </div>
            WealthPilot AI
          </span>
        </div>
        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-xs space-y-6">
            <LoginForm />
            <p className="text-muted-foreground text-center text-sm">
              New customer?{" "}
              <Link to="/create-user" className="text-foreground underline underline-offset-4">
                Create your profile
              </Link>
            </p>
          </div>
        </div>
      </div>
      <div className="bg-muted relative hidden lg:block">
        <div className="from-primary/15 via-primary/5 absolute inset-0 bg-linear-to-br to-transparent" />
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 p-10 text-center">
          <div className="bg-primary/10 text-primary flex size-20 items-center justify-center rounded-2xl">
            <PieChart className="size-10" />
          </div>
          <div className="max-w-sm space-y-2">
            <p className="text-lg font-semibold">Agentic AI-based decision-support prototype</p>
            <p className="text-muted-foreground text-sm text-balance">
              Risk assessment, portfolio optimization, and compliance-checked recommendations —
              orchestrated across specialized agents, explained in plain language.
            </p>
          </div>
        </div>
      </div>
    </main>
  )
}
