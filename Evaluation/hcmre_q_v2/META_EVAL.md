# HCMRE-Q v2 — Kết quả đánh giá chính bộ dữ liệu (meta-evaluation)

Ngày: 28/10/2026. Giao thức và ngưỡng đạt được đăng ký trước trong [`PROTOCOL.md`](PROTOCOL.md) mục 7. Mọi thay
đổi so với giao thức nằm ở mục 9 của file đó.

File này có ba loại kết quả, được ghi rõ ở từng chỗ:

- **Tự động.** Tính lại được bằng script trong thư mục này. Đây là kết quả chính thức.
- **Tự kiểm của AI.** Trợ lý AI (Claude) chấm thử bộ chấm tay mà không mở `human/keys/`. Đây chỉ là **dự báo
  tạm thời**. Nó không thay được người chấm, vì một người chấm duy nhất và lại là AI đã viết bộ sinh dữ liệu.
- **Chờ người chấm.** Các phép kiểm A2–A6, B2, B3 chỉ được quyết định bằng câu trả lời của người, đặt trong
  `human/answers/`.

## 1. Tóm tắt

Các mục có dấu ✱ là điều kiện bắt buộc để dùng bộ dữ liệu cho báo cáo.

| Mã | Kiểm tra | Kết quả | Ngưỡng | Trạng thái |
|---|---|---|---|---|
| A1 ✱ | Chấm lại độc lập toàn bộ cặp (truy vấn, tin) | 6.703.000 cặp, khớp 100% | 100% | **Đạt** |
| A2 ✱ | Precision của hàm gán nhãn đặc điểm (H1) | AI: 0,969 (93/96), Wilson [0,912; 0,989]; mỗi đặc điểm sai ≤ 1/12 | ≥ 0,90; Wilson ≥ 0,80; không đặc điểm nào sai > 3/12 | Chờ người chấm |
| A3 | Tỉ lệ bỏ sót đặc điểm (H1) | AI: 11/96 = 0,115 | báo cáo | Chờ người chấm |
| A4 ✱ | Độ khớp nhãn 0–3 (H3) | AI: κ trọng số 0,941 (n = 131); khớp hẳn 95,4% | κ ≥ 0,60 | Chờ người chấm |
| A5 ✱ | Ưu tiên phường (H4) | AI: 40/60 = 0,667; p = 0,0067 | ≥ 0,70 và p < 0,05 | Chờ người chấm. AI dự báo **không đạt**, nhưng sát ngưỡng |
| A6 ✱ | Sửa giá của errata v3.1 (H5) | AI: 60/60; Wilson [0,940; 1] | ≥ 0,95; Wilson ≥ 0,85 | Chờ người chấm |
| B1 ✱ | Đọc ngược câu hỏi ra ràng buộc vàng | 1.000/1.000 | 100% | **Đạt** |
| B2 ✱ | Câu hỏi đúng và đủ ý (H2) | AI: 100/100 | ≥ 0,95 | Chờ người chấm |
| B3 | Độ tự nhiên (H2) | AI: 100% câu ≥ 3 điểm; trung bình 4,33 | ≥ 80% câu ≥ 3 | Chờ người chấm |
| B4 | Độ đa dạng | distinct-1 0,050; distinct-2 0,261; 36 khung câu | báo cáo | — |
| C1 ✱ | Tách tập train/val/test | 0 vi phạm | 0 | **Đạt** |
| C2 | Câu gần trùng giữa các tập | 0% | ≤ 1% | **Đạt** |
| C3 ✱ | Code nhãn không import `backend` | không có import | đạt | **Đạt** |
| C4 | Cân bằng giữa các tập (χ²) | p = 1,00 / 0,195 / 0,9999 | báo cáo | — |
| D1 ✱ | Kiểm tra hợp lý | oracle 0,990; random 0,004 | oracle ≥ 0,90; random ≤ 0,05 | **Đạt** |
| D2 | Sức phân biệt | 17/21 cặp hệ thống khác nhau có ý nghĩa | báo cáo | — |
| D3 ✱ | Ổn định khi chia đôi tập test | τ trung bình 0,905 | ≥ 0,80 | **Đạt** |
| D4 ✱ | Bền với nhiễu nhãn | τ trung bình 1,000 | ≥ 0,80 | **Đạt** |
| D5 | Nhạy với tham số | τ = 1,000 ở cả 6 biến thể | báo cáo | — |
| E1 ✱ | Tái lập với 3 giá trị `PYTHONHASHSEED` | hash trùng nhau | trùng | **Đạt** |

