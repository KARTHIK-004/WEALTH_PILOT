/**
 * Component cases for the "Data Protection" page, rendered to static HTML with react-dom/server through Vite's SSR loader (see tests/component.test.mjs; `npm test`). No browser,
 * no DOM library, no new dependency.
 *
 * Every response rendered here is a REAL backend response captured by `scripts/export_security_fixtures.py` from the actual route (the real encryption service and audit-chain verifier
 * on a throwaway SQLite file); `tests/backend/security/test_status_fixtures.py` fails if a fixture drifts from the backend. Assertions compare what is shown with the values IN the response, so a
 * swallowed state, an invented "verified" or a result shown after a failure makes a case fail.
 */
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import path from "node:path"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { renderToStaticMarkup } from "react-dom/server"
import { MemoryRouter } from "react-router"

import { SecurityStatusCard, SecurityStatusView, type SecurityStatusViewProps } from "@/components/security/security-status-card"
import { ApiClientError, ApiUnreachableError } from "@/lib/api-client"
import { SecurityStatusContent, SecurityStatusPage } from "@/pages/security-status-page"
import { CustomerProvider } from "@/providers/customer-context"
import type { components } from "@/types/api"

type Status = components["schemas"]["SecurityStatusOut"]

function fixture(name: string): Status {
  return JSON.parse(readFileSync(path.resolve(process.cwd(), "tests", "fixtures", `${name}.json`), "utf8")) as Status
}

const noop = () => {}
const view = (over: Partial<SecurityStatusViewProps> = {}): string =>
  renderToStaticMarkup(<SecurityStatusView data={undefined} loading={false} error={null} onRetry={noop} {...over} />)

