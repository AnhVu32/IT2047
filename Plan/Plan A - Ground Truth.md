# Plan A — Ground truth 2 tầng theo Phường/Xã (`gen_user_data/`)

## Context

Eval cho thấy precision/recall/NDCG thấp bất thường (đã điều tra chi tiết
trong `Evaluation/EVAL_PLAN.md` và `Evaluation/README.md`). Nguyên nhân gốc:
`relevance_v2()` (`gen_user_data/generation/gen_v2.py:171-198`) chỉ cho
trường `district` (giá trị thật là **Phường/Xã** sau sáp nhập, vd
`"Phường Thới Hòa"` — KHÔNG phải "Quận" cũ) 20% trọng số (2.0/10) trong tổng
điểm, và mỗi event chỉ xếp hạng trên 500/3030 listing lấy ngẫu nhiên — nên
top-10 "ground truth" thường trải trên 6-7 phường/xã khác nhau, trong khi hệ
thống search thật lọc theo `district` kiểu **cứng** (SQL `AND`, loại thẳng
nếu sai phường/xã — `backend/src/search/repository.py::_where()`). Kết quả:
hệ thống bị đánh giá thấp vì lý do không liên quan tới chất lượng ranking
thật.

Quyết định: nâng trọng số `district` lên mức gần như quyết định tuyệt đối,
cụ thể qua thiết kế nhiều tầng — đúng phường/xã luôn đứng trước; nếu thiếu,
bù bằng listing **gần về mặt địa lý** (cùng cụm/geohash) trước khi bù bất kỳ
listing nào khác trên toàn thành phố — làm ground truth nội tại nhất quán cả
về hành chính lẫn khoảng cách thực tế.

(Xem thêm [`Plan B - Backend.md`](Plan%20B%20-%20Backend.md) — tính năng
fallback khu vực tương ứng trên hệ thống thật, độc lập với plan này, có thể
làm trước.)

---

## 1. Dữ liệu vị trí địa lý (geohash/geo-cluster) — bổ sung mới

**Đã xác minh bằng dữ liệu thật**: `Data/real_estate_graph_ready_v2_address_mapping/Final_Data_graph_ready_filtered.csv`
có 3 cột `geohash_6`, `geohash_7`, `geo_cluster_150m` cho 3037/3037 listing —
đúng như mô tả: `geohash_6` là vùng **lớn nhất** (560 vùng phân biệt, trung
bình ~5.4 listing/vùng, ~1.2×0.6km ở vĩ độ VN — độ dài geohash 6 ký tự theo
chuẩn), `geohash_7` mịn hơn nhiều (1496 vùng, ~2.0 listing/vùng, ~150m),
`geo_cluster_150m` là cụm riêng theo khoảng cách thực (1069 vùng, ~2.8
listing/vùng). 3 cột này **hiện chưa có** trong `Listing`
(`gen_user_data/schemas.py:36-56`) hay trong `build_catalog()` — `Listing`
hiện chỉ build từ `Data/Final_Data.csv` (không có cột geo).

### `gen_user_data/schemas.py`
Thêm 3 field (đều optional — join có thể thiếu vài listing biên):
```python
class Listing(BaseModel):
    ...
    geohash_6: Optional[str] = None
    geohash_7: Optional[str] = None
    geo_cluster_150m: Optional[str] = None
```

### `gen_user_data/catalog.py::build_catalog()`
Thêm bước join sau khi đọc `Final_Data.csv` (trước hoặc sau lọc theo
`embeddings.pkl` đều được, join theo `listing_id`):
```python
GRAPH_READY_CSV = os.path.join(
    REPO_ROOT, "Data", "real_estate_graph_ready_v2_address_mapping",
    "Final_Data_graph_ready_filtered.csv",
)

def _geo_lookup() -> dict[int, tuple]:
    """listing_id -> (geohash_6, geohash_7, geo_cluster_150m). File nguồn có
    thể có nhiều dòng cùng listing_id (7 business id bị trùng, phân biệt bằng
    listing_node_id dạng "id__2") — giữ dòng đầu tiên, đủ dùng cho mục đích
    gom cụm địa lý (2 dòng trùng gần như cùng toạ độ)."""
    import pandas as pd
    if not os.path.exists(GRAPH_READY_CSV):
        return {}
    df = pd.read_csv(GRAPH_READY_CSV, usecols=["listing_id", "geohash_6", "geohash_7", "geo_cluster_150m"])
    df = df.drop_duplicates(subset="listing_id")
    return {
        int(r.listing_id): (r.geohash_6, r.geohash_7, r.geo_cluster_150m)
        for r in df.itertuples()
    }
```
Rồi khi build từng `Listing`, tra `_geo_lookup()` theo `listing_id`, gán vào
`geohash_6`/`geohash_7`/`geo_cluster_150m` (để `None` nếu không có — hàm ở
mục 2 xử lý an toàn cho trường hợp này).

