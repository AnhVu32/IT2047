# Tự kiểm của trợ lý AI — tạm thời, không phải kết quả chấm bằng người

Thư mục này chứa câu trả lời của trợ lý AI (Claude) cho toàn bộ kit chấm tay H1–H5, tổng cộng 543 mục. Mỗi file có
cùng định dạng với file `annotate.html` xuất ra; tên người chấm là `claude-preaudit`.

## Cách làm

- Trợ lý chấm sau khi hàm gán nhãn, bộ sinh câu và hướng dẫn đã được đóng băng (PROTOCOL.md 9.5g).
- Trợ lý không mở `human/keys/`. Trình xem chỉ hiện đúng những gì người chấm thấy.
  - Với H1, mọi tin được xem cùng một kiểu ngữ cảnh từ khoá.
  - Trợ lý không thấy hàm gán nhãn kích hoạt ở đâu.
- Cột `note` ghi lý do ở những ca ranh giới.

## Dùng để làm gì

Đây chỉ là **dự báo** để phát hiện sớm vấn đề. Kết quả nằm ở `../preaudit_report/` và được phân tích trong
`../../META_EVAL.md` mục 5.

Các phép kiểm A2–A6, B2 và B3 chỉ được quyết định bằng người chấm, với file đặt ở `human/answers/`. Không chép
các file ở đây sang đó.

Bản tự kiểm có ba giới hạn:

- chỉ có một người chấm;
- người chấm là AI;
- AI đó cũng là bên viết bộ sinh dữ liệu.
