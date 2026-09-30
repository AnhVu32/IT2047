# Crawl dữ liệu từ batdongsan.com.vn

Script này crawl danh sách tin từ:

- `https://batdongsan.com.vn/nha-dat-ban?vrs=1`

## Lưu ý quan trọng

- Website có cơ chế chống bot (Cloudflare), nên đôi lúc request có thể bị chặn.
- Chỉ dùng cho mục đích học tập/nghiên cứu.
- Nên crawl với tốc độ chậm, tôn trọng điều khoản sử dụng website.

## Cài đặt

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Chạy nhanh

```bash
python crawler.py --pages 1 --max-items 30 --format json --output data/listings.json --include-snippet
```

Mặc định script sẽ vào từng trang chi tiết để trích xuất đầy đủ trường (mã tin, loại tin, ngày hết hạn, địa chỉ, tọa độ, đặc điểm BĐS, thông tin dự án...).
Nếu chỉ muốn crawl nhanh từ trang danh sách, thêm `--skip-detail`.

## Xuất CSV

```bash
python crawler.py --pages 2 --max-items 100 --format csv --output data/listings.csv
```

## Xuất Excel (XLSX)

```bash
python crawler.py --pages 2 --max-items 100 --format xlsx --output data/listings.xlsx
```

Xuất cột tiếng Việt (mặc định đã bật):

```bash
python crawler.py --pages 2 --max-items 100 --format xlsx --output data/listings_vi.xlsx
```

Giữ tên cột gốc (không đổi tiếng Việt):

```bash
python crawler.py --pages 2 --max-items 100 --format xlsx --output data/listings_raw.xlsx --raw-columns
```

## Test parser (smoke test)

```bash
python -m unittest -v test_parser_smoke.py
```

## Trường dữ liệu output

- `title`: tiêu đề tin
- `url`: URL tin đăng
- `price`: giá (chuỗi thô)
- `area_m2`: diện tích (chuỗi thô)
- `price_per_m2`: đơn giá/m² (chuỗi thô)
- `location`: khu vực (nếu trích xuất được)
- `posted_date`: ngày đăng (nếu có)
- `contact_masked`: số điện thoại dạng ẩn (nếu có)
- `snippet`: đoạn mô tả ngắn (chỉ có khi dùng `--include-snippet`)
- `source_page`: trang nguồn crawl
- `all_text`: toàn bộ text hiển thị trên card tin
- `all_tokens`: toàn bộ text tách theo dấu `·` (nối bằng `|`)
- `all_links`: tất cả URL xuất hiện trong card tin (JSON array dạng chuỗi)
- `image_urls`: tất cả ảnh trong card tin (JSON array dạng chuỗi)
- `card_html`: HTML thô của card tin để lưu đầy đủ thông tin hiển thị
- `listing_code`: Mã tin
- `listing_type`: Loại tin
- `expiry_date`: Ngày hết hạn
- `real_estate_type`: Loại BĐS
- `province`: Tỉnh thành
- `district`: Quận huyện
- `description_text`: Thông tin mô tả
- `price_range`: Khoảng giá
- `bedrooms`: Phòng ngủ
- `folder`: Folder (slug thư mục từ URL)
- `address`: Địa chỉ
- `old_address`: Địa chỉ cũ
- `link_location`: Link Location (bản đồ)
- `latitude`: Vĩ độ
- `longitude`: Kinh độ
- `property_features`: toàn bộ trường trong mục Đặc điểm bất động sản (JSON)
- `project_info`: thông tin dự án (JSON)
- `dac_diem_*`: các cột bung từ từng trường trong Đặc điểm bất động sản
- `du_an_*`: các cột bung từ từng trường trong Thông tin dự án

## Tham số CLI

```text
--pages            Số trang cần crawl (mặc định: 1)
--max-items        Giới hạn số bản ghi, 0 = không giới hạn (mặc định: 100)
--format           json|csv|xlsx (mặc định: json)
--output           Đường dẫn file output
--timeout          Timeout request giây (mặc định: 25)
--retries          Số lần retry (mặc định: 3)
--delay            Nghỉ giữa request/trang, giây (mặc định: 1.2)
--include-snippet  Giữ trường snippet trong output
--skip-detail      Bỏ crawl trang chi tiết, chỉ lấy dữ liệu từ trang danh sách
--vi-columns       Đổi tên cột output sang tiếng Việt (mặc định: bật)
--raw-columns      Giữ tên cột gốc (không đổi sang tiếng Việt)
```
