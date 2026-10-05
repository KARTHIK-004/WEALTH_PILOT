import { cn } from "cn"
import { useEffect, useRef, useState } from "react"
import { useLocation, useNavigate, useSearchParams } from "react-router"

import { Button } from "@/components/ui/button"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
  FieldSeparator,
  FieldTitle,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { FamilyDemoNotSeededError, resolveDemoCustomer, resolveFamilyDemoCustomer } from "@/lib/demo-customer"
import { DEMO_EMAIL, DEMO_PASSWORD } from "@/lib/prototype-auth"
import { useAuth } from "@/providers/auth-context"
import { useCustomer } from "@/providers/customer-context"

interface LocationState {
  from?: { pathname: string }
}

/**
 * Adapted from shadcn/ui's `login-02` block (`npx shadcn@latest add
 * login-02`, Phase 20) -- the original template's "Forgot your password?"
 * link, "Login with GitHub" social button, and "Sign up" link were removed
 * per this phase's explicit scope (no password recovery, no social login,
 * no new-user flow yet). The `Field`/`FieldGroup`/`FieldLabel`/
 * `FieldSeparator`/`FieldError` primitives are the CLI-generated ones,
 * unmodified. Everything below is prototype authentication only -- see
 * `lib/prototype-auth.ts` -- never a real credential check against a
 * backend.
 *
 * UX fix (post-Phase-25): there is only ONE supported prototype account
 * (the demo credential -- `lib/prototype-auth.ts` has no other), so a
 * successful regular Sign In and "Use Demo Account" must resolve to the
 * SAME associated customer, automatically, with no manual "enter a
 * profile id" step in between -- both paths now call the same
 * `completeLogin()`, which resolves the one canonical demo customer
 * (`lib/demo-customer.ts`, real backend APIs, never fabricated in React)
 * and sets it as the active profile before navigating. Previously only
 * "Use Demo Account" did this; a regular Sign In left the active profile
 * unresolved, which is exactly what forced the old manual profile-id
 * picker to exist. See `reports/post_login_profile_flow_report.md`.
 *
 * Family demo (ADR-036): a second demo entry point, "Use Family Demo", signs
 * in with the same demo credential but resolves the primary member of the
 * canonical "WealthPilot Demo Family" household instead
 * (`resolveFamilyDemoCustomer`, find-only) and opens the Customer Profile page
 * with the Household section expanded. Sign In and "Use Individual Demo" are
 * unchanged. Either way exactly one customer is active for the session -- the
 * choice happens here, at login, never through an in-app switcher (ADR-021).
 *
 * Public Home page: its "Individual Demo" / "Family Demo" buttons link here
 * with `?demo=individual|family`. That hint only moves focus to, and
 * highlights, the matching demo button below -- it never signs in by itself
 * and changes nothing about how either demo authenticates.
 */
