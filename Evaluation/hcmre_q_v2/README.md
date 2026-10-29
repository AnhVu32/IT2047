# HCMRE-Q v2 — benchmark tìm kiếm BĐS theo phường mới, trên toàn bộ dữ liệu v3

Bộ đánh giá độc lập cho hệ thống tìm kiếm của IT2047. Gồm:

- 1.000 câu tìm kiếm tiếng Việt;
- nhãn liên quan 0–3 cho **cả 6.703 tin** của `Data/v3`;
- quy trình đánh giá chính bộ dữ liệu (meta-evaluation).

Bản v1 nằm ở `../hcmre_q/` (3.037 tin cũ, nhãn 0–2) và được giữ nguyên để so sánh.

| Tài liệu | Nội dung |
|---|---|
| [`HUONG_DAN_CHAY.md`](HUONG_DAN_CHAY.md) | **Hướng dẫn chạy từng bước cho người mới**: cài đặt, lệnh, thời gian, đọc kết quả, lỗi thường gặp |
| [`PROTOCOL.md`](PROTOCOL.md) | Giao thức đăng ký trước khi sinh dữ liệu: định nghĩa nhãn, thước đo, các phép kiểm định và ngưỡng đạt, nhật ký sai lệch |
| [`DATASET_CARD.md`](DATASET_CARD.md) | Mô tả bộ dữ liệu: thành phần, thống kê, cách dùng đúng, giới hạn, hash |
| [`META_EVAL.md`](META_EVAL.md) | Kết quả đánh giá chính bộ dữ liệu: tự động, độ tin cậy, tự kiểm của trợ lý AI, phần chờ người chấm |
| [`human/GUIDELINES.md`](human/GUIDELINES.md) | Hướng dẫn chấm tay H1–H5 |

## Khác gì v1

| | v1 (`hcmre_q/`) | v2 (thư mục này) |
|---|---|---|
| Kho tin | 3.037 tin cũ | 6.703 tin `Data/v3` sau errata v3.1 (cũ + crawl 2026) |
| `doc_id` | `properties.id` (đổi khi nạp lại DB) | `listing_id` (ổn định) |
| Vị trí | trộn phường/quận | **ưu tiên phường mới**. 70% câu nêu phường; tên phường trùng tên quận cũ luôn có tiền tố |
| Nhãn | 0/1/2 | 0–3: đúng phường > đúng phường lệch nhẹ > **sát** phường (≤ 1 km) > không liên quan |
| Kiểm định bộ dữ liệu | 96 mẫu đặc điểm do AI chấm | giao thức đăng ký trước, 13 phép kiểm tự động, bộ chấm tay H1–H5 (mù, tách khỏi mẫu phát triển) có ngưỡng đạt |

## Chạy lại từ đầu

Cần Python ≥ 3.10 và `pip install -r requirements.txt`. Hướng dẫn chi tiết từng bước: [`HUONG_DAN_CHAY.md`](HUONG_DAN_CHAY.md).

```bash
# 0) dữ liệu v3.1 — chạy MỘT lần ở gốc repo (sửa tại chỗ, không có mạng)
python Data/v3/pipeline/fix_v3_quality.py            # chạy thử: chỉ ghi báo cáo
python Data/v3/pipeline/fix_v3_quality.py --apply    # sửa master_v3.csv, postgres/, graph/

cd Evaluation/hcmre_q_v2
python build_benchmark.py --out data                 # 1.000 câu + qrels (seed cố định)
python check_labels.py --data data                   # A1: chấm lại độc lập, phải khớp 100%
python meta_eval.py --data data --out results/meta_eval.json     # B1, B4, C1–C4, E1
python make_snapshot.py --dsn postgresql://USER:PASS@HOST:PORT/DB   # điểm full-text của PostgreSQL
python eval_benchmark.py --data data --snapshot snapshot --out results   # hệ thống offline + D1–D5
python human/make_samples.py                         # bộ chấm tay H1–H5
python explain_qrels.py                              # lý do của từng nhãn -> data/qrels_explained.csv
```

Mọi script in tiến độ kèm thời gian còn lại, và tự ghi log vào `logs/<script>_<ngày-giờ>.log`. Đầu log có lệnh,
phiên bản Python, commit git và hash dữ liệu vào; dòng cuối là `OK` hoặc `FAILED` cùng thời gian chạy
(`runlog.py`; đặt `HCMRE_NO_LOG=1` để tắt ghi file). Log chỉ thêm thông báo, không đổi file kết quả nào.

Kết quả nằm trong `results/`:

- `summary.json` (theo tập, họ, phong cách, loại vị trí, khoảng tin cậy);
- `per_query_metrics.csv`;
- `reliability.json` (D1–D5);
- `meta_eval.json`;
- `runs.jsonl.gz`.

