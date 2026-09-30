from __future__ import annotations

import re
import unicodedata
from typing import Iterable, List


FEATURE_ALIASES = {
    "pool": ("ho boi", "be boi", "pool"),
    "gym": ("phong gym", "gym", "phong tap"),
    "park": ("khuon vien", "cong vien noi khu"),
    "bbq": ("bbq", "khu nuong"),
    "kids_playground": ("khu vui choi tre em", "san choi tre em"),
    "sports_court": ("san the thao", "san tennis", "san pickleball"),
    "security_24h": ("an ninh 24h", "bao ve 24/7", "an ninh 24/7"),
    "reception": ("le tan", "reception"),
    "elevator": ("thang may",),
    "parking": ("bai dau xe", "bai do xe", "ham xe", "parking"),
    "near_metro": ("gan metro", "gan ga metro", "gan tau dien"),
    "near_bus": ("gan bus", "gan xe buyt", "gan ben xe"),
    "near_highway": ("gan cao toc", "gan vanh dai"),
    "near_school": ("gan truong", "gan truong hoc"),
    "near_hospital": ("gan benh vien",),
    "near_mall": ("gan trung tam thuong mai", "gan tttm", "gan sieu thi"),
    "near_market": ("gan cho", "gan cho dan sinh"),
    "near_park": ("gan cong vien",),
    "river_view": ("view song", "huong song"),
    "park_view": ("view cong vien", "view cay xanh"),
    "city_view": ("view thanh pho", "city view"),
    "balcony": ("ban cong", "lo gia"),
    "garden": ("san vuon", "co vuon"),
    "garage": ("gara", "garage"),
    "terrace": ("san thuong", "terrace"),
}

AMENITY_CATEGORY_ALIASES = {
    "metro": ("metro", "ga metro", "tau dien"),
    "park": ("cong vien", "cay xanh"),
    "school": ("truong hoc", "truong"),
    "hospital": ("benh vien",),
    "mall": ("trung tam thuong mai", "tttm", "sieu thi"),
    "market": ("cho", "cho dan sinh"),
    "bus": ("xe buyt", "bus", "ben xe"),
}

PROPERTY_TYPE_ALIASES = {
    "Căn hộ": ("can ho", "chung cu", "apartment"),
    "Nhà đất": ("nha dat", "nha pho", "nha rieng", "biet thu", "dat nen"),
}


def remove_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_text(value: str) -> str:
    value = remove_accents(value).lower().replace("đ", "d")
    return re.sub(r"\s+", " ", value).strip()


def csv_values(value) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        values: Iterable = value
    else:
        values = str(value).split(",")
    return [str(item).strip() for item in values if str(item).strip()]


def price_to_billion(value: float, unit: str) -> float:
    return value / 1000 if normalize_text(unit).startswith("trieu") else value


def first_alias_match(text: str, aliases: dict[str, tuple[str, ...]]) -> List[str]:
    normalized = normalize_text(text)
    return [key for key, words in aliases.items() if any(word in normalized for word in words)]

