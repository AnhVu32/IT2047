# Hướng Dẫn Sử Dụng Bộ Cào Dữ Liệu Bất Động Sản (README_NEW)

Tài liệu này tổng hợp hướng dẫn sử dụng và kiến trúc hoàn thiện của hệ thống cào dữ liệu [crawler.py](file:///d:/My%20Folder/Tài%20liệu/master/KyThuatXuLyDuLieu/project/IT2047/crawl_data/crawler.py).

---

## Tiến Độ Cập Nhật (Roadmap Progress)

- [x] **Phase 1: Quản lý Phân Khúc BĐS (Multi-Category)** *(Đã hoàn thành)*
  - Hỗ trợ tham số `--category` với 2 phân khúc chính.
  - Tự động sinh URL chuẩn phân trang: `p1`, `p2`, `p3`...
  - Tự động phân tách thư mục dữ liệu: `data/{category}/`.
- [x] **Phase 2: Lưu trữ dạng Streaming JSONL (Chống Crash)** *(Đã hoàn thành)*
  - Lưu trữ luồng dòng `data.jsonl`: cào xong tin nào, lưu ngay lập tức tin đó xuống ổ cứng (`flush=True`).
  - Loại bỏ hoàn toàn nguy cơ hỏng file khi crash giữa chừng.
  - Mặc định `--format jsonl`.
- [x] **Phase 3: Checkpoint & Resume Cấp Độ Từng Tin (`--resume`)** *(Đã hoàn thành)*
  - Tự động lưu tiến độ vào `data/{category}/checkpoint.json`.
  - Hỗ trợ cờ `--resume`: nạp các URL đã cào vào bộ nhớ, tự động **SKIP** các tin đã có trong database.
  - Hỗ trợ tham số `--start-page`: cho phép chủ động chọn trang bắt đầu.
- [x] **Phase 4: Tiện ích xuất dữ liệu Excel (`.xlsx`), JSON & CSV** *(Đã hoàn thành)*
  - Hỗ trợ cờ `--export xlsx|json|csv`: chuyển đổi tức thì từ `data.jsonl` mà không cần cào lại mạng.
  - Hỗ trợ xuất đồng bộ khi kết thúc cào với `--format xlsx|json|csv`.

---

## Cấu Trúc Thư Mục Dữ Liệu Tự Động

Mỗi phân khúc dữ liệu được lưu độc lập trong thư mục riêng:

```text
crawl_data/
├── crawler.py
└── data/
    ├── ban-can-ho-chung-cu-tp-ho-chi-minh/
    │   ├── data.jsonl                              <-- File dữ liệu gốc (ghi streaming từng tin)
    │   ├── checkpoint.json                         <-- File lưu tiến độ cào để phục vụ resume
    │   ├── track_20261003_160700_ban-can-ho-...log <-- Nhật ký theo dõi chi tiết từng trang & điểm crash
    │   ├── ban-can-ho-chung-cu-tp-ho-chi-minh.xlsx <-- File Excel xuất ra
    │   └── ban-can-ho-chung-cu-tp-ho-chi-minh.json <-- File JSON mảng hoàn chỉnh
    │
    └── ban-nha-dat-tp-ho-chi-minh/
        ├── data.jsonl
        ├── checkpoint.json
        ├── track_20261003_160350_ban-nha-dat-...log
        └── ban-nha-dat-tp-ho-chi-minh.xlsx
```

---

## Hướng Dẫn Sử Dụng Chi Tiết

### 1. Cào Mới (Fresh Crawl)

* **Cào cơ bản (Mặc định cào trọn vẹn theo số trang, KHÔNG giới hạn số tin):**
  *Mặc định `--max-items` là `0` (không giới hạn). Script sẽ cào trọn vẹn toàn bộ các tin có trên số trang bạn chỉ định mà không dừng giữa chừng.*
  ```powershell
  # Cào toàn bộ tin trên 3 trang của phân khúc căn hộ (không giới hạn số lượng tin)
  python crawler.py --category ban-can-ho-chung-cu-tp-ho-chi-minh --pages 3
  ```

* **Ràng buộc giới hạn số lượng tin nếu muốn (`--max-items`):**
  *Nếu bạn chỉ muốn cào thử nghiệm hoặc lấy đúng một số lượng tin nhất định rồi dừng lại:*
  ```powershell
  # Cào tối đa 30 tin (đạt đủ 30 tin sẽ tự động lưu checkpoint và dừng)
  python crawler.py --category ban-can-ho-chung-cu-tp-ho-chi-minh --pages 5 --max-items 30
  ```

* **Cào và tự động xuất ra file Excel / JSON / CSV (`--format`):**
  *Mặc định dữ liệu stream vào `data.jsonl` để chống crash. Thêm cờ `--format` để sau khi cào xong, script tự động tạo thêm file theo định dạng mong muốn.*
  ```powershell
  # Cào 2 trang và tự động sinh thêm file Excel (.xlsx) sau khi hoàn tất
  python crawler.py --category ban-can-ho-chung-cu-tp-ho-chi-minh --pages 2 --format xlsx

  # Cào 2 trang và tự động sinh thêm file JSON mảng chuẩn (.json)
  python crawler.py --category ban-nha-dat-tp-ho-chi-minh --pages 2 --format json
  ```

* **Điều chỉnh thời gian nghỉ giữa các request (`--delay`):**
  *Mặc định là `1.2` giây. Khi cào nhiều trang hoặc mạng chậm, nên tăng lên `2.0` đến `3.0` giây để hành vi giống người dùng thật, tránh bị Cloudflare chặn IP.*
  ```powershell
  # Nghỉ 2.5 giây giữa các lượt cào chi tiết để chống chặn bot an toàn
  python crawler.py --category ban-can-ho-chung-cu-tp-ho-chi-minh --pages 5 --delay 2.5
  ```

* **Cào tốc độ cao (bỏ qua trang chi tiết - `--skip-detail`):**
  *Chỉ cào thông tin tóm tắt hiển thị trên danh sách (giá, diện tích, tiêu đề, ngày đăng), chạy siêu nhanh:*
  ```powershell
  # Cào nhanh danh sách 3 trang (bỏ qua chi tiết)
  python crawler.py --category ban-can-ho-chung-cu-tp-ho-chi-minh --pages 3 --skip-detail
  ```

* **Lệnh phối hợp toàn diện (Ví dụ thực tế khuyên dùng khi cào nhiều trang):**
  ```powershell
  # Cào 10 trang trọn vẹn, không giới hạn số tin, giãn cách 2.0s, xuất thẳng ra file Excel
  python crawler.py --category ban-can-ho-chung-cu-tp-ho-chi-minh --pages 10 --delay 2.0 --format xlsx
  ```

---

### 2. Tiếp Tục Khi Bị Crash / Gián Đoạn (`--resume`)

Nếu quá trình cào bị dừng giữa chừng (do mất mạng, Cloudflare challenge, hoặc bạn chủ động tắt máy):

```powershell
python crawler.py --category ban-can-ho-chung-cu-tp-ho-chi-minh --pages 10 --resume
```

* **Cơ chế**:
  1. Không xóa file dữ liệu cũ.
  2. Nạp toàn bộ các URL đã có vào bộ nhớ.
  3. Đọc `checkpoint.json` để quay lại trang đang cào dở.
  4. Quét qua trang dở dang: Các tin đã cào sẽ hiển thị `[SKIP]` và bỏ qua ngay lập tức, chỉ cào các tin còn thiếu.
  5. Tiếp tục các trang tiếp theo cho đến khi hoàn thành.

* **Chỉ định trang bắt đầu thủ công:**
  ```powershell
  python crawler.py --category ban-can-ho-chung-cu-tp-ho-chi-minh --start-page 5 --pages 20 --resume
  ```

---

### 3. Theo Dõi Tiến Độ & Bắt Lỗi Crash (Tracking Log)

Mỗi lần chạy script, hệ thống sẽ tự động tạo một file nhật ký riêng biệt:
`data/{category}/track_{YYYYMMDD_HHMMSS}_{category}.log`

File nhật ký này được ghi theo cơ chế **xả đệm tức thì (`flush=True`)**, giúp bạn:
1. **Biết trang nào đã hoàn tất**:
   - Khi hoàn thành 1 trang, log sẽ ghi dòng:
     ```text
     [2026-10-03 16:07:05] [PAGE COMPLETED] Hoàn tất Trang 3/10 | Lưu mới: 18 tin | Bỏ qua: 2 tin | Tổng DB hiện tại: 58 tin
     ```
2. **Biết chính xác vị trí bị crash giữa chừng**:
   - Nếu tiến trình bị đứt mạng, lỗi HTTP, Cloudflare challenge, hoặc bạn chủ động bấm `Ctrl+C`:
     ```text
     [2026-10-03 16:08:12] [CRASH / ERROR] Tiến trình bị lỗi đột ngột tại Trang 4/10 (đang xử lý tin thứ 7/20) | Nguyên nhân: Cannot fetch ... Tổng DB đã lưu an toàn: 65 tin.
     ```
   - Nhờ đó, bạn biết chính xác tiến độ dừng ở **Trang 4, tin thứ 7**, và 65 tin trước đó đã được lưu an toàn tuyệt đối trong `data.jsonl`.
   - Bạn chỉ cần chạy lại lệnh kèm cờ `--resume` để tiếp tục ngay tại điểm dừng mà không bị cào lặp.

---

### 4. Tiện Ích Xuất Dữ Liệu Sang Excel / JSON / CSV (`--export`)

Sau khi cào xong (hoặc bất cứ lúc nào), bạn có thể xuất dữ liệu từ `data.jsonl` sang định dạng mong muốn mà **không tốn request mạng nào**:

* **Xuất ra Excel (`.xlsx`):**
  ```powershell
  python crawler.py --category ban-can-ho-chung-cu-tp-ho-chi-minh --export xlsx
  ```
  *(File được tạo tại: `data/ban-can-ho-chung-cu-tp-ho-chi-minh/ban-can-ho-chung-cu-tp-ho-chi-minh.xlsx`)*

* **Xuất ra JSON chuẩn (`.json`):**
  ```powershell
  python crawler.py --category ban-can-ho-chung-cu-tp-ho-chi-minh --export json
  ```

* **Xuất ra CSV (`.csv`):**
  ```powershell
  python crawler.py --category ban-can-ho-chung-cu-tp-ho-chi-minh --export csv
  ```

* **Chỉ định tên file xuất tùy ý:**
  ```powershell
  python crawler.py --category ban-can-ho-chung-cu-tp-ho-chi-minh --export xlsx --output data/chung_cu_q7.xlsx
  ```

---

## Bảng Tham Số Dòng Lệnh Đầy Đủ

| Tham số | Giá trị mặc định | Giải thích |
| :--- | :---: | :--- |
| `--category` | `ban-can-ho-chung-cu-tp-ho-chi-minh` | Phân khúc BĐS (`ban-can-ho-chung-cu-tp-ho-chi-minh` hoặc `ban-nha-dat-tp-ho-chi-minh`). |
| `--pages` | `1` | Số trang cần duyệt. |
| `--start-page` | `None` | Trang bắt đầu cào (tự động lấy từ checkpoint nếu có `--resume`). |
| `--resume` | `False` | Cờ bật cơ chế tiếp tục cào từ checkpoint, chống trùng tin. |
| `--max-items` | `0` | Giới hạn số bản ghi (`0` = không giới hạn, cào trọn vẹn theo số trang). Người dùng tự thiết lập nếu muốn giới hạn số tin. |
| `--format` | `jsonl` | Định dạng output chính: `jsonl`, `json`, `csv`, `xlsx`. |
| `--export` | `None` | Lệnh xuất file độc lập từ `data.jsonl`: `xlsx`, `json`, `csv`. |
| `--output` | `""` | Đường dẫn file xuất tùy chỉnh (nếu muốn đặt tên riêng). |
| `--delay` | `1.5` | Số giây nghỉ giữa mỗi request/trang (tránh bị chặn IP). |
| `--timeout` | `30` | Timeout request tính bằng giây. |
| `--retries` | `3` | Số lần thử lại khi gặp sự cố mạng. |
| `--skip-detail` | `False` | Bỏ qua trang chi tiết, chỉ lấy thông tin từ thẻ danh sách. |

> **Lưu ý về tên cột**: Mọi trường dữ liệu xuất ra (JSONL, JSON, CSV, Excel) đều **mặc định sử dụng tên tiếng Anh dạng snake_case** chuẩn (ví dụ: `title`, `price`, `area_m2`, `price_per_m2`, `district`, `address`, `latitude`, `longitude`, ...) để tối ưu hóa việc phân tích với Pandas, nạp vào Database và huấn luyện Machine Learning.

---

## Kiểm Thử Hệ Thống (Smoke Tests)
Để kiểm tra tính toàn vẹn của bộ bóc tách HTML:
```powershell
python -m unittest -v test_parser_smoke.py
```
