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
    <section className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-foreground">Bất động sản tương tự</h2>
        <p className="text-sm text-muted-foreground">Các tin đăng có nội dung tương đồng với căn này.</p>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {similarProperties.map((property) => (
          <PropertyCard key={property.id} property={property} variant="compact" />
        ))}
      </div>
    </section>
  )
}
