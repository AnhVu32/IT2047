'use client'

import { MapPin, Home } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

interface PropertyHeaderProps {
  property: {
    title: string
    price_range: string
    area: number | null
    address: string
    listing_type: string
  }
}

const getBadgeStyle = (listingType: string) => {
  if (listingType === 'VIP Kim Cương') {
    return { bg: 'bg-[#E03C31]', text: 'VIP KIM CƯƠNG' }
  } else if (listingType === 'VIP Vàng') {
    return { bg: 'bg-orange-500', text: 'VIP VÀNG' }
  }
  return null
}

const calculatePricePerM2 = (priceRange: string, area: number | null) => {
  if (!area) return null

  // Parse price_range (e.g., "5.5" from "5.5 Tỷ VNĐ")
  const price = parseFloat(priceRange)
  if (isNaN(price)) return null

  // Convert tỷ VNĐ to VNĐ and calculate price per m²
  const priceInVND = price * 1_000_000_000
  const pricePerM2 = Math.round(priceInVND / area)

  return pricePerM2.toLocaleString('vi-VN')
}

export function PropertyHeader({ property }: PropertyHeaderProps) {
  const badgeStyle = getBadgeStyle(property.listing_type)
  const pricePerM2 = calculatePricePerM2(property.price_range, property.area)

  return (
    <div className="space-y-4 pb-4 border-b border-border">
      {/* Title and Badge */}
      <div className="flex items-start gap-3">
        <div className="flex-1">
          <h1 className="text-2xl md:text-3xl font-bold text-foreground mb-2">{property.title}</h1>
          {badgeStyle && (
            <Badge className={`${badgeStyle.bg} hover:${badgeStyle.bg} text-white text-xs font-medium px-2 py-1`}>
              {badgeStyle.text}
            </Badge>
          )}
        </div>
      </div>

      {/* Address */}
      <div className="flex items-start gap-2 text-muted-foreground">
        <MapPin className="h-5 w-5 flex-shrink-0 mt-0.5" />
        <span>{property.address}</span>
      </div>

      {/* Price and Area Bar */}
      <div className="bg-[#E03C31]/5 rounded-lg p-4 space-y-3">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-muted-foreground mb-1">Giá</p>
            <p className="text-2xl font-bold text-[#E03C31]">{property.price_range} Tỷ VNĐ</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground mb-1">Diện tích</p>
            <p className="text-2xl font-bold text-foreground">{property.area} m²</p>
          </div>
        </div>

        {/* Price per m² */}
        {pricePerM2 && (
          <div className="pt-2 border-t border-border">
            <p className="text-sm text-muted-foreground mb-1">Giá trên m²</p>
            <p className="text-lg font-semibold text-foreground">{pricePerM2} VNĐ/m²</p>
          </div>
        )}
      </div>
    </div>
  )
}
