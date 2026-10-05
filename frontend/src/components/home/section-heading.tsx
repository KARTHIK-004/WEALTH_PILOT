interface SectionHeadingProps {
  id: string
  eyebrow: string
  title: string
  description: string
}

/** Shared heading block for the Home page's content sections. `id` is the
 * heading's own id, referenced by the section's `aria-labelledby`. */
export function SectionHeading({ id, eyebrow, title, description }: SectionHeadingProps) {
  return (
    <div className="mx-auto max-w-2xl space-y-3 text-center">
      <p className="text-primary text-sm font-medium">{eyebrow}</p>
      <h2 id={id} className="text-3xl font-semibold tracking-tight text-balance">
        {title}
      </h2>
      <p className="text-muted-foreground text-pretty">{description}</p>
    </div>
  )
}
