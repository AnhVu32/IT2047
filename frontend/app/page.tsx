"use client"

import { useState, useCallback, useMemo, useEffect } from "react"
import Link from "next/link"
import { ArrowRight, Sparkles } from "lucide-react"
import { Header } from "@/components/header"
import { SearchBar } from "@/components/search-bar"
import { SidebarFilter } from "@/components/SidebarFilter"
import { PropertyListings } from "@/components/property-listings"
import { Footer } from "@/components/footer"
import { cn } from "@/lib/utils"

const DEFAULT_PROPERTY_TYPE = "Căn hộ,Nhà đất"

const VALUE_FILTER_KEYS = ["district", "bedrooms", "bathrooms", "legal_status", "furniture", "house_direction", "balcony_direction"]

// Counts filter groups the user changed, for the badge on the mobile filter button.
function countActiveFilters(filters: Record<string, unknown>) {
  const has = (key: string) => filters[key] !== undefined && filters[key] !== ""
  const groups = [
    filters.property_type !== undefined && filters.property_type !== DEFAULT_PROPERTY_TYPE,
    has("min_price") || has("max_price"),
    has("min_area") || has("max_area"),
    // Amenities are sent as individual boolean flags.
    Object.values(filters).some((value) => value === true),
    ...VALUE_FILTER_KEYS.map(has),
  ]
  return groups.filter(Boolean).length
}

export default function RealEstatePage() {
  const [filters, setFilters] = useState<Record<string, unknown>>({})
  const [query, setQuery] = useState("")
  const [sortOption, setSortOption] = useState("newest")
  const [currentPage, setCurrentPage] = useState(1)
  const [filtersOpen, setFiltersOpen] = useState(false)

  // Keyword and sidebar filters are independent, so applying one never drops the other.
  const activeFilters = useMemo(() => (query ? { ...filters, query } : filters), [filters, query])

  const handleApplyFilters = useCallback((next: Record<string, unknown>) => {
    setFilters(next)
    setCurrentPage(1)
  }, [])

  const handleSearch = useCallback((next: string) => {
    setQuery(next)
    setCurrentPage(1)
  }, [])

  // Lock page scroll while the mobile filter drawer is open.
  useEffect(() => {
    if (!filtersOpen) return
    const previous = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.body.style.overflow = previous
    }
  }, [filtersOpen])

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <header className="sticky top-0 z-40 w-full">
        <Header />
      </header>

      <section className="relative overflow-hidden bg-primary text-primary-foreground">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.08] [background-image:radial-gradient(circle_at_1px_1px,currentColor_1px,transparent_0)] [background-size:22px_22px]"
        />
        <div className="container relative mx-auto px-4 py-8 md:py-10">
          <div className="max-w-3xl">
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-balance">
              Tìm ngôi nhà phù hợp tại TP. Hồ Chí Minh
            </h1>
            <p className="mt-2 text-sm md:text-base text-primary-foreground/80">
              Lọc theo ngân sách, khu vực và tiện ích — hoặc để trợ lý AI tư vấn theo nhu cầu của bạn.
            </p>
            <div className="mt-5">
              <SearchBar query={query} onSearch={handleSearch} />
            </div>
            <Link
              href="/tim-kiem-chuyen-sau"
              className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-primary-foreground/90 hover:text-primary-foreground"
            >
              <Sparkles className="h-4 w-4" />
              Chưa rõ nhu cầu? Hỏi trợ lý AI
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      <main className="flex-1 container mx-auto px-4 py-6">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[300px_minmax(0,1fr)] xl:grid-cols-[320px_minmax(0,1fr)]">
          {/* A single filter instance: a drawer on mobile, a sticky column on desktop. */}
          <aside
            className={cn(
              "lg:sticky lg:top-20 lg:block lg:h-[calc(100vh-6rem)] lg:self-start",
              filtersOpen ? "fixed inset-0 z-50 bg-black/40 lg:static lg:bg-transparent" : "hidden",
            )}
            onClick={(e) => {
              if (e.target === e.currentTarget) setFiltersOpen(false)
            }}
          >
            <div className="absolute inset-y-0 left-0 w-[88%] max-w-sm p-3 lg:static lg:h-full lg:w-auto lg:max-w-none lg:p-0">
              <SidebarFilter onApplyFilters={handleApplyFilters} onClose={() => setFiltersOpen(false)} />
            </div>
          </aside>

          <section className="min-w-0">
            <PropertyListings
              activeFilters={activeFilters}
              sortOption={sortOption}
              onSortChange={(value) => {
                setSortOption(value)
                setCurrentPage(1)
              }}
              currentPage={currentPage}
              onPageChange={setCurrentPage}
              searchQuery={query}
              onClearSearch={() => handleSearch("")}
              activeFilterCount={countActiveFilters(filters)}
              onOpenFilters={() => setFiltersOpen(true)}
            />
          </section>
        </div>
      </main>

      <Footer />
    </div>
  )
}
