/**
 * Unit tests for the Create Profile form rules (src/lib/profile-form.ts), run by `npm test`. The limits are cross-checked against `ProfileCreateRequest` in the BACKEND source, so the form
 * can never accept something the API rejects for these reasons, and the messages are checked to be field-specific, plain, and free of the user's input.
 */
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { test } from "node:test"

import { PROFILE_FIELD_ORDER, PROFILE_LIMITS, validateProfileForm, type ProfileFormInput } from "../src/lib/profile-form.ts"

const SCHEMAS = readFileSync(new URL("../../backend/wealthpilot/api/schemas.py", import.meta.url), "utf8")
const block = SCHEMAS.slice(SCHEMAS.indexOf("class ProfileCreateRequest"), SCHEMAS.indexOf("class ProfileCreateResponse"))

const valid: ProfileFormInput = { name: "Asha Rao", age: "31", employmentStatus: "Full-time", income: "960000" }
const check = (over: Partial<ProfileFormInput>) => validateProfileForm({ ...valid, ...over })

test("the limits equal the backend schema's", () => {
  assert.match(block, /name: str = Field\(min_length=1, max_length=(\d+)\)/)
  assert.equal(PROFILE_LIMITS.nameMax, Number(/name: str = Field\(min_length=1, max_length=(\d+)\)/.exec(block)?.[1]))
  const age = /age: int \| None = Field\(default=None, ge=(\d+), le=(\d+)\)/.exec(block)
  assert.deepEqual([PROFILE_LIMITS.ageMin, PROFILE_LIMITS.ageMax], [Number(age?.[1]), Number(age?.[2])])
  assert.match(block, /income: float \| None = Field\(default=None, ge=0\)/)
  assert.equal(PROFILE_LIMITS.employmentMax, Number(/employment_status: str \| None = Field\(default=None, max_length=(\d+)\)/.exec(block)?.[1]))
})

test("a complete valid form gives a trimmed payload", () => {
  const result = check({ name: "  Asha Rao  ", employmentStatus: "  Full-time " })
  assert.equal(result.ok, true)
  if (result.ok) assert.deepEqual(result.payload, { name: "Asha Rao", age: 31, income: 960000, employment_status: "Full-time" })
})

test("optional fields left empty are omitted (unknown), never sent as zero", () => {
  const result = check({ age: "", income: "", employmentStatus: "   " })
  assert.equal(result.ok, true)
  if (result.ok) {
    assert.equal(result.payload.age, undefined)
    assert.equal(result.payload.income, undefined)
    assert.equal(result.payload.employment_status, undefined)
    assert.ok(!("age" in JSON.parse(JSON.stringify(result.payload))))
  }
})

test("an explicit zero age or income is a real value and is kept", () => {
  const result = check({ age: "0", income: "0" })
  assert.equal(result.ok, true)
  if (result.ok) assert.deepEqual([result.payload.age, result.payload.income], [0, 0])
})

test("an empty or whitespace-only name is refused", () => {
  for (const name of ["", " ", "\t\n  "]) {
    const result = check({ name })
    assert.equal(result.ok, false)
    if (!result.ok) {
      assert.equal(result.firstInvalid, "name")
      assert.equal(result.errors.name, "Enter your full name.")
    }
  }
})

test("the name limit is in characters: 200 is accepted, 201 is refused, and an emoji counts once", () => {
  assert.equal(check({ name: "a".repeat(200) }).ok, true)
  assert.equal(check({ name: "a".repeat(201) }).ok, false)
  assert.equal(check({ name: "\u{1F600}".repeat(200) }).ok, true)
  assert.equal(check({ name: "\u{1F600}".repeat(201) }).ok, false)
})

test("age must be a whole number from 0 to 120", () => {
  for (const age of ["0", "1", "120", " 45 "]) assert.equal(check({ age }).ok, true, age)
  for (const age of ["121", "999", "-1", "30.5", "3e1", "abc", "1 2", "+5", "1000"]) {
    const result = check({ age })
    assert.equal(result.ok, false, age)
    if (!result.ok) assert.equal(result.errors.age, "Age must be a whole number from 0 to 120.")
  }
})

test("income must be a finite number that is 0 or more", () => {
  for (const income of ["0", "0.01", "960000", "1e6", " 52000.50 "]) assert.equal(check({ income }).ok, true, income)
  for (const income of ["-1", "-0.01", "abc", "Infinity", "NaN", "1,000"]) {
    const result = check({ income })
    assert.equal(result.ok, false, income)
    if (!result.ok) assert.equal(result.errors.income, "Annual income must be a number that is 0 or more.")
  }
})

test("employment status is limited to the backend's 100 characters", () => {
  assert.equal(check({ employmentStatus: "x".repeat(100) }).ok, true)
  const result = check({ employmentStatus: "x".repeat(101) })
  assert.equal(result.ok, false)
  if (!result.ok) assert.match(result.errors.employmentStatus ?? "", /100 characters or fewer/)
})

test("every invalid field is reported together and focus goes to the first one in page order", () => {
  const result = validateProfileForm({ name: "", age: "500", employmentStatus: "x".repeat(101), income: "-5" })
  assert.equal(result.ok, false)
  if (!result.ok) {
    assert.deepEqual(Object.keys(result.errors).sort(), ["age", "employmentStatus", "income", "name"])
    assert.equal(result.firstInvalid, "name")
  }
  const ageFirst = validateProfileForm({ ...valid, age: "500", income: "-5" })
  assert.equal(!ageFirst.ok && ageFirst.firstInvalid, "age")
  assert.deepEqual([...PROFILE_FIELD_ORDER], ["name", "age", "employmentStatus", "income"])
})

test("messages are specific plain sentences that never echo the input", () => {
  const secret = "PRIVATE-9931"
  const result = validateProfileForm({ name: secret.repeat(40), age: `${secret}`, employmentStatus: secret.repeat(20), income: `${secret}` })
  assert.equal(result.ok, false)
  if (!result.ok) for (const message of Object.values(result.errors)) assert.ok(!message.includes(secret) && message.endsWith("."), message)
})

test("the page uses these rules: noValidate stays on, errors are announced and tied to their fields", () => {
  const page = readFileSync(new URL("../src/pages/create-user-page.tsx", import.meta.url), "utf8")
  assert.match(page, /validateProfileForm\(/)
  assert.match(page, /<form onSubmit=\{handleSubmit\} noValidate/)
  for (const id of ["name", "age", "employment", "income"]) {
    assert.match(page, new RegExp(`aria-describedby=\\{fieldError\\("[a-zA-Z]+"\\) \\? "create-user-${id}-error" : undefined\\}`))
    assert.match(page, new RegExp(`<FieldError id="create-user-${id}-error">`))
  }
  assert.match(page, /document\.getElementById\(FIELD_IDS\[checked\.firstInvalid\]\)\?\.focus\(\)/)
  assert.doesNotMatch(page, /age: age\.trim\(\) === ""/) // the old unchecked conversion is gone
})
