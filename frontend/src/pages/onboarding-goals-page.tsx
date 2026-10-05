import { AlertTriangle, CheckCircle2, GraduationCap, Info } from "lucide-react"
import { useState } from "react"
import { Link, useNavigate } from "react-router"

import { ErrorState } from "@/components/shell/error-state"
import { LoadingState } from "@/components/shell/loading-state"
import { OnboardingNoProfile } from "@/components/shell/onboarding-no-profile"
import { OnboardingSteps } from "@/components/shell/onboarding-steps"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { useCreateGoal } from "@/hooks/use-create-goal"
import { useProfileQuery } from "@/hooks/use-profile"
import { formatCurrency, formatDate } from "@/lib/format"
import { useCustomer } from "@/providers/customer-context"

/**
 * `/onboarding/goals` -- Phase 22 built this page as a local-only planning
 * list because no backend write path existed for a goal on an
 * already-created profile; Phase 23 adds the real
 * `POST /api/profiles/{id}/goals` endpoint that closes that gap, so this
 * page now submits each goal for real and shows the profile's genuinely
 * persisted goals (via the existing, unmodified `useProfileQuery` ->
 * `GET /api/profiles/{id}`, the same read `pages/profile-page.tsx` already
 * uses -- no new goals-retrieval endpoint or hook was needed, since this
 * one already returns a profile's goals).
 *
 * Each "Add goal" click is its own independent `POST` — never a batch —
 * so one goal's success and another's failure are always shown separately
 * and truthfully; there is no "All goals saved" message anywhere in this
 * file, because there is no batch operation that could make that claim
 * true or false in the first place. A failed attempt shows a real RFC 7807
 * error and does not add anything to the saved list; the form's entered
 * values are preserved so the user can retry.
 *
 * Goals cannot be removed once saved (Phase 23 deliberately implements
 * CREATE + RETRIEVE only, not DELETE — "avoid unnecessary CRUD
 * expansion"), so no remove control exists here for a persisted goal.
 *
 * Still distinct from two other pages that also mention "goals":
 * `pages/goals-page.tsx` (`/goals`) displays `AnalysisResult.goals[]` --
 * Phase 7's Monte Carlo/feasibility OUTPUT for an already-run analysis --
 * and this page never computes or displays any of that. No goal math
 * (required contribution, future value, inflation, Monte Carlo,
 * feasibility) is computed anywhere in this file.
 */
