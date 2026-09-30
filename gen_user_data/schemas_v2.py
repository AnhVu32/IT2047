"""schemas_v2.py — Bản chuẩn hoá của UserProfile & Interaction/Event.

KHÔNG ghi đè schemas.py gốc (recommender.py, generation/, run_eval.py... vẫn
đang import từ đó) — đây là bản đề xuất để review/migrate dần.

Vocab nguồn — CHIA 2 LOẠI khác hẳn nhau, đừng gộp chung:
  * `preferred_districts`/`property_type`: mô tả CATALOG BĐS thật (quận/loại
    nhà đang có để bán) — lấy từ config/vocab_real_data.py + districts_real.json,
    rút trích từ Data/Final_Data.csv thật (đã sáp nhập hành chính 2025,
    "Phường Long Bình" thay "Quận 9" cũ...). KHÔNG dùng
    config/distribution_config.py cho 2 field này nữa — đó là config MÔ
    PHỎNG (dùng tên quận cũ, không khớp catalog thật hiện tại).
  * `age_group`/`marital_status`/`income_level`: đặc điểm NHÂN KHẨU HỌC của
    user — Final_Data.csv là dữ liệu BĐS nên không có "bản thật" để đối
    chiếu; vẫn dùng config/distribution_config.py (giả định hợp lý, không
    phải lỗi) cho 3 field này.

Hai thay đổi triết lý chính so với schemas.py gốc:

1. UserProfile tách rõ 2 loại thông tin:
   - `explicit_preferences`: những gì user CHỦ ĐỘNG cung cấp (chọn filter,
     gõ trong chat) — đáng tin cậy, có thể dùng ngay để lọc/rank.
   - `inferred_attributes`: demographic (tuổi, hôn nhân, con cái, thu nhập)
     mà KHÔNG nền tảng BĐS nào hỏi thẳng lúc user tìm nhà. Field vẫn giữ lại
     (đúng yêu cầu) nhưng mỗi field bọc trong `InferredValue` — mặc định
     value=None, confidence=0 ("chưa biết"), và chỉ được điền khi hệ thống
     (LLM đọc hội thoại, hoặc suy luận hành vi) rút trích được, kèm bằng
     chứng (`evidence`) và độ tin cậy. Tách bạch explicit/inferred cũng cần
     thiết cho Knowledge Graph: cạnh từ dữ liệu explicit nên có trọng số/độ
     tin cậy khác cạnh suy luận.

2. Interaction/Event tách thành 2 bảng thay vì 1:
   - `RecommendationEvent`: 1 dòng / 1 lần hệ thống trả kết quả (retrieval +
     generation). Lưu đủ: query gốc, toàn bộ top-K đã hiển thị (không chỉ
     item user click), và output LLM tại đúng thời điểm đó.
   - `Interaction`: 1 dòng / 1 hành động thật của user (view/save/share/
     contact), trỏ ngược `result_set_id` -> RecommendationEvent.
   Lý do tách: (a) tránh lặp `recommended_items`/`llm_output` trên mọi dòng
   click thuộc cùng 1 lần trả kết quả; (b) `RecommendationEvent` một khi có
   đủ query+context+answer chính là input thẳng cho RAG eval kiểu Ragas
   (Answer Relevance/Context Precision/Faithfulness) — không cần replay lại
   query sau này (LLM không deterministic nên replay có thể ra câu khác);
   (c) có `rank`/`score` cho từng candidate nên tính CTR theo rank, Context
   Precision/Recall thật được — không cần sampled-negatives giả định như
   `run_eval.py` hiện tại.
"""
from __future__ import annotations

import json
import os
import warnings
from typing import Dict, Generic, List, Literal, Optional, Tuple, TypeVar
from pydantic import BaseModel, Field, field_validator

