import Link from "next/link"
import { Logo } from "@/components/header"

export function Footer() {
  return (
    <footer className="border-t border-border bg-card mt-12">
      <div className="container mx-auto px-4 py-8 flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
        <div className="space-y-2">
          <Logo />
          <p className="text-sm text-muted-foreground max-w-md">
            Tìm kiếm và nhận tư vấn bất động sản tại TP.HCM với trợ lý AI dựa trên dữ liệu tin đăng và tiện ích khu vực.
          </p>
        </div>
        <nav className="flex gap-6 text-sm text-muted-foreground">
          <Link href="/" className="hover:text-foreground transition-colors">Tìm nhà</Link>
          <Link href="/tim-kiem-chuyen-sau" className="hover:text-foreground transition-colors">Tư vấn AI</Link>
        </nav>
      </div>
      <div className="border-t border-border">
        <p className="container mx-auto px-4 py-4 text-xs text-muted-foreground">
          © {new Date().getFullYear()} BATDONGSAN AI. Thông tin chỉ mang tính tham khảo.
        </p>
      </div>
    </footer>
  )
}