**Kết luận hiện tại.**

- Mọi ngưỡng ✱ kiểm được tự động đều đạt.
- Các ngưỡng ✱ cần người chấm (A2, A4, A5, A6, B2) **chưa có**. Theo mục 7 của giao thức, bộ dữ liệu chưa được
  dùng cho báo cáo chính thức cho tới khi có kết quả này.
- Bản tự kiểm của AI dự báo:
  - A2, A4, A6, B2 và B3 nhiều khả năng đạt.
  - A5 nằm sát ngưỡng và nghiêng về **không** đạt. Khi đó luật dự phòng đã đăng ký trước được áp dụng: đổi chỗ
    mức 1 ↔ 2 cho thước đo chính, tức `--grade-policy near_first`, và báo cáo cả hai cách.
  - Thứ hạng các hệ thống không đổi giữa hai cách (mục 4.2).
- Bản sao offline của hệ thống production đã được đối chiếu với backend chạy thật (mục 4.3). Khi dữ liệu, vector
  và ngày như nhau, top-10 trùng hoàn toàn ở 200/200 câu test, cả khi tắt và khi bật embedding. Nhánh Neo4j chưa
  được đối chiếu.

## 2. Thiết kế phép đánh giá

Câu hỏi đặt ra là: **có tin được con số nDCG mà benchmark này cho ra không?** Câu hỏi đó được tách làm năm phần,
mỗi phần có phép kiểm riêng và ngưỡng chốt trước khi thấy dữ liệu.

| Nhóm | Câu hỏi | Cách kiểm |
|---|---|---|
| A. Nhãn đúng không? | Nhãn có đúng định nghĩa, và định nghĩa có đúng với người mua? | (A1) viết lại bộ chấm từ đầu, chỉ dựa trên văn bản giao thức, rồi so trên **mọi** cặp. (A2–A6) người chấm mù trên mẫu ngẫu nhiên, báo cáo khoảng tin cậy Wilson hoặc κ có trọng số |
| B. Câu hỏi đúng không? | Câu có nói đúng ràng buộc vàng, và có giống câu người thật gõ? | (B1) một bộ đọc độc lập lấy lại giá trị vàng từ câu; (B2, B3) người chấm; (B4) thống kê đa dạng |
| C. Tách tập sạch không? | Có rò rỉ giữa train/val/test, hay giữa nhãn và hệ thống? | Kiểm trùng qid, hạt giống, khung câu, câu gần trùng; kiểm tĩnh import; χ² cân bằng |
| D. Có đo được hệ thống không? | Benchmark có phân biệt được hệ thống tốt và kém, và kết luận có bền không? | Hệ thống mốc (oracle, random); kiểm định hoán vị + Holm; Kendall τ khi chia đôi, khi thêm nhiễu nhãn, khi đổi tham số |
| E. Tái lập được không? | Chạy lại có ra đúng như cũ? | Sinh lại với 3 giá trị `PYTHONHASHSEED`, so hash |

Các biện pháp liêm chính:

- Đăng ký trước giao thức, kèm nhật ký sai lệch.
- Nhãn độc lập với hệ thống: không import `backend/`, được kiểm tĩnh.
- Chấm **toàn bộ** 6.703 tin cho mỗi câu, nên không có thiên lệch pool.
- Hàm gán nhãn và bộ sinh câu được **đóng băng** trước khi rút mẫu chấm tay.
- Mẫu chấm tay **tách khỏi** mọi tin đã dùng để phát triển (PROTOCOL mục 9.5d và 9.7).
- Người chấm **mù** với nhãn tự động. H1 trộn tin máy nói "có" và "không" vào một file.

## 3. Kết quả tự động

### 3.1 Thành phần và nhãn

| Chỉ số | Giá trị |
|---|---|
| Câu hỏi | 1.000. Chia train/val/test = 600/200/200 |
| Vị trí trong câu | phường 704, quận cũ 162, không nêu 134. Trong các câu có nêu vị trí, 81,3% nêu phường |
| Câu nêu phường kèm quận cũ | 120 |
| Dòng qrels (mức > 0) | 40.459. Gồm mức 1: 14.991; mức 2: 10.315; mức 3: 15.153 |
| Số tin mức 3 mỗi câu, tập test | trung bình 14,5; trung vị 10; nhỏ nhất 1; lớn nhất 50 |
| Cặp liên quan có thuộc tính lấy từ văn bản | giá 1,45%; phòng ngủ 0,21%; pháp lý 0,16%; nội thất 0,51% |
| Cặp liên quan có tin bị cờ `ward_coord_outlier` | 2,28% |
| Tỉ lệ tin crawl 2026 trong cặp liên quan | 57,2%. Trong toàn kho là 57,5%, nên nhãn không thiên về nguồn nào |

