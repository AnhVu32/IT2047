# HCMRE-Q v2 — Giao thức (đăng ký trước khi sinh dữ liệu)

Ngày chốt: 28/10/2026. File này được viết **trước** khi sinh truy vấn và nhãn. Mọi tham số, ngưỡng chấp
nhận và quy tắc ra quyết định dưới đây được cố định từ đầu. Nếu sau khi xem kết quả mà phải đổi một điểm nào,
thay đổi đó được ghi vào mục 9 (nhật ký sai lệch), kèm lý do. Không âm thầm sửa nội dung các mục 1–8.

## 1. Mục tiêu và nguyên tắc

HCMRE-Q v2 đo chất lượng **tìm kiếm tin bán bất động sản bằng câu tiếng Việt tự do** trên toàn bộ dữ liệu
gộp `Data/v3` (6.703 tin). Địa giới dùng là **phường/xã mới (sau 1/7/2025)**. Benchmark ưu tiên đúng phường:
một tin trong phường người dùng nêu luôn được xếp trên tin ở ngoài phường.

Nguyên tắc liêm chính (giữ nguyên từ v1):

1. **Nhãn độc lập với hệ thống.** Nhãn chỉ tính từ thuộc tính tin đăng, khoảng cách thực đo và hàm gán nhãn đã
   kiểm định. Code sinh nhãn không import gì từ `backend/`. Bước kiểm tra C3 (mục 7) xác nhận điều này.
2. **Câu hỏi không viết theo parser.** Mẫu câu và từ vựng được soạn từ cách người dùng gõ, không đọc
   `query_parser.py` hay `normalizer.py`.
3. **Nhãn toàn bộ, không gộp pool.** Mỗi truy vấn được chấm cho **cả 6.703 tin**. Vì vậy không có thiên lệch
   pool như các bộ chấm dựa trên kết quả của vài hệ thống.
4. **Tái lập được.** Seed cố định. Kết quả không phụ thuộc `PYTHONHASHSEED`. Hash của đầu vào và đầu ra được ghi
   trong dataset card.

## 2. Tiền điều kiện: dữ liệu v3.1

Nhãn tính trên `Data/v3/master_v3.csv` **sau** khi chạy `Data/v3/pipeline/fix_v3_quality.py --apply`
(sha256 `5b65c94dabd2…`; bản errata đầu tiên `741002081f0f…` đã được sửa lại, xem mục 9). Errata v3.1 sửa các lỗi
sau:

- 3.857 `property_type` chi tiết được gom về hai nhóm app dùng.
- 8 dòng bị đảo phường ↔ quận cũ.
- 5 diện tích sai.
- 392 giá bán. Đây là các tin crawler lấy nhầm số đầu tiên của tiêu đề, ví dụ số tiền giảm, tiền thuê, đơn giá/m²
  hoặc giá cũ, hoặc làm rơi phần "tỷ 750".

Bằng chứng từng ô nằm ở `Data/v3/reports/v3_1_corrections.csv`. Bộ trích giá từ văn bản được thẩm định
trên dữ liệu cũ, vốn có giá do một quy trình khác nhập. Trên 2.596 tin cũ mà bộ trích tìm được giá, có 99,2% khớp
giá đã lưu. Độ chính xác của chính các sửa đổi được kiểm bằng người ở bộ H5.

## 3. Bảng thuộc tính phía nhãn (`corpus.py`)

`doc_id` = `listing_id`. Khoá này giữ nguyên dù nạp lại cơ sở dữ liệu, khác với `properties.id`.

| Thuộc tính | Nguồn chính | Khi nguồn chính trống (ghi cờ `*_src = text`) |
|---|---|---|
| `property_type` | cột v3.1 (`Căn hộ` / `Nhà đất`) | — |
| `subtype` | `Folder` (Nhà riêng, Căn hộ chung cư, Nhà mặt phố, Biệt thự/Liền kề, Shophouse) | — |
| `ward`, `former_area` | `district`, `former_admin_area` | — |
| `price` (tỷ) | `price_range` | giá nêu rõ trong tiêu đề/mô tả (`price_text.stated_price`) |
| `area` (m²) | `area` | — |
| `bedrooms` | `bedrooms` | đúng **một** giá trị "N PN / N phòng ngủ" (1–10) trong văn bản |
| `has_title` (có sổ) | `legal_status` chuẩn hoá: sổ hồng/sổ đỏ/có sổ → 1; chờ sổ/HĐMB/vi bằng/giấy tay → 0 | từ khoá trong văn bản, có phủ định |
| `full_furniture` | `furnishing` chuẩn hoá: đầy đủ/full/cao cấp → 1; cơ bản/không/thô → 0 | từ khoá trong văn bản, loại "cơ bản" |
| `drive_<cat>_km` | **min** quãng đường lái xe trong 5 tiện ích gần nhất của loại đó (`listing_amenity_top5_edges.csv`). Backend lọc theo đúng nghĩa này (`EXISTS … driving_distance_km <= x`) | trống = không có tiện ích loại đó trong bán kính tìm |
| `dist_<landmark>_km` | haversine từ toạ độ tin tới 5 địa danh của v1 | trống nếu toạ độ không tin cậy |
| 8 đặc điểm mô tả | hàm gán nhãn (regex có phủ định) của v1, kiểm định lại trên v3 (H1) | — |

