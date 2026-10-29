# Evaluation

Mọi phần đánh giá hệ thống tìm kiếm bất động sản nằm trong thư mục này. Có **ba hướng đánh giá**, mỗi hướng một thư mục; hướng 2 và 3 dùng chung dữ liệu mô phỏng trong `gen_user_data/`. Hướng 1 có hai phiên bản: **v2 cho dữ liệu hiện hành `Data/v3`** và v1 cho bộ 3.037 tin cũ.

## 1. Ba hướng đánh giá

| Hướng | Thư mục | Ground truth | Vai trò |
|---|---|---|---|
| 1. Benchmark HCMRE-Q v2 | [`hcmre_q_v2/`](hcmre_q_v2/README.md) | 1.000 truy vấn tiếng Việt trên 6.703 tin `Data/v3` (errata v3.1), nhãn 0–3 ưu tiên phường mới, độc lập với `ranker.py`; giao thức đăng ký trước và đánh giá chính bộ dữ liệu | **Số liệu chính cho báo cáo** |
| 1'. HCMRE-Q v1 | [`hcmre_q/`](hcmre_q/README.md) | 600 truy vấn trên 3.037 tin cũ, nhãn 0/1/2 | Giữ để so sánh với kết quả cũ |
| 2. Live replay | [`live_replay/`](live_replay/README.md) | Ground truth v4, chọn bằng hàm chấm điểm của `ranker.py` | Kiểm tra tự nhất quán, bắt lỗi hồi quy |
| 3. Baseline offline | [`gen_user_data/`](gen_user_data/README.md) (`run_baselines.py`) | Tương tác mô phỏng v1 | Tham khảo |

**1. HCMRE-Q.** Nhãn liên quan tính từ thuộc tính tin đăng, khoảng cách lái xe thực đo và các hàm gán nhãn đã kiểm định, không dùng công thức xếp hạng của hệ thống. Câu truy vấn có 4 phong cách gõ (có dấu, không dấu, viết tắt, hội thoại) và không viết theo regex của parser. Có chia train/val/test. **v2** (`hcmre_q_v2/`):
- chấm cho cả 6.703 tin;
- 70% câu nêu phường mới;
- thang 0–3: đúng phường > đúng phường lệch nhẹ > sát phường;
- có giao thức đăng ký trước (`PROTOCOL.md`), 13 phép kiểm tự động, bộ chấm tay H1–H5 có ngưỡng đạt, và cách chạy hệ thống thật (offline với embedding, hoặc gọi API live);
- kết quả đánh giá chính bộ dữ liệu nằm ở `META_EVAL.md`, mô tả bộ dữ liệu ở `DATASET_CARD.md`. Các phép kiểm bằng người (A2–A6, B2, B3) **vẫn chờ người chấm**; trong lúc chờ, `META_EVAL.md` có dự báo từ bản tự kiểm của trợ lý AI.

v1 (`hcmre_q/`) là kết quả cũ, diễn giải ở mục 6.9 và Phụ lục A của `Documentation/DL_Proposal_BDS_HCM.md`.

**2. Live replay.** Gửi lại câu hỏi mô phỏng qua `POST /v1/search` của backend đang chạy và tính 25 metric (nhóm A–G). Ground truth v4 dùng chung công thức với ranker và câu hỏi được viết khớp parser, nên con số chỉ cho biết hệ thống có nhất quán với chính nó hay không. Đọc [`docs/04_KET_QUA_V4_VA_HAN_CHE.md`](docs/04_KET_QUA_V4_VA_HAN_CHE.md) mục 5 trước khi trích dẫn. Kết quả 488 event ở `live_replay/results/Final/`.

**3. Baseline offline.** Ba recommender nền (popularity, content, embed_cf) chấm trên tương tác mô phỏng, chia tập theo thời gian. Dùng để cho thấy bộ metric phân biệt được xếp hạng tốt và xấu. Kết quả ở `gen_user_data/data/eval_results.json`.

## 2. Cấu trúc thư mục

```
Evaluation/
├── README.md            file này
├── docs/                tài liệu phương pháp, đọc theo số thứ tự (mục 4)
├── hcmre_q_v2/          hướng 1 (hiện hành): benchmark trên Data/v3, giao thức, meta-eval, bộ chấm tay
├── hcmre_q/             hướng 1, bản v1 trên 3.037 tin cũ
├── live_replay/         hướng 2: replay qua POST /v1/search
│   ├── run_validate.py, run_eval.py, recompute_from_cache.py
│   ├── config.py, adapters.py, live_client.py, reco_metrics_lib/
│   └── results/         Final/ = kết quả gộp 488 event
├── gen_user_data/       dữ liệu mô phỏng (user, tương tác, ground truth v1/v3/v4), KG phụ, hướng 3
└── archive/             bản cũ không còn dùng: dữ liệu v2 và script đi kèm
```

## 3. Dữ liệu mô phỏng: phiên bản nào đang dùng

Các file nằm trong `gen_user_data/data/`; script sinh nằm trong `gen_user_data/`.