export function LoginForm({ className, ...props }: React.ComponentProps<"form">) {
  const { login } = useAuth()
  const { setProfileId } = useCustomer()
  const navigate = useNavigate()
  const location = useLocation()
  const redirectTo = (location.state as LocationState | null)?.from?.pathname ?? "/dashboard"
  const [searchParams] = useSearchParams()
  const demoHint = searchParams.get("demo")
  const individualDemoRef = useRef<HTMLButtonElement>(null)
  const familyDemoRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (demoHint === "individual") individualDemoRef.current?.focus()
    if (demoHint === "family") familyDemoRef.current?.focus()
  }, [demoHint])

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  // Which action is currently resolving the account's customer -- lets
  // each button show its OWN pending label instead of both changing
  // together, while a single boolean (`pendingAction !== null`) still
  // disables both during either action.
  const [pendingAction, setPendingAction] = useState<"signin" | "demo" | "family" | null>(null)

  /** Resolves and activates the account's associated customer, then
   * navigates -- the one deterministic mapping every successful
   * authentication (regular Sign In or Use Demo Account) goes through, so
   * the user always lands directly on Dashboard, never a profile picker. */
  const completeLogin = async (action: "signin" | "demo" | "family") => {
    setPendingAction(action)
    try {
      if (action === "family") {
        const customerId = await resolveFamilyDemoCustomer()
        setProfileId(customerId)
        navigate("/profile?household=open", { replace: true })
        return
      }
      const customerId = await resolveDemoCustomer()
      setProfileId(customerId)
      navigate(redirectTo, { replace: true })
    } catch (caught) {
      setError(
        caught instanceof FamilyDemoNotSeededError
          ? "The family demo has not been set up in this environment yet (seed_demo_data.py setup-family)."
          : "Could not set up your account. Please try again.",
      )
    } finally {
      setPendingAction(null)
    }
  }

  const attemptLogin = async (
    candidateEmail: string,
    candidatePassword: string,
    action: "signin" | "demo" | "family",
  ) => {
    setError(null)
    const ok = login(candidateEmail, candidatePassword)
    if (!ok) {
      // Deliberately generic -- never reveals which field was wrong.
      setError("Invalid email or password.")
      return
    }
    await completeLogin(action)
  }

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    void attemptLogin(email, password, "signin")
  }

  const handleDemoLogin = async () => {
    setEmail(DEMO_EMAIL)
    setPassword(DEMO_PASSWORD)
    await attemptLogin(DEMO_EMAIL, DEMO_PASSWORD, "demo")
  }

  const handleFamilyDemoLogin = async () => {
    setEmail(DEMO_EMAIL)
    setPassword(DEMO_PASSWORD)
    await attemptLogin(DEMO_EMAIL, DEMO_PASSWORD, "family")
  }

  return (
    <form className={cn("flex flex-col gap-6", className)} onSubmit={handleSubmit} noValidate {...props}>
      <FieldGroup>
        <div className="flex flex-col items-center gap-1 text-center">
          <h1 className="text-2xl font-bold">Sign in</h1>
          <p className="text-muted-foreground text-sm text-balance">
            Prototype authentication — for demonstration only.
          </p>
        </div>

        {error ? <FieldError>{error}</FieldError> : null}

        <Field>
          <FieldLabel htmlFor="login-email">Email</FieldLabel>
          <Input
            id="login-email"
            type="email"
            autoComplete="username"
            placeholder="m@example.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            aria-invalid={error ? true : undefined}
            required
          />
        </Field>
        <Field>
          <FieldLabel htmlFor="login-password">Password</FieldLabel>
          <Input
            id="login-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            aria-invalid={error ? true : undefined}
            required
          />
        </Field>
        <Field>
          <Button type="submit" disabled={pendingAction !== null}>
            {pendingAction === "signin" ? "Signing in…" : "Sign In"}
          </Button>
        </Field>

        <FieldSeparator>or</FieldSeparator>

        <Field className="bg-muted/50 gap-3 rounded-lg border p-3">
          <FieldTitle>Demo Accounts</FieldTitle>
          <FieldDescription>
            Email: <span className="font-mono">{DEMO_EMAIL}</span>
            <br />
            Password: <span className="font-mono">{DEMO_PASSWORD}</span>
          </FieldDescription>
          <div className={cn("flex flex-col gap-1.5 rounded-md", demoHint === "individual" && "ring-primary ring-2 ring-offset-4 ring-offset-muted")}>
            <Button
              ref={individualDemoRef}
              type="button"
              variant="outline"
              onClick={handleDemoLogin}
              disabled={pendingAction !== null}
            >
              {pendingAction === "demo" ? "Setting up demo…" : "Use Individual Demo"}
            </Button>
            <FieldDescription>
              One customer&apos;s own analysis: risk, financial health, goals, portfolio and recommendation.
            </FieldDescription>
          </div>
          <div className={cn("flex flex-col gap-1.5 rounded-md", demoHint === "family" && "ring-primary ring-2 ring-offset-4 ring-offset-muted")}>
            <Button
              ref={familyDemoRef}
              type="button"
              variant="outline"
              onClick={handleFamilyDemoLogin}
              disabled={pendingAction !== null}
            >
              {pendingAction === "family" ? "Opening family demo…" : "Use Family Demo"}
            </Button>
            <FieldDescription>
              A household&apos;s members, income, expenses, assets, liabilities, summary and goals. Household
              figures are context only — there is no household risk score or recommendation.
            </FieldDescription>
          </div>
        </Field>
      </FieldGroup>
    </form>
  )
}
