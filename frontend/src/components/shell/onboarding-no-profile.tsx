import { UserRoundSearch } from "lucide-react"
import { Link } from "react-router"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

/**
 * The onboarding-page equivalent of `no-profile-selected.tsx` (section 6:
 * "If no active profile exists: show a clear empty state, provide a route
 * back to Create User or Login as appropriate. Do not silently use
 * another customer."). Not a reuse of `NoProfileSelected` because that
 * component's copy assumes the `AppShell` header is visible -- it never
 * is on these standalone onboarding pages. Neither component offers a
 * manual customer-id picker (removed post-Phase-25) -- every
 * authenticated session resolves its customer automatically at login/
 * account-creation time, so this state means that association is
 * genuinely missing, not merely unchosen.
 */
export function OnboardingNoProfile() {
  return (
    <Card>
      <CardHeader>
        <div className="bg-muted text-muted-foreground mb-2 flex size-10 items-center justify-center rounded-lg">
          <UserRoundSearch className="size-5" />
        </div>
        <CardTitle>No active profile</CardTitle>
        <CardDescription>
          This step needs an active WealthPilot profile. Create a new one, or log in with
          an existing account.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-2">
        <Button render={<Link to="/create-user" />}>Create New User</Button>
        <Button variant="outline" render={<Link to="/login" />}>
          Back to Login
        </Button>
      </CardContent>
    </Card>
  )
}
