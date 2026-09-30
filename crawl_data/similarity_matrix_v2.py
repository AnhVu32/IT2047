"""
Ma trận Tương đồng (Similarity Matrix) - Phiên bản gọn
========================================================
Sử dụng TRỰC TIẾP các trường gốc từ Final_Data.json, không tạo field mới.

Gồm 2 ma trận:
1. Ma trận tương đồng TIÊU CHÍ (36x36) — mở rộng tìm kiếm cho user
2. Ma trận tương đồng BĐS (NxN) — so sánh giữa các BĐS với nhau
"""

import json
import math
import numpy as np
import pandas as pd


# ===========================================================================
# PHẦN 1: MA TRẬN TƯƠNG ĐỒNG TIÊU CHÍ (Criteria Similarity Matrix)
# ===========================================================================
#
# 36 tiêu chí chia 5 nhóm theo đề bài: Giá - Diện tích - Tiện ích - Vị trí - Pháp lý
# Giá trị similarity [0, 1] dựa trên tri thức chuyên gia BĐS tại HCM.
#
# Ý nghĩa: Khi user yêu cầu tiêu chí A, hệ thống cũng xét tiêu chí B
# nếu similarity(A, B) >= ngưỡng (mặc định 0.5)

CRITERIA = {
    # --- Giá ---
    "gia_thap": "Giá thấp (dưới 3 tỷ)",
    "gia_trung_binh": "Giá trung bình (3-7 tỷ)",
    "gia_cao": "Giá cao (7-15 tỷ)",
    "gia_rat_cao": "Giá rất cao (trên 15 tỷ)",
    "don_gia_thap": "Đơn giá thấp (dưới 40 tr/m²)",
    "don_gia_cao": "Đơn giá cao (trên 80 tr/m²)",
    # --- Diện tích ---
    "dien_tich_nho": "Diện tích nhỏ (dưới 50m²)",
    "dien_tich_vua": "Diện tích vừa (50-80m²)",
    "dien_tich_lon": "Diện tích lớn (80-150m²)",
    "dien_tich_rat_lon": "Diện tích rất lớn (trên 150m²)",
    "nhieu_phong_ngu": "Nhiều phòng ngủ (>=3 PN)",
    "it_phong_ngu": "Ít phòng ngủ (1-2 PN)",
    # --- Tiện ích ---
    "tien_ich_giao_duc": "Tiện ích giáo dục (trường học, đại học)",
    "tien_ich_y_te": "Tiện ích y tế (bệnh viện, phòng khám)",
    "tien_ich_thuong_mai": "Tiện ích thương mại (siêu thị, chợ, TTTM)",
    "tien_ich_giai_tri": "Tiện ích giải trí (công viên, hồ bơi, gym, spa)",
    "tien_ich_giao_thong": "Tiện ích giao thông (metro, sân bay, bến xe)",
    "noi_that_day_du": "Nội thất đầy đủ/cao cấp",
    "noi_that_co_ban": "Nội thất cơ bản/thô",
    "view_dep": "View đẹp (sông, biển, công viên)",
    "an_ninh_tot": "An ninh tốt (bảo vệ, camera 24/7)",
    "gan_truong_hoc": "Gần trường học",
    "gan_benh_vien": "Gần bệnh viện",
    "gan_sieu_thi": "Gần siêu thị/chợ",
    "gan_cong_vien": "Gần công viên",
    "co_ho_boi": "Có hồ bơi",
    "co_gym": "Có phòng gym/yoga",
    # --- Vị trí ---
    "vi_tri_trung_tam": "Vị trí trung tâm (Q1, Q3, Bình Thạnh, Phú Nhuận)",
    "vi_tri_can_trung_tam": "Vị trí cận trung tâm (Q7, Thủ Đức, Tân Bình)",
    "vi_tri_ngoai_thanh": "Vị trí ngoại thành (Bình Chánh, Hóc Môn, Nhà Bè)",
    "huong_tot": "Hướng tốt (Đông, Đông-Nam, Nam)",
    "huong_xau": "Hướng xấu (Tây, Tây-Nam)",
    # --- Pháp lý ---
    "so_hong_rieng": "Sổ hồng/sổ đỏ riêng",
    "so_chung": "Sổ chung/sử dụng chung",
    "hop_dong_mua_ban": "Hợp đồng mua bán (chưa có sổ)",
    "dang_cho_so": "Đang chờ sổ",
}

