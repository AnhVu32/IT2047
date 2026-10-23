# OSM live graph: 3.857 listing

Mở `graph_live/README.md` trước khi import.

Đã xử lý đủ 150,313 quan hệ Top-5; không còn route pending. Xem route_status để phân biệt route hợp lệ, snap xa hoặc không tìm được đường.

- `graph_live/`: CSV graph-ready, hướng dẫn import Neo4j và kiểm tra.
- `pipeline/`: mã tái lập và cập nhật.
- `live_cache/`: phản hồi gốc Overpass/OSRM.
- `prior/`, `inputs/`: seed tọa độ/cấu trúc graph và input để tái lập.

Có thể tái lập từ cache với `--cache-only`, không gửi request nào.
