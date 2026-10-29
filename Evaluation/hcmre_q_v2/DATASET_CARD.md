# Dataset card — HCMRE-Q v2

| | |
|---|---|
| Tên | HCMRE-Q v2: Ho Chi Minh City Real Estate Queries, phiên bản 2 |
| Phiên bản | 2.0, ngày 28/10/2026 |
| Thuộc | đồ án IT2047, thư mục `Evaluation/hcmre_q_v2/` |
| Nhiệm vụ | truy hồi tin bán bất động sản từ câu tìm kiếm tiếng Việt tự do (ad-hoc retrieval) |
| Quy mô | 1.000 câu hỏi × 6.703 tin, nhãn 0–3 cho mọi cặp |
| Giao thức | [`PROTOCOL.md`](PROTOCOL.md), đăng ký trước khi sinh dữ liệu |
| Kết quả kiểm định | [`META_EVAL.md`](META_EVAL.md) |

## 1. Mục đích

Bộ dữ liệu dùng để:

- đo chất lượng xếp hạng của hệ thống tìm kiếm IT2047 và các biến thể của nó: lexical, embedding, graph, LLM
  parser;
- so sánh các biến thể bằng cùng một thước đo, có khoảng tin cậy và kiểm định;
- đo riêng từng khả năng: hiểu giá, phòng ngủ, diện tích, khoảng cách tới tiện ích hay địa danh, đặc điểm mô tả,
  loại nhà con, và tôn trọng **phường mới** (sau 1/7/2025).

Không nên dùng bộ dữ liệu để:

- huấn luyện rồi báo cáo trên chính tập test;
- suy ra hành vi tìm kiếm thật của người dùng. Câu hỏi được sinh từ khung câu, không phải log truy vấn;
- đánh giá giá trị thị trường. Giá là giá chào bán trong tin;
- so trực tiếp với điểm của HCMRE-Q v1, vì kho tin, thang nhãn và định nghĩa vị trí khác nhau.

## 2. Thành phần

### 2.1 Kho tin (`data/corpus_attributes.csv`)

Có 6.703 tin, lấy từ `Data/v3/master_v3.csv` sau errata v3.1 (sha256 `5b65c94dabd2…`).

| | Số tin |
|---|---|
| Nguồn: chỉ crawl cũ | 2.846 |
| Nguồn: chỉ crawl 2026 | 3.673 |
| Nguồn: có ở cả hai | 184 |
| Loại: Nhà đất | 5.112, gồm nhà riêng 3.495, nhà mặt phố 1.043, biệt thự/liền kề 468, shophouse 106 |
| Loại: Căn hộ chung cư | 1.591 |
| Địa giới | 125 phường/xã mới; 35 quận/huyện cũ |
| Toạ độ tin cậy | 6.669 |
| Bị cờ `ward_coord_outlier` | 154 |
| Không có giá | 21 |
| Không rõ số phòng ngủ | 791 |

Các cột chính:

- khoá: `doc_id` (= `listing_id`, giữ nguyên khi nạp lại DB) và `source`;
- loại: `property_type`, `subtype`;
- vị trí: `ward` (phường mới), `former_area` (quận/huyện cũ), `lat`, `lon`, `coords_reliable`, `ward_coord_outlier`;
- thông số: `price` (tỷ), `area` (m²), `bedrooms`, `has_title`, `full_furniture`. Mỗi cột có cột `*_src` đi kèm,
  cho biết giá trị lấy từ trường dữ liệu hay từ văn bản;
- khoảng cách lái xe tới tiện ích gần nhất, 9 loại: `drive_<loại>_km`;
- khoảng cách chim bay tới 5 địa danh: `dist_<địa danh>_km`;
- 8 đặc điểm mô tả, kiểu True/False: `hem_xe_hoi`, `dong_tien`, `can_goc`, `nha_moi`, `view_song`,
  `thang_may_nha`, `san_vuon`, `ho_boi`.

### 2.2 Câu hỏi (`data/queries.jsonl`)

Mỗi dòng là một câu hỏi, với các trường:

- định danh: `qid`;
- phân loại: `split` (train/val/test), `family` (F1–F6), `style` (S1–S4), `frame_id`, `loc_kind` (ward /
  former_area / none);
- nội dung: `text` và `gold` (ràng buộc vàng);
- nguồn gốc: `seed_doc_id` (tin hạt giống);
- số tin theo mức: `n3`, `n2`, `n1`.

