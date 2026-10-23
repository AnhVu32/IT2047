'use client'

import { Bed, Bath, Compass, FileCheck2, Sofa, DoorOpen } from 'lucide-react'
import { DetailSection } from '@/components/property-detail/section'

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
    N: 'Bắc',
    S: 'Nam',
    E: 'Đông',
    W: 'Tây',
    NE: 'Đông Bắc',
    NW: 'Tây Bắc',
    SE: 'Đông Nam',
    SW: 'Tây Nam',
  }

  return directionMap[direction] || direction
}

export function QuickSpecsGrid({ property }: QuickSpecsGridProps) {
  const specs = [
    { icon: Bed, label: 'Phòng ngủ', value: property.bedrooms },
    { icon: Bath, label: 'Phòng tắm', value: property.bathrooms },
    { icon: FileCheck2, label: 'Pháp lý', value: property.legal_status },
    { icon: Sofa, label: 'Nội thất', value: property.furnishing },
    { icon: Compass, label: 'Hướng nhà', value: getDirectionLabel(property.house_direction) },
    { icon: DoorOpen, label: 'Hướng ban công', value: getDirectionLabel(property.balcony_direction) },
  ]

  const filledSpecs = specs.filter((spec) => spec.value !== null && spec.value !== undefined && spec.value !== '')
  if (filledSpecs.length === 0) return null

  return (
    <DetailSection title="Đặc điểm bất động sản">
      <dl className="grid grid-cols-1 gap-x-8 sm:grid-cols-2">
        {filledSpecs.map((spec) => {
          const Icon = spec.icon
          return (
            <div key={spec.label} className="flex items-center gap-3 border-b border-border py-3">
              <Icon className="h-5 w-5 flex-shrink-0 text-primary" />
              <dt className="text-sm text-muted-foreground">{spec.label}</dt>
              <dd className="ml-auto text-right text-sm font-semibold text-foreground">{spec.value}</dd>
            </div>
          )
        })}
      </dl>
    </DetailSection>
  )
}
