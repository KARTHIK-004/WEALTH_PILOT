import { Plus } from "lucide-react"
import { useState } from "react"

import { ErrorState } from "@/components/shell/error-state"
import { LoadingState } from "@/components/shell/loading-state"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  useCreateHouseholdFinanceRecord,
  useDeleteHouseholdFinanceRecord,
  useHouseholdFinanceQuery,
  useUpdateHouseholdFinanceRecord,
  type FinanceResource,
} from "@/hooks/use-household-finances"
import { formatCurrency, formatDate, formatPercent, formatStatusLabel } from "@/lib/format"

/**
 * Phase 33 — the household's own financial records: income, expenses, assets
 * and liabilities. It lists exactly what `GET /api/households/{id}/{resource}`
 * returns and lets the household's PRIMARY member add, edit and delete them;
 * every other member sees the same lists read-only (the backend enforces both).
 *
 * **No total, sum, net worth, savings, ratio or coverage figure is displayed
 * or computed here, and none may be added** — Phase 33 stores source data and
 * aggregation is a later phase (`docs/DECISIONS.md` ADR-032). The only
 * number handling in this file is display formatting of an API value and
 * parsing a typed field back to a number on submit.
 *
 * A value the API returns as `null` renders as "Not provided", never as 0.
 */

type FieldDef =
  | { kind: "text"; name: string; label: string; required: boolean; maxLength: number; description?: string }
  | { kind: "money"; name: string; label: string; positive: boolean; required: boolean; description?: string }
  /** Phase 35 -- a rate, entered as a decimal and sent verbatim (the Phase 28
   * convention). Never converted, and never used in any calculation. */
  | { kind: "rate"; name: string; label: string; required: boolean; description?: string }
  /** Phase 36 -- a calendar date, entered with the native date input and sent
   * as the ISO `YYYY-MM-DD` string it produces. */
  | { kind: "date"; name: string; label: string; required: boolean; description?: string }
  | { kind: "select"; name: string; label: string; options: readonly string[]; required: boolean; description?: string }
  | { kind: "boolean"; name: string; label: string; initial: "true" | "false" | ""; description?: string }

interface ColumnDef {
  name: string
  label: string
  render: (record: Record<string, unknown>) => string
}

interface ResourceConfig {
  singular: string
  emptyMessage: string
  note: string
  fields: FieldDef[]
  columns: ColumnDef[]
}

const FREQUENCIES = ["monthly", "yearly", "one_time"] as const
const EXPENSE_CATEGORIES = [
  "housing", "food", "utilities", "transportation", "education", "healthcare",
  "insurance", "debt_payment", "childcare", "entertainment", "other",
] as const
const ASSET_TYPES = ["cash", "bank_account", "fixed_deposit", "investment", "real_estate", "vehicle", "retirement", "other"] as const
const LIABILITY_TYPES = ["mortgage", "personal_loan", "education_loan", "vehicle_loan", "credit_card", "other"] as const
const GOAL_TYPES = ["emergency_fund", "house", "education", "retirement", "travel", "major_purchase", "other"] as const

/** `null` means "not provided" — never 0 (`docs/RULES.md` Rule 13). */
const money = (value: unknown): string => (value === null || value === undefined ? "Not provided" : formatCurrency(value as number))
const text = (value: unknown): string => (value === null || value === undefined || value === "" ? "Not provided" : String(value))
const yesNo = (value: unknown): string => (value ? "Yes" : "No")
const label = (value: unknown): string => formatStatusLabel(String(value))
/** A stored decimal rate shown with a % suffix -- `formatPercent`'s approved
 * display formatting. `null` stays "Not provided", never 0%. */
const rate = (value: unknown): string =>
  value === null || value === undefined ? "Not provided" : formatPercent(value as number, 2)

