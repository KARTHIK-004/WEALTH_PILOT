/**
 * Presentation constants shared by every chart in `components/charts/` —
 * colours come from the project's own theme tokens (`index.css`), so the
 * charts follow the light/dark toggle. Nothing here touches data.
 */
export const AXIS_TICK = { fill: "var(--muted-foreground)", fontSize: 12 } as const

export const TOOLTIP_STYLE = {
  backgroundColor: "var(--popover)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  color: "var(--popover-foreground)",
  fontSize: 12,
} as const

export const TOOLTIP_ITEM_STYLE = { color: "var(--popover-foreground)" } as const

/** The emphasised series (near-black in light mode, near-white in dark). */
export const SERIES_EMPHASIS = "var(--primary)"

/** The de-emphasised series. Every series is also identified by a text
 * label, never by colour alone. */
export const SERIES_MUTED = "var(--muted-foreground)"

/** Donut slice fills — the same `--chart-*` tokens the project's existing
 * allocation chart already used. */
export const SLICE_COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"] as const
