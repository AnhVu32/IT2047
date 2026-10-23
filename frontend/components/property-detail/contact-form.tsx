'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { CheckCircle2, Heart, Share2, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/lib/auth-context'
import { getSavedListingIds, sendInteraction, setSavedListing } from '@/lib/feedback'
import { cn } from '@/lib/utils'

interface ContactFormProps {
  listingId?: number | string
}

// Vietnamese mobile numbers: 0xxxxxxxxx or +84xxxxxxxxx, ignoring spaces/dots/dashes.
const PHONE_PATTERN = /^(0|\+84)\d{9,10}$/

export function ContactForm({ listingId }: ContactFormProps) {
  const [formData, setFormData] = useState({ name: '', phone: '' })
  const [phoneError, setPhoneError] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)
  const [shareNotice, setShareNotice] = useState<string | null>(null)
  const { user } = useAuth()
  const [saved, setSaved] = useState(false)

  // Reflect the real saved state on load (and when the user logs in/out).
  useEffect(() => {
    if (listingId == null) return
    let active = true
    getSavedListingIds().then((set) => {
      if (active) setSaved(set.has(Number(listingId)))
    })
    return () => {
      active = false
    }
  }, [user, listingId])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target
    setFormData((prev) => ({ ...prev, [name]: value }))
    if (name === 'phone') setPhoneError(null)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!PHONE_PATTERN.test(formData.phone.replace(/[\s.-]/g, ''))) {
      setPhoneError('Số điện thoại chưa đúng định dạng')
      return
    }
    if (listingId != null) {
      sendInteraction({ listing_id: listingId, action_type: 'contact', source: 'detail' })
    }
    setSubmitted(true)
  }

  const handleSave = () => {
    if (listingId == null) return
    const next = !saved
    setSaved(next)
    setSavedListing(listingId, next, 'detail')
  }

  const handleShare = async () => {
    if (listingId != null) {
      sendInteraction({ listing_id: listingId, action_type: 'share', source: 'detail' })
    }
    if (typeof navigator === 'undefined') return
    if (navigator.share) {
      navigator.share({ url: window.location.href }).catch(() => {})
      return
    }
    try {
      await navigator.clipboard.writeText(window.location.href)
      setShareNotice('Đã sao chép liên kết')
    } catch {
      setShareNotice('Không thể sao chép liên kết')
    }
    window.setTimeout(() => setShareNotice(null), 2500)
  }

  return (
    <div className="space-y-3">
      <div id="lien-he" className="scroll-mt-24 rounded-xl border border-border bg-card p-5 shadow-sm">
        {submitted ? (
          <div className="flex flex-col items-center py-4 text-center">
            <CheckCircle2 className="h-10 w-10 text-primary" />
            <p className="mt-3 font-semibold text-foreground">Đã ghi nhận yêu cầu</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Yêu cầu liên hệ của {formData.name.trim()} ({formData.phone}) đã được gửi.
            </p>
            <Button type="button" variant="ghost" size="sm" className="mt-3" onClick={() => setSubmitted(false)}>
              Sửa thông tin
            </Button>
          </div>
        ) : (
          <>
            <h3 className="font-semibold text-foreground">Cần tư vấn về căn này?</h3>
            <p className="mt-1 text-sm text-muted-foreground">Để lại thông tin, chuyên viên sẽ gọi lại cho bạn.</p>

            <form onSubmit={handleSubmit} className="mt-4 space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="name">Họ và tên</Label>
                <Input
                  id="name"
                  name="name"
                  placeholder="Nguyễn Văn A"
                  autoComplete="name"
                  required
                  value={formData.name}
                  onChange={handleChange}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="phone">Số điện thoại</Label>
                <Input
                  id="phone"
                  name="phone"
                  type="tel"
                  inputMode="tel"
                  placeholder="09xx xxx xxx"
                  autoComplete="tel"
                  required
                  aria-invalid={Boolean(phoneError)}
                  aria-describedby={phoneError ? 'phone-error' : undefined}
                  value={formData.phone}
                  onChange={handleChange}
                />
                {phoneError && <p id="phone-error" className="text-xs text-destructive">{phoneError}</p>}
              </div>

              <Button type="submit" className="h-11 w-full">
                Yêu cầu gọi lại
              </Button>
            </form>
          </>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2">
        <Button type="button" variant="outline" className="bg-card" onClick={handleSave} aria-pressed={saved}>
          <Heart className={cn('h-4 w-4', saved && 'fill-price text-price')} />
          {saved ? 'Đã lưu' : 'Lưu tin'}
        </Button>
        <Button type="button" variant="outline" className="bg-card" onClick={handleShare}>
          <Share2 className="h-4 w-4" />
          Chia sẻ
        </Button>
      </div>
      {shareNotice && <p className="text-center text-xs text-muted-foreground" role="status">{shareNotice}</p>}

      <Link
        href="/tim-kiem-chuyen-sau"
        className="flex items-center gap-3 rounded-xl border border-primary/20 bg-accent p-4 text-sm transition-colors hover:border-primary/40"
      >
        <Sparkles className="h-5 w-5 flex-shrink-0 text-primary" />
        <span>
          <span className="block font-semibold text-accent-foreground">Hỏi trợ lý AI</span>
          <span className="text-muted-foreground">So sánh với các lựa chọn khác theo nhu cầu của bạn</span>
        </span>
      </Link>
    </div>
  )
}