SIMILARITY_PAIRS = [
    # --- Giá nội nhóm ---
    ("gia_thap", "gia_trung_binh", 0.5),
    ("gia_trung_binh", "gia_cao", 0.5),
    ("gia_cao", "gia_rat_cao", 0.5),
    ("gia_thap", "gia_cao", 0.15),
    ("gia_thap", "gia_rat_cao", 0.0),
    ("gia_trung_binh", "gia_rat_cao", 0.15),
    ("gia_thap", "don_gia_thap", 0.7),
    ("gia_rat_cao", "don_gia_cao", 0.7),
    ("gia_cao", "don_gia_cao", 0.5),
    ("gia_trung_binh", "don_gia_thap", 0.4),
    ("don_gia_thap", "don_gia_cao", 0.0),
    # --- Diện tích nội nhóm ---
    ("dien_tich_nho", "dien_tich_vua", 0.5),
    ("dien_tich_vua", "dien_tich_lon", 0.5),
    ("dien_tich_lon", "dien_tich_rat_lon", 0.5),
    ("dien_tich_nho", "dien_tich_lon", 0.15),
    ("dien_tich_nho", "dien_tich_rat_lon", 0.0),
    ("dien_tich_vua", "dien_tich_rat_lon", 0.15),
    ("dien_tich_nho", "it_phong_ngu", 0.75),
    ("dien_tich_lon", "nhieu_phong_ngu", 0.75),
    ("dien_tich_rat_lon", "nhieu_phong_ngu", 0.8),
    ("dien_tich_vua", "it_phong_ngu", 0.4),
    ("dien_tich_vua", "nhieu_phong_ngu", 0.35),
    ("it_phong_ngu", "nhieu_phong_ngu", 0.0),
    # --- Giá ↔ Diện tích ---
    ("gia_thap", "dien_tich_nho", 0.55),
    ("gia_cao", "dien_tich_lon", 0.5),
    ("gia_rat_cao", "dien_tich_rat_lon", 0.5),
    ("gia_trung_binh", "dien_tich_vua", 0.45),
    ("don_gia_cao", "vi_tri_trung_tam", 0.6),
    # --- Tiện ích ngữ nghĩa ---
    ("gan_truong_hoc", "tien_ich_giao_duc", 0.85),
    ("gan_benh_vien", "tien_ich_y_te", 0.85),
    ("gan_sieu_thi", "tien_ich_thuong_mai", 0.85),
    ("gan_cong_vien", "tien_ich_giai_tri", 0.7),
    ("co_ho_boi", "tien_ich_giai_tri", 0.75),
    ("co_gym", "tien_ich_giai_tri", 0.7),
    ("co_ho_boi", "co_gym", 0.65),
    ("view_dep", "gan_cong_vien", 0.5),
    ("an_ninh_tot", "noi_that_day_du", 0.4),
    ("co_ho_boi", "view_dep", 0.45),
    ("noi_that_day_du", "noi_that_co_ban", 0.0),
    # --- Tiện ích ↔ Tiện ích ---
    ("tien_ich_giao_duc", "tien_ich_y_te", 0.35),
    ("tien_ich_giao_duc", "tien_ich_thuong_mai", 0.4),
    ("tien_ich_y_te", "tien_ich_thuong_mai", 0.35),
    ("tien_ich_thuong_mai", "tien_ich_giai_tri", 0.45),
    ("tien_ich_giao_thong", "tien_ich_thuong_mai", 0.4),
    ("tien_ich_giao_thong", "tien_ich_giao_duc", 0.3),
    # --- Tiện ích ↔ Vị trí ---
    ("vi_tri_trung_tam", "tien_ich_thuong_mai", 0.65),
    ("vi_tri_trung_tam", "tien_ich_giai_tri", 0.55),
    ("vi_tri_trung_tam", "tien_ich_giao_thong", 0.6),
    ("vi_tri_trung_tam", "tien_ich_y_te", 0.5),
    ("vi_tri_trung_tam", "tien_ich_giao_duc", 0.45),
    ("vi_tri_trung_tam", "an_ninh_tot", 0.4),
    ("vi_tri_can_trung_tam", "tien_ich_giao_thong", 0.5),
    ("vi_tri_can_trung_tam", "tien_ich_thuong_mai", 0.45),
    ("vi_tri_ngoai_thanh", "dien_tich_lon", 0.5),
    ("vi_tri_ngoai_thanh", "gia_thap", 0.55),
    # --- Vị trí nội nhóm ---
    ("vi_tri_trung_tam", "vi_tri_can_trung_tam", 0.45),
    ("vi_tri_can_trung_tam", "vi_tri_ngoai_thanh", 0.4),
    ("vi_tri_trung_tam", "vi_tri_ngoai_thanh", 0.1),
    # --- Giá ↔ Vị trí ---
    ("vi_tri_trung_tam", "gia_cao", 0.55),
    ("vi_tri_trung_tam", "gia_rat_cao", 0.6),
    ("vi_tri_trung_tam", "gia_thap", 0.05),
    ("vi_tri_ngoai_thanh", "gia_rat_cao", 0.05),
    # --- Hướng ---
    ("huong_tot", "huong_xau", 0.0),
    ("huong_tot", "view_dep", 0.35),
    ("huong_tot", "gia_cao", 0.25),
    # --- Pháp lý nội nhóm ---
    ("so_hong_rieng", "so_chung", 0.3),
    ("so_hong_rieng", "hop_dong_mua_ban", 0.15),
    ("so_hong_rieng", "dang_cho_so", 0.2),
    ("so_chung", "hop_dong_mua_ban", 0.35),
    ("so_chung", "dang_cho_so", 0.4),
    ("hop_dong_mua_ban", "dang_cho_so", 0.6),
    # --- Pháp lý ↔ Giá ---
    ("so_hong_rieng", "gia_cao", 0.35),
    ("hop_dong_mua_ban", "gia_thap", 0.4),
    ("dang_cho_so", "gia_thap", 0.35),
    # --- Giá ↔ Tiện ích ---
    ("gia_rat_cao", "noi_that_day_du", 0.5),
    ("gia_rat_cao", "co_ho_boi", 0.45),
    ("gia_rat_cao", "co_gym", 0.4),
    ("gia_rat_cao", "view_dep", 0.5),
    ("gia_thap", "noi_that_co_ban", 0.45),
]