Ví dụ:

```json
{"qid": "v2q0001", "split": "train", "family": "F1_structured", "style": "S1", "loc_kind": "ward",
 "text": "Tìm căn hộ 2 phòng ngủ tại phường Cát Lái (quận 2 cũ) 9 - 12 tỷ",
 "gold": {"property_type": "Căn hộ", "price": {"min": 9.0, "max": 12.0}, "beds": {"kind": "exact", "value": 2},
          "location": {"kind": "ward", "value": "Phường Cát Lái", "with_former": "Quận 2"}},
 "seed_doc_id": 46233148, "n3": 7, "n2": 14, "n1": 3}
```

Phân bố câu hỏi:

| Chiều | Phân bố |
|---|---|
| Tập | train 600, val 200, test 200 |
| Họ | F1 cấu trúc 280; F2 cấu trúc+ 100; F3 tiện ích 200; F4 đặc điểm 240; F5 địa danh 80; F6 loại con 100 |
| Phong cách | S1 có dấu 280; S2 không dấu 209; S3 viết tắt 252; S4 hội thoại 259 |
| Vị trí | phường 704 (92 phường khác nhau); quận cũ 162 (23 khu vực); không nêu 134 |
| Loại | Nhà đất 688; Căn hộ 312. Có 100 câu nêu loại con: mặt phố 59, biệt thự/liền kề 29, shophouse 12 |
| Giá | 834 câu: "tối đa" 345, "khoảng" 321, "từ … đến" 168 |
| Ràng buộc khác | phòng ngủ 221; diện tích 88; có sổ 69; full nội thất 12 |
| Đặc điểm (240) | căn góc 42, nhà mới 38, dòng tiền 37, hẻm xe hơi 33, view sông 29, thang máy 24, hồ bơi 19, sân vườn 18 |
| Tiện ích (200) | trường 48, bệnh viện 32, công viên 29, chợ 23, siêu thị 18, TTTM 16, trạm buýt 14, metro 10, đại học 10 |
| Địa danh (80) | Làng ĐH Thủ Đức 30, Phú Mỹ Hưng 18, chợ Bến Thành 12, Landmark 81 11, sân bay Tân Sơn Nhất 9 |

### 2.3 Nhãn (`data/qrels.tsv`)

File theo định dạng TREC: `qid 0 doc_id grade`. Chỉ ghi các cặp có mức > 0, tổng 40.459 dòng; cặp không có trong
file là mức 0.

```
mức 3 = đúng loại ∧ đúng khu vực ∧ mọi ràng buộc mềm thoả
mức 2 = đúng loại ∧ đúng khu vực ∧ đúng MỘT ràng buộc mềm lệch trong dải dung sai
mức 1 = đúng loại ∧ sát khu vực (≤ 1 km tới lõi khu vực) ∧ mọi ràng buộc mềm thoả
mức 0 = còn lại
```

Ở đây "đúng loại" là thoả mọi ràng buộc cứng: loại, loại con, có sổ, full nội thất và đặc điểm. Dải dung sai và
định nghĩa lõi khu vực nằm ở PROTOCOL mục 3 và 5.

Số dòng theo mức: mức 1 có 14.991, mức 2 có 10.315, mức 3 có 15.153. Ở tập test, mỗi câu có trung bình 14,5 tin
mức 3, trung vị 10, ít nhất 1, nhiều nhất 50.

### 2.4 Các file khác

| Đường dẫn | Nội dung |
|---|---|
| `data/stats.json` | thống kê sinh dữ liệu: phân bố, khung câu theo tập, số tin liên quan |
| `snapshot/` | ảnh chụp dữ liệu phía hệ thống cho các baseline offline: `search_text`, bằng chứng tiện ích, điểm full-text của PostgreSQL. `manifest.json` ghi hash đầu vào và đầu ra |
| `results/` | kết quả các hệ thống offline và các phép kiểm D1–D5, B1–E1 |
| `human/` | bộ chấm tay H1–H5, công cụ chấm `annotate.html`, hướng dẫn, khoá, script phân tích, tự kiểm của AI |

## 3. Quy trình tạo