from schemas import (  # nguồn sự thật cho vocab đã ổn định
    BOOLEAN_FEATURE_FIELDS,
    ACTION_TYPES,
    SOURCES,
    INTENTS,
    BUDGET_GROUPS,
)
from config.vocab_real_data import PROPERTY_TYPES_REAL  # catalog thật (Final_Data.csv)
from config.distribution_config import (  # chỉ dùng cho demographic — xem docstring
    AGE_GROUP_WEIGHTS,
    MARITAL_WEIGHTS,
    INCOME_WEIGHTS,
)

AGE_GROUPS = list(AGE_GROUP_WEIGHTS)
MARITAL_STATUSES = list(MARITAL_WEIGHTS)
INCOME_LEVELS = list(INCOME_WEIGHTS)
PROPERTY_TYPES = PROPERTY_TYPES_REAL

# Danh sách quận/phường thật — nạp động từ config/districts_real.json (sinh
# bởi extract_vocab.py qua pandas.read_csv trên Data/Final_Data.csv, đã sáp
# nhập hành chính 2025). Không hardcode ở đây vì danh sách lớn/có thể đổi.
_DISTRICTS_REAL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "config", "districts_real.json"
)
try:
    with open(_DISTRICTS_REAL_PATH, encoding="utf-8") as _f:
        DISTRICTS: Optional[List[str]] = list(json.load(_f).keys())
except FileNotFoundError:
    DISTRICTS = None  # chưa chạy extract_vocab.py — validator sẽ bỏ qua, không chặn cứng
    warnings.warn(
        "config/districts_real.json không tồn tại — preferred_districts sẽ KHÔNG được "
        "validate theo catalog thật. Chạy `cd gen_user_data && python extract_vocab.py` "
        "để sinh danh sách quận/phường thật (sau sáp nhập 2025) rồi import lại.",
        stacklevel=2,
    )

PREFERENCE_SOURCES = ["explicit_filter", "explicit_chat", "inferred_behavior"]
INFERENCE_SOURCES = ["user_stated", "llm_chat_inference", "behavioral_inference"]

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Khối dùng chung
# ---------------------------------------------------------------------------
class Preference(BaseModel):
    """Một sở thích có trọng số — đơn vị cạnh (edge) cho Knowledge Graph.

    Thay list[str] phẳng của schema cũ bằng object có `weight` để (a) build
    cạnh KG có trọng số thay vì nhị phân có/không, (b) phân biệt must-have
    (weight ~1.0) và nice-to-have (weight thấp) — điều mà
    `must_have_features`/`nice_to_have_features` ở tầng request hiện tại có
    dùng nhưng KHÔNG lưu lại vào hồ sơ user.
    """

    value: str
    weight: float = Field(1.0, ge=0.0, le=1.0)
    source: Literal["explicit_filter", "explicit_chat", "inferred_behavior"] = "explicit_filter"
    updated_at: str


class InferredValue(BaseModel, Generic[T]):
    """Một thuộc tính KHÔNG được hỏi trực tiếp — chỉ có giá trị nếu hệ thống
    tự rút trích được từ hội thoại/hành vi. `value=None, confidence=0` là
    trạng thái mặc định thực tế (chưa biết gì), không phải lỗi thiếu dữ liệu.
    """

    value: Optional[T] = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    source: Literal["user_stated", "llm_chat_inference", "behavioral_inference"] = "llm_chat_inference"
    evidence: Optional[str] = None  # trích đoạn hội thoại / tín hiệu hành vi làm căn cứ
    updated_at: Optional[str] = None


