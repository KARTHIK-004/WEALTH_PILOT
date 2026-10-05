import { Navigate, Outlet, useLocation } from "react-router"

import { useAuth } from "@/providers/auth-context"

/**
 * Route guard for the Phase 20 prototype authentication gate. Renders the
 * protected subtree via `<Outlet />` when `isAuthenticated`; otherwise
 * redirects to `/login`, preserving the originally requested location in
 * router state so `LoginForm` can return the user there after a successful
 * demo login (section 17: direct URL access to a protected route while
 * logged out must redirect, not just hide a nav link).
 */
export function ProtectedRoute() {
  const { isAuthenticated } = useAuth()
  const location = useLocation()

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <Outlet />
}