**Toạ độ tin cậy** gồm các trạng thái `coordinate_status` sau: `original_valid`, `corrected_by_exact_address`,
`corrected_by_folder`, `imputed_exact_address`, `imputed_same_listing_id`. Hai trạng thái
`original_out_of_region` và `imputed_by_ward_centroid` bị loại khỏi mọi phép tính khoảng cách.

**Lõi của một khu vực** (phường hoặc quận cũ) là các tin có toạ độ tin cậy, gán nhãn khu vực đó, và không phải
điểm ngoại lai:

```
c        = (trung vị vĩ độ, trung vị kinh độ) của các tin trong khu vực
d_i      = haversine(tin i, c)
MAD      = trung vị |d_i − trung vị(d)|
lõi      = { i : d_i ≤ max(2,0 km ; trung vị(d) + 5 × 1,4826 × MAD) }
           (khu vực có < 5 tin tin cậy: lõi = mọi tin tin cậy)
gần(L, A) = L không thuộc A, L có toạ độ tin cậy, và min_{j ∈ lõi(A)} haversine(L, j) ≤ 1,0 km
```

Tin gán nhãn phường W nhưng nằm ngoài lõi của W được ghi cờ `ward_coord_outlier`. Benchmark vẫn coi tin đó thuộc
W, vì nhãn phường lấy từ địa chỉ và cũng là thứ hệ thống lọc theo. Số tin bị cờ được báo cáo, và có một phép phân
tích độ nhạy loại bỏ các tin này.

## 4. Truy vấn

### 4.1 Họ truy vấn và số lượng

Tổng cộng 1.000 câu. Mỗi họ được chia train/val/test theo tỉ lệ 60/20/20.

| Họ | Số câu | Ràng buộc | Vị trí: phường / quận cũ / không nêu |
|---|---|---|---|
| F1 cấu trúc | 280 | loại + vị trí + giá, có thể kèm phòng ngủ | 0,80 / 0,20 / 0 |
| F2 cấu trúc+ | 100 | F1 + 1–2 trong số: diện tích tối thiểu, có sổ, full nội thất | 0,80 / 0,20 / 0 |
| F3 tiện ích | 200 | loại + "gần" hoặc "cách ≤ x" một trong 9 loại tiện ích, có thể kèm giá | 0,75 / 0,15 / 0,10 |
| F4 đặc điểm | 240 | loại + một đặc điểm mô tả, có thể kèm giá và phòng ngủ | 0,75 / 0,15 / 0,10 |
| F5 địa danh | 80 | loại + gần một trong 5 địa danh, có thể kèm giá và phòng ngủ | 0 / 0 / 1 |
| F6 loại con | 100 | nhà mặt phố / biệt thự-liền kề / shophouse, có thể kèm giá và diện tích | 0,70 / 0,20 / 0,10 |

Theo kỳ vọng, khoảng 70% câu nêu phường, và khoảng 80% số câu có nêu địa điểm là nêu phường.

### 4.2 Hạt giống và điều kiện trả lời được

- Mỗi câu sinh từ một tin hạt giống có thật, nên luôn có ít nhất một tin đạt mức 3.
- Phường được làm hạt giống khi có ≥ 10 tin (93 phường). Quận cũ được làm hạt giống khi có ≥ 20 tin (27 khu vực).
- Câu có ràng buộc giá thì hạt giống phải có giá ≥ 1 tỷ.
- **Điều kiện trả lời được** là `1 ≤ n3 ≤ 50` và `n(≥1) ≤ 200`. Ở đây `n3` là số tin mức 3. Câu không đạt thì
  sinh lại.

### 4.3 Bề mặt câu chữ

- Có 4 phong cách, với tỉ trọng như sau:
  - S1, chuẩn có dấu: 0,30.
  - S2, không dấu: 0,20.
  - S3, viết tắt/teencode: 0,25.
  - S4, hội thoại: 0,25.
- Mỗi phong cách có 12 khung câu, chia 7 / 2 / 3 khung cho train / val / test. S2 dùng khung của S1.
- Cách viết phường được chọn như sau:
  - Các dạng có thể dùng là "phường X", "P. X", "P.X" và "xã X".
  - Viết trần "X" chỉ được dùng khi tên X **không trùng** tên một quận/huyện/thành phố cũ.
  - Có 17 tên trùng, ví dụ Phường Tân Bình ↔ Quận Tân Bình và Phường Thủ Đức ↔ TP Thủ Đức. Với các tên này,
    tiền tố phường/xã là bắt buộc.
- Với S1, S2 và S4, 15% câu nêu phường kèm thêm quận cũ, ví dụ "phường Bàn Cờ (quận 3 cũ)". Vị trí vàng của các
  câu này vẫn chỉ là phường.
