/**
 * PROTOTYPE AUTHENTICATION ONLY -- Phase 20.
 *
 * WealthPilot AI has no backend identity/authentication system: Phase 20
 * inspected `backend/wealthpilot` for a `User` model, password hashing,
 * token/session infrastructure, and any `/api/auth`-style route, and found
 * none. Per this phase's own instructions, no production-grade
 * authentication backend was invented to fill that gap. This module exists
 * ONLY to gate entry into the demo application for a viva/presentation --
 * it is NOT secure, NOT production authentication, and must never be
 * described as either. There is no password hashing, no token, no
 * server-side session, and no encryption: the "authenticated" flag this
 * module backs (see `providers/auth-context.tsx`) is a plain localStorage
 * marker that anyone with browser devtools can set directly, and the demo
 * password below is compared as a literal string on the client.
 *
 * The single demo credential is intentionally public -- it is displayed
 * directly on the login page for viva convenience -- and must never be
 * treated as a real secret. No real personal credential may ever be added
 * to this file.
 */

export const DEMO_EMAIL = "demo@wealthpilot.ai"
export const DEMO_PASSWORD = "WealthPilotDemo@2026"

export function isValidPrototypeCredential(email: string, password: string): boolean {
  return email.trim().toLowerCase() === DEMO_EMAIL && password === DEMO_PASSWORD
}
