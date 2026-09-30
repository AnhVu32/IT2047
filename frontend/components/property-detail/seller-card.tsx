'use client'

import { Phone, MessageCircle } from 'lucide-react'
import { Avatar, AvatarImage, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'

export function SellerCard() {
  return (
    <div className="bg-card rounded-lg border border-border p-4 space-y-4">
      {/* Seller Info */}
      <div className="flex items-center gap-3">
        <Avatar className="h-12 w-12">
          <AvatarImage src="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=400&fit=crop" alt="Seller" />
          <AvatarFallback>AG</AvatarFallback>
        </Avatar>
        <div className="flex-1">
          <p className="font-semibold text-foreground">Nguyễn Văn A</p>
          <p className="text-sm text-muted-foreground">Chuyên viên tư vấn</p>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="space-y-2">
        <Button className="w-full bg-[#E03C31] hover:bg-[#c43428] text-white font-medium">
          <Phone className="h-4 w-4 mr-2" />
          Gọi ngay
        </Button>
        <Button variant="outline" className="w-full font-medium">
          <MessageCircle className="h-4 w-4 mr-2" />
          Nhắn tin
        </Button>
      </div>
    </div>
  )
}