export function OnboardingGoalsPage() {
  const navigate = useNavigate()
  const { profileId } = useCustomer()
  const profileQuery = useProfileQuery(profileId)
  const createGoalMutation = useCreateGoal(profileId)

  const [goalType, setGoalType] = useState("")
  const [targetAmount, setTargetAmount] = useState("")
  const [targetDate, setTargetDate] = useState("")
  const [currentSavings, setCurrentSavings] = useState("")
  const [priority, setPriority] = useState("1")
  const [formError, setFormError] = useState<string | null>(null)

  const handleAddGoal = (event: React.FormEvent) => {
    event.preventDefault()
    setFormError(null)
    createGoalMutation.reset()

    const trimmedType = goalType.trim()
    const parsedAmount = Number(targetAmount)
    const parsedSavings = currentSavings.trim() === "" ? 0 : Number(currentSavings)
    const parsedPriority = priority.trim() === "" ? 1 : Number(priority)

    if (trimmedType.length === 0) {
      setFormError("Goal name is required.")
      return
    }
    if (!Number.isFinite(parsedAmount) || parsedAmount <= 0) {
      setFormError("Target amount must be greater than 0.")
      return
    }
    if (!targetDate) {
      setFormError("Target date is required.")
      return
    }
    if (!Number.isFinite(parsedSavings) || parsedSavings < 0) {
      setFormError("Current savings cannot be negative.")
      return
    }
    if (!Number.isInteger(parsedPriority) || parsedPriority < 1) {
      setFormError("Priority must be a whole number of 1 or more.")
      return
    }

    createGoalMutation.mutate(
      {
        goal_type: trimmedType,
        target_amount: parsedAmount,
        target_date: targetDate,
        current_savings: parsedSavings,
        priority: parsedPriority,
      },
      {
        onSuccess: () => {
          profileQuery.refetch()
          setGoalType("")
          setTargetAmount("")
          setTargetDate("")
          setCurrentSavings("")
          setPriority("1")
        },
      },
    )
  }

  const savedGoals = profileQuery.data?.goals ?? []

  return (
    <div className="bg-background min-h-svh p-6 md:p-10">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
        <div className="flex items-center gap-2">
          <div className="bg-primary text-primary-foreground flex size-6 items-center justify-center rounded-md">
            <GraduationCap className="size-4" />
          </div>
          <span className="font-medium">WealthPilot AI</span>
        </div>

        <OnboardingSteps current="goals" />

        {profileId === null ? (
          <OnboardingNoProfile />
        ) : (
          <>
            <div className="space-y-1">
              <h1 className="text-2xl font-bold">Your Financial Goals</h1>
              <p className="text-muted-foreground text-sm">
                Add the goals you want WealthPilot to consider in your financial plan.
              </p>
            </div>

            <Alert>
              <Info />
              <AlertTitle>Each goal you add is saved to your profile</AlertTitle>
              <AlertDescription>
                Clicking "Add goal" saves it immediately. Goals cannot be edited or removed
                from this page once saved.
              </AlertDescription>
            </Alert>

            <Card>
              <CardHeader>
                <CardTitle>Add a goal</CardTitle>
                <CardDescription>Fields match WealthPilot's financial-goal record exactly.</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleAddGoal} noValidate className="flex flex-col gap-4">
                  {formError ? (
                    <Alert variant="destructive">
                      <AlertDescription>{formError}</AlertDescription>
                    </Alert>
                  ) : null}
                  {createGoalMutation.isError ? (
                    <ErrorState error={createGoalMutation.error} onRetry={() => createGoalMutation.reset()} />
                  ) : null}
                  {createGoalMutation.isSuccess ? (
                    <Alert>
                      <CheckCircle2 />
                      <AlertTitle>Goal saved</AlertTitle>
                      <AlertDescription>
                        "{createGoalMutation.data.goal_type}" was saved to your profile.
                      </AlertDescription>
                    </Alert>
                  ) : null}
                  <FieldGroup>
                    <Field>
                      <FieldLabel htmlFor="goal-type">Goal name</FieldLabel>
                      <Input
                        id="goal-type"
                        value={goalType}
                        onChange={(event) => setGoalType(event.target.value)}
                        maxLength={100}
                        placeholder="e.g. Retirement, House Purchase, Education"
                      />
                    </Field>
                    <Field className="@md/field-group:flex-row @md/field-group:*:flex-1" orientation="responsive">
                      <Field>
                        <FieldLabel htmlFor="goal-target-amount">Target amount</FieldLabel>
                        <Input
                          id="goal-target-amount"
                          type="number"
                          inputMode="decimal"
                          min={0.01}
                          step="0.01"
                          value={targetAmount}
                          onChange={(event) => setTargetAmount(event.target.value)}
                        />
                      </Field>
                      <Field>
                        <FieldLabel htmlFor="goal-target-date">Target date</FieldLabel>
                        <Input
                          id="goal-target-date"
                          type="date"
                          value={targetDate}
                          onChange={(event) => setTargetDate(event.target.value)}
                        />
                      </Field>
                    </Field>
                    <Field className="@md/field-group:flex-row @md/field-group:*:flex-1" orientation="responsive">
                      <Field>
                        <FieldLabel htmlFor="goal-current-savings">Current savings</FieldLabel>
                        <Input
                          id="goal-current-savings"
                          type="number"
                          inputMode="decimal"
                          min={0}
                          step="0.01"
                          value={currentSavings}
                          onChange={(event) => setCurrentSavings(event.target.value)}
                        />
                        <FieldDescription>Optional — defaults to 0.</FieldDescription>
                      </Field>
                      <Field>
                        <FieldLabel htmlFor="goal-priority">Priority</FieldLabel>
                        <Input
                          id="goal-priority"
                          type="number"
                          inputMode="numeric"
                          min={1}
                          step={1}
                          value={priority}
                          onChange={(event) => setPriority(event.target.value)}
                        />
                        <FieldDescription>1 is highest priority.</FieldDescription>
                      </Field>
                    </Field>
                  </FieldGroup>
                  <Button type="submit" variant="outline" className="self-start" disabled={createGoalMutation.isPending}>
                    {createGoalMutation.isPending ? "Saving…" : "Add goal"}
                  </Button>
                </form>
              </CardContent>
            </Card>

            {profileQuery.isLoading ? (
              <LoadingState label="Loading saved goals" />
            ) : profileQuery.error ? (
              <ErrorState error={profileQuery.error} onRetry={() => profileQuery.refetch()} />
            ) : savedGoals.length > 0 ? (
              <div className="flex flex-col gap-3">
                {savedGoals.map((goal) => (
                  <Card key={goal.id}>
                    <CardContent className="flex flex-wrap items-center gap-3 pt-6">
                      <CheckCircle2 className="text-primary size-4 shrink-0" aria-hidden="true" />
                      <div>
                        <p className="text-sm font-medium">{goal.goal_type}</p>
                        <p className="text-muted-foreground text-xs">
                          Target {formatCurrency(goal.target_amount)} by {formatDate(goal.target_date)} · Saved{" "}
                          {formatCurrency(goal.current_savings)} · Priority {goal.priority}
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <div className="text-muted-foreground flex items-center gap-2 text-sm">
                <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
                No goals saved yet.
              </div>
            )}

            <div className="flex flex-wrap items-center justify-between gap-2">
              <Button variant="outline" render={<Link to="/onboarding/questionnaire" />}>
                Back
              </Button>
              <Button onClick={() => navigate("/dashboard")}>Continue to Dashboard</Button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
