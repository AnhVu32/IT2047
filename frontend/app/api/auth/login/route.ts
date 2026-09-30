import { proxyJson } from "@/lib/backend"

export async function POST(request: Request) {
  return proxyJson(request, "/v1/auth/login")
}