### 3.2 Câu hỏi (B1, B4) và tách tập (C1–C4)

- **B1:** cả 1.000 câu đọc ngược ra đủ giá trị vàng: tên khu vực, số tiền, số phòng, khoảng cách, từ khoá loại và
  đặc điểm.
- **B4:**
  - 1.000 câu khác nhau, dùng 36 khung câu;
  - độ dài trung bình 15,7 từ, p10 = 8, p90 = 25;
  - distinct-1 = 0,050, distinct-2 = 0,261.
- **C1:**
  - không có qid, câu hay tin hạt giống nào dùng chung giữa các tập;
  - không có khung câu của test xuất hiện ở train/val;
  - không có khung câu của val xuất hiện ở train.
- **C2:** không có câu nào gần trùng với câu ở tập khác (Jaccard 3-gram ký tự ≥ 0,9).
- **C3:** `corpus.py`, `build_benchmark.py`, `check_labels.py` và `Data/v3/pipeline/price_text.py` không import
  `backend`.
- **C4:**
  - phân phối họ câu giống hệt nhau giữa các tập (p = 1,00);
  - phân phối phong cách: χ² = 8,64, df = 6, p = 0,195;
  - phân phối loại vị trí: p = 0,9999.

### 3.3 Tái lập (E1)

Sinh lại với `PYTHONHASHSEED` = 0, 1 và 12345 đều ra đúng các hash sau:

```
queries.jsonl          4084fdf1d94871c98d8c19a02cbf0fce784978bc5a6b875a1c946894efad8d57
qrels.tsv              7e2ab59c99ae1892ec0831df790f97c68852b12e63dbced23db52908c50c694f
corpus_attributes.csv  55b9e4911812437e0ff3532a685b17e8cb98b0a2214d5e9b1b7f02f87131b21c
stats.json             02a5b2a7d7df7d4ca51e6ce1247143f0c314829f24ca4e0903f7c1924a26f186
```

Ngoài phạm vi E1, kết quả hệ thống cũng được kiểm tái lập. Toàn bộ pipeline được chạy lại từ đầu: xoá `data/`,
`results/` và bộ chấm tay, rồi sinh lại. Sau đó `eval_benchmark.py` được chạy thêm lần thứ hai. Kết quả:

- mọi file trong `data/`, `results/` và bộ chấm tay đều trùng từng byte;
- riêng thứ tự hoà điểm ở sâu trong bảng xếp hạng `bm25_rule` (hạng > 50) từng đổi theo hash seed của Python, có
  lẽ do code backend duyệt `set`. Metric không đổi. Script nay tự chạy với `PYTHONHASHSEED=0`.

## 4. Độ tin cậy khi so sánh hệ thống (D1–D5) và kết quả baseline

### 4.1 Kết quả trên tập test (200 câu)

Cột "near_first" là cùng thước đo khi đổi chỗ mức 1 ↔ 2, theo luật dự phòng của A5.

| Hệ thống | nDCG@10 | KTC 95% | P@10 | MRR@10 | Success@10 | Recall@100 | WardP@10 | nDCG@10 near_first |
|---|---|---|---|---|---|---|---|---|
| oracle_constraints (mốc trên) | 0,990 | 0,985–0,994 | 0,716 | 1,000 | 1,00 | 1,000 | 0,942 | 0,962 |
| bm25_rule | 0,240 | 0,203–0,279 | 0,149 | 0,338 | 0,56 | 0,413 | 0,418 | 0,233 |
| bm25 | 0,142 | 0,114–0,173 | 0,097 | 0,205 | 0,46 | 0,388 | 0,382 | 0,135 |
| bm25_noaccent | 0,118 | 0,092–0,147 | 0,078 | 0,171 | 0,36 | 0,363 | 0,322 | 0,115 |
| tfidf_char | 0,080 | 0,061–0,100 | 0,055 | 0,126 | 0,30 | 0,311 | 0,244 | 0,078 |
| prod_nodl_graph | 0,074 | 0,057–0,091 | 0,050 | 0,131 | 0,31 | 0,083 | 0,193 | 0,072 |
| prod_nodl | 0,062 | 0,046–0,080 | 0,040 | 0,129 | 0,25 | 0,060 | 0,145 | 0,064 |
| pg_fts | 0,011 | 0,004–0,022 | 0,006 | 0,022 | 0,04 | 0,020 | 0,022 | 0,012 |
| random (mốc dưới) | 0,004 | 0,003–0,006 | 0,003 | 0,008 | 0,03 | 0,016 | 0,018 | 0,005 |

