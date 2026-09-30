"""Làm giàu dữ liệu bằng LLM (tuỳ chọn): persona cho user, description cho listing.

Chỉ chạy khi LLM bật (USE_LLM=1 + key). Phân phối/nhãn KHÔNG đổi — chỉ thêm text.
Gọi theo BATCH để tiết kiệm token; lỗi batch nào thì bỏ qua batch đó (giữ None).
"""
from __future__ import annotations

from typing import List

from schemas import Listing, UserProfile
from generation.llm_client import LLMClient

BATCH = 20


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield i, seq[i:i + n]


def enrich_personas(users: List[UserProfile], llm: LLMClient) -> int:
    if not llm.enabled:
        return 0
    system = (
        "Bạn viết chân dung khách hàng bất động sản. Với mỗi input, viết MỘT câu "
        "tiếng Việt (<= 30 từ) mô tả nhu cầu/hoàn cảnh của người mua, giọng tự nhiên. "
        "Trả về JSON array chuỗi, ĐÚNG thứ tự & số lượng input."
    )
    done = 0
    for _, chunk in _chunks(users, BATCH):
        specs = [{
            "segment": u.segment, "intent": u.primary_intent,
            "age": u.demographics.age_group, "marital": u.demographics.marital_status,
            "children": u.demographics.children,
            "budget_ty": u.explicit_preferences.budget_range,
            "districts": u.explicit_preferences.preferred_districts,
            "likes": u.explicit_preferences.liked_amenities,
        } for u in chunk]
        out = llm.complete_json_list(system, __import__("json").dumps(specs, ensure_ascii=False))
        if out and len(out) == len(chunk):
            for u, text in zip(chunk, out):
                u.persona = str(text)
                done += 1
    return done


def enrich_descriptions(listings: List[Listing], llm: LLMClient,
                        limit: int | None = None) -> int:
    if not llm.enabled:
        return 0
    targets = listings if limit is None else listings[:limit]
    system = (
        "Bạn viết mô tả tin đăng bất động sản. Với mỗi input, viết MỘT câu tiếng "
        "Việt (<= 35 từ) mô tả căn nhà hấp dẫn, đúng dữ liệu (giá tỷ, diện tích, "
        "phòng ngủ, quận, tiện ích). KHÔNG bịa tiện ích không có. "
        "Trả về JSON array chuỗi, ĐÚNG thứ tự & số lượng input."
    )
    done = 0
    for _, chunk in _chunks(targets, BATCH):
        specs = [{
            "type": l.property_type, "district": l.district,
            "price_ty": l.price_billion, "area_m2": l.area_sqm,
            "bedrooms": l.bedrooms, "bathrooms": l.bathrooms,
            "amenities": [f for f, v in l.features.items() if v][:6],
        } for l in chunk]
        out = llm.complete_json_list(system, __import__("json").dumps(specs, ensure_ascii=False))
        if out and len(out) == len(chunk):
            for l, text in zip(chunk, out):
                l.description = str(text)
                done += 1
    return done
