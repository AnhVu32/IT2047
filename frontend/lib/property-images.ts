export const PROPERTY_IMAGE_FALLBACK = "/placeholder.jpg"

const PROPERTY_IMAGE_MARKER = "/images/"

/**
 * Convert the private MinIO URL stored in PostgreSQL into a same-origin image
 * URL. Other public image URLs are left unchanged.
 */
export function getPropertyImageSrc(value?: string | null): string {
  const rawValue = value?.trim()
  if (!rawValue) return PROPERTY_IMAGE_FALLBACK
  if (rawValue.startsWith("/api/property-images?")) return rawValue

  let pathname = rawValue
  try {
    pathname = new URL(rawValue).pathname
  } catch {
    // The DB may store an object key instead of an absolute URL.
  }

  const markerIndex = pathname.indexOf(PROPERTY_IMAGE_MARKER)
  if (markerIndex === -1 && !pathname.startsWith("images/")) return rawValue

  const encodedPath = markerIndex === -1
    ? pathname
    : pathname.slice(markerIndex + 1)

  let objectPath: string
  try {
    objectPath = decodeURIComponent(encodedPath).replace(/^\/+/, "")
  } catch {
    return PROPERTY_IMAGE_FALLBACK
  }

  if (!objectPath.startsWith("images/")) return PROPERTY_IMAGE_FALLBACK
  return `/api/property-images?path=${encodeURIComponent(objectPath)}`
}
