"use client"

import { useState, useMemo } from "react"
import { Search, SlidersHorizontal, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { cn } from "@/lib/utils"

const WARDS = [
  "Phường An Đông", "Phường An Hội Đông", "Phường An Hội Tây", "Phường An Khánh", "Phường An Lạc", "Phường An Nhơn", "Phường An Phú Đông", "Phường Bàn Cờ", "Phường Bảy Hiền", "Phường Bến Thành", "Phường Bình Dương", "Phường Bình Đông", "Phường Bình Hòa", "Phường Bình Hưng Hòa", "Phường Bình Lợi Trung", "Phường Bình Phú", "Phường Bình Quới", "Phường Bình Tân", "Phường Bình Tây", "Phường Bình Thạnh", "Phường Bình Thới", "Phường Bình Tiên", "Phường Bình Trị Đông", "Phường Bình Trưng", "Phường Cát Lái", "Phường Cầu Kiệu", "Phường Cầu Ông Lãnh", "Phường Chánh Hiệp", "Phường Chánh Hưng", "Phường Chánh Phú Hòa", "Phường Chợ Lớn", "Phường Chợ Quán", "Phường Diên Hồng", "Phường Dĩ An", "Phường Đông Hòa", "Phường Đông Hưng Thuận", "Phường Đức Nhuận", "Phường Gia Định", "Phường Gò Vấp", "Phường Hạnh Thông", "Phường Hiệp Bình", "Phường Hòa Bình", "Phường Hòa Hưng", "Phường Khánh Hội", "Phường Linh Xuân", "Phường Long Bình", "Phường Long Hương", "Phường Long Nguyên", "Phường Long Phước", "Phường Long Trường", "Phường Minh Phụng", "Phường Nhiêu Lộc", "Phường Phú Định", "Phường Phú Lâm", "Phường Phú Lợi", "Phường Phú Nhuận", "Phường Phú Thạnh", "Phường Phú Thọ", "Phường Phú Thọ Hòa", "Phường Phú Thuận", "Phường Phước Long", "Phường Phước Thắng", "Phường Rạch Dừa", "Phường Sài Gòn", "Phường Tam Bình", "Phường Tam Thắng", "Phường Tân Bình", "Phường Tân Định", "Phường Tân Đông Hiệp", "Phường Tân Hòa", "Phường Tân Hưng", "Phường Tân Mỹ", "Phường Tân Phú", "Phường Tân Sơn", "Phường Tân Sơn Hòa", "Phường Tân Sơn Nhất", "Phường Tân Sơn Nhì", "Phường Tân Tạo", "Phường Tân Thới Hiệp", "Phường Tân Thuận", "Phường Tăng Nhơn Phú", "Phường Tây Thạnh", "Phường Thạnh Mỹ Tây", "Phường Thới An", "Phường Thới Hòa", "Phường Thông Tây Hội", "Phường Thủ Dầu Một", "Phường Thủ Đức", "Phường Thuận Giao", "Phường Trung Mỹ Tây", "Phường Vĩnh Hội", "Phường Vũng Tàu", "Phường Vườn Lài", "Phường Xóm Chiếu", "Phường Xuân Hòa",
  "Xã Bà Điểm", "Xã Bàu Bàng", "Xã Bình Chánh", "Xã Bình Hưng", "Xã Bình Lợi", "Xã Đất Đỏ", "Xã Hiệp Phước", "Xã Hồ Tràm", "Xã Hóc Môn", "Xã Hưng Long", "Xã Nhà Bè", "Xã Tân An Hội", "Xã Tân Nhựt", "Xã Tân Vĩnh Lộc", "Xã Trừ Văn Thố", "Xã Vĩnh Lộc", "Xã Xuân Thới Sơn"
]

const AMENITIES = [
  "Hồ bơi", "Gym", "Khuôn viên", "BBQ", "Khu vui chơi trẻ em", "Sân thể thao",
  "An ninh 24h", "Lễ tân", "Thang máy", "Bãi đậu xe", "Gần Metro", "Gần Bus", "Gần cao tốc",
  "Gần trường", "Gần bệnh viện", "Gần siêu thị", "Gần chợ", "Gần công viên", "View sông",
  "View công viên", "View thành phố", "Ban công", "Vườn", "Garage", "Sân thượng"
]

const LEGAL_STATUS_OPTIONS = ["Sổ hồng riêng", "Đang chờ sổ", "Sổ chung", "Không rõ"]

const FURNITURE_OPTIONS = ["Cơ bản", "Đầy đủ", "Cao cấp", "Không nội thất"]

const DIRECTIONS = [
  "Đông", "Tây", "Nam", "Bắc", "Đông - Nam", "Tây - Nam", "Đông - Bắc", "Tây - Bắc", "Không rõ"
]

const PROPERTY_TYPES = ["Tất cả", "Căn hộ", "Nhà đất"]

// The listing API compares bedrooms/bathrooms with ">=", so each chip means "at least N".
const BEDROOM_OPTIONS = ["1", "2", "3", "4", "5"]
const BATHROOM_OPTIONS = ["1", "2", "3", "4"]

// Prices are stored in tỷ VNĐ.
const PRICE_PRESETS = [
  { label: "Dưới 3 tỷ", min: "", max: "3" },
  { label: "3 – 5 tỷ", min: "3", max: "5" },
  { label: "5 – 10 tỷ", min: "5", max: "10" },
  { label: "Trên 10 tỷ", min: "10", max: "" },
]

const AMENITY_MAPPING: { [key: string]: string } = {
  "Hồ bơi": "pool",
  "Gym": "gym",
  "Khuôn viên": "park",
  "BBQ": "bbq",
  "Khu vui chơi trẻ em": "kids_playground",
  "Sân thể thao": "sports_court",
  "An ninh 24h": "security_24h",
  "Lễ tân": "reception",
  "Thang máy": "elevator",
  "Bãi đậu xe": "parking",
  "Gần Metro": "near_metro",
  "Gần Bus": "near_bus",
  "Gần cao tốc": "near_highway",
  "Gần trường": "near_school",
  "Gần bệnh viện": "near_hospital",
  "Gần siêu thị": "near_mall",
  "Gần chợ": "near_market",
  "Gần công viên": "near_park",
  "View sông": "river_view",
  "View công viên": "park_view",
  "View thành phố": "city_view",
  "Ban công": "balcony",
  "Vườn": "garden",
  "Garage": "garage",
  "Sân thượng": "terrace"
}

interface AdvancedFilterProps {
  onApplyFilters: (filters: any) => void
  onClose?: () => void
  title?: string
  applyLabel?: string
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "rounded-full border px-3 py-1.5 text-sm transition-colors",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-card text-foreground hover:border-primary/50 hover:bg-accent",
      )}
    >
      {children}
    </button>
  )
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return <p className="mb-2 text-sm font-semibold text-foreground">{children}</p>
}

