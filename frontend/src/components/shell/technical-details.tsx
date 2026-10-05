import { ChevronRight } from "lucide-react"
import { Fragment, type ReactNode } from "react"

import { cn } from "cn"

export interface TechnicalItem {
  label: string
  value: ReactNode
}

/**
 * Collapsed-by-default "Technical details" (`docs/DESIGN.md` section 30):
 * the raw API value, method name, ticker, rule id or version behind a
 * plain-language label. A native `<details>`/`<summary>`, so it is keyboard
 * operable (Enter/Space) and announced as expandable without any script.
 *
 * Items render as a two-column definition list -- label and value are
 * always separate elements, so values can never run together ("Model
 * v1models/risk"). A `null`/`undefined` value is shown as "Not provided",
 * never dropped and never shown as 0.
 */
export function TechnicalDetails({
  items,
  children,
  title = "Technical details",
  className,
}: {
  items?: TechnicalItem[]
  children?: ReactNode
  title?: string
  className?: string
}) {
  return (
    <details className={cn("group rounded-md border text-xs", className)}>
      <summary className="text-muted-foreground hover:text-foreground focus-visible:ring-ring/50 flex cursor-pointer list-none items-center gap-1.5 rounded-md px-3 py-2 outline-none select-none focus-visible:ring-3 [&::-webkit-details-marker]:hidden">
        <ChevronRight className="size-3.5 shrink-0 transition-transform group-open:rotate-90" aria-hidden="true" />
        {title}
      </summary>
      <div className="space-y-2 border-t px-3 py-2">
        {items && items.length > 0 ? (
          <dl className="grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-[minmax(0,max-content)_minmax(0,1fr)]">
            {items.map((item) => (
              <Fragment key={item.label}>
                <dt className="text-muted-foreground">{item.label}</dt>
                <dd className="mb-1.5 font-mono break-words sm:mb-0">
                  {item.value === null || item.value === undefined || item.value === "" ? "Not provided" : item.value}
                </dd>
              </Fragment>
            ))}
          </dl>
        ) : null}
        {children}
      </div>
    </details>
  )
}