- Quận cũ được viết là "quận 3", "Q3", "quận 3 cũ", "quận Tân Bình" và "TP Thủ Đức". Truy vấn "TP Thủ Đức" chấp
  nhận cả ba nhãn Thành Phố Thủ Đức, Quận 2 và Quận 9.

## 5. Nhãn liên quan (0–3)

Ràng buộc chia làm ba nhóm:

- **Cứng:** loại, loại con, có sổ, full nội thất và đặc điểm. Thiếu dữ liệu thì tính là không thoả.
- **Vị trí:** đúng khu vực, gần (mục 3), hoặc khác.
- **Mềm có dải dung sai:** thiếu dữ liệu thì không thoả và cũng không nằm trong dải.

```
giá  ≤ M          : thoả p ≤ M                 | trong dải M < p ≤ 1,15·M
giá  khoảng T     : thoả |p−T| ≤ 0,10·T        | trong dải |p−T| ≤ 0,20·T
giá  từ L đến H   : thoả L ≤ p ≤ H             | trong dải 0,85·L ≤ p ≤ 1,15·H
diện tích ≥ A     : thoả a ≥ A                 | trong dải a ≥ 0,85·A
phòng ngủ đúng b  : thoả = b                   | trong dải = b+1
phòng ngủ ≥ b     : thoả ≥ b                   | trong dải = b−1
tiện ích ≤ D km   : thoả d ≤ D                 | trong dải d ≤ 1,5·D
địa danh ≤ D km   : thoả d ≤ D                 | trong dải d ≤ 1,5·D
```

Bán kính ngầm định của "gần X" giữ như v1. Trường hợp tiện ích, dùng quãng đường lái xe:

- 1 km cho trường, chợ, siêu thị, công viên.
- 0,5 km cho trạm xe buýt.
- 2 km cho bệnh viện, TTTM, metro, đại học.

Trường hợp địa danh, dùng đường chim bay: 2 km, riêng sân bay và làng đại học là 3 km.

Ngưỡng ghi rõ trong câu nằm trong bán kính tìm tiện ích:

- Metro: 1, 2 hoặc 3 km.
- Trạm xe buýt: 0,3, 0,5 hoặc 1 km.
- Bệnh viện, TTTM, đại học: 1, 2 hoặc 3 km.
- Các loại khác: 0,3 đến 2 km.

Với câu có nêu vị trí:

```
mức 3 = cứng thoả  ∧ đúng khu vực ∧ mọi ràng buộc mềm thoả
mức 2 = cứng thoả  ∧ đúng khu vực ∧ đúng MỘT ràng buộc mềm nằm trong dải, còn lại thoả
mức 1 = cứng thoả  ∧ gần khu vực  ∧ mọi ràng buộc mềm thoả
mức 0 = còn lại
```

Câu không nêu vị trí chỉ có mức 3, 2 và 0, với định nghĩa như trên nhưng bỏ điều kiện vị trí.

**Ưu tiên phường.** Một tin trong phường hơi lệch một ràng buộc mềm (mức 2) được đặt **trên** một tin sát
phường thoả mọi ràng buộc (mức 1). Đây là một giả định về người dùng, và được kiểm bằng người ở H4. Quy tắc quyết
định nằm ở mục 7, A5.

## 6. Thước đo

- **Chính:** nDCG@10 với gain `2^g − 1` (7, 3, 1, 0), trên tập **test** (200 câu).
- **Phụ:**
  - P@10, MRR@10 và Success@10, trong đó chỉ tính mức 3 là liên quan (thước đo nghiêm).
  - Recall@100 trên các tin mức 3.
  - WardP@10, chỉ áp dụng cho câu nêu phường: tỉ lệ 10 kết quả đầu nằm đúng phường. Thước đo này đo riêng khả
    năng tôn trọng phường, không xét các ràng buộc khác.
- **Báo cáo:** trung bình, kèm khoảng tin cậy bootstrap 95% (10.000 lần lấy mẫu lại theo truy vấn). So sánh hai
  hệ thống dùng kiểm định hoán vị ghép cặp hai phía (10.000 hoán vị) và hiệu chỉnh Holm.
- **Phân rã:** theo họ, theo phong cách, theo loại vị trí (phường / quận cũ / không nêu) và theo nguồn tin
  (cũ / mới).

## 7. Đánh giá chính bộ dữ liệu (meta-evaluation) và ngưỡng chấp nhận

Bộ dữ liệu chỉ được dùng để báo cáo khi đạt **mọi** ngưỡng có dấu ✱. Các mục khác chỉ cần báo cáo.

**A. Độ đúng của nhãn**

