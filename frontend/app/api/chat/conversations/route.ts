import { proxyJson } from "@/lib/backend"

export async function GET(request: Request) {
  return proxyJson(request, "/v1/chat/conversations")
}
