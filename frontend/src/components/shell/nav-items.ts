import type { LucideIcon } from "lucide-react"
import {
  Activity,
  FlaskConical,
  Gauge,
  HeartPulse,
  Info,
  LayoutDashboard,
  Lightbulb,
  PieChart,
  ShieldQuestion,
  Target,
  UserRound,
} from "lucide-react"

/**
 * MASTER_PROMPT.md section 4 / BUILD_PLAN.md section 13 name nine pages;
 * Phase 17's own prompt additionally requires a dedicated "Goals" page
 * (its sections 22-25 give it a full, unambiguous specification) that
 * isn't among the original nine, and orders the five pages it assigns to
 * this phase as Dashboard, Customer Profile, Risk Assessment, Financial
 * Health, Goals — followed here for both the addition and the order,
 * per section 1's own instruction to follow the CURRENT authoritative
 * instruction's terminology where it's more specific than the earlier
 * docs (Goals covers Phase 7's goal-engine output, genuinely distinct
 * from Financial Health's Phase 5 expense-persona/behaviour data).
 */
export interface NavItem {
  title: string
  url: string
  icon: LucideIcon
}

export interface NavGroup {
  label: string
  items: NavItem[]
}

/**
 * Phase 25: grouped for the sidebar (`AppSidebar`) into the three logical
 * sections this phase's own brief suggests — Overview / Customer /
 * Analysis — a purely presentational grouping; every route, label, icon,
 * and page-to-nav-item mapping is byte-for-byte unchanged from Phase 17.
 * `NAV_ITEMS` (below) is derived from this and stays a flat list in the
 * same order, so `Header.tsx`'s `NAV_ITEMS.find(...)` lookup is
 * unaffected.
 */
export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Overview",
    items: [{ title: "Dashboard", url: "/dashboard", icon: LayoutDashboard }],
  },
  {
    label: "Customer",
    items: [
      { title: "Customer Profile", url: "/profile", icon: UserRound },
      { title: "Risk Assessment", url: "/risk-assessment", icon: Gauge },
      { title: "Financial Health", url: "/financial-health", icon: HeartPulse },
      { title: "Goals", url: "/goals", icon: Target },
    ],
  },
  {
    label: "Analysis",
    items: [
      { title: "Portfolio Analysis", url: "/portfolio", icon: PieChart },
      { title: "AI Recommendation", url: "/recommendation", icon: Lightbulb },
      { title: "Why This Recommendation?", url: "/why-this-recommendation", icon: ShieldQuestion },
      { title: "Agent Activity", url: "/agent-activity", icon: Activity },
      { title: "Scenario Simulator", url: "/scenarios", icon: FlaskConical },
    ],
  },
  {
    // Public page (outside AppShell): explains the project itself, not a customer.
    label: "Project",
    items: [{ title: "About This Project", url: "/about", icon: Info }],
  },
]

export const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((group) => group.items)
