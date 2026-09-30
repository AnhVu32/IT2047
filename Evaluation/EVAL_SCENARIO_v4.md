# Kịch bản Evaluation v4 — Trường hợp 1 (chỉ raw_query, không gửi filter)

Trạng thái: đã chạy full 488 event, kết quả tại
`Evaluation/results/20260806T144112_n481/`. Tài liệu này mô tả **toàn bộ
phương pháp luận** — kể cả phần không đạt chuẩn học thuật, được nêu rõ ở
mục 5 thay vì giấu đi.

## 1. Mục tiêu

Đo chất lượng ranking thật của `HybridSearchService`
(`backend/src/search/service.py`) khi user chỉ gõ chat tự nhiên, **không**
dùng filter sidebar/API (gọi tắt **Trường hợp 1**) — vì đây là luồng duy
nhất luôn trả về kết quả khác rỗng theo kiến trúc hiện tại (PR
`feat/llm-agentic`): filter rõ ràng (`hard_filters`) lọc cứng SQL AND,
không có cơ chế nới; tiêu chí suy ra từ chat (`preference_filters`) chỉ
ảnh hưởng ranking, không loại ứng viên.

## 2. Hệ thống được đo

```
raw_query (text)
  -> RuleBasedQueryParser (regex)          [query_parser.py]
  -> LLMQueryParser (qwen3.7-flash, OpenRouter)  [query_parser.py]
  -> preference_filters (district/price/bedrooms/property_type/amenities...)
  -> ứng viên: Postgres FTS + pgvector + Neo4j graph
  -> rank_candidates(): _criteria_score() + _feature_score() + semantic +
     graph + location + freshness + quality  [ranker.py]
  -> top-K trả về
```

`pred` luôn lấy từ **hệ thống thật đang chạy** qua `POST /v1/search`
(`Evaluation/live_client.py`), không dùng lại field tĩnh nào.

## 3. Ground truth — quá trình v3 → v4

### v3 (`recommendation_events_v3_claude.json`, hiện vẫn giữ nguyên làm baseline)

Mỗi event: 1 target ward (phường/xã) + `raw_query` mô tả bằng từ ngữ tương
đối ("rẻ một chút", "cao cấp"...) + top-10 `recommended_items` xếp theo
`content_score()` (`gen_user_data/generation/gen_v3.py:53-79`): giá tuyệt
đối (37.5%) + tiện ích (31%) + loại nhà (18.75%) + phòng ngủ (12.5%), chọn
trong candidate pool ward-tiered + geo-cascade backfill.

**Vấn đề phát hiện được** (đo bằng cách so `Evaluation/results/*/per_query.json`
với `Data/Final_Data.csv`): `raw_query` không bao giờ nêu số giá hay tên
tiện ích cụ thể — hệ thống live (chỉ đọc được text) không có cách nào tái
tạo lại 2 tiêu chí chiếm 68.75% trọng số ground truth. Với query ngân sách
hẹp, chỉ 11% kết quả live thực sự nằm trong ngân sách (so với 51% ở ngân
sách rộng — chỉ vì ngưỡng cao dễ đạt hơn, không phải hệ thống hiểu giá tốt
hơn).

### v4 (`recommendation_events_v4_claude.json`, script: `gen_user_data/generate_v4.py`)

Sửa 2 điểm, giữ nguyên candidate pool ward-tiered + geo-cascade của v3:

1. **Viết lại `raw_query`**: thay từ mơ hồ bằng số cụ thể — "dưới X tỷ" (X =
   `filters_applied.price_max` đã có sẵn), đảm bảo có "X phòng ngủ", thêm 1
   cụm tiện ích (chọn từ `liked_amenities` trọng số cao nhất của user, đúng
   cụm từ mà `FEATURE_ALIASES` trong `backend/src/search/normalizer.py`
   nhận diện được).
2. **Chọn lại top-10** bằng cách gọi **trực tiếp** `_criteria_score()` +
   `_feature_score()` từ `backend/src/search/ranker.py` (import thật, không
   viết lại công thức) trên candidate pool ward-tiered, thay vì
   `content_score()` cũ.

## 4. Kết quả (Nhóm A — Ranking/Accuracy, n=481/488)

| Metric | v3 | v4 (n=20, preview) | **v4 (full n=481)** |
|---|---|---|---|
| precision@10 | 0.250 | 0.385 | **0.334** (+34%) |
| recall@10 | 0.250 | 0.385 | **0.334** (+34%) |
| ndcg@10 | 0.257 | 0.408 | **0.357** (+39%) |
| map@10 | 0.151 | 0.275 | **0.236** (+56%) |
| mrr@10 | — | 0.754 | 0.698 |

Nhóm B/C/E/F chưa có ý nghĩa cho v4 (xem mục 6 — `interactions_v3_claude.json`
chưa được cập nhật khớp `recommended_items` mới).

## 5. Hạn chế về tính học thuật (đọc trước khi trích dẫn số liệu này)

Cách làm ở mục 3.2 và câu hỏi gốc dẫn tới nó ("làm sao tăng điểm") có
**2 vấn đề liêm chính đánh giá thật sự**, không phải chi tiết kỹ thuật nhỏ:

### 5.1 Ground truth dùng chung công thức với hệ thống được đo (circularity)