# ---------------------------------------------------------------------------
# UserProfile
# ---------------------------------------------------------------------------
class ExplicitPreferences(BaseModel):
    """Chỉ chứa những gì user chủ động cung cấp (filter UI hoặc gõ trong
    chat) — dữ liệu tin cậy nhất, dùng trực tiếp cho hard filter/scoring."""

    preferred_districts: List[Preference] = Field(default_factory=list)
    property_type: List[Preference] = Field(default_factory=list)
    liked_amenities: List[Preference] = Field(default_factory=list)
    min_bedrooms: Optional[int] = Field(None, ge=0)
    budget_range: Optional[Tuple[float, float]] = None  # (min, max) tỷ VNĐ

    @field_validator("preferred_districts")
    @classmethod
    def _check_districts(cls, v: List[Preference]) -> List[Preference]:
        # DISTRICTS = None khi config/districts_real.json chưa được sinh
        # (chưa chạy extract_vocab.py) — bỏ qua validate thay vì chặn cứng,
        # đã cảnh báo (warnings.warn) lúc import module.
        if DISTRICTS is not None:
            unknown = {p.value for p in v} - set(DISTRICTS)
            if unknown:
                raise ValueError(f"district không hợp lệ (không có trong catalog thật): {sorted(unknown)}")
        return v

    @field_validator("property_type")
    @classmethod
    def _check_property_type(cls, v: List[Preference]) -> List[Preference]:
        unknown = {p.value for p in v} - set(PROPERTY_TYPES)
        if unknown:
            raise ValueError(f"property_type không hợp lệ: {sorted(unknown)}")
        return v

    @field_validator("liked_amenities")
    @classmethod
    def _check_amenities(cls, v: List[Preference]) -> List[Preference]:
        unknown = {p.value for p in v} - set(BOOLEAN_FEATURE_FIELDS)
        if unknown:
            raise ValueError(f"amenity không hợp lệ: {sorted(unknown)}")
        return v

    @field_validator("budget_range")
    @classmethod
    def _valid_range(cls, v: Optional[Tuple[float, float]]) -> Optional[Tuple[float, float]]:
        if v is None:
            return v
        lo, hi = v
        if lo < 0 or hi < lo:
            raise ValueError(f"budget_range không hợp lệ: {v}")
        return v


MAX_CHILDREN = 10


class InferredAttributes(BaseModel):
    """Demographic không được hỏi thẳng — điền dần qua chat. Mặc định mọi
    field đều "chưa biết" (value=None, confidence=0)."""

    age_group: InferredValue[str] = Field(default_factory=InferredValue)
    marital_status: InferredValue[str] = Field(default_factory=InferredValue)
    # Số con thực tế (0..MAX_CHILDREN) thay vì bool has_children — cho phép
    # KG/scoring phân biệt "1 con nhỏ" với "3 con" (vd trọng số min_bedrooms,
    # kids_playground/near_school có thể tăng theo số con) thay vì chỉ có/không.
    children: InferredValue[int] = Field(default_factory=InferredValue)
    income_level: InferredValue[str] = Field(default_factory=InferredValue)

    @field_validator("age_group")
    @classmethod
    def _check_age_group(cls, v: InferredValue) -> InferredValue:
        if v.value is not None and v.value not in AGE_GROUPS:
            raise ValueError(f"age_group không hợp lệ: {v.value}")
        return v

    @field_validator("marital_status")
    @classmethod
    def _check_marital_status(cls, v: InferredValue) -> InferredValue:
        if v.value is not None and v.value not in MARITAL_STATUSES:
            raise ValueError(f"marital_status không hợp lệ: {v.value}")
        return v

    @field_validator("children")
    @classmethod
    def _check_children(cls, v: InferredValue) -> InferredValue:
        if v.value is not None and not (0 <= v.value <= MAX_CHILDREN):
            raise ValueError(f"children phải trong [0, {MAX_CHILDREN}]: {v.value}")
        return v

    @field_validator("income_level")
    @classmethod
    def _check_income_level(cls, v: InferredValue) -> InferredValue:
        if v.value is not None and v.value not in INCOME_LEVELS:
            raise ValueError(f"income_level không hợp lệ: {v.value}")
        return v


