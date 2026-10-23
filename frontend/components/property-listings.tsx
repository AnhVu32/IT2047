"use client"

import { useEffect, useRef, useState } from "react"
import { ChevronLeft, ChevronRight, SearchX, SlidersHorizontal, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { PropertyCard } from "@/components/property-card"
import { cn } from "@/lib/utils"

interface Property {
  id: string
  title: string
  price_range: string
  area: number | null
  address: string
  description: string
  images: string[]
  listing_type: string
  bedrooms: number | null
  bathrooms: number | null
  posted_date: string
}

interface PropertyListingsProps {
  activeFilters?: any
  sortOption?: string
  onSortChange?: (value: string) => void
  currentPage?: number
  onPageChange?: (page: number) => void
  searchQuery?: string
  onClearSearch?: () => void
  activeFilterCount?: number
  onOpenFilters?: () => void
}

const SKELETON_COUNT = 5

const SORT_PARAMS: Record<string, { sort_by: string; sort_order: string }> = {
  newest: { sort_by: "newest", sort_order: "desc" },
  oldest: { sort_by: "oldest", sort_order: "asc" },
  price_asc: { sort_by: "price_asc", sort_order: "asc" },
  price_desc: { sort_by: "price_desc", sort_order: "desc" },
}

function PropertyCardSkeleton() {
  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden animate-pulse">
      <div className="flex flex-col md:flex-row">
        <div className="w-full md:w-[260px] lg:w-[300px] h-[200px] md:h-[210px] bg-muted flex-shrink-0" />
        <div className="flex-1 p-4 flex flex-col space-y-3">
          <div className="h-5 bg-muted rounded w-3/4" />
          <div className="h-6 bg-muted rounded w-1/3" />
          <div className="h-4 bg-muted rounded w-2/3" />
          <div className="h-4 bg-muted rounded w-full" />
          <div className="mt-auto h-4 bg-muted rounded w-1/4" />
        </div>
      </div>
    </div>
  )
}

// Page numbers with a sliding window of 5 and ellipses towards the first/last page.
function getPageNumbers(page: number, totalPages: number) {
  const pages: (number | string)[] = []
  const maxVisible = 5

  if (totalPages <= maxVisible) {
    for (let i = 1; i <= totalPages; i++) pages.push(i)
    return pages
  }

  let start = Math.max(1, page - Math.floor(maxVisible / 2))
  const end = Math.min(totalPages, start + maxVisible - 1)
  if (end === totalPages) start = Math.max(1, end - maxVisible + 1)

  if (start > 1) {
    pages.push(1)
    if (start > 2) pages.push("...")
  }
  for (let i = start; i <= end; i++) pages.push(i)
  if (end < totalPages) {
    if (end < totalPages - 1) pages.push("...")
    pages.push(totalPages)
  }
  return pages
}