const CONFIG: Record<FinanceResource, ResourceConfig> = {
  income: {
    singular: "income record",
    emptyMessage: "No income has been recorded for this household yet.",
    note: "Each income stream is stored on its own, exactly as entered. No total is calculated.",
    fields: [
      { kind: "text", name: "source", label: "Source", required: true, maxLength: 100, description: "For example: Salary, Rental, Pension." },
      { kind: "money", name: "amount", label: "Amount", positive: true, required: true, description: "Must be greater than 0." },
      { kind: "select", name: "frequency", label: "Frequency", options: FREQUENCIES, required: true },
      { kind: "boolean", name: "is_active", label: "Currently active", initial: "true" },
      { kind: "text", name: "notes", label: "Notes", required: false, maxLength: 500, description: "Optional. Your own context; nothing is calculated from it." },
    ],
    columns: [
      { name: "source", label: "Source", render: (r) => text(r.source) },
      { name: "amount", label: "Amount", render: (r) => money(r.amount) },
      { name: "frequency", label: "Frequency", render: (r) => label(r.frequency) },
      { name: "is_active", label: "Active", render: (r) => yesNo(r.is_active) },
      { name: "notes", label: "Notes", render: (r) => text(r.notes) },
    ],
  },
  expenses: {
    singular: "expense record",
    emptyMessage: "No expenses have been recorded for this household yet.",
    note: "Each expense is stored on its own. Nothing is totalled, and essential expenses are not summed.",
    fields: [
      { kind: "select", name: "category", label: "Category", options: EXPENSE_CATEGORIES, required: true },
      { kind: "text", name: "description", label: "Description", required: false, maxLength: 200, description: "Optional. Left blank, it stays unrecorded." },
      { kind: "money", name: "amount", label: "Amount", positive: true, required: true, description: "Must be greater than 0." },
      { kind: "select", name: "frequency", label: "Frequency", options: FREQUENCIES, required: true },
      { kind: "boolean", name: "is_essential", label: "Essential expense", initial: "", description: "Your household's own judgement — it is never assumed." },
      { kind: "boolean", name: "is_active", label: "Currently active", initial: "true" },
      { kind: "text", name: "notes", label: "Notes", required: false, maxLength: 500, description: "Optional. Your own context; nothing is calculated from it." },
    ],
    columns: [
      { name: "category", label: "Category", render: (r) => label(r.category) },
      { name: "description", label: "Description", render: (r) => text(r.description) },
      { name: "amount", label: "Amount", render: (r) => money(r.amount) },
      { name: "frequency", label: "Frequency", render: (r) => label(r.frequency) },
      { name: "is_essential", label: "Essential", render: (r) => yesNo(r.is_essential) },
      { name: "is_active", label: "Active", render: (r) => yesNo(r.is_active) },
      { name: "notes", label: "Notes", render: (r) => text(r.notes) },
    ],
  },
  assets: {
    singular: "asset record",
    emptyMessage: "No assets have been recorded for this household yet.",
    note: "Self-reported values, stored as entered — they are not market prices and are never revalued or optimised.",
    fields: [
      { kind: "text", name: "name", label: "Name", required: true, maxLength: 100, description: "For example: Joint savings account." },
      { kind: "select", name: "asset_type", label: "Type", options: ASSET_TYPES, required: true },
      { kind: "money", name: "current_value", label: "Current value", positive: false, required: true, description: "May be 0, but not negative." },
      { kind: "boolean", name: "is_liquid", label: "Liquid", initial: "", description: "Can it be converted to cash quickly?" },
      { kind: "text", name: "description", label: "Description", required: false, maxLength: 200, description: "Optional detail beyond the name." },
      { kind: "text", name: "notes", label: "Notes", required: false, maxLength: 500, description: "Optional. Your own context; nothing is calculated from it." },
    ],
    columns: [
      { name: "name", label: "Name", render: (r) => text(r.name) },
      { name: "asset_type", label: "Type", render: (r) => label(r.asset_type) },
      { name: "current_value", label: "Current value", render: (r) => money(r.current_value) },
      { name: "is_liquid", label: "Liquid", render: (r) => yesNo(r.is_liquid) },
      { name: "description", label: "Description", render: (r) => text(r.description) },
      { name: "notes", label: "Notes", render: (r) => text(r.notes) },
    ],
  },
  liabilities: {
    singular: "liability record",
    emptyMessage: "No liabilities have been recorded for this household yet.",
    note: "Stored as entered. The interest rate is recorded for reference only — no debt ratio, repayment schedule, payoff date or interest amount is calculated.",
    fields: [
      { kind: "text", name: "name", label: "Name", required: true, maxLength: 100, description: "For example: Home loan." },
      { kind: "select", name: "liability_type", label: "Type", options: LIABILITY_TYPES, required: true },
      { kind: "money", name: "outstanding_amount", label: "Outstanding amount", positive: false, required: true, description: "May be 0, but not negative." },
      { kind: "money", name: "monthly_payment", label: "Monthly payment", positive: false, required: false, description: "Optional. Left blank it stays unrecorded, which is not the same as 0." },
      { kind: "rate", name: "interest_rate", label: "Interest rate", required: false, description: "Optional. As a decimal — 0.0425 means 4.25%. Left blank it stays unrecorded; 0 means interest-free." },
      { kind: "text", name: "description", label: "Description", required: false, maxLength: 200, description: "Optional detail beyond the name." },
      { kind: "text", name: "notes", label: "Notes", required: false, maxLength: 500, description: "Optional. Your own context; nothing is calculated from it." },
    ],
    columns: [
      { name: "name", label: "Name", render: (r) => text(r.name) },
      { name: "liability_type", label: "Type", render: (r) => label(r.liability_type) },
      { name: "outstanding_amount", label: "Outstanding", render: (r) => money(r.outstanding_amount) },
      { name: "monthly_payment", label: "Monthly payment", render: (r) => money(r.monthly_payment) },
      { name: "interest_rate", label: "Interest rate", render: (r) => rate(r.interest_rate) },
      { name: "description", label: "Description", render: (r) => text(r.description) },
      { name: "notes", label: "Notes", render: (r) => text(r.notes) },
    ],
  },
  goals: {
    singular: "goal",
    emptyMessage: "No goals have been recorded for this household yet.",
    note: "Your household's own goals, stored as entered and listed in the order they were added. No projection, required contribution or feasibility is calculated — the household's return, inflation and contribution assumptions are not recorded.",
    fields: [
      { kind: "text", name: "name", label: "Name", required: true, maxLength: 100, description: "For example: Deposit for a home." },
      { kind: "select", name: "goal_type", label: "Goal type", options: GOAL_TYPES, required: true },
      { kind: "money", name: "target_amount", label: "Target amount", positive: true, required: true, description: "Must be greater than 0." },
      { kind: "money", name: "current_savings", label: "Current amount", positive: false, required: false, description: "Optional. What is already set aside. Left blank it stays unrecorded, which is not the same as 0." },
      { kind: "date", name: "target_date", label: "Target date", required: true },
      { kind: "boolean", name: "is_active", label: "Currently active", initial: "true" },
      { kind: "text", name: "notes", label: "Notes", required: false, maxLength: 500, description: "Optional. Your own context; nothing is calculated from it." },
    ],
    columns: [
      { name: "name", label: "Name", render: (r) => text(r.name) },
      { name: "goal_type", label: "Goal type", render: (r) => label(r.goal_type) },
      { name: "target_amount", label: "Target amount", render: (r) => money(r.target_amount) },
      { name: "current_savings", label: "Current amount", render: (r) => money(r.current_savings) },
      { name: "target_date", label: "Target date", render: (r) => formatDate(r.target_date as string) },
      { name: "is_active", label: "Active", render: (r) => yesNo(r.is_active) },
      { name: "notes", label: "Notes", render: (r) => text(r.notes) },
    ],
  },
}

