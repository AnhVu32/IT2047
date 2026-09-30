import { proxyJson } from "@/lib/backend"

export async function GET(request: Request) {
  const search = new URL(request.url).search // includes leading "?" when present
  return proxyJson(request, `/v1/properties${search}`)
}
