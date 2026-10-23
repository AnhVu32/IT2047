# Enrich dữ liệu BĐS mới bằng OpenStreetMap (OSM) — bản cache + công cụ cập nhật trực tiếp

## Trạng thái thực tế của lần chạy này

- Đã dùng **1.896 POI có OSM ID** trích từ file cũ `Final_Data_full_amenities_enriched.csv`, vốn có nhãn nguồn `OpenStreetMap_Overpass`.
- **CHƯA truy vấn live Overpass hay OSRM** trong lần chạy này vì máy xử lý không có kết nối mạng đến các API đó.
- 3.857 tin mới; giữ nguyên **toàn bộ 50 cột gốc**, xuất đúng schema **209 cột** của bản enrich cũ.
- Tạo **143.411 quan hệ ứng viên Top-5** trong bán kính theo nhóm tiện ích; **Top-5 này chỉ tính trong bộ POI cache cũ**, không bảo đảm đầy đủ hoặc cập nhật mới nhất từ OSM.
- 3.724 tọa độ nguồn có vẻ ở đúng khu vực; 133 tọa độ bất thường; sửa 106 nhờ trùng listing ID hoặc đồng thuận tại địa chỉ chính xác, giữ 27 chưa đủ căn cứ ở trạng thái trống.
- Tái sử dụng 1.028 cặp khoảng cách/thời gian OSRM cũ **chỉ khi listing ID, OSM ID và tọa độ cách nhau không quá 30m**. Các khoảng cách lái xe còn lại **để trống**, không ước lượng bừa.
- `straight_line_km`: khoảng cách Haversine, không phải khoảng cách đường đi thực tế.
- Các cờ `within_*_driving` để trống khi thiếu route; đừng hiểu trống là false.

## Các file đã tạo

| File | Vai trò |
|---|---|
| `listings_209cols_osm_cache_enriched.csv` | Dataset chính, đủ 209 cột tương thích dữ liệu enrich cũ, 50 cột ban đầu không đổi |
| `osm_poi_nodes.csv` | Danh mục 1.896 POI có OSM ID, tên, loại, tọa độ, địa chỉ |
| `listing_amenity_top5_edges.csv` | Top 5 POI mỗi loại nằm trong bán kính, gồm khoảng cách đường thẳng, route nếu thực sự có |
| `neo4j_listing_nodes.csv` | Listing nodes với giá numeric, địa chỉ cũ/mới và tọa độ |
| `neo4j_amenity_nodes.csv` | POI nodes nhiều nhãn: Amenity, Hospital, School... |
| `neo4j_listing_amenity_edges.csv` | Quan hệ `NEAR_AMENITY` Top-5 cho `neo4j-admin` |
| `neo4j_cluster_nodes.csv`, `neo4j_listing_cluster_edges.csv` | Cluster 150m |
| `neo4j_ward_nodes.csv`, `neo4j_listing_ward_edges.csv` | Phường mới |
| `neo4j_former_admin_area_nodes.csv`, `neo4j_listing_former_area_edges.csv` | Khu vực hành chính cũ |
| `neo4j_ward_former_area_edges.csv` | Quan hệ cũ/mới rút ra từ dữ liệu nguồn |
| `coordinate_quality.csv` | Nguồn, trạng thái, confidence của mỗi tọa độ |
| `needs_coordinate_review.csv` | 27 listing cần xác minh tọa độ |
| `summary.json`, `validation.json` | Thống kê và kết quả kiểm thử |
| `build_from_osm_cache.py` | Chạy lại enrich từ cache và POI được tải bổ sung |
| `refresh_osm_live.py` | Tải POI mới từ Overpass với rate-limit, tile cache và resumable |
| `compute_osrm_routes.py` | Tính khoảng cách/thời gian lái xe qua OSRM **tự host** |

## Khoảng cách chọn ứng viên Top-5

- Hospital 7km; School 3km; College/University 7km
- Metro 5km; Mall 7km; Market 3km
- Supermarket 3km; Park 5km; Bus Stop 2km

Các ngưỡng trên là **bán kính đường thẳng để lựa chọn POI**, không phải giới hạn đường lái xe. `rank=1` là gần nhất trong catalog có sẵn, không phải khẳng định gần nhất trong toàn OSM hiện hành.

## Chạy lại trên máy có kết nối Internet để fetch OSM live

Cài:

```bash
python -m pip install requests numpy scipy
```

Trong folder giải nén ZIP, chạy lệnh sau (thay `contact@yourdomain.com` bằng liên hệ thật và đường dẫn file chính tương ứng):

