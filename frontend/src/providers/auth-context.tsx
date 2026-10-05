import { createContext, useContext, useMemo, useState, type ReactNode } from "react"

import { isValidPrototypeCredential } from "@/lib/prototype-auth"

const STORAGE_KEY = "wealthpilot-prototype-authenticated"

interface AuthContextValue {
  isAuthenticated: boolean
  login: (email: string, password: string) => boolean
  logout: () => void
  grantSessionAfterProfileCreation: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

function readStoredAuth(): boolean {
  if (typeof window === "undefined") return false
  return window.localStorage.getItem(STORAGE_KEY) === "true"
}

/**
 * PROTOTYPE AUTHENTICATION ONLY (see `lib/prototype-auth.ts` for why no
 * real backend-verified session exists). Gates entry into the application
 * for demonstration purposes -- `login` only ever compares against the
 * single hard-coded demo credential, never calls the backend, and never
 * stores a real password. Persisted to `localStorage` using the same
 * mechanism `customer-context.tsx` already uses for the active profile id,
 * purely so a page reload during a live demo does not force a re-login;
 * this is not a real session (no token, no expiry, no server-side check).
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(readStoredAuth)

  const login = (email: string, password: string): boolean => {
    if (!isValidPrototypeCredential(email, password)) return false
    window.localStorage.setItem(STORAGE_KEY, "true")
    setIsAuthenticated(true)
    return true
  }

  const logout = () => {
    window.localStorage.removeItem(STORAGE_KEY)
    setIsAuthenticated(false)
  }

  /**
   * Phase 21 (Create New User): `/create-user` is a public route, reachable
   * without a prior demo login (BUILD_PLAN.md's "public registration"
   * exception -- see `pages/create-user-page.tsx`). This grants the SAME
   * prototype session `login`/`logout` already manage -- same storage key,
   * same non-real-session caveats -- for the ONE legitimate case where a
   * session should start without the demo credential: immediately after a
   * genuine, backend-confirmed `POST /api/profiles` success. It is never
   * called from the login form itself, and never bypasses credential
   * checking for the demo-account path.
   */
  const grantSessionAfterProfileCreation = () => {
    window.localStorage.setItem(STORAGE_KEY, "true")
    setIsAuthenticated(true)
  }

  const value = useMemo(
    () => ({ isAuthenticated, login, logout, grantSessionAfterProfileCreation }),
    [isAuthenticated],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error("useAuth must be used within an AuthProvider.")
  return context
}
