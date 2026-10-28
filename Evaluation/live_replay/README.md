# Live replay — đánh giá hệ thống đang chạy qua `POST /v1/search`

Gửi lại `raw_query` của từng event trong ground truth qua backend đang chạy, lấy thứ hạng thật của hệ thống làm `pred`, rồi tính 25 metric (nhóm A–G) bằng `reco_metrics_lib/`. Thiết kế và lý do chọn metric: [`../docs/01_THIET_KE_DANH_GIA.md`](../docs/01_THIET_KE_DANH_GIA.md). Kết quả và hạn chế của lần chạy hiện có: [`../docs/04_KET_QUA_V4_VA_HAN_CHE.md`](../docs/04_KET_QUA_V4_VA_HAN_CHE.md).

> **Đọc trước khi trích dẫn số liệu.** Ground truth v4 được chọn bằng chính hàm chấm điểm của `ranker.py`, và câu hỏi được viết khớp parser. Vì vậy các con số ở đây là **kiểm tra tự nhất quán**, dùng để bắt lỗi và hồi quy, không phải thước đo chất lượng gợi ý. Benchmark độc lập là [`../hcmre_q/`](../hcmre_q/README.md).

| File | Vai trò |
|---|---|
| `config.py` | Đường dẫn dữ liệu (events, interactions, users, listings) và địa chỉ backend |
| `adapters.py` | Chuyển JSON ground truth thành DataFrame theo API của `recommenders` |
| `live_client.py` | Gọi `POST /v1/search`, trả về `[{listing_id, score, rank}]` |
| `run_validate.py` | Giai đoạn 0, offline: kiểm tra cấu trúc dữ liệu, không tính metric |
| `run_eval.py` | Giai đoạn 1, cần backend: replay và tính toàn bộ metric |
| `recompute_from_cache.py` | Tính lại metric từ `per_query.json` của lần chạy trước, không gọi backend |
| `reco_metrics_lib/` | Bản rút gọn thư viện metric Microsoft `recommenders` (MIT, xem `NOTICE.md`) |
| `results/` | Kết quả các lần chạy; `Final/` là bản gộp dùng để báo cáo |

## Dữ liệu đầu vào

Khai báo trong `config.py`, đọc từ `../gen_user_data/data/`:

| Vai trò | File | Số bản ghi |
|---|---|---|
| Ground truth (nhóm A) | `recommendation_events_v4_claude.json` | 488 event, mỗi event 10 `recommended_items` |
| Hành vi (nhóm B/C/E/F) | `interactions_v3_claude.json` | 982 tương tác |
| User (phân khúc, intent) | `users_v3.json` | 200 user |
| Catalog (đặc trưng tiện ích, độ phủ) | `listings.json` | 3.030 tin |

Ground truth là 10 `recommended_items` của mỗi event, không phải `llm_output` (lớp giải thích hiển thị cho người dùng; xem `../docs/01_THIET_KE_DANH_GIA.md` mục 0). Tương tác vẫn là bản v3 vì chưa được sinh lại cho v4, nên nhóm B/C/E/F chưa có ý nghĩa với v4 (`../docs/04_KET_QUA_V4_VA_HAN_CHE.md` mục 6).

`pred` luôn lấy từ hệ thống thật. Script chỉ gửi `raw_query` và **không gửi `filters`**: backend tự suy ra tiêu chí vào `preference_filters`, vốn chỉ ảnh hưởng thứ hạng chứ không loại ứng viên. Lý do nằm trong docstring của `fetch_live_results()` trong `run_eval.py`.

## Cài đặt

```bash
cd Evaluation/live_replay
pip install -r requirements.txt
```

`reco_metrics_lib/` cần pandas 2.x; với pandas 3 các metric báo lỗi `nested renamer is not supported`, nên `requirements.txt` giới hạn `pandas<3`. Backend phải đang chạy (`docker compose up -d backend` ở gốc repo). Muốn có semantic search đầy đủ thì LM Studio phải chạy đúng model embedding đã dùng để build index; xem `README.md` gốc, mục "Embedding provider".

## Chạy

```bash
python run_validate.py                          # giai đoạn 0 — offline
python run_eval.py                              # giai đoạn 1 — cả 488 event (khoảng 53 giây/truy vấn)
python run_eval.py --limit 20                   # chạy thử 20 event đầu
python run_eval.py --ids rs_300005,rs_300007    # chạy lại vài event (ví dụ các event bị lỗi)
python run_eval.py --k 5                        # đổi k (mặc định = số ground truth mỗi event = 10)
python recompute_from_cache.py --run-dir results/20260806T144112_n481,results/20260806T162644_n7
```

Biến môi trường `EVAL_BACKEND_URL` (mặc định `http://localhost:8001`) đổi địa chỉ backend.

## Kết quả

Mỗi lần chạy tạo `results/<timestamp>_n<số event>/` gồm `summary.json` (metric tổng hợp, NDCG theo phân khúc và intent), `per_query.json` (từng câu hỏi: ground truth, `live_pred`, các hit) và `per_query.csv` (bản phẳng để mở bằng Excel).

| Thư mục | Nội dung |
|---|---|
| `results/20260806T144112_n481/` | Lần chạy đầy đủ: 481/488 event thành công, 7 event lỗi timeout hoặc ngắt kết nối |
| `results/20260806T162644_n7/` | Chạy lại 7 event lỗi bằng `--ids` |
| `results/Final/` | Gộp hai lần trên bằng `recompute_from_cache.py`: **488 event, bản dùng để báo cáo** |
| `results/full_run_v4.log` | Log của lần chạy đầy đủ |

Nhóm A của `Final/`: precision@10 = recall@10 = 0,333; NDCG@10 = 0,356; MAP@10 = 0,235; MRR@10 = 0,694.

Khi một kết quả trông bất thường, mở `per_query.json` hoặc `per_query.csv` của lần chạy và đối chiếu với `Data/Final_Data.csv` (nguồn thật) trước khi kết luận.

## Metric

- **Nhóm A — xếp hạng:** precision, recall, NDCG, MAP, MRR, ARHR, average precision, average recall @k.
- **Nhóm B/C — rating và phân loại:** RMSE, MAE, MSE, R², explained variance, MAPE; AUC, logloss. So `implicit_score` mô phỏng với `final_score` của hệ thống.
- **Nhóm D — đa dạng**, **E — mới lạ**, **F — bất ngờ**, **G — độ phủ** (catalog và distributional).