/** Visible text: tags removed, common entities decoded, whitespace collapsed. */
function textOf(markup: string): string {
  return markup
    .replace(/<[^>]*>/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#x27;|&#39;/g, "'")
    .replace(/\s+/g, " ")
}

/** The status badges' text, in order: [encryption, audit chain, external ledger]. The verdict lives in these, not in the explanatory sentences around them. */
function badgesOf(markup: string): string[] {
  return [...markup.matchAll(/data-slot="badge"[^>]*>([^<]*)</g)].map((m) => m[1])
}

const seeded = (profileId: number, name: string): QueryClient => {
  const client = new QueryClient()
  client.setQueryData(["security-status", profileId], fixture(name))
  return client
}

export const cases: Record<string, () => void | Promise<void>> = {
  "operational: shows the prototype label exactly, the encryption result, the chain result and the backend's own counts"() {
    const data = fixture("security-operational")
    const text = textOf(view({ data }))
    assert.equal(data.prototype_notice, "Academic prototype — not a real blockchain.")
    assert.ok(text.includes("Academic prototype — not a real blockchain."))
    assert.deepEqual(badgesOf(view({ data })), ["Operating", "Internally consistent", "Not configured"])
    assert.match(text, /AES-256-GCM/)
    assert.match(text, /Self-test: passed/)
    assert.match(text, new RegExp(`Events checked: ${data.ledger.events_checked}\\b`))
    assert.match(text, new RegExp(`Protected notes saved for this profile: ${data.protected_note_count}\\b`))
    assert.match(text, /Off-chain, in the private application database\./)
    assert.doesNotMatch(text, /Verification failed|Self-test failed|Not configured\s+No usable/)
  },

  "operational: the chain note says consistency is not proof of no tampering"() {
    const data = fixture("security-operational")
    assert.match(textOf(view({ data })), /does not prove the database was never tampered with/)
  },

  "existing data: states that older records are not encrypted and lists every category the backend names"() {
    const data = fixture("security-operational")
    const text = textOf(view({ data }))
    assert.equal(data.existing_data.encrypted, false)
    assert.match(text, /Existing data is not encrypted/)
    assert.ok(data.existing_data.unprotected_categories.length >= 4)
    for (const category of data.existing_data.unprotected_categories) assert.ok(text.includes(category), category)
    assert.ok(text.includes(data.existing_data.note))
  },

  "limitations: every limitation the backend lists is shown, including the asserted-identity one"() {
    const data = fixture("security-operational")
    const text = textOf(view({ data }))
    for (const limitation of data.limitations) assert.ok(text.includes(limitation), limitation)
    assert.match(text, /Identity is asserted by the client/)
  },

  "external ledger: shown as not configured with the backend's detail, never as connected"() {
    const data = fixture("security-operational")
    const text = textOf(view({ data }))
    assert.equal(data.external_anchor.state, "not_configured")
    assert.match(text, /External ledger/)
    assert.ok(text.includes(data.external_anchor.detail))
    assert.doesNotMatch(text, /Available|Connected|Anchored|Confirmed/)
  },

  "honest wording: the page says what the audit trail is not, and makes no unqualified blockchain, decentralization or immutability claim"() {
    const text = textOf(view({ data: fixture("security-operational") }))
    assert.match(text, /not decentralized, has no consensus, and is not independently tamper-proof/)
    assert.doesNotMatch(text.replace(/not decentralized/g, "").replace(/no consensus/g, ""), /decentrali[sz]ed|consensus|immutable|production-ready|compliant|certified/i)
  },

  "empty ledger: says no events yet, never 'internally consistent'"() {
    const data = fixture("security-empty-ledger")
    assert.equal(data.ledger.verification, "empty")
    const text = textOf(view({ data }))
    assert.deepEqual(badgesOf(view({ data })), ["Operating", "No events recorded yet", "Not configured"])
    assert.match(text, /Events checked: 0\b/)
  },

  "no key configured: encryption is shown as not configured with the backend's reason, and no self-test line"() {
    const data = fixture("security-not-configured")
    assert.equal(data.encryption.self_test_passed, null)
    const text = textOf(view({ data }))
    assert.deepEqual(badgesOf(view({ data })).slice(0, 2), ["Not configured", "No events recorded yet"])
    assert.ok(text.includes(data.encryption.unavailable_reason as string))
    assert.doesNotMatch(text, /Self-test:|Operating/)
  },

  "failed encryption self-test: shown as failed with the backend's reason and a failed self-test line, never as operating"() {
    const data = fixture("security-self-test-failed")
    assert.equal(data.encryption.status, "failed")
    assert.equal(data.encryption.self_test_passed, false)
    const markup = view({ data })
    const text = textOf(markup)
    assert.deepEqual(badgesOf(markup).slice(0, 1), ["Self-test failed"])
    assert.match(text, /Self-test: failed/)
    assert.ok(text.includes(data.encryption.unavailable_reason as string))
    assert.doesNotMatch(text, /Operating|Self-test: passed/)
    assert.match(markup, /bg-destructive/)
  },

  "failed chain verification: shows the failing event number and the backend's non-sensitive reason, and not 'consistent'"() {
    const data = fixture("security-ledger-invalid")
    assert.equal(data.ledger.verification, "invalid")
    const markup = view({ data })
    const text = textOf(markup)
    assert.deepEqual(badgesOf(markup), ["Operating", "Verification failed", "Not configured"])
    assert.match(text, new RegExp(`First failing event: #${data.ledger.first_invalid_sequence}\\b`))
    assert.ok(text.includes(data.ledger.reason as string))
    assert.match(markup, /bg-destructive/) // the failure is visually distinct, not only worded
  },

  "nothing in the markup looks like a hash, a key, an identifier or note text"() {
    for (const name of ["security-operational", "security-empty-ledger", "security-not-configured", "security-ledger-invalid"]) {
      const markup = view({ data: fixture(name) })
      assert.doesNotMatch(markup, /[0-9a-f]{64}/i, name)
      assert.doesNotMatch(markup, /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i, name)
      assert.doesNotMatch(markup, /[A-Za-z0-9+/]{43}=/, name)
    }
  },

  "loading: a busy status with no result wording"() {
    const markup = view({ loading: true })
    const text = textOf(markup)
    assert.match(markup, /role="status"/)
    assert.match(text, /Running the security checks…/)
    assert.doesNotMatch(text, /Operating|Internally consistent|Self-test|Existing data/)
  },

  "error: replaces the result, offers a retry, and never shows earlier data beside it"() {
    for (const error of [new ApiUnreachableError(new Error("down")), new ApiClientError({ type: "about:blank", title: "Access denied", status: 403, detail: "no" })]) {
      const text = textOf(view({ data: fixture("security-operational"), error }))
      assert.match(text, /Try again/)
      assert.doesNotMatch(text, /Operating|Internally consistent|Protected notes saved/)
    }
  },

  "a 503 from the backend is shown with the backend's own sentence, not as a failed analysis, and nothing else is shown"() {
    const detail = "Protected storage is not set up on this database: the migration that creates its tables has not been applied. Nothing was read or saved."
    const error = new ApiClientError({ type: "about:blank", title: "Service unavailable", status: 503, detail })
    const markup = view({ data: fixture("security-operational"), error })
    const text = textOf(markup)
    assert.match(text, /Protection status is not available/)
    assert.ok(text.includes(detail))
    assert.match(text, /Try again/)
    assert.doesNotMatch(text, /analysis|Operating|Internally consistent|Protected notes saved/)
    assert.match(markup, /role="alert"/)
  },

  "any other API error keeps the shared plain-language message"() {
    const text = textOf(view({ error: new ApiClientError({ type: "about:blank", title: "Internal server error", status: 500, detail: "An unexpected error occurred." }) }))
    assert.match(text, /Something went wrong on our side/)
    assert.doesNotMatch(text, /Protection status is not available/)
  },

  "card: renders the cached backend response for its profile, and shows loading (never a result) before data arrives"() {
    const render = (client: QueryClient) =>
      textOf(
        renderToStaticMarkup(
          <MemoryRouter>
            <QueryClientProvider client={client}>
              <SecurityStatusCard profileId={2} />
            </QueryClientProvider>
          </MemoryRouter>,
        ),
      )
    assert.match(render(seeded(2, "security-operational")), /Internally consistent/)
    const empty = render(new QueryClient())
    assert.match(empty, /Running the security checks…/)
    assert.doesNotMatch(empty, /Operating|Internally consistent/)
  },

  "page: one level-one heading, and each profile shows only its own cached result"() {
    const client = seeded(2, "security-operational")
    client.setQueryData(["security-status", 3], fixture("security-not-configured"))
    const render = (id: number) =>
      renderToStaticMarkup(
        <MemoryRouter>
          <QueryClientProvider client={client}>
            <SecurityStatusContent profileId={id} />
          </QueryClientProvider>
        </MemoryRouter>,
      )
    const two = render(2)
    assert.equal((two.match(/<h1\b/g) ?? []).length, 1)
    assert.match(/<h1[^>]*>(.*?)<\/h1>/s.exec(two)?.[1] ?? "", /Data Protection/)
    assert.match(textOf(two), /Operating/)
    const three = textOf(render(3))
    assert.match(three, /Not configured/)
    assert.doesNotMatch(three, /Operating/)
    assert.doesNotMatch(textOf(render(9)), /Operating|Not configured\s+No usable/) // no cache for 9: loading, not borrowed data
  },

  "page: without a profile it shows the standard no-profile prompt and no result"() {
    const markup = renderToStaticMarkup(
      <MemoryRouter>
        <QueryClientProvider client={new QueryClient()}>
          <CustomerProvider>
            <SecurityStatusPage />
          </CustomerProvider>
        </QueryClientProvider>
      </MemoryRouter>,
    )
    const text = textOf(markup)
    assert.match(text, /Data Protection/)
    assert.match(text, /Create Profile/)
    assert.doesNotMatch(text, /Operating|Internally consistent|Existing data is not encrypted/)
  },
}
