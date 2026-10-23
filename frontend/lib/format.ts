// Display helpers for listing values. Prices are stored in tỷ VNĐ (1 tỷ = 1e9 VNĐ).

function toNumber(value?: string | number | null): number | null {
  if (value === null || value === undefined || value === "") return null
  const num = typeof value === "number" ? value : parseFloat(value)
  return Number.isFinite(num) ? num : null
}

const vi = (value: number, digits = 2) => value.toLocaleString("vi-VN", { maximumFractionDigits: digits })

/** "5,5 tỷ", "850 triệu", or "Thỏa thuận" when the price is missing. */
export function formatPrice(price?: string | number | null): string {
  const ty = toNumber(price)
  if (ty === null) {
    return price === null || price === undefined || price === "" ? "Thỏa thuận" : String(price)
  }
  if (ty > 0 && ty < 1) return `${vi(ty * 1000, 0)} triệu`
  return `${vi(ty)} tỷ`
}

/** "62,5 triệu/m²", or null when price or area is unusable. */
export function formatPricePerM2(price?: string | number | null, area?: number | null): string | null {
  const ty = toNumber(price)
  if (ty === null || !area || area <= 0) return null
  const millionsPerM2 = (ty * 1000) / area
  return `${vi(millionsPerM2, 1)} triệu/m²`
}

export function formatDate(dateString?: string | null): string | null {
  if (!dateString) return null
  const date = new Date(dateString)
  if (Number.isNaN(date.getTime())) return dateString
  return date.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" })
}

// The dataset stores tiers as e.g. "Tin VIP Kim Cương", so match on the tier name.
export function getListingBadge(listingType?: string | null) {
  if (listingType?.includes("VIP Kim Cương")) return { className: "bg-price text-white", text: "VIP Kim Cương" }
  if (listingType?.includes("VIP Vàng")) return { className: "bg-amber-500 text-white", text: "VIP Vàng" }
  return null
}
