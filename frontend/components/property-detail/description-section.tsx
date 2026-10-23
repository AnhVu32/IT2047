'use client'

import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { DetailSection } from '@/components/property-detail/section'
import { cn } from '@/lib/utils'

interface DescriptionSectionProps {
  description: string
}

// Long seller descriptions are collapsed so specs and location stay within reach.
const COLLAPSE_AFTER_CHARS = 600

export function DescriptionSection({ description }: DescriptionSectionProps) {
  const [expanded, setExpanded] = useState(false)
  if (!description?.trim()) return null

  const collapsible = description.length > COLLAPSE_AFTER_CHARS

  return (
    <DetailSection title="Mô tả chi tiết">
      <div className="relative">
        <p
          className={cn(
            'whitespace-pre-wrap text-[15px] leading-relaxed text-foreground/85',
            collapsible && !expanded && 'max-h-56 overflow-hidden',
          )}
        >
          {description}
        </p>
        {collapsible && !expanded && (
          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-card to-transparent" />
        )}
      </div>
      {collapsible && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="mt-3 flex items-center gap-1 text-sm font-medium text-primary hover:underline"
        >
          {expanded ? 'Thu gọn' : 'Xem thêm'}
          <ChevronDown className={cn('h-4 w-4 transition-transform', expanded && 'rotate-180')} />
        </button>
      )}
    </DetailSection>
  )
}
