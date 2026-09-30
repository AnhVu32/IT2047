"""Sinh dữ liệu theo SCHEMA V2 (schemas_v2.py) — KHÔNG đụng bản v1.

Xuất 3 file (thêm hậu tố _v2, giữ nguyên data cũ):
  * data/users_v2.json                 — UserProfile v2 (explicit vs inferred)
  * data/recommendation_events_v2.json — 1 dòng / 1 lần hệ thống trả top-K + LLM
  * data/interactions_v2.json          — 1 dòng / 1 hành động user, trỏ result_set_id

Listings dùng chung data/listings.json (thật, từ Final_Data.csv).
Phân phối/nhãn vẫn do RNG có seed; LLM (nếu bật) chỉ sinh raw_query + explanation.
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import numpy as np

from config import distribution_config as C
from schemas import Listing
import schemas_v2 as V2
from catalog import load_catalog, derive_pools
from generation.generate_users import _sample_children
from generation.llm_client import LLMClient, QueryGenerator, _TIER_HINT_VI

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "data")

# LLM-as-reranker: retrieval lấy TOP_K=10 ứng viên rồi ĐƯA CẢ 10 cho LLM;
# LLM đọc hết, CHỌN & xếp ra LLM_OUTPUT_K=3 căn tốt nhất để tư vấn.
# -> recommended_items = 10 (đưa vào LLM); llm_output = 3 (LLM chọn ra).
TOP_K = 10                   # số ứng viên retrieval = INPUT gửi cho LLM
LLM_OUTPUT_K = 3             # số OUTPUT LLM chọn ra & giải thích
POSITIVE_ACTIONS = {"save", "share", "contact"}
_WINDOW_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
_WINDOW_DAYS = 120
_PROFILE_CREATED = datetime(2025, 12, 1, tzinfo=timezone.utc)

# xác suất một demographic được hệ thống suy luận (còn lại = chưa biết)
_P_INFERRED = {"age_group": 0.45, "marital_status": 0.6, "children": 0.4, "income_level": 0.35}
_EVIDENCE = {
    "age_group": '"Vợ chồng tôi cũng có tuổi rồi, muốn an cư."',
    "marital_status": '"Nhà em có hai vợ chồng với các cháu."',
    "children": '"Bé nhà em sắp vào lớp 1 nên cần gần trường."',
    "income_level": '"Tài chính bọn em cũng thoải mái một chút."',
}


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _weighted(rng, mapping: Dict[str, float]) -> str:
    keys = list(mapping)
    w = np.array([mapping[k] for k in keys], dtype=float)
    return str(rng.choice(keys, p=w / w.sum()))


def _segment_from_budget(hi: float) -> str:
    if hi <= C.BUDGET_SEGMENTS["affordable"]["price_range"][1]:
        return "affordable"
    if hi <= C.BUDGET_SEGMENTS["mid_range"]["price_range"][1]:
        return "mid_range"
    return "luxury"


# --- amenity similarity (cho partial_match_features) ------------------------
def _load_amenity_sim() -> Dict[tuple, float]:
    path = os.path.join(DATA_DIR, "kg", "similarity_edges.json")
    out = {}
    if os.path.exists(path):
        for e in json.load(open(path, encoding="utf-8")):
            if e["group"] == "amenity":
                out[(e["attr_a"], e["attr_b"])] = e["weight"]
                out[(e["attr_b"], e["attr_a"])] = e["weight"]
    return out


# ---------------------------------------------------------------------------
# Users v2
# ---------------------------------------------------------------------------
_FAMILY_AMEN = ["near_school", "kids_playground", "park", "near_hospital"]
_INVEST_AMEN = ["near_mall", "near_market", "security_24h"]
_OTHER_AMEN = ["gym", "pool", "sports_court", "near_metro", "near_bus", "elevator", "parking"]


def generate_users_v2(catalog: List[Listing], seed: int = C.RANDOM_SEED,
                      n: int = C.NUM_USERS) -> List[V2.UserProfile]:
    rng = np.random.default_rng(seed + 1)
    districts, d_w, ptypes, p_w = derive_pools(catalog)

    seg_price = C.BUDGET_SEGMENTS
    users: List[V2.UserProfile] = []
    for i in range(n):
        seg = _weighted(rng, {s: seg_price[s]["weight"] for s in seg_price})
        lo, hi = seg_price[seg]["price_range"]
        b_lo = round(float(rng.uniform(lo, (lo + hi) / 2)), 1)
        b_hi = round(float(rng.uniform((lo + hi) / 2, hi)), 1)

        intent = _weighted(rng, C.INTENT_WEIGHTS)
        marital = _weighted(rng, C.MARITAL_WEIGHTS)
        age = _weighted(rng, C.AGE_GROUP_WEIGHTS)
        income = _weighted(rng, C.INCOME_WEIGHTS)
        children = _sample_children(rng, marital)

        created = _PROFILE_CREATED + timedelta(days=float(rng.uniform(0, 25)))
        updated = created + timedelta(days=float(rng.uniform(1, 30)))
        c_iso, u_iso = _iso(created), _iso(updated)

        # explicit preferences (Preference có trọng số)
        n_dist = int(rng.integers(1, min(4, len(districts) + 1)))
        d_idx = rng.choice(len(districts), size=n_dist, replace=False, p=d_w)
        pref_d = [V2.Preference(value=districts[j], weight=(1.0 if k == 0 else round(float(rng.uniform(0.4, 0.8)), 2)),
                                source="explicit_filter", updated_at=c_iso)
                  for k, j in enumerate(d_idx)]

        n_pt = int(rng.integers(1, min(3, len(ptypes) + 1)))
        pt_idx = rng.choice(len(ptypes), size=n_pt, replace=False, p=p_w)
        pref_pt = [V2.Preference(value=ptypes[j], weight=1.0, source="explicit_filter", updated_at=c_iso)
                   for j in pt_idx]

        # liked amenities: vài cái explicit + vài cái inferred (trọng số thấp hơn)
        liked_pool = []
        if children > 0:
            liked_pool += _FAMILY_AMEN
        if intent == "investment":
            liked_pool += _INVEST_AMEN
        liked_pool += list(rng.choice(_OTHER_AMEN, size=2, replace=False))
        seen, liked = set(), []
        for a in liked_pool:
            if a not in seen:
                seen.add(a); liked.append(a)
        liked = liked[:int(rng.integers(2, 5))]
        pref_am = []
        for k, a in enumerate(liked):
            if k == 0:
                pref_am.append(V2.Preference(value=a, weight=1.0, source="explicit_chat", updated_at=u_iso))
            else:
                pref_am.append(V2.Preference(value=a, weight=round(float(rng.uniform(0.3, 0.7)), 2),
                                             source="inferred_behavior", updated_at=u_iso))

        min_beds = 3 if children >= 3 else (2 if children >= 1 else int(rng.integers(1, 3)))

        explicit = V2.ExplicitPreferences(
            preferred_districts=pref_d, property_type=pref_pt, liked_amenities=pref_am,
            min_bedrooms=min_beds, budget_range=(b_lo, b_hi))

        # inferred attributes: chỉ điền khi "suy luận được"
        def inf(field, value):
            if rng.random() < _P_INFERRED[field]:
                return V2.InferredValue(value=value, confidence=round(float(rng.uniform(0.5, 0.95)), 2),
                                        source="llm_chat_inference", evidence=_EVIDENCE[field], updated_at=u_iso)
            return V2.InferredValue()  # chưa biết

        inferred = V2.InferredAttributes(
            age_group=inf("age_group", age), marital_status=inf("marital_status", marital),
            children=inf("children", int(children)), income_level=inf("income_level", income))

        users.append(V2.UserProfile(
            user_id=f"usr_{1000 + i}", created_at=c_iso, updated_at=u_iso,
            segment=_segment_from_budget(b_hi), primary_intent=intent,
            explicit_preferences=explicit, inferred_attributes=inferred))
    return users


# ---------------------------------------------------------------------------
# Relevance (v2) — đọc từ explicit_preferences
# ---------------------------------------------------------------------------
def relevance_v2(user: V2.UserProfile, listing: Listing) -> float:
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
    districts = {x.value for x in p.preferred_districts}
    total += 2.0
    if listing.district in districts:
        score += 2.0
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


def _matched_partial(user: V2.UserProfile, listing: Listing, amen_sim) -> tuple:
    liked = [x.value for x in user.explicit_preferences.liked_amenities]
    matched = [a for a in liked if listing.features.get(a)]
    partial = []
    listing_amen = {f for f, v in listing.features.items() if v}
    for a in liked:
        if listing.features.get(a):
            continue
        for b in listing_amen:
            if amen_sim.get((a, b), 0) >= 0.5:
                partial.append(f"{a}~{b}")
                break
    return matched, partial


# ---------------------------------------------------------------------------
# Events + Interactions v2
# ---------------------------------------------------------------------------
def _dwell(rng):
    d = min(float(rng.lognormal(C.DWELL_LOGNORMAL_MEAN, C.DWELL_LOGNORMAL_SIGMA)), C.DWELL_MAX_SECONDS)
    di = int(round(d))
    return di, di < C.BOUNCE_THRESHOLD_SECONDS


def _implicit(action, dwell):
    aw = C.ACTION_WEIGHTS[action]
    return round(aw * min(1.0, math.log1p(dwell) / math.log1p(C.DWELL_SATURATION_SECONDS)), 3)


def generate_events_interactions_v2(users, catalog, seed=C.RANDOM_SEED,
                                    llm: Optional[LLMClient] = None):
    rng = np.random.default_rng(seed + 2)
    qgen = QueryGenerator(seed=seed + 3, llm=llm)
    amen_sim = _load_amenity_sim()
    model_name = llm.model if (llm and llm.enabled) else "template_v1"

    all_ids = np.arange(len(catalog))
    events: List[V2.RecommendationEvent] = []
    interactions: List[V2.Interaction] = []
    evt_c, inter_c = 0, 0

    for user in users:
        T = int(np.clip(rng.poisson(C.INTERACTIONS_PER_USER_LAMBDA),
                        C.MIN_INTERACTIONS_PER_USER, C.MAX_INTERACTIONS_PER_USER))
        n_events = max(1, math.ceil(T / LLM_OUTPUT_K))  # mỗi event user thấy 3 căn
        acts_left = T
        n_sessions = int(rng.integers(1, 4))
        sessions = [f"sess_{user.user_id[4:]}_{s}" for s in range(n_sessions)]

        for e in range(n_events):
            # RETRIEVAL: pool -> rank theo relevance -> TOP_K=10 ứng viên (đưa CẢ 10 cho LLM)
            pool_idx = rng.choice(len(all_ids), size=min(500, len(all_ids)), replace=False)
            pool = [catalog[i] for i in pool_idx]
            rels = np.array([relevance_v2(user, l) for l in pool])
            order = np.argsort(-rels)[:TOP_K]
            top = [(pool[i], float(rels[i])) for i in order]

            ts = _WINDOW_START + timedelta(seconds=float(rng.uniform(0, _WINDOW_DAYS * 86400)))
            rsid = f"rs_{100000 + evt_c}"
            session = str(rng.choice(sessions))
            intent = user.primary_intent

            # query + filters (dùng tier giá theo khu vực của listing top-1)
            lead = top[0][0]
            tier = lead.price_tier_area or "mid"
            raw_query = qgen.template(intent=intent or "buy_for_living", district=lead.district,
                                      price=lead.price_billion, beds=lead.bedrooms,
                                      property_type=lead.property_type, price_tier=tier)
            filters = {"district": str(rng.choice([x.value for x in user.explicit_preferences.preferred_districts]))}
            if user.explicit_preferences.budget_range:
                filters["price_max"] = float(user.explicit_preferences.budget_range[1])
            if user.explicit_preferences.min_bedrooms:
                filters["bedrooms"] = int(user.explicit_preferences.min_bedrooms)

            # recommended_items = CẢ 10 ứng viên retrieval (INPUT cho LLM)
            rec_items = []
            item_info = []  # để đưa vào LLM rerank
            for rank, (listing, rel) in enumerate(top):
                matched, partial = _matched_partial(user, listing, amen_sim)
                rec_items.append(V2.RecommendedItem(
                    listing_id=listing.listing_id, rank=rank,
                    score=round(rel + float(rng.uniform(-0.02, 0.02)), 3),
                    matched_features=matched, partial_match_features=partial))
                item_info.append({"listing": listing, "matched": matched})

            # LLM đọc CẢ 10 -> CHỌN & xếp ra LLM_OUTPUT_K=3 (offline: lấy top-3 retrieval)
            llm_out = _rerank_and_explain(qgen, llm, raw_query, item_info, model_name)

            events.append(V2.RecommendationEvent(
                result_set_id=rsid, user_id=user.user_id, session_id=session, timestamp=_iso(ts),
                algorithm_version="llm_rerank_v2",
                context=V2.SearchContext(raw_query=raw_query, filters_applied=filters,
                                         inferred_intent=intent, budget_group=user.segment),
                recommended_items=rec_items, llm_output=llm_out))

            # User CHỈ thấy LLM_OUTPUT_K căn LLM chọn -> chỉ tương tác trong nhóm này.
            rel_by_id = {c["listing"].listing_id: c for c in item_info}
            shown = [(rel_by_id[int(lid)]["listing"],
                      next(rel for (l, rel) in top if l.listing_id == int(lid)))
                     for lid in llm_out]  # dict giữ đúng thứ tự LLM xếp
            last = (e == n_events - 1)
            n_act = acts_left if last else min(acts_left, int(rng.integers(1, 4)))
            n_act = max(0, min(n_act, len(shown)))
            if n_act > 0:
                rank_w = np.array([(shown[r][1] + 1e-3) / (r + 1) for r in range(len(shown))])
                rank_w /= rank_w.sum()
                chosen = rng.choice(len(shown), size=n_act, replace=False, p=rank_w)
                for r in sorted(chosen):
                    listing, rel = shown[r]
                    dwell, bounce = _dwell(rng)
                    # action mạnh hơn nếu rank cao + relevance cao
                    strong = min(1.0, rel * 1.5) * (1.0 / (r + 1)) ** 0.3
                    base = np.array([C.ACTION_FREQ[a] for a in ["view", "save", "share", "contact"]])
                    boost = np.array([1.0, 1 + strong, 1 + strong, 1 + strong * 1.4])
                    w = base * boost; w /= w.sum()
                    action = str(rng.choice(["view", "save", "share", "contact"], p=w))
                    if bounce:
                        action = "view"
                    it_ts = ts + timedelta(seconds=float(rng.uniform(5, 600)))
                    interactions.append(V2.Interaction(
                        interaction_id=f"evt_{100000 + inter_c}", result_set_id=rsid,
                        user_id=user.user_id, session_id=session, listing_id=listing.listing_id,
                        rank_position=r, action_type=action, timestamp=_iso(it_ts),
                        dwell_time_seconds=dwell,
                        source=str(rng.choice(list(C.SOURCE_WEIGHTS),
                                              p=np.array(list(C.SOURCE_WEIGHTS.values())) / sum(C.SOURCE_WEIGHTS.values()))),
                        implicit_score=_implicit(action, dwell), is_bounce=bounce))
                    inter_c += 1
                    acts_left -= 1
            evt_c += 1

    interactions.sort(key=lambda x: x.timestamp)
    return events, interactions


def _template_explain(listing: Listing, matched) -> str:
    m = ", ".join(matched) if matched else "vị trí và tầm giá phù hợp"
    return f"{listing.property_type} tại {listing.district}, {listing.price_billion} tỷ, {listing.bedrooms}PN — hợp vì {m}."


def _rerank_and_explain(qgen, llm, query: str, item_info: List[dict], model_name: str) -> Dict[str, "V2.LLMOutput"]:
    """Đưa CẢ item_info (10 ứng viên) cho LLM -> LLM CHỌN & xếp ra LLM_OUTPUT_K=3
    căn tốt nhất kèm explanation/comparison. Offline/lỗi -> lấy top-3 retrieval.
    Trả về dict {str(listing_id): LLMOutput} đúng thứ tự LLM chọn."""
    by_id = {c["listing"].listing_id: c for c in item_info}

    if llm and llm.enabled:
        chosen = _llm_rerank(llm, query, item_info)  # list [{listing_id, explanation, comparison}]
        if chosen:
            out, seen = {}, set()
            for r in chosen:
                lid = r.get("listing_id")
                try:
                    lid = int(lid)
                except (TypeError, ValueError):
                    continue
                if lid in by_id and lid not in seen:
                    seen.add(lid)
                    out[str(lid)] = V2.LLMOutput(
                        explanation=str(r.get("explanation", "")).strip() or _template_explain(by_id[lid]["listing"], by_id[lid]["matched"]),
                        comparison=(str(r["comparison"]).strip() if r.get("comparison") else None),
                        model_name=model_name)
                if len(out) >= LLM_OUTPUT_K:
                    break
            if out:
                return out
    # offline / fallback: top-LLM_OUTPUT_K theo retrieval
    return {str(c["listing"].listing_id): V2.LLMOutput(
        explanation=_template_explain(c["listing"], c["matched"]), comparison=None,
        model_name=model_name) for c in item_info[:LLM_OUTPUT_K]}


def _llm_rerank(llm, query: str, item_info: List[dict]) -> Optional[List[dict]]:
    """1 call: gửi CẢ danh sách ứng viên -> LLM chọn & xếp LLM_OUTPUT_K căn tốt nhất."""
    system = (
        f"Bạn là chuyên gia BĐS. Từ danh sách ứng viên, CHỌN đúng {LLM_OUTPUT_K} căn phù hợp "
        f"nhất với YÊU CẦU và xếp hạng giảm dần. CHỈ dùng dữ liệu cho sẵn, không bịa. "
        f"Trả về JSON array {LLM_OUTPUT_K} phần tử: "
        f'[{{"listing_id": <int>, "explanation": "<vì sao hợp>", "comparison": "<điểm mạnh so căn khác>"}}]'
    )
    props = [{"listing_id": c["listing"].listing_id, "type": c["listing"].property_type,
              "district": c["listing"].district, "price_ty": c["listing"].price_billion,
              "bedrooms": c["listing"].bedrooms, "area": c["listing"].area_sqm,
              "matched_features": c["matched"]} for c in item_info]
    user = f"YÊU CẦU: {query}\n\nỨNG VIÊN ({len(props)} căn):\n{json.dumps(props, ensure_ascii=False)}"
    return llm.complete_json_list(system, user, max_tokens=2000)


# ---------------------------------------------------------------------------
def save(obj_list, name):
    path = os.path.join(DATA_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([o.model_dump() for o in obj_list], f, ensure_ascii=False, indent=2)
    return path
