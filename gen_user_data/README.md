# gen_user_data — Sinh dữ liệu mô phỏng (KG) & Đánh giá Hệ gợi ý BĐS

Bộ công cụ **sinh dữ liệu người dùng/tương tác mô phỏng** cho hệ thống gợi ý bất
động sản (giải bài toán *cold-start*), **map sang Knowledge Graph**, và **đánh giá**
bằng các metric chuẩn của ngành recommendation.

Triển khai theo `recsys_kg_rag_guide.md` (cùng thư mục). Đánh giá dùng **trực tiếp
thư viện metric** của repo
[aryan-jadon/Evaluation-Metrics-for-Recommendation-Systems](https://github.com/aryan-jadon/Evaluation-Metrics-for-Recommendation-Systems)
(bundle thư viện Microsoft `recommenders`).

---

## 1. Pipeline

```
Data/Final_Data.csv (listing THẬT) + embeddings.pkl (id + vector)
        │
        ▼
   catalog.py ───────────────► data/listings.json      (thuộc tính + địa chỉ THẬT)
                                      │
 generate_users.py ─────────► data/users.json          (ép phân phối 60/30/10)
                                      │
 generate_interactions.py ──► data/interactions.json   (tín hiệu ground-truth)
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        ▼                             ▼                              ▼
   kg/build_kg.py              run_eval.py                    export_csv.py
   nodes/edges.csv             (temporal split +              data/csv/*.csv
   import.cypher               sampled-negatives)                    │
        │                      metric từ repo clone           visualize_graph.py
        ▼                             │                        graph_viz.html
   Neo4j / DGL             data/eval_results.json
```

Mọi bước **tất định** (seed `RANDOM_SEED`) → chạy lại cho kết quả y hệt.

---

## 2. Cài đặt & chạy nhanh

### 2.1. Phụ thuộc

```bash
pip install -r requirements.txt      # numpy, pandas, pydantic, networkx, scikit-learn
```

### 2.2. Clone repo metric (một lần, tuỳ chọn)

```bash
# đứng ở gốc dự án (CS2307/)
git clone https://github.com/aryan-jadon/Evaluation-Metrics-for-Recommendation-Systems.git
```

`run_eval.py` tự tìm repo tại `../Evaluation-Metrics-for-Recommendation-Systems`
và gọi `recommenders.evaluation.python_evaluation`. **Nếu chưa clone → tự fallback**
sang module `metrics/` nội bộ (cùng công thức). Chỉ cần `numpy/pandas/sklearn` để
dùng các hàm metric — **không** cần Spark/TF/torch (chỉ phục vụ benchmark MovieLens
của repo, không dùng ở đây).

### 2.3. Chạy toàn bộ

```bash
cd gen_user_data
python generate_all.py         # 1) listings + users + interactions + KG
python run_eval.py             # 2) NDCG/MRR/HitRate/Recall/Precision/MAP @10
python export_csv.py           # 3) xuất data/csv/*.csv (Excel/BI)
python visualize_graph.py      # 4) -> graph_viz.html (mở bằng trình duyệt)
python tests/test_metrics.py   #    kiểm chứng metric (6/6 PASS)
python tests/test_load_all.py  #    kiểm chứng loader (6/6 PASS)
```

### 2.4. Bật LLM sinh văn bản (tuỳ chọn — Groq)

Mặc định pipeline chạy **offline** bằng template + RNG. Nếu muốn văn bản tự nhiên
hơn, bật LLM — **RNG vẫn kiểm soát toàn bộ phân phối/nhãn**, LLM chỉ lo phần chữ:

| Trường | Khi TẮT (mặc định) | Khi BẬT LLM |
|---|---|---|
| `interactions.raw_query` | câu ghép từ template | câu tìm kiếm tự nhiên do LLM sinh |
| `users.persona` | `null` | "bio" ngắn mô tả nhu cầu khách |
| `listings.description` | `null` | mô tả tin đăng (đúng dữ liệu, không bịa tiện ích) |

Cấu hình qua `.env` (gốc dự án — script tự nạp) hoặc `export`:

```bash
USE_LLM=1
LLM_PROVIDER=groq                 # groq | grok | openai (đều tương thích OpenAI API)
GROQ_API_KEY=gsk_...              # https://console.groq.com/keys
# LLM_MODEL=llama-3.3-70b-versatile   # tuỳ chọn
# LLM_MAX_LISTINGS_DESC=150           # số listing sinh description (0 = tắt)
```

Cần cài `openai` (đã có trong `requirements.txt`). Đổi provider chỉ bằng đổi
`LLM_PROVIDER`/`LLM_MODEL`/key — client **provider-agnostic** (OpenAI-compatible).
Mọi lời gọi LLM đều **batch** (tiết kiệm token) và **fallback template** nếu lỗi →
không bao giờ làm hỏng pipeline. Bật hay tắt, dữ liệu vẫn hợp lệ cùng một schema.

### 2.5. Công thức thường dùng (recipes)

| Tôi muốn… | Làm gì |
|---|---|
| Sinh lại **N user** (vd 300) | Sửa `NUM_USERS=300` trong `config/distribution_config.py` → `python generate_all.py` |
| Đổi **số interaction/user** | Sửa `INTERACTIONS_PER_USER_LAMBDA` + `MIN/MAX_INTERACTIONS_PER_USER` |
| Đổi **tỷ lệ phân khúc/intent** | Sửa `BUDGET_SEGMENTS` / `INTENT_WEIGHTS` |
| **Bật LLM** sinh chữ | `.env`: `USE_LLM=1` + `GROQ_API_KEY=...` → `python generate_all.py` |
| **Nạp vào DB** để query SQL | `python load_all.py` → mở `data/warehouse.sqlite` |
| **Tính sẵn** cho query nhanh | `python precompute.py` → dùng `content_neighbors` / `popularity` / `query_expansion` |
| **Chấm điểm** recommender | `python run_eval.py` → `data/eval_results.json` |
| Xuất **CSV** cho Excel/BI | `python export_csv.py` → `data/csv/*.csv` |
| Xem **đồ thị** trực quan | `python visualize_graph.py` → mở `graph_viz.html` |
| Chạy **toàn bộ** một mạch | `generate_all.py` → `load_all.py` → `precompute.py` → `run_eval.py` |

**Truy vấn ví dụ trên warehouse** (sau `load_all.py`):
```python
import sqlite3
c = sqlite3.connect("data/warehouse.sqlite")
# top 20 BĐS tương tự listing 45222670 (đã precompute)
c.execute("SELECT neighbor_id, sim FROM pc_item_neighbor "
          "WHERE listing_id=45222670 ORDER BY rank LIMIT 5").fetchall()
# nới rộng truy vấn: near_school -> attribute liên quan
c.execute("SELECT related, weight FROM pc_query_expansion "
          "WHERE attr='near_school' ORDER BY weight DESC").fetchall()
```

---

## 3. Cấu trúc thư mục

```
gen_user_data/
├── recsys_kg_rag_guide.md          # tài liệu gốc (yêu cầu)
├── README.md                       # file này
├── work_log.html                   # nhật ký công việc + kết quả (mở bằng trình duyệt)
├── requirements.txt
│
├── config/
│   └── distribution_config.py      # MỌI tỷ lệ phân phối, seed, trọng số
├── schemas.py                      # Pydantic: Listing / UserProfile / Interaction
├── catalog.py                      # nạp listing THẬT từ Data/Final_Data.csv (địa chỉ sau sáp nhập)
│
├── generation/
│   ├── generate_users.py           # -> data/users.json
│   ├── generate_interactions.py    # -> data/interactions.json (+ hàm relevance())
│   ├── llm_client.py               # client LLM provider-agnostic (Groq) + QueryGenerator
│   └── enrich.py                   # (LLM) persona cho user, description cho listing
├── generate_all.py                 # driver: chạy cả 4 bước sinh + build KG
│
├── kg/
│   └── build_kg.py                 # -> data/kg/{nodes,edges}.csv + import.cypher
│
├── metrics/                        # bộ metric NỘI BỘ (đã test, dùng làm fallback)
│   ├── ranking.py                  # ndcg_at_k, mrr, average_precision, map_at_k
│   ├── retrieval.py                # hit_rate_at_k, recall_at_k, precision_at_k
│   └── similarity.py               # cosine, jaccard, euclidean, manhattan, pearson
├── eval_engine.py                  # adapter gọi TRỰC TIẾP metric của repo đã clone
├── run_eval.py                     # temporal split + 3 recommender + báo cáo
│
├── similarity_kg.py                # (task 1.3) ma trận similarity -> cạnh KG + KIỂM CHỨNG hành vi
├── load_all.py                     # (task 1.4) nạp SQLite (quan hệ) + graph stub NetworkX — IDEMPOTENT
├── precompute.py                   # tính sẵn artifact phục vụ query (neighbors, popularity, expansion...)
├── export_csv.py                   # JSON -> data/csv/*.csv
├── visualize_graph.py              # -> graph_viz.html (SVG tự-chứa, theme-aware)
├── tests/
│   ├── test_metrics.py             # unit test công thức metric
│   └── test_load_all.py            # test loader: derived, validate, dedup, idempotent, full-refresh
│
└── data/                           # (SINH RA bằng script; tái tạo: python generate_all.py)
    ├── listings.json  users.json  interactions.json  eval_results.json
    ├── similarity_validation.json  # báo cáo kiểm chứng declared vs hành vi
    ├── warehouse.sqlite            # (load_all.py + precompute.py) kho quan hệ — .gitignore
    ├── graph/kg_networkx.pkl       # (load_all.py) graph stub — .gitignore
    ├── precomputed/*.json          # (precompute.py) cache query-time — .gitignore
    ├── csv/           *.csv
    └── kg/            nodes.csv  edges.csv  import.cypher
                       similarity_edges.json           # declared (amenity + criteria)
                       location_similarity_edges.json  # từ hành vi (quận↔quận)
```

### 3.1. Bản đồ Input → Output theo script

Mỗi script là một **hàm thuần**: đọc file/nguồn cố định → ghi file cố định. Không có
trạng thái ẩn; chạy lại cho kết quả như nhau (seed).

| Script | INPUT | OUTPUT | Hàm chính |
|---|---|---|---|
| `catalog.py` | `Data/Final_Data.csv` (thật) + `embeddings.pkl` (lọc id) | `data/listings.json` | `build_catalog`, `derive_pools`, `assign_area_price_tier` |
| `generation/generate_users.py` | config | `data/users.json` | `generate_users` |
| `generation/generate_interactions.py` | users + listings (+ LLM nếu bật) | `data/interactions.json` | `generate_interactions`, `relevance` |
| `generation/llm_client.py` | `.env` (`USE_LLM`, key) | *(dịch vụ sinh chữ)* | `LLMClient`, `QueryGenerator` |
| `generation/enrich.py` | users/listings + LLM | `persona`/`description` (điền vào JSON) | `enrich_personas`, `enrich_descriptions` |
| `generate_all.py` | *(gọi các bước trên)* | listings/users/interactions + KG | `main` |
| `similarity_kg.py` | `knowledge.py` + `similarity_matrix_v2.py` + interactions | `similarity_edges.json`, `location_similarity_edges.json`, `similarity_validation.json` | `main` |
| `kg/build_kg.py` | users/listings/interactions + similarity edges | `kg/nodes.csv`, `edges.csv`, `import.cypher` | `build` |
| `load_all.py` | các file `*.json` + similarity edges | `warehouse.sqlite` + `graph/kg_networkx.pkl` | `run` |
| `precompute.py` | listings/interactions + `embeddings.pkl` + similarity edges | `precomputed/*.json` + bảng `pc_*` | `main` |
| `run_eval.py` | users/listings/interactions (+ embeddings) | `data/eval_results.json` (stdout report) | `main` |
| `export_csv.py` | `*.json` + `precomputed/*.json` | `data/csv/*.csv` | `main` |
| `visualize_graph.py` | users/listings/interactions + eval | `graph_viz.html` | `main` |
| `tests/*.py` | fixture nội bộ | PASS/FAIL | — |

---

## 4. Cấu trúc dữ liệu (schema)

Định nghĩa & validate trong [`schemas.py`](schemas.py) (Pydantic v2). Tên field
amenity/accessibility/view **khớp chính xác**
`backend/src/services/inference/knowledge.py` để KG map thẳng sang listing thật.

### 4.1. `users.json`
```jsonc
{
  "user_id": "usr_1000",
  "segment": "affordable",              // affordable | mid_range | luxury
  "primary_intent": "buy_for_living",   // buy_for_living | investment | rent
  "demographics": { "age_group": "30-40", "marital_status": "married",
                    "children": 2, "income_level": "medium_high" },  // số con 0-10 (VN thường 0-3)
  "explicit_preferences": {
    "preferred_districts": ["Quận 9", "Phường Long Bình"],
    "min_bedrooms": 2, "budget_range": [2.0, 2.4],   // tỷ VNĐ
    "property_type": ["Căn hộ"],
    "liked_amenities": ["near_school", "kids_playground"]
  }
}
```

### 4.2. `interactions.json`
```jsonc
{
  "interaction_id": "evt_100000", "user_id": "usr_1000",
  "session_id": "sess_1000_0", "listing_id": 45222670,
  "action_type": "contact",             // view | save | share | contact
  "timestamp": "2026-01-04T08:12:33Z", "dwell_time_seconds": 180,
  "source": "ai_recommendation",        // search_bar | ai_recommendation | homepage | related_items
  "context": {
    "raw_query": "căn hộ quận 9 cho gia đình giá khoảng 2 tỷ",
    "filters_applied": { "price_max": 2.4, "bedrooms": 2 },
    "inferred_intent": "buy_for_living", "budget_group": "affordable"
  },
  "implicit_score": 5.0,                 // action_weight × f(dwell_time)
  "is_bounce": false
}
```

### 4.3. `listings.json`
**Toàn bộ thuộc tính là DỮ LIỆU THẬT** lấy từ [`Data/Final_Data.csv`](../Data/Final_Data.csv)
(join theo `listing_id`, lọc các id có trong `embeddings.pkl` → 3030 căn):
giá, diện tích, phòng ngủ/tắm, loại BĐS, **địa chỉ + phường/xã SAU sáp nhập** (2025),
và các cột tiện ích 0/1. Chỉ **users & interactions** là mô phỏng (không có data user thật).

- `district` — **phường/xã thật sau sáp nhập** (vd `Phường Long Bình`, `Phường An Khánh`, `Xã Nhà Bè`); `address` = địa chỉ đầy đủ.
- `budget_group` — phân khúc **tuyệt đối** theo giá thật (affordable ≤3 / mid 3-8 / luxury >8 tỷ).
- `price_tier_area` — mức giá **tương đối trong quận** (`cheap`/`mid`/`premium`),
  tính bằng tercile (p33/p66) của phân bổ giá **chính quận đó** (`catalog.district_price_quantiles`).
  → dùng để chọn từ ngữ query: "nhà rẻ" ở Quận 1 (p33≈2.1 tỷ) khác "nhà rẻ" ở Quận 9.
  Câu query lấy từ `price_tier_area` chứ không nhắc con số tỷ tuyệt đối.

- `description` (chỉ khi bật LLM, ngược lại `null`) — mô tả tin đăng do LLM sinh, bám đúng dữ liệu.

### 4.4. Knowledge Graph CSV (`data/kg/`)

Xuất từ `build_kg.py`. Hai file dạng **danh sách cạnh/đỉnh** (nạp được vào Neo4j/DGL/NetworkX):

**`nodes.csv`** — mỗi dòng 1 node:

| Cột | Ý nghĩa |
|---|---|
| `id` | khoá duy nhất, dạng `Label:name` (vd `Listing:45222670`, `Amenity:pool`) |
| `label` | loại node: `User/Listing/Location/Amenity/Intent/Query/Criterion` |
| `name` | tên hiển thị |
| *(cột khác)* | thuộc tính tuỳ loại (vd Listing có `price`, `bedrooms`…) — trống nếu không áp dụng |

**`edges.csv`** — mỗi dòng 1 cạnh:

| Cột | Ý nghĩa |
|---|---|
| `src`, `dst` | node nguồn/đích (khớp `nodes.id`) |
| `rel` | loại quan hệ: `VIEWED/SAVED/SHARED/CONTACTED`, `SEARCHED`, `LOCATED_IN`, `HAS_AMENITY`, `PREFERS_DISTRICT`, `LIKES_AMENITY`, `HAS_INTENT`, `SIMILAR_TO`, `SIMILAR_LOCATION` |
| `score`,`dwell_time`,`timestamp`,`source` | thuộc tính cạnh tương tác (rỗng với cạnh khác) |
| `weight` | trọng số cạnh `SIMILAR_TO`/`SIMILAR_LOCATION` |

`import.cypher` = cùng nội dung nhưng dạng lệnh `MERGE` chạy thẳng trên Neo4j.

### 4.5. Kho quan hệ SQLite (`data/warehouse.sqlite`, từ `load_all.py`)

| Bảng | Khoá chính | Nội dung |
|---|---|---|
| `properties` | `listing_id` | thuộc tính + derived (`price_per_sqm_mil`, `amenity_count`, `family_suitable`) |
| `property_amenity` | (`listing_id`,`amenity`) | listing ↔ tiện ích (long format) |
| `users` | `user_id` | profile + `budget_min/max`, `persona` |
| `user_pref_district` / `user_liked_amenity` | (user, giá trị) | preference dạng long |
| `behavior` | `interaction_id` | event + cờ `is_positive` (save/share/contact) |
| `attribute_similarity` | (`attr_a`,`attr_b`,`grp`) | cạnh similarity (chuẩn hoá a≤b) |
| `pc_popularity` / `pc_item_neighbor` / `pc_query_expansion` | | bảng tra cứu do `precompute.py` ghi |

### 4.6. Artifact tính sẵn (`data/precomputed/`, từ `precompute.py`)

```jsonc
// content_neighbors.json — {listing_id: [top-20 tương tự]}
"45222670": [ {"listing_id": 43716231, "sim": 0.9787}, ... ]
// popularity.json
{ "per_listing": {"45222670": 0.83, ...},
  "top_by_district": {"Quận 9": [id, id, ...]}, "global_top": [...] }
// query_expansion.json — {attribute: [attribute liên quan]}
"near_school": [ {"attr": "kids_playground", "weight": 0.3, "group": "amenity"}, ... ]
```

---

## 5. Cấu hình phân phối

Chỉnh mọi thứ ở một chỗ: [`config/distribution_config.py`](config/distribution_config.py).

| Chiều | Mục tiêu |
|---|---|
| Phân khúc giá | 60% affordable · 30% mid_range · 10% luxury |
| Intent | ~55% buy_for_living · ~30% investment · ~15% rent |
| Trọng số action (edge weight) | view=1 · save=3 · share=4 · contact=5 |
| dwell_time | lognormal; `<10s` = bounce (lọc click ảo) |
| `implicit_score` | `action_weight × min(1, log1p(dwell)/log1p(180))` |

---

## 6. Knowledge Graph

[`kg/build_kg.py`](kg/build_kg.py) xuất `nodes.csv`, `edges.csv` và `import.cypher`
(chạy được ngay trên Neo4j: `cat import.cypher | cypher-shell`).

- **Nodes:** `User`, `Listing`, `Location`(district), `Amenity`, `Intent`, `Query`, `Criterion`
- **Edges:** `VIEWED/SAVED/SHARED/CONTACTED {score,dwell,timestamp}`, `SEARCHED`,
  `HAS_INTENT`, `PREFERS_DISTRICT`, `LIKES_AMENITY`, `LOCATED_IN`, `HAS_AMENITY`,
  `SIMILAR_TO {weight}` (amenity/criterion), `SIMILAR_LOCATION {weight}` (quận↔quận)

Quy mô hiện tại: **~7.081 node · ~33.169 edge**.

### 6.1. Similarity matrix & kiểm chứng (task 1.3)

[`similarity_kg.py`](similarity_kg.py) — **không nạp ma trận nguyên si mà kiểm chứng với hành vi**:

1. **Declared → cạnh** (`data/kg/similarity_edges.json`), đúng format `{attr_a, attr_b, weight}`:
   - amenity↔amenity từ `knowledge.py` (24 cặp, cùng tên field với data);
   - criteria↔criteria (ngữ nghĩa) từ `crawl_data/similarity_matrix_v2.py` (79 cặp) → node `Criterion`.
2. **Empirical từ hành vi** (interactions): cosine trên ma trận `user×amenity` và `user×district`.
3. **Kiểm chứng** declared vs hành vi → `data/similarity_validation.json`:
   tương quan **Spearman ρ** + tỷ lệ khớp (|Δ|≤0.2) + top cặp lệch nhất.
4. **Location edges từ hành vi** (`location_similarity_edges.json`) — vd `Phường Dĩ An ↔ Quận 9`.

> **Kết quả trên dữ liệu mô phỏng hiện tại:** ρ ≈ 0.2, khớp 13/24 cặp. Nghĩa là ma
> trận chuyên gia **chưa được hành vi mô phỏng xác nhận** — vì simulator gán amenity
> *độc lập* theo phân khúc nên các amenity bị tương quan đồng loạt. Đây chính là điều
> cần "kiểm chứng": với **dữ liệu thật** ρ sẽ có ý nghĩa; hoặc muốn sim phản ánh ma
> trận thì phải **tiêm tương quan amenity** vào `catalog.py`. Việc kiểm chứng là công
> cụ, không phải nạp mù.

### 6.2. Pipeline nạp dữ liệu — `load_all.py` (task 1.4, IDEMPOTENT)

[`load_all.py`](load_all.py) nạp dữ liệu vào 2 kho:

- **Quan hệ** (property / behavior / criteria) → **SQLite** `data/warehouse.sqlite`
  (zero-config; đổi sang Postgres chỉ cần thay connection).
- **Đồ thị** → **NetworkX** pickle `data/graph/kg_networkx.pkl`
  (Neo4j: đã có `data/kg/import.cypher` cho data engineer nạp).

```bash
python load_all.py                    # nạp tất cả
python load_all.py --verify-idempotent   # chạy 2 lần, khẳng định số dòng KHÔNG đổi
```

| Hàm | Việc |
|---|---|
| `load_properties()` | + derived: `price_per_sqm_mil`, `amenity_count`, `family_suitable`; bảng `properties` + `property_amenity` |
| `load_users()` | `users` + link `user_pref_district` / `user_liked_amenity` |
| `load_behavior()` | **sau khi validate** referential integrity (user & listing phải tồn tại); bảng `behavior` + cờ `is_positive` |
| `load_similarity()` | edges Attribute↔Attribute vào `attribute_similarity` (chuẩn hoá thứ tự cặp) |
| `build_graph_stub()` | NetworkX `MultiDiGraph`: node **User / Property / Attribute** + edges (behavior, HAS_ATTRIBUTE, PREFERS, LIKES, SIMILAR_TO) |

**Cơ chế idempotent:** mỗi bảng **MIRROR file nguồn** — `DELETE FROM` rồi bulk-insert
(full-refresh) nên vừa không nhân đôi khi re-run, vừa **xử lý đúng khi data co lại**
(vd đổi 300 → 5 user, row cũ biến mất); similarity chuẩn hoá `(a,b)` với `a<=b`;
graph dựng lại từ đầu rồi ghi đè pickle. Đã xác minh: chạy 2 lần → số dòng mọi bảng
**giống hệt**.

### 6.3. Tính sẵn phục vụ query — `precompute.py`

[`precompute.py`](precompute.py) tính trước những thứ đắt để **query về sau chỉ việc tra cứu**
(nhanh hơn & chất lượng hơn). Kết quả → `data/precomputed/*.json` + bảng SQLite (`pc_*`).

```bash
python precompute.py     # chạy sau generate_all.py + similarity_kg.py
```

| Artifact | Nội dung | Giúp query gì |
|---|---|---|
| `popularity.json` | điểm phổ biến mỗi listing + top-N theo quận/segment | **cold-start**, fallback ranking, tie-break |
| `content_neighbors.json` | top-20 BĐS tương tự theo **embedding thật** (cosine) | "BĐS tương tự", mở rộng candidate tức thì |
| `co_engagement.json` | item-item từ **hành vi** ("ai contact X cũng contact Y") | gợi ý theo hành vi, bổ sung content |
| `query_expansion.json` | mỗi attribute → attribute liên quan (từ similarity matrix) | **nới rộng truy vấn**: lọc `near_school` cũng xét `kids_playground` (0.3), `near_park` (0.28) |
| `segment_affinity.json` | amenity quan trọng theo `segment×intent` | prior cá nhân hoá / re-rank |

Bảng SQLite tra cứu nhanh: `pc_popularity`, `pc_item_neighbor` (60.6k dòng), `pc_query_expansion`.
Idempotent (ghi đè file + `INSERT OR REPLACE`). Dùng embeddings đã **dedup** listing_id trùng để BĐS không tự làm hàng xóm của chính nó.

---

## 7. Đánh giá (Evaluation)

[`run_eval.py`](run_eval.py):

1. **Temporal split** 80/20 theo `timestamp` (chống leakage — *không* random).
2. Mỗi user: candidate pool = positives + 100 negative lấy mẫu
   (**sampled-negatives**, giao thức NCF) → số liệu diễn giải được.
3. Ba recommender baseline (hàm `score(user, listing)`):
   - `popularity` — độ phổ biến toàn cục (tổng `implicit_score` train)
   - `content` — độ khớp thuộc tính user↔listing (hàm `relevance()`)
   - `embed_cf` — cosine(profile embedding user, embedding listing) dùng
     `embeddings.pkl` thật
4. Metric (K=10) lấy từ repo đã clone (fallback `metrics/`): **NDCG, MRR, Recall,
   Precision, MAP** + **HitRate** (tính bổ sung).

### Kết quả tham chiếu (193 user có tín hiệu tích cực)

| Recommender | NDCG@10 | Recall@10 | HitRate@10 | Precision@10 | MAP@10 |
|---|---|---|---|---|---|
| **content**  | **0.136** | **0.248** | **0.358** | **0.036** | **0.093** |
| embed_cf     | 0.062 | 0.101 | 0.161 | 0.016 | 0.042 |
| popularity   | 0.045 | 0.092 | 0.140 | 0.015 | 0.027 |

`content` vượt trội → bộ metric **phân biệt đúng** ranking tốt/xấu.

> **Lưu ý MRR:** hàm `mrr_at_k` của repo chỉ lấy trung bình trên user có hit trong
> top-k (giá trị đọc cao hơn, ~0.34–0.44, không cùng thang các metric khác) — đây
> là quy ước riêng của repo, dùng nguyên trạng.

---

## 8. CSV & Visualize

- [`export_csv.py`](export_csv.py) → `data/csv/*.csv` (phẳng, UTF-8-BOM để Excel đọc
  đúng tiếng Việt; `listings` tách 25 cột feature boolean). Xuất: `users`, `listings`,
  `interactions`, `eval_results`, `similarity_edges`, và các artifact precompute
  (`content_neighbors`, `co_engagement`, `popularity`, `query_expansion`,
  `segment_affinity`) — cái nào chưa có nguồn thì tự bỏ qua.
- [`visualize_graph.py`](visualize_graph.py) → `graph_viz.html` (tự-chứa, theme-aware):
  sơ đồ **schema**, **subgraph mẫu** (layout `networkx`), biểu đồ **thống kê node/edge**
  và biểu đồ **kết quả eval**. Màu theo palette đã qua validator, kèm secondary
  encoding (size + nhãn + legend).

---

## 9. Thiết kế đáng lưu ý

- **Grounded trên dữ liệu thật:** listing lấy 100% từ `Data/Final_Data.csv` (giá,
  diện tích, tiện ích, **địa chỉ phường/xã sau sáp nhập**); chỉ user/interaction là mô phỏng.
- **Kiểm soát phân phối bằng RNG có seed** thay vì phó mặc LLM (LLM hay trôi về
  trung bình). LLM chỉ dùng cho `raw_query`, có **template offline fallback** →
  chạy được **không cần mạng/API key** (bật LLM thật: `USE_LLM=1`).
- **Ground-truth có kiểm soát:** ~75% interaction lệch về listing khớp preferences.
- **Đã kiểm chứng:** 6/6 unit test metric so với ví dụ tính tay.

---

## 10. Hướng mở rộng

- **RAG metrics** (`metrics/rag.py`, chưa làm): khi tích hợp chatbot LLM giải thích
  gợi ý → thêm Answer Relevance / Context Precision / Faithfulness (Ragas / TruLens).
  `RecommendationEvent` (schema v2) chính là input sẵn (query+context+answer).
- **Thay thuộc tính mô phỏng bằng dữ liệu thật:** listings đã dùng `Final_Data.csv`;
  chỉ user/interaction là mô phỏng (không có data user thật).

---

## 11. Schema v2 (song song — `schemas_v2.py`)

Bản chuẩn hoá hơn, **chạy song song, KHÔNG đè v1**. Sinh bằng:

```bash
python generate_all_v2.py     # -> data/{users,recommendation_events,interactions}_v2.json
```

Hai thay đổi triết lý:

1. **UserProfile tách 2 loại** — `explicit_preferences` (user chủ động cung cấp: filter/chat,
   mỗi mục là `Preference{value, weight, source}` có trọng số cho KG) vs
   `inferred_attributes` (demographic suy luận: mỗi field bọc `InferredValue{value,
   confidence, evidence}`, mặc định `None`/conf 0 = "chưa biết").
2. **Tách `RecommendationEvent` khỏi `Interaction`**:
   - `RecommendationEvent` — 1 dòng/1 lần trả kết quả, theo **LLM-as-reranker**:
     retrieval lấy **10 ứng viên** (`recommended_items`, có `rank/score/matched_features`)
     → đưa **cả 10 vào LLM** → LLM **chọn & xếp ra 3** căn tốt nhất (`llm_output`:
     explanation + comparison). `algorithm_version="llm_rerank_v2"`. → chính là
     (query, context, answer) cho **RAG eval** (Ragas) và tính **Context
     Precision/Recall theo rank thật** — không cần sampled-negatives.
     (Offline/không key: fallback lấy top-3 theo retrieval; chỉnh `TOP_K`/`LLM_OUTPUT_K` trong `gen_v2.py`.)
   - `Interaction` — 1 dòng/1 hành động user, trỏ ngược `result_set_id` + `rank_position`.

| File | Vai trò |
|---|---|
| `schemas_v2.py` | schema v2 (Preference, InferredValue, RecommendationEvent…) |
| `config/vocab_real_data.py` · `config/districts_real.json` | vocab & 112 phường/xã **thật** (validate v2) |
| `extract_vocab.py` | rút vocab/districts từ `Final_Data.csv` |
| `generation/gen_v2.py` · `generate_all_v2.py` | sinh dữ liệu v2 (rerank bằng LLM cấu hình, mặc định Groq 70b) |
| `prep_rerank.py` · `apply_rerank.py` | rerank bằng **workflow agent Claude** (10→3) → ghi `*_v2_claude.json` |
| `data/*_v2.json` | dữ liệu v2 do **Groq 70b**/template rerank (v1 `users.json`/`interactions.json` **giữ nguyên**) |
| `data/*_v2_claude.json` | biến thể do **Claude agents** rerank — để so sánh chất lượng chọn |

**Hai reranker (cùng bộ 10 ứng viên, khác "người chọn"):**
- Groq 70b (in-pipeline): `USE_LLM=1 python generate_all_v2.py` → `*_v2.json`.
- Claude agents (offline): `python prep_rerank.py` → workflow rerank → `python apply_rerank.py` → `*_v2_claude.json`.
  Trên bộ hiện tại, Claude chọn top-3 **khác 84%** so với heuristic (tôn trọng ràng buộc cứng loại nhà/ngân sách trước, rồi mới tới tiện ích gia đình).

> Pipeline v1 (KG/load/precompute/eval) **chưa** chuyển sang đọc v2 — migrate dần
> khi cần (vd RAG eval đọc thẳng `recommendation_events_v2.json`).
