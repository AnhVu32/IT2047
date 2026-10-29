# Hướng dẫn chấm tay — HCMRE-Q v2

Bộ chấm này kiểm tra xem nhãn tự động và câu hỏi của benchmark có đúng với cách một người mua nhà thật sự
hiểu hay không. Ngưỡng đạt/không đạt đã được chốt từ trước, xem `PROTOCOL.md` mục 7. Vì vậy hãy chấm theo cảm
nhận của bạn, **đừng cố đoán xem máy đã gán nhãn gì**.

## Cách làm

1. Mở `human/annotate.html` bằng Chrome, Edge hoặc Firefox. Không cần mạng.
2. Gõ tên người chấm, viết liền không dấu, ví dụ `vu`. Sau đó chọn một file trong `human/tasks/`.
3. Bấm đáp án bằng chuột hoặc phím `1` `2` `3` `4`. Chuyển câu bằng phím `←` `→`.
   - Bài đang chấm được lưu tự động trong trình duyệt.
   - Muốn chấm tiếp trên máy khác thì xuất file rồi dùng nút "Nạp kết quả cũ".
4. Chấm xong một file thì bấm **Xuất kết quả**. Chép file `answers_<task>_<tên>.csv` vào `human/answers/`.
5. Chạy `python human/analyze_human.py`. Kết quả nằm ở `human/REPORT.md`.

Quy tắc:

- **Không mở `human/keys/`.** Thư mục này chứa nhãn tự động.
- Nếu có hai người chấm, hai người làm **độc lập** và không bàn với nhau trước khi cả hai xuất file. Hai người
  chấm cho phép đo độ đồng thuận giữa người với người, tức "trần" của κ.
- Gặp câu không chắc thì chọn "Không rõ", hoặc ghi chú lại. Đừng đoán.

Thời gian ước tính cho một người:

| File | Số câu | Thời gian |
|---|---|---|
| H1 | 192 | ~75 phút |
| H2 | 100 | ~30 phút |
| H3 | 131 | ~90 phút |
| H4 | 60 | ~40 phút |
| H5 | 60 | ~30 phút |

## H1 — Tin có đặc điểm này không?

Chỉ dựa vào tiêu đề và mô tả. Chọn **Có** khi tin khẳng định đặc điểm đó **cho chính căn nhà hoặc căn hộ đang
bán**. Chọn **Không** khi tin không nhắc tới đặc điểm, nhắc ở dạng phủ định, hoặc chỉ nói tới một thứ ở gần
đó.

| Đặc điểm | Có | Không |
|---|---|---|
| Hẻm xe hơi | hẻm xe hơi / hẻm ô tô / ô tô đỗ cửa / ô tô vào tận nhà / gara ô tô trong nhà / nhà ở mặt đường ô tô | "cách hẻm xe hơi 20m", "gần đường xe hơi", "xe hơi vào được 200m" (không tới nhà), hẻm xe máy, hẻm ba gác |
| Dòng tiền | căn nhà **đang** tạo thu nhập cho thuê: đang cho thuê, có hợp đồng thuê (HĐT), nêu thu nhập/dòng tiền hiện có ("thu nhập 30tr/tháng"); hoặc bản thân căn nhà là CHDV, nhà trọ, dãy phòng trọ (kể cả đang để trống) | chỉ nói "phù hợp / tiện / có thể" cho thuê, làm hoặc xây CHDV; thu nhập "dự kiến", "có thể đạt"; "không kinh doanh" |
| Căn góc | nhà đất: căn góc, lô góc, nhà góc, 2 mặt tiền. Căn hộ: chính căn hộ là căn góc / lô góc / góc 2 view | "kế góc", "gần ngã tư", chữ "góc" trong tên đường; với căn hộ: dự án "nằm trên 2 mặt tiền đường" |
| Nhà mới | mới xây, mới hoàn thiện, mới hoàn công, mới 100%, mới bàn giao, "nhà mới 5 tầng" | "có thể / phù hợp xây mới", "còn mới", "nội thất mới", nhà cũ |
| View sông | view sông, nhìn ra sông, hướng sông, ban công nhìn sông | "gần sông" nhưng không thấy sông, "ra bờ kè view sông 150m", "công viên ven sông", "không có view sông" |
| Thang máy | nhà có thang máy | "chừa sẵn ô thang máy", "thuận tiện / có thể lắp thang máy" |
| Sân vườn | có sân vườn, có vườn, nhà vườn, biệt thự sân vườn | "có thể / phù hợp / lý tưởng làm sân vườn", "phù hợp xây nhà vườn", "hàng xóm có sân vườn", "view sân vườn" |
| Hồ bơi | hồ bơi hoặc bể bơi của căn nhà hoặc của dự án / nội khu, "căn hộ view hồ bơi" của dự án | "gần hồ bơi", "không có hồ bơi" |

