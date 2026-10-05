import { Sparkles, UserRound } from "lucide-react"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { useProfileQuery } from "@/hooks/use-profile"
import { isDemoCustomerId, isFamilyDemoCustomerId } from "@/lib/demo-customer"
import { useCustomer } from "@/providers/customer-context"

/**
 * Replaces the former `CustomerSelector` (a Dialog letting the user type
 * an arbitrary numeric profile id — "Select customer profile" / "Enter
 * the numeric id of an existing profile"). That UI existed only because a
 * regular Sign In previously left the active profile unresolved; now
 * every successful authentication (`login-form.tsx`'s `completeLogin`,
 * `create-user-page.tsx`'s `handleContinue`) deterministically sets the
 * active customer itself, so there is nothing left for a user to pick —
 * this component is a pure, read-only "who is logged in" indicator, not a
 * control, and contains no input of any kind (section 8/20: no
 * customer-switching UI anywhere in the authenticated shell).
 *
 * Shows "Demo Account" (icon + text, never color alone) when the active
 * profile is the Phase 24 canonical demo customer (`isDemoCustomerId`,
 * unchanged), or the real customer's own name (from the same
 * `useProfileQuery` every page already reads) otherwise — never a raw
 * "Profile #<id>" placeholder, and never a hard-coded label.
 *
 * The family demo's session reads "Family Demo" instead (ADR-036), so a
 * reviewer can always tell which of the two demo scenarios they are in. It is
 * a label only, derived from which demo login was used -- never a permission.
 */
export function AccountIdentity() {
  const { profileId } = useCustomer()
  const isDemo = isDemoCustomerId(profileId)
  const demoLabel = isFamilyDemoCustomerId(profileId) ? "Family Demo" : "Demo Account"
  const query = useProfileQuery(profileId)
  const label = isDemo ? demoLabel : (query.data?.name ?? "Account")

  return (
    <div className="flex items-center gap-2 px-1.5 py-1" aria-label={`Signed in as ${label}`}>
      <Avatar className="size-6">
        <AvatarFallback>
          <UserRound className="size-3.5" />
        </AvatarFallback>
      </Avatar>
      {isDemo ? (
        <Badge variant="secondary">
          <Sparkles />
          {demoLabel}
        </Badge>
      ) : (
        <span className="text-muted-foreground hidden max-w-32 truncate text-xs sm:inline">{label}</span>
      )}
    </div>
  )
}
