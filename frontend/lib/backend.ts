// Single source of truth for the FastAPI backend base URL used by all
// app/api/* proxy routes (avoids re-declaring BACKEND_URL in each file).
export const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8001"

// Forward the caller's Authorization header (if any) to the backend so
// authenticated proxy calls carry the bearer token.
export function forwardAuthHeaders(request: Request): HeadersInit {
  const headers: Record<string, string> = { "Content-Type": "application/json" }
  const auth = request.headers.get("authorization")
  if (auth) headers["Authorization"] = auth
  return headers
}

// Shared proxy for every app/api/* route: forwards method + auth + body to the
// backend and passes the backend's JSON body and status straight back. Network
// failures return a consistent { error } shape so the client can surface them.
export async function proxyJson(
  request: Request,
  backendPath: string,
  opts: { method?: string } = {},
): Promise<Response> {
  const method = (opts.method || request.method || "GET").toUpperCase()
  const init: RequestInit = {
    method,
    headers: forwardAuthHeaders(request),
    cache: "no-store",
  }
  if (method !== "GET" && method !== "HEAD") {
    init.body = await request.text()
  }
  try {
    const response = await fetch(`${BACKEND_URL}${backendPath}`, init)
    const text = await response.text()
    const data = text ? JSON.parse(text) : null
    return Response.json(data, { status: response.status })
  } catch (error) {
    return Response.json(
      { error: error instanceof Error ? error.message : "Upstream request failed" },
      { status: 502 },
    )
  }
}