def build_criteria_similarity_matrix():
    """Xây dựng ma trận tương đồng 36x36 giữa các tiêu chí."""
    keys = list(CRITERIA.keys())
    n = len(keys)
    matrix = np.eye(n)
    idx = {k: i for i, k in enumerate(keys)}

    for c1, c2, score in SIMILARITY_PAIRS:
        i, j = idx[c1], idx[c2]
        matrix[i][j] = score
        matrix[j][i] = score

    return pd.DataFrame(matrix, index=keys, columns=keys)


# ===========================================================================
# PHẦN 2: MA TRẬN TƯƠNG ĐỒNG BĐS (Property Similarity Matrix)
# ===========================================================================
#
# Dùng trực tiếp các trường gốc, KHÔNG tạo field mới.
# Mỗi cặp BĐS được so sánh theo 5 nhóm đặc trưng gốc:
#   1. "Khoảng giá" + "Đơn giá"          → so sánh số
#   2. "Diện tích" + "Số phòng ngủ/tắm"  → so sánh số
#   3. "Quận huyện" + tọa độ GPS          → so sánh vị trí
#   4. "Pháp lý" + "Nội thất" + "Hướng"  → so sánh chuỗi (exact match)
#   5. "Mô tả" (tiện ích)                 → đếm từ khóa chung

