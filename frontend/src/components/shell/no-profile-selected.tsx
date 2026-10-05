import { UserRoundSearch } from "lucide-react"
import { Link } from "react-router"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

/**
 * Shown by every protected page when no customer profile is in context
 * (section 44: "do not make arbitrary requests" when context is
 * unavailable — none of these pages fires an API call in this state).
 *
 * UX fix (post-Phase-25): every authenticated session now deterministically
 * associates a customer at login/account-creation time (`login-form.tsx`,
 * `create-user-page.tsx`), so reaching this component means that
 * association is genuinely missing — not that the user simply hasn't
 * picked one yet (there is no picker anymore). Copy and actions reflect
 * that: no numeric-id input, just a route back to the two places that
 * legitimately establish it. Never silently falls back to another
 * customer.
 */
export function NoProfileSelected() {
  return (
    <Card>
      <CardHeader>
        <div className="bg-muted text-muted-foreground mb-2 flex size-10 items-center justify-center rounded-lg">
          <UserRoundSearch className="size-5" />
        </div>
        <CardTitle>No customer profile associated with this account</CardTitle>
        <CardDescription>
          Your account is authenticated, but no customer profile is associated with it.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-2">
        <Button render={<Link to="/create-user" />}>Create Profile</Button>
        <Button variant="outline" render={<Link to="/login" />}>
          Return to Login
        </Button>
      </CardContent>
    </Card>
  )
}
