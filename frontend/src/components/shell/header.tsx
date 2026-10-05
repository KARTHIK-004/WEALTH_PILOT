import { LogOut } from "lucide-react"
import { useLocation, useNavigate } from "react-router"

import { AccountIdentity } from "@/components/shell/account-identity"
import { NAV_ITEMS } from "@/components/shell/nav-items"
import { ThemeToggle } from "@/components/shell/theme-toggle"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { useAuth } from "@/providers/auth-context"
import { useCustomer } from "@/providers/customer-context"

export function Header() {
  const location = useLocation()
  const navigate = useNavigate()
  const { logout } = useAuth()
  const { setProfileId } = useCustomer()
  const current = NAV_ITEMS.find((item) => item.url === location.pathname)

  const handleSignOut = () => {
    // Prototype sign-out only (Phase 20): clears the local auth flag AND
    // the active-customer association (UX fix: "after logout ... the
    // associated customer ID is cleared" -- previously only the auth flag
    // was cleared here, leaving a stale profile id in localStorage until
    // the next login silently overwrote it). Never touches customer
    // records, analysis results, or any database data -- `setProfileId`
    // only clears which LOCAL browser tab currently treats which customer
    // as active.
    logout()
    setProfileId(null)
    navigate("/login", { replace: true })
  }

  return (
    <header className="bg-background/95 supports-[backdrop-filter]:bg-background/60 sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b px-4 backdrop-blur">
      <SidebarTrigger className="-ml-1" aria-label="Toggle navigation" />
      <Separator orientation="vertical" className="mr-2 h-4" />
      {/* A page-level `<h1>` (PageContainer's own heading) provides the
          real heading hierarchy start; this is a non-heading location
          label so each page has exactly one h1, not two. */}
      <p className="text-muted-foreground min-w-0 truncate text-sm font-medium">
        {current?.title ?? "WealthPilot AI"}
      </p>
      <div className="ml-auto flex items-center gap-2">
        <ThemeToggle />
        <Separator orientation="vertical" className="h-4" />
        <AccountIdentity />
        <Button variant="ghost" size="sm" onClick={handleSignOut} aria-label="Sign out">
          <LogOut />
          <span className="hidden sm:inline">Sign out</span>
        </Button>
      </div>
    </header>
  )
}
