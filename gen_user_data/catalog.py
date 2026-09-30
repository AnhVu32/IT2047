"""Xây dựng catalog listing từ DỮ LIỆU THẬT `Data/Final_Data.csv`.

Trước đây thuộc tính listing được mô phỏng bằng RNG (vì chỉ có embeddings.pkl =
id + vector). Nay dùng file thật `Data/Final_Data.csv` — có đầy đủ:
giá, diện tích, phòng ngủ/tắm, loại BĐS, **địa chỉ + quận/phường SAU sáp nhập**,
và các cột tiện ích 0/1. Chỉ giữ các listing_id có trong embeddings.pkl (để
embed_cf / content_neighbors dùng được).

Users & interactions vẫn mô phỏng (không có dữ liệu user thật) — nhưng nay tham
chiếu tới listing THẬT nên relevance/ground-truth sát thực tế hơn.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Tuple

import numpy as np

from config import distribution_config as C
from schemas import (
    ACCESSIBILITY_FIELDS,
    AMENITY_FIELDS,
    VIEW_FIELDS,
    Listing,
)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
EMBEDDINGS_PKL = os.path.join(REPO_ROOT, "backend", "src", "data", "embeddings.pkl")
FINAL_DATA_CSV = os.path.join(REPO_ROOT, "Data", "Final_Data.csv")
GRAPH_READY_CSV = os.path.join(
    REPO_ROOT, "Data", "real_estate_graph_ready_v2_address_mapping",
    "Final_Data_graph_ready_filtered.csv")
DATA_DIR = os.path.join(HERE, "data")
LISTINGS_PATH = os.path.join(DATA_DIR, "listings.json")

# Ngưỡng phân khúc tuyệt đối (tỷ VNĐ) — khớp knowledge.py PROFILE_RULES.
_AFFORDABLE_MAX = C.BUDGET_SEGMENTS["affordable"]["price_range"][1]  # 3.0
_MID_MAX = C.BUDGET_SEGMENTS["mid_range"]["price_range"][1]          # 8.0

# Các cột boolean tiện ích trong Listing.features
_FEATURE_FIELDS = AMENITY_FIELDS + ACCESSIBILITY_FIELDS + VIEW_FIELDS


def _budget_group(price: float) -> str:
    if price <= _AFFORDABLE_MAX:
        return "affordable"
    if price <= _MID_MAX:
        return "mid_range"
    return "luxury"


def _geo_lookup() -> dict:
    """listing_id -> (geohash_6, geohash_7, geo_cluster_150m). File graph-ready có
    thể có nhiều dòng cùng listing_id -> giữ dòng đầu. {} nếu thiếu file."""
    import pandas as pd
    if not os.path.exists(GRAPH_READY_CSV):
        return {}
    df = pd.read_csv(GRAPH_READY_CSV,
                     usecols=["listing_id", "geohash_6", "geohash_7", "geo_cluster_150m"])
    df = df.drop_duplicates(subset="listing_id")
    out = {}
    for r in df.itertuples(index=False):
        out[int(r.listing_id)] = (
            None if pd.isna(r.geohash_6) else str(r.geohash_6),
            None if pd.isna(r.geohash_7) else str(r.geohash_7),
            None if pd.isna(r.geo_cluster_150m) else str(r.geo_cluster_150m),
        )
    return out


def _embeddings_ids() -> set:
    import pandas as pd
    if not os.path.exists(EMBEDDINGS_PKL):
        return set()
    df = pd.read_pickle(EMBEDDINGS_PKL)
    return {int(x) for x in df["listing_id"]}


def build_catalog(seed: int = C.RANDOM_SEED, limit: int | None = None) -> List[Listing]:
    """Đọc Final_Data.csv -> Listing thật (lọc theo id có embedding)."""
    import pandas as pd

    if not os.path.exists(FINAL_DATA_CSV):
        raise FileNotFoundError(
            f"Không tìm thấy {FINAL_DATA_CSV}. Đây là nguồn thuộc tính listing THẬT."
        )
    df = pd.read_csv(FINAL_DATA_CSV)
    df = df.drop_duplicates(subset="listing_id")

    # join vùng địa lý (geohash/geo_cluster) từ file graph-ready (nếu có)
    geo = _geo_lookup()

    emb_ids = _embeddings_ids()
    if emb_ids:
        df = df[df["listing_id"].astype(int).isin(emb_ids)]

    # dọn kiểu
    df["area_num"] = pd.to_numeric(df["area"], errors="coerce")
    area_default = float(df["area_num"].median())

    def _parse_latlon(s):
        # định dạng "q=<lat>,<lon>"
        try:
            s = str(s).split("=", 1)[-1]
            lat, lon = s.split(",")
            return round(float(lat), 6), round(float(lon), 6)
        except Exception:
            return None, None

    listings: List[Listing] = []
    for _, r in df.iterrows():
        price = float(r["price_range"])
        area = float(r["area_num"]) if not pd.isna(r["area_num"]) else area_default
        beds = int(r["bedrooms"]) if not pd.isna(r["bedrooms"]) else 0
        baths = int(r["bathrooms"]) if not pd.isna(r["bathrooms"]) else 0

        features = {}
        for f in _FEATURE_FIELDS:
            v = r[f] if f in r else 0
            features[f] = bool(int(v)) if not pd.isna(v) else False

        title = str(r["title"]) if not pd.isna(r.get("title")) else f"BĐS {r['listing_id']}"
        lat, lon = _parse_latlon(r.get("latitude_longitude"))
        gh6, gh7, gcl = geo.get(int(r["listing_id"]), (None, None, None))
        listings.append(
            Listing(
                listing_id=int(r["listing_id"]),
                title=title[:120],
                property_type=str(r["property_type"]),
                district=str(r["district"]),
                address=str(r["address"]) if not pd.isna(r.get("address")) else None,
                city_province=str(r["city_province"]) if not pd.isna(r.get("city_province")) else None,
                latitude=lat, longitude=lon,
                geohash_6=gh6, geohash_7=gh7, geo_cluster_150m=gcl,
                price_billion=round(price, 3),
                area_sqm=round(area, 1),
                bedrooms=max(0, beds),
                bathrooms=max(0, baths),
                budget_group=_budget_group(price),
                features=features,
            )
        )
        if limit and len(listings) >= limit:
            break

    assign_area_price_tier(listings)
    return listings


# --- price tier tương đối theo quận (giữ nguyên logic cũ, nay trên quận THẬT) ---
_AREA_TIER_QUANTILES = (0.33, 0.66)
_MIN_LISTINGS_PER_DISTRICT = 6


def district_price_quantiles(listings: List[Listing]):
    from collections import defaultdict
    by_dist = defaultdict(list)
    all_prices = []
    for l in listings:
        by_dist[l.district].append(l.price_billion)
        all_prices.append(l.price_billion)
    ql, qh = _AREA_TIER_QUANTILES
    g_lo, g_hi = float(np.quantile(all_prices, ql)), float(np.quantile(all_prices, qh))
    stats = {"_global": (g_lo, g_hi)}
    for d, prices in by_dist.items():
        if len(prices) >= _MIN_LISTINGS_PER_DISTRICT:
            stats[d] = (float(np.quantile(prices, ql)), float(np.quantile(prices, qh)))
        else:
            stats[d] = (g_lo, g_hi)
    return stats


def _tier_for(price: float, lo: float, hi: float) -> str:
    if price <= lo:
        return "cheap"
    if price <= hi:
        return "mid"
    return "premium"


def assign_area_price_tier(listings: List[Listing]) -> None:
    stats = district_price_quantiles(listings)
    for l in listings:
        lo, hi = stats.get(l.district, stats["_global"])
        l.price_tier_area = _tier_for(l.price_billion, lo, hi)


def derive_pools(listings: List[Listing]) -> Tuple[List[str], np.ndarray, List[str], np.ndarray]:
    """Rút danh sách quận & loại BĐS THẬT (kèm trọng số theo tần suất) để
    generate_users sinh preference khớp với listing thật."""
    from collections import Counter
    dc = Counter(l.district for l in listings)
    pc = Counter(l.property_type for l in listings)
    districts = [d for d, _ in dc.most_common()]
    d_w = np.array([dc[d] for d in districts], dtype=float)
    ptypes = [p for p, _ in pc.most_common()]
    p_w = np.array([pc[p] for p in ptypes], dtype=float)
    return districts, d_w / d_w.sum(), ptypes, p_w / p_w.sum()


def save_catalog(listings: List[Listing], path: str = LISTINGS_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([l.model_dump() for l in listings], f, ensure_ascii=False, indent=2)


def load_catalog(path: str = LISTINGS_PATH) -> List[Listing]:
    with open(path, encoding="utf-8") as f:
        return [Listing(**row) for row in json.load(f)]


if __name__ == "__main__":
    cat = build_catalog()
    save_catalog(cat)
    seg = {}
    for l in cat:
        seg[l.budget_group] = seg.get(l.budget_group, 0) + 1
    print(f"[catalog] {len(cat)} listing THẬT (Final_Data.csv) -> {LISTINGS_PATH}")
    print("[catalog] budget_group:", {k: round(v / len(cat), 3) for k, v in sorted(seg.items())})
    print("[catalog] số quận (phường) thật:", len({l.district for l in cat}))
    print("[catalog] loại BĐS:", {l.property_type for l in cat})
