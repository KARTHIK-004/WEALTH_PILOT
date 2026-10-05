import { Info, UserPlus, Users } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { useSearchParams } from "react-router"

import { ErrorState } from "@/components/shell/error-state"
import { LoadingState } from "@/components/shell/loading-state"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { HouseholdFinanceSection } from "@/components/profile/household-finance-section"
import {
  HouseholdFinancialSummarySection,
  HouseholdGoalsEmergencyFundReference,
} from "@/components/profile/household-financial-summary"
import {
  useAddHouseholdMember,
  useCreateHousehold,
  useHouseholdMembersQuery,
  useProfileHouseholdQuery,
  useRemoveHouseholdMember,
} from "@/hooks/use-household"
import { formatStatusLabel } from "@/lib/format"
import type { FinanceResource } from "@/hooks/use-household-finances"
import type { components } from "@/types/api"

type Relationship = components["schemas"]["HouseholdMemberCreateRequest"]["relationship"]
type Role = components["schemas"]["HouseholdMemberCreateRequest"]["role"]

/** What a primary member may add. `self` is reserved for the primary member
 * itself and `primary` cannot be assigned (the API rejects both). */
const RELATIONSHIP_OPTIONS: Exclude<Relationship, "self">[] = ["spouse", "parent", "child", "sibling", "other"]
const ROLE_OPTIONS: Exclude<Role, "primary">[] = ["member", "dependent"]

/** The household's record lists, as tabs beside Members: the four financial
 * record types (Phase 33) and its goals (Phase 36). Each tab lists stored
 * records only — nothing is totalled, projected or ranked. */
const FINANCE_TABS: { resource: FinanceResource; label: string }[] = [
  { resource: "income", label: "Income" },
  { resource: "expenses", label: "Expenses" },
  { resource: "assets", label: "Assets" },
  { resource: "liabilities", label: "Liabilities" },
  { resource: "goals", label: "Goals" },
]

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-0.5">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className="text-sm font-medium">{value}</p>
    </div>
  )
}

function CreateHouseholdForm({ profileId }: { profileId: number }) {
  const [name, setName] = useState("")
  const mutation = useCreateHousehold(profileId)

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    if (name.trim() === "") return
    mutation.mutate({ name })
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-3">
      {mutation.isError ? <ErrorState error={mutation.error} onRetry={() => mutation.reset()} /> : null}
      <Field>
        <FieldLabel htmlFor="household-name">Household name</FieldLabel>
        <Input
          id="household-name"
          value={name}
          maxLength={100}
          placeholder="Not created yet"
          onChange={(event) => setName(event.target.value)}
        />
        <FieldDescription>
          You become the household's primary member. Nothing else is created — members are added
          separately, and no household finances are recorded.
        </FieldDescription>
      </Field>
      <Button type="submit" variant="outline" className="self-start" disabled={mutation.isPending || name.trim() === ""}>
        {mutation.isPending ? "Creating…" : "Create Household"}
      </Button>
    </form>
  )
}