### Index tra cứu nhanh
Thêm cạnh `derive_pools()`, 4 hàm cùng khuôn mẫu:
```python
def build_district_index(listings: List[Listing]) -> Dict[str, List[int]]:
    """district (Phường/Xã) -> danh sách index trong `listings`."""
    idx: Dict[str, List[int]] = {}
    for i, l in enumerate(listings):
        idx.setdefault(l.district, []).append(i)
    return idx

def build_geo_index(listings: List[Listing], field: str) -> Dict[str, List[int]]:
    """Dùng chung cho geohash_6 / geohash_7 / geo_cluster_150m -> index.
    Bỏ qua listing có field=None (thiếu dữ liệu join)."""
    idx: Dict[str, List[int]] = {}
    for i, l in enumerate(listings):
        value = getattr(l, field)
        if value:
            idx.setdefault(value, []).append(i)
    return idx
```
Build 1 lần, dùng lại xuyên suốt `generate_events_interactions_v2` để không
phải quét lại catalog mỗi event.

## 2. `gen_user_data/generation/gen_v2.py` — nâng trọng số `district` lên quyết định, có bù theo khoảng cách thực

Nói đơn giản: thay vì `district` chỉ chiếm 20% điểm như hiện tại
(`relevance_v2()`, dòng 171-198), biến nó thành **tiêu chí quyết định trước
tiên** — đúng phường/xã user thích thì luôn được xếp lên đầu, các tiêu chí
còn lại (giá/loại nhà/phòng ngủ/tiện ích) chỉ dùng để xếp thứ tự *trong*
nhóm đó. Khi phường/xã đó không đủ 10 listing, **không lấy bừa listing ở bất
kỳ đâu khác trong thành phố** — ưu tiên bù bằng listing gần về mặt địa lý
trước (cùng cụm 150m → cùng geohash_7 (~150m) → cùng geohash_6 (~1.2km,
vùng rộng nhất) → cuối cùng mới lấy bất kỳ đâu nếu vẫn thiếu). Cụ thể:

1. Viết hàm điểm phụ mới `secondary_relevance(user, listing)` — **giống hệt
   công thức `relevance_v2` hiện tại nhưng bỏ hẳn phần cộng điểm `district`**
   (chỉ còn giá + loại nhà + phòng ngủ + tiện ích, tổng trọng số 8.0 thay vì
   10.0). `relevance_v2()` cũ giữ nguyên, không xoá, không dùng nữa trong
   luồng sinh event.
2. Thêm `select_tier_candidates(user, catalog, district_index, geo_indexes, target_district, top_k=TOP_K)`
   (`geo_indexes` = dict `{"geo_cluster_150m": ..., "geohash_7": ..., "geohash_6": ...}`,
   mỗi cái là kết quả `build_geo_index()` ở mục 1):
   - **Tầng 1**: toàn bộ listing có `district == target_district`, xếp theo
     `secondary_relevance` giảm dần (`argsort(..., kind="stable")` để kết quả
     tất định khi trùng điểm — phường/xã nhỏ dễ trùng).
   - Nếu tầng 1 đã đủ `top_k` → dừng, trả về luôn.
   - **Tầng 2 (bù theo khoảng cách, chỉ chạy khi tầng 1 thiếu)**: lấy tập
     giá trị `geo_cluster_150m`/`geohash_7`/`geohash_6` xuất hiện trong tầng
     1 (từ các listing tầng 1 đã có, bỏ qua `None`). Lần lượt theo thứ tự
     **hẹp → rộng**:
     - 2a. Listing NGOÀI `target_district` nhưng `geo_cluster_150m` trùng 1
       trong các cụm của tầng 1.
     - 2b. (nếu vẫn thiếu) Listing NGOÀI `target_district`, chưa lấy ở 2a,
       có `geohash_7` trùng.
     - 2c. (nếu vẫn thiếu) Listing NGOÀI `target_district`, chưa lấy ở
       2a/2b, có `geohash_6` trùng.
     Mỗi bước con xếp theo `secondary_relevance` giảm dần, chỉ lấy đủ số còn
     thiếu rồi dừng.
   - **Tầng 3 (chốt chặn cuối, hiếm khi cần)**: nếu tầng 1+2 vẫn chưa đủ
     `top_k` (phường/xã hẻo lánh, các vùng geohash lân cận cũng thưa listing)
     — bù nốt bằng listing tốt nhất theo `secondary_relevance` ở **bất kỳ
     đâu** trong catalog, không ràng buộc vị trí, để luôn đủ đúng `top_k`.
   - **Trường hợp tầng 1 rỗng hoàn toàn** (target_district không có listing
     nào — không nên xảy ra vì `preferred_districts` chỉ chứa phường/xã có
     thật trong catalog, nhưng vẫn xử lý an toàn): không có "cụm tầng 1" để
     tham chiếu → bỏ qua tầng 2a/2b/2c, đi thẳng tầng 3.
   - Nối các tầng theo đúng thứ tự trên, **luôn** giữ nguyên thứ tự này (tầng
     trước luôn đứng trên tầng sau bất kể điểm số) — đây chính là "trọng số
     district gần như tuyệt đối, ưu tiên cả khoảng cách thực khi phải bù".
