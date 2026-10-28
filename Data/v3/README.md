# Data v3 — hợp nhất tập cũ (3.037 tin) và tập OSM live (3.857 tin)

Sinh bởi `pipeline/build_v3.py`. Không file nào trong hai gói nguồn bị sửa.

| Nguồn | Vai trò |
|---|---|
| `../osm_poi_graph_3857_live_osrm_complete_20261021/` | Tập **mới** (3.857 tin, POI live 12.340 điểm, snapshot 21/10/2026 03:07Z) |
| `../Final_Data.csv` + `../real_estate_graph_ready_v2_address_mapping/` | Tập **cũ** (3.037 dòng = 3.030 mã tin) |
| `../../images/` (+ `images 2/3/4`) | Ảnh của cả hai tập |

## Kết quả

- **6.703 tin**: 3.673 chỉ có ở tập mới, 2.846 chỉ có ở tập cũ, 184 trùng mã tin.
- **Tin trùng lấy bản mới.** Giá trị cũ của ngày đăng, ngày hết hạn, giá nằm ở `prev_posted_date`, `prev_expiry_date`, `prev_price_range`; toàn bộ khác biệt ở `reports/overlap_changes.csv` (100 tin đổi giá, 25 tin đổi diện tích).
- 7 mã tin bị trùng trong tập cũ được gộp còn 1 dòng (dòng `duplicate_index=1`). `listing_node_id` của mọi tin bằng `listing_id` (không còn hậu tố `__1`).
- **Tiện ích**: tin mới giữ nguyên Top-5 và route của gói live (150.313 cạnh). Tin cũ được tính lại Top-5 theo danh mục POI live bằng đúng phương pháp của gói live (111.961 cạnh) và tính route qua OSRM public `router.project-osrm.org`. Tổng 262.274 cạnh: 262.074 `ok`, 200 `snapped_far`, 0 `unreachable`, 0 `pending`.
- **Ảnh**: 60.395 ảnh, mọi tin đều có ảnh. Cột `images` là JSON list khóa MinIO `images/<loại>/<phường>/<mã tin>/<file>`; ánh xạ file cục bộ ở `images_manifest.csv`.
- 27 tin chưa xác minh được tọa độ nên không có cạnh tiện ích và không có cụm 150 m (giống gói live).

## File

| File | Nội dung |
|---|---|
| `master_v3.csv` | 6.703 tin, giữ tên cột của `Final_Data.csv` nên `backend/scripts/build_search_index.py` đọc được; thêm `source` (`old`/`new`/`both`), `images`, `prev_*`, cột địa chỉ chuẩn hóa |
| `listing_amenity_top5_edges.csv` | Top-5 và route; cột `origin` = `live_package` hoặc `v3_recomputed` |
| `osm_poi_nodes.csv` | 12.340 POI live |
| `graph/neo4j_*.csv` | CSV graph đặt đúng tên và header mà `backend/scripts/neo4j/import_search_graph.cypher` đang đọc |
| `images_manifest.csv`, `reports/excluded_images.csv` | Ảnh được đưa vào / bị loại và lý do |
| `reports/merge_report.json`, `reports/validation.json` | Thống kê và kết quả kiểm tra (24/24 đạt) |

## Các quyết định cần biết

1. **ID phường/khu vực cũ**: tập cũ bỏ chữ `đ` khi tạo slug (`an-hoi-ong`), tập mới giữ (`an-hoi-dong`). v3 dùng một dạng chuẩn duy nhất (`đ`→`d`), nên 233 ID phường nguồn gộp thành 132 node. Công thức tái tạo đúng 121/121 ID phường và 40/40 ID khu vực của gói mới.
2. **Cụm 150 m tính lại** trên toàn bộ 6.703 tin bằng liên kết đơn (single linkage) 150 m, vì ID `Gxxxx` của hai gói trùng tên nhưng khác nghĩa. Thuật toán này khớp gần như hoàn toàn với cụm gốc (lệch 1–2 cụm trên mỗi tập) nhưng không phải mã nguồn gốc. Cột `geo_cluster_size` cũng đổi theo.
3. **Node phố** dựng lại từ `road_name_final` + phường chuẩn hóa cho cả hai tập (2.326 phố), vì gói mới không có node phố.
4. **`park_view` bị xóa nhầm trong gói mới** (rỗng ở cả 3.857 tin vì `build_live_graph.py` xóa mọi cột bắt đầu bằng `park_`). v3 khôi phục từ `prior/`.
5. **Node phường/khu vực chỉ có ở tập mới**: 20 phường và 11 khu vực cũ có `normalized_name`/`aliases` được sinh theo mẫu của tập cũ, không phải dữ liệu gốc.
6. **Cạnh `NEAR_AMENITY` là Top-5** (như gói live), trong khi graph cũ chỉ có rank 1. `is_nearest` = (rank = 1). `within_threshold` tính theo quãng đường lái xe và chỉ có khi route `ok`.

## Hạn chế