function toggleItem(list: string[], item: string) {
  return list.includes(item) ? list.filter((i) => i !== item) : [...list, item]
}

export function AdvancedFilter({
  onApplyFilters,
  onClose,
  title = "Bộ lọc",
  applyLabel = "Xem kết quả",
}: AdvancedFilterProps) {
  const [wardSearch, setWardSearch] = useState("")
  const [selectedWards, setSelectedWards] = useState<string[]>([])
  const [minPrice, setMinPrice] = useState("")
  const [maxPrice, setMaxPrice] = useState("")
  const [minArea, setMinArea] = useState("")
  const [maxArea, setMaxArea] = useState("")
  const [selectedBedrooms, setSelectedBedrooms] = useState("")
  const [selectedBathrooms, setSelectedBathrooms] = useState("")
  const [propertyType, setPropertyType] = useState("Tất cả")
  const [selectedLegalStatus, setSelectedLegalStatus] = useState<string[]>([])
  const [selectedFurniture, setSelectedFurniture] = useState<string[]>([])
  const [selectedHouseDirection, setSelectedHouseDirection] = useState<string[]>([])
  const [selectedBalconyDirection, setSelectedBalconyDirection] = useState<string[]>([])
  const [selectedAmenities, setSelectedAmenities] = useState<string[]>([])

  const filteredWards = useMemo(() => {
    if (!wardSearch) return WARDS
    return WARDS.filter((ward) => ward.toLowerCase().includes(wardSearch.toLowerCase()))
  }, [wardSearch])

  const activeCount = [
    selectedWards.length > 0,
    propertyType !== "Tất cả",
    Boolean(minPrice || maxPrice),
    Boolean(minArea || maxArea),
    Boolean(selectedBedrooms),
    Boolean(selectedBathrooms),
    selectedLegalStatus.length > 0,
    selectedFurniture.length > 0,
    selectedHouseDirection.length > 0,
    selectedBalconyDirection.length > 0,
    selectedAmenities.length > 0,
  ].filter(Boolean).length

  const buildFilters = () => {
    const filters: any = {}

    if (selectedWards.length > 0) filters.district = selectedWards.join(",")
    if (minPrice) filters.min_price = parseFloat(minPrice)
    if (maxPrice) filters.max_price = parseFloat(maxPrice)
    if (minArea) filters.min_area = parseFloat(minArea)
    if (maxArea) filters.max_area = parseFloat(maxArea)
    if (selectedBedrooms) filters.bedrooms = parseInt(selectedBedrooms)
    if (selectedBathrooms) filters.bathrooms = parseInt(selectedBathrooms)

    filters.property_type = propertyType === "Tất cả" ? "Căn hộ,Nhà đất" : propertyType

    // Multi-value fields are sent as the exact Vietnamese strings joined by commas.
    if (selectedLegalStatus.length > 0) filters.legal_status = selectedLegalStatus.join(",")
    if (selectedFurniture.length > 0) filters.furniture = selectedFurniture.join(",")
    if (selectedHouseDirection.length > 0) filters.house_direction = selectedHouseDirection.join(",")
    if (selectedBalconyDirection.length > 0) filters.balcony_direction = selectedBalconyDirection.join(",")

    selectedAmenities.forEach((amenity) => {
      const apiParam = AMENITY_MAPPING[amenity]
      if (apiParam) filters[apiParam] = true
    })

    return filters
  }

  const handleApplyFilters = (e?: React.FormEvent) => {
    e?.preventDefault()
    onApplyFilters(buildFilters())
    onClose?.()
  }

  const handleReset = () => {
    setWardSearch("")
    setSelectedWards([])
    setMinPrice("")
    setMaxPrice("")
    setMinArea("")
    setMaxArea("")
    setSelectedBedrooms("")
    setSelectedBathrooms("")
    setPropertyType("Tất cả")
    setSelectedLegalStatus([])
    setSelectedFurniture([])
    setSelectedHouseDirection([])
    setSelectedBalconyDirection([])
    setSelectedAmenities([])
    onApplyFilters({ property_type: "Căn hộ,Nhà đất" })
  }

  const extraGroups = [
    { key: "legal", label: "Pháp lý", options: LEGAL_STATUS_OPTIONS, selected: selectedLegalStatus, set: setSelectedLegalStatus },
    { key: "furniture", label: "Nội thất", options: FURNITURE_OPTIONS, selected: selectedFurniture, set: setSelectedFurniture },
    { key: "house", label: "Hướng nhà", options: DIRECTIONS, selected: selectedHouseDirection, set: setSelectedHouseDirection },
    { key: "balcony", label: "Hướng ban công", options: DIRECTIONS, selected: selectedBalconyDirection, set: setSelectedBalconyDirection },
    { key: "amenities", label: "Tiện ích", options: AMENITIES, selected: selectedAmenities, set: setSelectedAmenities },
  ]

  return (
    <form
      onSubmit={handleApplyFilters}
      // `relative` contains the hidden native inputs Radix checkboxes render inside a <form>;
      // without a positioned ancestor they escape overflow clipping and stretch the page.
      className="relative flex h-full flex-col overflow-hidden rounded-xl border border-border bg-card shadow-sm"
    >
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <SlidersHorizontal className="h-4 w-4 text-primary" />
        <h2 className="font-semibold text-foreground">{title}</h2>
        {activeCount > 0 && (
          <span className="rounded-full bg-primary px-2 py-0.5 text-xs font-medium text-primary-foreground">
            {activeCount}
          </span>
        )}
        <div className="ml-auto flex items-center gap-1">
          {activeCount > 0 && (
            <Button type="button" variant="ghost" size="sm" className="h-8 text-muted-foreground" onClick={handleReset}>
              Xóa lọc
            </Button>
          )}
          {onClose && (
            <Button type="button" variant="ghost" size="icon" className="h-8 w-8 lg:hidden" onClick={onClose} aria-label="Đóng bộ lọc">
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      <div className="flex-1 space-y-6 overflow-y-auto p-4">
        <div>
          <FieldLabel>Loại bất động sản</FieldLabel>
          <div className="grid grid-cols-3 gap-1 rounded-lg bg-muted p-1">
            {PROPERTY_TYPES.map((type) => (
              <button
                key={type}
                type="button"
                aria-pressed={propertyType === type}
                onClick={() => setPropertyType(type)}
                className={cn(
                  "rounded-md py-1.5 text-sm font-medium transition-colors",
                  propertyType === type ? "bg-card text-primary shadow-sm" : "text-muted-foreground hover:text-foreground",
                )}
              >
                {type}
              </button>
            ))}
          </div>
        </div>

        <div>
          <FieldLabel>Khoảng giá (tỷ VNĐ)</FieldLabel>
          <div className="mb-2 flex flex-wrap gap-2">
            {PRICE_PRESETS.map((preset) => {
              const active = minPrice === preset.min && maxPrice === preset.max
              return (
                <Chip
                  key={preset.label}
                  active={active}
                  onClick={() => {
                    setMinPrice(active ? "" : preset.min)
                    setMaxPrice(active ? "" : preset.max)
                  }}
                >
                  {preset.label}
                </Chip>
              )
            })}
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Input placeholder="Từ" type="number" min={0} step="any" inputMode="decimal" value={minPrice} onChange={(e) => setMinPrice(e.target.value)} />
            <Input placeholder="Đến" type="number" min={0} step="any" inputMode="decimal" value={maxPrice} onChange={(e) => setMaxPrice(e.target.value)} />
          </div>
        </div>

        <div>
          <FieldLabel>Diện tích (m²)</FieldLabel>
          <div className="grid grid-cols-2 gap-2">
            <Input placeholder="Từ" type="number" min={0} inputMode="decimal" value={minArea} onChange={(e) => setMinArea(e.target.value)} />
            <Input placeholder="Đến" type="number" min={0} inputMode="decimal" value={maxArea} onChange={(e) => setMaxArea(e.target.value)} />
          </div>
        </div>

        <div>
          <FieldLabel>Phòng ngủ</FieldLabel>
          <div className="flex flex-wrap gap-2">
            <Chip active={!selectedBedrooms} onClick={() => setSelectedBedrooms("")}>Bất kỳ</Chip>
            {BEDROOM_OPTIONS.map((n) => (
              <Chip key={n} active={selectedBedrooms === n} onClick={() => setSelectedBedrooms(n)}>{n}+</Chip>
            ))}
          </div>
        </div>

        <div>
          <FieldLabel>Phòng tắm</FieldLabel>
          <div className="flex flex-wrap gap-2">
            <Chip active={!selectedBathrooms} onClick={() => setSelectedBathrooms("")}>Bất kỳ</Chip>
            {BATHROOM_OPTIONS.map((n) => (
              <Chip key={n} active={selectedBathrooms === n} onClick={() => setSelectedBathrooms(n)}>{n}+</Chip>
            ))}
          </div>
        </div>

        <div>
          <FieldLabel>Khu vực</FieldLabel>
          {selectedWards.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-1.5">
              {selectedWards.map((ward) => (
                <button
                  key={ward}
                  type="button"
                  onClick={() => setSelectedWards((prev) => prev.filter((w) => w !== ward))}
                  className="flex items-center gap-1 rounded-full bg-secondary px-2.5 py-1 text-xs font-medium text-secondary-foreground hover:bg-secondary/80"
                  aria-label={`Bỏ ${ward}`}
                >
                  {ward}
                  <X className="h-3 w-3" />
                </button>
              ))}
            </div>
          )}
          <div className="relative mb-2">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Tìm phường/xã..."
              className="pl-9"
              value={wardSearch}
              onChange={(e) => setWardSearch(e.target.value)}
            />
          </div>
          <div className="relative max-h-48 space-y-0.5 overflow-y-auto rounded-lg border border-border p-1.5">
            {filteredWards.length === 0 && (
              <p className="px-2 py-3 text-center text-sm text-muted-foreground">Không tìm thấy phường/xã</p>
            )}
            {filteredWards.map((ward) => (
              <label key={ward} className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted">
                <Checkbox
                  checked={selectedWards.includes(ward)}
                  onCheckedChange={() => setSelectedWards((prev) => toggleItem(prev, ward))}
                />
                <span>{ward}</span>
              </label>
            ))}
          </div>
        </div>

        <Accordion type="multiple" className="-mx-1 border-t border-border">
          {extraGroups.map((group) => (
            <AccordionItem key={group.key} value={group.key} className="px-1">
              <AccordionTrigger className="py-3 text-sm font-semibold hover:no-underline">
                <span className="flex items-center gap-2">
                  {group.label}
                  {group.selected.length > 0 && (
                    <span className="rounded-full bg-secondary px-2 py-0.5 text-xs font-medium text-secondary-foreground">
                      {group.selected.length}
                    </span>
                  )}
                </span>
              </AccordionTrigger>
              <AccordionContent>
                <div className="flex flex-wrap gap-2">
                  {group.options.map((option) => (
                    <Chip
                      key={option}
                      active={group.selected.includes(option)}
                      onClick={() => group.set(toggleItem(group.selected, option))}
                    >
                      {option}
                    </Chip>
                  ))}
                </div>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>

      <div className="border-t border-border bg-card p-4">
        <Button type="submit" className="h-11 w-full text-base">
          {applyLabel}
        </Button>
      </div>
    </form>
  )
}
