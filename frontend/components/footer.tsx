"use client"

import { Home, Phone, Mail, Globe, Share2 } from "lucide-react"
import Link from "next/link"

export function Footer() {
  return (
    <footer className="bg-muted/50 border-t border-border mt-12">
      <div className="container mx-auto px-4 py-10">
        {/* Main Footer Content */}
        <div className="flex flex-col items-center text-center">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 mb-4">
            <div className="p-1.5 bg-[#E03C31] rounded">
              <Home className="h-5 w-5 text-white" />
            </div>
            <span className="font-bold text-lg text-foreground">BATDONGSAN AI</span>
          </Link>

          {/* Description */}
          <p className="text-sm text-muted-foreground max-w-md mb-6">
            Nền tảng bất động sản hàng đầu để mua, bán và cho thuê nhà đất trên khắp Việt Nam.
          </p>

          {/* Contact Info */}
          <div className="flex flex-wrap items-center justify-center gap-6 text-sm text-muted-foreground">
            <div className="flex items-center gap-2">
              <Phone className="h-4 w-4 text-[#E03C31]" />
              <span>Hotline: 1900 xxxx</span>
            </div>
            <div className="flex items-center gap-2">
              <Mail className="h-4 w-4 text-[#E03C31]" />
              <span>Email: cskh@batdongsanai.vn</span>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Bar */}
      <div className="border-t border-border">
        <div className="container mx-auto px-4 py-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-muted-foreground">
            <p>© 2024 Cổng thông tin BATDONGSAN AI. Tất cả quyền được bảo lưu.</p>
            <div className="flex items-center gap-4">
              <button className="hover:text-foreground transition-colors">
                <Globe className="h-5 w-5" />
              </button>
              <button className="hover:text-foreground transition-colors">
                <Share2 className="h-5 w-5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </footer>
  )
}