| Phiên bản | Sinh bằng | File | Dùng ở | Trạng thái |
|---|---|---|---|---|
| Catalog | `catalog.py` (gọi trong `generate_all.py`) | `listings.json` (3.030 tin thật) | Hướng 2, 3 | Đang dùng |
| v1 | `generate_all.py` | `users.json` (300), `interactions.json` (4.517), `kg/`, `similarity_validation.json` | Hướng 3, KG phụ | Đang dùng |
| v2 | — | — | — | Lưu trữ trong `archive/data_v2/` |
| v3 | `generate_all_v3.py`, rồi `prep_rerank.py` → Claude chọn 3/10 → `apply_rerank.py` | `users_v3.json` (200); `recommendation_events_v3.json`, `interactions_v3.json` (trước khi Claude chọn); `recommendation_events_v3_claude.json`, `interactions_v3_claude.json` (982) | Hướng 2: user, tương tác (nhóm B/C/E/F); đầu vào của v4 | Đang dùng |
| v4 | `generate_v4.py` | `recommendation_events_v4_claude.json` (488 event) | Hướng 2: ground truth nhóm A | Đang dùng |

Hướng 2 khai báo các file nó đọc tại một chỗ: `live_replay/config.py`.

## 4. Tài liệu (`docs/`)

| File | Nội dung | Trạng thái |
|---|---|---|
| [`01_THIET_KE_DANH_GIA.md`](docs/01_THIET_KE_DANH_GIA.md) | Thiết kế live replay: true/pred, 25 metric nhóm A–G, giai đoạn 0/1 | Thiết kế gốc (thời v2); phần metric vẫn áp dụng |
| [`02_GROUND_TRUTH_THEO_PHUONG.md`](docs/02_GROUND_TRUTH_THEO_PHUONG.md) | Plan A: ground truth theo phường/xã, bù theo khoảng cách địa lý | Đã hiện thực trong v3 (`gen_v3.py`) |
| [`03_USER_VA_TUONG_TAC.md`](docs/03_USER_VA_TUONG_TAC.md) | Cách sinh user và tương tác mô phỏng cho nhóm B/C/E/F | Mô tả dữ liệu đang dùng |
| [`04_KET_QUA_V4_VA_HAN_CHE.md`](docs/04_KET_QUA_V4_VA_HAN_CHE.md) | Kết quả live replay với ground truth v4 và hạn chế | Kết quả hiện có; đọc mục 5 trước khi trích dẫn |
| [`05_DE_XUAT_GROUND_TRUTH_DOC_LAP.md`](docs/05_DE_XUAT_GROUND_TRUTH_DOC_LAP.md) | Đề xuất ground truth độc lập cho live replay | Chưa hiện thực; HCMRE-Q theo cùng nguyên tắc |

## 5. Chạy nhanh

Người mới chạy hướng 1 lần đầu: đọc [`hcmre_q_v2/HUONG_DAN_CHAY.md`](hcmre_q_v2/HUONG_DAN_CHAY.md).

```bash
# Hướng 1 — HCMRE-Q v2, không cần backend (dữ liệu phải ở v3.1: python Data/v3/pipeline/fix_v3_quality.py --apply)
cd Evaluation/hcmre_q_v2
pip install -r requirements.txt
python eval_benchmark.py --data data --snapshot snapshot --out results
python run_live.py --base-url http://localhost:8001 --split test --out results/live_test   # hệ thống thật, cần backend

# Hướng 2 — live replay
cd Evaluation/live_replay
pip install -r requirements.txt
python run_validate.py            # offline: kiểm tra cấu trúc dữ liệu
python run_eval.py --limit 20     # cần backend đang chạy (docker compose up -d backend)
python recompute_from_cache.py --run-dir results/20260806T144112_n481,results/20260806T162644_n7   # tính lại từ cache, không gọi backend

# Hướng 3 — baseline offline
cd Evaluation/gen_user_data
python run_baselines.py
```

## 6. Lịch sử sắp xếp

Ngày 28/10/2026 thư mục được sắp xếp lại hai lần: gom các phần đánh giá nằm rải rác vào đây, rồi chia theo hướng đánh giá. Bảng dưới giúp tìm file theo đường dẫn cũ. Các file kết quả trong `live_replay/results/` vẫn ghi đường dẫn tuyệt đối lúc chạy.

| Đường dẫn cũ | Đường dẫn mới |
|---|---|
| `gen_user_data/` (gốc repo) | `Evaluation/gen_user_data/` |
| `Experiments/benchmark/` | `Evaluation/hcmre_q/` |
| `Plan/Plan A - Ground Truth.md` | `Evaluation/docs/02_GROUND_TRUTH_THEO_PHUONG.md` |
| `Evaluation/EVAL_PLAN.md` | `Evaluation/docs/01_THIET_KE_DANH_GIA.md` |
| `Evaluation/EVAL_SCENARIO_USERS_INTERACTIONS.md` | `Evaluation/docs/03_USER_VA_TUONG_TAC.md` |
| `Evaluation/EVAL_SCENARIO_v4.md` | `Evaluation/docs/04_KET_QUA_V4_VA_HAN_CHE.md` |
| `Evaluation/EVAL_SCENARIO.md` | `Evaluation/docs/05_DE_XUAT_GROUND_TRUTH_DOC_LAP.md` |
| `Evaluation/{config,adapters,live_client,run_validate,run_eval,recompute_from_cache}.py`, `requirements.txt`, `reco_metrics_lib/`, `results/` | `Evaluation/live_replay/` |
| `Evaluation/gen_user_data/run_eval.py` | `Evaluation/gen_user_data/run_baselines.py` |
| `Evaluation/explore_data.py`, `Evaluation/gen_user_data/generate_all_v2.py` | `Evaluation/archive/` |
| `Evaluation/gen_user_data/data/*_v2*.json`, `data/csv/users_v2.csv`, `data/csv/recommendation_events_v2_claude.csv` | `Evaluation/archive/data_v2/` |
