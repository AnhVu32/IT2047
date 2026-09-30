"""Sinh dữ liệu v3 — GROUND TRUTH THEO PHƯỜNG/XÃ (Plan A).

Khác gen_v2 ở khâu tạo GROUND TRUTH (recommended_items):

  gen_v2: mỗi event lấy random 500/3030 căn rồi rank bằng relevance_v2 (district
          chỉ 20% trọng số) -> "ground truth" trải 6-7 phường khác nhau, KHÔNG
          khớp backend (vốn hard-filter theo district) -> eval apples-to-oranges.

  gen_v3 (Plan A): mỗi event có 1 TARGET WARD; ground truth = 2 tier:
    • Tier 1: TẤT CẢ căn thuộc target ward, xếp theo content_score (giá / loại /
      phòng ngủ / tiện ích — KHÔNG có district vì đã cố định).
    • Tier 2: chỉ backfill từ ward khác NẾU target ward có < MIN_WARD_LISTINGS.
    Quét TOÀN BỘ catalog (không sample 500). filters_applied.district = target
    ward (đúng thứ backend lọc). Giảm ~1055 -> ~500 event.

Schema giữ nguyên schemas_v2. Tái sử dụng helper của gen_v2 (user gen, rerank,
matched/partial, dwell...). Xuất data ra *_v3.json (v2 giữ nguyên).

Companion (Plan A): khi eval v3 cần chỉnh Evaluation/adapters.translate_filters_for_live
gửi ĐÚNG target ward (filters_applied.district) thay vì cả danh sách preferred.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import List, Optional

import numpy as np

from config import distribution_config as C
from schemas import Listing
import schemas_v2 as V2
from generation.llm_client import LLMClient, QueryGenerator
from generation.gen_v2 import (
    TOP_K,
    LLM_OUTPUT_K,
    generate_users_v2,      # user gen y hệt v2 (schema không đổi)
    _matched_partial,
    _rerank_and_explain,
    _load_amenity_sim,
    _dwell,
    _implicit,
    _iso,
    _WINDOW_START,
    _WINDOW_DAYS,
)

# --- Plan A config ---------------------------------------------------------
MIN_WARD_LISTINGS = 10       # ward có < ngần này mới backfill sang ward khác
N_EVENTS_MIN, N_EVENTS_MAX = 2, 3   # ~2.5 event/user × 200 user ≈ 500 event


def content_score(user: V2.UserProfile, listing: Listing) -> float:
    """Điểm khớp KHÔNG tính district (district đã cố định theo target ward).
    Dùng để xếp hạng trong từng tier. Trọng số: giá 3.0, tiện ích 2.5,
    loại 1.5, phòng ngủ 1.0 (tổng 8.0)."""
    p = user.explicit_preferences
    score, total = 0.0, 0.0
    total += 3.0
    if p.budget_range:
        lo, hi = p.budget_range
        if lo <= listing.price_billion <= hi:
            score += 3.0
        else:
            edge = lo if listing.price_billion < lo else hi
            score += 3.0 * max(0.0, 1.0 - abs(listing.price_billion - edge) / max(edge, 1e-6))
    ptypes = {x.value for x in p.property_type}
    total += 1.5
    if listing.property_type in ptypes:
        score += 1.5
    total += 1.0
    if p.min_bedrooms is None or listing.bedrooms >= p.min_bedrooms:
        score += 1.0
    liked = {x.value: x.weight for x in p.liked_amenities}
    total += 2.5
    if liked:
        hit = sum(w for a, w in liked.items() if listing.features.get(a))
        score += 2.5 * hit / sum(liked.values())
    return float(score / total)


# Cascade backfill theo vùng địa lý: hẹp -> rộng (Plan A).
_GEO_FIELDS = ("geo_cluster_150m", "geohash_7", "geohash_6")


def build_geo_index(catalog, field) -> dict:
    """{giá trị geo -> [listing]} cho 1 field; bỏ listing thiếu field."""
    idx = {}
    for l in catalog:
        v = getattr(l, field)
        if v:
            idx.setdefault(v, []).append(l)
    return idx


def _tiered_candidates(user, target_ward, by_ward, geo_idx, catalog):
    """(top_listings, n_tier1). Tier1 = in-ward (xếp content_score). Nếu thiếu
    TOP_K, backfill theo CASCADE vùng địa lý của tier1: geo_cluster_150m (~150m)
    -> geohash_7 -> geohash_6 -> bất kỳ đâu. Mỗi bậc xếp theo content_score."""
    tier1 = sorted(by_ward.get(target_ward, []),
                   key=lambda l: content_score(user, l), reverse=True)
    candidates = list(tier1)
    n_tier1_in_top = min(len(tier1), TOP_K)
    if len(candidates) >= TOP_K:
        return candidates[:TOP_K], n_tier1_in_top

    have = {l.listing_id for l in candidates}
    # bậc 2: cụm địa lý của tier1, hẹp -> rộng
    for field in _GEO_FIELDS:
        if len(candidates) >= TOP_K:
            break
        refs = {getattr(l, field) for l in tier1 if getattr(l, field)}
        pool, seen_pool = [], set()
        for v in refs:
            for l in geo_idx[field].get(v, []):
                if (l.district != target_ward and l.listing_id not in have
                        and l.listing_id not in seen_pool):
                    seen_pool.add(l.listing_id)
                    pool.append(l)
        pool.sort(key=lambda l: content_score(user, l), reverse=True)
        for l in pool:
            candidates.append(l)
            have.add(l.listing_id)
            if len(candidates) >= TOP_K:
                break
    # bậc 3 (hiếm): bù bất kỳ đâu để luôn đủ TOP_K
    if len(candidates) < TOP_K:
        rest = sorted([l for l in catalog if l.listing_id not in have],
                      key=lambda l: content_score(user, l), reverse=True)
        for l in rest:
            candidates.append(l)
            if len(candidates) >= TOP_K:
                break
    return candidates[:TOP_K], n_tier1_in_top


def generate_events_interactions_v3(users, catalog, seed=C.RANDOM_SEED,
                                    llm: Optional[LLMClient] = None):
    rng = np.random.default_rng(seed + 2)
    qgen = QueryGenerator(seed=seed + 3, llm=llm)
    amen_sim = _load_amenity_sim()
    model_name = llm.model if (llm and llm.enabled) else "template_v1"

    # FULL-CATALOG SCAN (1 lần): gom theo phường/xã + index vùng địa lý
    by_ward = defaultdict(list)
    for l in catalog:
        by_ward[l.district].append(l)
    geo_idx = {f: build_geo_index(catalog, f) for f in _GEO_FIELDS}

    events: List[V2.RecommendationEvent] = []
    interactions: List[V2.Interaction] = []
    evt_c = inter_c = 0
    tier1_items = tier1_in_ward = 0  # thống kê kiểm chứng

    for user in users:
        pref = [d.value for d in user.explicit_preferences.preferred_districts]
        if not pref:
            continue
        n_events = int(rng.integers(N_EVENTS_MIN, N_EVENTS_MAX + 1))
        n_sessions = int(rng.integers(1, 4))
        sessions = [f"sess_{user.user_id[4:]}_{s}" for s in range(n_sessions)]

        for e in range(n_events):
            target_ward = str(rng.choice(pref))
            top_listings, _ = _tiered_candidates(user, target_ward, by_ward, geo_idx, catalog)
            top = [(l, content_score(user, l)) for l in top_listings]

            ts = _WINDOW_START + timedelta_(rng)
            rsid = f"rs_{300000 + evt_c}"   # tiền tố 3xxxxx cho v3 (tránh trùng v2)
            session = str(rng.choice(sessions))
            intent = user.primary_intent

            lead = top[0][0]
            tier = lead.price_tier_area or "mid"
            raw_query = qgen.template(intent=intent or "buy_for_living", district=target_ward,
                                      price=lead.price_billion, beds=lead.bedrooms,
                                      property_type=lead.property_type, price_tier=tier)
            filters = {"district": target_ward}   # ĐÚNG target ward (khớp backend hard-filter)
            if user.explicit_preferences.budget_range:
                filters["price_max"] = float(user.explicit_preferences.budget_range[1])
            if user.explicit_preferences.min_bedrooms:
                filters["bedrooms"] = int(user.explicit_preferences.min_bedrooms)

            rec_items, item_info = [], []
            for rank, (listing, sc) in enumerate(top):
                matched, partial = _matched_partial(user, listing, amen_sim)
                rec_items.append(V2.RecommendedItem(
                    listing_id=listing.listing_id, rank=rank,
                    score=round(sc + float(rng.uniform(-0.02, 0.02)), 3),
                    matched_features=matched, partial_match_features=partial))
                item_info.append({"listing": listing, "matched": matched})
                tier1_items += 1
                if listing.district == target_ward:
                    tier1_in_ward += 1

            llm_out = _rerank_and_explain(qgen, llm, raw_query, item_info, model_name)

            events.append(V2.RecommendationEvent(
                result_set_id=rsid, user_id=user.user_id, session_id=session, timestamp=_iso(ts),
                algorithm_version="ward_tiered_v3",
                context=V2.SearchContext(raw_query=raw_query, filters_applied=filters,
                                         inferred_intent=intent, budget_group=user.segment),
                recommended_items=rec_items, llm_output=llm_out))

            # interactions: user chỉ thấy LLM_OUTPUT_K căn được chọn
            score_by_id = {l.listing_id: sc for (l, sc) in top}
            listing_by_id = {l.listing_id: l for (l, _) in top}
            shown = [(listing_by_id[int(lid)], score_by_id[int(lid)]) for lid in llm_out]
            n_act = max(0, min(int(rng.integers(1, LLM_OUTPUT_K + 1)), len(shown)))
            if n_act > 0:
                rank_w = np.array([(shown[r][1] + 1e-3) / (r + 1) for r in range(len(shown))])
                rank_w /= rank_w.sum()
                chosen = rng.choice(len(shown), size=n_act, replace=False, p=rank_w)
                for r in sorted(chosen):
                    listing, sc = shown[r]
                    dwell, bounce = _dwell(rng)
                    strong = min(1.0, sc * 1.5) * (1.0 / (r + 1)) ** 0.3
                    base = np.array([C.ACTION_FREQ[a] for a in ["view", "save", "share", "contact"]])
                    w = base * np.array([1.0, 1 + strong, 1 + strong, 1 + strong * 1.4]); w /= w.sum()
                    action = str(rng.choice(["view", "save", "share", "contact"], p=w))
                    if bounce:
                        action = "view"
                    it_ts = ts + _sec(rng, 5, 600)
                    interactions.append(V2.Interaction(
                        interaction_id=f"evt_{300000 + inter_c}", result_set_id=rsid,
                        user_id=user.user_id, session_id=session, listing_id=listing.listing_id,
                        rank_position=r, action_type=action, timestamp=_iso(it_ts),
                        dwell_time_seconds=dwell,
                        source=str(rng.choice(list(C.SOURCE_WEIGHTS),
                                              p=np.array(list(C.SOURCE_WEIGHTS.values())) / sum(C.SOURCE_WEIGHTS.values()))),
                        implicit_score=_implicit(action, dwell), is_bounce=bounce))
                    inter_c += 1
            evt_c += 1

    interactions.sort(key=lambda x: x.timestamp)
    pct = round(100 * tier1_in_ward / tier1_items, 1) if tier1_items else 0.0
    print(f"[gen_v3] ground-truth in-ward: {tier1_in_ward}/{tier1_items} ({pct}%)")
    return events, interactions


# helper thời gian (numpy rng -> timedelta) để tránh import lặp
from datetime import timedelta


def timedelta_(rng):
    return timedelta(seconds=float(rng.uniform(0, _WINDOW_DAYS * 86400)))


def _sec(rng, lo, hi):
    return timedelta(seconds=float(rng.uniform(lo, hi)))
