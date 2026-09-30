'use client'

import Link from 'next/link'
import { ChevronRight } from 'lucide-react'

interface PropertyDetailBreadcrumbProps {
  property: {
    address: string
  }
}

export function PropertyDetailBreadcrumb({ property }: PropertyDetailBreadcrumbProps) {
  const district = property.address.split(',').slice(-2, -1)[0]?.trim() || 'Quận'

  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <Link href="/" className="hover:text-foreground transition-colors">
        Trang chủ
      </Link>
      <ChevronRight className="h-4 w-4" />
      <Link href="/" className="hover:text-foreground transition-colors">
        Căn hộ
      </Link>
      <ChevronRight className="h-4 w-4" />
      <Link href="/" className="hover:text-foreground transition-colors">
        Thành phố Hồ Chí Minh
      </Link>
      <ChevronRight className="h-4 w-4" />
      <span className="text-foreground font-medium">{district}</span>
    </div>
  )
}
