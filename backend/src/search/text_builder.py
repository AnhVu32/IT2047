from __future__ import annotations

import re
from typing import Mapping


FEATURE_LABELS = {
    "pool": "hồ bơi", "gym": "phòng gym", "park": "công viên nội khu",
    "bbq": "khu BBQ", "kids_playground": "khu vui chơi trẻ em",
    "sports_court": "sân thể thao", "security_24h": "an ninh 24/7",
    "reception": "lễ tân", "elevator": "thang máy", "parking": "bãi đậu xe",
    "near_metro": "gần metro", "near_bus": "gần xe buýt",
    "near_highway": "gần cao tốc", "near_school": "gần trường học",
    "near_hospital": "gần bệnh viện", "near_mall": "gần trung tâm thương mại",
    "near_market": "gần chợ", "near_park": "gần công viên",
    "river_view": "view sông", "park_view": "view công viên",
    "city_view": "view thành phố", "balcony": "ban công", "garden": "sân vườn",
    "garage": "gara", "terrace": "sân thượng",
}


def clean_marketing_text(value: str, max_chars: int = 1800) -> str:
    text = re.sub(r"(?:\+?84|0)\d[\d .-]{7,12}", " ", value or "")
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"(.)\1{4,}", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def build_listing_search_text(item: Mapping) -> str:
    features = [label for key, label in FEATURE_LABELS.items() if item.get(key)]
    specs = []
    for key, label, unit in (
        ("bedrooms", "phòng ngủ", ""), ("bathrooms", "phòng tắm", ""),
        ("area", "diện tích", "m²"), ("price_range", "giá", "tỷ VNĐ"),
    ):
        if item.get(key) is not None:
            specs.append(f"{label} {item[key]} {unit}".strip())
    sections = [
        f"Loại bất động sản: {item.get('property_type') or 'Không rõ'}.",
        f"Tiêu đề: {clean_marketing_text(str(item.get('title') or ''), 400)}.",
        f"Mô tả: {clean_marketing_text(str(item.get('description') or ''))}.",
        f"Vị trí: {item.get('district') or ''}; {item.get('former_admin_area') or ''}; {item.get('address') or ''}.",
        f"Đặc điểm: {', '.join(specs)}.",
        f"Nội thất: {item.get('furnishing') or 'Không rõ'}. Pháp lý: {item.get('legal_status') or 'Không rõ'}.",
        f"Tiện ích: {', '.join(features) if features else 'Không rõ'}.",
    ]
    return " ".join(section for section in sections if section)