Cách đọc bảng:

- Các hệ thống `prod_*` là bản sao offline của pipeline production **khi tắt embedding**. Điểm thấp có lý do rõ:
  full-text của PostgreSQL (`plainto_tsquery`, ghép điều kiện bằng AND) chỉ khớp được ít nhất một tin ở **30/1.000**
  câu. Vì vậy ứng viên gần như chỉ được xếp theo độ mới.
- Đây là đặc điểm của hệ thống, không phải lỗi của bộ dữ liệu. Phần semantic/DL được đo bằng `embed_benchmark.py`
  hoặc `run_live.py`.
- `bm25_rule` (BM25 lấy ứng viên rồi ranker production xếp lại) cho thấy ranker có ích khi được nhận ứng viên tốt.
- Các bản sao `prod_*` cho đúng bảng xếp hạng của API thật (mục 4.3), nên điểm của chúng là điểm của hệ thống.

### 4.2 Các phép kiểm độ tin cậy

- **D1:**
  - oracle đạt 0,990 (≥ 0,90), random đạt 0,004 (≤ 0,05);
  - thứ tự oracle > bm25_rule > random đúng như yêu cầu.
- **D2:**
  - 17/21 cặp hệ thống thật khác nhau có ý nghĩa (hoán vị ghép cặp, Holm, α = 0,05);
  - 4 cặp không phân biệt được: bm25 ~ bm25_noaccent, prod_nodl ~ prod_nodl_graph, prod_nodl ~ tfidf_char và
    prod_nodl_graph ~ tfidf_char.
- **D3:** chia đôi tập test ngẫu nhiên 1.000 lần. τ trung bình giữa hai nửa là 0,905; phân vị 5% là 0,810.
- **D4:** dịch ±1 cho 10% nhãn khác 0, lặp 200 lần. τ luôn bằng 1,000.
- **D5:** τ = 1,000, tức thứ hạng hệ thống không đổi, trong cả 6 biến thể:
  - ngưỡng "gần" 0,5 km hoặc 1,5 km;
  - dải dung sai ×0,5 hoặc ×1,5;
  - đổi chỗ mức 1 ↔ 2;
  - bỏ các tin `ward_coord_outlier`.

Với `--grade-policy near_first`, D1 vẫn đạt (oracle 0,962), D3 có τ = 0,880 và D4 có τ = 1,000. Kết luận về thứ
hạng hệ thống vì vậy không phụ thuộc vào kết quả A5.

### 4.3 Bản sao offline so với backend chạy thật (29/10)

Điểm của `prod_*` chỉ có nghĩa nếu bản sao xếp hạng **giống hệt** API thật. Cách kiểm:

- Dựng backend thật từ chính repo: FastAPI, PostgreSQL 16 + pgvector, migration Alembic, `build_search_index.py`.
  Dữ liệu được nạp từ bản v3 gốc bằng `Data/v3/pipeline/load_v3.sql`, rồi vá bằng `v3_1_postgres.sql`; kết quả
  trùng bản v3.1. LLM parser, LLM answer và Neo4j tắt.
- Chạy 89 test của backend: đều đạt. `search_text` trong DB trùng `snapshot/` ở 6.703/6.703 tin.
- Gửi 200 câu test qua `POST /v1/search` bằng `run_live.py`, rồi so từng bảng xếp hạng với bản sao offline.

Môi trường kiểm không có LM Studio. Vì vậy cả backend lẫn `embed_benchmark.py` gọi cùng một **model thay thế**: một
server tất định giả lập `/v1/embeddings`, 1.024 chiều, băm túi từ. Điểm của nó không nói gì về chất lượng model
thật. Nó chỉ cho biết hai đường code có ra cùng kết quả khi dùng cùng vector hay không.

| Cấu hình backend | Bản sao | Top-10 trùng hẳn | Top-100 trùng hẳn | nDCG@10 live / offline |
|---|---|---|---|---|
| Không embedding; mọi tin cùng một `created_at` (nạp vào DB trống bằng `load_v3.sql`) | prod_nodl | 0/200 | 0/200 | 0,0796 / 0,0624 (p Holm = 0,53) |
| Không embedding; `created_at` tăng theo thứ tự dòng của `properties_v3.csv` | prod_nodl | **200/200** | 200/200 | 0,0624 / 0,0624 |
| Embedding thay thế; vector tài liệu float16 (bản cũ của `embed_benchmark.py`) | prod_dl | 191/200 | 42/200 | 0,2500 / 0,2500 |
| Như trên, vector float32 | prod_dl | **200/200** | 196/200 | 0,2500 / 0,2500 |
| Như trên, vector đọc thẳng từ PostgreSQL (`--doc-vectors-from-db`) | prod_dl | **200/200** | 194/200 | 0,2500 / 0,2500 |