export function PropertyListings({
  activeFilters = {},
  sortOption = "newest",
  onSortChange = () => {},
  currentPage = 1,
  onPageChange = () => {},
  searchQuery,
  onClearSearch,
  activeFilterCount = 0,
  onOpenFilters,
}: PropertyListingsProps) {
  const [properties, setProperties] = useState<Property[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [totalCount, setTotalCount] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const topRef = useRef<HTMLDivElement>(null)
  const isFirstLoad = useRef(true)

  useEffect(() => {
    const controller = new AbortController()

    const fetchProperties = async () => {
      try {
        setLoading(true)
        setError(null)

        const searchParams = new URLSearchParams()
        searchParams.append("page", currentPage.toString())
        const sort = SORT_PARAMS[sortOption]
        if (sort) {
          searchParams.append("sort_by", sort.sort_by)
          searchParams.append("sort_order", sort.sort_order)
        }
        Object.entries(activeFilters).forEach(([key, value]) => {
          if (value !== null && value !== undefined && value !== "") {
            searchParams.append(key, String(value))
          }
        })
        // Encode spaces as %20 rather than "+" for the backend's query parser.
        const queryString = searchParams.toString().replace(/\+/g, "%20")

        const response = await fetch(`/api/properties?${queryString}`, { signal: controller.signal })
        if (!response.ok) {
          throw new Error(`API Error: ${response.status}`)
        }

        const data = await response.json()
        const fetchedProperties = data.data?.properties || []
        const total = data.data?.total || data.total || fetchedProperties.length

        setProperties(fetchedProperties)
        setTotalCount(total)
        setTotalPages(data.data?.num_pages || 1)

        // Bring the top of the results into view after paging/filtering, but not on first paint.
        if (!isFirstLoad.current) {
          topRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
        }
        isFirstLoad.current = false
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return
        setError(err instanceof Error ? err.message : "Failed to fetch properties")
        setProperties([])
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }

    fetchProperties()
    return () => controller.abort()
  }, [currentPage, activeFilters, sortOption])

  const handlePageChange = (page: number) => {
    if (page < 1 || page > totalPages || page === currentPage) return
    onPageChange(page)
  }

  return (
    <div ref={topRef} className="scroll-mt-24">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-lg font-bold text-foreground">Bất động sản đang bán tại TP.HCM</h2>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {loading ? "Đang tải..." : `${totalCount.toLocaleString("vi-VN")} kết quả`}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {onOpenFilters && (
            <Button variant="outline" className="h-10 lg:hidden" onClick={onOpenFilters}>
              <SlidersHorizontal className="h-4 w-4" />
              Bộ lọc
              {activeFilterCount > 0 && (
                <span className="rounded-full bg-primary px-1.5 text-xs text-primary-foreground">{activeFilterCount}</span>
              )}
            </Button>
          )}
          <Select value={sortOption} onValueChange={onSortChange}>
            <SelectTrigger className="h-10 w-[170px] bg-card" aria-label="Sắp xếp">
              <SelectValue placeholder="Sắp xếp theo" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="newest">Tin mới nhất</SelectItem>
              <SelectItem value="oldest">Tin cũ nhất</SelectItem>
              <SelectItem value="price_asc">Giá thấp đến cao</SelectItem>
              <SelectItem value="price_desc">Giá cao đến thấp</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {searchQuery && (
        <div className="mb-4 flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">Từ khóa:</span>
          <button
            type="button"
            onClick={onClearSearch}
            className="flex items-center gap-1 rounded-full bg-secondary px-3 py-1 font-medium text-secondary-foreground hover:bg-secondary/80"
            aria-label={`Bỏ từ khóa ${searchQuery}`}
          >
            “{searchQuery}”
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          Không thể tải danh sách bất động sản. Vui lòng thử lại sau. <span className="opacity-70">({error})</span>
        </div>
      )}

      {loading && (
        <div className="space-y-4">
          {Array.from({ length: SKELETON_COUNT }).map((_, i) => (
            <PropertyCardSkeleton key={i} />
          ))}
        </div>
      )}

      {!loading && properties.length === 0 && !error && (
        <div className="flex flex-col items-center rounded-xl border border-dashed border-border bg-card px-6 py-14 text-center">
          <SearchX className="h-10 w-10 text-muted-foreground" />
          <p className="mt-3 font-semibold text-foreground">Không có bất động sản phù hợp</p>
          <p className="mt-1 max-w-sm text-sm text-muted-foreground">
            Thử nới rộng khoảng giá, diện tích hoặc bỏ bớt tiêu chí lọc.
          </p>
          {searchQuery && onClearSearch && (
            <Button variant="outline" className="mt-4" onClick={onClearSearch}>
              Bỏ từ khóa “{searchQuery}”
            </Button>
          )}
        </div>
      )}

      {!loading && properties.length > 0 && (
        <div className="space-y-4">
          {properties.map((property) => (
            <PropertyCard key={property.id} property={property} />
          ))}
        </div>
      )}

      {!loading && properties.length > 0 && totalPages > 1 && (
        <nav className="mt-8 flex items-center justify-center gap-1" aria-label="Phân trang">
          <Button
            variant="outline"
            size="icon"
            className="h-10 w-10"
            disabled={currentPage === 1}
            onClick={() => handlePageChange(currentPage - 1)}
            aria-label="Trang trước"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>

          {getPageNumbers(currentPage, totalPages).map((page, idx) =>
            page === "..." ? (
              <span key={`ellipsis-${idx}`} className="px-2 text-muted-foreground">
                …
              </span>
            ) : (
              <Button
                key={page}
                variant={currentPage === page ? "default" : "outline"}
                className={cn("h-10 w-10", currentPage !== page && "bg-card")}
                aria-current={currentPage === page ? "page" : undefined}
                onClick={() => handlePageChange(page as number)}
              >
                {page}
              </Button>
            ),
          )}

          <Button
            variant="outline"
            size="icon"
            className="h-10 w-10"
            disabled={currentPage === totalPages}
            onClick={() => handlePageChange(currentPage + 1)}
            aria-label="Trang sau"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </nav>
      )}
    </div>
  )
}
