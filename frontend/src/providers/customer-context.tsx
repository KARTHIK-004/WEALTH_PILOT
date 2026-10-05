import { createContext, useContext, useMemo, useState, type ReactNode } from "react"

interface CustomerContextValue {
  profileId: number | null
  setProfileId: (id: number | null) => void
}

const CustomerContext = createContext<CustomerContextValue | null>(null)
const STORAGE_KEY = "wealthpilot-profile-id"

function readStoredProfileId(): number | null {
  if (typeof window === "undefined") return null
  const raw = window.localStorage.getItem(STORAGE_KEY)
  if (!raw) return null
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

/**
 * The minimum customer-context mechanism every protected page needs
 * (section 9): a single active `profileId`, persisted to `localStorage`
 * so it survives navigation and reloads. No backend change was required
 * or made — there is no "list customers" endpoint, so this never attempts
 * a customer picker/search.
 *
 * UX fix (post-Phase-25): `setProfileId` is no longer exposed to the user
 * through any UI control (the former `CustomerSelector` header dialog is
 * removed) — it is called ONLY by the deterministic authentication flows
 * that establish an account's associated customer (`login-form.tsx`'s
 * `completeLogin`, `create-user-page.tsx`'s `handleContinue`, and
 * `header.tsx`'s sign-out, which clears it). Every protected page reads
 * this SAME context, so they always agree on which customer they're
 * showing, and none of them can independently change it.
 */
export function CustomerProvider({ children }: { children: ReactNode }) {
  const [profileId, setProfileIdState] = useState<number | null>(readStoredProfileId)

  const setProfileId = (id: number | null) => {
    if (id === null) {
      window.localStorage.removeItem(STORAGE_KEY)
    } else {
      window.localStorage.setItem(STORAGE_KEY, String(id))
    }
    setProfileIdState(id)
  }

  const value = useMemo(() => ({ profileId, setProfileId }), [profileId])

  return <CustomerContext.Provider value={value}>{children}</CustomerContext.Provider>
}

export function useCustomer(): CustomerContextValue {
  const context = useContext(CustomerContext)
  if (!context) throw new Error("useCustomer must be used within a CustomerProvider.")
  return context
}
