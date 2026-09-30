# Evaluation

Đánh giá chất lượng **thật** của hybrid search (`backend/src/search`) bằng cách
replay lại ground truth thật qua hệ thống đang chạy, thay vì chỉ so sánh dữ
liệu tĩnh với nhau. Toàn bộ thiết kế/lý luận chi tiết (vì sao chọn từng metric,
những lần sửa sai giữa chừng, các phát hiện về chất lượng dữ liệu) nằm ở
[`EVAL_PLAN.md`](EVAL_PLAN.md) — file này chỉ tóm tắt phần "cách dùng".

## Ground truth là gì

Ground truth lấy từ `gen_user_data/data/recommendation_events_v2_claude.json`:
mỗi event có `raw_query` + `filters_applied` + 10 `recommended_items` (xếp
hạng bằng hàm `relevance_v2()` — đo độ khớp thật giữa hồ sơ user và listing,
xem `gen_user_data/generation/gen_v2.py:171`). **`recommended_items` mới là
ground truth**, không phải `llm_output` (chỉ là lớp giải thích/hiển thị phía
sau, xem `EVAL_PLAN.md` mục 0 để biết vì sao).

`pred` (dự đoán để so sánh) luôn lấy từ **hệ thống thật đang chạy** — replay
`raw_query` qua `POST /v1/search`, không dùng lại field tĩnh nào trong JSON.

## Cài đặt

```bash
cd Evaluation
pip install -r requirements.txt
```

Cần backend đang chạy (`docker compose up -d backend` ở thư mục gốc repo).
Muốn có semantic search đầy đủ (không chỉ structured + full-text) thì cần
thêm LM Studio chạy model embedding đúng với model đã build index — xem
README.md gốc, mục "Embedding provider".

## Chạy

```bash
# Giai đoạn 0 — offline, không cần backend, chỉ validate cấu trúc dữ liệu
python run_validate.py

# Giai đoạn 1 — live, cần backend đang chạy, tính toàn bộ metric
python run_eval.py                  # chạy hết 1055 event
python run_eval.py --limit 100      # chỉ chạy 100 event đầu (test nhanh)
python run_eval.py --k 5            # ghi đè k (mặc định = số ground truth/event, hiện =10)
```

Biến môi trường `EVAL_BACKEND_URL` (mặc định `http://localhost:8001`) đổi
được nếu backend chạy ở địa chỉ khác (`config.py`).

## Output

Mỗi lần chạy `run_eval.py` tạo 1 folder riêng trong `results/`:

```
results/<timestamp>_n<số-event>/
├── summary.json      # toàn bộ metric tổng hợp + breakdown theo segment/intent
├── per_query.json     # chi tiết từng query: raw_query, ground_truth, live_pred, hit
└── per_query.csv       # bản rút gọn dạng bảng, mở bằng Excel/Sheets để so sánh tay
```

## Metric tính

- **Nhóm A — Ranking**: precision/recall/ndcg/map/mrr/arhr/average_precision/average_recall @k
- **Nhóm B/C — Rating & Classification**: rmse/mae/mse/rsquared/exp_var/mape,
  auc/logloss — so `implicit_score` thật (từ `interactions_v2_claude.json`) với
  score hệ thống trả về
- **Nhóm D — Diversity**, **Nhóm E — Novelty**, **Nhóm F — Serendipity**,
  **Nhóm G — Coverage** (catalog + distributional)

Toàn bộ hàm metric lấy từ `reco_metrics_lib/` — bản vendor rút gọn của
[`aryan-jadon/Evaluation-Metrics-for-Recommendation-Systems`](https://github.com/aryan-jadon/Evaluation-Metrics-for-Recommendation-Systems)
(dựa trên Microsoft `recommenders`, MIT license — xem
`reco_metrics_lib/NOTICE.md`), không cần cài `recommenders` đầy đủ.

## Lưu ý khi đọc kết quả

`Evaluation/adapters.py::translate_filters_for_live()` đã sửa 2 lỗi từng làm
điểm số thấp giả tạo (không phải do chất lượng search kém):
đổi tên `price_max` → `max_price` (đúng key backend nhận), và gửi **toàn bộ**
`preferred_districts` của user thay vì 1 quận chọn ngẫu nhiên. Chi tiết điều
tra + số liệu trước/sau nằm trong lịch sử trò chuyện lúc phát triển pipeline
này — nếu cần điều tra lại một vấn đề tương tự, viết script mới trong
`Evaluation/`, đọc `per_query.json`/`per_query.csv` của lần chạy gần nhất và
đối chiếu với `Data/Final_Data.csv` (nguồn thật) trước khi kết luận.
