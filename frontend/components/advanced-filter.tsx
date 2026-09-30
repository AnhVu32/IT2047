"use client"

import { useState, useMemo } from "react"
import { Search, SlidersHorizontal } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
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
  "Tất cả",
  "Phường An Đông", "Phường An Hội Đông", "Phường An Hội Tây", "Phường An Khánh", "Phường An Lạc", "Phường An Nhơn", "Phường An Phú Đông", "Phường Bàn Cờ", "Phường Bảy Hiền", "Phường Bến Thành", "Phường Bình Dương", "Phường Bình Đông", "Phường Bình Hòa", "Phường Bình Hưng Hòa", "Phường Bình Lợi Trung", "Phường Bình Phú", "Phường Bình Quới", "Phường Bình Tân", "Phường Bình Tây", "Phường Bình Thạnh", "Phường Bình Thới", "Phường Bình Tiên", "Phường Bình Trị Đông", "Phường Bình Trưng", "Phường Cát Lái", "Phường Cầu Kiệu", "Phường Cầu Ông Lãnh", "Phường Chánh Hiệp", "Phường Chánh Hưng", "Phường Chánh Phú Hòa", "Phường Chợ Lớn", "Phường Chợ Quán", "Phường Diên Hồng", "Phường Dĩ An", "Phường Đông Hòa", "Phường Đông Hưng Thuận", "Phường Đức Nhuận", "Phường Gia Định", "Phường Gò Vấp", "Phường Hạnh Thông", "Phường Hiệp Bình", "Phường Hòa Bình", "Phường Hòa Hưng", "Phường Khánh Hội", "Phường Linh Xuân", "Phường Long Bình", "Phường Long Hương", "Phường Long Nguyên", "Phường Long Phước", "Phường Long Trường", "Phường Minh Phụng", "Phường Nhiêu Lộc", "Phường Phú Định", "Phường Phú Lâm", "Phường Phú Lợi", "Phường Phú Nhuận", "Phường Phú Thạnh", "Phường Phú Thọ", "Phường Phú Thọ Hòa", "Phường Phú Thuận", "Phường Phước Long", "Phường Phước Thắng", "Phường Rạch Dừa", "Phường Sài Gòn", "Phường Tam Bình", "Phường Tam Thắng", "Phường Tân Bình", "Phường Tân Định", "Phường Tân Đông Hiệp", "Phường Tân Hòa", "Phường Tân Hưng", "Phường Tân Mỹ", "Phường Tân Phú", "Phường Tân Sơn", "Phường Tân Sơn Hòa", "Phường Tân Sơn Nhất", "Phường Tân Sơn Nhì", "Phường Tân Tạo", "Phường Tân Thới Hiệp", "Phường Tân Thuận", "Phường Tăng Nhơn Phú", "Phường Tây Thạnh", "Phường Thạnh Mỹ Tây", "Phường Thới An", "Phường Thới Hòa", "Phường Thông Tây Hội", "Phường Thủ Dầu Một", "Phường Thủ Đức", "Phường Thuận Giao", "Phường Trung Mỹ Tây", "Phường Vĩnh Hội", "Phường Vũng Tàu", "Phường Vườn Lài", "Phường Xóm Chiếu", "Phường Xuân Hòa",
  "Xã Bà Điểm", "Xã Bàu Bàng", "Xã Bình Chánh", "Xã Bình Hưng", "Xã Bình Lợi", "Xã Đất Đỏ", "Xã Hiệp Phước", "Xã Hồ Tràm", "Xã Hóc Môn", "Xã Hưng Long", "Xã Nhà Bè", "Xã Tân An Hội", "Xã Tân Nhựt", "Xã Tân Vĩnh Lộc", "Xã Trừ Văn Thố", "Xã Vĩnh Lộc", "Xã Xuân Thới Sơn"
]

const AMENITIES = [
  "Tất cả", "Hồ bơi", "Gym", "Khuôn viên", "BBQ", "Khu vui chơi trẻ em", "Sân thể thao", 
  "An ninh 24h", "Lễ tân", "Thang máy", "Bãi đậu xe", "Gần Metro", "Gần Bus", "Gần cao tốc", 
  "Gần trường", "Gần bệnh viện", "Gần siêu thị", "Gần chợ", "Gần công viên", "View sông", 
  "View công viên", "View thành phố", "Ban công", "Vườn", "Garage", "Sân thượng"
]

const LEGAL_STATUS_OPTIONS = [
  "Tất cả", "Sổ hồng riêng", "Đang chờ sổ", "Sổ chung", "Không rõ"
]

