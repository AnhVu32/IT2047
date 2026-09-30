"use client"

import { useState, useCallback } from "react"
import { Header } from "@/components/header"
import { SearchBar } from "@/components/search-bar"
import { SidebarFilter } from "@/components/SidebarFilter"
import { PropertyListings } from "@/components/property-listings"
import { Footer } from "@/components/footer"

export default function RealEstatePage() {
  const [activeFilters, setActiveFilters] = useState<any>({})
  const [sortOption, setSortOption] = useState("newest")
  const [currentPage, setCurrentPage] = useState(1)

  const handleApplyFilters = useCallback((filters: any) => {
    console.log("[v0] Filters applied:", filters)
    setActiveFilters(filters)
    setCurrentPage(1) // Reset to first page when filters change
  }, [])

  const handleSearch = useCallback((query: string) => {
    console.log("[v0] Search query:", query)
    // Add the search query to active filters
    setActiveFilters((prev: Record<string, unknown>) => ({
      ...prev,
      query: query
    }))
    setCurrentPage(1) // Reset to first page when search query changes
  }, [])

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <header className="sticky top-0 z-50 w-full bg-background shadow-sm">
        <Header />
        <SearchBar onSearch={handleSearch} />
      </header>
      
      <main className="flex-1 container mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Left Sidebar - Sticky with independent scrolling */}
          <aside className="lg:col-span-1 sticky top-24 h-[calc(100vh-7rem)] overflow-y-auto [&::-webkit-scrollbar]:hidden">
            <SidebarFilter onApplyFilters={handleApplyFilters} />
          </aside>
          
          {/* Right Main Column - 3/4 width */}
          <section className="lg:col-span-3">
            <PropertyListings 
              activeFilters={activeFilters}
              sortOption={sortOption}
              onSortChange={setSortOption}
              currentPage={currentPage}
              onPageChange={setCurrentPage}
            />
          </section>
        </div>
      </main>

      <Footer />
    </div>
  )
}
