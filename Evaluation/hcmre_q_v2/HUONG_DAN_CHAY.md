# Hướng dẫn chạy HCMRE-Q v2 cho người mới

File này hướng dẫn từng bước, từ máy chưa cài gì đến lúc có bảng kết quả. Phần giải thích phương pháp nằm ở
`README.md`, `PROTOCOL.md` và `META_EVAL.md`. Ở đây chỉ có cách chạy.

## 0. Bạn cần chạy tới đâu?

| Mức | Mục đích | Cần gì | Thời gian |
|---|---|---|---|
| **A. Xem kết quả có sẵn** | đọc số liệu, xem nhãn, xem lý do | không cần chạy gì | — |
| **B. Chạy lại offline** | tái lập bảng kết quả, so hệ thống mới với các baseline | Python | 5–10 phút |
| **C. Hệ thống thật** | đo phần Deep Learning và API đang chạy | B, cộng LM Studio, Docker (PostgreSQL, Neo4j, backend) | 15–30 phút |

Mọi lệnh dưới đây chạy trong thư mục `Evaluation/hcmre_q_v2` của repo, trừ khi ghi khác.

## 1. Mức A — xem dữ liệu và kết quả có sẵn

| Muốn xem | Mở file |
|---|---|
| 1.000 câu hỏi và ràng buộc vàng | `data/queries.jsonl` (mỗi dòng một JSON; mở bằng VS Code) |
| Nhãn: tin nào đúng với câu nào, mức 1–3 | `data/qrels.tsv`: `qid  0  listing_id  mức`. Cặp không có dòng là mức 0 |
| **Vì sao** mỗi tin được mức đó | `data/qrels_explained.csv` (mở bằng Excel; tạo ở bước 3.5 nếu chưa có) |
| Thuộc tính của 6.703 tin dùng để gán nhãn | `data/corpus_attributes.csv` |
| Bảng điểm các hệ thống | `results/summary.json`, mục `"test"` |
| Điểm từng câu | `results/per_query_metrics.csv` |
| Top-100 của từng hệ thống cho từng câu | `results/runs.jsonl.gz` |
| Kết quả kiểm định bộ dữ liệu | `META_EVAL.md` |

## 2. Cài đặt (một lần)

Cần Python 3.10 trở lên (khuyên dùng 3.11+) và repo đã có dữ liệu v3.1.

