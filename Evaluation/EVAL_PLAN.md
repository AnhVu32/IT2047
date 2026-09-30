# Kế hoạch Evaluate hệ thống gợi ý BĐS

Trạng thái: **DRAFT v3 — sửa lại sai lệch quan trọng về ground truth, chờ
duyệt**. Đã vendor xong thư viện metric (`reco_metrics_lib/`), backend đang
build embedding (xem mục 6). Chưa code phần lõi.

## 0. Sửa sai (quan trọng — đảo ngược true/pred so với v2)

Bản v2 của kế hoạch này hiểu **sai**: coi `recommended_items` là "hệ thống
cần chấm điểm" và `llm_output` là ground truth. **Sai.** Đã kiểm tra lại tận
`gen_user_data/generation/gen_v2.py:250-291` (nơi sinh ra
`recommendation_events_v2*.json`) và xác nhận:

```python
# RETRIEVAL: pool -> rank theo relevance -> TOP_K=10 ứng viên (đưa CẢ 10 cho LLM)
rels = np.array([relevance_v2(user, l) for l in pool])   # relevance THẬT, đo khớp
order = np.argsort(-rels)[:TOP_K]                         # user-profile <-> listing
...
# recommended_items = CẢ 10 ứng viên retrieval (INPUT cho LLM)
...
# LLM đọc CẢ 10 -> CHỌN & xếp ra LLM_OUTPUT_K=3 (offline: lấy top-3 retrieval)
llm_out = _rerank_and_explain(qgen, llm, raw_query, item_info, model_name)
```

- **`recommended_items`** (10 mục/event): xếp hạng theo `relevance_v2()` —
  hàm đo độ khớp **thật** giữa hồ sơ user (`explicit_preferences`,
  `budget_range`, `preferred_districts`...) và thuộc tính listing
  (`matched_features`/`partial_match_features` cũng tính từ đây). Đây **là
  ground truth** — tín hiệu relevance tất định, có thể diễn giải, không phải
  "hệ thống cần chấm điểm".
- **`llm_output`** (3 mục/event): một **lớp phía sau** `recommended_items` —
  LLM (Gemini/Groq ở bản gốc, Claude ở bản `_claude`) chọn & viết giải thích
  cho 3/10 để **hiển thị cho user**, hoặc fallback lấy top-3 theo rank nếu
  không có LLM. Đây là lớp UX/giải thích, **không phải** ground truth ranking
  — dù đôi khi (khi bật LLM thật) nó có chọn lệch khỏi top-3-theo-rank, đó là
  hành vi của lớp hiển thị, không thay đổi việc `recommended_items` mới là
  tham chiếu relevance gốc.

**Hệ quả đúng:** `true` = `recommended_items` (đã có sẵn), `pred` = kết quả
từ **hệ thống thật** (`HybridSearchService`) khi replay lại `raw_query`. Ghi
chú ở mục 0 bản v2 cũ (bạn dự định "nâng cấp lên 10 ground truth") thực ra
**đã đúng ngay từ bây giờ** — `recommended_items` vốn đã có 10 mục/event,
không cần đợi nâng cấp gì thêm.

**Bất biến Recall@10≈1 ở bản v2 cũ — không còn đúng, bỏ.** Đó là hệ quả của
hiểu sai (llm_output ⊆ recommended_items theo *cách sinh dữ liệu*, không phải
theo ý nghĩa đánh giá). Với `pred` bây giờ đến từ hệ thống thật (tính độc
lập, không được xây từ `recommended_items`), **không có gì đảm bảo** hệ
thống sẽ trả về đúng các item trong ground truth — mọi độ đo (kể cả
Recall@10) đều có ý nghĩa thật, không bị "trần" nhân tạo.

## 1. Dữ liệu