Cách đọc:

- **Bản sao đúng logic.** Khi dữ liệu, vector và ngày như nhau, top-10 trùng ở 200/200 câu, ở cả hai cấu hình.
- **Khác biệt còn lại chỉ nằm ở tin hoà điểm sâu trong top-100.** Ranker làm tròn `final_score` tới 4 chữ số, rồi
  xếp hoà theo `posted_date` và thứ tự ứng viên. Hai trường hợp đã xem:
  - tin trùng nội dung có vector trùng nhau, nên thứ tự giữa chúng là tuỳ ý;
  - sai số float của pgvector so với numpy (dưới 10⁻⁷) đẩy một điểm qua ngưỡng làm tròn. Ví dụ câu v2q0868, tin
    46015086: `final_score` chưa làm tròn là 0,4916511 ở offline và 0,4916510 ở live, nên thành 0,4917 và 0,4916.

  Không câu nào đổi nDCG@10.
- **Không embedding, thứ tự ứng viên phụ thuộc `created_at`.** 97% câu không khớp full-text, nên 500 ứng viên được
  lấy theo `ORDER BY text_score DESC, created_at DESC`. `load_v3.sql` chèn mọi tin mới bằng một lệnh, nên chúng có
  cùng `created_at`, và PostgreSQL trả về 500 tin tuỳ ý trong số đó. Đây là đặc điểm của backend, không phải của
  benchmark. Bản sao giả định `created_at` tăng theo thứ tự nạp, tức theo `listing_id`. Trên DB thật, kết quả live
  ở cấu hình này vì vậy có thể khác `prod_nodl`, dù mức điểm tương đương.
- **Float16 không đủ.** Lưu vector tài liệu dạng float16 làm lệch điểm semantic tới 1,3·10⁻⁴. Mức lệch đó đủ đổi
  một lần làm tròn, nên 9/200 top-10 bị đảo thứ tự. `embed_benchmark.py` nay lưu float32.
- **Ngày chạy.** `freshness_score` dùng ngày hiện tại của máy chủ (giờ Việt Nam trong Docker). Các bản sao chạy với
  ngày cố định 2026-10-28. Khi ngày lệch 8 ngày, top-10 còn trùng 197/200 và top-100 chỉ còn 82/200; nDCG@10 không
  đổi. Để so với một lần chạy live ở ngày khác, dùng `eval_benchmark.py --today <ngày>`.
- **Chưa đối chiếu:**
  - Nhánh Neo4j (`prod_nodl_graph`, `prod_dl_graph`). Môi trường kiểm không có Neo4j. Truy vấn Cypher lấy 500 tin
    theo `posted_date` giảm dần mà không có khoá phụ, nên ở ranh giới 500 cũng có hoà. Bản sao giả định thứ tự
    import.
  - LLM parser. Bản sao dùng parser luật, nên chỉ so được khi `SEARCH_USE_LLM_PARSER=false`.

  `run_live.py` nay tự in mức trùng giữa live và mọi bản sao (`replica_fidelity` trong `summary.json`). Chạy nó
  trên máy có Neo4j là đủ để kiểm phần này.

## 5. Tự kiểm của AI — dự báo tạm thời, không phải kết quả chính thức

**Cách làm.**

- Trợ lý chấm toàn bộ 543 mục của kit chính thức bằng các trình xem riêng, không mở `human/keys/`.
- Với H1, mọi tin được hiển thị cùng một kiểu ngữ cảnh từ khoá. Trợ lý không thấy hàm gán nhãn kích hoạt ở đâu.

Câu trả lời nằm ở `human/answers_preaudit/`, báo cáo ở `human/preaudit_report/`. Những dự báo này có ba giới
hạn:

- chỉ có một người chấm;
- người chấm là AI;
- AI đó cũng là bên viết bộ sinh dữ liệu, nên có thể mang cùng thiên lệch.

### 5.1 H1 — đặc điểm mô tả (A2, A3)

Precision 93/96 = 0,969. Ba lỗi dương tính giả của hàm gán nhãn:

| Đặc điểm | Đoạn văn | Vì sao hàm sai |
|---|---|---|
| thang máy | "Có không gian phù hợp lắp thang máy" | phủ định có "thuận tiện / có thể / chừa ô … lắp", nhưng chưa có "phù hợp lắp" |
| nhà mới | "Nội thất: Mới 100%" | mẫu "mới 100" không kiểm danh từ đứng trước |
| dòng tiền | "… phù hợp … hoặc khai thác căn hộ dịch vụ (CHDV)" | phủ định phủ tới "căn hộ dịch vụ"; chữ "(CHDV)" ngay sau nằm ngoài cửa sổ phủ định |

Bỏ sót 11/96 = 0,115. Toàn bộ số bỏ sót dồn vào hai đặc điểm:

- **Hẻm xe hơi, 5/12.** Đó là nhà mặt đường ô tô viết theo kiểu khác: "đường rộng 7m, ô tô ra vào thuận tiện",
  "hẻm 7m xe hơi tránh", "sân trước để xe hơi", "xe hơi ngủ ngon lành trong nhà".
- **Nhà mới, 6/12.** Đó là chữ "nhà mới" đứng trơn: "Nhà mới 2 tầng", "nhà mới chưa sử dụng", "kết cấu nhà mới:
  5 tầng".
  - Hàm gán nhãn chỉ nhận các cụm như "mới xây", "xây mới", "mới 100%", "mới tinh", "mới hoàn thiện / hoàn công
    / bàn giao" hay "nhà mới vào ở ngay".
  - Hướng dẫn chấm lại tính "nhà mới 5 tầng" là Có.
  - Hai định nghĩa lệch nhau. Vì vậy các câu F4 "nhà mới" có một số tin đúng bị chấm 0.

Hàm gán nhãn đã đóng băng, nên các lỗi này chỉ được báo cáo, không sửa. Nếu người chấm thấy một đặc điểm sai
> 3/12, luật A2 sẽ loại đặc điểm đó khỏi F4.

**So sánh với bộ H1 cũ (đã thay ở PROTOCOL 9.7).** Trên bộ cũ, AI ra precision 92/96, dòng tiền 9/12, và bỏ sót
7/96. Bộ cũ có hai vấn đề:

- **Không mù:** hai file tách riêng, và trình xem tô đậm chỗ hàm kích hoạt.
- **Có tin đã dùng khi phát triển hàm:** theo nhật ký, chắc chắn có 7/96 tin. Theo danh sách rộng `lf_dev` thì
  là 18/96 tin, trong đó 8/12 tin dòng tiền.

### 5.2 H2 — câu hỏi (B2, B3)

- **B2:** cả 100 câu nói đúng và đủ ràng buộc vàng. Wilson [0,963; 1].
- **B3:** độ tự nhiên trung bình 4,33. Theo phong cách: S1 4,20; S2 3,96; S3 4,88; S4 4,28.
- 7 câu chỉ được 3 điểm, vì:
  - câu hội thoại dồn nhiều ràng buộc liền nhau, không ngắt câu, ví dụ "… giá loanh quanh bốn tỷ rưỡi tối thiểu
    hai phòng ngủ với ạ";
  - số lớn viết bằng chữ ("năm mươi mét vuông", "mười sáu tỷ");
  - vài tổ hợp lạ do tin hạt giống thật có giá lạ, ví dụ "Quận Phú Nhuận nhà riêng quanh 350 tỷ".

### 5.3 H3 — nhãn 0–3 (A4)

κ có trọng số bậc hai là 0,941; 125/131 cặp khớp hẳn. Bảng nhầm lẫn, hàng là người chấm, cột là nhãn tự động:

| người \ máy | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| 0 | 59 | 0 | 2 | 1 |
| 1 | 0 | 20 | 0 | 0 |
| 2 | 1 | 0 | 19 | 2 |
| 3 | 0 | 0 | 0 | 27 |

Điểm trung bình người chấm cho theo từng tầng mẫu:

| Tầng mẫu | Điểm trung bình |
|---|---|
| mức 3 | 2,83 |
| mức 2 | 1,81 |
| mức 1 | 1,00 |
| mức 0 cùng khu vực | 0,07 |
| mức 0 được BM25 xếp cao | 0,00 |

Tỉ lệ âm tính giả (máy chấm 0, người chấm ≥ 2) là 1/60 = 1,7%, Wilson [0,3%; 8,9%].

Sáu cặp lệch có ba nguyên nhân:

