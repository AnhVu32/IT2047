import { CheckCircle2 } from "lucide-react"
import { Logo } from "@/components/header"

const BENEFITS = [
  "Lưu lịch sử trò chuyện với trợ lý AI",
  "Lưu tin và nhận gợi ý cá nhân hóa",
  "Tiếp tục tư vấn trên mọi thiết bị",
]

interface AuthShellProps {
  title: string
  subtitle: string
  children: React.ReactNode
  footer: React.ReactNode
}

export function AuthShell({ title, subtitle, children, footer }: AuthShellProps) {
  return (
    <div className="grid min-h-screen bg-background lg:grid-cols-2">
      <div className="relative hidden overflow-hidden bg-primary p-12 text-primary-foreground lg:flex lg:flex-col lg:justify-center">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.08] [background-image:radial-gradient(circle_at_1px_1px,currentColor_1px,transparent_0)] [background-size:22px_22px]"
        />
        <div className="relative max-w-md">
          <h2 className="text-3xl font-bold tracking-tight text-balance">Tư vấn bất động sản thông minh cho người mua nhà</h2>
          <ul className="mt-8 space-y-3">
            {BENEFITS.map((item) => (
              <li key={item} className="flex items-center gap-3 text-primary-foreground/90">
                <CheckCircle2 className="h-5 w-5 flex-shrink-0" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="flex flex-col px-4 py-8 sm:px-8">
        <Logo />
        <div className="flex flex-1 items-center justify-center py-10">
          <div className="w-full max-w-sm">
            <h1 className="text-2xl font-bold text-foreground">{title}</h1>
            <p className="mt-1 mb-6 text-sm text-muted-foreground">{subtitle}</p>
            {children}
            <p className="mt-6 text-center text-sm text-muted-foreground">{footer}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
