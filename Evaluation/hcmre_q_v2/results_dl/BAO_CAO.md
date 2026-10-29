# Báo cáo chạy HCMRE-Q v2 — hệ thống có embedding (offline)

Ngày chạy: 29/10/2026. Commit repo: `3544225`. Kết quả **tạm thời**, xem mục 5.

## 1. Phạm vi

- Chạy lại benchmark HCMRE-Q v2 ở chế độ offline, thêm các hệ thống dùng embedding (`dense`, `prod_dl`, `prod_dl_graph`, `rrf_bm25_dense`).
- **Không** chạy: `run_live.py` (gọi API thật), nhánh Neo4j thật, bộ chấm tay H1–H5.
- Thước đo chính: nDCG@10 trên tập test (200 câu), nhãn 0–3, `grade_policy = ward_first`.
- Kết quả nằm ở `results_dl/` (`summary.json`, `per_query_metrics.csv`, `reliability.json`, `runs.jsonl.gz`). `results/` giữ nguyên bản đã công bố.

## 2. Cấu hình (evaluation contract)

| Mục | Giá trị |
|---|---|
| Bộ truy vấn | 1.000 câu, chia train 600 / val 200 / test 200 |
| Kho tin | 6.703 tin `Data/v3` sau errata v3.1 (phía nhãn và snapshot) |
| Ngày đóng băng (`--today`) | 2026-10-28 (giống bản công bố) |
| Model embedding | `qwen/qwen3-embedding-4b`, 1024 chiều, qua OpenRouter (nhà cung cấp DeepInfra) |
| Tiền tố | `query: ` / `passage: ` |
| Vector câu hỏi | embed mới, batch 16 câu/request (đã kiểm: cos = 1,000000 so với gửi từng câu) |
| Vector tin | đọc thẳng từ PostgreSQL `properties.embedding`, đủ 6.703/6.703 |
| Parser | `RuleBasedQueryParser` của backend (bản sao offline) |
| Tham số hệ thống | không chỉnh; không dùng tập test để chọn tham số |
| Hash | `summary.json` `56036b03…`; `per_query_metrics.csv` `c2e6e5d6…` |

## 3. Kết quả chính (tập test, n = 200)

| Hệ thống | nDCG@10 | CI95 | P@10 | MRR@10 | Success@10 | Recall@100 | WardP@10 |
|---|---|---|---|---|---|---|---|
| oracle_constraints | 0,9896 | [0,985; 0,994] | 0,7155 | 1,0000 | 1,000 | 1,0000 | 0,9418 |
| **prod_dl** | **0,2553** | [0,218; 0,295] | 0,1700 | 0,3530 | 0,590 | 0,4012 | 0,3950 |
| bm25_rule | 0,2402 | [0,203; 0,279] | 0,1485 | 0,3382 | 0,560 | 0,4134 | 0,4184 |
| **prod_dl_graph** | **0,1897** | [0,158; 0,223] | 0,1265 | 0,2729 | 0,510 | 0,3891 | 0,3716 |
| rrf_bm25_dense | 0,1660 | [0,140; 0,195] | 0,1220 | 0,2408 | 0,540 | 0,4488 | 0,4539 |
| bm25 | 0,1420 | [0,114; 0,173] | 0,0965 | 0,2052 | 0,455 | 0,3878 | 0,3816 |
| dense | 0,1336 | [0,108; 0,162] | 0,0965 | 0,2168 | 0,385 | 0,3417 | 0,4333 |
| bm25_noaccent | 0,1182 | [0,092; 0,147] | 0,0775 | 0,1705 | 0,360 | 0,3629 | 0,3220 |
| tfidf_char | 0,0797 | [0,061; 0,099] | 0,0550 | 0,1262 | 0,300 | 0,3111 | 0,2440 |
| prod_nodl_graph | 0,0738 | [0,058; 0,092] | 0,0500 | 0,1314 | 0,310 | 0,0826 | 0,1929 |
| prod_nodl | 0,0624 | [0,046; 0,081] | 0,0395 | 0,1287 | 0,250 | 0,0602 | 0,1447 |
| pg_fts | 0,0113 | [0,004; 0,022] | 0,0055 | 0,0221 | 0,040 | 0,0204 | 0,0220 |
| random | 0,0042 | [0,003; 0,006] | 0,0032 | 0,0080 | 0,030 | 0,0160 | 0,0184 |

Các hệ thống không dùng embedding (từ `bm25` đến `random`, trừ bốn hệ thống DL) cho nDCG@10 trùng với bản công bố trong `results/` (đã so 4 chữ số; các metric khác chưa so từng cái).

### Ổn định qua các tập