| Mã | Kiểm tra | Ngưỡng |
|---|---|---|
| A1 ✱ | Viết lại hàm chấm độc lập (`check_labels.py`, chỉ dựa vào file này) và so với qrels trên toàn bộ cặp (truy vấn, tin) | khớp 100% |
| A2 ✱ | H1: lấy 12 tin dương tính ngẫu nhiên cho mỗi đặc điểm (8 × 12 = 96, chia đều tin cũ/mới) để người chấm | Precision gộp ≥ 0,90, cận dưới Wilson 95% ≥ 0,80. Đặc điểm nào sai > 3/12 thì bị loại khỏi F4 và F4 được sinh lại |
| A3 | H1r: lấy 12 tin âm tính nhưng có từ khoá lỏng cho mỗi đặc điểm, để ước lượng tỉ lệ sót | báo cáo |
| A4 ✱ | H3: chọn 30 câu ở tập test. Mỗi câu lấy 5 tin: 1 tin mỗi mức 3/2/1 nếu có, 1 tin mức 0 cùng khu vực, và 1 tin mức 0 nhưng được BM25 xếp cao. Người chấm 0–3 mà không thấy nhãn tự động | κ có trọng số bậc hai (người vs nhãn) ≥ 0,60. Tỉ lệ tin mức 0 bị người chấm ≥ 2 (âm tính giả) chỉ báo cáo |
| A5 ✱ | H4: 60 cặp cho câu nêu phường. Mỗi cặp gồm A (đúng phường, lệch đúng 1 ràng buộc mềm, mức 2) và B (sát phường, thoả hết, mức 1). Người chấm chọn tin phù hợp hơn | Chấp nhận chính sách ưu tiên phường khi tỉ lệ chọn A ≥ 0,70 **và** kiểm định dấu một phía có p < 0,05. Nếu không đạt: đổi chỗ mức 1 ↔ 2 cho thước đo chính, đồng thời báo cáo cả hai |
| A6 ✱ | H5: 60 sửa đổi giá ngẫu nhiên của errata v3.1, phân tầng R1/R2/thủ công | ≥ 0,95 đúng, cận dưới Wilson ≥ 0,85 |

**B. Độ đúng của câu hỏi**

| Mã | Kiểm tra | Ngưỡng |
|---|---|---|
| B1 ✱ | Kiểm tra khứ hồi tự động: một bộ đọc độc lập (không phải bộ sinh) tìm lại trong câu mọi giá trị vàng (tên khu vực, số tiền, số phòng, khoảng cách, từ khoá loại/đặc điểm) | 100% câu đạt |
| B2 ✱ | H2: 100 câu ngẫu nhiên phân tầng theo phong cách. Người chấm đánh giá câu có diễn đạt **đúng và đủ** các ràng buộc vàng không | ≥ 0,95 |
| B3 | H2: độ tự nhiên, thang 1–5 | ≥ 80% câu đạt ≥ 3, báo cáo theo phong cách |
| B4 | Độ đa dạng: distinct-1/2, số khung câu, phân phối độ dài | báo cáo |

**C. Tính toàn vẹn của phép chia tập**

| Mã | Kiểm tra | Ngưỡng |
|---|---|---|
| C1 ✱ | Không có qid hay tin hạt giống dùng chung giữa các tập, không có khung câu của test xuất hiện ở train/val, không có câu trùng hệt | 0 vi phạm |
| C2 | Câu gần trùng giữa các tập (Jaccard 3-gram ký tự ≥ 0,9) | ≤ 1% |
| C3 ✱ | Code sinh câu và nhãn không import `backend` (kiểm tra tĩnh) | đạt |
| C4 | χ² của phân phối họ, phong cách và loại vị trí theo tập | báo cáo p |

**D. Độ tin cậy khi dùng để so sánh hệ thống**

Các kiểm tra dưới đây dùng các hệ thống offline: random, BM25, BM25 không dấu, TF-IDF n-gram ký tự, PostgreSQL
FTS, bản sao pipeline production không có DL (có và không có graph), BM25 + ranker, và oracle dùng ràng buộc vàng.

| Mã | Kiểm tra | Ngưỡng |
|---|---|---|
| D1 ✱ | Kiểm tra hợp lý trên test: oracle ≥ 0,90, random ≤ 0,05, thứ tự oracle > hệ thống tốt nhất > random | đạt |
| D2 | Sức phân biệt: tỉ lệ cặp hệ thống khác nhau có ý nghĩa (hoán vị ghép cặp, Holm, α = 0,05) | báo cáo |
| D3 ✱ | Độ ổn định khi chia đôi: Kendall τ trung bình giữa thứ hạng hệ thống trên hai nửa test ngẫu nhiên, 1.000 lần | ≥ 0,80 |
| D4 ✱ | Nhiễu nhãn: τ giữa thứ hạng gốc và thứ hạng khi 10% nhãn khác 0 bị dịch ±1 ngẫu nhiên (trung bình 200 lần) | ≥ 0,80 |
| D5 | Độ nhạy tham số: τ khi ngưỡng "gần" là 0,5/1,5 km, khi dải dung sai ×0,5/×1,5, khi đổi chỗ mức 1 ↔ 2, và khi loại tin `ward_coord_outlier` | báo cáo |

**E. Tái lập**

