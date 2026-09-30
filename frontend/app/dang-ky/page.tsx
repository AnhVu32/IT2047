"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useAuth } from "@/lib/auth-context"

export default function RegisterPage() {
  const { register } = useAuth()
  const router = useRouter()
  const [username, setUsername] = useState("")
  const [displayName, setDisplayName] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await register(username.trim(), password, displayName.trim() || undefined)
      router.push("/tim-kiem-chuyen-sau")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Đăng ký thất bại")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/30 px-4">
      <div className="w-full max-w-sm bg-card border border-border rounded-xl p-6 shadow-sm">
        <h1 className="text-xl font-bold text-foreground mb-1">Đăng ký</h1>
        <p className="text-sm text-muted-foreground mb-6">Tạo tài khoản chỉ với tên đăng nhập và mật khẩu.</p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-sm font-medium text-foreground">Tên đăng nhập</label>
            <Input value={username} onChange={(e) => setUsername(e.target.value)} className="mt-1" autoFocus required />
          </div>
          <div>
            <label className="text-sm font-medium text-foreground">Tên hiển thị <span className="text-muted-foreground">(tùy chọn)</span></label>
            <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} className="mt-1" />
          </div>
          <div>
            <label className="text-sm font-medium text-foreground">Mật khẩu</label>
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1" required />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <Button type="submit" disabled={loading || !username.trim() || !password} className="w-full bg-[#E03C31] hover:bg-[#c43428] text-white">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Đăng ký"}
          </Button>
        </form>
        <p className="text-sm text-muted-foreground mt-4 text-center">
          Đã có tài khoản? <Link href="/dang-nhap" className="text-[#E03C31] font-medium">Đăng nhập</Link>
        </p>
      </div>
    </div>
  )
}