/** Form state is all strings so "empty", "0" and a partially typed value stay
 * distinguishable; conversion happens once, at submit. */
type FormValues = Record<string, string>

function initialValues(config: ResourceConfig, record?: Record<string, unknown>): FormValues {
  const values: FormValues = {}
  for (const field of config.fields) {
    const current = record?.[field.name]
    if (field.kind === "boolean") {
      values[field.name] = record ? String(Boolean(current)) : field.initial
    } else {
      values[field.name] = current === null || current === undefined ? "" : String(current)
    }
  }
  return values
}

/** Form-shape validation only (required / numeric / sign) — the mirror of the
 * API's own schema rules, which remain the enforcement point. */
function validate(config: ResourceConfig, values: FormValues): string | null {
  for (const field of config.fields) {
    const raw = (values[field.name] ?? "").trim()
    if (field.kind === "text" && field.required && raw === "") return `${field.label} is required.`
    if (field.kind === "select" && field.required && raw === "") return `${field.label} is required.`
    if (field.kind === "boolean" && raw === "") return `${field.label} is required.`
    if (field.kind === "money") {
      if (raw === "") {
        if (field.required) return `${field.label} is required.`
        continue
      }
      const parsed = Number(raw)
      if (!Number.isFinite(parsed)) return `${field.label} must be a number.`
      if (field.positive && parsed <= 0) return `${field.label} must be greater than 0.`
      if (!field.positive && parsed < 0) return `${field.label} cannot be negative.`
    }
    if (field.kind === "date") {
      if (raw === "") {
        if (field.required) return `${field.label} is required.`
        continue
      }
      if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) return `${field.label} must be a full date.`
    }
    if (field.kind === "rate") {
      if (raw === "") {
        if (field.required) return `${field.label} is required.`
        continue
      }
      const parsed = Number(raw)
      if (!Number.isFinite(parsed)) return `${field.label} must be a number.`
      if (parsed < 0) return `${field.label} cannot be negative.`
    }
  }
  return null
}

