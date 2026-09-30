"use client"

import { Button } from "@/components/ui/button"
import { AdvancedFilter } from "@/components/advanced-filter"

interface SidebarFilterProps {
  onApplyFilters?: (filters: any) => void
  showSupportCard?: boolean
}

export function SidebarFilter({ onApplyFilters, showSupportCard = true }: SidebarFilterProps) {
  const handleApplyFilters = (filters: any) => {
    console.log("[v0] SidebarFilter received filters:", filters)
    onApplyFilters?.(filters)
  }

  return (
    <div className="space-y-6 sticky top-24">
      {/* Filter Form - Rendered directly in sidebar */}
      <AdvancedFilter onApplyFilters={handleApplyFilters} />

      {/* Support CTA Card - Conditional rendering */}
      {showSupportCard && (
        <div className="bg-[#FFF5F4] border border-[#E03C31]/20 rounded-lg p-5">
          <h3 className="font-semibold text-[#E03C31] mb-2">
            Bạn cần hỗ trợ chuyên nghiệp?
          </h3>
          <p className="text-sm text-muted-foreground mb-4">
            Các chuyên viên của chúng tôi luôn sẵn sàng hỗ trợ bạn tìm thấy ngôi nhà mơ ước.
          </p>
          <Button className="w-full bg-[#E03C31] hover:bg-[#c43428] text-white h-11">
            Tìm môi giới
          </Button>
        </div>
      )}
    </div>
  )
}
