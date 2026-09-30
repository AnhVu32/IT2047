'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
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
import { SellerCard } from '@/components/property-detail/seller-card'
import { ContactForm } from '@/components/property-detail/contact-form'
import { SimilarProperties } from '@/components/property-detail/similar-properties'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { sendInteraction } from '@/lib/feedback'

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

  if (isLoading) {
    return (
      <div className="min-h-screen flex flex-col bg-background">
        <header className="sticky top-0 z-50 w-full bg-background shadow-sm">
          <Header />
        </header>

        <main className="flex-1 container mx-auto px-4 py-6">
          <div className="space-y-6">
            <Skeleton className="h-8 w-1/3" />
            <Skeleton className="h-96 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        </main>

        <Footer />
      </div>
    )
  }

  if (!property) {
    return (
      <div className="min-h-screen flex flex-col bg-background">
        <header className="sticky top-0 z-50 w-full bg-background shadow-sm">
          <Header />
        </header>

        <main className="flex-1 container mx-auto px-4 py-12">
          <div className="text-center space-y-4">
            <h2 className="text-2xl font-bold text-foreground">Không tìm thấy dữ liệu</h2>
            <p className="text-muted-foreground">Vui lòng quay lại trang chủ và chọn một bất động sản khác.</p>
            <Link href="/">
              <Button className="bg-[#E03C31] hover:bg-[#c43428] text-white">
                Quay lại trang chủ
              </Button>
            </Link>
          </div>
        </main>

        <Footer />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <header className="sticky top-0 z-50 w-full bg-background shadow-sm">
        <Header />
      </header>

      <main className="flex-1 container mx-auto px-4 py-6">
        <div className="space-y-6">
          {/* Breadcrumb */}
          <PropertyDetailBreadcrumb property={property} />

          {/* Main 2-Column Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Column - Main Content (70%) */}
            <div className="lg:col-span-2 space-y-6">
              {/* Image Gallery */}
              <ImageGallery images={property.images} title={property.title} />

              {/* Property Header Info */}
              <PropertyHeader property={property} />

              {/* Quick Specs Grid */}
              <QuickSpecsGrid property={property} />

              {/* Description Section */}
              <DescriptionSection description={property.description} />

              {/* Amenities Section */}
              <AmenitiesSection property={property} />

              {/* Location Map Section */}
              <LocationSection
                address={property.address}
                locationLink={property.location_link}
                latitudeLongitude={property.latitude_longitude}
              />

              {/* Knowledge Graph Section */}
              <KnowledgeGraphSection propertyId={String(propertyId || property.listing_id || property.id)} />

              {/* Similar Properties */}
              <SimilarProperties />
            </div>

            {/* Right Column - Sidebar (30%) */}
            <div className="lg:col-span-1">
              <div className="sticky top-24">
                <div className="space-y-4">
                  {/* Seller Contact Card */}
                  <SellerCard />

                  {/* Contact Form */}
                  <ContactForm listingId={property.listing_id ?? property.id} />
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  )
}