- Các cột `latitude_original`, `longitude_original`, `coordinate_source`, `latitude_longitude_enriched`, `map_link_enriched`, `road_name_source` để trống cho tin cũ (tập cũ không ghi nguồn gốc tọa độ như vậy; không suy diễn). `image_urls` cũng trống vì tin cũ không còn danh sách URL.
- 7 tin cũ có tọa độ `imputed_by_ward_centroid` vẫn được tính tiện ích; độ chính xác thấp hơn.
- `snapped_far` (200 cạnh) và các route có quãng đường lái xe ngắn hơn đường chim bay (~70 cạnh, do điểm snap) giữ nguyên để kiểm tra, không dùng cho cờ `within_*`.
- 331 ảnh (và 61 webp) có đuôi `.jpg` nhưng nội dung là PNG/WebP: khi upload MinIO cần đặt `Content-Type` theo nội dung. 1 ảnh JPEG bị cắt cụt và 8 ảnh của mã tin `44329382` (không có trong cả hai tập) bị loại.
- Các cột thống kê kế thừa theo từng tập (`listing_density_1km`, `nearest_listing_distance_m`, `road_snap_distance_m`, `distance_to_ben_thanh_km`) **không** được tính lại trên tập hợp nhất.
- Kết quả đánh giá (Evaluation) chạy trên dữ liệu cũ không so sánh trực tiếp được với v3.

## Chạy lại

```bash
python -m venv .venv && .venv/bin/pip install -r pipeline/requirements.txt
.venv/bin/python pipeline/build_v3.py assemble                 # offline
.venv/bin/python pipeline/build_v3.py route --osrm-url https://router.project-osrm.org --allow-coordinate-transfer
.venv/bin/python pipeline/build_v3.py finalize --osrm-url https://router.project-osrm.org
.venv/bin/python pipeline/build_v3.py validate
```

Cache trung gian (`work/`) và phản hồi OSRM gốc (`live_cache/osrm/`) đã được xóa để gọn thư mục: `assemble` tạo lại `work/` trong vài giây, nhưng muốn dựng lại `master_v3.csv` bằng `finalize` thì phải chạy lại `route` (~258 request OSRM, ~10 phút) hoặc dùng OSRM tự host. Giá trị route hiện có đã nằm sẵn trong `master_v3.csv`, `listing_amenity_top5_edges.csv` và `graph/`. Gói OSM nguồn cũng không còn `live_cache/` (phản hồi Overpass/OSRM gốc), nên không tái lập từ cache được.

`route` gửi tọa độ tin cũ và POI tới endpoint đã chọn; mặc định chỉ chấp nhận `localhost` nếu không có `--allow-coordinate-transfer`. Phản hồi được cache nên chạy lại không gửi trùng; có thể dùng OSRM tự host qua `--osrm-url` (đổi endpoint sẽ đổi khóa cache).

## Nạp vào hệ thống (đã làm trên máy local, project compose `cs2307`)

| Đích | Cách | Trạng thái |
|---|---|---|
| MinIO (bucket `MINIO_BUCKET_NAME`) | `pipeline/upload_images_minio.py` chạy trong container backend, đọc `images_manifest.csv` | 60.395 object / 15 GiB, Content-Type theo nội dung thật |
| PostgreSQL | `pipeline/prepare_postgres.py` rồi `pipeline/load_v3.sql` (một transaction, giữ `properties.id`, gộp 7 dòng trùng, thay toàn bộ `listing_amenity_distances`) | 6.703 tin, 262.274 dòng khoảng cách |
| Embedding | `backend/scripts/build_search_index.py --skip-catalog-import --skip-graph-metadata` | 6.703/6.703 bằng `qwen/qwen3-embedding-4b` |
| Neo4j | `graph/*.csv` + `backend/scripts/neo4j/import_search_graph.cypher` (graph cũ đã xóa, backup volume trước đó) | 6.703 Listing, 12.340 Amenity, 262.274 `NEAR_AMENITY`, 132 Ward, 43 FormerAdminArea, 2.326 Street, 1.609 GeoCluster |

Lưu ý:
- Khóa ảnh trong MinIO và cột `properties.images` dùng Unicode **NFD** (đúng như tên file trên macOS). Phải dùng chuỗi lấy nguyên từ DB/manifest; gõ lại tay (NFC) sẽ ra 400.
- Vector cũ trong DB được tạo bằng `text-embedding-qwen3-embedding-0.6b`, khác model dùng khi truy vấn, nên toàn bộ vector được tạo lại bằng một model duy nhất.

© OpenStreetMap contributors (ODbL). Routing: OSRM.

## Nguồn dữ liệu mặc định của repo

Các chỗ sau đã trỏ sang v3, nên lần dựng mới (DB trống, volume mới) sẽ dùng đúng dữ liệu này:
`docker-compose.yml` (service `neo4j-import-init` chép `Data/v3/graph`), `backend/scripts/build_search_index.py`
(`Data/v3/master_v3.csv`, gồm cả cột `images`, và `Data/v3/graph`), `backend/scripts/import_neo4j_v2.py`,
`scripts/build_real_estate_graph.sh`. `import_search_graph.cypher` nạp cạnh `NEAR_AMENITY` theo lô 10.000 dòng.
`Evaluation/` (gồm `Evaluation/gen_user_data/` và `Evaluation/hcmre_q/`) vẫn gắn với bộ 3.037 tin cũ (`Data/Final_Data.csv`) và không bị đổi.