function AddMemberForm({ householdId, profileId }: { householdId: number; profileId: number }) {
  const [customerId, setCustomerId] = useState("")
  const [relationship, setRelationship] = useState<Exclude<Relationship, "self">>("spouse")
  const [role, setRole] = useState<Exclude<Role, "primary">>("member")
  const [formError, setFormError] = useState<string | null>(null)
  const mutation = useAddHouseholdMember(householdId, profileId)

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    setFormError(null)
    mutation.reset()
    const parsed = Number(customerId)
    if (customerId.trim() === "" || !Number.isInteger(parsed) || parsed <= 0) {
      setFormError("Enter the profile ID of an existing customer (a whole number greater than 0).")
      return
    }
    mutation.mutate({ customer_id: parsed, relationship, role }, { onSuccess: () => setCustomerId("") })
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-3 rounded-lg border p-4">
      <p className="flex items-center gap-2 text-sm font-medium">
        <UserPlus className="text-muted-foreground size-4" /> Add member
      </p>
      <Alert>
        <Info />
        <AlertTitle>Prototype association</AlertTitle>
        <AlertDescription>
          Add an existing customer by profile ID. This only links them to this household — it does not
          let you view, edit or switch into their account.
        </AlertDescription>
      </Alert>
      {formError ? (
        <Alert variant="destructive">
          <AlertDescription>{formError}</AlertDescription>
        </Alert>
      ) : null}
      {mutation.isError ? <ErrorState error={mutation.error} onRetry={() => mutation.reset()} /> : null}
      <FieldGroup>
        <Field className="@md/field-group:flex-row @md/field-group:*:flex-1" orientation="responsive">
          <Field>
            <FieldLabel htmlFor="household-member-customer-id">Existing profile ID</FieldLabel>
            <Input
              id="household-member-customer-id"
              type="number"
              inputMode="numeric"
              min={1}
              step={1}
              placeholder="Profile ID"
              value={customerId}
              onChange={(event) => setCustomerId(event.target.value)}
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="household-member-relationship">Relationship</FieldLabel>
            <Select value={relationship} onValueChange={(value) => value && setRelationship(value as typeof relationship)}>
              <SelectTrigger id="household-member-relationship" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {RELATIONSHIP_OPTIONS.map((option) => (
                  <SelectItem key={option} value={option}>
                    {formatStatusLabel(option)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel htmlFor="household-member-role">Role</FieldLabel>
            <Select value={role} onValueChange={(value) => value && setRole(value as typeof role)}>
              <SelectTrigger id="household-member-role" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ROLE_OPTIONS.map((option) => (
                  <SelectItem key={option} value={option}>
                    {formatStatusLabel(option)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
        </Field>
      </FieldGroup>
      <Button type="submit" variant="outline" className="self-start" disabled={mutation.isPending}>
        {mutation.isPending ? "Adding…" : "Add member"}
      </Button>
    </form>
  )
}

function HouseholdMembers({
  householdId,
  profileId,
  canManage,
}: {
  householdId: number
  profileId: number
  canManage: boolean
}) {
  const membersQuery = useHouseholdMembersQuery(householdId, profileId)
  const removeMutation = useRemoveHouseholdMember(householdId, profileId)
  const [confirmingId, setConfirmingId] = useState<number | null>(null)

  return (
    <div className="flex flex-col gap-4">
      {membersQuery.isLoading ? (
        <LoadingState label="Loading household members" />
      ) : membersQuery.error ? (
        <ErrorState error={membersQuery.error} onRetry={() => membersQuery.refetch()} />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Relationship</TableHead>
              <TableHead>Role</TableHead>
              {canManage ? <TableHead className="text-right">Actions</TableHead> : null}
            </TableRow>
          </TableHeader>
          <TableBody>
            {membersQuery.data?.members.map((member) => (
              <TableRow key={member.id}>
                <TableCell className="font-medium">
                  {member.customer_name}
                  {member.customer_id === profileId ? (
                    <Badge variant="secondary" className="ml-2">
                      You
                    </Badge>
                  ) : null}
                </TableCell>
                <TableCell>{formatStatusLabel(member.relationship)}</TableCell>
                <TableCell>{formatStatusLabel(member.role)}</TableCell>
                {canManage ? (
                  <TableCell className="text-right">
                    {member.role === "primary" ? (
                      <span className="text-muted-foreground text-xs">Cannot be removed</span>
                    ) : confirmingId === member.id ? (
                      <span className="inline-flex gap-2">
                        <Button
                          size="sm"
                          variant="destructive"
                          disabled={removeMutation.isPending}
                          aria-label={`Confirm removing ${member.customer_name}`}
                          onClick={() => removeMutation.mutate(member.id, { onSettled: () => setConfirmingId(null) })}
                        >
                          {removeMutation.isPending ? "Removing…" : "Confirm"}
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => setConfirmingId(null)}>
                          Cancel
                        </Button>
                      </span>
                    ) : (
                      <Button
                        size="sm"
                        variant="outline"
                        aria-label={`Remove ${member.customer_name}`}
                        onClick={() => {
                          removeMutation.reset()
                          setConfirmingId(member.id)
                        }}
                      >
                        Remove
                      </Button>
                    )}
                  </TableCell>
                ) : null}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {removeMutation.isError ? <ErrorState error={removeMutation.error} onRetry={() => removeMutation.reset()} /> : null}

      {canManage ? (
        <AddMemberForm householdId={householdId} profileId={profileId} />
      ) : (
        <p className="text-muted-foreground text-xs">Only the household's primary member can add or remove members.</p>
      )}
    </div>
  )
}

/**
 * Phase 32 — the Customer Profile page's household section: the household's
 * name, the customer's own role and relationship, and the member count exactly
 * as `GET /api/profiles/{id}/household` returns them, with a primary member
 * able to manage the member list. Opening the page never creates a household.
 *
 * Phase 33 adds the household's financial records (income, expenses, assets,
 * liabilities) as further tabs beside Members, again primary-managed and
 * member-readable. They are stored source records: this card displays them as
 * returned and computes NOTHING from them — no total, net worth, savings or
 * ratio (`docs/DECISIONS.md` ADR-032).
 *
 * Household membership is not account access: the authenticated customer
 * stays the active user, and adding a member by profile ID (a labelled
 * prototype association) never lets anyone switch into that customer.
 */
export function HouseholdCard({ profileId }: { profileId: number }) {
  const query = useProfileHouseholdQuery(profileId)
  // `?household=open` (the Family Demo login's landing URL, ADR-036) opens this
  // section and scrolls it into view; without it the card starts collapsed,
  // exactly as before.
  const [searchParams] = useSearchParams()
  const openedByLink = searchParams.get("household") === "open"
  const [showMembers, setShowMembers] = useState(openedByLink)
  const cardRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (openedByLink && query.data?.household) cardRef.current?.scrollIntoView({ block: "start" })
  }, [openedByLink, query.data?.household])

  const household = query.data?.household ?? null
  const membership = query.data?.membership ?? null

  return (
    <Card ref={cardRef}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Users className="text-muted-foreground size-4" /> Household
        </CardTitle>
        <CardDescription>
          The family this customer belongs to: its members, the household's own financial
          records, and a read-only summary the backend calculates from those records. Nothing
          here is scored or ranked, and no recommendation is made from it.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {query.isLoading ? (
          <LoadingState label="Loading household" />
        ) : query.error ? (
          <ErrorState error={query.error} onRetry={() => query.refetch()} />
        ) : !household || !membership ? (
          <>
            <p className="text-muted-foreground text-sm">No household created yet.</p>
            <CreateHouseholdForm profileId={profileId} />
          </>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Household" value={household.name} />
              <Stat label="Your role" value={formatStatusLabel(membership.role)} />
              <Stat label="Relationship" value={formatStatusLabel(membership.relationship)} />
              <Stat label="Members" value={String(household.member_count)} />
            </div>
            <Button variant="outline" aria-expanded={showMembers} onClick={() => setShowMembers((open) => !open)}>
              {showMembers ? "Hide Household" : "View Household"}
            </Button>
            {showMembers ? (
              <>
                <HouseholdFinancialSummarySection householdId={household.id} profileId={profileId} />
                <Tabs defaultValue="members">
                  {/* Scrolls sideways on narrow screens so no section tab is clipped. */}
                  <div className="max-w-full overflow-x-auto">
                    <TabsList aria-label="Household sections">
                      <TabsTrigger value="members">Members</TabsTrigger>
                      {FINANCE_TABS.map((tab) => (
                        <TabsTrigger key={tab.resource} value={tab.resource}>
                          {tab.label}
                        </TabsTrigger>
                      ))}
                    </TabsList>
                  </div>
                  <TabsContent value="members" className="pt-4">
                    <HouseholdMembers householdId={household.id} profileId={profileId} canManage={membership.role === "primary"} />
                  </TabsContent>
                  {FINANCE_TABS.map((tab) => (
                    <TabsContent key={tab.resource} value={tab.resource} className="space-y-3 pt-4">
                      {tab.resource === "goals" ? (
                        <HouseholdGoalsEmergencyFundReference householdId={household.id} profileId={profileId} />
                      ) : null}
                      <HouseholdFinanceSection
                        resource={tab.resource}
                        householdId={household.id}
                        profileId={profileId}
                        canManage={membership.role === "primary"}
                      />
                    </TabsContent>
                  ))}
                </Tabs>
              </>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  )
}
