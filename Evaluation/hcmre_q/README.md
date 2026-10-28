# HCMRE-Q — benchmark tìm kiếm bất động sản bằng truy vấn tiếng Việt

Bộ đánh giá độc lập cho hệ thống tìm kiếm: sinh truy vấn có nhãn liên quan, chạy các hệ thống và
baseline, tính metric và vẽ hình. Trước ngày 28/10/2026 thư mục này nằm ở `Experiments/benchmark/`.
Mô tả phương pháp và kết quả: mục 6.9 và Phụ lục A của `Documentation/DL_Proposal_BDS_HCM.md`.

| File / thư mục | Vai trò |
|---|---|
| `corpus.py` | Nạp kho 3.037 tin, sửa lỗi diện tích, hàm gán nhãn đặc điểm, toạ độ địa danh. `Experiments/eda` và `Experiments/preprocessing` cũng dùng file này |
| `build_benchmark.py` | Sinh 600 truy vấn + nhãn (`qrels.tsv`), chia train/val/test với seed cố định → `data/` |
| `extract_snapshot.py` | Trích bảng `properties`, khoảng cách tiện ích và vector tài liệu từ bản backup → `snapshot/` |
| `compute_fts_scores.py` | Tính điểm full-text PostgreSQL của 600 truy vấn → `snapshot/fts_scores.csv` |
| `embed_benchmark.py` | Sinh vector truy vấn qua embedding API (LM Studio), phần Deep Learning |
| `eval_benchmark.py` | Chạy các hệ thống và baseline, tính nDCG@10, MRR@10, P@10, Success@10, Recall@100 và khoảng tin cậy bootstrap → `results/` |
| `make_figures.py` | Vẽ hình cho tài liệu → `Documentation/figures/` |
| `data/`, `snapshot/`, `results/` | Dữ liệu benchmark, snapshot cơ sở dữ liệu, kết quả |

Yêu cầu: Python ≥ 3.10, `pandas`, `numpy`, `scipy`, `matplotlib`, `pydantic` 2.x, `python-dotenv` (hai gói cuối đã có trong `backend/requirements.txt`).

## 1. Chạy lại

```bash
cd Evaluation/hcmre_q
python build_benchmark.py --out data                    # sinh lại 600 truy vấn + qrels (seed cố định)
python eval_benchmark.py --repo ../.. --bench data --snapshot snapshot --out results
```

`snapshot/` đã được trích sẵn từ `backups/real_estate_2026-07-31.dump`, gồm bảng `properties`, khoảng cách tiện ích và **3.037 vector Qwen3-Embedding-0.6B mà hệ thống dùng lúc đó**. Muốn trích lại thì chạy `python extract_snapshot.py` (cần `pg_restore` 16). Điểm full-text của PostgreSQL (`fts_scores.csv`) được tính lại bằng `python compute_fts_scores.py --dsn <postgres>`.

Lưu ý: `.gitignore` của repo bỏ qua `*.npy`, nên `snapshot/qwen3_0.6b_doc_embeddings.npy` không được commit. Máy khác cần chạy lại `extract_snapshot.py`.

## 2. Phần cần chạy trên máy có embedding API (phần Deep Learning)

Vector **truy vấn** phải được sinh trên máy có LM Studio (hoặc endpoint OpenAI-compatible khác). Script dùng đúng tiền tố `query: ` như `backend/src/search/embedding.py`:

```bash
cd Evaluation/hcmre_q
# cùng model với vector tài liệu trong bản backup → không cần mã hoá lại corpus
python embed_benchmark.py --model text-embedding-qwen3-embedding-0.6b --base-url http://127.0.0.1:1234/v1
python eval_benchmark.py --repo ../.. --bench data --snapshot snapshot --out results
# model khác (ví dụ qwen/qwen3-embedding-4b): thêm --corpus rồi chạy eval với --embedding-tag tương ứng
```

Khi có vector truy vấn, `eval_benchmark.py` tự chạy thêm các hệ thống DL: `dense`, `prod_dl`, `prod_dl_graph`, `rrf_bm25_dense`.

## 3. HCMRE-Q — định nghĩa

* **Corpus:** 3.037 tin đăng (`doc_id` = `properties.id`) của bộ dữ liệu cũ, chưa phải bộ v3 (6.703 tin).
* **Truy vấn:** 600 câu, gồm 6 họ:

  | Họ | Nội dung |
  |---|---|
  | F1 | Cấu trúc: loại + vị trí + giá ± phòng ngủ |
  | F2 | F1 kèm diện tích, pháp lý hoặc nội thất |
  | F3 | Gần tiện ích, theo khoảng cách lái xe thực đo |
  | F4 | Đặc điểm mô tả: hẻm xe hơi, dòng tiền, căn góc, nhà mới, view sông, thang máy, sân vườn, hồ bơi |
  | F5 | Gần địa danh: chợ Bến Thành, sân bay Tân Sơn Nhất, Landmark 81, Phú Mỹ Hưng, Làng Đại học |
  | F6 | Loại con: nhà mặt phố, biệt thự/liền kề, shophouse |

  Mỗi họ có 4 phong cách gõ:

  | Phong cách | Mô tả |
  |---|---|
  | S1 | Chuẩn, có dấu |
  | S2 | Không dấu |
  | S3 | Viết tắt/teencode: PN, HXH, Q7, tỏi, 2ty5… |
  | S4 | Hội thoại: số viết bằng chữ, "đổ lại", "tài chính"… |

* **Nhãn (target):** `2` khi thoả mọi ràng buộc. `1` khi thoả mọi ràng buộc cứng và chỉ lệch đúng một ràng buộc mềm trong dải dung sai: giá +15%, diện tích −15%, phòng ngủ ±1, khoảng cách ×1,5, hoặc cùng quận cũ thay vì cùng phường. Còn lại là `0`. Nhãn chỉ tính từ thuộc tính tin đăng, khoảng cách thực đo và hàm gán nhãn đã kiểm định (`corpus.py`). Nhãn **không** dùng `ranker.py`, nên tránh được tính vòng tròn của ground truth v4 (`Evaluation/gen_user_data/generate_v4.py`).
* **Kiểm định hàm gán nhãn đặc điểm:** 96 mẫu dương tính ngẫu nhiên (12 mẫu cho mỗi đặc điểm) cho độ chính xác 94/96 = 97,9% (Wilson 95%: 92,7–99,4%), xem `data/aspect_label_audit.csv`. Mẫu này do trợ lý AI đọc và chấm. Nhóm nên đọc lại 96 dòng này trước khi nộp.
* **Chia tập:** 360 / 120 / 120 truy vấn (train/val/test), chia theo truy vấn. Tập test không dùng chung khung câu (frame) với train/val. Truy vấn của mỗi tập được sinh từ một tập tin đăng "hạt giống" riêng.

## 4. Hình trong tài liệu

```bash
cd Evaluation/hcmre_q && python make_figures.py --results results --data data --fig ../../Documentation/figures
```
