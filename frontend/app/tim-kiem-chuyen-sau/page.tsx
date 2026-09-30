"use client"

import { useState } from "react"
import { Header } from "@/components/header"
import { SidebarFilter } from "@/components/SidebarFilter"
import { AIChat } from "@/components/ai-chat"

export default function AdvancedSearchPage() {
  // State lifting: track filters from SidebarFilter and pass to AIChat
  const [currentFilters, setCurrentFilters] = useState<any>({})
  const [showFilterPopup, setShowFilterPopup] = useState(false)

  const handleApplyFilters = (filters: any) => {
    console.log("[v0] Page received filters:", filters)
    setCurrentFilters(filters)
    setShowFilterPopup(true)
  }

  // Helper function to format filter summary in Vietnamese
  const formatFilterSummary = (filters: any): string[] => {
    const summary: string[] = []

    // Price range
    if (filters.min_price || filters.max_price) {
      const minPrice = filters.min_price || 0
      const maxPrice = filters.max_price || "Không giới hạn"
      summary.push(`Mức giá: Từ ${minPrice.toLocaleString("vi-VN")} đến ${maxPrice === 999999 ? "Không giới hạn" : maxPrice.toLocaleString("vi-VN")}`)
    }

    // Area range
    if (filters.min_area || filters.max_area) {
      const minArea = filters.min_area || 0
      const maxArea = filters.max_area || "Không giới hạn"
      summary.push(`Diện tích: Từ ${minArea} đến ${maxArea === 999999 ? "Không giới hạn" : maxArea} m²`)
    }

    // Bedrooms
    if (filters.bedrooms && filters.bedrooms !== "0") {
      summary.push(`Số phòng ngủ: ${filters.bedrooms}`)
    }

    // Bathrooms
    if (filters.bathrooms && filters.bathrooms !== "0") {
      summary.push(`Số phòng tắm: ${filters.bathrooms}`)
    }

    // District
    if (filters.district && filters.district.trim() !== "") {
      summary.push(`Khu vực: ${filters.district}`)
    }

    // Property type
    if (filters.property_type && filters.property_type.trim() !== "") {
      summary.push(`Loại BĐS: ${filters.property_type}`)
    }

    // Legal status
    if (filters.legal_status && filters.legal_status.trim() !== "") {
      summary.push(`Pháp lý: ${filters.legal_status}`)
    }

    // Furniture
    if (filters.furniture && filters.furniture.trim() !== "") {
      summary.push(`Nội thất: ${filters.furniture}`)
    }

    // House direction
    if (filters.house_direction && filters.house_direction.trim() !== "") {
      summary.push(`Hướng nhà: ${filters.house_direction}`)
    }

    // Balcony direction
    if (filters.balcony_direction && filters.balcony_direction.trim() !== "") {
      summary.push(`Hướng ban công: ${filters.balcony_direction}`)
    }

    // Collect amenities
    const amenities: string[] = []
    const amenityMap: { [key: string]: string } = {
      pool: "Hồ bơi",
      gym: "Phòng gym",
      park: "Công viên",
      bbq: "Khu BBQ",
      kids_playground: "Sân chơi trẻ em",
      sports_court: "Sân thể thao",
      security_24h: "Bảo vệ 24/7",
      reception: "Tiếp tân",
      elevator: "Thang máy",
      parking: "Bãi đỗ xe",
      near_metro: "Gần tàu điện",
      near_bus: "Gần xe buýt",
      near_highway: "Gần đường cao tốc",
      near_school: "Gần trường học",
      near_hospital: "Gần bệnh viện",
      near_mall: "Gần trung tâm thương mại",
      near_market: "Gần chợ",
      near_park: "Gần công viên",
      river_view: "View sông",
      park_view: "View công viên",
      city_view: "View thành phố",
      balcony: "Ban công",
      garden: "Vườn",
      garage: "Garage",
      terrace: "Sân thượng",
    }

    for (const [key, label] of Object.entries(amenityMap)) {
      if (filters[key]) {
        amenities.push(label)
      }
    }

    if (amenities.length > 0) {
      summary.push(`Tiện ích: ${amenities.join(", ")}`)
    }

    return summary.length > 0 ? summary : ["Không có bộ lọc được chọn"]
  }

  const filterSummary = formatFilterSummary(currentFilters)

  return (
    <div className="h-screen overflow-hidden flex flex-col bg-background">
      {/* Fixed height header - only top navigation */}
      <div className="shrink-0">
        <Header />
      </div>
      
      {/* Main content - grid layout with independently scrollable columns */}
      <main className="flex-1 min-h-0 grid grid-cols-12 overflow-hidden">
        {/* Left Column - Complex Filter (col-span-5) */}
        <aside className="col-span-12 lg:col-span-5 h-full min-h-0 overflow-y-auto border-r border-border p-6">
          <SidebarFilter onApplyFilters={handleApplyFilters} showSupportCard={false} />
        </aside>
        
        {/* Right Column - AI Chat (col-span-7) */}
        <section className="col-span-12 lg:col-span-7 h-full min-h-0 overflow-hidden bg-muted/30">
          <AIChat filters={currentFilters} />
        </section>
      </main>
      
      {/* Success Popup - Filter Applied */}
      {showFilterPopup && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
          onClick={() => setShowFilterPopup(false)}
        >
          <div 
            className="bg-background p-6 rounded-lg shadow-lg max-w-md w-full mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-bold text-green-600 mb-4">✅ Đã áp dụng bộ lọc</h3>
            
            <div className="space-y-2 mb-4">
              {filterSummary.map((item, index) => (
                <div 
                  key={index} 
                  className="inline-block bg-muted px-3 py-1.5 rounded-md text-sm text-foreground mr-2 mb-2"
                >
                  {item}
                </div>
              ))}
            </div>

            <p className="text-xs text-muted-foreground text-center">Nhấn ra ngoài để tiếp tục chat</p>
          </div>
        </div>
      )}
      
      {/* NO FOOTER */}
    </div>
  )
}
