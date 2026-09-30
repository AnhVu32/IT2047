"""Sinh user profile mô phỏng -> data/users.json.

Ép phân phối theo config/distribution_config.py (60/30/10 phân khúc giá, intent,
demographics...). Tất định theo RANDOM_SEED để tái lập.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Dict, List

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import distribution_config as C  # noqa: E402
from schemas import (  # noqa: E402
    ACCESSIBILITY_FIELDS,
    AMENITY_FIELDS,
    Demographics,
    ExplicitPreferences,
    UserProfile,
)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "data")
USERS_PATH = os.path.join(DATA_DIR, "users.json")

# Amenity mà từng nhóm nhân khẩu có xu hướng thích (để profile không ngẫu nhiên
# hoàn toàn — tạo tương quan có ý nghĩa cho KG/eval).
_FAMILY_AMENITIES = ["near_school", "kids_playground", "park", "near_hospital"]
_WELLNESS_AMENITIES = ["gym", "pool", "sports_court"]
_MOBILITY_AMENITIES = ["near_metro", "near_bus", "elevator", "parking"]
_INVEST_AMENITIES = ["near_mall", "near_market", "security_24h"]


def _weighted(rng: np.random.Generator, mapping: Dict[str, float]) -> str:
    keys = list(mapping)
    w = np.array([mapping[k] for k in keys], dtype=float)
    return str(rng.choice(keys, p=w / w.sum()))


def _sample_children(rng, marital: str) -> int:
    dist = C.CHILDREN_DIST.get(marital, C.CHILDREN_DIST["single"])
    counts = list(dist.keys())
    probs = np.array([dist[c] for c in counts], dtype=float)
    probs = probs / probs.sum()
    return int(rng.choice(counts, p=probs))


def _liked_amenities(rng, *, children: int, intent: str) -> List[str]:
    pool: List[str] = []
    if children > 0:
        pool += _FAMILY_AMENITIES
    if intent == "investment":
        pool += _INVEST_AMENITIES
    pool += list(rng.choice(_WELLNESS_AMENITIES + _MOBILITY_AMENITIES,
                            size=2, replace=False))
    # loại trùng, giữ thứ tự
    seen, out = set(), []
    for a in pool:
        if a not in seen:
            seen.add(a)
            out.append(a)
    # lấy ngẫu nhiên 2-4 amenity
    k = int(rng.integers(2, min(5, len(out) + 1)))
    idx = rng.choice(len(out), size=min(k, len(out)), replace=False)
    return [out[i] for i in sorted(idx)]


def generate_users(seed: int = C.RANDOM_SEED, n: int = C.NUM_USERS,
                   pools=None) -> List[UserProfile]:
    """pools = (districts, district_weights, ptypes, ptype_weights) rút từ catalog
    THẬT (catalog.derive_pools). None -> fallback list trong config (để test/độc lập)."""
    rng = np.random.default_rng(seed + 1)  # offset để độc lập với catalog

    if pools is not None:
        districts, district_w, ptypes_pool, ptype_w = pools
    else:
        districts = C.DISTRICTS
        district_w = np.array(C.DISTRICT_WEIGHTS) / np.sum(C.DISTRICT_WEIGHTS)
        ptypes_pool = C.PROPERTY_TYPES
        ptype_w = np.array(C.PROPERTY_TYPE_WEIGHTS) / np.sum(C.PROPERTY_TYPE_WEIGHTS)

    seg_names = list(C.BUDGET_SEGMENTS)
    seg_w = np.array([C.BUDGET_SEGMENTS[s]["weight"] for s in seg_names])
    seg_w = seg_w / seg_w.sum()

    users: List[UserProfile] = []
    for i in range(n):
        segment = str(rng.choice(seg_names, p=seg_w))
        lo, hi = C.BUDGET_SEGMENTS[segment]["price_range"]
        # budget_range của user: một khoảng con trong phân khúc.
        b_lo = round(float(rng.uniform(lo, (lo + hi) / 2)), 1)
        b_hi = round(float(rng.uniform((lo + hi) / 2, hi)), 1)

        intent = _weighted(rng, C.INTENT_WEIGHTS)
        age = _weighted(rng, C.AGE_GROUP_WEIGHTS)
        marital = _weighted(rng, C.MARITAL_WEIGHTS)
        income = _weighted(rng, C.INCOME_WEIGHTS)
        children = _sample_children(rng, marital)

        n_dist = int(rng.integers(1, min(4, len(districts) + 1)))
        d_idx = rng.choice(len(districts), size=n_dist, replace=False, p=district_w)
        pref_districts = [districts[j] for j in d_idx]

        # càng nhiều con càng cần nhiều phòng ngủ (>=2 nếu có con, +1 nếu >=3 con)
        if children >= 3:
            min_beds = 3
        elif children >= 1:
            min_beds = 2
        else:
            min_beds = int(rng.integers(1, 3))

        n_ptype = int(rng.integers(1, min(3, len(ptypes_pool) + 1)))
        pt_idx = rng.choice(len(ptypes_pool), size=n_ptype, replace=False, p=ptype_w)
        ptypes = [ptypes_pool[j] for j in pt_idx]

        prefs = ExplicitPreferences(
            preferred_districts=pref_districts,
            min_bedrooms=min_beds,
            budget_range=(b_lo, b_hi),
            property_type=ptypes,
            liked_amenities=_liked_amenities(rng, children=children, intent=intent),
        )
        users.append(
            UserProfile(
                user_id=f"usr_{1000 + i}",
                segment=segment,
                primary_intent=intent,
                demographics=Demographics(
                    age_group=age, marital_status=marital,
                    children=children, income_level=income,
                ),
                explicit_preferences=prefs,
            )
        )
    return users


def save_users(users: List[UserProfile], path: str = USERS_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([u.model_dump() for u in users], f, ensure_ascii=False, indent=2)


def _report(users: List[UserProfile]) -> None:
    from collections import Counter
    seg = Counter(u.segment for u in users)
    intent = Counter(u.primary_intent for u in users)
    n = len(users)
    print(f"[users] {n} users -> {os.path.abspath(USERS_PATH)}")
    print("[users] segment:", {k: round(v / n, 3) for k, v in seg.items()})
    print("[users] intent :", {k: round(v / n, 3) for k, v in intent.items()})


if __name__ == "__main__":
    us = generate_users()
    save_users(us)
    _report(us)