| Mã | Kiểm tra | Ngưỡng |
|---|---|---|
| E1 ✱ | Sinh lại hai lần với `PYTHONHASHSEED` = 0, 1 và 12345 | hash mọi file đầu ra trùng nhau |

## 8. Những điều benchmark không đo

- Giá trị nhãn phản ánh **dữ liệu đăng tin**. Nếu người đăng ghi sai phường hoặc sai giá trong chính tin đăng thì
  nhãn sai theo. H5 và cờ `ward_coord_outlier` đo được một phần lỗi này.
- Đặc điểm mô tả được gán bằng regex. Độ sót (A3) có thể làm một số tin đúng bị chấm 0. A4 ước lượng tỉ lệ
  âm tính giả ở phần đầu danh sách xếp hạng.
- Câu hỏi được sinh từ khung. Benchmark đo khả năng hiểu ràng buộc trong câu tự nhiên, nhưng không thay được log
  truy vấn thật.

## 9. Nhật ký sai lệch so với giao thức

Mọi thay đổi sau ngày chốt được ghi ở đây, kèm ngày và lý do.

- Mục 1–4 diễn ra **trước** khi có bất kỳ kết quả hệ thống nào.
- Mục 5–7 diễn ra khi đã có điểm baseline của bản dựng trước.
  - Mục 5 chỉ dựa trên việc đọc nhãn và câu chữ. Ảnh hưởng của nó lên điểm được ghi ở cuối mục.
  - Mục 6 và 7 không đổi nhãn hay câu hỏi, chỉ đổi công cụ phân tích và mẫu chấm tay.
- Mục 8 và 9 diễn ra sau khi công bố. Chúng chỉ đổi công cụ; không nhãn, câu hỏi hay số nào đã công bố thay đổi.

Không thay đổi nào được chọn dựa trên điểm của hệ thống.

1. **28/10 — một phủ định thêm cho hàm gán nhãn `san_vuon`.** Khi đọc mẫu tin của crawl 2026 trước khi sinh dữ
   liệu, phát hiện các câu dạng "có thể làm biệt thự nghỉ dưỡng sân vườn" và "phù hợp mở cafe sân vườn" bị gán
   dương tính sai. Đã thêm phủ định cho dạng "(có thể | phù hợp | thích hợp | để | nên) (làm | xây | mở | cải tạo)
   … sân vườn". Các đặc điểm khác giữ nguyên như v1.
2. **28/10 — dùng hạn ngạch thay cho xác suất khi chọn loại vị trí.** Mục 4.1 cho tỉ lệ phường / quận cũ / không
   nêu theo từng họ. Lần sinh thử đầu tiên rút loại vị trí theo xác suất. Vì điều kiện trả lời được loại bỏ câu
   theo quận cũ nhiều hơn câu theo phường, tỉ lệ thực tế bị lệch thành 79% câu nêu phường. Bản cuối chia **hạn
   ngạch đúng** theo tỉ lệ ở mục 4.1, bằng phương pháp phần dư lớn nhất cho từng họ × tập: 704 câu nêu phường, 162
   câu nêu quận cũ, 134 câu không nêu.
3. **28/10 — phép kiểm tra B1 phát hiện câu sinh ra có thể đọc sai.** Ví dụ "giá không quá sáu tỷ ba phòng ngủ"
   có thể đọc thành 6,3 tỷ. Bộ sinh câu nay chèn dấu phẩy khi số tiền đứng ngay trước một con số khác. Lần sinh thử
   đầu tiên có 27 câu như vậy; bản cuối đạt B1 100%.
4. **28/10 — sửa lại errata v3.1 sau khi tự kiểm trước bộ H5.** Trước khi giao bộ chấm tay, trợ lý AI đọc thử 60
   mẫu H5 của bản errata đầu tiên. Kết quả: 8/60 sửa đổi sai, tức 86,7%, dưới ngưỡng A6 là 95%.
   - **Nguyên nhân chính:** luật R2 xoá giá cả khi văn bản nêu *nhiều* giá, ví dụ "Giá chào 175 tỷ, giá kỳ vọng
     giao dịch 155 tỷ". Bộ trích giá cũng đọc sai vài cụm: "giá mới", "giá cắt lỗ", "giá giao dịch thực tế",
     "16,5 tỷ giảm 13,7 tỷ" và "nhỉnh 7 tỷ … nay còn 7,89 tỷ".
   - **Đã sửa:**
     - R2 chỉ áp dụng khi văn bản không nêu giá nào.
     - Tin nêu nhiều giá được quyết định bằng tay; thêm 1 tin vào `MANUAL_PRICE`.
     - Không sửa khi số crawler đọc được chính là một giá văn bản nêu rõ.
     - Bộ trích giá xử lý thêm các cụm trên; bộ tự kiểm `price_text.py` có 58 ca.
   - **Kiểm lại:** sau khi sửa, trợ lý đọc **toàn bộ** các sửa đổi R1 và R2 kèm các câu có giá trong tin, không
     chỉ một mẫu. Lần đọc này tìm thêm **2 lỗi** và đã sửa trước khi chốt:
     - tin 46019267: giá đúng là 10,5 tỷ ("… giảm tiếp 10.5 tỷ");
     - tin 46305106: giữ nguyên giá đã lưu là 18 tỷ, vì lần sửa đầu là sai.

     Sau cùng có 371 sửa đổi R1, 13 sửa đổi R2 và 8 sửa thủ công. *(Đính chính ngày 28/10: bản trước của mục này
     ghi nhầm là "không thấy lỗi".)*
   - **Kiểm bằng người:** bộ H5 dùng cho kiểm định bằng người được rút **lại** từ bản errata cuối, nên con số A6
     chính thức không dựa trên mẫu 60 tin đã dùng để sửa. *(Bổ sung ngày 28/10:)* vì trợ lý đã đọc toàn bộ sửa đổi
     R1 và R2, A6 đo tỉ lệ lỗi **còn sót** sau lần đọc đó, theo đánh giá của người.
   - **Kết quả:** errata mới có 392 giá, 13 giá bị xoá (trước là 20), và master_v3 có sha256 `5b65c94dabd2…`.