3. Trong `generate_events_interactions_v2()` (dòng 230-334):
   - Bỏ dòng lấy mẫu ngẫu nhiên `pool_idx = rng.choice(..., size=min(500, ...))`
     — **quét toàn bộ ~3030 listing** thay vì 500 ngẫu nhiên (rẻ, chạy 1 lần
     lúc sinh dữ liệu offline, không phải lúc user query thật).
   - `district_index = build_district_index(catalog)` và
     `geo_indexes = {f: build_geo_index(catalog, f) for f in ("geo_cluster_150m", "geohash_7", "geohash_6")}`
     — build 1 lần, đặt gần `amen_sim = _load_amenity_sim()`.
   - Thay khối chọn ứng viên cũ bằng:
     ```python
     target_district = str(rng.choice([x.value for x in user.explicit_preferences.preferred_districts]))
     top = select_tier_candidates(user, catalog, district_index, geo_indexes, target_district, top_k=TOP_K)
     lead = top[0][0]
     ... (raw_query giữ nguyên logic cũ, tự nhiên sẽ nhắc đúng phường/xã vì lead luôn ở target_district khi tầng 1 không rỗng) ...
     filters = {"district": target_district}   # suy ra trực tiếp, không random 1 lần nữa
     ```
   - Phần còn lại (`rec_items`, `_rerank_and_explain`, sinh interactions)
     không cần sửa — đã xác nhận qua đọc toàn bộ hàm, chỉ đọc `top` như
     `List[(Listing, float)]` chung chung.

## 3. Giảm tổng số event từ ~1055 xuống ~500

Số event hiện tại = tổng qua 200 user của `ceil(T / 3)` với
`T ~ clip(Poisson(15), 10, 20)` (config hiện tại,
`gen_user_data/config/distribution_config.py:16-20`) → trung bình ~5
event/user × 200 user ≈ 1000-1055, khớp con số thực tế đã quan sát.

Để còn **~500 event** (500 query, mỗi query top-10), sửa
`gen_user_data/config/distribution_config.py`:
```python
INTERACTIONS_PER_USER_LAMBDA = 7   # từ 15
MIN_INTERACTIONS_PER_USER = 5      # từ 10
MAX_INTERACTIONS_PER_USER = 10     # từ 20
```
Trung bình T≈7 → `ceil(T/3)`≈2.5-3 event/user × 200 user ≈ 500-540 event.
Đây là số **xấp xỉ** (do lấy mẫu Poisson ngẫu nhiên), không chốt đúng 500
tuyệt đối — chạy thử 1 lần rồi xem con số in ra (`generate_all_v2.py` in
tổng số event) để tinh chỉnh lại `INTERACTIONS_PER_USER_LAMBDA` nếu cần sát
hơn.

## 4. `Evaluation/adapters.py` — sửa kèm theo (bắt buộc, không tuỳ chọn)
`translate_filters_for_live()` (dòng 161-187) hiện gửi **toàn bộ**
`preferred_districts` của user lên hệ thống thật — đây là bản vá cho ground
truth CŨ (district chỉ 20% trọng số nên trải nhiều phường/xã). Sau khi sửa
xong, ground truth tầng 1 đã gắn với đúng 1 phường/xã xác định
(`filters["district"]` mới) — tiếp tục gửi cả danh sách sẽ:
- Làm filter gửi lên **rộng hơn** thực tế ground truth được xây (lệch theo
  chiều ngược lại).
