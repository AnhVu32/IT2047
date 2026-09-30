'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { PropertyCard } from '@/components/property-card'

export function SimilarProperties() {
  const params = useParams<{ id: string }>()
  const [similarProperties, setSimilarProperties] = useState<any[]>([])

  useEffect(() => {
    if (!params.id) return
    const controller = new AbortController()
    fetch(`/api/properties/${encodeURIComponent(params.id)}/similar?limit=6`, {
      signal: controller.signal,
    })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("Similar search failed")))
      .then((payload) => setSimilarProperties(payload.data?.results || []))
      .catch((error) => {
        if (error.name !== "AbortError") setSimilarProperties([])
      })
    return () => controller.abort()
  }, [params.id])

  if (similarProperties.length === 0) return null

  return (
    <div className="space-y-4 pt-6">
      <h2 className="text-xl font-bold text-foreground">Bất động sản tương tự</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {similarProperties.map((property) => (
          <PropertyCard key={property.id} property={property} variant="compact" />
        ))}
      </div>
    </div>
  )
}
