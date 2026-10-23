"use client"

import { Building2, LogIn, LogOut, Search, Sparkles } from "lucide-react"
import { Button } from "@/components/ui/button"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useAuth } from "@/lib/auth-context"
import { cn } from "@/lib/utils"

const NAV_ITEMS = [
  { href: "/", label: "Tìm nhà", icon: Search },
  { href: "/tim-kiem-chuyen-sau", label: "Tư vấn AI", icon: Sparkles },
]

export function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2 shrink-0">
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <Building2 className="h-5 w-5" />
      </span>
      <span className="leading-tight">
        <span className="block font-bold tracking-tight text-foreground">BATDONGSAN AI</span>
        <span className="hidden sm:block text-[11px] text-muted-foreground">Tư vấn bất động sản TP.HCM</span>
      </span>
    </Link>
  )
}

export function Header() {
  const pathname = usePathname()
  const { user, logout, loading } = useAuth()

  return (
    <div className="border-b border-border bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/80">
      <div className="container mx-auto px-4 h-16 flex items-center justify-between gap-2 sm:gap-4">
        <Logo />

        <nav className="flex items-center gap-1 rounded-full bg-muted p-1">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const active = pathname === href
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium transition-colors",
                  active
                    ? "bg-card text-primary shadow-sm"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                <Icon className="h-4 w-4" />
                <span className="hidden sm:inline">{label}</span>
              </Link>
            )
          })}
        </nav>

        <div className="flex items-center gap-2 shrink-0">
          {loading ? null : user ? (
            <>
              <span className="hidden md:flex items-center gap-2 text-sm text-foreground">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-secondary text-xs font-semibold uppercase text-secondary-foreground">
                  {(user.display_name || user.username).slice(0, 1)}
                </span>
                <span className="max-w-32 truncate font-medium">{user.display_name || user.username}</span>
              </span>
              <Button variant="ghost" size="sm" onClick={logout} aria-label="Đăng xuất">
                <LogOut className="h-4 w-4" />
                <span className="hidden lg:inline">Đăng xuất</span>
              </Button>
            </>
          ) : (
            <>
              <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
                <Link href="/dang-ky">Đăng ký</Link>
              </Button>
              <Button asChild size="sm">
                <Link href="/dang-nhap" aria-label="Đăng nhập">
                  <LogIn className="h-4 w-4 sm:hidden" />
                  <span className="hidden sm:inline">Đăng nhập</span>
                </Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
