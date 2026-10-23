"use client"

import Link from "next/link"
import { ArrowRight, Sparkles } from "lucide-react"
import { AdvancedFilter } from "@/components/advanced-filter"

interface SidebarFilterProps {
  onApplyFilters?: (filters: any) => void
  onClose?: () => void
  showSupportCard?: boolean
  title?: string
  applyLabel?: string
}

export function SidebarFilter({
  onApplyFilters,
  onClose,
  showSupportCard = true,
  title,
  applyLabel,
}: SidebarFilterProps) {
  return (
    <div className="flex h-full flex-col gap-4">
      <div className="min-h-0 flex-1">
        <AdvancedFilter
          onApplyFilters={(filters) => onApplyFilters?.(filters)}
          onClose={onClose}
          title={title}
          applyLabel={applyLabel}
        />
      </div>

      {showSupportCard && (
        <Link
          href="/tim-kiem-chuyen-sau"
          className="group hidden lg:block shrink-0 rounded-xl border border-primary/20 bg-accent p-4 transition-colors hover:border-primary/40"
        >
          <div className="flex items-center gap-2 font-semibold text-accent-foreground">
            <Sparkles className="h-4 w-4 text-primary" />
            Chưa rõ nên chọn gì?
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Mô tả nhu cầu, trợ lý AI sẽ gợi ý và so sánh các căn phù hợp.
          </p>
          <span className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-primary">
            Trò chuyện với trợ lý
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </span>
        </Link>
      )}
    </div>
  )
}
