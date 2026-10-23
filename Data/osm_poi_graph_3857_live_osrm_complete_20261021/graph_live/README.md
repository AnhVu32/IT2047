# POI OSM mới và graph cho 3.857 listing

**Trạng thái xuất gói:** đã xử lý đủ **150,313** quan hệ Top-5: **150,193** route `ok`, **120** route `snapped_far`, **0** `unreachable`; **0 pending**. Khoảng cách/thời gian trống chỉ xuất hiện khi không tìm được route. 27 listing chưa xác minh tọa độ vẫn được giữ trong node và file review. Tọa độ listing/POI đã được người dùng cho phép gửi tới `router.project-osrm.org` để tính route.

## Nguồn và phạm vi

- Input hiện tại: `cleaned_master_data.csv`, đúng 3.857 listing ID. Tập ID và chuỗi tọa độ nguồn khớp bộ graph trước đó.
- Cloud Browser đã mở OpenStreetMap và kiểm tra Overpass. Overpass trong browser có lúc trả 502/406; phản hồi POI thành công được tải trực tiếp từ API bằng Python, không phải dữ liệu trích từ trang 406.
- Snapshot Overpass: **2026-10-21T03:07:35Z**, tức **10:07:35 ngày 21/10/2026, giờ Việt Nam**. Vùng truy vấn: nam 10.26, tây 106.36, bắc 11.46, đông 107.28, có đệm ít nhất 7km quanh các tọa độ listing hợp lệ.
- `osm_poi_nodes.csv` chỉ chứa POI từ phản hồi live mới. Không trộn lại POI lịch sử hoặc route lịch sử. Raw JSON, câu truy vấn, checkpoint OSRM được đóng gói kèm để kiểm tra nguồn.
- Giữ tọa độ và cờ chất lượng đã có: 3.724 tọa độ nguồn hợp lệ, 106 tọa độ đã suy diễn trước đó (103 theo địa chỉ, 3 theo listing ID), 27 chưa xác minh. Lần này không geocode lại 27 địa chỉ lỗi. Các tọa độ suy diễn cần được kiểm tra nếu ứng dụng cần độ chính xác dưới 200m.
- Các thuộc tính hành chính, cụm 150m và geohash được kế thừa từ gói trước, không phải dữ liệu hành chính mới tải từ OSM. Quan hệ phường/khu vực cũ chỉ phản ánh các cặp xuất hiện trong dữ liệu nguồn.

## Định nghĩa Top-5

Mỗi listing có tối đa 5 **OSM feature** gần nhất cho từng nhóm, xếp chính xác theo khoảng cách Haversine trên cầu bán kính 6.371km. Chỉ tạo quan hệ nếu POI nằm trong bán kính nhóm:

| category | Phân nhóm OSM | Bán kính đường chim bay |
|---|---|---|
| hospital | bệnh viện và phòng khám (`amenity=hospital/clinic`) | 7km |
| school | trường học và mẫu giáo | 3km |
| college_university | cao đẳng/đại học | 7km |
| metro | ga có nhãn mạng Ho Chi Minh City Metro | 5km |
| mall | trung tâm thương mại | 7km |
| market | chợ | 3km |
| supermarket | siêu thị | 3km |
| park | công viên | 5km |
| bus_stop | điểm dừng xe buýt/platform có `bus=yes` | 2km |

- `rank=1` là gần nhất theo đường chim bay trong snapshot/cách phân nhóm này, không phải xếp hạng theo đường đi. Route được tính cho các ứng viên đã chọn. Không khẳng định đây là Top-5 toàn cục theo quãng đường lái xe.
- Nếu không đủ 5 POI trong bán kính, chỉ xuất số thực có. Xem `listing_category_coverage.csv` để phân biệt thiếu tọa độ với không có POI trong vùng.
- Metro dùng 14 feature ga, không dùng 35 cửa vào như các ga độc lập. Các ga thiếu nhãn mạng/chưa xác minh và feature không hoạt động có trong `excluded_poi_review.csv`. Nhãn mạng OSM không thay thế việc xác minh vận hành thực địa.
- Khóa POI là `node/ID`, `way/ID`, `relation/ID`. Một cơ sở có thể có nhiều feature OSM riêng, và hai chiều điểm dừng xe buýt có thể đứng gần nhau. Không tự gộp các ID chỉ vì tên hoặc tọa độ gần nhau.
- `name` trống nghĩa là OSM chưa có tên. `subtype` giúp tách phòng khám/mẫu giáo khỏi bệnh viện/trường học nếu cần.
- Với way/relation, tọa độ là tâm bounding box (`out center`), có thể không trùng cổng vào. `coordinate_method` thể hiện điều này.

