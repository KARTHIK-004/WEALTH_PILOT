import { Outlet } from "react-router"

import { AppSidebar } from "@/components/shell/app-sidebar"
import { Header } from "@/components/shell/header"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"

/**
 * The application shell: sidebar navigation + header + main content
 * region (routed pages render via `<Outlet />`).
 * Everything below the header is Phase 17/18's responsibility — this
 * component only establishes the persistent structure around it.
 */
export function AppShell() {
  return (
    <SidebarProvider>
      <a
        href="#main-content"
        className="bg-background text-foreground focus-visible:ring-ring sr-only z-50 rounded-md border px-4 py-2 text-sm focus-visible:not-sr-only focus-visible:fixed focus-visible:top-4 focus-visible:left-4 focus-visible:ring-2"
      >
        Skip to main content
      </a>
      <AppSidebar />
      <SidebarInset className="min-w-0">
        <Header />
        <main id="main-content" tabIndex={-1} className="flex flex-1 flex-col">
          <Outlet />
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
