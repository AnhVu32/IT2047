"use client"

import { useEffect, useState } from "react"
import Image from "next/image"
import Link from "next/link"
import { Heart, MapPin, Camera, Bed, Bath } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { useAuth } from "@/lib/auth-context"
import { getSavedListingIds, setSavedListing } from "@/lib/feedback"
import { getPropertyImageSrc, PROPERTY_IMAGE_FALLBACK } from "@/lib/property-images"
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

const getBadgeStyle = (listingType?: string | null) => {
  if (listingType === "VIP Kim Cương") {
    return { bg: "bg-[#E03C31]", text: "VIP KIM CƯƠNG" }
  } else if (listingType === "VIP Vàng") {
    return { bg: "bg-orange-500", text: "VIP VÀNG" }
  }
  return null
}

const formatDate = (dateString?: string | null) => {
  if (!dateString) return "Chưa cập nhật"

  try {
    const date = new Date(dateString)
    if (Number.isNaN(date.getTime())) return dateString
    const day = String(date.getDate()).padStart(2, "0")
    const month = String(date.getMonth() + 1).padStart(2, "0")
    const year = date.getFullYear()
    return `${day}/${month}/${year}`
  } catch {
    return dateString
  }
}

const formatPrice = (price?: string | number | null) => {
  if (price === null || price === undefined || price === "") return "Liên hệ"
  return `${price} Tỷ VNĐ`
}

export function PropertyCard({ property, variant = "list" }: PropertyCardProps) {
  const hasPropertyImage = Boolean(property.images?.[0]?.trim())
  const imageUrl = getPropertyImageSrc(property.images?.[0])
  const badgeStyle = getBadgeStyle(property.listing_type)
  const { user } = useAuth()
  const [saved, setSaved] = useState(false)
  const [imageFailed, setImageFailed] = useState(!hasPropertyImage)
  const isCompact = variant === "compact"

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
    // Save full property data to sessionStorage
    sessionStorage.setItem('selectedProperty', JSON.stringify(property))
  }

  const handleSave = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const next = !saved
    setSaved(next)
    setSavedListing(listingId, next, "search_bar")
  }

  return (
    <Link href={`/chi-tiet/${property.id}`} onClick={handleCardClick} className="block h-full">
      <article className="h-full bg-card border border-border rounded-lg overflow-hidden hover:shadow-md transition-shadow cursor-pointer">
        <div className={cn("flex h-full flex-col", !isCompact && "md:flex-row")}>
          {/* Image Section - Left Side */}
          <div
            className={cn(
              "relative w-full flex-shrink-0",
              isCompact
                ? "h-48 sm:h-52"
                : "h-[200px] md:h-auto md:min-h-[220px] md:w-[280px] lg:w-[320px]",
            )}
          >
            <Image
              src={imageFailed ? PROPERTY_IMAGE_FALLBACK : imageUrl}
              alt={property.title || "Hình ảnh bất động sản"}
              fill
              className="object-cover"
              onError={() => setImageFailed(true)}
            />
            
            {/* Badge - Only show if not "Tin thường" */}
            {badgeStyle && (
              <div className="absolute top-3 left-3">
                <Badge className={`${badgeStyle.bg} hover:${badgeStyle.bg} text-white text-xs font-medium px-2 py-1`}>
                  {badgeStyle.text}
                </Badge>
              </div>
            )}

            {/* Make it clear that the repeated fallback is not a MinIO image. */}
            {imageFailed && (
              <div className="absolute bottom-3 left-3 rounded bg-black/60 px-2 py-1 text-xs text-white">
                Ảnh minh họa
              </div>
            )}

            {/* Photo Count */}
            {!imageFailed && property.images && property.images.length > 0 && (
              <div className="absolute bottom-3 right-3 bg-black/60 text-white text-xs px-2 py-1 rounded flex items-center gap-1">
                <Camera className="h-3 w-3" />
                <span>{property.images.length}</span>
              </div>
            )}
          </div>

          {/* Content Section - Right Side */}
          <div className="flex min-w-0 flex-1 flex-col p-4">
            {/* Title & Favorite */}
            <div className="flex items-start justify-between gap-2 mb-2">
              <h3 className="font-semibold text-foreground line-clamp-2 flex-1">
                {property.title || "Bất động sản chưa cập nhật tiêu đề"}
              </h3>
              <button
                type="button"
                aria-label="Lưu tin"
                className="p-1.5 hover:bg-muted rounded-full transition-colors flex-shrink-0"
                onClick={handleSave}
              >
                <Heart className={`h-5 w-5 ${saved ? "fill-[#E03C31] text-[#E03C31]" : "text-muted-foreground"}`} />
              </button>
            </div>

            {/* Price & Area */}
            <div className={cn("mb-2 flex items-center", isCompact ? "gap-2" : "gap-3")}>
              <span className={cn("font-bold text-[#E03C31]", isCompact ? "text-base" : "text-lg")}>
                {formatPrice(property.price_range)}
              </span>
              {property.area !== null && property.area !== undefined && (
                <>
                  <span className="text-muted-foreground">|</span>
                  <span className="whitespace-nowrap text-muted-foreground">{property.area} m²</span>
                </>
              )}
            </div>

            {/* Location */}
            <div className="flex items-center gap-1.5 text-sm text-muted-foreground mb-3">
              <MapPin className="h-4 w-4 flex-shrink-0" />
              <span className="line-clamp-1">{property.address || "Địa chỉ đang cập nhật"}</span>
            </div>

            {/* Description */}
            {!isCompact && (
              <p className="mb-4 line-clamp-2 flex-1 text-sm text-muted-foreground">
                {property.description || "Thông tin mô tả đang được cập nhật."}
              </p>
            )}

            {/* Specs - Bedrooms & Bathrooms */}
            <div className="mb-3 flex min-h-5 items-center gap-4">
              {property.bedrooms !== null && property.bedrooms !== undefined && (
                <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                  <Bed className="h-4 w-4" />
                  <span>{property.bedrooms} phòng</span>
                </div>
              )}
              {property.bathrooms !== null && property.bathrooms !== undefined && (
                <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                  <Bath className="h-4 w-4" />
                  <span>{property.bathrooms} phòng tắm</span>
                </div>
              )}
            </div>

            {/* Footer - Posted Date or View Details Button */}
            <div className="flex items-center justify-between pt-3 border-t border-border">
              <p className="text-xs text-muted-foreground">
                {formatDate(property.posted_date)}
              </p>
              {isCompact ? (
                <span className="text-sm font-medium text-[#E03C31]">Xem chi tiết</span>
              ) : (
                <Button className="bg-[#E03C31] hover:bg-[#c43428] text-white h-9 px-4 text-sm">
                  Xem chi tiết
                </Button>
              )}
            </div>
          </div>
        </div>
      </article>
    </Link>
  )
}