## Khoảng cách OSRM

- `driving_distance_km`: km dọc theo route ô tô do OSRM tính. `driving_duration_min`: phút ước tính theo profile, không có giao thông thời gian thực.
- OSRM Table trả khoảng cách của route tối ưu theo trọng số thời gian/profile, không bảo đảm quãng đường lái xe ngắn nhất tuyệt đối.
- `route_status=ok`: có kết quả, điểm snap đầu/cuối cách tọa độ gốc không quá 500m.
- `route_status=snapped_far`: có kết quả OSRM nhưng điểm snap cách gốc trên 500m. Giữ kết quả để kiểm tra, không dùng để bật cờ `within_*_driving`.
- `route_status=unreachable`: OSRM không tìm được route. Để trống khoảng cách/thời gian, không ghi 0.
- `route_status=pending`: chưa có phản hồi thành công. Xem `summary.json` cho độ phủ thực tế của lần chạy.
- `source_snap_m`, `destination_snap_m` là khoảng cách từ tọa độ gốc tới đường OSRM snap vào. Không tự cộng khoảng cách này vào route ô tô.
- Mỗi phản hồi được lưu. Luồng chính nghỉ tối thiểu 2 giây giữa các request; bước bổ sung cache dùng tối đa 2 worker với khoảng cách giữa lần bắt đầu request ít nhất 3 giây. Pipeline dừng khi dịch vụ lỗi liên tiếp hoặc trả giới hạn truy cập. Không ước lượng quãng đường bằng hệ số nhân Haversine.
- Các cột `nearest_*` và `*_driving_*` trong master mô tả **ứng viên rank 1 theo Haversine**. Muốn xếp theo đường đi trong số 5 ứng viên, dùng bảng edge.
- `within_*_driving` chỉ có 0/1 khi rank 1 có route trạng thái `ok`. Trống là chưa có phép đo đủ điều kiện. Tổng số nhóm trong ngưỡng để trống nếu chưa đủ cả 8 nhóm có ngưỡng.

## Các file chính

| File | Nội dung |
|---|---|
| `listings_osm_osrm_enriched.csv` | Tất cả 3.857 listing, trường rank 1 theo nhóm, tọa độ/chất lượng, mốc snapshot |
| `osm_poi_nodes.csv` | Catalog POI mới, subtype, nguồn, tags OSM và tọa độ |
| `listing_amenity_top5_edges.csv` | Quan hệ Top-5, khoảng cách/thời gian và trạng thái route |
| `neo4j_*_nodes.csv` | Node Listing/Amenity/GeoCluster/Ward/FormerAdminArea với header import có kiểu |
| `neo4j_*_edges.csv` | Relationship và ID group tương ứng |
| `coordinate_quality.csv` | Chất lượng tọa độ và số edge thực tế mỗi listing |
| `needs_coordinate_review.csv` | 27 listing chưa đủ tọa độ an toàn |
| `listing_category_coverage.csv` | Độ phủ theo listing và category |
| `summary.json`, `validation.json` | Số lượng, độ phủ route, kiểm tra dữ liệu và khóa graph |
| `example_queries.cypher` | Truy vấn minh họa trong Neo4j |

Master kế thừa các cột đặc trưng của bản trước và bổ sung trường `image_urls` từ input hiện tại. Các trường POI/route được tính lại, trường `location_link` đã bỏ tham số API key nhúng. Không ghi lại credential trong gói kết quả.

