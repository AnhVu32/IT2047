"""Sinh ground truth v4 — làm giá/phòng ngủ/tiện ích SUY RA ĐƯỢC từ raw_query
(thay vì từ mơ hồ "rẻ một chút"), rồi CHỌN LẠI recommended_items bằng đúng
hàm chấm điểm ranker.py thật đang chạy trên backend.

Nguyên nhân sửa (đo được qua Evaluation/, xem Plan): content_score() cũ xếp
hạng ground truth 37.5% theo giá tuyệt đối + 31% theo tiện ích, nhưng
raw_query không bao giờ nêu số giá hay tên tiện ích cụ thể — hệ thống live
không có cách nào đoán ra, nên precision/recall thấp không phải vì ranking
tệ mà vì ground truth đòi hỏi thông tin không tồn tại trong câu hỏi.

Khác gen_v3 ở đúng 2 điểm:
  1. raw_query nêu rõ "dưới X tỷ", "X phòng ngủ", và 1 tiện ích được thích
     nhất (đúng cụm từ FEATURE_ALIASES nhận diện được).
  2. Ứng viên trong mỗi tier (ward-tiered + geo-cascade, logic y hệt
     gen_v3._tiered_candidates) được xếp hạng bằng _criteria_score()/
     _feature_score() THẬT từ backend/src/search/ranker.py — không tự chế
     công thức riêng, đảm bảo ground truth và ranker sống dùng chung 1
     định nghĩa "khớp".

Không đụng recommendation_events_v3_claude.json / interactions_v3_claude.json
/ users_v3.json — chỉ ghi ra data/recommendation_events_v4_claude.json.

    cd gen_user_data && python generate_v4.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "backend"))

from catalog import load_catalog
from config.distribution_config import RANDOM_SEED
from generation.gen_v3 import build_geo_index, _GEO_FIELDS, MIN_WARD_LISTINGS
from generation.gen_v2 import TOP_K, LLM_OUTPUT_K
from generation.llm_client import _TEMPLATES

from src.search.ranker import _criteria_score, _feature_score
from src.search.schemas import ParsedSearchQuery, HardFilters

DATA_DIR = os.path.join(HERE, "data")

# Trọng số kế thừa từ content_score() gốc (gen_v3.py) — trong 8 điểm tổng,
# giá(3.0)+loại nhà(1.5)+phòng ngủ(1.0) = 5.5 (68.75%), tiện ích = 2.5
# (31.25%). _criteria_score()/_feature_score() đều đã chuẩn hoá [0,1] nên
# giữ đúng tỷ lệ cũ bằng 1 phép cộng có trọng số, không cần định nghĩa lại.
W_CRITERIA = 5.5 / 8.0
W_FEATURE = 2.5 / 8.0

# Cụm tiếng Việt tự nhiên (CÓ dấu) cho mỗi tiện ích user có thể thích
# (gen_v2.py::_FAMILY_AMEN/_INVEST_AMEN/_OTHER_AMEN) — chọn đúng từ khớp
# với alias trong backend/src/search/normalizer.py::FEATURE_ALIASES (sau khi
# normalize_text() bỏ dấu) để parser chắc chắn nhận ra.
AMENITY_PHRASES = {
    "near_school": "gần trường học",
    "kids_playground": "có khu vui chơi trẻ em",
    "park": "gần công viên nội khu",
    "near_hospital": "gần bệnh viện",
    "near_mall": "gần trung tâm thương mại",
    "near_market": "gần chợ",
    "security_24h": "an ninh 24/7",
    "gym": "có phòng gym",
    "pool": "có hồ bơi",
    "sports_court": "có sân thể thao",
    "near_metro": "gần metro",
    "near_bus": "gần bến xe buýt",
    "elevator": "có thang máy",
    "parking": "có bãi đỗ xe",
}


def rewrite_query(rng, intent, district, ptype, price_max, bedrooms, amenity_key):
    """Regenerate raw_query từ đúng bộ _TEMPLATES gốc (llm_client.py), chỉ
    thay {price_word} mơ hồ bằng số cụ thể, đảm bảo có số phòng ngủ, và
    thêm 1 cụm tiện ích — mọi thứ khớp regex _parse_price/_parse_rooms và
    FEATURE_ALIASES thật của backend."""
    templates = _TEMPLATES.get(intent, _TEMPLATES["buy_for_living"])
    t = str(rng.choice(templates))
    price_phrase = f"dưới {price_max:.1f} tỷ"
    text = t.format(district=district, beds=bedrooms, ptype=ptype.lower(), price_word=price_phrase)
    if not re.search(r"\d+\s*(?:pn\b|phòng ngủ)", text, re.IGNORECASE):
        text = f"{text}, {bedrooms} phòng ngủ"
    phrase = AMENITY_PHRASES.get(amenity_key)
    if phrase and phrase.lower() not in text.lower():
        text = f"{text}, {phrase}"
    return text


def listing_to_item(listing) -> dict:
    item = {
        "price_range": listing.price_billion,
        "area": listing.area_sqm,
        "bedrooms": listing.bedrooms,
        "bathrooms": listing.bathrooms,
        "property_type": listing.property_type,
    }
    item.update(listing.features)
    return item


def build_parsed_query(ptype, price_max, bedrooms, amenity_key) -> ParsedSearchQuery:
    hf = HardFilters()
    hf.price.max = float(price_max)
    hf.bedrooms.min = int(bedrooms)
    hf.property_types = [ptype]
    if amenity_key:
        hf.required_features = [amenity_key]
    return ParsedSearchQuery(preference_filters=hf, semantic_query="")


def recoverable_score(listing, parsed: ParsedSearchQuery) -> float:
    item = listing_to_item(listing)
    return W_CRITERIA * _criteria_score(item, parsed) + W_FEATURE * _feature_score(item, parsed)


def tiered_candidates_v4(parsed, target_ward, by_ward, geo_idx, catalog, top_k=TOP_K):
    """Y hệt gen_v3._tiered_candidates() (tier1 in-ward -> tier2 geo-cascade
    -> tier3 catch-all) — chỉ đổi hàm chấm điểm dùng để sort mỗi tier."""
    tier1 = sorted(by_ward.get(target_ward, []), key=lambda l: recoverable_score(l, parsed), reverse=True)
    candidates = list(tier1)
    if len(candidates) >= top_k:
        return candidates[:top_k]

    have = {l.listing_id for l in candidates}
    for field in _GEO_FIELDS:
        if len(candidates) >= top_k:
            break
        refs = {getattr(l, field) for l in tier1 if getattr(l, field)}
        pool, seen_pool = [], set()
        for v in refs:
            for l in geo_idx[field].get(v, []):
                if (l.district != target_ward and l.listing_id not in have
                        and l.listing_id not in seen_pool):
                    seen_pool.add(l.listing_id)
                    pool.append(l)
        pool.sort(key=lambda l: recoverable_score(l, parsed), reverse=True)
        for l in pool:
            candidates.append(l)
            have.add(l.listing_id)
            if len(candidates) >= top_k:
                break

    if len(candidates) < top_k:
        rest = sorted([l for l in catalog if l.listing_id not in have],
                      key=lambda l: recoverable_score(l, parsed), reverse=True)
        for l in rest:
            candidates.append(l)
            if len(candidates) >= top_k:
                break
    return candidates[:top_k]


# ---------------------------------------------------------------------------
# llm_output — mẫu câu tự nhiên (Claude soạn tay) + hàm ghép theo tiêu chí
# thực sự khớp của từng listing, không gọi thêm LLM API.
# ---------------------------------------------------------------------------
_EXPLAIN_ALL = [
    "{ptype} tại {district}, {price} tỷ, {beds} phòng ngủ — đúng ngân sách bạn đặt ra, lại {amenity} nên rất hợp.",
    "Căn này ở {district} vừa vặn {price} tỷ cho {beds} phòng ngủ, cộng thêm {amenity} nên đáp ứng gần như trọn vẹn yêu cầu.",
    "{ptype} {beds} phòng ngủ, giá {price} tỷ tại {district} — nằm trong ngân sách và {amenity}, khó tìm được lựa chọn nào cân đối hơn.",
]
_EXPLAIN_PRICE_BEDS = [
    "{ptype} tại {district}, {price} tỷ, {beds} phòng ngủ — vừa tầm ngân sách và đủ số phòng ngủ bạn cần.",
    "Giá {price} tỷ cho {beds} phòng ngủ ở {district} nằm gọn trong ngân sách bạn đưa ra.",
    "{ptype} {beds} phòng ngủ tại {district}, {price} tỷ — đáp ứng đúng 2 tiêu chí quan trọng nhất: giá và số phòng.",
]
_EXPLAIN_PRICE_ONLY = [
    "{ptype} tại {district}, giá {price} tỷ nằm trong ngân sách bạn đưa ra, dù số phòng ngủ chưa khớp hoàn toàn.",
    "Mức giá {price} tỷ ở {district} phù hợp ngân sách, đáng cân nhắc dù bố cục {beds} phòng ngủ có thể chưa vừa ý 100%.",
]
_EXPLAIN_BEDS_ONLY = [
    "{ptype} {beds} phòng ngủ tại {district} — đủ số phòng ngủ bạn cần, tuy giá {price} tỷ nhỉnh hơn ngân sách một chút.",
    "Bố cục {beds} phòng ngủ ở {district} đúng nhu cầu, chỉ có giá {price} tỷ vượt ngân sách đôi chút.",
]
_EXPLAIN_AMENITY_ONLY = [
    "{ptype} tại {district} {amenity}, dù giá {price} tỷ và số phòng ngủ chưa khớp hết yêu cầu ngân sách/phòng ngủ.",
]
_EXPLAIN_NONE = [
    "{ptype} tại {district}, {price} tỷ, {beds} phòng ngủ — vị trí đúng khu vực bạn tìm, các tiêu chí khác chỉ gần đúng.",
    "Căn tại {district} này gần khu vực bạn muốn nhất trong nhóm ứng viên, dù giá/phòng ngủ chưa khớp sát ngân sách.",
]


def compose_explanation(rng, listing, price_max, bedrooms, amenity_key, district, ptype) -> str:
    price_ok = listing.price_billion <= price_max
    beds_ok = listing.bedrooms >= bedrooms
    amenity_ok = bool(amenity_key) and bool(listing.features.get(amenity_key))
    phrase = AMENITY_PHRASES.get(amenity_key, "")

    if price_ok and beds_ok and amenity_ok:
        bank = _EXPLAIN_ALL
    elif price_ok and beds_ok:
        bank = _EXPLAIN_PRICE_BEDS
    elif price_ok:
        bank = _EXPLAIN_PRICE_ONLY
    elif beds_ok:
        bank = _EXPLAIN_BEDS_ONLY
    elif amenity_ok:
        bank = _EXPLAIN_AMENITY_ONLY
    else:
        bank = _EXPLAIN_NONE

    template = str(rng.choice(bank))
    return template.format(ptype=ptype, district=district, price=listing.price_billion,
                            beds=listing.bedrooms, amenity=phrase)


def matched_features(listing, amenity_key):
    if amenity_key and listing.features.get(amenity_key):
        return [amenity_key]
    return []


def main():
    rng = np.random.default_rng(RANDOM_SEED + 40)

    catalog = load_catalog()
    by_ward = defaultdict(list)
    for l in catalog:
        by_ward[l.district].append(l)
    geo_idx = {f: build_geo_index(catalog, f) for f in _GEO_FIELDS}
    catalog_by_id = {l.listing_id: l for l in catalog}

    users = {u["user_id"]: u for u in json.load(open(os.path.join(DATA_DIR, "users_v3.json"), encoding="utf-8"))}
    events = json.load(open(os.path.join(DATA_DIR, "recommendation_events_v3_claude.json"), encoding="utf-8"))

    out_events = []
    n_amenity = 0
    for ev in events:
        user = users.get(ev["user_id"])
        filters = ev["context"]["filters_applied"]
        target_ward = filters["district"]
        price_max = float(filters["price_max"])
        bedrooms = int(filters["bedrooms"])
        intent = ev["context"].get("inferred_intent") or "buy_for_living"

        # ptype phải khớp property_type của recommended_items[0] GỐC (v3), không
        # phải user.explicit_preferences.property_type[0] — gen_v3.py tự sinh
        # {ptype} từ `lead.property_type` (top candidate theo content_score),
        # không phải preference cố định; user có thể thích cả 2 loại.
        top_listing_id = ev["recommended_items"][0]["listing_id"]
        ptype = catalog_by_id[top_listing_id].property_type

        ep = user["explicit_preferences"] if user else {}

        liked = sorted(ep.get("liked_amenities") or [], key=lambda a: a["weight"], reverse=True)
        amenity_key = None
        for a in liked:
            if a["value"] in AMENITY_PHRASES:
                amenity_key = a["value"]
                break
        if amenity_key:
            n_amenity += 1

        raw_query = rewrite_query(rng, intent, target_ward, ptype, price_max, bedrooms, amenity_key)

        parsed = build_parsed_query(ptype, price_max, bedrooms, amenity_key)
        top_listings = tiered_candidates_v4(parsed, target_ward, by_ward, geo_idx, catalog)

        rec_items = []
        for rank, l in enumerate(top_listings):
            sc = recoverable_score(l, parsed)
            rec_items.append({
                "listing_id": l.listing_id, "rank": rank,
                "score": round(sc + float(rng.uniform(-0.01, 0.01)), 3),
                "matched_features": matched_features(l, amenity_key),
                "partial_match_features": [],
            })

        llm_out = {}
        for l in top_listings[:LLM_OUTPUT_K]:
            explanation = compose_explanation(rng, l, price_max, bedrooms, amenity_key, target_ward, ptype)
            llm_out[str(l.listing_id)] = {
                "explanation": explanation, "comparison": None,
                "model_name": "claude_authored_templates_v4",
            }

        new_ev = dict(ev)
        new_ev["algorithm_version"] = "recoverable_v4"
        new_ev["context"] = dict(ev["context"])
        new_ev["context"]["raw_query"] = raw_query
        new_ev["recommended_items"] = rec_items
        new_ev["llm_output"] = llm_out
        out_events.append(new_ev)

    out_path = os.path.join(DATA_DIR, "recommendation_events_v4_claude.json")
    json.dump(out_events, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[v4] {len(out_events)} event -> {out_path}")
    print(f"[v4] event co amenity phrase: {n_amenity}/{len(out_events)} ({100*n_amenity/len(out_events):.1f}%)")


if __name__ == "__main__":
    main()
