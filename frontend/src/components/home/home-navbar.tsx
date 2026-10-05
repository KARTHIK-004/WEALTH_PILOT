import { cn } from "cn"
import { Menu } from "lucide-react"
import { useState } from "react"
import { Link, useLocation } from "react-router"

import { BrandMark } from "@/components/home/brand-mark"
import { HOME_SECTIONS, scrollToSection } from "@/components/home/section-nav"
import { Button, buttonVariants } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { useAuth } from "@/providers/auth-context"

/** Matches the Sheet's own `duration-200` close transition, so the page is
 * scrolled only once the dialog has released its scroll lock. */
const SHEET_CLOSE_MS = 220

/**
 * Public Home page top bar: brand on the left, in-page section links in the
 * middle (`md` and up), Login / Get Started on the right. Below `md` the
 * section links and actions move into the shadcn `Sheet` menu.
 *
 * Reads `useAuth().isAuthenticated` only to decide which actions to show --
 * an already signed-in session gets "Open Dashboard" instead of Login / Get
 * Started. No authentication logic lives here.
 */
export function HomeNavbar() {
  const { isAuthenticated } = useAuth()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  // On another public page (/about) the section links go to the Home page's
  // sections instead of scrolling the current page; `HomePage` scrolls to the hash.
  const onHome = location.pathname === "/"
  const onAbout = location.pathname === "/about"

  const handleSectionClick = (event: React.MouseEvent<HTMLAnchorElement>, id: string) => {
    event.preventDefault()
    scrollToSection(id)
  }

  const handleMobileSectionClick = (event: React.MouseEvent<HTMLAnchorElement>, id: string) => {
    event.preventDefault()
    setMenuOpen(false)
    window.setTimeout(() => scrollToSection(id), SHEET_CLOSE_MS)
  }

  const actions = isAuthenticated ? (
    <Link to="/dashboard" className={cn(buttonVariants({ size: "lg" }), "px-4")}>
      Open Dashboard
    </Link>
  ) : (
    <>
      <Link to="/login" className={cn(buttonVariants({ variant: "ghost", size: "lg" }), "px-3")}>
        Login
      </Link>
      <Link to="/create-user" className={cn(buttonVariants({ size: "lg" }), "px-4")}>
        Get Started
      </Link>
    </>
  )

  return (
    <header className="bg-background/95 sticky top-0 z-40 border-b">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-4 px-4 md:px-6">
        <Link
          to="/"
          className="focus-visible:ring-ring/50 rounded-md outline-none focus-visible:ring-3"
          aria-label="WealthPilot AI home"
        >
          <BrandMark />
        </Link>

        <nav aria-label="Page sections" className="hidden md:block">
          <ul className="flex items-center gap-1">
            {HOME_SECTIONS.map((section) => (
              <li key={section.id}>
                {onHome ? (
                  <a
                    href={`#${section.id}`}
                    onClick={(event) => handleSectionClick(event, section.id)}
                    className={cn(buttonVariants({ variant: "ghost" }), "text-muted-foreground hover:text-foreground px-3")}
                  >
                    {section.label}
                  </a>
                ) : (
                  <Link
                    to={`/#${section.id}`}
                    className={cn(buttonVariants({ variant: "ghost" }), "text-muted-foreground hover:text-foreground px-3")}
                  >
                    {section.label}
                  </Link>
                )}
              </li>
            ))}
            <li>
              <Link
                to="/about"
                aria-current={onAbout ? "page" : undefined}
                className={cn(
                  buttonVariants({ variant: "ghost" }),
                  "px-3",
                  onAbout ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                )}
              >
                About
              </Link>
            </li>
          </ul>
        </nav>

        <div className="hidden items-center gap-2 md:flex">{actions}</div>

        <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
          <SheetTrigger render={<Button variant="outline" size="icon-lg" className="md:hidden" aria-label="Open menu" />}>
            <Menu aria-hidden="true" />
          </SheetTrigger>
          <SheetContent side="right" className="w-72">
            <SheetHeader>
              <SheetTitle>
                <BrandMark />
              </SheetTitle>
              <SheetDescription>Educational decision-support prototype.</SheetDescription>
            </SheetHeader>
            <nav aria-label="Page sections" className="px-4">
              <ul className="flex flex-col gap-1">
                {HOME_SECTIONS.map((section) => (
                  <li key={section.id}>
                    {onHome ? (
                      <a
                        href={`#${section.id}`}
                        onClick={(event) => handleMobileSectionClick(event, section.id)}
                        className={cn(buttonVariants({ variant: "ghost", size: "lg" }), "w-full justify-start")}
                      >
                        {section.label}
                      </a>
                    ) : (
                      <Link
                        to={`/#${section.id}`}
                        className={cn(buttonVariants({ variant: "ghost", size: "lg" }), "w-full justify-start")}
                      >
                        {section.label}
                      </Link>
                    )}
                  </li>
                ))}
                <li>
                  <Link
                    to="/about"
                    aria-current={onAbout ? "page" : undefined}
                    className={cn(buttonVariants({ variant: "ghost", size: "lg" }), "w-full justify-start")}
                  >
                    About
                  </Link>
                </li>
              </ul>
            </nav>
            <div className="flex flex-col gap-2 px-4">{actions}</div>
          </SheetContent>
        </Sheet>
      </div>
    </header>
  )
}
