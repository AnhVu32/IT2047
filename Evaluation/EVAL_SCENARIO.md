# Kịch bản tạo Ground Truth liêm chính + Kịch bản Evaluation

## 1. Nguyên tắc liêm chính (đã duyệt)

**(a) Ground truth độc lập** — hàm relevance sống trong `gen_user_data/`,
**không import `backend/`**. Đã có sẵn: `content_score()`
(`gen_user_data/generation/gen_v3.py:53-79`) — giá + tiện ích + loại nhà +
phòng ngủ, so với hồ sơ user (`explicit_preferences`). Chỉ cần **không**
thay bằng hàm thật của `ranker.py` như v4 đã làm.

**(b) Ground truth phải có độ ngẫu nhiên** — không phải mọi query đều nêu
đủ mọi tiêu chí. Ngẫu nhiên hoá 2 chiều:
- *Có nêu hay không*: xác suất p (không phải 100%) quyết định câu hỏi có
  nêu giá cụ thể/tiện ích hay không.
- *Nêu theo dạng nào*: số chính xác ("dưới 2.4 tỷ") / khoảng ("tầm 2-3 tỷ")

  không cố định 1 dạng. Số tiện ích nêu: 0, 1, hoặc nhiều — không luôn = 1.

Bonus tự động thoả nguyên tắc "không may đo parser": quy trình sinh câu hỏi
chỉ cần biết hồ sơ user, **không đọc `query_parser.py`/`normalizer.py`** —
nếu đổi cách backend parse text mà câu hỏi không cần sửa gì, tức là độc
lập thật.

## 2. Quy trình tạo Ground Truth (sự kiện) — cụ thể hoá nguyên tắc ở mục 1

### 2.1 Chọn candidate — ward-tiered + geo-cascade (đã triển khai, giữ nguyên)

Đây là phần đã làm đúng ở `gen_user_data/generation/gen_v3.py`, kế thừa từ
`Plan/Plan A - Ground Truth.md` — **không cần sửa gì thêm**, chỉ nhắc lại
để kịch bản đầy đủ, không thiếu bước nào:

1. Mỗi event gắn với **1 target ward** (phường/xã), chọn từ
   `user.explicit_preferences.preferred_districts`.
2. **Tầng 1**: toàn bộ listing trong catalog có `district == target_ward`,
   xếp theo `content_score(user, listing)` giảm dần.
3. Nếu tầng 1 chưa đủ `TOP_K=10` (ward < `MIN_WARD_LISTINGS=10`) — **Tầng 2**
   bù theo khoảng cách địa lý thực, hẹp → rộng: `geo_cluster_150m` (~150m)
   → `geohash_7` (~150m, mịn) → `geohash_6` (~1.2km, rộng nhất) — dữ liệu
   lấy từ `Data/real_estate_graph_ready_v2_address_mapping/Final_Data_graph_ready_filtered.csv`,
   đã join sẵn vào `Listing.geohash_6/7/geo_cluster_150m`
   (`gen_user_data/schemas.py`, `catalog.py`).
4. **Tầng 3** (hiếm khi cần): nếu tầng 1+2 vẫn thiếu, bù bằng listing tốt
   nhất theo `content_score` ở bất kỳ đâu trong catalog, để luôn đủ đúng
   `TOP_K`.
5. Nối tầng theo đúng thứ tự trên, **tầng trước luôn đứng trên tầng sau**
   bất kể điểm số — đây là cách thể hiện "trọng số ward gần như tuyệt đối"
   mà không cần một con số trọng số đơn lẻ.

Kết quả đo được: 97.9% ground truth nằm đúng trong ward (so với ~10% ở bản
gốc trước khi sửa) — xác nhận cơ chế tầng hoạt động đúng.

### 2.2 Chấm điểm — `content_score()` độc lập (đã có, giữ nguyên)

Trong mỗi tầng, xếp hạng bằng `content_score()`
(`gen_v3.py:53-79`): giá (3.0/8, so với `budget_range`) + tiện ích (2.5/8,
so với `liked_amenities`) + loại nhà (1.5/8) + phòng ngủ (1.0/8). Hàm này
**không đụng gì tới `backend/`** — đây chính là điều kiện (a) ở mục 1, đã
đúng ngay từ bản gốc, chỉ cần **không thay** bằng `ranker.py` như v4 từng
làm.

### 2.3 Sinh `raw_query` — ngẫu nhiên hoá mức độ cụ thể (CẦN THÊM MỚI)

