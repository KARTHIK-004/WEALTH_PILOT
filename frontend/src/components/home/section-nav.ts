/**
 * In-page navigation for the public Home page. The ids here are the `id`
 * attributes of the page's own `<section>` elements; the navbar and footer
 * render plain `<a href="#id">` links (so they work without JavaScript) and
 * enhance them with `scrollToSection`, which scrolls smoothly unless the
 * user prefers reduced motion and then moves focus to the section so
 * keyboard and screen-reader users land where they asked to go.
 */
export const HOME_SECTIONS = [
  { id: "home", label: "Home" },
  { id: "how-it-works", label: "How It Works" },
  { id: "features", label: "Features" },
] as const

export type HomeSectionId = (typeof HOME_SECTIONS)[number]["id"]

export function scrollToSection(id: string) {
  const target = document.getElementById(id)
  if (!target) return
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
  target.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" })
  target.focus({ preventScroll: true })
  window.history.replaceState(null, "", `#${id}`)
}
