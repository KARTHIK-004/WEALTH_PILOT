import { CircleHelp } from "lucide-react"
import { useId, useState, type ReactNode } from "react"

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

/**
 * A small "?" button that explains a term in plain words (`docs/DESIGN.md`
 * section 30). Uses the existing shadcn Tooltip: it opens on hover, on
 * keyboard focus and on tap/click, and closes on Escape. The same text is
 * also linked with `aria-describedby` (from a `hidden` element, so it is not
 * read twice in the page flow), so a screen reader announces it on focus
 * even if the tooltip is not shown. Help text is supplementary --
 * nothing a user needs is ever available ONLY here.
 */
export function HelpTip({ label, text }: { label: string; text: string }) {
  const id = useId()
  const [open, setOpen] = useState(false)

  return (
    <>
      <Tooltip open={open} onOpenChange={setOpen}>
        <TooltipTrigger
          render={
            <button
              type="button"
              aria-label={`About ${label}`}
              aria-describedby={id}
              onClick={() => setOpen(true)}
              className="text-muted-foreground hover:text-foreground focus-visible:ring-ring/50 inline-flex size-5 shrink-0 items-center justify-center rounded-full align-middle outline-none focus-visible:ring-3"
            />
          }
        >
          <CircleHelp className="size-3.5" aria-hidden="true" />
        </TooltipTrigger>
        <TooltipContent className="text-left leading-snug">{text}</TooltipContent>
      </Tooltip>
      {/* `hidden`: out of the reading flow (no duplicate announcement), yet
          still used as the button's accessible description. */}
      <span id={id} hidden>
        {text}
      </span>
    </>
  )
}

/** A term followed by its help button, kept together on one line. */
export function TermLabel({ children, help, label }: { children: ReactNode; help: string; label?: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      {children}
      <HelpTip label={label ?? (typeof children === "string" ? children : "this term")} text={help} />
    </span>
  )
}