1. **Dữ liệu nguồn.** Gộp crawl cũ với crawl 2026, đổi địa giới sang phường mới, rồi sửa lỗi bằng errata v3.1. Bước
   này gom loại nhà, sửa 8 dòng đảo phường ↔ quận, 5 diện tích và 392 giá. Bằng chứng từng ô nằm trong
   `Data/v3/reports/v3_1_corrections.csv`.
2. **Bảng thuộc tính** (`corpus.py`):
   - lấy thuộc tính từ các trường có cấu trúc, và chỉ dùng văn bản khi trường trống;
   - khoảng cách tiện ích là quãng đường lái xe, đúng như cách backend lọc;
   - 8 đặc điểm mô tả được gán bằng regex có phủ định.
3. **Sinh câu hỏi** (`build_benchmark.py`):
   - mỗi câu bắt đầu từ một tin hạt giống có thật, nên luôn có ít nhất một tin mức 3;
   - dùng 4 phong cách × 12 khung câu; khung câu được chia riêng cho train, val và test;
   - hạn ngạch vị trí được chốt trước;
   - điều kiện trả lời được là `1 ≤ n3 ≤ 50` và `n(≥1) ≤ 200`.
4. **Gán nhãn** cho cả 6.703.000 cặp theo PROTOCOL mục 5. Bộ chấm lại `check_labels.py` được viết riêng và phải
   khớp 100% (A1).
5. **Kiểm định:** tự động (B1, B4, C1–C4, D1–D5, E1), cộng thêm bộ chấm tay H1–H5. Xem `META_EVAL.md`.

Seed của bộ sinh là 20261028. Mỗi bộ chấm tay có seed riêng, dạng `"20261029-<bộ>"`.

## 4. Cách dùng đúng

- **Thước đo chính:** nDCG@10 với gain `2^g − 1`, tính trên **tập test** (200 câu).
  - Báo cáo kèm khoảng tin cậy bootstrap 95%.
  - So hai hệ thống bằng kiểm định hoán vị ghép cặp, hiệu chỉnh Holm.
  - Script `eval_benchmark.py` và `run_live.py` làm sẵn các bước này.
- **Thước đo phụ:** P@10, MRR@10, Success@10 (chỉ tính mức 3), Recall@100 và WardP@10.
- **Chính sách mức:** mặc định là `ward_first`, tức tin trong phường lệch nhẹ xếp trên tin sát phường. Nếu phép kiểm
  A5 bằng người không đạt, thước đo chính chuyển sang `--grade-policy near_first`, và báo cáo cả hai.
- **Chỉ chỉnh tham số trên train/val.** Khung câu của test không xuất hiện ở hai tập này.
- **Đánh giá live:** cơ sở dữ liệu của backend phải ở v3.1. Nếu không, nhãn và dữ liệu hệ thống thấy sẽ khác nhau.
  `run_live.py` cảnh báo khi gặp `listing_id` lạ, và so bảng xếp hạng live với bản sao offline tương ứng
  (`META_EVAL.md` mục 4.3).

## 5. Giới hạn và thiên lệch

Chi tiết nằm ở `META_EVAL.md` mục 5 và 7. Tóm tắt:

- **Câu hỏi sinh từ khung.** Có 36 khung, distinct-2 = 0,26. Câu đa dạng về bề mặt nhưng vẫn ít hơn log thật. Mỗi
  câu thường có 2–4 ràng buộc.
- **Phân loại loại nhà thô.** "Nhà riêng / nhà phố / nhà" ứng với cả nhóm `Nhà đất`, gồm shophouse và biệt thự.
- **Đặc điểm gán bằng regex.** Bản tự kiểm của AI cho precision khoảng 0,97, nhưng độ sót cao ở "hẻm xe hơi" và
  "nhà mới".
- **Lỗi trong chính tin đăng**, như sai nhãn phường hay ghi "giá mồi", đi thẳng vào nhãn. 154 tin bị cờ
  `ward_coord_outlier`; phép D5 cho thấy bỏ chúng đi không đổi thứ hạng hệ thống.
- **Giá thiếu được coi là không thoả** ràng buộc giá. 21 tin rơi vào trường hợp này.
- **Vị trí** dùng địa giới phường mới. Tên phường trùng tên quận cũ luôn có tiền tố "phường/P.". 15% câu S1, S2,
  S4 nêu kèm quận cũ.