| Nguyên nhân | Cặp | Máy → người |
|---|---|---|
| **Phân loại thô:** "nhà riêng / nhà" được hiểu là cả nhóm `Nhà đất`, gồm shophouse và biệt thự | shophouse cho câu "nhà riêng"; shophouse khối đế chung cư cho câu "nhà ≥ 245 m²" (264,5 m² là diện tích sử dụng); biệt thự 8×16 m cho câu "nhà phố" | 2 → 0; 3 → 0; 3 → 2 |
| **Quy ước của giao thức** | "gần ĐHQG" không ghi số: giao thức cho bán kính 3 km, người thấy 2,85 km là hơi xa. Tin không ghi giá: giao thức coi là không thoả, người chấm 2 | 3 → 2; 0 → 2 |
| **Lỗi dữ liệu** | tin 42009237: trường giá là 2 tỷ, nhưng đó là tiền "nhận nhà"; mô tả ghi "Giá: 9 tỷ" | 2 → 0 |

### 5.4 H4 — ưu tiên phường (A5)

Người chấm chọn tin trong phường ở 40/60 cặp, tức 0,667, Wilson [0,541; 0,773], p một phía = 0,0067. Tỉ lệ này
có ý nghĩa thống kê nhưng dưới ngưỡng 0,70, nên **không đạt**.

Kết quả này nằm **sát ngưỡng**. Bỏ 12 cặp có tin nằm trong danh sách `lf_dev` (mục 5.7) thì còn 34/48 = 0,708.
Khoảng tin cậy rộng, nên kết quả của người chấm có thể rơi vào bên nào của ngưỡng cũng được.

Phân rã theo ràng buộc mà tin trong phường bị lệch (cột `in_ward_off` của khoá; đây là phân tích thăm dò):

| Tin trong phường lệch ở | Chọn tin trong phường |
|---|---|
| giá thấp hơn mức "khoảng" (`price_under`) | 8/8 |
| thừa một phòng ngủ (`beds_extra`) | 8/8 |
| hơi xa tiện ích hoặc địa danh (`distance`) | 8/9 |
| giá vượt ngân sách (`price_over`) | 16/28 |
| thiếu một phòng ngủ (`beds_short`) | 0/5 |
| diện tích hơi nhỏ (`area_short`) | 0/2 |

Cách đọc: ưu tiên phường đứng vững khi tin trong phường chỉ lệch theo hướng có lợi hoặc vô hại, như rẻ hơn, thừa
phòng, xa thêm một chút. Ưu tiên này mất khi tin trong phường vượt ngân sách, thiếu phòng hay thiếu diện tích. Ngân
sách và kích thước tối thiểu được người mua coi gần như ràng buộc cứng.

Nếu người chấm cũng ra kết quả như vậy:

- **v2:** áp dụng đúng luật dự phòng đã đăng ký: `--grade-policy near_first` cho thước đo chính, và báo cáo cả hai.
- **v2.1 (đề xuất):** một quy tắc xếp mức theo loại lệch có thể hợp người dùng hơn. Quy tắc đó phải được đăng ký
  lại và kiểm trên mẫu mới. Không được chọn nó dựa trên chính mẫu H4 này.

### 5.5 H5 — sửa giá (A6)

Cả 60/60 sửa đổi đều đúng:

- R1 (khôi phục giá): 40/40;
- R2 (xoá giá): 13/13;
- thủ công: 7/7.

Một ca ranh giới: tin ghi 4,95 tỷ và có câu "chốt 4 tỷ 600". Trợ lý chấm đúng, vì giá niêm yết là 4,95 tỷ.

### 5.6 Lỗi dữ liệu và hàm gán nhãn phát hiện thêm (ghi lại, không sửa sau đóng băng)

| Tin | Vấn đề | Đã được giao thức xử lý? |
|---|---|---|
| 46111539 | nhãn Phường Tân Sơn Nhất, toạ độ ở khu Bình Tây | có, cờ `ward_coord_outlier` (D5 cho τ = 1) |
| 46176934 | tin đường Tam Bình, nhãn Phường An Khánh | có, cờ `ward_coord_outlier` |
| 45835007 | tin đường Ngô Đức Kế, nhãn Phường Bình Thạnh, toạ độ ở quận 1 cũ | có, cờ `ward_coord_outlier` |
| 42009237 | trường giá là tiền "nhận nhà" (2 tỷ); giá bán ghi trong mô tả là 9 tỷ | không. Errata v3.1 bỏ sót loại "giá mồi" này. H5 chỉ đo độ đúng của các sửa đổi, không đo độ sót |
| 44440279 | "sát HXH" bị gán hẻm xe hơi | không. Phủ định có "sát hẻm xe hơi" nhưng chưa có dạng viết tắt "sát HXH", nên hàm gán nhãn cho dương tính giả |