/** Builds the request body: an empty optional field is sent as `null`
 * ("not provided"), never as 0 or "". */
function toBody(config: ResourceConfig, values: FormValues): Record<string, unknown> {
  const body: Record<string, unknown> = {}
  for (const field of config.fields) {
    const raw = (values[field.name] ?? "").trim()
    if (field.kind === "boolean") {
      body[field.name] = raw === "true"
    } else if (field.kind === "money" || field.kind === "rate") {
      // Parsing the typed text back to a number -- the value itself is sent
      // exactly as entered, never scaled or converted.
      body[field.name] = raw === "" ? null : Number(raw)
    } else {
      body[field.name] = raw === "" ? null : raw
    }
  }
  return body
}

function RecordDialog({
  resource,
  config,
  record,
  open,
  onOpenChange,
  householdId,
  profileId,
}: {
  resource: FinanceResource
  config: ResourceConfig
  record?: Record<string, unknown>
  open: boolean
  onOpenChange: (open: boolean) => void
  householdId: number
  profileId: number
}) {
  const [values, setValues] = useState<FormValues>(() => initialValues(config, record))
  const [formError, setFormError] = useState<string | null>(null)
  const createMutation = useCreateHouseholdFinanceRecord(resource, householdId, profileId)
  const updateMutation = useUpdateHouseholdFinanceRecord(resource, householdId, profileId)
  const mutation = record ? updateMutation : createMutation
  const isEdit = record !== undefined
  const titleId = `${resource}-dialog-title`

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    setFormError(null)
    mutation.reset()
    const problem = validate(config, values)
    if (problem) {
      setFormError(problem)
      return
    }
    // `toBody` builds exactly this resource's own fields from its config, so
    // the object matches that resource's generated schema; the cast is the
    // one place that cannot be expressed generically.
    const body = toBody(config, values) as never
    const onSuccess = () => onOpenChange(false)
    if (isEdit) {
      updateMutation.mutate({ recordId: record.id as number, body }, { onSuccess })
    } else {
      createMutation.mutate(body, { onSuccess })
    }
  }

  const set = (name: string, value: string) => setValues((previous) => ({ ...previous, [name]: value }))

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-labelledby={titleId}>
        <DialogHeader>
          <DialogTitle id={titleId}>
            {isEdit ? `Edit ${config.singular}` : `Add ${config.singular}`}
          </DialogTitle>
          <DialogDescription>
            Stored for the household exactly as entered. Nothing is calculated from it.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
          {formError ? (
            <Alert variant="destructive">
              <AlertDescription>{formError}</AlertDescription>
            </Alert>
          ) : null}
          {mutation.isError ? <ErrorState error={mutation.error} onRetry={() => mutation.reset()} /> : null}

          <FieldGroup>
            {config.fields.map((field) => {
              const inputId = `${resource}-${field.name}`
              return (
                <Field key={field.name}>
                  <FieldLabel htmlFor={inputId}>
                    {field.label}
                    {field.kind !== "boolean" && !field.required ? " (optional)" : ""}
                  </FieldLabel>
                  {field.kind === "text" ? (
                    <Input
                      id={inputId}
                      maxLength={field.maxLength}
                      value={values[field.name] ?? ""}
                      onChange={(event) => set(field.name, event.target.value)}
                    />
                  ) : field.kind === "money" ? (
                    <Input
                      id={inputId}
                      type="number"
                      inputMode="decimal"
                      min={field.positive ? undefined : 0}
                      step="0.01"
                      placeholder={field.required ? undefined : "Not provided"}
                      value={values[field.name] ?? ""}
                      onChange={(event) => set(field.name, event.target.value)}
                    />
                  ) : field.kind === "date" ? (
                    <Input
                      id={inputId}
                      type="date"
                      value={values[field.name] ?? ""}
                      onChange={(event) => set(field.name, event.target.value)}
                    />
                  ) : field.kind === "rate" ? (
                    <Input
                      id={inputId}
                      type="number"
                      inputMode="decimal"
                      min={0}
                      step="0.0001"
                      placeholder={field.required ? undefined : "Not provided"}
                      value={values[field.name] ?? ""}
                      onChange={(event) => set(field.name, event.target.value)}
                    />
                  ) : field.kind === "select" ? (
                    <Select value={values[field.name] || null} onValueChange={(value) => value && set(field.name, value)}>
                      <SelectTrigger id={inputId} className="w-full">
                        <SelectValue placeholder="Select…" />
                      </SelectTrigger>
                      <SelectContent>
                        {field.options.map((option) => (
                          <SelectItem key={option} value={option}>
                            {formatStatusLabel(option)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <Select value={values[field.name] || null} onValueChange={(value) => value && set(field.name, value)}>
                      <SelectTrigger id={inputId} className="w-full">
                        <SelectValue placeholder="Select…" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="true">Yes</SelectItem>
                        <SelectItem value="false">No</SelectItem>
                      </SelectContent>
                    </Select>
                  )}
                  {field.description ? <FieldDescription>{field.description}</FieldDescription> : null}
                </Field>
              )
            })}
          </FieldGroup>

          <DialogFooter>
            <DialogClose render={<Button type="button" variant="outline" />}>Cancel</DialogClose>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Saving…" : isEdit ? "Save changes" : `Add ${config.singular}`}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function HouseholdFinanceSection({
  resource,
  householdId,
  profileId,
  canManage,
}: {
  resource: FinanceResource
  householdId: number
  profileId: number
  canManage: boolean
}) {
  const config = CONFIG[resource]
  const query = useHouseholdFinanceQuery(resource, householdId, profileId)
  const deleteMutation = useDeleteHouseholdFinanceRecord(resource, householdId, profileId)
  const [dialogFor, setDialogFor] = useState<"new" | number | null>(null)
  const [confirmingId, setConfirmingId] = useState<number | null>(null)

  const records = (query.data ?? []) as unknown as Record<string, unknown>[]
  const openRecord = typeof dialogFor === "number" ? records.find((r) => r.id === dialogFor) : undefined

  return (
    <div className="flex flex-col gap-3">
      <p className="text-muted-foreground text-xs">{config.note}</p>

      {query.isLoading ? (
        <LoadingState label={`Loading household ${resource}`} />
      ) : query.error ? (
        <ErrorState error={query.error} onRetry={() => query.refetch()} />
      ) : records.length === 0 ? (
        <p className="text-sm">{config.emptyMessage}</p>
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                {config.columns.map((column) => (
                  <TableHead key={column.name}>{column.label}</TableHead>
                ))}
                {canManage ? <TableHead className="text-right">Actions</TableHead> : null}
              </TableRow>
            </TableHeader>
            <TableBody>
              {records.map((record) => {
                const rowLabel = String(record.source ?? record.name ?? record.category ?? record.id)
                return (
                  <TableRow key={record.id as number}>
                    {config.columns.map((column, index) => (
                      <TableCell key={column.name} className={index === 0 ? "font-medium" : undefined}>
                        {column.render(record)}
                      </TableCell>
                    ))}
                    {canManage ? (
                      <TableCell className="text-right">
                        {confirmingId === record.id ? (
                          <span className="inline-flex gap-2">
                            <Button
                              size="sm"
                              variant="destructive"
                              disabled={deleteMutation.isPending}
                              aria-label={`Confirm deleting ${rowLabel}`}
                              onClick={() =>
                                deleteMutation.mutate(record.id as number, { onSettled: () => setConfirmingId(null) })
                              }
                            >
                              {deleteMutation.isPending ? "Deleting…" : "Confirm"}
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => setConfirmingId(null)}>
                              Cancel
                            </Button>
                          </span>
                        ) : (
                          <span className="inline-flex gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              aria-label={`Edit ${rowLabel}`}
                              onClick={() => setDialogFor(record.id as number)}
                            >
                              Edit
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              aria-label={`Delete ${rowLabel}`}
                              onClick={() => {
                                deleteMutation.reset()
                                setConfirmingId(record.id as number)
                              }}
                            >
                              Delete
                            </Button>
                          </span>
                        )}
                      </TableCell>
                    ) : null}
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      )}

      {deleteMutation.isError ? <ErrorState error={deleteMutation.error} onRetry={() => deleteMutation.reset()} /> : null}

      {canManage ? (
        <Button variant="outline" className="self-start" onClick={() => setDialogFor("new")}>
          <Plus />
          Add {config.singular}
        </Button>
      ) : (
        <p className="text-muted-foreground text-xs">
          Only the household's primary member can add, edit or delete financial records.
        </p>
      )}

      {dialogFor !== null ? (
        <RecordDialog
          key={typeof dialogFor === "number" ? `edit-${dialogFor}` : "new"}
          resource={resource}
          config={config}
          record={openRecord}
          open
          onOpenChange={(open) => !open && setDialogFor(null)}
          householdId={householdId}
          profileId={profileId}
        />
      ) : null}
    </div>
  )
}
