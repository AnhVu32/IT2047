'use client'

import { Bed, Bath, Compass, BookOpen, Sofa } from 'lucide-react'

interface QuickSpecsGridProps {
  property: {
    area: number | null
    bedrooms: number | null
    bathrooms: number | null
    house_direction: string | null
    balcony_direction: string | null
    legal_status: string | null
    furnishing: string | null
  }
}

const getDirectionLabel = (direction: string | null) => {
  if (!direction) return null

  const directionMap: { [key: string]: string } = {
    N: 'Hướng Bắc',
    S: 'Hướng Nam',
    E: 'Hướng Đông',
    W: 'Hướng Tây',
    NE: 'Hướng Đông Bắc',
    NW: 'Hướng Tây Bắc',
    SE: 'Hướng Đông Nam',
    SW: 'Hướng Tây Nam',
  }

  return directionMap[direction] || direction
}

export function QuickSpecsGrid({ property }: QuickSpecsGridProps) {
  const specs = [
    { icon: Bed, label: 'Phòng ngủ', value: property.bedrooms },
    { icon: Bath, label: 'Phòng tắm', value: property.bathrooms },
    { icon: Compass, label: 'Hướng nhà', value: getDirectionLabel(property.house_direction) },
    { icon: Compass, label: 'Hướng ban công', value: getDirectionLabel(property.balcony_direction) },
    { icon: BookOpen, label: 'Pháp lý', value: property.legal_status },
    { icon: Sofa, label: 'Nội thất', value: property.furnishing },
  ]

  const filledSpecs = specs.filter((spec) => spec.value !== null && spec.value !== undefined)

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-4 py-4 border-b border-border">
      {filledSpecs.map((spec, index) => {
        const Icon = spec.icon
        return (
          <div key={index} className="flex flex-col items-center text-center p-3 rounded-lg bg-card hover:bg-muted/50 transition-colors">
            <Icon className="h-6 w-6 text-[#E03C31] mb-2" />
            <p className="text-xs text-muted-foreground mb-1">{spec.label}</p>
            <p className="text-sm font-semibold text-foreground break-words">{spec.value}</p>
          </div>
        )
      })}
    </div>
  )
}
