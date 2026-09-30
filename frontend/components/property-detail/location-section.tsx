'use client'

import { MapPin } from 'lucide-react'

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

  return (
    <div className="space-y-3 pb-4 border-b border-border">
      <h2 className="text-xl font-bold text-foreground">Vị trí trên bản đồ</h2>
      <div className="relative w-full aspect-video rounded-lg overflow-hidden bg-muted border border-border group">
        <iframe
          src={mapSrc}
          width="100%"
          height="100%"
          style={{ border: 0, borderRadius: '8px' }}
          allowFullScreen={true}
          loading="lazy"
          referrerPolicy="strict-origin-when-cross-origin"
          title={`Bản đồ vị trí: ${address}`}
          className="w-full h-full"
        />
      </div>

      {/* Address Info */}
      <div className="flex items-start gap-2 p-3 bg-card rounded-lg">
        <MapPin className="h-5 w-5 text-[#E03C31] flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-foreground">Địa chỉ</p>
          <p className="text-sm text-muted-foreground">{address}</p>
        </div>
      </div>
    </div>
  )
}