5. **28/10 — sửa sau khi trợ lý AI tự kiểm bản nháp của kit chấm tay.** Trước khi giao kit, trợ lý đọc bản nháp
   của H1 (96 tin), H1r (96 tin) và H2 (100 câu). Các lỗi tìm được dẫn tới những thay đổi dưới đây.
   - **(a) Câu chữ: 138 câu đổi chữ, nghĩa giữ nguyên.** H2 cho thấy một số cách viết gượng. Đã sửa bộ sinh như
     sau:
     - hai đầu một khoảng giá viết cùng kiểu, cùng dấu thập phân và cùng dạng chữ/số;
     - bỏ các nối từ thừa như "trong tầm khoảng …", "ở … ở", "nào một …";
     - câu tiện ích viết tự nhiên hơn và có mục đích, ví dụ "có trường học trong vòng 1 km cho con đi học";
     - cụm "dòng tiền" và "nhà mới" nói rõ nghĩa "đang có thu nhập cho thuê" và "mới xây".

     Cách sửa **không đổi dòng số ngẫu nhiên**: một lựa chọn bị ép vẫn rút đúng số lần như trước. Vì vậy hạt
     giống, ràng buộc vàng và qrels giữ nguyên.
   - **(b) Hàm gán nhãn đặc điểm.** Bản nháp H1 có 10/96 tin sai, tức precision 0,896:

     | Đặc điểm | Số tin sai |
     |---|---|
     | dòng tiền | 5/12 |
     | sân vườn | 2/12 |
     | căn góc | 1/12 |
     | thang máy | 1/12 |
     | view sông | 1/12 |

     Nếu đây là lần kiểm chính thức A2 thì "dòng tiền" đã bị loại. Đây chỉ là bản nháp do AI đọc, nên hàm gán
     nhãn được sửa rồi kiểm lại trên mẫu **mới**. Những thay đổi:

     | Đặc điểm | Thay đổi | Số tin dương tính |
     |---|---|---|
     | dòng tiền | Định nghĩa lại là căn nhà *đang* tạo thu nhập (đang cho thuê, có HĐT, nêu thu nhập hay doanh thu hiện có), hoặc bản thân là CHDV/nhà trọ. Thêm phủ định cho "phù hợp / có thể / tiện … làm CHDV", "dự kiến / ước tính / tiềm năng … thu nhập", "CTXD / GPXD … CHDV", "phương án / thiết kế CHDV … có thể" | 1.233 → 1.018 |
     | căn góc | Với căn hộ, chỉ tính khi chính căn là căn góc, không tính "dự án nằm trên 2 mặt tiền" | 792 → 777 |
     | view sông | Phủ định "ra bờ kè / công viên … view sông" | 264 → 263 |
     | thang máy | Phủ định "thuận tiện / có thể / chừa ô … lắp thang máy" | 424 → 423 |
     | sân vườn | Phủ định mở rộng sang "nhà vườn", "lý tưởng / tiện làm sân vườn" | 145 → 142 |

     Mỗi bản thử được so với bản cũ trên toàn bộ kho tin, đọc danh sách tin thêm và bớt. "Dòng tiền" được kiểm
     thêm bằng 3 mẫu phát triển, mỗi mẫu 30 tin; mẫu cuối đúng 30/30. Các mẫu phát triển rút từ những tin ngoài
     bản nháp của kit. Việc loại chúng khỏi kit chính thức chỉ được làm đầy đủ ở mục 7.
   - **(c) Hướng dẫn chấm.** Bảng H1 trong `GUIDELINES.md` và mô tả đặc điểm trong kit nay ghi rõ ranh giới:
     - "dòng tiền" tính cả CHDV/nhà trọ đang để trống, không tính "phù hợp / có thể / dự kiến";
     - "căn góc" của căn hộ chỉ xét chính căn đó;
     - "hẻm xe hơi" tính cả nhà mặt đường ô tô;
     - "hồ bơi" tính cả hồ bơi nội khu dự án;
     - thêm ví dụ âm tính cho view sông, thang máy và sân vườn.
   - **(d) Mẫu chấm tay mới, tách khỏi mẫu phát triển.**
     - Mỗi bộ H1–H5 có dòng ngẫu nhiên riêng, seed `"20261029-<bộ>"`. Nhờ vậy rút lại một bộ không làm đổi bộ khác.
     - Các mục trợ lý đã đọc bị loại khỏi mẫu mới: 93 tin H1, 96 tin H1r và 100 câu H2. Danh sách nằm trong
       `human/preaudit_items.json`.
   - **(e) Lỗi ràng buộc phòng ngủ.** Khi sinh lại, một khẳng định nội bộ báo hạt giống 45881981 không đạt mức 3.
     Nguyên nhân: F4/F5 viết "đúng 4 phòng ngủ" cho hạt giống có hơn 4 phòng. Đã sửa: hạt giống có hơn 4 phòng thì
     ràng buộc là "≥ 4".
   - **(f) Biên dung sai và số thực.** Khi rà lại, phát hiện phép so sánh ở đúng biên bị sai do số thực nhị phân.
     Ví dụ |4,4 − 4,0| / 4,0 = 0,10000000000000009 > 0,10, hay 1,15 × 20 = 22,999999999999996. Các biên ở mục 5 là
     biên **đóng**, nên đã sửa như sau:
     - bộ sinh cộng ε = 10⁻⁹ vào mọi biên;
     - bộ kiểm A1 so sánh sau khi làm tròn 9 chữ số.

     Điều kiện trả lời được đổi ở vài câu, nên 37 câu được sinh lại: 28 câu F2, 8 câu F1 và 1 câu F3. A1 vẫn khớp
     100%.
   - **(g) Đóng băng.** Từ commit `f0d285a`, hàm gán nhãn, bộ sinh câu và hướng dẫn chấm được đóng băng. Không
     chỉnh tiếp dựa trên bất kỳ mẫu nào của kit chính thức, kể cả bản tự kiểm của AI ở mục 6.
   - **Ảnh hưởng lên điểm hệ thống.** Ghi ra để minh bạch, không dùng để chọn thay đổi. So nDCG@10 test của 9 hệ
     thống offline trước và sau mục 5:
     - thứ tự các hệ thống không đổi;
     - chênh lệch tuyệt đối lớn nhất là 0,0087, ở bm25: 0,1507 → 0,1420.