```bash
python refresh_osm_live.py \
  --master listings_209cols_osm_cache_enriched.csv \
  --base-poi osm_poi_nodes.csv \
  --output refreshed_osm_poi_nodes.csv \
  --cache-dir overpass_tile_cache \
  --max-tiles 3 \
  --user-agent 'YourOrgRealEstatePOI/1.0 (contact: contact@yourdomain.com)'
```

Script mặc định tải tối đa 3 ô mỗi lần để tránh gây tải lớn cho dịch vụ Overpass công cộng. Nó lưu phản hồi JSON theo từng ô và có thể chạy lại để tiếp tục. Để phủ toàn bộ dữ liệu, sử dụng nhiều lượt có kiểm soát hoặc một Overpass instance riêng nếu được phép; `--max-tiles` có thể điều chỉnh. Khi đổi catalog:

```bash
python build_from_osm_cache.py \
  --input /path/to/cleaned_master_data_50cols_enriched.csv \
  --historical /path/to/Final_Data_full_amenities_enriched.csv \
  --extra-poi refreshed_osm_poi_nodes.csv \
  --output refreshed_graph
```

**Hai file nguồn 50 cột và 209 cột lịch sử không đóng gói lặp trong ZIP**; dùng các file đầu vào bạn đã có (hoặc tải từ cuộc trò chuyện). Script offline sẽ tạo đầy đủ file cho graph mới.

## Tính quãng đường lái xe thực tế (OSRM)

Chỉ dùng một **OSRM server riêng**, có bản đồ đường bộ khu vực TP.HCM/Bình Dương/Đồng Nai đã chuẩn bị. Không bắn 3.857 x 9 hoặc 3.857 x 45 requests vào OSRM demo công cộng.

```bash
python compute_osrm_routes.py \
  --master listings_209cols_osm_cache_enriched.csv \
  --edges listing_amenity_top5_edges.csv \
  --poi osm_poi_nodes.csv \
  --osrm-url http://localhost:5000 \
  --output-dir osrm_routed \
  --top-k 1 \
  --max-listings 100
```

Chạy tiếp nhiều lượt để hoàn thiện toàn bộ, script có checkpoint JSONL tránh làm lại các listing thành công. `--top-k 5` nếu muốn tính route cho đủ Top-5; chỉ nên dùng với server riêng. Output gồm `listing_amenity_top5_edges_routed.csv` và `listings_209cols_osm_osrm_enriched.csv`.

## Import vào Neo4j database mới

Sao chép tất cả file `neo4j_*.csv` vào thư mục import của Neo4j và chạy từ thư mục đó (chỉ dùng cho database chưa tồn tại hoặc chuẩn bị cho full import):

```bash
neo4j-admin database import full graphdb \
  --id-type=string \
  --nodes=neo4j_listing_nodes.csv \
  --nodes=neo4j_amenity_nodes.csv \
  --nodes=neo4j_cluster_nodes.csv \
  --nodes=neo4j_ward_nodes.csv \
  --nodes=neo4j_former_admin_area_nodes.csv \
  --relationships=neo4j_listing_amenity_edges.csv \
  --relationships=neo4j_listing_cluster_edges.csv \
  --relationships=neo4j_listing_ward_edges.csv \
  --relationships=neo4j_listing_former_area_edges.csv \
  --relationships=neo4j_ward_former_area_edges.csv \
  --multiline-fields=true
```

Sau import, tạo constraint/index trong `post_import_indexes.cypher`. `:ID` header dùng để kết nối relationship; dữ liệu graph property lưu dưới tên cột trước hậu tố type.

**Chú ý:** File là graph riêng cho 3.857 tin mới. Để nhập cùng graph 3.037 tin cũ, nên làm bước deduplicate/upsert theo `listing_id`, bảo toàn các node amenity theo `osm_id` và ward/former area theo khóa chuẩn hóa. Không dùng `full import` vào graph đang hoạt động.

## Các lưu ý về chất lượng

1. Có 27 listing chưa đủ tọa độ để tính POI: xem `needs_coordinate_review.csv`.
2. Với 106 tọa độ suy diễn, cần đối chiếu nếu định dùng bán kính chính xác dưới 200m.
3. Catalog chỉ chứa các tiện ích từng được chọn là gần nhất trong dữ liệu cũ; POI mới, POI nhỏ hoặc các điểm gần khác có thể thiếu.
4. OSM POI của way/relation được tính từ điểm trung tâm, không nhất thiết là cổng vào tòa nhà; hướng/điểm tiếp cận khi routing cần hiệu chỉnh thêm.
5. Source `OpenStreetMap_Overpass_historical_cache` khác với `OpenStreetMap_Overpass_live`; không gộp hai trường này khi đánh giá độ mới.
6. Nên gắn attribution “© OpenStreetMap contributors” trong sản phẩm và kiểm tra điều khoản ODbL nếu phân phối dữ liệu.
