"use client"

import { useState, useMemo } from "react"
import { SlidersHorizontal, Search } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

const WARDS = [
  "Tất cả", "An Đông", "An Hội Đông", "An Hội Tây", "An Khánh", "An Lạc", "An Long", "An Nhơn", 
  "An Nhơn Tây", "An Phú", "An Phú Đông", "An Thới Đông", "Bà Điểm", "Bà Rịa", "Bắc Tân Uyên", 
  "Bàn Cờ", "Bàu Bàng", "Bàu Lâm", "Bảy Hiền", "Bến Cát", "Bến Thành", "Bình Chánh", "Bình Châu", 
  "Bình Cơ", "Bình Đông", "Bình Dương", "Bình Giã", "Bình Hòa", "Bình Hưng", "Bình Hưng Hòa", 
  "Bình Khánh", "Bình Lợi", "Bình Lợi Trung", "Bình Mỹ", "Bình Phú", "Bình Quới", "Bình Tân", 
  "Bình Tây", "Bình Thạnh", "Bình Thới", "Bình Tiên", "Bình Trị Đông", "Bình Trưng", "Cần Giờ", 
  "Cát Lái", "Cầu Kiệu", "Cầu Ông Lãnh", "Chánh Hiệp", "Chánh Hưng", "Chánh Phú Hòa", "Châu Đức", 
  "Châu Pha", "Chợ Lớn", "Chợ Quán", "Côn Đảo", "Củ Chi", "Đất Đỏ", "Dầu Tiếng", "Dĩ An", 
  "Diên Hồng", "Đông Hòa", "Đông Hưng Thuận", "Đông Thạnh", "Đức Nhuận", "Gia Định", "Gò Vấp", 
  "Hạnh Thông", "Hiệp Bình", "Hiệp Phước", "Hồ Tràm", "Hòa Bình", "Hòa Hiệp", "Hòa Hội", 
  "Hòa Hưng", "Hòa Lợi", "Hóc Môn", "Hưng Long", "Khánh Hội", "Kim Long", "Lái Thiêu", 
  "Linh Xuân", "Long Bình", "Long Điền", "Long Hải", "Long Hòa", "Long Hương", "Long Nguyên", 
  "Long Phước", "Long Sơn", "Long Trường", "Minh Phụng", "Minh Thạnh", "Ngãi Giao", "Nghĩa Thành", 
  "Ngọc Hà", "Nhà Bè", "Nhiêu Lộc", "Nhuận Đức", "Phú An", "Phú Định", "Phú Giáo", "Phú Hòa Đông", 
  "Phú Lâm", "Phú Lợi", "Phú Mỹ", "Phú Nhuận", "Phú Thạnh", "Phú Thọ", "Phú Thọ Hòa", "Phú Thuận", 
  "Phước Hải", "Phước Hòa", "Phước Long", "Phước Thắng", "Phước Thành", "Rạch Dừa", "Sài Gòn", 
  "Tam Bình", "Tam Long", "Tam Thắng", "Tân An Hội", "Tân Bình", "Tân Định", "Tân Đông Hiệp", 
  "Tân Hải", "Tân Hiệp", "Tân Hòa", "Tân Hưng", "Tân Khánh", "Tân Mỹ", "Tân Nhựt", "Tân Phú", 
  "Tân Phước", "Tân Sơn", "Tân Sơn Hòa", "Tân Sơn Nhất", "Tân Sơn Nhì", "Tân Tạo", "Tân Thành", 
  "Tân Thới Hiệp", "Tân Thuận", "Tân Uyên", "Tân Vĩnh Lộc", "Tăng Nhơn Phú", "Tây Nam", "Tây Thạnh", 
  "Thái Mỹ", "Thạnh An", "Thanh An", "Thạnh Mỹ Tây", "Thới An", "Thới Hòa", "Thông Tây Hội", 
  "Thủ Đức", "Thuận An", "Thuận Giao", "Trà Vinh", "Trảng Bàng", "Trường Thọ", "Vĩnh Cửu", 
  "Vĩnh Lộc", "Vĩnh Phú", "Vũng Tàu", "Xuyên Mộc"
]

const AMENITIES = [
  "Tất cả", "Hồ bơi", "Gym", "Khuôn viên", "BBQ", "Khu vui chơi trẻ em", "Sân thể thao", 
  "An ninh 24h", "Lễ tân", "Thang máy", "Bãi đậu xe", "Gần Metro", "Gần Bus", "Gần cao tốc", 
  "Gần trường", "Gần bệnh viện", "Gần siêu thị", "Gần chợ", "Gần công viên", "View sông", 
  "View công viên", "View thành phố", "Ban công", "Vườn", "Garage", "Sân thượng"
]

