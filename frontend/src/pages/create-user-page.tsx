import { GraduationCap } from "lucide-react"
import { useState } from "react"
import { Link, useNavigate } from "react-router"

import { ErrorState } from "@/components/shell/error-state"
import { OnboardingSteps } from "@/components/shell/onboarding-steps"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { validateProfileForm, type ProfileFormField } from "@/lib/profile-form"
import { CAPACITY_OPTIONS } from "@/lib/terminology"
import { useCreateProfile } from "@/hooks/use-create-profile"
import { useAuth } from "@/providers/auth-context"
import { useCustomer } from "@/providers/customer-context"

const UNSPECIFIED = "unspecified"

/**
 * Real FAR-Trans category values (`reports/phase2_data_quality_report.md`'s
 * `customer_type_distribution` / `investment_capacity_distribution`,
 * `Predicted_*`/`Not_Available` excluded per CLAUDE.md rule 7 -- those are
 * another model's output, not genuine categories a new profile should
 * claim). `ProfileCreateRequest.customer_type`/`.investment_capacity` are
 * plain, unconstrained strings in the Pydantic schema (no backend enum to
 * mirror), so these options are a UI convenience grounded in the dataset's
 * own real values, not an invented business rule -- selecting "Unspecified"
 * omits the field entirely, exactly like leaving it blank.
 */
const CUSTOMER_TYPE_OPTIONS = [
  { value: UNSPECIFIED, label: "Unspecified" },
  { value: "Mass", label: "Mass" },
  { value: "Premium", label: "Premium" },
  { value: "Professional", label: "Professional" },
  { value: "Inactive", label: "Inactive" },
  { value: "Legal Entity", label: "Legal Entity" },
]

const INVESTMENT_CAPACITY_OPTIONS = [
  { value: UNSPECIFIED, label: "Unspecified" },
  ...CAPACITY_OPTIONS,
]

/**
 * `/create-user` -- Phase 21. A standalone onboarding page, deliberately
 * outside `AppShell` (no sidebar/header, matching `/login`'s own
 * treatment -- section 7/35: an onboarding action, not an analysis page)
 * and deliberately a PUBLIC route (not wrapped in `ProtectedRoute`), since
 * `reports/phase21_create_user_report.md`'s own "final user experience"
 * diagram shows Create New User as a path parallel to, not gated behind,
 * the Demo Account login -- BUILD_PLAN's "public registration" exception
 * to the default guard. On a genuine `POST /api/profiles` success, this
 * page also calls `grantSessionAfterProfileCreation()` (the SAME Phase 20
 * prototype-auth context, not a second auth system) so the resulting
 * "Continue" action can reach the protected Dashboard without a separate,
 * redundant login step.
 *
 * Every submitted field is a real `ProfileCreateRequest` field (generated
 * from the FastAPI schema, `types/api.ts`) -- nothing invented, no goal
 * fields (Phase 22 collects those separately -- see
 * `pages/onboarding-goals-page.tsx` for why they can't be attached to this
 * already-created profile), no risk-category picker (section 13: risk
 * stays a backend/model responsibility), no financial figure this API does
 * not literally accept.
 *
 * Phase 22 changes exactly one thing here: `handleContinue` now navigates
 * to `/onboarding/questionnaire` instead of `/` (Dashboard) -- the "small
 * routing/link change" its own phase brief explicitly anticipated, not a
 * redesign. Everything else in this file is unchanged from Phase 21.
 */
