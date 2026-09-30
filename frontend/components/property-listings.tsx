"use client"

import { useEffect, useState } from "react"
import { ChevronDown, ChevronLeft, ChevronRight, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { PropertyCard } from "@/components/property-card"

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
}

const SKELETON_COUNT = 5

function PropertyCardSkeleton() {
  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden animate-pulse">
      <div className="flex flex-col md:flex-row">
        {/* Image Skeleton */}
        <div className="w-full md:w-[280px] lg:w-[320px] h-[200px] md:min-h-[220px] bg-muted flex-shrink-0" />
        
        {/* Content Skeleton */}
        <div className="flex-1 p-4 flex flex-col space-y-3">
          <div className="h-6 bg-muted rounded w-3/4" />
          <div className="h-4 bg-muted rounded w-1/2" />
          <div className="h-4 bg-muted rounded w-2/3" />
          <div className="h-4 bg-muted rounded w-full" />
          <div className="h-4 bg-muted rounded w-full" />
          <div className="mt-auto h-10 bg-muted rounded w-full" />
        </div>
      </div>
    </div>
  )
}

export function PropertyListings({
  activeFilters = {},
  sortOption = "newest",
  onSortChange = () => {},
  currentPage = 1,
  onPageChange = () => {},
}: PropertyListingsProps) {
  const [properties, setProperties] = useState<Property[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [totalCount, setTotalCount] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [internalPage, setInternalPage] = useState(currentPage)

  // Build query parameters from activeFilters and sortOption
  const buildQueryParams = () => {
    const searchParams = new URLSearchParams()

    // Add page
    searchParams.append("page", internalPage.toString())

    // Map sortOption to API parameters
    if (sortOption === "newest") {
      searchParams.append("sort_by", "newest")
      searchParams.append("sort_order", "desc")
    } else if (sortOption === "oldest") {
      searchParams.append("sort_by", "oldest")
      searchParams.append("sort_order", "asc")
    } else if (sortOption === "price_asc") {
      searchParams.append("sort_by", "price_asc")
      searchParams.append("sort_order", "asc")
    } else if (sortOption === "price_desc") {
      searchParams.append("sort_by", "price_desc")
      searchParams.append("sort_order", "desc")
    }

    // Add all active filters
    Object.entries(activeFilters).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== "") {
        searchParams.append(key, String(value))
      }
    })

    // Fix URL encoding: replace + with %20 for proper space encoding
    return searchParams.toString().replace(/\+/g, '%20')
  }

  useEffect(() => {
    const fetchProperties = async () => {
      try {
        setLoading(true)
        setError(null)

        const queryString = buildQueryParams()
        console.log("[v0] Fetching with query:", queryString)
        
        const response = await fetch(`/api/properties?${queryString}`)
        
        if (!response.ok) {
          throw new Error(`API Error: ${response.status}`)
        }

        const data = await response.json()
        console.log("[v0] API Response:", data)
        
        const fetchedProperties = data.data?.properties || []
        const total = data.data?.total || data.total || fetchedProperties.length
        
        setProperties(fetchedProperties)
        setTotalCount(total)
        setTotalPages(data.data?.num_pages || 1)
        
        console.log("[v0] Loaded", fetchedProperties.length, "properties. Total:", total)
        
        // Scroll to top smoothly
        window.scrollTo({ top: 0, behavior: 'smooth' })
      } catch (err) {
        console.error("[v0] Fetch error:", err)
        setError(err instanceof Error ? err.message : "Failed to fetch properties")
        setProperties([])
      } finally {
        setLoading(false)
      }
    }

    fetchProperties()
  }, [internalPage, activeFilters, sortOption])

  // Helper function to generate page numbers with sliding window
  const getPageNumbers = () => {
    const pages: (number | string)[] = []
    const maxVisible = 5
    
    if (totalPages <= maxVisible) {
      // Show all pages if totalPages is small
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i)
      }
    } else {
      // Calculate the sliding window
      let start = Math.max(1, internalPage - Math.floor(maxVisible / 2))
      let end = Math.min(totalPages, start + maxVisible - 1)
      
      // Adjust start if end is at totalPages
      if (end === totalPages) {
        start = Math.max(1, end - maxVisible + 1)
      }
      
      // Add first page if not in range
      if (start > 1) {
        pages.push(1)
        if (start > 2) pages.push('...')
      }
      
      // Add page numbers in range
      for (let i = start; i <= end; i++) {
        pages.push(i)
      }
      
      // Add last page if not in range
      if (end < totalPages) {
        if (end < totalPages - 1) pages.push('...')
        pages.push(totalPages)
      }
    }
    
    return pages
  }

  const handleSortChange = (value: string) => {
    onSortChange(value)
  }

  const handlePageChange = (page: number) => {
    setInternalPage(page)
    onPageChange(page)
  }

  return (
    <div>
      {/* Header with sort */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-xl font-bold text-foreground">
            Mua bán Bất động sản ở Thành phố Hồ Chí Minh
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Hiển thị {totalCount.toLocaleString('vi-VN')} bất động sản đã xác thực
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Sắp xếp:</span>
          <Select value={sortOption} onValueChange={handleSortChange}>
            <SelectTrigger className="w-[180px] h-10">
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

      {/* Error State */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 text-red-700">
          <p>Không thể tải bất động sản: {error}</p>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="space-y-4">
          {Array.from({ length: SKELETON_COUNT }).map((_, i) => (
            <PropertyCardSkeleton key={i} />
          ))}
        </div>
      )}

      {/* Empty State */}
      {!loading && properties.length === 0 && !error && (
        <div className="text-center py-12">
          <p className="text-muted-foreground">Không có bất động sản nào</p>
        </div>
      )}

      {/* Property Cards */}
      {!loading && properties.length > 0 && (
        <div className="space-y-4">
          {properties.map((property) => (
            <PropertyCard key={property.id} property={property} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {!loading && properties.length > 0 && totalPages > 1 && (
        <div className="flex items-center justify-center gap-1 mt-8">
          {/* Previous Button */}
          <Button 
            variant="outline" 
            size="icon" 
            className="h-10 w-10"
            disabled={internalPage === 1}
            onClick={() => handlePageChange(Math.max(internalPage - 1, 1))}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>

          {/* Page Numbers */}
          {getPageNumbers().map((page, idx) => {
            if (page === '...') {
              return (
                <span key={`ellipsis-${idx}`} className="px-2 text-muted-foreground">
                  ...
                </span>
              )
            }
            
            const pageNum = page as number
            const isActive = internalPage === pageNum
            
            return (
              <Button
                key={pageNum}
                variant={isActive ? "default" : "outline"}
                className={`h-10 w-10 ${
                  isActive 
                    ? "bg-[#E03C31] hover:bg-[#c43428] text-white" 
                    : ""
                }`}
                onClick={() => handlePageChange(pageNum)}
              >
                {pageNum}
              </Button>
            )
          })}

          {/* Next Button */}
          <Button 
            variant="outline" 
            size="icon" 
            className="h-10 w-10"
            disabled={internalPage === totalPages}
            onClick={() => handlePageChange(Math.min(internalPage + 1, totalPages))}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  )
}
