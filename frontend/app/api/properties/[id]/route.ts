import { proxyJson } from "@/lib/backend"

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params
  if (!id) {
    return Response.json({ error: "Missing property ID" }, { status: 400 })
  }
  return proxyJson(request, `/v1/properties/${encodeURIComponent(id)}`)
}