# --- Trọng số từng trường gốc ---
WEIGHTS = {
    "Khoảng giá": 0.15,
    "Đơn giá": 0.10,
    "Diện tích": 0.12,
    "Số phòng ngủ": 0.08,
    "Số phòng tắm, vệ sinh": 0.03,
    "Quận huyện": 0.12,
    "Tọa độ": 0.08,
    "Pháp lý": 0.10,
    "Nội thất": 0.05,
    "Hướng nhà": 0.05,
    "Hướng ban công": 0.02,
    "Mô tả (tiện ích)": 0.10,
}
# Tổng = 1.00

# Từ khóa dùng để đếm tiện ích trong "Mô tả" (trường gốc, không tạo field mới)
AMENITY_KEYWORDS = [
    "trường học", "trường mầm non", "đại học", "bệnh viện", "phòng khám",
    "siêu thị", "chợ", "trung tâm thương mại", "vincom", "aeon", "lotte",
    "coopmart", "big c", "bách hóa", "công viên", "hồ bơi", "gym", "yoga",
    "spa", "sauna", "tennis", "golf", "khu vui chơi", "BBQ",
    "metro", "sân bay", "bến xe", "an ninh", "bảo vệ", "camera",
]


def parse_number(text, remove_suffix=""):
    """Parse chuỗi số tiếng Việt → float. Trả về None nếu lỗi."""
    if not text:
        return None
    try:
        cleaned = text.replace(remove_suffix, "").replace(",", ".").strip()
        return float(cleaned)
    except (ValueError, AttributeError):
        return None


def parse_price(s):
    """'3,95 tỷ' → 3.95 | '800 triệu' → 0.8"""
    if not s:
        return None
    s = s.strip().lower()
    if "tỷ" in s:
        return parse_number(s, "tỷ")
    if "triệu" in s:
        v = parse_number(s, "triệu")
        return v / 1000 if v else None
    return None


