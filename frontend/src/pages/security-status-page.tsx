import { SecurityStatusCard } from "@/components/security/security-status-card"
import { NoProfileSelected } from "@/components/shell/no-profile-selected"
import { PageContainer } from "@/components/shell/page-container"
import { SECURITY_DESCRIPTION } from "@/lib/security-status-labels"
import { useCustomer } from "@/providers/customer-context"

export const SECURITY_PAGE_TITLE = "Data Protection"

/** The page content for one profile. Keyed by profile so a different profile never shows an earlier profile's result. */
export function SecurityStatusContent({ profileId }: { profileId: number }) {
  return (
    <PageContainer title={SECURITY_PAGE_TITLE} description={SECURITY_DESCRIPTION}>
      <SecurityStatusCard key={profileId} profileId={profileId} />
    </PageContainer>
  )
}

/**
 * "Data Protection" -- the backend's own report on encryption of protected notes and verification of the local audit chain (ADR-047). DISPLAY ONLY: the page runs no check,
 * computes nothing and never shows a result the backend did not return.
 */
export function SecurityStatusPage() {
  const { profileId } = useCustomer()
  if (profileId === null) {
    return (
      <PageContainer title={SECURITY_PAGE_TITLE} description={SECURITY_DESCRIPTION}>
        <NoProfileSelected />
      </PageContainer>
    )
  }
  return <SecurityStatusContent profileId={profileId} />
}
