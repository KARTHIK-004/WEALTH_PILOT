import { Link, useLocation } from "react-router"

import { DemoFinancialBehaviourCard } from "@/components/financial-health/demo-financial-behaviour-card"
import { DEMO_PAGE_DESCRIPTION } from "@/components/financial-health/demo-financial-behaviour"
import { DemoFamilyCard } from "@/components/financial-health/demo-family-behaviour-card"
import { DemoRequestNotice } from "@/components/financial-health/demo-request-notice"
import { FAMILY_PAGE_DESCRIPTION } from "@/components/financial-health/demo-family-behaviour"
import { FinancialBehaviourReal } from "@/components/financial-health/financial-behaviour-real"
import { BEHAVIOUR_DESCRIPTION } from "@/components/financial-health/behaviour-sentiment-view"
import { NoProfileSelected } from "@/components/shell/no-profile-selected"
import { PageContainer } from "@/components/shell/page-container"
import { DEMO_MODE_ALLOWED } from "@/lib/demo-build"
import { demoRequest, type DemoProblem } from "@/lib/demo-mode"
import { useCustomer } from "@/providers/customer-context"

export const BEHAVIOUR_PAGE_TITLE = "Financial Behaviour & Sentiment"

/**
 * The page content for one profile. Keyed by profile so that a different profile starts with an empty box and no earlier response: the typed text lives only in the card's component
 * state and the response only in the in-memory query cache, which is dropped as soon as the card unmounts (`hooks/use-personalized-insight.ts`). Nothing is written to browser storage.
 */
export function FinancialBehaviourContent({ profileId, demoProblem = null, demoHint = false }: { profileId: number; demoProblem?: DemoProblem | null; demoHint?: boolean }) {
  return (
    <PageContainer title={BEHAVIOUR_PAGE_TITLE} description={BEHAVIOUR_DESCRIPTION}>
      {demoProblem ? <DemoRequestNotice problem={demoProblem} /> : null}
      <FinancialBehaviourReal key={profileId} profileId={profileId} demoHint={demoHint} />
      <p className="text-muted-foreground text-sm">
        Your risk assessment stays the authority on your risk profile. See the short summary on{" "}
        <Link to="/financial-health" className="text-primary underline underline-offset-2">
          Financial Health
        </Link>
        .
      </p>
    </PageContainer>
  )
}

/** The demonstration body: FICTIONAL months from the backend's demo route. It needs no profile (it is nobody's record) and never reads or writes a customer. */
export function FinancialBehaviourDemoContent() {
  return (
    <PageContainer title={BEHAVIOUR_PAGE_TITLE} description={DEMO_PAGE_DESCRIPTION}>
      <DemoFinancialBehaviourCard />
    </PageContainer>
  )
}

/** The family demonstration body: a FICTIONAL family (three members and a household) from the backend's demo route. It needs no profile and never reads or writes a customer. */
export function FinancialBehaviourFamilyDemoContent() {
  return (
    <PageContainer title={BEHAVIOUR_PAGE_TITLE} description={FAMILY_PAGE_DESCRIPTION}>
      <DemoFamilyCard />
    </PageContainer>
  )
}

/**
 * "Financial Behaviour & Sentiment" -- the dedicated home of the detailed behaviour findings, the optional text box, the reading of the user's words, its limitations and the conflict
 * display (ADR-043). DISPLAY ONLY: every number and sentence comes from `POST /api/profiles/{id}/personalized-insights`; the page never calculates a figure or changes a risk profile.
 *
 * Demonstration mode (development only): with `?demo=true` on a build that allows it (`DEMO_MODE_ALLOWED`) the page shows fictional, fixed demonstration data from
 * `POST /api/demo/financial-behaviour` instead. Without the query, or on a build that does not allow it, nothing changes: no profile shows "no profile selected", a profile with no records
 * shows the empty state, and an unreachable backend shows "Service unavailable". Demo data is never substituted for any of those.
 */
export function FinancialBehaviourPage({ allowDemo = DEMO_MODE_ALLOWED }: { allowDemo?: boolean } = {}) {
  const { profileId } = useCustomer()
  const { search } = useLocation()
  const { kind, problem } = demoRequest(search, allowDemo)
  if (kind === "family") return <FinancialBehaviourFamilyDemoContent />
  if (kind === "individual") return <FinancialBehaviourDemoContent />
  if (profileId === null) {
    return (
      <PageContainer title={BEHAVIOUR_PAGE_TITLE} description={BEHAVIOUR_DESCRIPTION}>
        {problem ? <DemoRequestNotice problem={problem} /> : null}
        <NoProfileSelected />
      </PageContainer>
    )
  }
  return <FinancialBehaviourContent profileId={profileId} demoProblem={problem} demoHint={allowDemo} />
}