export function CreateUserPage() {
  const navigate = useNavigate()
  const { setProfileId } = useCustomer()
  const { grantSessionAfterProfileCreation } = useAuth()
  const mutation = useCreateProfile()

  const [name, setName] = useState("")
  const [age, setAge] = useState("")
  const [income, setIncome] = useState("")
  const [employmentStatus, setEmploymentStatus] = useState("")
  const [customerType, setCustomerType] = useState(UNSPECIFIED)
  const [investmentCapacity, setInvestmentCapacity] = useState(UNSPECIFIED)

  // The form is `noValidate` (the browser's own checks never run), so the rules the backend enforces are checked here, in plain words, per field (`@/lib/profile-form`). Errors appear
  // only after a first attempt to submit, and the first invalid field receives focus.
  const [attempted, setAttempted] = useState(false)
  const checked = validateProfileForm({ name, age, employmentStatus, income })
  const fieldError = (field: ProfileFormField): string | undefined => (attempted && !checked.ok ? checked.errors[field] : undefined)
  const FIELD_IDS: Record<ProfileFormField, string> = {
    name: "create-user-name",
    age: "create-user-age",
    employmentStatus: "create-user-employment",
    income: "create-user-income",
  }

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!checked.ok) {
      setAttempted(true)
      document.getElementById(FIELD_IDS[checked.firstInvalid])?.focus()
      return
    }
    mutation.mutate({
      ...checked.payload,
      customer_type: customerType === UNSPECIFIED ? undefined : customerType,
      investment_capacity: investmentCapacity === UNSPECIFIED ? undefined : investmentCapacity,
    })
  }

  const handleContinue = () => {
    if (!mutation.data) return
    setProfileId(mutation.data.customer_id)
    grantSessionAfterProfileCreation()
    navigate("/onboarding/questionnaire", { replace: true })
  }

  return (
    <main id="main-content" className="bg-background min-h-svh p-6 md:p-10">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
        <div className="flex items-center gap-2">
          <div className="bg-primary text-primary-foreground flex size-6 items-center justify-center rounded-md">
            <GraduationCap className="size-4" />
          </div>
          <span className="font-medium">WealthPilot AI</span>
        </div>

        <OnboardingSteps current="profile" />

        {mutation.isSuccess ? (
          <Card>
            {/* `CardTitle` renders a <div>, not a heading element -- this
                sr-only <h1> gives the success state a real, announced
                heading (section 32's heading-hierarchy check) without
                changing its visible design. */}
            <h1 className="sr-only">Profile Created Successfully</h1>
            <CardHeader>
              <CardTitle>Profile Created Successfully</CardTitle>
              <CardDescription>Your WealthPilot profile has been created.</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm">
                Profile ID: <span className="font-mono font-medium">{mutation.data.customer_id}</span>
              </p>
            </CardContent>
            <CardFooter>
              <Button onClick={handleContinue}>Continue</Button>
            </CardFooter>
          </Card>
        ) : (
          <>
            <div className="space-y-1">
              <h1 className="text-2xl font-bold">Create Your Profile</h1>
              <p className="text-muted-foreground text-sm">
                Enter your information to create a WealthPilot profile. Only the fields this
                API supports are shown below.
              </p>
            </div>

            {mutation.isError ? <ErrorState error={mutation.error} onRetry={() => mutation.reset()} /> : null}

            <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-6">
              <Card>
                <CardHeader>
                  <CardTitle>Personal Information</CardTitle>
                </CardHeader>
                <CardContent>
                  <FieldGroup>
                    <Field data-invalid={fieldError("name") ? true : undefined}>
                      <FieldLabel htmlFor="create-user-name">Full name</FieldLabel>
                      <Input
                        id="create-user-name"
                        value={name}
                        onChange={(event) => setName(event.target.value)}
                        required
                        aria-invalid={fieldError("name") ? true : undefined}
                        aria-describedby={fieldError("name") ? "create-user-name-error" : undefined}
                      />
                      {fieldError("name") ? <FieldError id="create-user-name-error">{fieldError("name")}</FieldError> : null}
                    </Field>
                    <Field className="@md/field-group:flex-row @md/field-group:*:flex-1" orientation="responsive">
                      <Field data-invalid={fieldError("age") ? true : undefined}>
                        <FieldLabel htmlFor="create-user-age">Age</FieldLabel>
                        <Input
                          id="create-user-age"
                          type="number"
                          inputMode="numeric"
                          min={0}
                          max={120}
                          step={1}
                          value={age}
                          onChange={(event) => setAge(event.target.value)}
                          aria-invalid={fieldError("age") ? true : undefined}
                          aria-describedby={fieldError("age") ? "create-user-age-error" : undefined}
                        />
                        {fieldError("age") ? <FieldError id="create-user-age-error">{fieldError("age")}</FieldError> : <FieldDescription>Optional.</FieldDescription>}
                      </Field>
                      <Field data-invalid={fieldError("employmentStatus") ? true : undefined}>
                        <FieldLabel htmlFor="create-user-employment">Employment status</FieldLabel>
                        <Input
                          id="create-user-employment"
                          value={employmentStatus}
                          onChange={(event) => setEmploymentStatus(event.target.value)}
                          placeholder="e.g. Full-time, Self-employed, Retired"
                          aria-invalid={fieldError("employmentStatus") ? true : undefined}
                          aria-describedby={fieldError("employmentStatus") ? "create-user-employment-error" : undefined}
                        />
                        {fieldError("employmentStatus") ? (
                          <FieldError id="create-user-employment-error">{fieldError("employmentStatus")}</FieldError>
                        ) : (
                          <FieldDescription>Optional.</FieldDescription>
                        )}
                      </Field>
                    </Field>
                  </FieldGroup>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Financial / Investment Profile</CardTitle>
                  <CardDescription>
                    These categories match the source dataset's own classification, not a
                    risk assessment — risk category is always computed by the backend.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <FieldGroup>
                    <Field data-invalid={fieldError("income") ? true : undefined}>
                      <FieldLabel htmlFor="create-user-income">Annual income</FieldLabel>
                      <Input
                        id="create-user-income"
                        type="number"
                        inputMode="decimal"
                        min={0}
                        step="0.01"
                        value={income}
                        onChange={(event) => setIncome(event.target.value)}
                        aria-invalid={fieldError("income") ? true : undefined}
                        aria-describedby={fieldError("income") ? "create-user-income-error" : undefined}
                      />
                      {fieldError("income") ? <FieldError id="create-user-income-error">{fieldError("income")}</FieldError> : <FieldDescription>Optional.</FieldDescription>}
                    </Field>
                    <Field>
                      <FieldLabel htmlFor="create-user-customer-type">Customer type</FieldLabel>
                      <Select items={CUSTOMER_TYPE_OPTIONS} value={customerType} onValueChange={(value) => setCustomerType(value ?? UNSPECIFIED)}>
                        <SelectTrigger id="create-user-customer-type" className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {CUSTOMER_TYPE_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FieldDescription>Optional.</FieldDescription>
                    </Field>
                    <Field>
                      <FieldLabel htmlFor="create-user-investment-capacity">Capacity band</FieldLabel>
                      <Select
                        items={INVESTMENT_CAPACITY_OPTIONS}
                        value={investmentCapacity}
                        onValueChange={(value) => setInvestmentCapacity(value ?? UNSPECIFIED)}
                      >
                        <SelectTrigger id="create-user-investment-capacity" className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {INVESTMENT_CAPACITY_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FieldDescription>Optional.</FieldDescription>
                    </Field>
                  </FieldGroup>
                </CardContent>
              </Card>

              <Button type="submit" disabled={mutation.isPending} className="self-start">
                {mutation.isPending ? "Creating profile…" : "Create Profile"}
              </Button>
            </form>
          </>
        )}

        <p className="text-muted-foreground text-sm">
          <Link to="/login" className="underline underline-offset-4">
            Back to Login
          </Link>
        </p>
      </div>
    </main>
  )
}
