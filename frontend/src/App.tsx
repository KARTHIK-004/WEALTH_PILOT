import { Route, Routes } from "react-router"

import { AppShell } from "@/components/shell/app-shell"
import { ProtectedRoute } from "@/components/shell/protected-route"
import { AboutPage } from "@/pages/about-page"
import { AgentActivityPage } from "@/pages/agent-activity-page"
import { CreateUserPage } from "@/pages/create-user-page"
import { DashboardPage } from "@/pages/dashboard-page"
import { FinancialHealthPage } from "@/pages/financial-health-page"
import { GoalsPage } from "@/pages/goals-page"
import { HomePage } from "@/pages/home-page"
import { LoginPage } from "@/pages/login-page"
import { NotFoundPage } from "@/pages/not-found-page"
import { OnboardingGoalsPage } from "@/pages/onboarding-goals-page"
import { OnboardingQuestionnairePage } from "@/pages/onboarding-questionnaire-page"
import { PortfolioPage } from "@/pages/portfolio-page"
import { ProfilePage } from "@/pages/profile-page"
import { RecommendationPage } from "@/pages/recommendation-page"
import { RiskAssessmentPage } from "@/pages/risk-assessment-page"
import { ScenarioSimulatorPage } from "@/pages/scenario-simulator-page"
import { WhyThisRecommendationPage } from "@/pages/why-this-recommendation-page"

/**
 * `/about` is the public About This Project page (`pages/about-page.tsx`),
 * static like Home.
 *
 * `/` is the public Home page (`pages/home-page.tsx`): static, no API call,
 * outside both `ProtectedRoute` and `AppShell`. The Dashboard lives at
 * `/dashboard` and is the default post-login destination.
 *
 * Route definitions: the ten sidebar pages (Dashboard, Customer Profile,
 * Risk Assessment, Financial Health, Goals, Portfolio Analysis, AI
 * Recommendation, Why This Recommendation, Agent Activity, Scenario
 * Simulator — see `components/shell/nav-items.ts`), all real pages reading
 * live API data.
 *
 * `/login` and `/create-user` are public siblings of the protected tree,
 * never nested inside `AppShell` — neither renders a sidebar/header.
 * `/create-user` is deliberately NOT behind `ProtectedRoute`: it is reachable
 * directly from the (unauthenticated) Login page as a path parallel to Demo
 * Account (see `pages/create-user-page.tsx`'s own docstring and
 * `reports/phase21_create_user_report.md`). Every other route is wrapped in
 * `ProtectedRoute`, which redirects to `/login` when the prototype auth
 * state is not authenticated — a route guard, not just a hidden nav link.
 *
 * `/onboarding/questionnaire` and `/onboarding/goals` sit INSIDE
 * `ProtectedRoute` but, like `/login` and `/create-user`, outside
 * `AppShell` (standalone, no sidebar). They operate on whatever profile
 * `customer-context.tsx` currently holds — the one the authenticated session
 * deterministically resolved at login or account-creation time, never a
 * manually picked one. They are reached from the create-user flow and, for an
 * existing profile, from the Questionnaire card on the Customer Profile page.
 */
function App() {
  return (
    <Routes>
      <Route index element={<HomePage />} />
      <Route path="about" element={<AboutPage />} />
      <Route path="login" element={<LoginPage />} />
      <Route path="create-user" element={<CreateUserPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="onboarding/questionnaire" element={<OnboardingQuestionnairePage />} />
        <Route path="onboarding/goals" element={<OnboardingGoalsPage />} />
        <Route element={<AppShell />}>
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="risk-assessment" element={<RiskAssessmentPage />} />
          <Route path="financial-health" element={<FinancialHealthPage />} />
          <Route path="goals" element={<GoalsPage />} />
          <Route path="portfolio" element={<PortfolioPage />} />
          <Route path="recommendation" element={<RecommendationPage />} />
          <Route path="why-this-recommendation" element={<WhyThisRecommendationPage />} />
          <Route path="agent-activity" element={<AgentActivityPage />} />
          <Route path="scenarios" element={<ScenarioSimulatorPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  )
}

export default App
