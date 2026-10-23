'use client'

import Link from 'next/link'
import { ChevronLeft, ChevronRight } from 'lucide-react'

interface PropertyDetailBreadcrumbProps {
  property: {
    address: string
  }
}

export function PropertyDetailBreadcrumb({ property }: PropertyDetailBreadcrumbProps) {
  const district = property.address?.split(',').slice(-2, -1)[0]?.trim()

  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-sm text-muted-foreground">
      <Link href="/" className="flex items-center gap-1 font-medium hover:text-foreground transition-colors">
        <ChevronLeft className="h-4 w-4 sm:hidden" />
        Tìm nhà
      </Link>
      {district && (
        <span className="hidden sm:contents">
          <ChevronRight className="h-4 w-4" />
          <span className="text-foreground">{district}</span>
        </span>
      )}
    </nav>
  )
}
