# Kịch bản User & Interaction — dữ liệu nền cho Nhóm B/C/E/F

`EVAL_SCENARIO.md` mô tả ground truth (`recommended_items`) cho Nhóm A,
nhưng chưa nói **user mô phỏng được tạo thế nào** và **hành vi
(`interactions`) được mô phỏng thế nào** — 2 nguồn dữ liệu mà Nhóm B/C/E/F
(rating/classification, novelty, serendipity) cần. Tài liệu này bổ sung
phần đó.

## 1. User mô phỏng (`users_v3.json`)

Sinh bởi `generate_users_v2()` (`gen_user_data/generation/gen_v2.py`, dùng
lại nguyên cho v3), tách 2 loại thông tin theo đúng schema
`schemas_v2.py::UserProfile`:

- **`explicit_preferences`** (user chủ động cung cấp — filter/chat):
  `preferred_districts`, `property_type`, `budget_range`, `min_bedrooms`,
  `liked_amenities`. Lấy mẫu có trọng số theo tần suất THẬT trong catalog
  (`derive_pools()`, `Data/Final_Data.csv`) — vd phường/xã nào có nhiều
  listing hơn thì có xác suất được chọn làm preference cao hơn, phản ánh
  đúng phân bổ cung thật thay vì đều tay.
- **`inferred_attributes`** (demographic — tuổi/hôn nhân/con cái/thu nhập):
  mặc định `value=None, confidence=0` ("chưa biết"), chỉ điền theo xác suất
  `_P_INFERRED` (vd 45% user có `age_group` được "suy luận" từ 1 câu
  evidence mẫu). Mô phỏng đúng thực tế: **không phải trường nào hệ thống
  cũng biết chắc về user**, tránh ground truth giả định biết hết mọi thứ.

**Độc lập với `backend/`**: toàn bộ bước này chỉ đọc `Data/Final_Data.csv`
+ `config/distribution_config.py` (trọng số phân khúc/độ tuổi/hôn nhân...)
— không đọc gì từ `backend/src/search/`. Đạt nguyên tắc (a) ở
`EVAL_SCENARIO.md` mục 1.

## 2. Mô phỏng hành vi (`interactions_v3_claude.json`)

Với mỗi event, user chỉ "nhìn thấy" `LLM_OUTPUT_K=3` căn (từ `llm_output`,
không phải cả 10 `recommended_items`) — đúng hành vi thật: user không đọc
hết trang kết quả, chỉ tương tác với vài căn được hiển thị nổi bật.
`gen_v2.py` (dùng lại cho v3):

1. **Chọn căn nào được tương tác**: xác suất tỷ lệ thuận với
   `content_score` (điểm ground truth độc lập, không phải điểm live) và tỷ
   lệ nghịch với thứ hạng hiển thị — `rank_w ∝ (score + ε) / (rank + 1)`.
   Tức là: căn khớp hồ sơ user hơn (theo `content_score` độc lập) VÀ được
   xếp cao hơn thì dễ được tương tác hơn — mô phỏng hành vi thật (người
   dùng ưu tiên đọc kết quả đầu, và có xu hướng chọn đúng cái hợp nhu cầu).
2. **Loại hành động** (`view`/`save`/`share`/`contact`): trọng số nền
   `ACTION_FREQ = {view: 0.70, save: 0.16, share: 0.05, contact: 0.09}`
   (`config/distribution_config.py:56`), điều chỉnh tăng dần theo độ khớp
   (`strong = min(1, score×1.5) × (1/rank)^0.3`) — căn càng khớp càng dễ có
   hành động "mạnh" (contact > share > save > view).
3. **Dwell time**: lognormal (median ~49s, `DWELL_LOGNORMAL_MEAN=3.9`), cắt
   ở `DWELL_MAX_SECONDS=1200`; dưới `BOUNCE_THRESHOLD_SECONDS=10` tính là
   bounce (hành động ảo, không tính là quan tâm thật).
4. **`implicit_score`**: `ACTION_WEIGHTS[action] × log-saturating(dwell)`
   — hành động mạnh + ở lại lâu → điểm cao, nhưng có bão hoà
   (`DWELL_SATURATION_SECONDS=180`) để không cho dwell cực đại lấn át loại
   hành động.

**Độc lập với `backend/`**: toàn bộ cơ chế trên chỉ dùng `content_score`
(độc lập, mục 1-2 của `EVAL_SCENARIO.md`) + RNG có seed — **không** đọc
`final_score`/`ranker.py` của backend. Đây là điểm quan trọng cần xác nhận
rõ: nếu hành vi mô phỏng lại tương quan với chính điểm số hệ thống được đo,
Nhóm B/C/E/F cũng sẽ dính circularity y hệt vấn đề đã phát hiện ở Nhóm A —
đã kiểm tra code, **không xảy ra**, vì `interactions` chỉ phụ thuộc
`content_score`/`llm_output`, tính trước và độc lập với việc replay qua
`/v1/search`.

## 3. Nhóm B/C/E/F cần gì từ 2 nguồn này

| Nhóm | Cần | Cách dùng |
|---|---|---|
| B/C (rating/classification) | `implicit_score`, `action_type` (có phải `save`/`share`/`contact` không) | So với `final_score` (live) cho **cùng** `(result_set_id, listing_id)` — chỉ tính được nếu listing đó nằm trong cả `interactions` lẫn live prediction |
| E (novelty) | Toàn bộ `interactions` (không phân biệt version) làm nền "phổ biến" | Item càng ít xuất hiện trong lịch sử tương tác càng "novel" |
| F (serendipity) | `interactions` theo từng `user_id` thật | So kết quả live với lịch sử tương tác CỦA CHÍNH user đó — cần đúng `user_id`, không trộn lẫn giữa các user |

## 4. Ràng buộc version — nhắc lại vì hay bị bỏ sót

`interactions` phải được sinh **cùng lúc, cùng phiên bản** với
`recommended_items`/`llm_output` nó tham chiếu — vì bước 1 ở mục 2 cần
`llm_output` (căn nào được hiển thị) và `content_score` (độ khớp) của
CHÍNH phiên bản ground truth đó. Dùng `interactions` của phiên bản cũ với
`recommended_items` của phiên bản mới (như đã từng xảy ra khi đối chiếu
báo cáo v4 với `interactions_v3_claude.json`) khiến Nhóm B/C/E/F đọc nhãn
hành vi không khớp gì với tập kết quả đang được đo — số liệu (AUC≈0.49,
gần ngẫu nhiên) không phản ánh đúng chất lượng gì cả, chỉ phản ánh sự lệch
version.
