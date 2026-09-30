import { proxyJson } from "@/lib/backend"

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params
  return proxyJson(request, `/v1/chat/conversations/${encodeURIComponent(id)}`)
}
