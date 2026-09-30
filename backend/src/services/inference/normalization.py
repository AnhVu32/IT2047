import json
import re
import unicodedata
from pathlib import Path
from typing import Optional


PROPERTY_TYPE_GROUP_MAP = {
    "Căn hộ chung cư": "Căn hộ",
    "Nhà riêng": "Nhà đất",
    "Nhà mặt phố": "Nhà đất",
    "Nhà biệt thự, liền kề": "Nhà đất",
    "Shophouse, nhà phố thương mại": "Nhà đất",
}

LEGAL_PATTERNS = [
    ("Sổ chung", ["sử dụng chung", "sổ chung"]),
    ("Đang chờ sổ", ["hđmb", "hợp đồng mua bán", "chờ sổ"]),
    ("Sổ hồng riêng", ["sổ hồng riêng", "sổ đỏ", "sổ hồng", "có sổ"]),
]

FURNISHING_PATTERNS = [
    ("Cao cấp", ["cao cấp", "luxury"]),
    ("Đầy đủ", ["đầy đủ", "full nội thất", "full", "hoàn thiện đầy đủ"]),
    ("Cơ bản", ["cơ bản", "nội thất cơ bản"]),
    ("Không nội thất", ["không nội thất", "bàn giao thô"]),
]

DIRECTION_PATTERNS = {
    "Đông - Bắc": ["đông bắc", "đông - bắc"],
    "Tây - Bắc": ["tây bắc", "tây - bắc"],
    "Đông - Nam": ["đông nam", "đông - nam"],
    "Tây - Nam": ["tây nam", "tây - nam"],
    "Đông": ["đông"],
    "Tây": ["tây"],
    "Nam": ["nam"],
    "Bắc": ["bắc"],
}

FEATURE_KEYWORDS = {
    "balcony": ["ban công", "logia", "lô gia"],
    "garden": ["sân vườn", "vườn", "garden"],
    "garage": ["gara", "garage", "ô tô trong nhà"],
    "terrace": ["sân thượng", "terrace"],
    "pool": ["hồ bơi", "pool", "bể bơi"],
    "gym": ["gym", "phòng tập", "yoga", "fitness"],
    "park": ["công viên nội khu", "công viên cây xanh", "sky garden", "vườn dạo bộ"],
    "bbq": ["bbq", "nướng", "khu tiệc nướng"],
    "kids_playground": ["khu vui chơi trẻ em", "sân chơi trẻ em", "kids", "trẻ em"],
    "sports_court": ["sân thể thao", "sports court", "sân tennis", "sân bóng", "pickleball"],
    "security_24h": ["an ninh 24/7", "an ninh", "bảo vệ 24/7", "camera an ninh"],
    "reception": ["lễ tân", "reception", "sảnh đón"],
    "elevator": ["thang máy", "elevator"],
    "parking": ["bãi đỗ", "đậu xe", "hầm xe", "parking", "gara"],
    "near_metro": ["metro", "ga tàu điện"],
    "near_bus": ["xe buýt", "bus", "bến xe"],
    "near_highway": ["cao tốc", "xa lộ", "vành đai", "đại lộ"],
    "near_school": ["trường học", "trường quốc tế", "vinschool", "đại học", "mầm non"],
    "near_hospital": ["bệnh viện", "phòng khám", "trung tâm y tế"],
    "near_mall": ["vincom", "gigamall", "aeon", "trung tâm thương mại", "mall"],
    "near_market": ["chợ", "siêu thị", "coopmart", "bách hóa xanh"],
    "near_park": ["gần công viên", "công viên", "bờ sông", "mảng xanh"],
    "river_view": ["view sông", "sông", "hướng sông"],
    "park_view": ["view công viên", "view nội khu", "view cây xanh"],
    "city_view": ["view thành phố", "city view", "skyline"],
}


def remove_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    lowered = remove_accents(value).lower()
    lowered = lowered.replace("\n", " ")
    return re.sub(r"\s+", " ", lowered).strip()


NORMALIZED_LEGAL_PATTERNS = [
    (target, [normalize_text(pattern) for pattern in patterns]) for target, patterns in LEGAL_PATTERNS
]

NORMALIZED_FURNISHING_PATTERNS = [
    (target, [normalize_text(pattern) for pattern in patterns]) for target, patterns in FURNISHING_PATTERNS
]

NORMALIZED_DIRECTION_PATTERNS = {
    target: [normalize_text(pattern) for pattern in patterns] for target, patterns in DIRECTION_PATTERNS.items()
}


def parse_float_from_text(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    normalized = text.replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)", normalized)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def parse_price_to_billion(price_text: Optional[str]) -> Optional[float]:
    if not price_text:
        return None
    normalized = normalize_text(price_text).replace("ty", " tỷ").replace("trieu", " triệu")
    match = re.search(r"(\d+(?:\.\d+)?)", normalized.replace(",", "."))
    if not match:
        return None
    value = float(match.group(1))
    if "ty" in remove_accents(price_text).lower() or "tỷ" in price_text.lower():
        return round(value, 3)
    if "trieu" in remove_accents(price_text).lower() or "triệu" in price_text.lower():
        return round(value / 1000, 3)
    return round(value, 3)