| Nguồn | Số dòng | Vai trò |
|---|---|---|
| `gen_user_data/data/listings.json` | 3.030 listing thật | Catalog — `features` (25 amenity boolean) dùng làm item-feature vector |
| `gen_user_data/data/users_v2.json` | 200 user mô phỏng | `segment`, `primary_intent` — breakdown kết quả theo phân khúc |
| `gen_user_data/data/recommendation_events_v2_claude.json` | 1.055 event | **Ground truth**: `raw_query` + `filters_applied` + 10 `recommended_items` (rank/score theo `relevance_v2`, matched/partial_match_features). `llm_output` chỉ dùng tham khảo UX, không dùng làm nhãn đánh giá |
| `gen_user_data/data/interactions_v2_claude.json` | 2.122 interaction | Tín hiệu hành vi **thật, độc lập** — `implicit_score`, `action_type`, `is_bounce` — vẫn giữ nguyên vai trò như v2 (không bị ảnh hưởng bởi sửa sai ở mục 0) |
| `Data/real_estate_graph_ready/*` | 60.649 listing node, quan hệ graph phủ ~3.037 | Xác nhận subset 3.030 của `gen_user_data` khớp subset có đủ quan hệ graph |

## 2. Thư viện metric — đã vendor vào `Evaluation/reco_metrics_lib/` (không đổi so với v2)

Giữ nguyên như bản trước: 5 file cần thiết từ
`aryan-jadon/Evaluation-Metrics-for-Recommendation-Systems` (MIT, dựa trên
Microsoft `recommenders`), đã trim chỉ còn phần cần cho
`recommenders.evaluation.python_evaluation` (numpy/pandas/scikit-learn, xem
`reco_metrics_lib/NOTICE.md`). `Evaluation/requirements.txt` đã có sẵn.

API vẫn nhận 2 `pandas.DataFrame` khoá theo `col_user`/`col_item`; vẫn dùng
`result_set_id` làm `col_user` (per-query eval).

## 3. Toàn bộ metric — cập nhật true/pred đúng theo mục 0

**Nhóm A — Ranking/Accuracy** (`true` = `recommended_items`, xếp hạng theo
`rank`/`score` từ `relevance_v2`; `pred` = kết quả xếp hạng của
`HybridSearchService` khi replay `raw_query` + `filters_applied`), k=10 (đúng
bằng `len(recommended_items)`, đọc động chứ không hardcode):
`precision_at_k`, `recall_at_k`, `ndcg_at_k`, `map_at_k`, `mrr_at_k`,
`arhr_at_k`, `average_precision_at_k`, `average_recall_at_k`
→ câu hỏi cốt lõi: hệ thống thật hiện tại có tái tạo lại được xếp hạng
relevance-thật (theo hồ sơ user) hay không.

**Nhóm B — Rating/Calibration** (`true` = `implicit_score` thật từ
`interactions_v2_claude.json`; `pred` = **score của hệ thống thật** cho đúng
listing đó khi replay `raw_query` — tra trong kết quả trả về của
`HybridSearchService`, không dùng lại `score` tĩnh trong `recommended_items`
nữa):
`rmse`, `mae`, `mse`, `rsquared`, `exp_var`, `mape`
→ score hệ thống hiện tại có tương quan với mức độ engagement thật không.

**Nhóm C — Classification/Calibration** (`true` = nhãn nhị phân hành động
tích cực từ interactions thật; `pred` = score hệ thống thật, như Nhóm B):
`auc`, `logloss`

**Nhóm D — Diversity** (`reco_df` = kết quả hệ thống thật cho từng query,
`item_feature_df` = 25 cột `features` trong `listings.json`):
`user_diversity`, `diversity`

**Nhóm E — Novelty** (`train_df` = interactions thật, `reco_df` = kết quả hệ
thống thật):
`historical_item_novelty`, `novelty`

**Nhóm F — Serendipity** (`train_df` = interactions thật, `reco_df` = kết
quả hệ thống thật kèm cờ relevance tra từ `recommended_items` gốc,
`item_feature_df` như Nhóm D):
`user_item_serendipity`, `user_serendipity`, `serendipity`

**Nhóm G — Coverage** (`train_df` riêng = toàn bộ 3.030 listing làm universe,
`reco_df` = kết quả hệ thống thật gộp qua toàn bộ 1.055 query):
`catalog_coverage`, `distributional_coverage`

