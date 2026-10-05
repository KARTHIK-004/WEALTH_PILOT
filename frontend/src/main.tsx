import { QueryClientProvider } from "@tanstack/react-query"
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router"

import App from "@/App.tsx"
import { ErrorBoundary } from "@/components/error-boundary"
import { TooltipProvider } from "@/components/ui/tooltip"
import "@/index.css"
import { queryClient } from "@/lib/query-client"
import { AuthProvider } from "@/providers/auth-context"
import { CustomerProvider } from "@/providers/customer-context"
import { ThemeProvider } from "@/providers/theme-provider"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <CustomerProvider>
              <TooltipProvider>
                <BrowserRouter>
                  <App />
                </BrowserRouter>
              </TooltipProvider>
            </CustomerProvider>
          </AuthProvider>
        </QueryClientProvider>
      </ThemeProvider>
    </ErrorBoundary>
  </StrictMode>,
)