def haversine_km(lat1, lon1, lat2, lon2):
    """Khoảng cách Haversine giữa 2 tọa độ (km)."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_lat_lon(item):
    """Trích tọa độ từ trường gốc 'Latitude and Longitude'."""
    s = item.get("Latitude and Longitude", "")
    if not s or "q=" not in s:
        return None, None
    try:
        parts = s.split("q=")[1].split(",")
        return float(parts[0]), float(parts[1])
    except (IndexError, ValueError):
        return None, None


def count_amenities(text):
    """Đếm số từ khóa tiện ích xuất hiện trong chuỗi mô tả."""
    if not text:
        return 0
    text_lower = text.lower()
    return sum(1 for kw in AMENITY_KEYWORDS if kw.lower() in text_lower)


def compute_property_similarity(data):
    """
    Tính ma trận tương đồng NxN giữa các BĐS.

    So sánh trực tiếp trên các trường gốc:
      - Trường số (giá, diện tích, phòng ngủ...): sim = 1 - |a-b| / max_range
      - Trường chuỗi (pháp lý, nội thất, hướng, quận): sim = 1.0 nếu giống, 0.0 nếu khác
      - Tọa độ GPS: sim dựa trên khoảng cách Haversine
      - Mô tả: sim dựa trên tỷ lệ từ khóa tiện ích chung (Jaccard-like)
    """
    n = len(data)

    # --- Bước 1: Parse trường số một lần (dùng trực tiếp trường gốc) ---
    prices = [parse_price(item.get("Khoảng giá")) for item in data]
    unit_prices = [parse_number(item.get("Đơn giá"), "tr/m²") for item in data]
    areas = [parse_number(item.get("Diện tích"), "m²") for item in data]

    def safe_int(s):
        try:
            v = int(s)
            return v if v <= 10 else None
        except (ValueError, TypeError):
            return None

    bedrooms = [safe_int(item.get("Số phòng ngủ")) for item in data]
    bathrooms = [safe_int(item.get("Số phòng tắm, vệ sinh")) for item in data]

    # Tọa độ (đọc từ trường gốc "Latitude and Longitude")
    coords = [get_lat_lon(item) for item in data]

    # Đếm tiện ích từ "Mô tả" + "Tiêu đề" (trường gốc)
    amenity_counts = [
        count_amenities((item.get("Mô tả") or "") + " " + (item.get("Tiêu đề") or ""))
        for item in data
    ]

    # Tập từ khóa tiện ích cho mỗi BĐS (dùng cho Jaccard)
    amenity_sets = []
    for item in data:
        text = ((item.get("Mô tả") or "") + " " + (item.get("Tiêu đề") or "")).lower()
        found = frozenset(kw for kw in AMENITY_KEYWORDS if kw.lower() in text)
        amenity_sets.append(found)

    # --- Bước 2: Xác định max range cho chuẩn hóa trường số ---
    def max_range(values):
        valid = [v for v in values if v is not None]
        return (max(valid) - min(valid)) if len(valid) >= 2 else 1.0

    price_range = max_range(prices)
    uprice_range = max_range(unit_prices)
    area_range = max_range(areas)
    bed_range = max_range(bedrooms)
    bath_range = max_range(bathrooms)
    amenity_range = max_range(amenity_counts)

    # --- Bước 3: Hàm sim cho từng trường gốc ---

    def num_sim(a, b, rng):
        """Similarity trường số: 1 - |a-b|/range. None → 0.5 (trung lập)."""
        if a is None or b is None:
            return 0.5
        return 1.0 - abs(a - b) / rng if rng > 0 else 1.0

    def str_sim(a, b):
        """Similarity trường chuỗi: giống = 1.0, khác = 0.0, None = 0.5."""
        if a is None or b is None:
            return 0.5
        return 1.0 if a.strip().lower() == b.strip().lower() else 0.0

    def geo_sim(i, j):
        """Similarity tọa độ: 0km → 1.0, >=30km → 0.0."""
        lat1, lon1 = coords[i]
        lat2, lon2 = coords[j]
        if lat1 is None or lat2 is None:
            return 0.5
        dist = haversine_km(lat1, lon1, lat2, lon2)
        return max(0.0, 1.0 - dist / 30.0)

    def amenity_sim(i, j):
        """Similarity tiện ích (Jaccard): |A∩B| / |A∪B|."""
        a, b = amenity_sets[i], amenity_sets[j]
        if not a and not b:
            return 1.0
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

    # --- Bước 4: Tính ma trận ---
    print(f"Đang tính ma trận tương đồng cho {n} BĐS...")
    sim_matrix = np.zeros((n, n))

    for i in range(n):
        if i % 500 == 0:
            print(f"  Processing {i}/{n}...")
        sim_matrix[i][i] = 1.0
        for j in range(i + 1, n):
            s = 0.0

            # Trường "Khoảng giá"
            s += WEIGHTS["Khoảng giá"] * num_sim(prices[i], prices[j], price_range)
            # Trường "Đơn giá"
            s += WEIGHTS["Đơn giá"] * num_sim(unit_prices[i], unit_prices[j], uprice_range)
            # Trường "Diện tích"
            s += WEIGHTS["Diện tích"] * num_sim(areas[i], areas[j], area_range)
            # Trường "Số phòng ngủ"
            s += WEIGHTS["Số phòng ngủ"] * num_sim(bedrooms[i], bedrooms[j], bed_range)
            # Trường "Số phòng tắm, vệ sinh"
            s += WEIGHTS["Số phòng tắm, vệ sinh"] * num_sim(bathrooms[i], bathrooms[j], bath_range)
            # Trường "Quận huyện" (exact match trên trường gốc)
            s += WEIGHTS["Quận huyện"] * str_sim(
                data[i].get("Quận huyện"), data[j].get("Quận huyện"))
            # Trường "Latitude and Longitude" → khoảng cách GPS
            s += WEIGHTS["Tọa độ"] * geo_sim(i, j)
            # Trường "Pháp lý" (exact match trên trường gốc)
            s += WEIGHTS["Pháp lý"] * str_sim(
                data[i].get("Pháp lý"), data[j].get("Pháp lý"))
            # Trường "Nội thất" (exact match trên trường gốc)
            s += WEIGHTS["Nội thất"] * str_sim(
                data[i].get("Nội thất"), data[j].get("Nội thất"))
            # Trường "Hướng nhà" (exact match trên trường gốc)
            s += WEIGHTS["Hướng nhà"] * str_sim(
                data[i].get("Hướng nhà"), data[j].get("Hướng nhà"))
            # Trường "Hướng ban công" (exact match trên trường gốc)
            s += WEIGHTS["Hướng ban công"] * str_sim(
                data[i].get("Hướng ban công"), data[j].get("Hướng ban công"))
            # Trường "Mô tả" → Jaccard similarity trên từ khóa tiện ích
            s += WEIGHTS["Mô tả (tiện ích)"] * amenity_sim(i, j)

            s = min(s, 1.0)
            sim_matrix[i][j] = s
            sim_matrix[j][i] = s

    return sim_matrix


# ===========================================================================
# PHẦN 3: CHẠY VÀ XUẤT KẾT QUẢ
# ===========================================================================

def main():
    print("=" * 70)
    print("  MA TRẬN TƯƠNG ĐỒNG v2 — DỮ LIỆU GỐC, KHÔNG TẠO FIELD MỚI")
    print("=" * 70)

    # --- 1. Ma trận tiêu chí ---
    print("\n[1/3] Ma trận Tương đồng Tiêu chí (36x36)...")
    criteria_df = build_criteria_similarity_matrix()
    criteria_df.to_csv("criteria_similarity_matrix_v2.csv", encoding="utf-8-sig")
    print(f"  → Đã lưu: criteria_similarity_matrix_v2.csv")

    print("\n  Mẫu 5x5:")
    print(criteria_df.iloc[:5, :5].to_string())

    # --- 2. Đọc dữ liệu gốc ---
    print("\n[2/3] Đọc Final_Data.json...")
    with open("Final_Data.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"  → {len(data)} BĐS")

    # --- 3. Tính ma trận BĐS ---
    print("\n[3/3] Tính Ma trận Tương đồng BĐS...")
    prop_sim = compute_property_similarity(data)

    np.save("property_similarity_matrix_v2.npy", prop_sim)
    print(f"  → Đã lưu: property_similarity_matrix_v2.npy")

    # Index mapping
    id_list = [item.get("Mã tin") for item in data]
    with open("property_id_index_v2.json", "w", encoding="utf-8") as f:
        json.dump({
            "id_to_index": {mid: i for i, mid in enumerate(id_list)},
            "index_to_id": id_list
        }, f, ensure_ascii=False, indent=2)
    print(f"  → Đã lưu: property_id_index_v2.json")

    # --- Thống kê ---
    upper = prop_sim[np.triu_indices(len(data), k=1)]
    print(f"\n  Thống kê:")
    print(f"    Similarity TB:     {upper.mean():.4f}")
    print(f"    Similarity min:    {upper.min():.4f}")
    print(f"    Similarity max:    {upper.max():.4f}")
    print(f"    Similarity median: {np.median(upper):.4f}")

    print(f"\n  Top 10 cặp BĐS tương đồng nhất:")
    flat_idx = np.argsort(upper)[::-1][:10]
    tri_i, tri_j = np.triu_indices(len(data), k=1)
    for rank, idx in enumerate(flat_idx):
        i, j = tri_i[idx], tri_j[idx]
        print(f"    #{rank+1}: {id_list[i]} ↔ {id_list[j]} | sim={prop_sim[i][j]:.4f}")

    # --- Trọng số đã dùng ---
    print(f"\n  Trọng số theo trường gốc:")
    for field, w in WEIGHTS.items():
        print(f"    {field:30s} {w:.0%}")

    print("\n" + "=" * 70)
    print("  HOÀN TẤT!")
    print("=" * 70)


if __name__ == "__main__":
    main()
