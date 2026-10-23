'use client'

import { DetailSection } from '@/components/property-detail/section'
import {
  Waves,
  Dumbbell,
  TreePine,
  Flame,
  Play,
  Trophy,
  Lock,
  Clock,
  ArrowUp,
  ParkingCircle,
  Train,
  Bus,
  Zap,
  School,
  Hospital,
  ShoppingCart,
  Store,
  Leaf,
  Sprout,
  Building2,
  DoorOpen,
  Trees,
  Warehouse,
  LayoutGrid,
} from 'lucide-react'

interface AmenitiesSectionProps {
  property: {
    pool: boolean
    gym: boolean
    park: boolean
    bbq: boolean
    kids_playground: boolean
    sports_court: boolean
    security_24h: boolean
    reception: boolean
    elevator: boolean
    parking: boolean
    near_metro: boolean
    near_bus: boolean
    near_highway: boolean
    near_school: boolean
    near_hospital: boolean
    near_mall: boolean
    near_market: boolean
    near_park: boolean
    river_view: boolean
    park_view: boolean
    city_view: boolean
    balcony: boolean
    garden: boolean
    garage: boolean
    terrace: boolean
  }
}

const amenityMap = [
  { key: 'pool', label: 'Bể bơi', icon: Waves },
  { key: 'gym', label: 'Phòng tập', icon: Dumbbell },
  { key: 'park', label: 'Công viên', icon: TreePine },
  { key: 'bbq', label: 'Khu BBQ', icon: Flame },
  { key: 'kids_playground', label: 'Sân chơi trẻ em', icon: Play },
  { key: 'sports_court', label: 'Sân thể thao', icon: Trophy },
  { key: 'security_24h', label: 'Bảo vệ 24/7', icon: Lock },
  { key: 'reception', label: 'Lễ tân', icon: Clock },
  { key: 'elevator', label: 'Thang máy', icon: ArrowUp },
  { key: 'parking', label: 'Bãi đỗ xe', icon: ParkingCircle },
  { key: 'near_metro', label: 'Gần tàu điện', icon: Train },
  { key: 'near_bus', label: 'Gần xe buýt', icon: Bus },
  { key: 'near_highway', label: 'Gần đường cao tốc', icon: Zap },
  { key: 'near_school', label: 'Gần trường học', icon: School },
  { key: 'near_hospital', label: 'Gần bệnh viện', icon: Hospital },
  { key: 'near_mall', label: 'Gần trung tâm thương mại', icon: ShoppingCart },
  { key: 'near_market', label: 'Gần chợ', icon: Store },
  { key: 'near_park', label: 'Gần công viên', icon: Leaf },
  { key: 'river_view', label: 'View sông', icon: Waves },
  { key: 'park_view', label: 'View công viên', icon: Sprout },
  { key: 'city_view', label: 'View thành phố', icon: Building2 },
  { key: 'balcony', label: 'Ban công', icon: DoorOpen },
  { key: 'garden', label: 'Vườn', icon: Trees },
  { key: 'garage', label: 'Garage', icon: Warehouse },
  { key: 'terrace', label: 'Sân thượng', icon: LayoutGrid },
] as const

export function AmenitiesSection({ property }: AmenitiesSectionProps) {
  const activeAmenities = amenityMap.filter((amenity) => property[amenity.key as keyof Omit<AmenitiesSectionProps['property'], never>])

  if (activeAmenities.length === 0) return null

  return (
    <DetailSection title="Tiện ích nội/ngoại khu" description={`${activeAmenities.length} tiện ích nổi bật`}>
      <ul className="grid grid-cols-2 gap-2 md:grid-cols-3">
        {activeAmenities.map((amenity) => {
          const Icon = amenity.icon
          return (
            <li key={amenity.key} className="flex items-center gap-2.5 rounded-lg bg-muted/60 px-3 py-2.5">
              <Icon className="h-4 w-4 flex-shrink-0 text-primary" />
              <span className="text-sm font-medium text-foreground">{amenity.label}</span>
            </li>
          )
        })}
      </ul>
    </DetailSection>
  )
}
