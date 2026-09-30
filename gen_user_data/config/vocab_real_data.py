"""Vocabulary (category) rút trích/thực nghiệm từ dữ liệu thật.

QUAN TRỌNG: có 2 file trong Data/, KHÔNG tương đương nhau:

  * Data/Final_Data.json — crawl thô, 3037 tin, "Pháp lý"/"Nội thất" là free
    text do người đăng tự gõ (nhiều biến thể/lỗi chính tả).
  * Data/Final_Data.csv  — bản đã qua ETL, cùng 3037 dòng, đổi tên field
    sang tiếng Anh (property_type, legal_status, furnishing, district...)
    và có sẵn 25 cột boolean (pool, gym, near_metro,...) — khớp CHÍNH XÁC
    schema Postgres `properties` mà backend dùng và
    Listing.features trong gen_user_data/schemas.py.

  => Data/Final_Data.csv là nguồn ĐÚNG/canonical để lấy vocab cho LLM
     generate, KHÔNG phải Final_Data.json. Toàn bộ hằng số dưới đây rút từ
     CSV, đã xác nhận bằng cách cộng count từng giá trị ứng viên khớp đúng
     tổng 3037 dòng (kỹ thuật giống lượt trước, xem comment từng field).

Nếu Data/ được crawl/ETL lại sau này, chạy lại
`gen_user_data/extract_vocab.py` (đã cập nhật để đọc CSV) để refresh file
này thay vì sửa tay.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Từ Final_Data.csv — ĐÃ XÁC NHẬN ĐÓNG/SẠCH
# ---------------------------------------------------------------------------

# "property_type" — ĐÓNG tuyệt đối, chỉ 2 giá trị (CSV gộp 5 loại chi tiết
# bên Final_Data.json thành 2 nhóm rộng cho backend). Xác nhận:
# "Căn hộ" 489 (= đúng số "Căn hộ chung cư" bên JSON) +
# "Nhà đất" 2548 (= 1877 Nhà riêng + 167 Nhà biệt thự/liền kề + 477 Nhà mặt
# phố + 27 Shophouse bên JSON) = 3037/3037 (100%).
PROPERTY_TYPES_REAL = [
    "Căn hộ",   # 489/3037
    "Nhà đất",  # 2548/3037
]

FURNISHING_REAL = [
    "Đầy đủ",
    "Cơ bản",
    "Không nội thất",
    "Cao cấp",
]

LEGAL_STATUS_REAL = [
    "Sổ hồng riêng", 
    "Đang chờ sổ",    
    "Sổ chung",       
    "Không rõ",
]


DIRECTIONS_REAL = [
    "Đông", "Tây", "Nam", "Bắc",
    "Đông - Bắc", "Đông - Nam", "Tây - Bắc", "Tây - Nam",
]

# 25 field boolean feature (pool, gym, park, bbq, kids_playground,
# sports_court, security_24h, reception, elevator, parking, near_metro,
# near_bus, near_highway, near_school, near_hospital, near_mall,
# near_market, near_park, river_view, park_view, city_view, balcony,
# garden, garage, terrace) — đây CHÍNH LÀ AMENITY_FIELDS/ACCESSIBILITY_
# FIELDS/VIEW_FIELDS đã có trong gen_user_data/schemas.py, không cần định
# nghĩa lại; chỉ cần biết giá trị luôn là 0/1 (không có null/thiếu).

# "district" trong CSV = "Quận huyện" trong JSON — danh sách MỞ, hàng chục
# phường/xã thật sau sáp nhập hành chính 2025 (vd "Phường Long Bình", "Xã
# Tân Nhựt" — thay cho tên quận cũ như "Quận 9"). KHÔNG hardcode ở đây vì
# số lượng lớn/dễ sai khi gõ tay và có thể đổi khi crawl thêm dữ liệu.
#
# schemas_v2.py đọc danh sách này TỰ ĐỘNG từ config/districts_real.json
# (sinh ra bởi extract_vocab.py, dùng pandas.read_csv nên tách cột chuẩn
# 100% — không dùng regex thủ công cho field lớn/mở như thế này). Chạy:
#
#     cd gen_user_data && python extract_vocab.py
#
# mỗi khi Data/Final_Data.csv được crawl/ETL lại, để preferred_districts
# trong schemas_v2.py luôn khớp danh sách phường/xã thật mới nhất.
