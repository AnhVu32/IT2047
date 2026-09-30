"""Cấu hình phân phối cho dữ liệu mô phỏng (cold-start).

Toàn bộ tỷ lệ ở đây được các generator dùng để ép dữ liệu tuân thủ phân phối
"thực tế" thay vì để LLM/RNG tự do trôi về trung bình. Chỉnh ở một chỗ này là
đủ để thay đổi tính chất của toàn bộ dataset sinh ra.

Nguồn tham chiếu field: backend/src/services/inference/knowledge.py
Ngưỡng budget (tỷ VNĐ) khớp PROFILE_RULES: affordable<=3, mid 3-8, luxury>8.
"""
from __future__ import annotations

# --- Reproducibility ---------------------------------------------------------
RANDOM_SEED = 20260723

# --- Quy mô sinh -------------------------------------------------------------
NUM_USERS = 200
# Số interaction trung bình mỗi user (Poisson lambda). Clamp về [MIN, MAX].
INTERACTIONS_PER_USER_LAMBDA = 15
MIN_INTERACTIONS_PER_USER = 10
MAX_INTERACTIONS_PER_USER = 20

# --- Phân khúc giá (budget segment) -----------------------------------------
# Guide: 60% rẻ / 30% trung cấp / 10% cao cấp.
BUDGET_SEGMENTS = {
    "affordable": {"weight": 0.60, "price_range": (1.2, 3.0)},
    "mid_range": {"weight": 0.30, "price_range": (3.0, 8.0)},
    "luxury": {"weight": 0.10, "price_range": (8.0, 30.0)},
}

# --- Intent ------------------------------------------------------------------
INTENT_WEIGHTS = {
    "buy_for_living": 0.55,
    "investment": 0.30,
    "rent": 0.15,
}

# --- Demographics ------------------------------------------------------------
AGE_GROUP_WEIGHTS = {"20-30": 0.25, "30-40": 0.40, "40-50": 0.22, "50+": 0.13}
MARITAL_WEIGHTS = {"single": 0.38, "married": 0.62}
INCOME_WEIGHTS = {"medium": 0.45, "medium_high": 0.40, "high": 0.15}
# Số con — phân phối theo tình trạng hôn nhân. Dân VN thường 0-3 (giá trị 0-10).
# married mean ~1.5 con (khớp TFR VN ~2, nhiều nhà 1-2 con).
CHILDREN_DIST = {
    "single": {0: 0.92, 1: 0.06, 2: 0.02},
    "married": {0: 0.20, 1: 0.30, 2: 0.32, 3: 0.14, 4: 0.03, 5: 0.01},
}
MAX_CHILDREN = 10

PROPERTY_TYPES = ["Căn hộ", "Nhà phố", "Đất nền", "Biệt thự"]
PROPERTY_TYPE_WEIGHTS = [0.55, 0.28, 0.10, 0.07]

# --- Action types & trọng số (dùng cho Edge weight + implicit_score) ---------
# Guide: view=1, save=3, share=4, contact=5.
ACTION_WEIGHTS = {"view": 1.0, "save": 3.0, "share": 4.0, "contact": 5.0}
# Phân phối tần suất action trong một phiên (đa số là view).
ACTION_FREQ = {"view": 0.70, "save": 0.16, "share": 0.05, "contact": 0.09}

# --- Nguồn traffic (source) --------------------------------------------------
SOURCE_WEIGHTS = {
    "ai_recommendation": 0.40,
    "search_bar": 0.30,
    "homepage": 0.18,
    "related_items": 0.12,
}

# --- Dwell time (giây) -------------------------------------------------------
# Lognormal; < BOUNCE_THRESHOLD được coi là click ảo (bounce).
DWELL_LOGNORMAL_MEAN = 3.9   # ln-space -> median ~ e^3.9 ~ 49s
DWELL_LOGNORMAL_SIGMA = 0.9
DWELL_MAX_SECONDS = 1200
BOUNCE_THRESHOLD_SECONDS = 10
# Dwell dùng để chuẩn hoá implicit_score; ngưỡng "no" bão hoà.
DWELL_SATURATION_SECONDS = 180

# --- Mô hình sinh interaction: quan hệ user<->listing -----------------------
# Tỷ lệ interaction "relevant" (khớp preferences của user) vs "noise" (nhiễu,
# khám phá). Đây là tín hiệu ground-truth để evaluation có ý nghĩa.
P_RELEVANT_INTERACTION = 0.75

# Khi khớp preferences: listing càng khớp thì càng dễ có action mạnh
# (contact/save). Hệ số này khuếch đại tương quan relevance -> action strength.
RELEVANCE_ACTION_BOOST = 1.6

# --- Districts: CHỈ LÀ FALLBACK ----------------------------------------------
# Quận/phường THẬT dùng cho listing & user preference được rút từ
# Data/Final_Data.csv qua catalog.derive_pools() (tên phường/xã SAU sáp nhập).
# Danh sách dưới (tên quận CŨ) chỉ dùng khi gọi generate_users() độc lập, không
# truyền pools (vd test) — pipeline chính KHÔNG dùng.
DISTRICTS = [
    "Quận 1", "Quận 2", "Quận 3", "Quận 4", "Quận 7", "Quận 9",
    "Quận Bình Thạnh", "Quận Gò Vấp", "Quận Thủ Đức", "Quận Tân Bình",
    "Phường Long Bình", "Phường Dĩ An", "Phường An Phú", "Phường Hiệp Bình",
]
# Trọng số quận (một vài quận hot hơn).
DISTRICT_WEIGHTS = [
    0.10, 0.09, 0.07, 0.05, 0.11, 0.10,
    0.08, 0.06, 0.09, 0.05,
    0.05, 0.05, 0.03, 0.02,
]