const DIRECTIONS = [
  "Tất cả", "Tây - Nam", "Đông - Nam", "Bắc", "Nam", "Đông - Bắc", "Tây - Bắc", "Tây", "Đông", "Không rõ"
]

export function FilterSidebar() {
  const [wardSearch, setWardSearch] = useState("")
  const [selectedWards, setSelectedWards] = useState<string[]>([])
  const [selectedAmenities, setSelectedAmenities] = useState<string[]>([])

  const filteredWards = useMemo(() => {
    if (!wardSearch) return WARDS
    return WARDS.filter(ward => 
      ward.toLowerCase().includes(wardSearch.toLowerCase())
    )
  }, [wardSearch])

  const handleWardChange = (ward: string, checked: boolean) => {
    if (ward === "Tất cả") {
      if (checked) {
        setSelectedWards(WARDS)
      } else {
        setSelectedWards([])
      }
    } else {
      if (checked) {
        const newSelected = [...selectedWards, ward]
        if (newSelected.length === WARDS.length - 1) {
          setSelectedWards(WARDS)
        } else {
          setSelectedWards(newSelected)
        }
      } else {
        setSelectedWards(selectedWards.filter(w => w !== ward && w !== "Tất cả"))
      }
    }
  }

  const handleAmenityChange = (amenity: string, checked: boolean) => {
    if (amenity === "Tất cả") {
      if (checked) {
        setSelectedAmenities(AMENITIES)
      } else {
        setSelectedAmenities([])
      }
    } else {
      if (checked) {
        const newSelected = [...selectedAmenities, amenity]
        if (newSelected.length === AMENITIES.length - 1) {
          setSelectedAmenities(AMENITIES)
        } else {
          setSelectedAmenities(newSelected)
        }
      } else {
        setSelectedAmenities(selectedAmenities.filter(a => a !== amenity && a !== "Tất cả"))
      }
    }
  }

  return (
    <div className="space-y-6">
      {/* Filter Card */}
      <div className="bg-card border border-border rounded-lg p-5">
        <div className="flex items-center gap-2 mb-6">
          <SlidersHorizontal className="h-5 w-5 text-[#E03C31]" />
          <h2 className="font-semibold text-foreground">Bộ lọc chi tiết</h2>
        </div>

        {/* 1. VỊ TRÍ - Checkbox list with search */}
        <div className="mb-5">
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 block">
            Vị trí
          </label>
          <div className="relative mb-2">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input 
              placeholder="Tìm phường/xã..." 
              className="h-9 pl-9 text-sm"
              value={wardSearch}
              onChange={(e) => setWardSearch(e.target.value)}
            />
          </div>
          <div className="max-h-60 overflow-y-auto border border-border rounded-md p-2 space-y-1">
            {filteredWards.map((ward) => (
              <label 
                key={ward} 
                className="flex items-center gap-2 py-1 px-1 hover:bg-muted/50 rounded cursor-pointer text-sm"
              >
                <Checkbox 
                  checked={selectedWards.includes(ward)}
                  onCheckedChange={(checked) => handleWardChange(ward, checked as boolean)}
                />
                <span className={ward === "Tất cả" ? "font-medium" : ""}>{ward}</span>
              </label>
            ))}
          </div>
        </div>

        {/* 2. LOẠI BĐS - Property Type Select */}
        <div className="mb-5">
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 block">
            Loại bđs
          </label>
          <Select>
            <SelectTrigger className="h-10">
              <SelectValue placeholder="Tất cả" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tất cả</SelectItem>
              <SelectItem value="can-ho">Căn hộ</SelectItem>
              <SelectItem value="nha-dat">Nhà đất</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* 3. KHOẢNG GIÁ */}
        <div className="mb-5">
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 block">
            Khoảng giá (VNĐ)
          </label>
          <div className="flex items-center gap-2">
            <Input placeholder="Từ" className="h-10" />
            <span className="text-muted-foreground">-</span>
            <Input placeholder="Đến" className="h-10" />
          </div>
        </div>

        {/* 4. BIẾN ĐỘNG TRONG 1 NĂM QUA */}
        <div className="mb-5">
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 block">
            Biến động trong 1 năm qua
          </label>
          <div className="flex items-center gap-2">
            <Input placeholder="Từ" className="h-10" />
            <span className="text-muted-foreground">-</span>
            <Input placeholder="Đến" className="h-10" />
          </div>
        </div>

        {/* 5. DIỆN TÍCH */}
        <div className="mb-5">
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 block">
            Diện tích (m²)
          </label>
          <Input placeholder="Ví dụ: 100" className="h-10" />
        </div>

        {/* 6. SỐ PHÒNG NGỦ & SỐ PHÒNG TẮM - side by side inputs */}
        <div className="grid grid-cols-2 gap-3 mb-5">
          <div>
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 block">
              Số phòng ngủ
            </label>
            <Input placeholder="Tất cả" className="h-10" />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 block">
              Số phòng tắm
            </label>
            <Input placeholder="Tất cả" className="h-10" />
          </div>
        </div>

        {/* 7. PHÁP LÝ & NỘI THẤT - side by side selects */}
        <div className="grid grid-cols-2 gap-3 mb-5">
          <div>
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 block">
              Pháp lý
            </label>
            <Select>
              <SelectTrigger className="h-10">
                <SelectValue placeholder="Tất cả" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tất cả</SelectItem>
                <SelectItem value="so-hong-rieng">Sổ hồng riêng</SelectItem>
                <SelectItem value="dang-cho-so">Đang chờ sổ</SelectItem>
                <SelectItem value="so-chung">Sổ chung</SelectItem>
                <SelectItem value="khong-ro">Không rõ</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 block">
              Nội thất
            </label>
            <Select>
              <SelectTrigger className="h-10">
                <SelectValue placeholder="Tất cả" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tất cả</SelectItem>
                <SelectItem value="co-ban">Cơ bản</SelectItem>
                <SelectItem value="day-du">Đầy đủ</SelectItem>
                <SelectItem value="cao-cap">Cao cấp</SelectItem>
                <SelectItem value="khong-noi-that">Không nội thất</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* 8. HƯỚNG NHÀ & HƯỚNG BAN CÔNG - side by side selects */}
        <div className="grid grid-cols-2 gap-3 mb-5">
          <div>
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 block">
              Hướng nhà
            </label>
            <Select>
              <SelectTrigger className="h-10">
                <SelectValue placeholder="Tất cả" />
              </SelectTrigger>
              <SelectContent>
                {DIRECTIONS.map((direction) => (
                  <SelectItem key={direction} value={direction.toLowerCase().replace(/\s/g, "-")}>
                    {direction}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 block">
              Hướng ban công
            </label>
            <Select>
              <SelectTrigger className="h-10">
                <SelectValue placeholder="Tất cả" />
              </SelectTrigger>
              <SelectContent>
                {DIRECTIONS.map((direction) => (
                  <SelectItem key={direction} value={direction.toLowerCase().replace(/\s/g, "-")}>
                    {direction}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* 9. TIỆN ÍCH - Checkbox grid */}
        <div className="mb-6">
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 block">
            Tiện ích
          </label>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1 border border-border rounded-md p-3 max-h-48 overflow-y-auto">
            {AMENITIES.map((amenity) => (
              <label 
                key={amenity} 
                className="flex items-center gap-2 py-1 hover:bg-muted/50 rounded cursor-pointer text-sm"
              >
                <Checkbox 
                  checked={selectedAmenities.includes(amenity)}
                  onCheckedChange={(checked) => handleAmenityChange(amenity, checked as boolean)}
                />
                <span className={amenity === "Tất cả" ? "font-medium" : ""}>{amenity}</span>
              </label>
            ))}
          </div>
        </div>

        {/* 10. Apply Filter Button */}
        <Button className="w-full bg-[#E03C31] hover:bg-[#c43428] text-white h-11">
          Áp dụng bộ lọc
        </Button>
      </div>

      {/* Support CTA Card */}
      <div className="bg-[#FFF5F4] border border-[#E03C31]/20 rounded-lg p-5">
        <h3 className="font-semibold text-[#E03C31] mb-2">
          Bạn cần hỗ trợ chuyên nghiệp?
        </h3>
        <p className="text-sm text-muted-foreground mb-4">
          Các chuyên viên của chúng tôi luôn sẵn sàng hỗ trợ bạn tìm thấy ngôi nhà mơ ước.
        </p>
        <Button className="w-full bg-[#E03C31] hover:bg-[#c43428] text-white h-11">
          Tìm môi giới
        </Button>
      </div>
    </div>
  )
}
