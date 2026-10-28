"""Build a clean, label-ready attribute table for the 3,037 listings.

The table is the *ground-truth side* of the benchmark: every relevance label is
computed from these attributes, never from the ranking function of the system
under test (backend/src/search/ranker.py).

Sources (all row-aligned, verified):
  - Data/Final_Data.csv                                   (listing attributes)
  - Data/real_estate_graph_ready_v2_address_mapping/
      Final_Data_graph_ready_filtered.csv                 (geo + driving distances)
Row i of both files == properties.id (i + 1) in the PostgreSQL backup.
"""
from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

# Evaluation/hcmre_q/corpus.py -> repository root is two levels up.
REPO = Path(os.environ.get("IT2047_ROOT", Path(__file__).resolve().parents[2]))
DATA = REPO / "Data"
V2 = DATA / "real_estate_graph_ready_v2_address_mapping"

BOOL_FEATURES = [
    "pool", "gym", "park", "bbq", "kids_playground", "sports_court", "security_24h",
    "reception", "elevator", "parking", "near_metro", "near_bus", "near_highway",
    "near_school", "near_hospital", "near_mall", "near_market", "near_park",
    "river_view", "park_view", "city_view", "balcony", "garden", "garage", "terrace",
]

AMENITY_CATEGORIES = [
    "school", "bus_stop", "supermarket", "market", "park",
    "college_university", "hospital", "mall", "metro",
]

# Approximate WGS84 coordinates of well-known HCMC landmarks (used only for
# landmark-type queries; radius-based labels are therefore robust to ~200 m error).
LANDMARKS = {
    "ben_thanh": (10.7725, 106.6980),       # Chợ Bến Thành
    "tan_son_nhat": (10.8185, 106.6588),    # Sân bay Tân Sơn Nhất
    "landmark81": (10.7949, 106.7218),      # Landmark 81 (Vinhomes Central Park)
    "phu_my_hung": (10.7290, 106.7187),     # Crescent Mall / Phú Mỹ Hưng
    "dhqg": (10.8700, 106.8030),            # Làng Đại học / ĐHQG TP.HCM (Linh Trung)
}


def strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.replace("đ", "d").replace("Đ", "D")