`make_snapshot.py` cần một PostgreSQL bất kỳ, ví dụ DB trong docker-compose. Script tạo bảng tạm, tính điểm rồi
tự xoá. `snapshot/fts_scores.csv` đã được tính sẵn nên có thể bỏ qua bước này.

Mọi file đầu ra đều tái lập được tới từng byte. Bộ sinh không phụ thuộc hash seed (phép kiểm E1), còn
`eval_benchmark.py` tự chạy với `PYTHONHASHSEED=0`. Hash để so nằm trong `DATASET_CARD.md` mục 7.

## Đánh giá hệ thống thật (phần Deep Learning)

Hai cách, bổ sung cho nhau. Cả hai đã được đối chiếu với backend chạy thật (`META_EVAL.md` mục 4.3).

**(a) Offline, với vector của model embedding.** Chạy trên máy có LM Studio:

```bash
python embed_benchmark.py --model qwen/qwen3-embedding-4b --dimensions 1024 --corpus
#   hoặc lấy đúng vector tài liệu backend đang tìm (DB ở v3.1, đã chạy build_search_index.py) — nên dùng khi so với live:
python embed_benchmark.py --model qwen/qwen3-embedding-4b --dimensions 1024 --doc-vectors-from-db postgresql://...
python eval_benchmark.py --embedding-tag qwen3-embedding-4b --out results_dl
```

Lệnh trên thêm các hệ thống `dense`, `prod_dl`, `prod_dl_graph`, `rrf_bm25_dense` vào bảng kết quả và vào các phép
kiểm D2–D5. Ghi ra `results_dl/` để `results/` giữ đúng bản đã công bố. Vector được lưu dạng float32, và mỗi câu
hỏi được gửi một request, giống backend.

**(b) Live, gọi thẳng API đang chạy.** Hệ thống được đo đúng như khi triển khai, gồm LLM parser nếu có cấu hình,
embedding, Neo4j và ranker:

```bash
python run_live.py --base-url http://localhost:8001 --split test --out results/live_test \
    --offline results_dl/per_query_metrics.csv
```

Mỗi cấu hình backend cần một thư mục `--out` riêng. Câu trả lời được lưu đệm trong đó, nên một lần chạy bị ngắt sẽ
chạy tiếp từ chỗ dừng.

Trước khi chạy live, cơ sở dữ liệu phải ở v3.1. Nếu không, nhãn và dữ liệu hệ thống thấy sẽ khác nhau:

```bash
psql -d real_estate -f Data/v3/patches/v3_1_postgres.sql
docker compose exec backend python scripts/build_search_index.py --skip-catalog-import --skip-graph-metadata
cypher-shell -f Data/v3/patches/v3_1_neo4j.cypher      # hoặc nạp lại graph từ Data/v3/graph/
```

**Live khớp với bản sao offline nào.** `run_live.py` tự nhận ra cấu hình từ câu trả lời của API:

| Semantic search (embedding phủ 100%) | Neo4j (`SEARCH_USE_NEO4J`) | Bản sao offline |
|---|---|---|
| tắt | tắt | `prod_nodl` |
| tắt | bật | `prod_nodl_graph` |
| bật | tắt | `prod_dl` |
| bật | bật | `prod_dl_graph` |

Nếu cạnh file `--offline` có `runs.jsonl.gz`, script so từng bảng xếp hạng live với mọi hệ thống offline. Kết quả
nằm trong `summary.json`, ở `matching_offline_replica` và `replica_fidelity`. Khi dữ liệu, vector và ngày như nhau,
bản sao đúng phải trùng top-10 ở gần như mọi câu. Phép so chỉ có nghĩa khi `SEARCH_USE_LLM_PARSER=false`, vì bản
sao dùng parser luật. Nếu trùng dưới 95%, kiểm theo thứ tự:

1. **Ngày.** `freshness_score` dùng ngày hiện tại của máy chủ. Chạy lại offline với ngày của lần chạy live (ghi ở
   `run_dates`): `python eval_benchmark.py --embedding-tag ... --today 2026-11-05 --out results_dl_1105`.
2. **Vector.** Dùng `--doc-vectors-from-db` để có đúng vector tài liệu trong DB. Cho `--model` và `--dimensions`
   giống `SEARCH_EMBEDDING_MODEL` và `SEARCH_EMBEDDING_REQUEST_DIMENSIONS` trong `.env` của backend
   (`--dimensions 0` nếu biến này không đặt), để câu hỏi được mã hoá đúng như backend làm.