- Khiến tính năng fallback khu vực (xem Plan B) gần như không bao giờ được
  kích hoạt khi chạy eval (filter đa-khu-vực hiếm khi trả về rỗng).

**Sửa**: bỏ hẳn khối override, để `filters["district"]` đi thẳng từ
`event["context"]["filters_applied"]["district"]` (giờ đã là 1 chuỗi đúng).
Cập nhật lại docstring hàm này + đoạn liên quan trong `Evaluation/README.md`
(mục "Lưu ý khi đọc kết quả") cho khớp lý do mới.

## 5. Không cần sửa (đã xác nhận)
- `prep_rerank.py`, `apply_rerank.py` — xử lý `recommended_items`/`llm_output`
  chung chung, không phụ thuộc nội bộ phường/xã/`relevance_v2`.
- `Evaluation/adapters.py::ground_truth_k()` — đã đọc `len(recommended_items)`
  động, luôn = 10 vì tầng 1+2+3 cộng lại luôn đủ (catalog ~3030 listing,
  phường/xã nhỏ nhất có 1 listing, tầng 3 là chốt chặn không ràng buộc vị
  trí nên luôn bù đủ nếu tầng 1+2 còn thiếu).
- Pipeline v1 (`run_eval.py`, `load_all.py`, `precompute.py`, `similarity_kg.py`,
  `kg/build_kg.py`) — không đọc file v2, không gọi `relevance_v2`.

---

## Thứ tự triển khai

1. **Sửa code** — `schemas.py` + `catalog.py` (mục 1, thêm field geo + join
   + index), `gen_v2.py` (mục 2, thiết kế nhiều tầng), giảm số event trong
   `distribution_config.py` (mục 3).
2. **Chạy thử nhỏ** — script adhoc build 1 catalog giả nhỏ (vài listing
   phường A có gán geohash, vài phường B/C ở cụm geo khác nhau), gọi
   `select_tier_candidates` — xác nhận: đủ phường A thì chỉ trả phường A xếp
   đúng thứ tự điểm; thiếu thì ưu tiên bù listing cùng `geo_cluster_150m`/
   `geohash_7`/`geohash_6` với phường A trước (đúng thứ tự hẹp→rộng), chỉ
   lấy listing bất kỳ khi các tầng geo cũng không đủ; tổng luôn đúng
   `top_k`. `secondary_relevance` không đổi theo phường/vị trí (sanity check
   không rò rỉ điểm district/geo vào điểm số).
3. **Chạy full pipeline sinh dữ liệu**:
   ```bash
   cd gen_user_data
   python generate_all_v2.py     # -> recommendation_events_v2.json (bản mới, ~500 event)
   python prep_rerank.py         # -> scratchpad/rerank/batch_*.json
   # --- chạy workflow Claude-agent rerank bên ngoài (thủ công/agentic) ---
   python apply_rerank.py        # -> recommendation_events_v2_claude.json (bản cuối)
   ```
   Bước rerank-workflow là thủ công/ngoài script, mất thời gian — nên bắt
   đầu sớm, đừng để thành điểm nghẽn cuối cùng.
4. In thống kê sau khi có `recommendation_events_v2.json` mới: tổng số event
   sinh ra (kỳ vọng ~500), và trong 10 `recommended_items` mỗi event có bao
   nhiêu item cùng `filters_applied["district"]` (kỳ vọng tăng mạnh so với
   baseline ~1/10 trước đây).
5. **Sửa `Evaluation/adapters.py`** (mục 4) ngay sau khi có
   `recommendation_events_v2_claude.json` mới.
6. **Chạy lại `Evaluation/run_eval.py`** để xác nhận cải thiện:
   ```bash
   cd Evaluation && python run_eval.py --limit 100
   ```
   So precision/recall/NDCG với baseline đã ghi
   (`Evaluation/results/20260805T142916_n97/summary.json`) — kỳ vọng tăng rõ
   rệt, đến từ ground truth nhất quán hơn chứ không phải ranking thay đổi.
   Đồng thời xác nhận tính năng fallback khu vực ở Plan B thực sự được kích
   hoạt qua đường eval (một số query sẽ rơi vào trường hợp 0 kết quả đúng
   phường/xã → kích hoạt fallback).
