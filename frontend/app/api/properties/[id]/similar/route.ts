import { proxyJson } from "@/lib/backend"

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params
  const limit = new URL(request.url).searchParams.get("limit") || "6"
  return proxyJson(
    request,
    `/v1/properties/${encodeURIComponent(id)}/similar?limit=${encodeURIComponent(limit)}`,
  )
}
