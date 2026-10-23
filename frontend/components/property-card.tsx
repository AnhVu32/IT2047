"use client"

import { useEffect, useState } from "react"
import Image from "next/image"
import Link from "next/link"
import { Heart, MapPin, Camera, Bed, Bath, Maximize, ArrowRight } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { getSavedListingIds, setSavedListing } from "@/lib/feedback"
import { getPropertyImageSrc, PROPERTY_IMAGE_FALLBACK } from "@/lib/property-images"
import { formatDate, formatPrice, formatPricePerM2, getListingBadge } from "@/lib/format"
import { cn } from "@/lib/utils"

interface PropertyCardProps {
  property: {
    id: string | number
    listing_id?: number | string
    title?: string | null
    price_range?: string | number | null
    area: number | null
    address?: string | null
    description?: string | null
    images?: string[] | null
    listing_type?: string | null
    bedrooms: number | null
    bathrooms: number | null
    posted_date?: string | null
  }
  variant?: "list" | "compact"
}

export function PropertyCard({ property, variant = "list" }: PropertyCardProps) {
  const hasPropertyImage = Boolean(property.images?.[0]?.trim())
  const imageUrl = getPropertyImageSrc(property.images?.[0])
  const badge = getListingBadge(property.listing_type)
  const { user } = useAuth()
  const [saved, setSaved] = useState(false)
  const [imageFailed, setImageFailed] = useState(!hasPropertyImage)
  const isCompact = variant === "compact"
  const pricePerM2 = formatPricePerM2(property.price_range, property.area)
  const postedDate = formatDate(property.posted_date)

  const listingId = property.listing_id ?? property.id

  // Reflect the real saved state on load (and when the user logs in/out).
  useEffect(() => {
    let active = true
    getSavedListingIds().then((set) => {
      if (active) setSaved(set.has(Number(listingId)))
    })
    return () => {
      active = false
    }
  }, [user, listingId])

  const handleCardClick = () => {
    // Lets the detail page paint instantly from the card payload.
    sessionStorage.setItem('selectedProperty', JSON.stringify(property))
  }

  const handleSave = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const next = !saved
    setSaved(next)
    setSavedListing(listingId, next, "search_bar")
  }

  const specs = [
    property.area !== null && property.area !== undefined && { icon: Maximize, text: `${property.area} m²` },
    property.bedrooms !== null && property.bedrooms !== undefined && { icon: Bed, text: `${property.bedrooms} PN` },
    property.bathrooms !== null && property.bathrooms !== undefined && { icon: Bath, text: `${property.bathrooms} WC` },
  ].filter(Boolean) as { icon: typeof Bed; text: string }[]

  return (
    // The card adapts to its container (not the viewport) so it also fits inside chat bubbles.
    <Link href={`/chi-tiet/${property.id}`} onClick={handleCardClick} className="@container group block h-full">
      <article className="h-full overflow-hidden rounded-xl border border-border bg-card transition-all hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-lg">
        <div className={cn("flex h-full flex-col", !isCompact && "@lg:flex-row")}>
          <div
            className={cn(
              "relative w-full flex-shrink-0 overflow-hidden bg-muted",
              isCompact ? "aspect-[4/3]" : "aspect-[16/10] @lg:aspect-auto @lg:min-h-[210px] @lg:w-[42%] @3xl:w-[300px]",
            )}
          >
            <Image
              src={imageFailed ? PROPERTY_IMAGE_FALLBACK : imageUrl}
              alt={property.title || "Hình ảnh bất động sản"}
              fill
              className="object-cover transition-transform duration-500 group-hover:scale-105"
              onError={() => setImageFailed(true)}
            />

            {badge && (
              <span className={cn("absolute left-3 top-3 rounded-md px-2 py-0.5 text-xs font-semibold shadow-sm", badge.className)}>
                {badge.text}
              </span>
            )}

            <button
              type="button"
              aria-label={saved ? "Bỏ lưu tin" : "Lưu tin"}
              aria-pressed={saved}
              className="absolute right-3 top-3 rounded-full bg-white/90 p-2 shadow-sm transition-colors hover:bg-white"
              onClick={handleSave}
            >
              <Heart className={cn("h-4 w-4", saved ? "fill-price text-price" : "text-slate-600")} />
            </button>

            {/* Make it clear that the repeated fallback is not a real photo of the listing. */}
            {imageFailed ? (
              <span className="absolute bottom-3 left-3 rounded bg-black/60 px-2 py-0.5 text-xs text-white">Ảnh minh họa</span>
            ) : (
              property.images && property.images.length > 1 && (
                <span className="absolute bottom-3 right-3 flex items-center gap-1 rounded bg-black/60 px-2 py-0.5 text-xs text-white">
                  <Camera className="h-3 w-3" />
                  {property.images.length}
                </span>
              )
            )}
          </div>

          <div className="flex min-w-0 flex-1 flex-col p-4">
            <h3 className="line-clamp-2 font-semibold leading-snug text-foreground transition-colors group-hover:text-primary">
              {property.title || "Bất động sản chưa cập nhật tiêu đề"}
            </h3>

            <div className="mt-2 flex flex-wrap items-baseline gap-x-2">
              <span className={cn("font-bold text-price", isCompact ? "text-lg" : "text-xl")}>
                {formatPrice(property.price_range)}
              </span>
              {pricePerM2 && <span className="text-xs text-muted-foreground">~{pricePerM2}</span>}
            </div>

            {specs.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {specs.map(({ icon: Icon, text }) => (
                  <span key={text} className="flex items-center gap-1 rounded-md bg-muted px-2 py-1 text-xs font-medium text-foreground">
                    <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                    {text}
                  </span>
                ))}
              </div>
            )}

            <p className="mt-2.5 flex items-start gap-1.5 text-sm text-muted-foreground">
              <MapPin className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <span className="line-clamp-1">{property.address || "Địa chỉ đang cập nhật"}</span>
            </p>

            {!isCompact && property.description && (
              <p className="mt-2 hidden text-sm text-muted-foreground @lg:line-clamp-2">{property.description}</p>
            )}

            <div className="mt-auto flex items-center justify-between pt-3 text-xs text-muted-foreground">
              <span>{postedDate ? `Đăng ${postedDate}` : ""}</span>
              <span className="flex items-center gap-1 font-medium text-primary">
                Xem chi tiết
                <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
              </span>
            </div>
          </div>
        </div>
      </article>
    </Link>
  )
}
