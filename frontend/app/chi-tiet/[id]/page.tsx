'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Phone } from 'lucide-react'
import { useParams } from 'next/navigation'
import { Header } from '@/components/header'
import { Footer } from '@/components/footer'
import { PropertyDetailBreadcrumb } from '@/components/property-detail/breadcrumb'
import { ImageGallery } from '@/components/property-detail/image-gallery'
import { PropertyHeader } from '@/components/property-detail/property-header'
import { QuickSpecsGrid } from '@/components/property-detail/quick-specs-grid'
import { DescriptionSection } from '@/components/property-detail/description-section'
import { AmenitiesSection } from '@/components/property-detail/amenities-section'
import { LocationSection } from '@/components/property-detail/location-section'
import { KnowledgeGraphSection } from '@/components/property-detail/knowledge-graph-section'
import { ContactForm } from '@/components/property-detail/contact-form'
import { SimilarProperties } from '@/components/property-detail/similar-properties'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { sendInteraction } from '@/lib/feedback'
import { formatPrice, formatPricePerM2 } from '@/lib/format'

interface PropertyData {
  id: string
  listing_id?: number | string
  title: string
  price_range: string
  area: number | null
  address: string
  location_link?: string | null
  latitude_longitude?: string | null
  description: string
  images: string[]
  listing_type: string
  bedrooms: number | null
  bathrooms: number | null
  legal_status: string | null
  furnishing: string | null
  balcony_direction: string | null
  house_direction: string | null
  posted_date: string
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

export default function PropertyDetailPage() {
  const params = useParams<{ id: string }>()
  const propertyId = params?.id
  const [property, setProperty] = useState<PropertyData | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!propertyId) return

    const controller = new AbortController()
    let hasCachedProperty = false
    setIsLoading(true)

    // Use the card payload for an instant first paint, but always refresh from
    // the backend so direct links and browser refreshes work as expected.
    const selectedProperty = sessionStorage.getItem('selectedProperty')
    if (selectedProperty) {
      try {
        const parsedProperty = JSON.parse(selectedProperty) as PropertyData
        const cachedIds = [parsedProperty.id, parsedProperty.listing_id].filter(Boolean).map(String)
        if (cachedIds.includes(String(propertyId))) {
          setProperty(parsedProperty)
          hasCachedProperty = true
          setIsLoading(false)
        }
      } catch (err) {
        console.error('Error parsing selected property:', err)
      }
    }

    fetch(`/api/properties/${encodeURIComponent(propertyId)}`, {
      signal: controller.signal,
      cache: 'no-store',
    })
      .then(async (response) => {
        const payload = await response.json().catch(() => ({}))
        if (!response.ok) throw new Error(payload.error || 'Failed to fetch property')
        return payload
      })
      .then((payload) => {
        if (!payload.data) throw new Error('Property not found')
        setProperty(payload.data)
        sessionStorage.setItem('selectedProperty', JSON.stringify(payload.data))
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        if (!hasCachedProperty) setProperty(null)
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false)
      })

    return () => controller.abort()
  }, [propertyId])

  // Record a `view` on open and the accumulated dwell time on leave.
  const propertyListingKey = property ? String(property.listing_id ?? property.id) : null
  useEffect(() => {
    if (!propertyListingKey) return
    const listingId = propertyListingKey
    const openedAt = Date.now()
    return () => {
      const dwell = (Date.now() - openedAt) / 1000
      sendInteraction({
        listing_id: listingId,
        action_type: "view",
        source: "detail",
        dwell_time_seconds: dwell,
      })
    }
  }, [propertyListingKey])

  const shell = (content: React.ReactNode) => (
    <div className="min-h-screen flex flex-col bg-background">
      <header className="sticky top-0 z-40 w-full">
        <Header />
      </header>
      {content}
      <Footer />
    </div>
  )

  if (isLoading) {
    return shell(
      <main className="flex-1 container mx-auto px-4 py-6">
        <Skeleton className="h-5 w-40 mb-4" />
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="space-y-4">
            <Skeleton className="aspect-[16/10] w-full rounded-xl" />
            <Skeleton className="h-40 w-full rounded-xl" />
          </div>
          <Skeleton className="h-80 w-full rounded-xl" />
        </div>
      </main>,
    )
  }

  if (!property) {
    return shell(
      <main className="flex-1 container mx-auto px-4 py-16">
        <div className="mx-auto max-w-md text-center space-y-3">
          <h2 className="text-2xl font-bold text-foreground">Không tìm thấy bất động sản</h2>
          <p className="text-muted-foreground">Tin đăng có thể đã hết hạn hoặc bị gỡ. Hãy quay lại danh sách để xem các lựa chọn khác.</p>
          <Button asChild className="mt-2">
            <Link href="/">Quay lại danh sách</Link>
          </Button>
        </div>
      </main>,
    )
  }

  const pricePerM2 = formatPricePerM2(property.price_range, property.area)

  return shell(
    <>
      <main className="flex-1 container mx-auto px-4 py-6 pb-28 lg:pb-6">
        <PropertyDetailBreadcrumb property={property} />

        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="min-w-0 space-y-6">
            <ImageGallery images={property.images} title={property.title} />
            <PropertyHeader property={property} />
            <QuickSpecsGrid property={property} />
            <DescriptionSection description={property.description} />
            <AmenitiesSection property={property} />
            <LocationSection
              address={property.address}
              locationLink={property.location_link}
              latitudeLongitude={property.latitude_longitude}
            />
            <KnowledgeGraphSection propertyId={String(propertyId || property.listing_id || property.id)} />
          </div>

          <aside className="lg:sticky lg:top-20 lg:self-start">
            <ContactForm listingId={property.listing_id ?? property.id} />
          </aside>
        </div>

        <div className="mt-10">
          <SimilarProperties />
        </div>
      </main>

      {/* Mobile: keep price and the contact action reachable while scrolling. */}
      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card/95 px-4 py-3 backdrop-blur lg:hidden">
        <div className="flex items-center gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-lg font-bold leading-tight text-price">{formatPrice(property.price_range)}</p>
            {pricePerM2 && <p className="text-xs text-muted-foreground">{pricePerM2}</p>}
          </div>
          <Button asChild className="h-11 px-5">
            <a href="#lien-he">
              <Phone className="h-4 w-4" />
              Liên hệ tư vấn
            </a>
          </Button>
        </div>
      </div>
    </>,
  )
}