- **Phân bố không đều.** 57% tin đến từ crawl 2026. Một số phường có rất ít tin, và chỉ phường có ≥ 10 tin mới
  được làm hạt giống.

## 6. Quyền riêng tư và nguồn

- Tin đăng là dữ liệu công khai, được thu thập cho mục đích nghiên cứu của đồ án. Số điện thoại trong mô tả đã bị
  che một phần ở nguồn, ví dụ "0909 456 \*\*\*".
- Bộ dữ liệu không chứa thông tin người dùng nào.
- Trước khi công bố rộng rãi, cần xem lại điều khoản sử dụng của các trang nguồn.

## 7. Tái lập và hash

Chạy lại từ đầu theo `README.md`. Đầu vào:

```
Data/v3/master_v3.csv (sau errata v3.1)            5b65c94dabd25a89f4b878c7b8e84948bf86b51da4394513f1bda19e5e82942d
Data/v3/postgres/properties_v3.csv                  6c35c12d0ba48d227f1ff2dfcc3683f2be055f31d9cd9e7ba521416775a25033
Data/v3/postgres/listing_amenity_distances_v3.csv   f770a1f0933a2b226396112afdeb7205d6f7bb57abff7e6a28e090fc8f083a14
```

Đầu ra. Các hash này trùng nhau với cả 3 giá trị `PYTHONHASHSEED` (phép kiểm E1):

```
data/queries.jsonl          4084fdf1d94871c98d8c19a02cbf0fce784978bc5a6b875a1c946894efad8d57
data/qrels.tsv              7e2ab59c99ae1892ec0831df790f97c68852b12e63dbced23db52908c50c694f
data/corpus_attributes.csv  55b9e4911812437e0ff3532a685b17e8cb98b0a2214d5e9b1b7f02f87131b21c
data/stats.json             02a5b2a7d7df7d4ca51e6ce1247143f0c314829f24ca4e0903f7c1924a26f186
```

Kết quả các hệ thống offline và bộ chấm tay. Các file này cũng trùng từng byte giữa các lần chạy. Ngày 29/10,
`summary.json` có thêm khoá `today` (PROTOCOL 9.8); mọi số trong đó và các file còn lại giữ nguyên:

```
results/summary.json                  7bf4baaf656d00ecc008a0619196087118dd3669891c30be6924312d2a939918
results/per_query_metrics.csv         78dc258e0f264192e91ad610708d6f6d2925d6c878fc5e2ad6a495f9f0fc3ed3
results/reliability.json              1c1d5a8b59ed5421895546d3bea793c183ac10bf9bf0012139f92a6bcfa7183d
results/runs.jsonl.gz                 0bfad8466d4b482c7708dfa8d195533f63a1230e9f5a60f18955ccd8cfa88805
human/tasks/H1_aspects.csv            5349472ad75c40e6c6adb269db395a7d7f33034a2416acaf55c0bbef1e7aa297
human/tasks/H2_queries.csv            fd174858f53fb1967613b796b4e37dfd99865640057b6be5e4c0b9cf7d5d179c
human/tasks/H3_graded_pairs.csv       c177622437c920758491bc0018dde7f3e5f6f99076e9958e92cc0992196c3b2a
human/tasks/H4_ward_priority.csv      2488a403638983b9ba4b4ed4aefb4696b47114297afc1f29401bc69c7c3dd454
human/tasks/H5_price_corrections.csv  4917503cbfb3e88a6eaafcedeb01d767d910c0d08d1c6c2d0974139ea9696b55
```

Môi trường đo các hash trên: Linux x86-64, Python 3.13.16, numpy 2.5.3, pandas 3.0.5, scipy 1.18.1, scikit-learn
1.9.1. Trên nền tảng hoặc thư viện khác, số thực có thể lệch ở chữ số rất nhỏ, làm hash đổi. Khi đó hãy kiểm bằng
`check_labels.py` (A1) và so các metric thay vì so hash.

## 8. Bảo trì

- Mọi thay đổi ở dữ liệu nguồn, hàm gán nhãn hay bộ sinh câu đều tạo một **phiên bản mới**, với hash mới và một
  mục mới trong nhật ký sai lệch.
- Kết quả của các phiên bản khác nhau không được trộn với nhau.
- Kết quả chấm tay được thêm vào `human/answers/`. Kết luận của chúng được ghi vào `META_EVAL.md` và
  `PROTOCOL.md` mục 9.
