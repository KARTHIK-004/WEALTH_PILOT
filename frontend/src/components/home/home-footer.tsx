import { Link, useLocation } from "react-router"

import { BrandMark } from "@/components/home/brand-mark"
import { HOME_SECTIONS, scrollToSection } from "@/components/home/section-nav"

const linkClassName =
  "text-muted-foreground hover:text-foreground focus-visible:ring-ring/50 rounded-sm outline-none focus-visible:ring-3"

/** Public-page footer: project name, section links, About and Login. */
export function HomeFooter() {
  const onHome = useLocation().pathname === "/"
  return (
    <footer className="border-t">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 py-10 md:px-6">
        <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
          <div className="space-y-2">
            <BrandMark />
            <p className="text-muted-foreground text-sm">Agentic AI-Based Autonomous Financial Advisor</p>
          </div>
          <nav aria-label="Footer">
            <ul className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
              {HOME_SECTIONS.map((section) => (
                <li key={section.id}>
                  {onHome ? (
                    <a
                      href={`#${section.id}`}
                      onClick={(event) => {
                        event.preventDefault()
                        scrollToSection(section.id)
                      }}
                      className={linkClassName}
                    >
                      {section.label}
                    </a>
                  ) : (
                    <Link to={`/#${section.id}`} className={linkClassName}>
                      {section.label}
                    </Link>
                  )}
                </li>
              ))}
              <li>
                <Link to="/about" className={linkClassName}>
                  About
                </Link>
              </li>
              <li>
                <Link to="/login" className={linkClassName}>
                  Login
                </Link>
              </li>
            </ul>
          </nav>
        </div>
      </div>
    </footer>
  )
}
