# archive — bản cũ không còn dùng

Các file ở đây thuộc **thế hệ dữ liệu v2**, đã được thay bằng v3 và v4 (bảng phiên bản ở [`../README.md`](../README.md), mục 3). Không script nào đang dùng đọc chúng. Giữ lại để tra cứu và để đối chiếu các con số cũ nhắc trong `../docs/01_THIET_KE_DANH_GIA.md` và `../docs/02_GROUND_TRUTH_THEO_PHUONG.md`.

| File | Nội dung | Thay bằng |
|---|---|---|
| `data_v2/users_v2.json` | 200 user, giống hệt từng byte với `users_v3.json` | `gen_user_data/data/users_v3.json` |
| `data_v2/recommendation_events_v2.json`, `data_v2/interactions_v2.json` | 1.055 event, 2.298 tương tác; top-3 chọn bằng template hoặc Groq | Bản v3 |
| `data_v2/recommendation_events_v2_claude.json`, `data_v2/interactions_v2_claude.json` | Cùng 1.055 event, top-3 do Claude chọn; 2.122 tương tác | Bản v3 `_claude` |
| `data_v2/*_v2_sample.json` | Vài bản ghi mẫu minh hoạ schema | — |
| `data_v2/csv/` | CSV xuất từ dữ liệu v2 (`users_v2.csv`, `recommendation_events_v2_claude.csv`) | — |
| `generate_all_v2.py` | Driver sinh dữ liệu v2 | `gen_user_data/generate_all_v3.py` |
| `explore_data.py` | Khám phá dữ liệu v2: đếm bản ghi, kiểm tra id | `live_replay/run_validate.py` |

Hai script vẫn chạy được:

```bash
cd Evaluation/archive
python explore_data.py        # đọc data_v2/ và ../gen_user_data/data/listings.json, không ghi gì
python generate_all_v2.py     # sinh lại v2 vào ../gen_user_data/data/; bản lưu trong data_v2/ giữ nguyên
```

Dữ liệu sinh lại có thể khác bản lưu, vì code dùng chung (`catalog.py`, `generation/gen_v2.py`) đã thay đổi sau khi sinh v2. Muốn chạy Claude chọn lại 3/10 cho v2 thì để file `recommendation_events_v2.json` và `users_v2.json` trong `../gen_user_data/data/` (sinh lại như trên, hoặc chép từ `data_v2/`), rồi chạy `RERANK_VERSION=v2 python prep_rerank.py` và `RERANK_VERSION=v2 python apply_rerank.py` trong `../gen_user_data/`.