```bash
cd Evaluation/hcmre_q_v2
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Trên Windows, gõ `python` thay cho `python3`.

**Kiểm tra dữ liệu đã ở v3.1.** `build_benchmark.py` tự dừng nếu sai. Muốn kiểm trước:

```bash
python3 -c "import corpus; print(corpus.sha256(corpus.V3 / 'master_v3.csv')[:12])"
```

Kết quả phải là `5b65c94dabd2`. Nếu khác, ở **gốc repo** chạy:

```bash
python Data/v3/pipeline/fix_v3_quality.py --apply
```

## 3. Mức B — chạy lại offline

Mỗi lệnh in tiến độ ra màn hình, kèm thời gian còn lại, và tự ghi log vào `logs/<tên script>_<ngày-giờ>.log`.
Dòng cuối của log là `OK` hoặc `FAILED`, kèm thời gian chạy. Đầu log ghi lệnh đã chạy, phiên bản Python, commit git
và hash của dữ liệu vào. Nhờ vậy luôn biết một kết quả đến từ lần chạy nào.

| Bước | Lệnh | Làm gì | Thời gian | Đầu ra |
|---|---|---|---|---|
| 3.1 | `python3 build_benchmark.py --out data` | sinh 1.000 câu và nhãn của mọi cặp (seed cố định) | khoảng 1 phút | `data/` |
| 3.2 | `python3 check_labels.py` | A1: chấm lại độc lập mọi cặp; phải in `A1 passed` | 30–60 giây | màn hình |
| 3.3 | `python3 meta_eval.py` | các phép kiểm B1, B4, C1–C4, E1 | 1–2 phút | `results/meta_eval.json` |
| 3.4 | `python3 eval_benchmark.py --out results` | chạy 9 hệ thống, metric, kiểm định D1–D5 | 3–5 phút | `results/` |
| 3.5 | `python3 explain_qrels.py` | giải thích từng nhãn | khoảng 1 phút | `data/qrels_explained.csv` |

Bước 3.1 và 3.3 chỉ cần khi muốn tái lập bộ dữ liệu. Dữ liệu đã có sẵn trong `data/`, nên muốn chấm một hệ thống thì
có thể bắt đầu từ bước 3.4.

Có thể bỏ E1 cho nhanh: `python3 meta_eval.py --skip-determinism`.

**Kiểm tra đã tái lập đúng.** So hash các file với `DATASET_CARD.md` mục 7:

```bash
shasum -a 256 data/*.jsonl data/*.tsv results/summary.json results/per_query_metrics.csv   # Linux: sha256sum
```

Nếu dùng phiên bản thư viện khác bản ghi trong mục 7, hash có thể lệch ở số rất nhỏ. Khi đó hãy dựa vào
`A1 passed` và so metric, không so hash.

**Đọc kết quả.** Mở `results/summary.json`, mục `"test"`: mỗi hệ thống có `ndcg@10` (thước đo chính), `p@10`,
`mrr@10`, `success@10`, `recall@100`, `wardp@10`. Khoảng tin cậy nằm ở `test_ndcg_ci95`. Hai hệ thống có khác nhau
thật không thì xem `reliability.json` → `D2_discriminative_power` → `p_holm` (khác nhau có ý nghĩa nếu < 0,05).

## 4. Mức C — hệ thống thật (Deep Learning)

### 4.1 Chuẩn bị backend và dữ liệu

1. Chạy LM Studio, nạp model `qwen/qwen3-embedding-4b`, bật server (mặc định `http://127.0.0.1:1234/v1`).
2. Ở gốc repo, khởi động các dịch vụ:

   ```bash
   docker compose build backend      # cần sau lần sửa backend/requirements.txt ngày 29/10
   docker compose up -d
   ```

3. Đưa DB lên v3.1 (chỉ một lần), rồi tạo lại `search_text` và vector cho các tin vừa sửa:

   ```bash
   psql -h localhost -p 5433 -U postgres -d real_estate -f Data/v3/patches/v3_1_postgres.sql
   docker compose exec backend python scripts/build_search_index.py --skip-catalog-import --skip-graph-metadata
   cypher-shell -f Data/v3/patches/v3_1_neo4j.cypher
   ```

4. Kiểm tra API: `curl -s -X POST localhost:8001/v1/search -H 'Content-Type: application/json' -d '{"query":"căn hộ 2 phòng ngủ quận 7","top_k":5}'`
   phải trả về JSON có `"semantic_enabled": true`.

Để so với bản sao offline, `.env` cần `SEARCH_USE_LLM_PARSER=false`.

### 4.2 Ba lệnh chạy

Chạy cả ba trong **cùng một ngày**, vì ranker có điểm "độ mới" tính theo ngày chạy.

```bash
cd Evaluation/hcmre_q_v2
# (1) vector câu hỏi bằng model thật + vector tài liệu lấy thẳng từ DB
python3 embed_benchmark.py --model qwen/qwen3-embedding-4b --dimensions 1024 \
    --doc-vectors-from-db "postgresql://postgres:<mật khẩu>@localhost:5433/real_estate"
# (2) 13 hệ thống offline, gồm dense, prod_dl, prod_dl_graph, rrf_bm25_dense
python3 eval_benchmark.py --embedding-tag qwen3-embedding-4b --today $(date +%F) --out results_dl
# (3) gọi API thật cho 200 câu test, rồi so với kết quả offline
python3 run_live.py --base-url http://localhost:8001 --split test --out results/live_test \
    --offline results_dl/per_query_metrics.csv
```

- `--dimensions` phải giống `SEARCH_EMBEDDING_REQUEST_DIMENSIONS` trong `.env`; dùng `--dimensions 0` nếu biến đó
  không đặt.
- Trên Windows, thay `$(date +%F)` bằng ngày hôm nay dạng `2026-11-05`.
- Bước (3) lưu từng câu trả lời vào `results/live_test/responses.jsonl`. Nếu bị ngắt, chạy lại đúng lệnh đó sẽ chạy
  tiếp từ chỗ dừng. Mỗi cấu hình backend khác nhau cần một thư mục `--out` khác.

### 4.3 Đọc kết quả live

Trong log hoặc `results/live_test/summary.json`:

- `mean.ndcg@10`: điểm của hệ thống thật.
- `matching_offline_replica`: bản sao offline ứng với cấu hình đang chạy (`prod_dl_graph` nếu bật Neo4j).
- Dòng `replica check: ... identical top-10 on X/200 queries`. X ≥ 190 nghĩa là bản sao offline đúng là hệ thống
  thật, nên có thể dùng điểm offline của nó trong báo cáo. Nếu thấp hơn, xem README mục "Live khớp với bản sao
  offline nào".
- `vs_offline.p_holm`: live có khác từng hệ thống offline một cách có ý nghĩa không.

## 5. Phân tích lỗi: vì sao hệ thống trả về tin sai

```bash
python3 explain_qrels.py --run results_dl/runs.jsonl.gz --system prod_dl_graph --k 10
python3 explain_qrels.py --run results/live_test/responses.jsonl --k 10       # kết quả live
python3 explain_qrels.py --qid v2q0801 --listing 46361337                      # một cặp bất kỳ
```

Lệnh đầu in tỉ lệ mức 3/2/1/0 trong top-10 và đếm lý do các tin mức 0 sai: ngoài khu vực, trượt giá, sai loại
nhà, thiếu đặc điểm, … Chi tiết từng tin nằm trong `results_dl/explained_prod_dl_graph_top10.csv`.

## 6. Lỗi thường gặp

| Hiện tượng | Nguyên nhân và cách sửa |
|---|---|
| `master_v3.csv is not v3.1` | chạy `fix_v3_quality.py --apply` ở gốc repo (mục 2) |
| `ModuleNotFoundError` | chưa kích hoạt venv, hoặc chưa `pip install -r requirements.txt` |
| `A1 FAILED` | dữ liệu hoặc code nhãn bị sửa; so hash với `DATASET_CARD.md` |
| `embed_benchmark.py`: kết nối bị từ chối | LM Studio chưa bật server, hoặc sai `--base-url` |
| `query vectors have X dimensions, document vectors Y` | `--dimensions` khác với cấu hình backend |
| `run_live.py`: `request failed` | backend chưa chạy hoặc sai cổng (mặc định 8001); sửa rồi chạy lại cùng lệnh để chạy tiếp |
| `WARNING: semantic search was OFF` | vector trong DB chưa đủ 100%; chạy lại `build_search_index.py` |
| `WARNING: ... listing_ids are not in the benchmark corpus` | DB chưa ở v3.1 (mục 4.1 bước 3) |
| `NOTE: offline replicas ran with --today ...` | chạy lại bước (2) với ngày của lần chạy live |
| Không biết lần chạy đã xong chưa | xem file mới nhất trong `logs/`: dòng cuối là `OK` / `FAILED` |

## 7. Những điều không được làm

- Không chỉnh tham số hệ thống dựa trên tập **test**. Chỉ dùng train/val.
- Không sửa `data/qrels.tsv` hay hàm gán nhãn. Mọi thay đổi phải ghi vào `PROTOCOL.md` mục 9 và tạo phiên bản mới.
- Không chép file trong `human/answers_preaudit/` vào `human/answers/`. Đó là bản tự kiểm của AI, không phải người chấm.
- Không ghi kết quả có embedding vào `results/`. Dùng `results_dl/` để `results/` giữ đúng bản đã công bố.