**Không đổi so với v2:** danh sách 25 hàm dùng hết, lý do chọn từng nhóm giữ
nguyên (xem bản v2 nếu cần chi tiết lý luận) — điểm đổi duy nhất và cốt lõi
là **`pred` giờ luôn phải lấy từ hệ thống thật**, không còn hàm nào dùng lại
field tĩnh trong `recommendation_events_v2_claude.json` làm `pred`.

## 4. Hệ quả: không còn "giai đoạn offline tính metric" — mọi metric cần backend thật

Bản v2 chia Giai đoạn 1 (offline, không cần backend) / Giai đoạn 2 (live).
Với true/pred đã sửa đúng, **Giai đoạn 1 kiểu cũ không còn ý nghĩa để tính
metric** (nó so `recommended_items` với `llm_output` — cả hai đều tĩnh, một
cái là con của cái kia, so sánh không nói lên gì về hệ thống thật). Đổi lại:

### Giai đoạn 0 — Offline, KHÔNG tính metric (chỉ chuẩn bị + validate dữ liệu)

Chạy được ngay, không cần backend: validate cấu trúc ground truth
(`recommended_items` đủ 10, rank liên tục, `llm_output` ⊆ `recommended_items`
— đã kiểm tra đúng ở `explore_data.py`), build `item_feature_df` từ
`listings.json`, build `train_df` từ interactions, thống kê mô tả (phân phối
`score`, `segment`, `primary_intent`...). Không in ra bất kỳ con số
precision/recall/ndcg nào — vì chưa có `pred`.

### Giai đoạn 1 — Live, CẦN backend chạy (tính toàn bộ 25 metric ở mục 3)

Với mỗi trong 1.055 event: gọi `raw_query`
(+ `filters_applied` nếu muốn giữ đúng ngữ cảnh gốc) qua
`HybridSearchService.search()` (trực tiếp trong process Python, theo đúng
cách bootstrap của `backend/scripts/build_search_index.py` — không cần
HTTP/Docker riêng, chỉ cần Postgres có embedding đã build) để lấy `pred`,
rồi tính đủ 25 metric so với `recommended_items`/interactions thật.

## 5. Trạng thái backend

Backend hiện **đã build và chạy được** (`cs2307-backend-1` healthy, port
8001) — khác so với lúc viết bản v2 (khi đó daemon chưa chạy). Đang chạy
bước build embedding (`build_search_index.py --skip-catalog-import`) cho
3.030 listing — cần bước này xong (mọi listing có `embedding`) thì Giai đoạn
1 mới dùng được retrieval ngữ nghĩa đầy đủ; nếu chưa xong, `HybridSearchService`
vẫn chạy được ở chế độ structured + full-text (không semantic), pred vẫn có
nhưng chưa phản ánh đúng toàn bộ pipeline.

## 6. Cấu trúc file dự kiến trong `Evaluation/`

```
Evaluation/
├── EVAL_PLAN.md              (file này)
├── explore_data.py           (đã có)
├── requirements.txt          (đã có)
├── reco_metrics_lib/         (đã có — vendor, xem mục 2)
├── config.py                 đường dẫn: repo root, gen_user_data/data
├── adapters.py               ground truth JSON -> DataFrame (Nhóm A-G, mục 3)
├── live_client.py            gọi HybridSearchService trực tiếp trong process
│                             (theo pattern backend/scripts/build_search_index.py),
│                             trả về pred cho từng raw_query
├── run_validate.py           Giai đoạn 0 — offline, validate + thống kê mô tả
├── run_eval.py                Giai đoạn 1 — live, tính 25 metric + in bảng
│                             + ghi results/*.json
└── results/                  output có timestamp (sẽ .gitignore)
```

## 7. Còn cần bạn xác nhận

1. Cách hiểu true/pred ở mục 0/3 — đúng ý bạn chưa?
2. `pred` gọi `HybridSearchService` trực tiếp trong process (không qua HTTP)
   — vẫn giữ như đã chọn trước đó, hay giờ muốn đổi sang gọi qua HTTP
   `/v1/search` vì backend đã chạy thật rồi?
3. Có nên đợi build embedding xong hẳn mới bắt đầu code Giai đoạn 1, hay code
   song song (test trước bằng vài event, chạy full sau khi embedding xong)?
