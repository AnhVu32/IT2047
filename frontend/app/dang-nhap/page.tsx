"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useAuth } from "@/lib/auth-context"
import { AuthShell } from "@/components/auth-shell"

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
    <AuthShell
      title="Đăng nhập"
      subtitle="Chào mừng bạn quay lại."
      footer={<>Chưa có tài khoản? <Link href="/dang-ky" className="font-medium text-primary hover:underline">Đăng ký</Link></>}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <label className="block">
          <span className="text-sm font-medium text-foreground">Tên đăng nhập</span>
          <Input value={username} onChange={(e) => setUsername(e.target.value)} className="mt-1.5 h-11" autoFocus required />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-foreground">Mật khẩu</span>
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1.5 h-11" required />
        </label>
        {error && <p role="alert" className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
        <Button type="submit" disabled={loading || !username.trim() || !password} className="h-11 w-full">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Đăng nhập"}
        </Button>
      </form>
    </AuthShell>
  )
}
