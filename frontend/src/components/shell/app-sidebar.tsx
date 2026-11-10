import { GraduationCap } from "lucide-react"
import { Link, useLocation } from "react-router"

import { NAV_GROUPS } from "@/components/shell/nav-items"
import { BEHAVIOUR_PAGE_PATH } from "@/lib/behaviour-summary"
import { DEMO_MODE_ALLOWED } from "@/lib/demo-build"
import { behaviourLinkTarget } from "@/lib/demo-mode"
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"

/**
 * The application's primary navigation — one entry per page
 * MASTER_PROMPT.md section 4 requires, nothing else (section 13: "Do not
 * create navigation links to pages that are not defined by the
 * authoritative project plan"). Built entirely from shadcn/ui's Sidebar
 * primitives, which already provide the responsive mobile behaviour
 * (a Sheet-based off-canvas panel below the `md` breakpoint) — no
 * separate mobile navigation system was built.
 *
 * Phase 25: items render in three labeled groups (`NAV_GROUPS` — Overview
 * / Customer / Analysis) instead of one flat list, for scannability in a
 * financial decision-support app; no route, label, icon, or page was
 * added, removed, or reordered relative to Phase 17-24.
 */
export function AppSidebar() {
  const location = useLocation()
  // On a phone the sidebar is an off-canvas sheet: choosing a page must close it, or it stays open over the page that was just opened.
  const { setOpenMobile } = useSidebar()
  const closeMobileSheet = () => setOpenMobile(false)

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              render={<Link to="/dashboard" />}
              onClick={closeMobileSheet}
              className="data-[slot=sidebar-menu-button]:!p-2"
            >
              <div className="bg-primary text-primary-foreground flex aspect-square size-8 items-center justify-center rounded-lg">
                <GraduationCap className="size-4" />
              </div>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-semibold">WealthPilot AI</span>
                <span className="text-muted-foreground truncate text-xs">
                  Decision-support prototype
                </span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        {NAV_GROUPS.map((group) => (
          <SidebarGroup key={group.label}>
            <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {group.items.map((item) => {
                  const isActive = location.pathname === item.url
                  return (
                    <SidebarMenuItem key={item.url}>
                      <SidebarMenuButton
                        isActive={isActive}
                        onClick={closeMobileSheet}
                        tooltip={item.title}
                        render={<Link to={item.url === BEHAVIOUR_PAGE_PATH ? behaviourLinkTarget(location.pathname, location.search, DEMO_MODE_ALLOWED) : item.url} aria-current={isActive ? "page" : undefined} />}
                      >
                        <item.icon />
                        <span>{item.title}</span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  )
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>
    </Sidebar>
  )
}