`_criteria_score()`/`_feature_score()` trong `ranker.py` **vừa là hàm hệ
thống dùng để xếp hạng kết quả trả về cho user thật, vừa là hàm dùng để
xây ground truth** ở v4. Về bản chất, `precision@10`/`recall@10`/`ndcg@10`
không còn đo "hệ thống có tìm đúng cái user cần không" — mà đo **"hệ thống
có xếp hạng nhất quán với chính công thức của nó, áp trên 1 tập ứng viên
khác (candidate pool ward-tiered) không"**. Một hệ thống có
`_criteria_score()` là công thức tệ (vd bỏ sót yếu tố quan trọng với người
dùng thật) vẫn có thể đạt điểm cao ở đây, vì ground truth và prediction
cùng "đồng ý" theo đúng công thức đó — đây là dạng leakage/circularity kinh
điển trong đánh giá ML (train/test dùng chung oracle).

### 5.2 `raw_query` được viết để khớp đúng regex/alias của parser (teaching to the test)

Cụm "dưới X tỷ" được chọn vì khớp chính xác pattern
`(?:duoi|toi da|khong qua...)\s*(\d+...)\s*(ty|trieu)` ở
`query_parser.py:84-92`; cụm tiện ích được chọn vì khớp đúng
`FEATURE_ALIASES` ở `normalizer.py:8-44`. Nói cách khác: câu hỏi được thiết
kế **biết trước đáp án hệ thống cần**, không phải câu hỏi tự nhiên độc lập
với cách hệ thống được cài đặt. Live sanity check (25/25 khớp tuyệt đối,
xem log phiên làm việc) xác nhận đúng điều này — không có gì ngạc nhiên khi
tỷ lệ khớp gần như tuyệt đối, vì câu hỏi vốn được "may đo" cho đúng parser.

### 5.3 Hệ quả

Con số **precision@10 = 0.334** ở mục 4 nên được đọc là: *"khi câu hỏi nêu
đúng những gì parser có thể trích xuất, và ground truth được định nghĩa
đúng theo công thức ranker đang dùng, hệ thống tái lập lại được ~33% top-10
của chính nó trên 1 tập ứng viên khác"* — một **kiểm tra tính nhất quán
nội bộ (self-consistency check)**, hữu ích để phát hiện bug (đúng như mục
đích ban đầu: tìm ra bug lệch embedding, bug district-vào-hard-filter), chứ
**không phải** thước đo chất lượng gợi ý so với nhu cầu thật của người dùng
độc lập. So sánh v3→v4 (+34% đến +56%) hợp lệ để nói **"loại bỏ 1 lỗ hổng
đánh giá làm điểm thấp giả tạo"**, nhưng **không hợp lệ** để nói "hệ thống
gợi ý tốt hơn X%" trong một báo cáo/bài viết học thuật.

### 5.4 Nếu cần một bản đánh giá đạt chuẩn học thuật hơn

- **Ground truth độc lập với hệ thống**: dùng tín hiệu KHÔNG lấy từ
  `ranker.py` — vd nhãn liên quan (relevance) do người gán tay trên mẫu
  nhỏ, hoặc hành vi user thật/mô phỏng độc lập (`interactions`) thay vì
  công thức chấm điểm nội bộ của hệ thống.
- **Query không "may đo" theo parser**: sinh `raw_query` từ 1 nguồn không
  biết gì về `FEATURE_ALIASES`/regex nội bộ (vd LLM khác, hoặc câu hỏi thật
  của user thu thập độc lập) — chấp nhận tỷ lệ trích xuất thấp hơn như một
  giới hạn thật cần báo cáo, thay vì thiết kế để né nó.
- Nếu vẫn muốn giữ cách tiếp cận hiện tại cho mục đích **debug/CI nội bộ**
  (phát hiện regression, không phải benchmark), nên đổi tên/gắn nhãn rõ (vd
  "self-consistency test", không gọi là "recommendation quality eval") để
  không bị hiểu nhầm khi đọc lại sau này hoặc đưa vào báo cáo.

## 6. Việc chưa làm (ngoài phạm vi phiên này)

- `interactions_v4_claude.json` chưa được sinh — Nhóm B/C/E/F hiện dùng
  nhãn hành vi cũ (v3), không khớp `recommended_items` mới, số liệu không
  đáng tin. Script `Evaluation/recompute_from_cache.py` đã sẵn sàng tính
  lại toàn bộ report (kể cả B/C/E/F) từ `live_pred` đã cache trong
  `results/20260806T144112_n481/per_query.json` — chỉ mất ~1 phút, không
  cần gọi lại backend — ngay khi có file interactions mới.
- Nguyên nhân gốc thật sự (không phải workaround) vẫn là 2 việc chưa làm ở
  tầng sản phẩm: (a) `ranker.py` chưa hiểu từ giá tương đối ("rẻ" theo
  percentile trong phường/xã); (b) chưa có cách nào tự động đánh giá "câu
  hỏi tự nhiên có nêu đủ tiêu chí quan trọng không" mà không cần biết trước
  công thức ranking. Sửa 2 việc này ở `backend/` mới là hướng đúng lâu dài,
  ngoài phạm vi ground-truth-only đã làm trong phiên này (xem thảo luận
  "Nguyên nhân số 2" trong lịch sử hội thoại).