3. **Dữ liệu.** DB phải ở v3.1. Script cảnh báo khi API trả về `listing_id` lạ.
4. **Hoà điểm trong thứ tự ứng viên.** Khi tắt embedding, backend lấy 500 ứng viên theo `created_at`. Nếu cả bảng
   được nạp bằng một lệnh, mọi tin có cùng `created_at` và PostgreSQL trả 500 tin tuỳ ý. Bản sao giả định
   `created_at` tăng theo thứ tự dòng của `properties_v3.csv`, tức theo `listing_id` tăng dần. Trên một **bản sao
   DB dùng để đánh giá**, không phải DB production, có thể đặt lại cho khớp:

   ```sql
   UPDATE properties p SET created_at = timestamp '2026-01-01' + o.rnk * interval '1 second'
   FROM (SELECT id, row_number() OVER (ORDER BY listing_id) AS rnk FROM properties) o
   WHERE o.id = p.id;
   ```

   Neo4j có vấn đề tương tự: Cypher lấy 500 tin theo `posted_date` mà không có khoá phụ.

`run_live.py` cũng cảnh báo nếu:

- semantic search bị tắt (độ phủ embedding < 100%), hoặc cấu hình đổi giữa chừng;
- chính sách mức hay ngày khác với kết quả offline đem so.

## Giải thích nhãn và phân tích lỗi

`explain_qrels.py` tính lại mức của một cặp (câu hỏi, tin) theo từng ràng buộc, bằng chính các hàm của
`check_labels.py`, và dừng nếu kết quả khác `qrels.tsv`:

```bash
python explain_qrels.py                                            # mọi cặp mức 1–3 -> data/qrels_explained.csv
python explain_qrels.py --qid v2q0001                              # một câu, in ra màn hình
python explain_qrels.py --qid v2q0801 --listing 46361337           # một cặp bất kỳ, kể cả mức 0
python explain_qrels.py --run results/runs.jsonl.gz --system bm25_rule --k 10   # vì sao top-10 của một hệ thống sai
python explain_qrels.py --run results/live_test/responses.jsonl --k 10          # như trên, cho kết quả live
```

Mỗi dòng có cột `ly_do`, ví dụ "mức 2: trong Phường Cát Lái, lệch nhẹ 1 ràng buộc — Căn hộ ✓; giá 8 tỷ (hỏi
9–12 tỷ): lệch nhẹ; 2 PN (hỏi đúng 2 PN): đạt", cùng các cột giá trị thật, giá trị hỏi và trạng thái của từng ràng
buộc, khoảng cách tới khu vực, và đoạn văn khớp đặc điểm. Chế độ `--run` còn đếm lý do các kết quả mức 0 bị sai
(ngoài khu vực, trượt giá, sai loại nhà, …).

## Kiểm định bằng người

1. Mở `human/annotate.html` và chấm 5 file trong `human/tasks/` theo `human/GUIDELINES.md`. Tốt nhất có hai người
   chấm độc lập.
2. Chép file kết quả xuất ra vào `human/answers/`.
3. Chạy `python human/analyze_human.py`.

Kết quả và kết luận đạt/không đạt theo ngưỡng của `PROTOCOL.md` mục 7 nằm ở `human/REPORT.md`.

`human/answers_preaudit/` chứa bản **tự kiểm của trợ lý AI**. Bản này chỉ là dự báo tạm thời, báo cáo của nó nằm ở
`human/preaudit_report/`. Không chép các file này vào `human/answers/`. Để chạy lại báo cáo tự kiểm:

```bash
python human/analyze_human.py --answers human/answers_preaudit --out human/preaudit_report \
    --title "TIỀN KIỂM ĐỊNH BỞI AI (claude-preaudit) — tạm thời, KHÔNG thay thế người chấm"
```

## Báo cáo kết quả thế nào cho đúng

- **Thước đo chính:** nDCG@10 trên **tập test** (200 câu), kèm khoảng tin cậy 95% và kiểm định hoán vị ghép cặp
  khi so hai hệ thống.
- **Chính sách mức.** Mặc định là `ward_first`: tin trong phường lệch nhẹ (mức 2) xếp trên tin sát phường thoả
  hết (mức 1). Nếu phép kiểm A5 bằng người không đạt, thước đo chính chuyển sang `near_first`, và báo cáo cả hai:

  ```bash
  python eval_benchmark.py --grade-policy near_first --out results_near_first
  python run_live.py --grade-policy near_first --offline results_near_first/per_query_metrics.csv --out results/live_test_near_first
  ```

- **Chỉ dùng train/val để chỉnh tham số.** Không chỉnh trên test. Khung câu của test không xuất hiện ở train/val.
- Không trộn kết quả v1 và v2. Hai bản có kho tin, thang nhãn và định nghĩa vị trí khác nhau.
