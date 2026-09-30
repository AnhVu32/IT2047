import { proxyJson } from "@/lib/backend"

export async function POST(request: Request) {
  return proxyJson(request, "/v1/properties/ai-search")
}
