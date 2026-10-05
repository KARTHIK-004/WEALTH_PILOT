import { useEffect } from "react"
import { useLocation } from "react-router"

import { AiExplanationSection } from "@/components/home/ai-explanation-section"
import { DemoCtaSection } from "@/components/home/demo-cta-section"
import { FeaturesSection } from "@/components/home/features-section"
import { HeroSection } from "@/components/home/hero-section"
import { HomeFooter } from "@/components/home/home-footer"
import { HomeNavbar } from "@/components/home/home-navbar"
import { scrollToSection } from "@/components/home/section-nav"
import { HouseholdSection } from "@/components/home/household-section"
import { HowItWorksSection } from "@/components/home/how-it-works-section"

/**
 * The public landing page at `/`. Like `/login` and `/create-user` it is a
 * sibling of the protected route tree in `App.tsx` -- no `ProtectedRoute`,
 * no `AppShell`, no sidebar -- so it renders without signing in.
 *
 * Static by design: no API call, no customer context, no calculation. The
 * only numbers on the page are the hero preview's fixed sample values, each
 * labelled "Illustrative". The feature list names only capabilities the app
 * actually has.
 */
export function HomePage() {
  const { hash } = useLocation()
  // Arriving from another page via "/#features" etc.: scroll to that section.
  useEffect(() => {
    if (!hash) return
    const frame = window.requestAnimationFrame(() => scrollToSection(hash.slice(1)))
    return () => window.cancelAnimationFrame(frame)
  }, [hash])

  return (
    <div className="bg-background text-foreground flex min-h-svh flex-col">
      <a
        href="#main-content"
        className="bg-background focus-visible:ring-ring/50 sr-only z-50 rounded-md text-sm focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:border focus:px-3 focus:py-2 focus-visible:ring-3"
      >
        Skip to content
      </a>
      <HomeNavbar />
      <main id="main-content" className="flex-1">
        <HeroSection />
        <HowItWorksSection />
        <FeaturesSection />
        <AiExplanationSection />
        <HouseholdSection />
        <DemoCtaSection />
      </main>
      <HomeFooter />
    </div>
  )
}