def parse_area(area_text: Optional[str]) -> Optional[float]:
    return parse_float_from_text(area_text)


def parse_int(value: Optional[str]) -> Optional[int]:
    parsed = parse_float_from_text(value)
    return int(parsed) if parsed is not None else None


def normalize_legal_status(value: Optional[str]) -> str:
    normalized = normalize_text(value)
    for target, patterns in NORMALIZED_LEGAL_PATTERNS:
        if any(pattern in normalized for pattern in patterns):
            return target
    return "Không rõ"


def normalize_furnishing(value: Optional[str]) -> str:
    normalized = normalize_text(value)
    for target, patterns in NORMALIZED_FURNISHING_PATTERNS:
        if any(pattern in normalized for pattern in patterns):
            return target
    return "Không nội thất" if not normalized else "Cơ bản"


def normalize_direction(value: Optional[str]) -> Optional[str]:
    normalized = normalize_text(value)
    if not normalized:
        return None
    for target, patterns in NORMALIZED_DIRECTION_PATTERNS.items():
        if any(pattern == normalized or pattern in normalized for pattern in patterns):
            return target
    return value.strip() if value else None


def has_keyword(text: str, keywords: list[str]) -> bool:
    return any(normalize_text(keyword) in text for keyword in keywords)


def extract_numeric_measure(text: str, labels: list[str]) -> Optional[float]:
    for label in labels:
        pattern = rf"{label}\s*(?:rộng|:)?\s*(\d+(?:[.,]\d+)?)\s*m"
        match = re.search(pattern, text)
        if match:
            return float(match.group(1).replace(",", "."))
    return None


def normalize_property(record: dict) -> dict:
    title = record.get("Tiêu đề") or ""
    description = record.get("Mô tả") or ""
    combined_text = normalize_text(f"{title} {description}")
    property_type = record.get("Loại BĐS") or "Khác"

    normalized = {
        "listing_id": str(record.get("Mã tin") or ""),
        "listing_type": record.get("Loại tin"),
        "property_type": property_type,
        "property_type_group": PROPERTY_TYPE_GROUP_MAP.get(property_type, "Nhà đất"),
        "city_province": record.get("Tỉnh thành") or "Không rõ",
        "district": record.get("Quận huyện") or "Không rõ",
        "title": title,
        "description": description,
        "address": record.get("Địa chỉ"),
        "old_address": record.get("Địa chỉ cũ"),
        "posted_date": record.get("Ngày đăng"),
        "expiry_date": record.get("Ngày hết hạn"),
        "location_link": record.get("Link Location"),
        "latitude_longitude": record.get("Latitude and Longitude"),
        "area_price_history": record.get("Lịch sử giá khu"),
        "price_text": record.get("Khoảng giá"),
        "price_billion": parse_price_to_billion(record.get("Khoảng giá")),
        "area_text": record.get("Diện tích"),
        "area_sqm": parse_area(record.get("Diện tích")),
        "price_per_sqm_text": record.get("Đơn giá"),
        "bedrooms": parse_int(record.get("Số phòng ngủ")),
        "bathrooms": parse_int(record.get("Số phòng tắm, vệ sinh")),
        "balcony_direction": normalize_direction(record.get("Hướng ban công")),
        "house_direction": normalize_direction(record.get("Hướng nhà")),
        "legal_status": normalize_legal_status(record.get("Pháp lý")),
        "furnishing": normalize_furnishing(record.get("Nội thất")),
        "frontage": extract_numeric_measure(combined_text, ["mat tien", "mặt tiền"]),
        "access_road": extract_numeric_measure(combined_text, ["duong truoc nha", "đường", "hem", "hẻm"]),
        "image_list": record.get("image_list") or [],
        "source_payload": record,
    }

    for feature, keywords in FEATURE_KEYWORDS.items():
        normalized[feature] = has_keyword(combined_text, keywords)

    if normalized["balcony_direction"]:
        normalized["balcony"] = True
    if normalized["property_type_group"] == "Căn hộ":
        normalized["elevator"] = normalized["elevator"] or True
        normalized["parking"] = normalized["parking"] or True
    if normalized["garage"]:
        normalized["parking"] = True

    return normalized


def load_normalized_dataset(dataset_path: Path) -> list[dict]:
    records = json.loads(dataset_path.read_text(encoding="utf-8"))
    seen_listing_ids = set()
    normalized_records = []
    for record in records:
        normalized = normalize_property(record)
        listing_id = normalized["listing_id"]
        if not listing_id or listing_id in seen_listing_ids:
            continue
        seen_listing_ids.add(listing_id)
        normalized_records.append(normalized)
    return normalized_records