6. **28/10 — công cụ phân tích và bản tự kiểm của AI trên kit chính thức.**
   - **Khoá H4** có thêm cột `in_ward_off`. Cột này cho biết ràng buộc mềm mà tin trong phường bị lệch, kèm chiều
     lệch, và được tính bằng `check_labels.py`. Cột không rút số ngẫu nhiên, nên mọi mẫu giữ nguyên byte. Phân rã A5
     theo cột này chỉ là **thăm dò**, không thay luật quyết định A5.
   - **`analyze_human.py`** có thêm:
     - tham số `--out` và `--title`, để báo cáo tự kiểm không ghi đè báo cáo chính thức;
     - ma trận nhầm lẫn và danh sách các cặp lệch lớn cho A4;
     - kết quả thăm dò của A4 và A5 khi bỏ các tin thuộc danh sách `lf_dev` (mục 7).
   - **`eval_benchmark.py` và `run_live.py`** có thêm `--grade-policy near_first`. Tham số này thực hiện đúng luật
     dự phòng của A5: đổi chỗ mức 1 ↔ 2 cho thước đo chính và báo cáo cả hai.
   - **`eval_benchmark.py` tự chạy với `PYTHONHASHSEED=0`**, và ghi `runs.jsonl.gz` không kèm dấu thời gian.
     - Lý do: thứ tự hoà điểm ở sâu trong 1–3/9.000 bảng xếp hạng `bm25_rule` từng đổi theo hash seed. Metric
       không đổi.
     - Nhờ vậy mọi file kết quả trùng từng byte giữa các lần chạy.
   - **Bản tự kiểm của AI.** Trợ lý AI chấm thử **toàn bộ** kit chính thức (543 mục) mà không mở `human/keys/`.
     - Kết quả nằm ở `human/answers_preaudit/` và `human/preaudit_report/`, có nhãn "tạm thời".
     - Đây **không** phải kết quả A2–A6, B2 hay B3. Các mục đó chỉ được quyết định bằng câu trả lời của người
       chấm trong `human/answers/`.
     - Bản tự kiểm không dẫn tới thay đổi nào ở nhãn hay câu hỏi (mục 5g). Các điểm đáng chú ý được ghi trong
       `META_EVAL.md`.