def norm(text: str) -> str:
    text = strip_accents(str(text or "")).lower()
    return re.sub(r"\s+", " ", text).strip()


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dlmb = np.radians(lon2) - np.radians(lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


# ---------------------------------------------------------------------------
# Labeling functions (weak supervision) for descriptive aspects that have no
# structured column. Patterns run on accent-stripped, lower-cased title +
# description. NEG patterns veto a match (negation / "near but not in").
# Precision was audited manually on a random sample (see audit in README).
# ---------------------------------------------------------------------------
ASPECTS = {
    "hem_xe_hoi": dict(
        pos=r"hem xe hoi|hem o ?to|\bhxh\b|hem xe tai|hem thong xe hoi|hem rong xe hoi|"
            r"(?:xe hoi|o ?to|oto) (?:do|dau|vao|ngu|tan|quay dau|tranh|ra vao)[a-z ]{0,12}(?:cua|nha|thoai mai)|"
            r"(?:xe hoi|o ?to|oto) (?:vao|toi|den) tan (?:noi|nha|cua)|"
            r"(?:xe hoi|o ?to|oto) (?:ngu|do) trong nha|gara (?:xe hoi|o ?to|oto)|"
            r"(?:xe hoi|o ?to|oto) (?:ne|tranh) nhau",
        neg=r"\b(?:cach|gan|sat|ra) hem xe hoi|\b(?:cach|gan|sat) duong xe hoi|hem xe may|hem ba gac",
        types={"Nhà đất"},
    ),
    "dong_tien": dict(
        pos=r"\bchdv\b|can ho dich vu|\bday tro\b|\bnha tro\b|\bphong tro\b|dong tien|"
            r"thu nhap (?:on dinh|deu|hang thang|\d)|hop dong thue|\bhdt\b|doanh thu|"
            r"dang cho thue (?:\d|duoc|voi|gia)|cho thue (?:\d+[.,]?\d*) ?(?:tr|trieu)",
        neg=r"\bkhong (?:cho thue|kinh doanh)",
        types={"Nhà đất"},
    ),
    "can_goc": dict(
        pos=r"can goc|nha goc|lo goc|\bgoc 2 m|(?:^|[^0-9a-z.,])(?:2|hai) mat tien|(?:^|[^0-9a-z.,])2 ?mt\b|goc hai mat",
        neg=r"khong phai can goc|quy hoach thanh goc|\bqh thanh goc|lo goc \d{3,}",
        types={"Nhà đất", "Căn hộ"},
    ),
    "nha_moi": dict(
        pos=r"moi xay|moi 100|moi tinh|moi hoan thien|moi hoan cong|nha moi (?:dep )?(?:vao|o) (?:ngay|luon)|"
            r"moi ban giao|nha (?:dep )?xay moi\b(?! (?:theo|chia|cao tang|lai))",
        neg=r"\b(?:can|nen|thich hop|phu hop|hop|tien|mua|de|co the|hoac) xay moi|xay moi (?:hoan toan )?theo y",
        types={"Nhà đất", "Căn hộ"},
    ),
    "view_song": dict(
        pos=r"view song|huong song|nhin (?:ra|thang ra|xuong) song|truc dien song|view ra song|"
            r"view (?:truc dien )?song sai gon|ban cong (?:nhin|huong) (?:ra )?song",
        neg=r"\bkhong (?:co )?view song",
        types={"Nhà đất", "Căn hộ"},
    ),
    "thang_may_nha": dict(
        pos=r"thang may",
        neg=r"\b(?:khong|chua) (?:co )?thang may|\bcho (?:lap|gan) thang may|\b(?:khung|ho|o) (?:cho )?thang may|"
            r"\bcho thang may|\b(?:co the|de) (?:lap|gan) thang may",
        types={"Nhà đất"},
    ),
    "san_vuon": dict(
        pos=r"san vuon\b|nha vuon\b|co vuon\b|\bvuon (?:cay|rong|truoc|sau)\b|khoang vuon\b|biet thu vuon\b(?! la[in])",
        neg=r"\bkhong (?:co )?san vuon|thiet ke (?:gara/)?san vuon|xay (?:biet thu )?san vuon|hang xom.{0,40}san vuon|"
            r"(?:view|nhin)[a-z ]{0,25}(?:san|khoang) vuon",
        types={"Nhà đất"},
    ),
    "ho_boi": dict(
        pos=r"ho boi|be boi",
        neg=r"\b(?:gan|cach) ho boi|\bkhong (?:co )?ho boi",
        types={"Nhà đất", "Căn hộ"},
    ),
}

_COMPILED = {
    name: (re.compile(spec["pos"]), re.compile(spec["neg"]) if spec.get("neg") else None)
    for name, spec in ASPECTS.items()
}


def aspect_flags(text_norm: str, prop_type: str) -> dict:
    out = {}
    for name, (pos, neg) in _COMPILED.items():
        if prop_type not in ASPECTS[name]["types"]:
            out[name] = False
            continue
        hit = bool(pos.search(text_norm))
        if hit and neg is not None:
            # Veto only if every positive hit sits inside a negative context.
            positives = [m.start() for m in pos.finditer(text_norm)]
            negatives = [(m.start(), m.end()) for m in neg.finditer(text_norm)]
            hit = any(not any(s - 25 <= p <= e for s, e in negatives) for p in positives)
        out[name] = hit
    return out


def subtype_from_folder(folder: str) -> str:
    part = str(folder).split("/")
    raw = part[3] if len(part) > 3 else ""
    raw = re.sub(r"\s+tại.*", "", raw).strip()
    return {
        "Nhà riêng": "Nhà riêng",
        "Căn hộ chung cư": "Căn hộ chung cư",
        "Nhà mặt phố": "Nhà mặt phố",
        "Nhà biệt thự, liền kề": "Biệt thự/Liền kề",
        "Shophouse, nhà phố thương mại": "Shophouse",
    }.get(raw, "Khác")


def fix_area(area_raw, title: str, description: str):
    """Repair the thousands-separator bug (e.g. '1.038' -> 1038 m²).

    The cleanup notebook turned Vietnamese '1.038' (= 1,038) into 1.038. A value
    < 10 m² is accepted as-is only if the text does not mention area*1000.
    """
    raw = str(area_raw).strip()
    value = pd.to_numeric(raw.replace(",", "."), errors="coerce")
    if pd.isna(value):
        # non-numeric field (e.g. 'z'): take the most frequent "xx m²" mentioned in the text
        found = re.findall(r"(\d+(?:[.,]\d+)?)\s*m(?:2|²)", f"{title} {description}")
        numbers = [float(x.replace(",", ".")) for x in found]
        if numbers:
            return max(set(numbers), key=numbers.count), "area_recovered_from_text"
        return np.nan, "invalid_area"
    # '1.038' style = Vietnamese thousands separator (exactly three decimals).
    if value < 10 and re.fullmatch(r"\d{1,3}\.\d{3}", raw):
        return value * 1000, "area_thousands_separator_fixed"
    return float(value), ""


def build_corpus() -> pd.DataFrame:
    f = pd.read_csv(DATA / "Final_Data.csv")
    g = pd.read_csv(V2 / "Final_Data_graph_ready_filtered.csv", low_memory=False)
    assert (f["listing_id"].values == g["listing_id"].values).all()

    rows = []
    for i, r in f.iterrows():
        gr = g.iloc[i]
        area, area_flag = fix_area(r["area"], r["title"], r["description"])
        text_norm = norm(f"{r['title']} . {r['description']}")
        row = dict(
            doc_id=i + 1,                      # == properties.id in PostgreSQL
            listing_id=int(r["listing_id"]),
            listing_node_id=gr["listing_node_id"],
            property_type=r["property_type"],
            subtype=subtype_from_folder(r["Folder"]),
            ward=r["district"],
            former_area=gr["former_admin_area"],
            price=float(r["price_range"]),
            area=area,
            area_flag=area_flag,
            bedrooms=r["bedrooms"],
            bathrooms=r["bathrooms"],
            legal_status=r["legal_status"],
            furnishing=r["furnishing"],
            house_direction=r["house_direction"],
            lat=float(gr["latitude"]),
            lon=float(gr["longitude"]),
            dist_ben_thanh_km=float(gr["distance_to_ben_thanh_km"]),
            posted_date=pd.to_datetime(r["posted_date"], format="%d/%m/%Y").date().isoformat(),
        )
        for cat in AMENITY_CATEGORIES:
            row[f"drive_{cat}_km"] = float(gr[f"{cat}_driving_distance_km"])
        row.update(aspect_flags(text_norm, r["property_type"]))
        rows.append(row)
    corpus = pd.DataFrame(rows)
    for name, (lat, lon) in LANDMARKS.items():
        corpus[f"dist_{name}_km"] = haversine_km(corpus["lat"], corpus["lon"], lat, lon).round(3)
    return corpus


if __name__ == "__main__":
    c = build_corpus()
    print(c.shape)
    print(c[list(ASPECTS)].sum().to_string())
    print(c["subtype"].value_counts().to_string())
    print(c["area_flag"].value_counts().to_string())
