'use client'

import { CalendarDays, MapPin } from 'lucide-react'
import { formatDate, formatPrice, formatPricePerM2, getListingBadge } from '@/lib/format'
import { cn } from '@/lib/utils'

interface PropertyHeaderProps {
  property: {
    title: string
    price_range: string
    area: number | null
    address: string
    listing_type: string
    posted_date?: string | null
  }
}

export function PropertyHeader({ property }: PropertyHeaderProps) {
  const badge = getListingBadge(property.listing_type)
  const pricePerM2 = formatPricePerM2(property.price_range, property.area)
  const postedDate = formatDate(property.posted_date)

  const stats = [
    { label: 'Mức giá', value: formatPrice(property.price_range), highlight: true },
    { label: 'Diện tích', value: property.area ? `${property.area} m²` : '—' },
    { label: 'Đơn giá', value: pricePerM2 ?? '—' },
  ]

  return (
    <div className="rounded-xl border border-border bg-card p-5 md:p-6">
      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        {badge && <span className={cn('rounded-md px-2 py-0.5 font-semibold', badge.className)}>{badge.text}</span>}
        {postedDate && (
          <span className="flex items-center gap-1">
            <CalendarDays className="h-3.5 w-3.5" />
            Đăng ngày {postedDate}
          </span>
        )}
      </div>

      <h1 className="text-xl md:text-2xl font-bold leading-snug text-foreground text-balance">{property.title}</h1>

      <p className="mt-2 flex items-start gap-1.5 text-sm text-muted-foreground">
        <MapPin className="mt-0.5 h-4 w-4 flex-shrink-0" />
        <span>{property.address}</span>
      </p>

      <dl className="mt-5 grid grid-cols-3 divide-x divide-border rounded-lg bg-muted/60">
        {stats.map((stat) => (
          <div key={stat.label} className="px-3 py-3 md:px-4">
            <dt className="text-xs text-muted-foreground">{stat.label}</dt>
            <dd className={cn('mt-0.5 font-bold', stat.highlight ? 'text-lg md:text-xl text-price' : 'text-base md:text-lg text-foreground')}>
              {stat.value}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
