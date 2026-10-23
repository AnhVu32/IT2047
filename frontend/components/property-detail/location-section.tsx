'use client'

import { ExternalLink, MapPin } from 'lucide-react'
import { DetailSection } from '@/components/property-detail/section'

interface LocationSectionProps {
  address: string
  locationLink?: string | null
  latitudeLongitude?: string | null
}

function parseCoordinates(value?: string | null): [number, number] | null {
  if (!value) return null

  let candidate = value.trim()
  try {
    const url = new URL(candidate)
    candidate = url.searchParams.get('q') || candidate
  } catch {
    // The dataset also stores coordinates as `q=lat,lng` or `lat,lng`.
  }

  const query = candidate.match(/(?:^|[?&])q=([^&]+)/i)?.[1]
  if (query) {
    try {
      candidate = decodeURIComponent(query)
    } catch {
      candidate = query
    }
  }

  const match = candidate.match(/^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/)
  if (!match) return null

  const latitude = Number(match[1])
  const longitude = Number(match[2])
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null
  if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) return null

  return [latitude, longitude]
}

export function LocationSection({ address, locationLink, latitudeLongitude }: LocationSectionProps) {
  const coordinates =
    parseCoordinates(latitudeLongitude) || parseCoordinates(locationLink)
  const coordinateQuery = coordinates ? `${coordinates[0]},${coordinates[1]}` : address
  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY?.trim()
  const mapSrc = apiKey
    ? `https://www.google.com/maps/embed/v1/place?key=${encodeURIComponent(apiKey)}&q=${encodeURIComponent(coordinateQuery)}`
    : `https://www.google.com/maps?q=${encodeURIComponent(coordinateQuery)}&z=16&output=embed`

  const externalMapUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(coordinateQuery)}`

  return (
    <DetailSection
      title="Vị trí"
      id="vi-tri"
      action={
        <a
          href={externalMapUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 text-sm font-medium text-primary hover:underline"
        >
          Mở Google Maps
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      }
    >
      <p className="mb-3 flex items-start gap-1.5 text-sm text-muted-foreground">
        <MapPin className="mt-0.5 h-4 w-4 flex-shrink-0 text-primary" />
        {address}
      </p>
      <div className="relative aspect-[16/9] w-full overflow-hidden rounded-lg border border-border bg-muted">
        <iframe
          src={mapSrc}
          width="100%"
          height="100%"
          style={{ border: 0 }}
          allowFullScreen={true}
          loading="lazy"
          referrerPolicy="strict-origin-when-cross-origin"
          title={`Bản đồ vị trí: ${address}`}
          className="h-full w-full"
        />
      </div>
    </DetailSection>
  )
}
