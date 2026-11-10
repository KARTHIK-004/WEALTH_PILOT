/**
 * Source-level guards for how the Financial Health page and the monthly-record hooks are wired (ADR-051), run with Node's built-in test runner (`npm test`). The rendered states of the new
 * spending and debt-and-commitments views are covered in tests/behaviour-sentiment-view.cases.tsx; this file pins the wiring those renders cannot show: which cached queries a saved month
 * refreshes, that each card is keyed by the active profile so switching profile cannot show another customer's data, and that nothing is computed or hard-coded in the UI.
 */
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { test } from "node:test"

import { SPENDING_FINDING_CODES, selectSpendingRows } from "../src/lib/behaviour-insights.ts"

const read = (relative: string): string => readFileSync(new URL(`../${relative}`, import.meta.url), "utf8").replace(/\r\n/g, "\n")

test("saving or deleting a month refreshes the behaviour and spending findings of that profile (the personalized-insight query), not only the month list", () => {
  const hook = read("src/hooks/use-monthly-records.ts")
  assert.match(hook, /queryKey: \["personalized-insight", profileId\]/)
  assert.match(hook, /queryKey: \["monthly-records", profileId\]/)
  assert.equal((hook.match(/onSuccess: \(\) => invalidateMonthlyViews\(queryClient, profileId\)/g) ?? []).length, 2, "both the save and the delete refresh the same views")
})

test("every Financial Health card that reads per-customer data is keyed by the active profile, so a profile switch remounts it with no earlier data", () => {
  const page = read("src/pages/financial-health-page.tsx")
  assert.match(page, /<SpendingFromRecords key=\{profileId\} profileId=\{profileId\} \/>/)
  assert.match(page, /<CommitmentsCard key=\{profileId\} profileId=\{profileId\} \/>/)
  assert.match(page, /<BehaviourSummaryCard key=\{profileId\} profileId=\{profileId\} \/>/)
})

test("the spending view reads the backend's findings through the existing hook and the household query is per profile", () => {
  const view = read("src/components/financial-health/spending-from-records.tsx")
  assert.match(view, /usePersonalizedInsightQuery\(profileId, null\)/)
  assert.match(view, /selectSpendingRows\(data\.behaviour\.findings\)/)
  assert.match(view, /if \(error\) return <ErrorState/)
  assert.ok(view.indexOf("if (error)") < view.indexOf("rows.length === 0"), "a failure is handled before the empty state, so it is never shown as 'no data'")
  assert.match(read("src/hooks/use-household.ts"), /queryKey: \["household", profileId\]/)
})

test("the spending and commitments views compute nothing, hard-code no figure and touch no browser storage", () => {
  for (const file of ["src/components/financial-health/spending-from-records.tsx", "src/components/financial-health/individual-finances.tsx", "src/lib/behaviour-insights.ts"]) {
    const source = read(file)
    assert.doesNotMatch(source, /localStorage|sessionStorage|indexedDB|document\.cookie|console\./, file)
    assert.doesNotMatch(source, /\.reduce\(|toFixed\(|Math\.(round|floor|ceil|sum|pow)|parseFloat\(/, file)
    assert.doesNotMatch(source, /₹ ?\d|\bmock\b|\bfake\b/i, file)
  }
})

test("the spending rows are exactly the backend's two spending finding codes, in the backend's order, sentences unchanged", () => {
  assert.deepEqual([...SPENDING_FINDING_CODES], ["expenses_trend", "expense_to_income_ratio"])
  const finding = (code: string, statement: string) => ({ code, category: "trend" as const, status: "observed" as const, statement, sources: ["x"], direction: null, values: {} })
  const rows = selectSpendingRows([
    finding("savings_trend", "Savings changed."),
    finding("expense_to_income_ratio", "Ratio sentence."),
    finding("expenses_trend", "Trend sentence."),
    { ...finding("expenses_trend", "Not observed sentence."), status: "unavailable" as const },
  ])
  assert.deepEqual(rows.map((r) => [r.code, r.statement]), [["expense_to_income_ratio", "Ratio sentence."], ["expenses_trend", "Trend sentence."]])
  assert.deepEqual(selectSpendingRows([]), [])
})