File H1 trộn lẫn hai loại tin, theo thứ tự ngẫu nhiên:

- tin máy cho là **có** đặc điểm, dùng để đo precision (A2);
- tin máy cho là **không** nhưng có từ khoá gần giống, dùng để đo mức bỏ sót (A3).

Mã câu và thứ tự không cho biết tin thuộc loại nào. Hãy chấm từng tin theo đúng nội dung của nó.

## H2 — Câu hỏi có đúng ý tiêu chí không?

Mỗi câu truy vấn đi kèm danh sách **tiêu chí vàng** mà máy dùng để chấm.

- **Đúng và đủ:** câu nêu đủ mọi tiêu chí, không thêm tiêu chí lạ, và số liệu khớp.
  - "khoảng 3 tỷ", "tầm 3 tỷ", "3 tỷ" đều là "khoảng 3 tỷ".
  - "dưới 3 tỷ", "3 tỷ đổ lại", "tối đa 3 tỷ" đều là "tối đa 3 tỷ".
  - Viết tắt, không dấu và teencode đều được chấp nhận. Ví dụ "2ty5" = 2,5 tỷ, "Q3" = quận 3, "P.Bàn Cờ" = phường Bàn Cờ.
  - Tiêu chí "gần X" không ghi số thì chỉ cần câu nói "gần X".
- **Sai / thiếu / thừa:** câu bỏ mất một tiêu chí, nêu sai số, đổi "tối đa" thành "khoảng", hoặc thêm tiêu chí
  không có trong danh sách. Hãy ghi chú lỗi cụ thể.
- **Độ tự nhiên (1–5):** người Việt có thể gõ câu như vậy khi tìm nhà không?
  - 1 = không ai viết thế.
  - 3 = hơi gượng nhưng hiểu được.
  - 5 = rất tự nhiên.
  - Đừng trừ điểm chỉ vì câu không dấu hoặc viết tắt, vì đó là chủ ý của phong cách S2/S3.

## H3 — Tin này phù hợp với câu tìm kiếm ở mức nào?

Hãy chấm như một người **đang thật sự tìm mua theo đúng câu đó**. Thẻ tin gồm:

- tiêu đề, mô tả;
- thông tin chính: giá, diện tích, phòng ngủ, pháp lý, nội thất, phường và quận cũ;
- các khoảng cách đo trên bản đồ khi câu hỏi có nhắc tới tiện ích, địa danh, hoặc khi tin nằm ngoài khu vực được
  hỏi.

| Mức | Ý nghĩa |
|---|---|
| **3** | Đúng ý: đúng loại nhà, đúng khu vực được nêu, đáp ứng mọi tiêu chí |
| **2** | Đúng khu vực nhưng **một** tiêu chí hơi lệch, người hỏi vẫn có thể cân nhắc. Ví dụ giá hơi quá ngân sách, diện tích hơi nhỏ, hơn một phòng ngủ, hơi xa tiện ích hơn yêu cầu |
| **1** | Không thuộc khu vực được nêu nhưng **sát bên**, và mọi tiêu chí khác đều ổn |
| **0** | Không phù hợp: sai loại, sai hoặc xa khu vực, lệch nhiều, hoặc lệch từ hai tiêu chí trở lên |

Không có công thức. "Hơi lệch" hay "lệch nhiều" là do bạn đánh giá. Nếu tin thiếu thông tin cần thiết, ví dụ
không ghi giá hoặc không ghi số phòng, hãy chấm theo những gì người mua biết được từ tin.

## H4 — Tin nào phù hợp HƠN?

Hai tin cùng gần đúng với câu tìm kiếm. Hãy chọn tin bạn sẽ đưa lên trước nếu bạn là môi giới của người hỏi.
Chọn "Như nhau" khi thật sự không phân biệt được. Không có đáp án "đúng" theo luật: đây là câu hỏi về sở thích
của người dùng.

## H5 — Giá sau khi sửa có đúng không?

Mỗi tin cho thấy giá cũ trong dữ liệu và giá MỚI sau khi sửa (errata v3.1).

- **Đúng:** giá mới đúng là giá bán mà tin nêu. Nếu tin ghi "giá cũ 18 tỷ, nay còn 15,7 tỷ" thì giá bán là
  15,7 tỷ.
- Giá mới để trống nghĩa là máy cho rằng tin không nêu giá bán. Chọn **Đúng** nếu quả thật tin không nêu. Ví dụ
  tin chỉ ghi "giảm 1 tỷ" hoặc "cho thuê 30 triệu/tháng".
- **Sai:** giá mới không phải giá bán. Nếu tin có nêu giá bán, ghi giá đúng (tỷ) vào ô "Giá đúng".
