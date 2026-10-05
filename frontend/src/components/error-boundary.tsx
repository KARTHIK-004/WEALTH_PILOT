import { AlertTriangle } from "lucide-react"
import { Component, type ErrorInfo, type ReactNode } from "react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
}

/**
 * Top-level error boundary for unexpected UI failures (section 19). The
 * fallback is always this fixed, safe message — never the caught error's
 * own message or stack (React error info is logged to the console only,
 * for local debugging, exactly like any other dev-only console log; it
 * is never rendered).
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unexpected UI error", error, info)
  }

  private handleReload = () => {
    this.setState({ hasError: false })
    window.location.assign("/dashboard")
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-svh items-center justify-center p-6">
          <Alert variant="destructive" className="max-w-md">
            <AlertTriangle />
            <AlertTitle>Something went wrong</AlertTitle>
            <AlertDescription className="space-y-4">
              <p>
                An unexpected error occurred while rendering this page. No financial data was lost.
              </p>
              <Button variant="outline" size="sm" onClick={this.handleReload}>
                Return to dashboard
              </Button>
            </AlertDescription>
          </Alert>
        </div>
      )
    }
    return this.props.children
  }
}