nDCG@10, các hệ thống chính:

| Hệ thống | train (600) | val (200) | test (200) | tất cả (1.000) |
|---|---|---|---|---|
| prod_dl | 0,2850 | 0,2672 | 0,2553 | 0,2755 |
| prod_dl_graph | 0,2347 | 0,2239 | 0,1897 | 0,2236 |
| bm25_rule | 0,2234 | 0,1927 | 0,2402 | 0,2206 |
| rrf_bm25_dense | 0,1776 | 0,1886 | 0,1660 | 0,1775 |
| dense | 0,1593 | 0,1611 | 0,1336 | 0,1545 |
| prod_nodl | 0,0783 | 0,0745 | 0,0624 | 0,0743 |

## 4. So sánh có ý nghĩa thống kê (p đã hiệu chỉnh Holm, test)

| Cặp | p_holm | Kết luận (ngưỡng 0,05) |
|---|---|---|
| prod_dl so với prod_nodl | 0,0055 | khác nhau |
| prod_dl so với dense | 0,0055 | khác nhau |
| prod_dl so với prod_dl_graph | 0,0055 | khác nhau (graph thấp hơn) |
| prod_dl so với rrf_bm25_dense | 0,0055 | khác nhau |
| prod_dl so với bm25 | 0,0055 | khác nhau |
| prod_dl so với bm25_rule | 1,0000 | **không** khác nhau |
| prod_dl_graph so với bm25_rule | 0,1524 | không khác nhau |
| prod_dl_graph so với rrf_bm25_dense | 0,9977 | không khác nhau |
| prod_dl_graph so với bm25 | 0,2266 | không khác nhau |

Tổng cộng 42/55 cặp hệ thống khác nhau có ý nghĩa.

## 5. Nhận xét

1. **Embedding là yếu tố cải thiện lớn nhất:** `prod_dl` 0,255 so với `prod_nodl` 0,062 (khoảng 4 lần), khác biệt có ý nghĩa. Tăng cả trên Success@10 (0,25 → 0,59) và Recall@100 (0,06 → 0,40).
2. **`prod_dl` chưa vượt `bm25_rule`:** 0,255 so với 0,240, p_holm = 1,0. Không kết luận hệ thống tốt hơn baseline BM25 có luật.
3. **Bật graph (Neo4j) làm giảm điểm trong bản sao offline:** `prod_dl_graph` 0,190 thấp hơn `prod_dl` 0,255 (có ý nghĩa). Hiệu ứng này ở cả train và val (0,235 và 0,224 so với 0,285 và 0,267), nên không chỉ do tập test.
4. **Embedding đơn thuần (`dense`, 0,134) yếu hơn nhiều so với `prod_dl` (0,255):** điểm của hệ thống đến từ việc kết hợp parser, bộ lọc và ranker, không chỉ từ vector.
5. Hệ thống còn cách xa oracle (0,990), tức còn nhiều chỗ để cải thiện. Báo cáo này chưa phân tích nguyên nhân từng lỗi; có thể dùng `explain_qrels.py` cho việc đó.

## 6. Phân rã theo loại (test, nDCG@10)

Số câu test: F1 56, F2 20, F3 40, F4 48, F5 16, F6 20. Nhóm nhỏ (F5, F2, F6) có nhiễu lớn, chỉ nên đọc xu hướng.

**Theo họ truy vấn**

| Họ | n | prod_dl | prod_dl_graph | prod_nodl | bm25_rule | dense |
|---|---|---|---|---|---|---|
| F1 ràng buộc có cấu trúc | 56 | 0,277 | 0,221 | 0,058 | 0,283 | 0,145 |
| F2 cấu trúc mở rộng | 20 | 0,340 | 0,272 | 0,029 | 0,165 | 0,125 |
| F3 gần tiện ích | 40 | 0,205 | 0,135 | 0,037 | 0,096 | 0,134 |
| F4 đặc điểm | 48 | 0,300 | 0,180 | 0,107 | 0,386 | 0,144 |
| F5 địa danh | 16 | 0,095 | 0,094 | 0,019 | 0,102 | 0,060 |
| F6 loại phụ | 20 | 0,231 | 0,230 | 0,086 | 0,247 | 0,143 |

**Theo phong cách gõ**

| Phong cách | n | prod_dl | prod_dl_graph | prod_nodl | bm25_rule | dense |
|---|---|---|---|---|---|---|
| S1 có dấu | 63 | 0,314 | 0,226 | 0,082 | 0,304 | 0,150 |
| S2 không dấu | 36 | 0,274 | 0,238 | 0,054 | 0,337 | 0,089 |
| S3 viết tắt | 50 | 0,144 | 0,130 | 0,036 | 0,140 | 0,112 |
| S4 hội thoại | 51 | 0,279 | 0,170 | 0,071 | 0,191 | 0,166 |