### 5.7 Mức trùng giữa kit và danh sách `lf_dev`

Danh sách `lf_dev` (990 tin, PROTOCOL 9.7) được lấy rộng: gồm mọi tin có mặt trong đầu ra phát triển, kể cả những
tin chỉ nằm trong file mà trợ lý có thể chưa đọc hết. Mức trùng với từng bộ:

| Bộ | Trùng với `lf_dev` | Ghi chú |
|---|---|---|
| H1 | 0 | đã rút lại ở PROTOCOL 9.7 |
| H3 | 24/131 tin | 5 tin thuộc câu hỏi có đặc điểm, nơi hàm gán nhãn ảnh hưởng tới nhãn |
| H4 | 12/60 cặp | 2 cặp thuộc câu hỏi có đặc điểm |
| H5 | 17/60 tin | xem đoạn dưới |

Nhãn 0–3 không được chỉnh dựa trên H3 hay H4. `analyze_human.py` vẫn báo cáo thêm kết quả khi bỏ các tin này, chỉ
để thăm dò. Trên bản tự kiểm:

- A4 khi bỏ các tin này có κ = 0,939, với n = 107;
- A5 khi bỏ các cặp này là 0,708 (mục 5.4).

H5 được rút từ tập sửa đổi mà trợ lý đã đọc **toàn bộ** khi rà errata (PROTOCOL 9.4). Vì vậy A6 đo tỉ lệ lỗi
**còn sót** sau lần rà đó, theo đánh giá của người.

## 6. Việc còn lại: chấm bằng người

1. Tốt nhất có **hai người chấm độc lập**. Mỗi người mở `human/annotate.html` và làm 5 file trong `human/tasks/`
   theo `human/GUIDELINES.md`, mất khoảng 4,5 giờ. Hai người không trao đổi trước khi cả hai xuất file.
2. Chép các file `answers_<task>_<tên>.csv` vào `human/answers/`. **Không** chép file của AI ở
   `human/answers_preaudit/`.
3. Chạy `python human/analyze_human.py`. Kết quả nằm ở `human/REPORT.md` và `human/report.json`, gồm κ giữa hai
   người.
   - Khi gần như mọi câu trả lời cùng một đáp án, như H2 và H5, κ có thể gần 0 dù hai người khớp nhau gần hết.
     Đây là nghịch lý κ khi phân phối lệch.
   - Vì vậy hãy đọc κ cùng với tỉ lệ khớp thô (`raw_agreement`).
4. Áp dụng luật quyết định đã đăng ký:

   | Phép kiểm không đạt | Việc phải làm |
   |---|---|
   | A2 | Loại đặc điểm sai > 3/12 khỏi F4 và sinh lại F4 |
   | A4 hoặc A6 | Chưa dùng bộ dữ liệu để báo cáo. Sửa nhãn hoặc errata, rồi kiểm lại trên mẫu mới |
   | A5 | Dùng `--grade-policy near_first` cho thước đo chính và báo cáo cả hai |
   | B2 | Sửa bộ sinh câu, rồi kiểm lại trên mẫu mới |

5. Ghi kết quả và mọi quyết định vào `PROTOCOL.md` mục 9 và vào file này.

## 7. Giới hạn đã biết

- **Phân loại loại nhà còn thô.** "Nhà riêng / nhà phố / nhà" đều ứng với cả nhóm `Nhà đất`, gồm shophouse và biệt
  thự (mục 5.3).
- **Tin không ghi giá luôn trượt ràng buộc giá.** Đây là lựa chọn của giao thức. Người chấm có thể khoan dung hơn.
- **Độ sót của hàm gán nhãn** dồn vào "hẻm xe hơi" và "nhà mới" (mục 5.1). Điều này làm tăng âm tính giả ở các câu
  F4 có hai đặc điểm đó.
- **Lỗi trong chính tin đăng**, như nhãn phường hay giá mồi, đi thẳng vào nhãn. Cờ `ward_coord_outlier` và phép D5
  đo được một phần lỗi phường.
- **Danh sách `lf_dev` chỉ là cố gắng tối đa.** Nhật ký của một phần buổi phát triển không còn đầy đủ (PROTOCOL
  9.7), nên danh sách này có thể sót một số tin.
- **Tự kiểm của AI không thay người chấm.** Xem đầu mục 5.
- **Bản sao nhánh Neo4j chưa được đối chiếu với Neo4j thật** (mục 4.3).
