# Câu trả lời của người chấm

Đặt ở đây các file `answers_<task>_<tên>.csv` mà `annotate.html` xuất ra, ví dụ `answers_H3_graded_pairs_vu.csv`.

- Tên người chấm viết liền, không dấu và không có dấu gạch dưới.
- Mỗi người chấm độc lập. Hai người không trao đổi trước khi cả hai xuất file.

Sau đó chạy:

```bash
python human/analyze_human.py
```

Báo cáo nằm ở `human/REPORT.md` và `human/report.json`. Bản tự kiểm của trợ lý AI nằm riêng ở
`human/answers_preaudit/`. **Không** chép bản đó vào đây.