7. **28/10 — rút lại bộ H1 và trộn H1/H1r thành một file mù.** Khi ghi kết quả tự kiểm, phát hiện hai vấn đề của
   bộ H1/H1r.
   - **Rò rỉ từ quá trình phát triển.** Mẫu H1/H1r đã loại các tin của bản nháp (mục 5d). Tuy vậy, nó chưa loại
     các tin trợ lý đã đọc khi sửa hàm gán nhãn, tức các mẫu phát triển và danh sách tin thêm/bớt.
     - Theo nhật ký còn lưu, chắc chắn có 7/96 tin H1 (4/12 tin "dòng tiền") và 5/96 tin H1r đã hiện ra trong lúc
       đó.
     - Tính theo danh sách rộng `lf_dev` ở dưới, con số là 18/96 tin H1 (8/12 tin "dòng tiền") và 14/96 tin H1r.
     - Precision đo trên chính các tin đã dùng để sửa hàm sẽ bị lạc quan.
   - **Không mù.** H1 và H1r nằm ở hai file riêng, và mã câu có tiền tố "H1r". Người chấm vì vậy biết máy đã gán
     nhãn gì.
   - **Đã sửa:**
     - `human/preaudit_items.json` có thêm danh sách `lf_dev` gồm 990 tin. Đó là mọi tin xuất hiện trong các đầu
       ra phát triển (mẫu, danh sách thêm/bớt), hoặc trong nhật ký công cụ còn lưu trước khi rút kit. Nhật ký của
       một phần buổi làm việc không còn đủ, nên danh sách được lấy rộng hơn mức cần.
     - Bộ H1 được rút lại và loại các tin này. Hai mẫu của mục 7 (A2 và A3, mỗi mẫu 12 tin cho mỗi đặc điểm) được
       trộn vào **một** file `human/tasks/H1_aspects.csv` gồm 192 tin, với mã câu trung tính. Khoá có cột `auto`
       để tách A2 và A3 khi phân tích.
     - Các bộ H2–H5 giữ nguyên byte.
   - **Hệ quả cho bản tự kiểm.** Trợ lý chấm lại bộ H1 mới theo cách mù hoàn toàn: mọi tin được xem cùng một kiểu
     ngữ cảnh từ khoá, không thấy hàm gán nhãn kích hoạt ở đâu. Kết quả trên bộ cũ vẫn được ghi trong
     `META_EVAL.md` để so sánh. 10 tin của bộ mới từng nằm trong bộ cũ; trợ lý đọc chúng sau khi đóng băng, nên
     chúng không ảnh hưởng tới hàm gán nhãn.
8. **29/10 — đối chiếu bản sao offline với backend chạy thật; sửa công cụ phần live và DL.** Cách làm và kết quả nằm
   ở `META_EVAL.md` mục 4.3. Tóm tắt: khi dữ liệu, vector và ngày như nhau, top-10 của `prod_nodl` và `prod_dl`
   trùng API thật ở 200/200 câu test. Các thay đổi:
   - **`embed_benchmark.py`:**
     - lưu vector tài liệu dạng float32 thay cho float16;
     - gửi mỗi câu hỏi một request, như backend (`--query-batch 1`);
     - ghi kích thước batch vào `embeddings_<tag>.json`.

     Lý do: ranker làm tròn `final_score` tới 4 chữ số. Sai số float16, tới 1,3·10⁻⁴ trên điểm semantic, đã làm đảo
     thứ tự ở 9/200 top-10. Chưa có kết quả DL nào được công bố, nên không số nào phải tính lại.
   - **`eval_benchmark.py --today`:** ngày mà `freshness_score` của ranker nhìn thấy. Mặc định là 2026-10-28, đúng
     ngày của kết quả đã công bố. `summary.json` ghi thêm khoá `today`. Mọi số trong đó và các file kết quả khác
     trùng từng byte với bản trước; hash mới nằm ở `DATASET_CARD.md`.
   - **`run_live.py`:**
     - ghi ngày chạy của từng câu;
     - nhận ra cấu hình backend (semantic, Neo4j) và bản sao offline tương ứng;
     - so từng bảng xếp hạng với `runs.jsonl.gz` của kết quả offline (`replica_fidelity`);
     - cảnh báo khi chính sách mức hoặc ngày khác với kết quả offline.
9. **29/10 — log, giải thích nhãn và hướng dẫn chạy.**
   - **`runlog.py`:** mọi script in tiến độ kèm thời gian còn lại, và ghi log vào `logs/`. Đầu log có lệnh, phiên
     bản Python, commit git và hash dữ liệu vào; dòng cuối là `OK` hoặc `FAILED`. Chạy lại toàn bộ pipeline sau
     thay đổi này cho `data/`, `results/` và `meta_eval.json` trùng từng byte với bản đã công bố.
   - **`explain_qrels.py`:** giải thích từng nhãn theo ràng buộc, bằng các hàm của `check_labels.py`, và dừng nếu
     mức tính lại khác `qrels.tsv`. Chế độ `--run` đếm lý do các kết quả sai của một hệ thống. Công cụ chỉ đọc nhãn.
   - **`HUONG_DAN_CHAY.md`** và **`requirements.txt`** cho người chạy lần đầu.