class UserProfile(BaseModel):
    user_id: str
    created_at: str
    updated_at: str

    # SYSTEM-COMPUTED từ budget_range (ngưỡng giống BUDGET_SEGMENTS trong
    # config/distribution_config.py) — không nhận trực tiếp từ client.
    segment: Optional[Literal["affordable", "mid_range", "luxury"]] = None

    # Đa số nền tảng BĐS hỏi thẳng mục đích tìm nhà (radio "mua để ở / đầu
    # tư / thuê") ngay từ đầu nên vẫn coi là explicit — nhưng None nếu user
    # chưa chọn (vd mới vào chat, chưa kịp hỏi).
    primary_intent: Optional[str] = None

    explicit_preferences: ExplicitPreferences = Field(default_factory=ExplicitPreferences)
    inferred_attributes: InferredAttributes = Field(default_factory=InferredAttributes)

    persona: Optional[str] = None  # bio ngắn do LLM tổng hợp từ hội thoại
    persona_updated_at: Optional[str] = None

    @field_validator("primary_intent")
    @classmethod
    def _check_intent(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in INTENTS:
            raise ValueError(f"primary_intent không hợp lệ: {v}")
        return v


# ---------------------------------------------------------------------------
# RecommendationEvent (retrieval + generation) & Interaction (hành động user)
# ---------------------------------------------------------------------------
class SearchContext(BaseModel):
    raw_query: Optional[str] = None
    filters_applied: Dict[str, object] = Field(default_factory=dict)
    inferred_intent: Optional[str] = None
    budget_group: Optional[str] = None

    @field_validator("inferred_intent")
    @classmethod
    def _check_intent(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in INTENTS:
            raise ValueError(f"inferred_intent không hợp lệ: {v}")
        return v

    @field_validator("budget_group")
    @classmethod
    def _check_budget_group(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in BUDGET_GROUPS:
            raise ValueError(f"budget_group không hợp lệ: {v}")
        return v


class RecommendedItem(BaseModel):
    """Một candidate trong top-K trả về — giữ đủ để build cạnh KG
    Query/Session -RETRIEVED-> Listing có trọng số, và để tính Context
    Precision/Recall (RAG) mà không cần sampled-negatives."""

    listing_id: int
    rank: int = Field(..., ge=0)
    score: float
    matched_features: List[str] = Field(default_factory=list)
    partial_match_features: List[str] = Field(default_factory=list)


class LLMOutput(BaseModel):
    """Snapshot explanation/comparison do LLM sinh TẠI ĐÚNG thời điểm hiển
    thị — không replay query sau này vì LLM không deterministic."""

    explanation: str
    comparison: Optional[str] = None
    model_name: str


class RecommendationEvent(BaseModel):
    """1 dòng / 1 lần hệ thống trả kết quả. Chính là bộ ba (query, context,
    answer) cần cho RAG eval kiểu Ragas — không cần dựng lại từ đâu khác."""

    result_set_id: str
    user_id: Optional[str] = None  # None nếu khách chưa đăng nhập
    session_id: str
    timestamp: str
    algorithm_version: str  # vd "knowledge_hybrid_v1", "popularity_baseline" — để so sánh A/B
    context: SearchContext
    recommended_items: List[RecommendedItem]
    llm_output: Dict[str, LLMOutput] = Field(default_factory=dict)  # key = str(listing_id)


class Interaction(BaseModel):
    interaction_id: str
    result_set_id: Optional[str] = None  # FK -> RecommendationEvent; None nếu action không xuất phát từ 1 danh sách gợi ý cụ thể
    user_id: str
    session_id: str
    listing_id: int
    rank_position: Optional[int] = Field(None, ge=0)  # denormalized để query nhanh, khỏi join
    action_type: str  # view | save | share | contact (không log "impression" ở đây — đã có trong RecommendationEvent.recommended_items)
    timestamp: str
    dwell_time_seconds: int = Field(..., ge=0)
    source: str
    implicit_score: float = Field(..., ge=0)
    is_bounce: bool = False

    @field_validator("action_type")
    @classmethod
    def _valid_action(cls, v: str) -> str:
        if v not in ACTION_TYPES:
            raise ValueError(f"action_type không hợp lệ: {v}")
        return v

    @field_validator("source")
    @classmethod
    def _valid_source(cls, v: str) -> str:
        if v not in SOURCES:
            raise ValueError(f"source không hợp lệ: {v}")
        return v
