'use client'

import { useEffect, useState } from 'react'
import { DetailSection } from '@/components/property-detail/section'
import { formatPrice } from '@/lib/format'

type Verdict = 'below' | 'within' | 'above'

interface PriceEstimate {
  estimated_price: number
  lower_bound: number
  upper_bound: number
  asking_price: number
  diff_pct: number
  verdict: Verdict
}

const VERDICTS: Record<Verdict, { label: string; className: string }> = {
  below: { label: 'Thấp hơn mức ước tính', className: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' },
  within: { label: 'Sát mức ước tính', className: 'bg-sky-500/10 text-sky-600 dark:text-sky-400' },
  above: { label: 'Cao hơn mức ước tính', className: 'bg-amber-500/10 text-amber-600 dark:text-amber-400' },
}

export function PriceEstimateSection({ propertyId }: { propertyId: string }) {
  const [estimate, setEstimate] = useState<PriceEstimate | null>(null)
  const [unavailable, setUnavailable] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    setEstimate(null)
    setUnavailable(null)
    fetch(`/api/properties/${encodeURIComponent(propertyId)}/price-estimate`, {
      signal: controller.signal,
      cache: 'no-store',
    })
      .then((response) => (response.ok ? response.json() : null))
      .then((payload) => {
        if (payload?.status === 'success') setEstimate(payload.data)
        else if (payload?.status === 'unavailable') setUnavailable(payload.errors?.[0]?.detail || 'Chưa có định giá cho tin này.')
      })
      .catch(() => {})
    return () => controller.abort()
  }, [propertyId])

  // Unscorable listings (missing fields, outside the training domain) say why instead of vanishing.
  if (!estimate) {
    if (!unavailable) return null
    return (
      <DetailSection title="Định giá AI">
        <p className="text-sm text-muted-foreground">Chưa có định giá cho tin này. {unavailable}</p>
      </DetailSection>
    )
  }

  const verdict = VERDICTS[estimate.verdict]
  const diff = `${estimate.diff_pct > 0 ? '+' : ''}${estimate.diff_pct.toLocaleString('vi-VN')}%`

  return (
    <DetailSection title="Định giá AI" description="So sánh giá rao với mức giá mô hình học máy ước tính cho khu vực này.">
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <p className="text-sm text-muted-foreground">Giá ước tính</p>
          <p className="text-2xl font-bold text-foreground">{formatPrice(estimate.estimated_price)}</p>
          <p className="text-sm text-muted-foreground">
            Khoảng {formatPrice(estimate.lower_bound)} – {formatPrice(estimate.upper_bound)}
          </p>
        </div>
        <div>
          <p className="text-sm text-muted-foreground">Giá rao</p>
          <p className="text-2xl font-bold text-foreground">{formatPrice(estimate.asking_price)}</p>
          <span className={`mt-1 inline-block rounded-full px-2.5 py-0.5 text-sm font-medium ${verdict.className}`}>
            {verdict.label} ({diff})
          </span>
        </div>
      </div>
      <p className="mt-4 text-xs text-muted-foreground">
        Ước tính tham khảo dựa trên diện tích, số phòng ngủ, vị trí và pháp lý của các tin đăng đã thu thập; không
        phải giá thẩm định hay giá giao dịch.
      </p>
    </DetailSection>
  )
}