const FURNITURE_OPTIONS = [
  "Tất cả", "Cơ bản", "Đầy đủ", "Cao cấp", "Không nội thất"
]

const DIRECTIONS = [
  "Tất cả", "Tây - Nam", "Đông - Nam", "Bắc", "Nam", "Đông - Bắc", "Tây - Bắc", "Tây", "Đông", "Không rõ"
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
}

export function AdvancedFilter({ onApplyFilters }: AdvancedFilterProps) {
  const [wardSearch, setWardSearch] = useState("")
  const [selectedWards, setSelectedWards] = useState<string[]>([])
  const [minPrice, setMinPrice] = useState("")
  const [maxPrice, setMaxPrice] = useState("")
  const [minArea, setMinArea] = useState("")
  const [maxArea, setMaxArea] = useState("")
  const [selectedBedrooms, setSelectedBedrooms] = useState("")
  const [selectedBathrooms, setSelectedBathrooms] = useState("")
  const [propertyType, setPropertyType] = useState("Tất cả")
  
  // Array states for 4 checkbox groups with exact Vietnamese strings
  const [selectedLegalStatus, setSelectedLegalStatus] = useState<string[]>([])
  const [selectedFurniture, setSelectedFurniture] = useState<string[]>([])
  const [selectedHouseDirection, setSelectedHouseDirection] = useState<string[]>([])
  const [selectedBalconyDirection, setSelectedBalconyDirection] = useState<string[]>([])
  
  const [selectedAmenities, setSelectedAmenities] = useState<string[]>([])

  const filteredWards = useMemo(() => {
    if (!wardSearch) return WARDS
    return WARDS.filter(ward => 
      ward.toLowerCase().includes(wardSearch.toLowerCase())
    )
  }, [wardSearch])

  const handleWardChange = (ward: string, checked: boolean) => {
    if (ward === "Tất cả") {
      setSelectedWards(checked ? WARDS : [])
    } else {
      let newSelected: string[]
      if (checked) {
        newSelected = [...selectedWards, ward]
        if (newSelected.length === WARDS.length - 1) {
          newSelected = WARDS
        }
      } else {
        newSelected = selectedWards.filter(w => w !== ward && w !== "Tất cả")
      }
      setSelectedWards(newSelected)
    }
  }

  const handleCheckboxGroupChange = (
    item: string,
    checked: boolean,
    allOptions: string[],
    currentSelected: string[],
    setSelected: (items: string[]) => void
  ) => {
    const otherOptions = allOptions.filter(o => o !== "Tất cả")
    
    if (item === "Tất cả") {
      setSelected(checked ? otherOptions : [])
    } else {
      let newSelected: string[]
      if (checked) {
        newSelected = [...currentSelected, item]
      } else {
        newSelected = currentSelected.filter(i => i !== item)
      }
      
      // Auto-check "Tất cả" if all individual items are selected
      if (newSelected.length === otherOptions.length) {
        newSelected = otherOptions
      }
      
      setSelected(newSelected)
    }
  }

  const isAllChecked = (selected: string[], allOptions: string[]) => {
    const otherOptions = allOptions.filter(o => o !== "Tất cả")
    return selected.length === otherOptions.length
  }

  const handleAmenityChange = (amenity: string, checked: boolean) => {
    const otherAmenities = AMENITIES.filter(a => a !== "Tất cả")
    
    if (amenity === "Tất cả") {
      // Checking "Tất cả" selects all amenities (without "Tất cả" itself)
      setSelectedAmenities(checked ? otherAmenities : [])
    } else {
      let newSelected: string[]
      if (checked) {
        newSelected = [...selectedAmenities, amenity]
      } else {
        newSelected = selectedAmenities.filter(a => a !== amenity)
      }
      
      // Auto-select all when all individual amenities are selected
      if (newSelected.length === otherAmenities.length) {
        newSelected = otherAmenities
      }
      
      setSelectedAmenities(newSelected)
    }
  }

  const handleApplyFilters = () => {
    const filters: any = {}

    // Districts/Wards - check if all districts are selected
    const selectedWardsWithoutAll = selectedWards.filter(w => w !== "Tất cả")
    const totalWardsWithoutAll = WARDS.filter(w => w !== "Tất cả").length
    
    // Only include district in payload if user selected a partial list (not all)
    if (selectedWardsWithoutAll.length > 0 && selectedWardsWithoutAll.length < totalWardsWithoutAll) {
      filters.district = selectedWardsWithoutAll.join(",")
    }

    if (minPrice) filters.min_price = parseFloat(minPrice)
    if (maxPrice) filters.max_price = parseFloat(maxPrice)
    if (minArea) filters.min_area = parseFloat(minArea)
    if (maxArea) filters.max_area = parseFloat(maxArea)
    if (selectedBedrooms) filters.bedrooms = parseInt(selectedBedrooms)
    if (selectedBathrooms) filters.bathrooms = parseInt(selectedBathrooms)

    // Property type mapping
    if (propertyType === "Tất cả") {
      filters.property_type = "Căn hộ,Nhà đất"
    } else if (propertyType === "Căn hộ") {
      filters.property_type = "Căn hộ"
    } else if (propertyType === "Nhà đất") {
      filters.property_type = "Nhà đất"
    }

    // Legal status - send exact Vietnamese strings joined by comma
    if (selectedLegalStatus.length > 0) {
      filters.legal_status = selectedLegalStatus.join(",")
    }

    // Furniture - send exact Vietnamese strings joined by comma
    if (selectedFurniture.length > 0) {
      filters.furniture = selectedFurniture.join(",")
    }

    // House direction - send exact Vietnamese strings joined by comma
    if (selectedHouseDirection.length > 0) {
      filters.house_direction = selectedHouseDirection.join(",")
    }

    // Balcony direction - send exact Vietnamese strings joined by comma
    if (selectedBalconyDirection.length > 0) {
      filters.balcony_direction = selectedBalconyDirection.join(",")
    }

    // Amenities - ONLY include boolean flags if user selected specific amenities (not all)
    const otherAmenities = AMENITIES.filter(a => a !== "Tất cả")
    const hasAllAmenities = selectedAmenities.length === otherAmenities.length
    
    // Only add amenity filters if specific amenities are selected (not all)
    if (selectedAmenities.length > 0 && !hasAllAmenities) {
      selectedAmenities.forEach(amenity => {
        const apiParam = AMENITY_MAPPING[amenity]
        if (apiParam) {
          filters[apiParam] = true
        }
      })
    }

    console.log("[v0] Filters payload:", filters)
    onApplyFilters(filters)
  }

  return (
    <Card className="bg-card border border-border rounded-lg shadow-sm overflow-hidden flex flex-col h-full">
      <div className="border-b border-border bg-background p-4 flex items-center gap-2">
        <SlidersHorizontal className="h-5 w-5 text-[#E03C31]" />
        <h2 className="font-semibold text-foreground">Bộ lọc chi tiết</h2>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {/* Vị trí */}
        <div>
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

        {/* Loại BĐS */}
        <div>
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 block">
            Loại BĐS
          </label>
          <Select value={propertyType} onValueChange={setPropertyType}>
            <SelectTrigger className="h-10">
              <SelectValue placeholder="Tất cả" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="Tất cả">Tất cả</SelectItem>
              <SelectItem value="Căn hộ">Căn hộ</SelectItem>
              <SelectItem value="Nhà đất">Nhà đất</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Khoảng giá */}
        <div>
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 block">
            Khoảng giá (VNĐ)
          </label>
          <div className="grid grid-cols-2 gap-3">
            <Input 
              placeholder="Từ" 
              className="h-10" 
              type="number"
              value={minPrice}
              onChange={(e) => setMinPrice(e.target.value)}
            />
            <Input 
              placeholder="Đến" 
              className="h-10" 
              type="number"
              value={maxPrice}
              onChange={(e) => setMaxPrice(e.target.value)}
            />
          </div>
        </div>

        {/* Diện tích */}
        <div>
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 block">
            Diện tích (m²)
          </label>
          <div className="grid grid-cols-2 gap-3">
            <Input 
              placeholder="Từ" 
              className="h-10"
              type="number"
              value={minArea}
              onChange={(e) => setMinArea(e.target.value)}
            />
            <Input 
              placeholder="Đến" 
              className="h-10"
              type="number"
              value={maxArea}
              onChange={(e) => setMaxArea(e.target.value)}
            />
          </div>
        </div>

        {/* Số phòng ngủ & phòng tắm */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 block">
              Số phòng ngủ
            </label>
            <Input 
              placeholder="Tất cả" 
              className="h-10"
              type="number"
              value={selectedBedrooms}
              onChange={(e) => setSelectedBedrooms(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 block">
              Số phòng tắm
            </label>
            <Input 
              placeholder="Tất cả" 
              className="h-10"
              type="number"
              value={selectedBathrooms}
              onChange={(e) => setSelectedBathrooms(e.target.value)}
            />
          </div>
        </div>

        {/* Pháp lý */}
        <div>
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 block">
            Pháp lý
          </label>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1 border border-border rounded-md p-3 max-h-40 overflow-y-auto">
            {LEGAL_STATUS_OPTIONS.map((option) => (
              <label 
                key={option} 
                className="flex items-center gap-2 py-1 hover:bg-muted/50 rounded cursor-pointer text-sm"
              >
                <Checkbox 
                  checked={option === "Tất cả" ? isAllChecked(selectedLegalStatus, LEGAL_STATUS_OPTIONS) : selectedLegalStatus.includes(option)}
                  onCheckedChange={(checked) => handleCheckboxGroupChange(
                    option,
                    checked as boolean,
                    LEGAL_STATUS_OPTIONS,
                    selectedLegalStatus,
                    setSelectedLegalStatus
                  )}
                />
                <span className={option === "Tất cả" ? "font-medium" : ""}>{option}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Nội thất */}
        <div>
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 block">
            Nội thất
          </label>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1 border border-border rounded-md p-3 max-h-40 overflow-y-auto">
            {FURNITURE_OPTIONS.map((option) => (
              <label 
                key={option} 
                className="flex items-center gap-2 py-1 hover:bg-muted/50 rounded cursor-pointer text-sm"
              >
                <Checkbox 
                  checked={option === "Tất cả" ? isAllChecked(selectedFurniture, FURNITURE_OPTIONS) : selectedFurniture.includes(option)}
                  onCheckedChange={(checked) => handleCheckboxGroupChange(
                    option,
                    checked as boolean,
                    FURNITURE_OPTIONS,
                    selectedFurniture,
                    setSelectedFurniture
                  )}
                />
                <span className={option === "Tất cả" ? "font-medium" : ""}>{option}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Hướng nhà */}
        <div>
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 block">
            Hướng nhà
          </label>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1 border border-border rounded-md p-3 max-h-40 overflow-y-auto">
            {DIRECTIONS.map((option) => (
              <label 
                key={option} 
                className="flex items-center gap-2 py-1 hover:bg-muted/50 rounded cursor-pointer text-sm"
              >
                <Checkbox 
                  checked={option === "Tất cả" ? isAllChecked(selectedHouseDirection, DIRECTIONS) : selectedHouseDirection.includes(option)}
                  onCheckedChange={(checked) => handleCheckboxGroupChange(
                    option,
                    checked as boolean,
                    DIRECTIONS,
                    selectedHouseDirection,
                    setSelectedHouseDirection
                  )}
                />
                <span className={option === "Tất cả" ? "font-medium" : ""}>{option}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Hướng ban công */}
        <div>
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 block">
            Hướng ban công
          </label>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1 border border-border rounded-md p-3 max-h-40 overflow-y-auto">
            {DIRECTIONS.map((option) => (
              <label 
                key={option} 
                className="flex items-center gap-2 py-1 hover:bg-muted/50 rounded cursor-pointer text-sm"
              >
                <Checkbox 
                  checked={option === "Tất cả" ? isAllChecked(selectedBalconyDirection, DIRECTIONS) : selectedBalconyDirection.includes(option)}
                  onCheckedChange={(checked) => handleCheckboxGroupChange(
                    option,
                    checked as boolean,
                    DIRECTIONS,
                    selectedBalconyDirection,
                    setSelectedBalconyDirection
                  )}
                />
                <span className={option === "Tất cả" ? "font-medium" : ""}>{option}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Tiện ích */}
        <div>
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 block">
            Tiện ích
          </label>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1 border border-border rounded-md p-3 max-h-48 overflow-y-auto">
            {AMENITIES.map((amenity) => {
              const otherAmenities = AMENITIES.filter(a => a !== "Tất cả")
              const isAllAmenitiesSelected = selectedAmenities.length === otherAmenities.length
              const isChecked = amenity === "Tất cả" ? isAllAmenitiesSelected : selectedAmenities.includes(amenity)
              
              return (
                <label 
                  key={amenity} 
                  className="flex items-center gap-2 py-1 hover:bg-muted/50 rounded cursor-pointer text-sm"
                >
                  <Checkbox 
                    checked={isChecked}
                    onCheckedChange={(checked) => handleAmenityChange(amenity, checked as boolean)}
                  />
                  <span className={amenity === "Tất cả" ? "font-medium" : ""}>{amenity}</span>
                </label>
              )
            })}
          </div>
        </div>
      </div>

      {/* Sticky Button at Bottom */}
      <div className="border-t border-border bg-white p-4">
        <Button 
          onClick={handleApplyFilters}
          className="w-full bg-[#E03C31] hover:bg-[#c43428] text-white h-12 text-base font-medium"
        >
          Áp dụng bộ lọc
        </Button>
      </div>
    </Card>
  )
}
