"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useAuth } from "@/lib/auth-context"

export default function LoginPage() {
  const { login } = useAuth()
  const router = useRouter()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(username.trim(), password)
      router.push("/tim-kiem-chuyen-sau")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Đăng nhập thất bại")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/30 px-4">
      <div className="w-full max-w-sm bg-card border border-border rounded-xl p-6 shadow-sm">
        <h1 className="text-xl font-bold text-foreground mb-1">Đăng nhập</h1>
        <p className="text-sm text-muted-foreground mb-6">Đăng nhập để lưu lịch sử trò chuyện và nhận gợi ý cá nhân hóa.</p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-sm font-medium text-foreground">Tên đăng nhập</label>
            <Input value={username} onChange={(e) => setUsername(e.target.value)} className="mt-1" autoFocus required />
          </div>
          <div>
            <label className="text-sm font-medium text-foreground">Mật khẩu</label>
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1" required />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <Button type="submit" disabled={loading || !username.trim() || !password} className="w-full bg-[#E03C31] hover:bg-[#c43428] text-white">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Đăng nhập"}
          </Button>
        </form>
        <p className="text-sm text-muted-foreground mt-4 text-center">
          Chưa có tài khoản? <Link href="/dang-ky" className="text-[#E03C31] font-medium">Đăng ký</Link>
        </p>
      </div>
    </div>
  )
}
