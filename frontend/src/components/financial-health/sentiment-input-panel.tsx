import { Eraser, LoaderCircle, Lock } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { MAX_USER_TEXT_CHARS, charactersRemaining, countCharacters, isSubmitShortcut, validateUserText } from "@/lib/user-text-input"

export interface SentimentInputPanelProps {
  /** The text in the box. It lives only in the parent's state. */
  draft: string
  /** True when a text has been submitted, so Clear has something to forget. */
  hasSubmittedText: boolean
  /** A request is in flight: a second submit is refused while this is true. */
  pending: boolean
  onDraftChange: (value: string) => void
  onSubmit: () => void
  onClear: () => void
}

/**
 * "In your own words": the optional text box. The rules for what may be sent, the duplicate-submit guard and what Clear forgets are in `@/lib/user-text-input` (unit-tested without a DOM);
 * this component only shows them. The text is never written to browser storage, a URL, the console or any analytics, and Clear drops it (and the submitted copy) at once.
 */
export function SentimentInputPanel({ draft, hasSubmittedText, pending, onDraftChange, onSubmit, onClear }: SentimentInputPanelProps) {
  const checked = validateUserText(draft)
  const used = countCharacters(draft)
  const remaining = charactersRemaining(draft)
  const invalid = !checked.ok
  const submitDisabled = pending || invalid

  return (
    <Card role="region" aria-labelledby="input-heading">
      <CardHeader>
        <CardTitle id="input-heading" role="heading" aria-level={2} className="text-base">
          In your own words
        </CardTitle>
        <CardDescription>Optional. Write about your financial concerns, goals or preferences to see how your words read.</CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="space-y-3"
          aria-label="Optional text about your finances"
          onSubmit={(event) => {
            event.preventDefault()
            onSubmit()
          }}
        >
          <div className="space-y-2">
            <Label htmlFor="insight-text">Describe your financial concerns, goals or feelings (optional)</Label>
            <Textarea
              id="insight-text"
              value={draft}
              rows={5}
              onChange={(event) => onDraftChange(event.target.value)}
              onKeyDown={(event) => {
                if (isSubmitShortcut(event.nativeEvent)) {
                  event.preventDefault()
                  onSubmit()
                }
              }}
              placeholder="For example: I want to invest more safely, but I worry about losing my savings."
              autoComplete="off"
              spellCheck={false}
              aria-invalid={invalid}
              aria-describedby={invalid ? "insight-text-help insight-text-counter insight-text-error" : "insight-text-help insight-text-counter"}
              className="min-h-32 resize-y"
            />
            <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
              <p id="insight-text-help" className="text-muted-foreground flex-1 basis-60 text-xs">
                Press Analyse, or Ctrl+Enter, to read it. Leave it empty to see your monthly behaviour only.
              </p>
              <p id="insight-text-counter" className={remaining < 0 ? "text-destructive text-xs font-medium" : "text-muted-foreground text-xs"}>
                {used} / {MAX_USER_TEXT_CHARS} characters ({remaining >= 0 ? `${remaining} left` : `${-remaining} over`})
              </p>
            </div>
            {checked.ok ? null : (
              <p id="insight-text-error" role="alert" className="text-destructive text-sm">
                {checked.reason}
              </p>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" disabled={submitDisabled} aria-disabled={submitDisabled}>
              {pending ? <LoaderCircle className="animate-spin" aria-hidden="true" /> : null}
              {pending ? "Analysing…" : "Analyse"}
            </Button>
            <Button type="button" variant="outline" onClick={onClear} disabled={pending || (draft === "" && !hasSubmittedText)}>
              <Eraser aria-hidden="true" /> Clear
            </Button>
          </div>

          <p className="text-muted-foreground flex items-start gap-2 border-t pt-3 text-xs">
            <Lock className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            <span>
              Your text is read once to find the feelings, topics and preferences you express. It is not saved on the server or in your browser's storage, and it is not used to change your stored risk
              assessment.
            </span>
          </p>
        </form>
      </CardContent>
    </Card>
  )
}