## Import Neo4j

Các CSV dùng UTF-8, dấu phẩy, quoting chuẩn CSV; ô trống là null. ID được chia nhóm nên ID số listing không xung đột ID amenity. Dùng **Neo4j 5+**, database mới; `import_full.sh` không có tùy chọn ghi đè database hiện có.

1. Giải nén gói và đặt thư mục `graph_live` vào máy có Neo4j. Dừng database đích nếu cần theo bản Neo4j bạn dùng.
2. Tại thư mục này chạy `bash import_full.sh graphdb`.
3. Khởi động database mới, chạy `post_import_indexes.cypher` bằng Neo4j Browser/cypher-shell.
4. Chạy `example_queries.cypher` để kiểm tra.

Import full phù hợp Neo4j tự quản trị. Aura không cho chạy `neo4j-admin` trực tiếp; cần dùng công cụ import tương ứng. Không dùng full import vào graph hiện hữu. Khóa cluster dạng `Gxxxx` chỉ có nghĩa trong snapshot nguồn này; cần namespace trước nếu hợp nhất với tập khác.

Chưa chạy import trên một Neo4j server thật trong môi trường tạo gói. Đã kiểm tra header kiểu số, ID duy nhất, toàn bộ đầu mút relationship, rank và so sánh Haversine độc lập; xem `validation.json`.

## Chạy lại

Mã nguồn nằm trong `pipeline/`. Cần Python 3, NumPy và SciPy. Từ thư mục gốc giải nén: `python pipeline/build_live_graph.py`, rồi `python pipeline/route_live.py --osrm-url http://localhost:5000`, sau cùng `python pipeline/validate_live_graph.py`. Bước build tạo lại master và xóa route trong output, nên luôn merge/routing lại sau khi build. Script tìm project root theo bố cục đóng gói. Chạy lại routing dùng checkpoint theo URL và tọa độ, không gọi lại các ma trận đã có. Đổi endpoint làm thay đổi khóa cache. Với refresh lặp lại/quy mô sản xuất, dùng OSRM riêng và chủ động quản lý snapshot bản đồ.

Để tái lập **chỉ từ cache**, không gửi request nào: `python pipeline/route_live.py --osrm-url https://router.project-osrm.org --cache-only`. Với endpoint bên ngoài máy, script yêu cầu cờ `--allow-coordinate-transfer` sau khi bạn chấp thuận gửi tọa độ listing và POI tới endpoint được chỉ định. Endpoint công cộng không được bật mặc định. Snapshot Overpass có thể refresh bằng `python pipeline/fetch_live_poi.py --user-agent 'TênỨngDụng/liên-hệ-thật' --refresh`; truy vấn chỉ gửi vùng bbox và bộ lọc POI, không gửi ID hay địa chỉ từng listing.

## Attribution và tài liệu

© OpenStreetMap contributors, dữ liệu theo ODbL: https://www.openstreetmap.org/copyright

Routing: OSRM, https://project-osrm.org/ . API Table và đơn vị: https://project-osrm.org/docs/v26.6.1/http . Hướng dẫn sử dụng Overpass: https://dev.overpass-api.de/overpass-doc/en/preface/commons.html . Giới hạn độ phủ OSM vẫn áp dụng: không có feature trong snapshot không chứng minh không có tiện ích ngoài thực tế.

Kiểm tra bổ sung: `route_provenance_validation.json` đối chiếu toàn bộ khoảng cách/thời gian của các edge với phản hồi OSRM gốc. Các cache có `derived_from_merged_response` là phép cắt ma trận, giữ nguyên từng giá trị OSRM; phản hồi lớn tương ứng nằm trong `live_cache/osrm_merged`. Số nhóm ma trận logic và số phản hồi API thành công được ghi riêng trong `summary.json`.

Master có thêm các cột `<category>_route_status`, `<category>_source_snap_m`, `<category>_destination_snap_m` cho ứng viên rank 1, để kiểm tra chất lượng route ngay trong bảng listing.
