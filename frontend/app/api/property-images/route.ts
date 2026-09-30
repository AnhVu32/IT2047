import { BACKEND_URL } from "@/lib/backend"

export async function GET(request: Request) {
  const path = new URL(request.url).searchParams.get("path")?.trim()
  if (!path || !path.startsWith("images/") || path.split("/").some((part) => part === "..")) {
    return Response.json({ error: "Invalid property image path" }, { status: 400 })
  }

  try {
    const upstream = await fetch(
      `${BACKEND_URL}/v1/properties/image?path=${encodeURIComponent(path)}`,
      { cache: "no-store" },
    )
    if (!upstream.ok || !upstream.body) {
      return new Response(null, { status: upstream.status || 502 })
    }

    const headers = new Headers()
    headers.set("Content-Type", upstream.headers.get("content-type") || "application/octet-stream")
    headers.set(
      "Cache-Control",
      upstream.headers.get("cache-control") || "public, max-age=86400, stale-while-revalidate=604800",
    )
    const contentLength = upstream.headers.get("content-length")
    if (contentLength) headers.set("Content-Length", contentLength)

    return new Response(upstream.body, { status: 200, headers })
  } catch {
    return new Response(null, { status: 502 })
  }
}
