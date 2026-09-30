"""Sinh interaction/event mô phỏng -> data/interactions.json.

Ý tưởng cốt lõi: tạo TÍN HIỆU ground-truth có kiểm soát để evaluation có nghĩa.

  1. Với mỗi user, tính relevance(user, listing) in [0,1] dựa trên preferences.
  2. Sample listing user tương tác: đa số (P_RELEVANT_INTERACTION) lệch về
     listing relevance cao; phần còn lại là nhiễu/khám phá.
  3. action_type & dwell_time tương quan với relevance (listing càng hợp -> càng
     dễ save/contact, dwell càng lâu).
  4. implicit_score = action_weight * dwell_factor  -> vừa là edge weight cho KG,
     vừa là nhãn liên tục cho NDCG.

Tất định theo RANDOM_SEED. Không cần LLM (raw_query dùng template offline).
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import distribution_config as C  # noqa: E402
from schemas import Interaction, Listing, SearchContext, UserProfile  # noqa: E402
from catalog import load_catalog  # noqa: E402
from generation.generate_users import generate_users  # noqa: E402
from generation.llm_client import QueryGenerator  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "data")
INTERACTIONS_PATH = os.path.join(DATA_DIR, "interactions.json")

# Cửa sổ thời gian sinh event (dùng cho temporal split khi eval).
_WINDOW_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
_WINDOW_DAYS = 120


def relevance(user: UserProfile, listing: Listing) -> float:
    """Điểm khớp user<->listing in [0,1]. Trọng số cộng dồn rồi chuẩn hoá."""
    p = user.explicit_preferences
    score, total = 0.0, 0.0

    # Ngân sách (trọng số cao nhất).
    total += 3.0
    lo, hi = p.budget_range
    if lo <= listing.price_billion <= hi:
        score += 3.0
    else:
        # phạt theo khoảng cách tương đối tới biên gần nhất
        edge = lo if listing.price_billion < lo else hi
        rel_gap = abs(listing.price_billion - edge) / max(edge, 1e-6)
        score += 3.0 * max(0.0, 1.0 - rel_gap)

    # Quận.
    total += 2.0
    if listing.district in p.preferred_districts:
        score += 2.0

    # Loại BĐS.
    total += 1.5
    if listing.property_type in p.property_type:
        score += 1.5

    # Phòng ngủ.
    total += 1.0
    if listing.bedrooms >= p.min_bedrooms:
        score += 1.0
    elif listing.bedrooms == p.min_bedrooms - 1:
        score += 0.5

    # Amenity ưa thích.
    total += 2.5
    if p.liked_amenities:
        hit = sum(1 for a in p.liked_amenities if listing.features.get(a))
        score += 2.5 * hit / len(p.liked_amenities)

    return float(score / total)


def _sample_dwell(rng: np.random.Generator) -> Tuple[int, bool]:
    dwell = float(rng.lognormal(C.DWELL_LOGNORMAL_MEAN, C.DWELL_LOGNORMAL_SIGMA))
    dwell = min(dwell, C.DWELL_MAX_SECONDS)
    dwell_i = int(round(dwell))
    return dwell_i, dwell_i < C.BOUNCE_THRESHOLD_SECONDS


def _action_from_relevance(rng: np.random.Generator, rel: float) -> str:
    """Listing càng hợp -> càng lệch về action mạnh (save/share/contact)."""
    base = np.array([C.ACTION_FREQ[a] for a in ["view", "save", "share", "contact"]])
    # Khuếch đại các action mạnh theo relevance.
    boost = np.array([1.0, 1 + rel * C.RELEVANCE_ACTION_BOOST,
                      1 + rel * C.RELEVANCE_ACTION_BOOST,
                      1 + rel * C.RELEVANCE_ACTION_BOOST * 1.3])
    w = base * boost
    w = w / w.sum()
    return str(rng.choice(["view", "save", "share", "contact"], p=w))


def _implicit_score(action: str, dwell: int) -> float:
    aw = C.ACTION_WEIGHTS[action]
    dwell_factor = min(1.0, math.log1p(dwell) / math.log1p(C.DWELL_SATURATION_SECONDS))
    return round(aw * dwell_factor, 3)


def _filters_from_user(user: UserProfile) -> Dict[str, float]:
    p = user.explicit_preferences
    f: Dict[str, float] = {"price_max": float(p.budget_range[1])}
    if p.min_bedrooms:
        f["bedrooms"] = float(p.min_bedrooms)
    return f


def generate_interactions(
    users: List[UserProfile],
    catalog: List[Listing],
    seed: int = C.RANDOM_SEED,
    candidate_pool: int = 500,
) -> List[Interaction]:
    rng = np.random.default_rng(seed + 2)
    qgen = QueryGenerator(seed=seed + 3)

    listing_by_id = {l.listing_id: l for l in catalog}
    all_ids = np.array([l.listing_id for l in catalog])

    interactions: List[Interaction] = []
    evt_counter = 0

    for user in users:
        # Poisson số event, clamp.
        k = int(np.clip(rng.poisson(C.INTERACTIONS_PER_USER_LAMBDA),
                        C.MIN_INTERACTIONS_PER_USER, C.MAX_INTERACTIONS_PER_USER))

        # Candidate pool ngẫu nhiên để giữ tốc độ, rồi tính relevance.
        pool_idx = rng.choice(len(all_ids), size=min(candidate_pool, len(all_ids)),
                              replace=False)
        pool = [catalog[i] for i in pool_idx]
        rels = np.array([relevance(user, l) for l in pool])

        # Trọng số chọn "relevant": softmax nhọn theo relevance.
        rel_w = np.exp(rels * 4.0)
        rel_w /= rel_w.sum()
        uniform_w = np.ones(len(pool)) / len(pool)

        # Chia k event thành relevant vs noise.
        n_rel = int(round(k * C.P_RELEVANT_INTERACTION))
        chosen_local: List[int] = []
        if n_rel > 0:
            chosen_local += list(rng.choice(len(pool), size=n_rel, replace=True, p=rel_w))
        if k - n_rel > 0:
            chosen_local += list(rng.choice(len(pool), size=k - n_rel, replace=True, p=uniform_w))

        # Mỗi user 1-3 session.
        n_sessions = int(rng.integers(1, 4))
        session_ids = [f"sess_{user.user_id[4:]}_{s}" for s in range(n_sessions)]

        for local_i in chosen_local:
            listing = pool[local_i]
            rel = float(rels[local_i])

            action = _action_from_relevance(rng, rel)
            dwell, is_bounce = _sample_dwell(rng)
            # Bounce thì hạ action về view (không ai contact rồi thoát trong 3s).
            if is_bounce:
                action = "view"
            score = _implicit_score(action, dwell)

            ts = _WINDOW_START + timedelta(
                seconds=float(rng.uniform(0, _WINDOW_DAYS * 86400)))

            intent = user.primary_intent
            ctx = SearchContext(
                raw_query=qgen.generate(
                    intent=intent, district=listing.district,
                    price=listing.price_billion, beds=listing.bedrooms,
                    property_type=listing.property_type,
                    price_tier=listing.price_tier_area),
                filters_applied=_filters_from_user(user),
                inferred_intent=intent,
                budget_group=user.segment,
            )

            interactions.append(
                Interaction(
                    interaction_id=f"evt_{100000 + evt_counter}",
                    user_id=user.user_id,
                    session_id=str(rng.choice(session_ids)),
                    listing_id=listing.listing_id,
                    action_type=action,
                    timestamp=ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    dwell_time_seconds=dwell,
                    source=str(rng.choice(list(C.SOURCE_WEIGHTS),
                                          p=np.array(list(C.SOURCE_WEIGHTS.values()))
                                          / sum(C.SOURCE_WEIGHTS.values()))),
                    context=ctx,
                    implicit_score=score,
                    is_bounce=is_bounce,
                )
            )
            evt_counter += 1

    # LLM (tuỳ chọn): thay raw_query template bằng câu tự nhiên. Dedup theo spec
    # + batch để tiết kiệm token; lỗi thì giữ nguyên câu template.
    if qgen.llm.enabled:
        n = _llm_rewrite_queries(interactions, listing_by_id, qgen)
        print(f"[interactions] LLM raw_query: đã sinh {n}/{len(interactions)} (còn lại giữ template)")

    # Sắp theo timestamp để tiện temporal split.
    interactions.sort(key=lambda x: x.timestamp)
    return interactions


def _llm_rewrite_queries(interactions, listing_by_id, qgen, batch=25) -> int:
    """Sinh raw_query bằng LLM, dedup theo (intent, district, price, beds, ptype)."""
    from generation.llm_client import _TIER_HINT_VI
    uniq = {}  # key -> spec
    key_of = {}  # interaction_id -> key
    for it in interactions:
        l = listing_by_id.get(it.listing_id)
        if not l:
            continue
        tier = l.price_tier_area or "mid"
        # dedup theo (intent, quận, TIER giá tương đối, số phòng, loại) — bỏ giá tuyệt đối
        key = (it.context.inferred_intent, l.district, tier, l.bedrooms, l.property_type)
        key_of[it.interaction_id] = key
        if key not in uniq:
            uniq[key] = {"intent": key[0], "district": key[1],
                         "price_hint": _TIER_HINT_VI.get(tier, tier),
                         "bedrooms": key[3], "type": key[4]}
    keys = list(uniq)
    text_by_key = {}
    for i in range(0, len(keys), batch):
        chunk = keys[i:i + batch]
        specs = [uniq[k] for k in chunk]
        out = qgen.llm_batch(specs)
        if out:
            for k, txt in zip(chunk, out):
                text_by_key[k] = txt
    done = 0
    for it in interactions:
        k = key_of.get(it.interaction_id)
        if k in text_by_key:
            it.context.raw_query = text_by_key[k]
            done += 1
    return done


def save_interactions(items: List[Interaction], path: str = INTERACTIONS_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([it.model_dump() for it in items], f, ensure_ascii=False, indent=2)


def _report(items: List[Interaction]) -> None:
    from collections import Counter
    n = len(items)
    act = Counter(it.action_type for it in items)
    src = Counter(it.source for it in items)
    bounce = sum(1 for it in items if it.is_bounce)
    print(f"[interactions] {n} events -> {os.path.abspath(INTERACTIONS_PATH)}")
    print("[interactions] action:", {k: round(v / n, 3) for k, v in act.items()})
    print("[interactions] source:", {k: round(v / n, 3) for k, v in src.items()})
    print(f"[interactions] bounce rate: {bounce / n:.3f}")


if __name__ == "__main__":
    users = generate_users()
    catalog = load_catalog()
    items = generate_interactions(users, catalog)
    save_interactions(items)
    _report(items)