Đây là phần **chưa có** trong cả `gen_v3.py` lẫn Plan A gốc — cả 2 đều mới
dừng ở mức "dùng từ ngữ tương đối" (`_PRICE_WORDS` trong
`gen_user_data/generation/llm_client.py`) nhưng chưa ngẫu nhiên hoá **việc
có nêu hay không**. Cần bổ sung vào bước sinh `raw_query`
(`QueryGenerator.template()`):

- Tung xác suất `p_price` (vd 40-50%, không phải 100%): nếu trúng, chèn 1
  trong 3 dạng — số chính xác / khoảng / chỉ từ tương đối (`_PRICE_WORDS`
  hiện có) — chọn ngẫu nhiên dạng nào; nếu trượt, không nhắc gì tới giá.
- Tung xác suất `p_amenity` tương tự cho tiện ích; nếu trúng, chọn ngẫu
  nhiên **số lượng** tiện ích nêu (0/1/nhiều, có trọng số ưu tiên tiện ích
  `liked_amenities` cao hơn) chứ không cố định luôn 1.
- Giữ nguyên phần district/loại nhà (luôn nêu rõ — hợp lý vì đây luôn là
  tiêu chí đầu tiên người mua nhà nói ra).

Không cần đọc `query_parser.py`/`normalizer.py` để thiết kế bước này (điều
kiện (b) — xem mục 1).

### 2.4 Quy mô lấy mẫu (đã có, giữ nguyên)

200 user mô phỏng, ~2-3 event/user (`N_EVENTS_MIN/MAX` trong `gen_v3.py`)
→ ~500 event, mỗi event top-10 `recommended_items`. Đã đúng, không cần đổi.

## 3. Kịch bản Evaluation qua các độ đo

Sau khi có ground truth liêm chính (mục 2), replay từng `raw_query` qua hệ
thống thật (`POST /v1/search`, Trường hợp 1 — không gửi `filters`), rồi
tính 25 metric (`reco_metrics_lib/recommenders/evaluation/python_evaluation.py`,
qua `Evaluation/run_eval.py`), chia 7 nhóm:

| Nhóm | Metric | Đo gì | Input |
|---|---|---|---|
| A — Ranking/Accuracy | precision/recall/ndcg/map/mrr/arhr@10 | Live prediction có trùng và xếp đúng thứ tự với top-10 ground truth không | `recommended_items` (mục 2) vs live prediction |
| B/C — Rating/Classification | rmse/mae/mse/auc/logloss | Điểm số live (`final_score`) có khớp hành vi thật (implicit_score, save/share/contact) không | `interactions` + live prediction |
| D — Diversity | diversity | Top-K trả về có đa dạng thuộc tính (không phải 10 căn giống hệt nhau) không | `item_feature_df` (tiện ích) |
| E — Novelty | novelty | Hệ thống có gợi ý cả listing ít phổ biến, không chỉ toàn hàng "hot" không | `interactions_train_df` |
| F — Serendipity | serendipity | Kết quả có bất ngờ-nhưng-hợp lý so với lịch sử của chính user đó không | `interactions` theo từng `user_id` thật |
| G — Coverage | catalog/distributional coverage | Hệ thống có phủ được nhiều phần catalog qua nhiều query, hay luôn quay về 1 nhóm nhỏ | Toàn bộ `reco_df` gộp qua các query |

**Lưu ý bắt buộc khi đọc kết quả**: Nhóm A chỉ phụ thuộc `recommended_items`
(mục 2) + live prediction — không phụ thuộc `interactions`. Nhóm B/C/E/F
phụ thuộc `interactions` — file này phải được sinh **khớp đúng** với
`recommended_items`/`llm_output` của cùng phiên bản ground truth (không
dùng lẫn `interactions` của phiên bản cũ với `recommended_items` của phiên
bản mới, như đã từng xảy ra khi đối chiếu v4 với `interactions_v3_claude.json`).

**Điểm số mong đợi**: sau khi có ground truth liêm chính (mục 2), Nhóm A sẽ
**thấp hơn** con số bị "may đo" ở v4 (precision@10≈0.334), gần với baseline
gốc hơn (~0.25-0.3, tuỳ tỷ lệ `p_price`/`p_amenity` chọn ở mục 2.3) — đây
là số **đúng**, phản ánh đúng khả năng hệ thống hiểu ngôn ngữ tự nhiên mơ
hồ, không phải số cần tối đa hoá. Muốn tăng hợp lệ: sửa `backend/` (dạy hệ
thống hiểu giá tương đối theo khu vực), không phải sửa ground truth.