**Theo loại vị trí**

| Vị trí | n | prod_dl | prod_dl_graph | prod_nodl | bm25_rule | dense |
|---|---|---|---|---|---|---|
| Phường mới | 141 | 0,216 | 0,168 | 0,061 | 0,248 | 0,124 |
| Khu vực/quận cũ | 32 | 0,455 | 0,305 | 0,066 | 0,293 | 0,238 |
| Không nêu vị trí | 27 | 0,224 | 0,167 | 0,065 | 0,136 | 0,059 |

Điểm đáng chú ý:
- `prod_dl` kém nhất ở câu địa danh (F5, 0,095) và câu viết tắt (S3, 0,144).
- Với câu nêu **phường mới** (70% bộ câu), `prod_dl` (0,216) thấp hơn `bm25_rule` (0,248). Hệ thống tốt hơn ở câu nêu khu vực/quận cũ (0,455).
- Đây là chỗ cần cải thiện nếu ưu tiên phường mới là mục tiêu.

## 7. Độ tin cậy của phép đo (chạy trong `results_dl/reliability.json`)

| Mã | Phép kiểm | Kết quả | Ngưỡng | Trạng thái |
|---|---|---|---|---|
| D1 | Hợp lý: oracle / random | 0,990 / 0,004 | oracle ≥ 0,90; random ≤ 0,05 | Đạt |
| D3 | Ổn định khi chia đôi tập test (τ trung bình) | 0,895 (p05 = 0,782) | ≥ 0,80 | Đạt |
| D4 | Bền với nhiễu nhãn (τ nhỏ nhất) | 1,000 | ≥ 0,80 | Đạt |
| D5 | Nhạy với tham số (đổi ngưỡng gần, đổi mức 1 và 2, bỏ ngoại lai toạ độ) | τ = 1,000 ở các biến thể hiển thị | báo cáo | Thứ hạng không đổi |

## 8. Hạn chế — đọc trước khi trích dẫn

1. **DB chưa áp errata v3.1.** Vector trong PostgreSQL (nguồn vector tin) tạo từ `search_text` của v3. Khoảng 3.861 tin (58% kho) bị errata v3.1 sửa (loại BĐS, giá, phường), nên vector của chúng phản ánh nội dung cũ. Nhãn và các hệ thống không dùng DL đã ở v3.1. **Điểm `prod_dl`, `prod_dl_graph`, `dense`, `rrf_bm25_dense` là tạm**; chưa đo được mức lệch.
2. **Chưa đối chiếu với hệ thống thật.** Không chạy `run_live.py`; chưa kiểm bản sao offline có khớp backend và Neo4j thật không (README của benchmark cũng ghi nhánh Neo4j chưa đối chiếu). Hiệu ứng graph ở mục 5.3 chỉ đúng với bản sao offline.
3. **Bộ dữ liệu chưa qua người chấm.** Các phép kiểm A2–A6, B2, B3 của `META_EVAL.md` vẫn chờ. Theo giao thức, bộ chưa được dùng cho báo cáo chính thức. Dự báo của AI: A5 (ưu tiên phường) có thể không đạt, khi đó thước đo chính chuyển sang `--grade-policy near_first`. Lần chạy này dùng `ward_first`.
4. **Một lần chạy, một seed.** Không có lặp lại; khoảng tin cậy chỉ phản ánh mẫu 200 câu, không phản ánh biến thiên của embedding.
5. **Nhóm nhỏ:** F5 (16 câu), F2 và F6 (20 câu) có khoảng tin cậy rộng.
6. **Cấu hình khác lúc chạy thật:** `.env` đang để `SEARCH_USE_LLM_PARSER=true`; bản offline dùng parser theo luật. Số ở đây không phải là điểm của API đang chạy.

## 9. Việc tiếp theo (nếu cần số chính thức)

1. Áp errata v3.1 lên PostgreSQL và Neo4j (`Data/v3/patches/`), chạy lại `build_search_index.py --skip-catalog-import --skip-graph-metadata`. Hoặc dùng `embed_benchmark.py --corpus` để embed lại từ `search_text` v3.1 của snapshot mà không động vào DB.
2. Chạy lại `embed_benchmark.py` và `eval_benchmark.py`; so với bảng ở mục 3 để biết mức lệch.
3. Đặt `SEARCH_USE_LLM_PARSER=false`, chạy `run_live.py` và kiểm tra `replica check` ≥ 190/200.
4. Chờ kết quả người chấm H1–H5.
