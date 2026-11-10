/**
 * Client-side rules for the Create Profile form (`pages/create-user-page.tsx`), mirroring `ProfileCreateRequest` in `backend/wealthpilot/api/schemas.py`:
 * name 1-200 characters, age a whole number 0-120, income a number >= 0, employment status at most 100 characters. Pure TypeScript with no React or DOM, so it is unit-tested
 * with Node's built-in runner (`npm test`). The backend stays the authority and re-checks everything; this only lets the form say WHICH field is wrong, in plain words, before a
 * request is sent (the form uses `noValidate`, so the browser's own `required`/`min`/`max` checks never run).
 *
 * It never invents or computes a financial value: an empty optional field is omitted from the payload (unknown), never sent as 0.
 */

export const PROFILE_LIMITS = { nameMax: 200, ageMin: 0, ageMax: 120, employmentMax: 100 } as const

export type ProfileFormField = "name" | "age" | "employmentStatus" | "income"

export interface ProfileFormInput {
  name: string
  age: string
  employmentStatus: string
  income: string
}

export interface ProfilePayloadPart {
  name: string
  age?: number
  income?: number
  employment_status?: string
}

export type ProfileFormResult =
  | { ok: true; payload: ProfilePayloadPart }
  | { ok: false; errors: Partial<Record<ProfileFormField, string>>; firstInvalid: ProfileFormField }

/** Order used to move focus to the first invalid field. */
export const PROFILE_FIELD_ORDER: readonly ProfileFormField[] = ["name", "age", "employmentStatus", "income"]

export function validateProfileForm(input: ProfileFormInput): ProfileFormResult {
  const errors: Partial<Record<ProfileFormField, string>> = {}

  const name = input.name.trim()
  if (name === "") errors.name = "Enter your full name."
  else if (Array.from(name).length > PROFILE_LIMITS.nameMax) errors.name = `Your name must be ${PROFILE_LIMITS.nameMax} characters or fewer.`

  const ageText = input.age.trim()
  let age: number | undefined
  if (ageText !== "") {
    if (!/^\d{1,3}$/.test(ageText) || Number(ageText) < PROFILE_LIMITS.ageMin || Number(ageText) > PROFILE_LIMITS.ageMax) {
      errors.age = `Age must be a whole number from ${PROFILE_LIMITS.ageMin} to ${PROFILE_LIMITS.ageMax}.`
    } else age = Number(ageText)
  }

  const employment = input.employmentStatus.trim()
  if (Array.from(employment).length > PROFILE_LIMITS.employmentMax) errors.employmentStatus = `Employment status must be ${PROFILE_LIMITS.employmentMax} characters or fewer.`

  const incomeText = input.income.trim()
  let income: number | undefined
  if (incomeText !== "") {
    const parsed = Number(incomeText)
    if (!Number.isFinite(parsed) || parsed < 0) errors.income = "Annual income must be a number that is 0 or more."
    else income = parsed
  }

  const firstInvalid = PROFILE_FIELD_ORDER.find((field) => errors[field] !== undefined)
  if (firstInvalid !== undefined) return { ok: false, errors, firstInvalid }
  return { ok: true, payload: { name, age, income, employment_status: employment === "" ? undefined : employment } }
}
