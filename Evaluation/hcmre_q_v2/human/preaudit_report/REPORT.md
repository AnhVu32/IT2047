# Kết quả kiểm định bằng người (tự sinh bởi analyze_human.py)

**TIỀN KIỂM ĐỊNH BỞI AI (claude-preaudit) — tạm thời, KHÔNG thay thế người chấm**

| Mã | Kết quả | Ngưỡng đăng ký trước | Đạt |
|---|---|---|---|
| A2_aspect_precision | 0.9688 (n=96) | ≥ 0,90 và cận dưới Wilson ≥ 0,80 | đạt |
| A4_graded_agreement | 0.9408 (n=131) | κ có trọng số ≥ 0,60 | đạt |
| A5_ward_priority | 0.6667 (n=60) | ≥ 0,70 và p < 0,05 | KHÔNG đạt |
| A6_price_corrections | 1.0 (n=60) | ≥ 0,95 và cận dưới Wilson ≥ 0,85 | đạt |
| B2_faithfulness | 1.0 (n=100) | ≥ 0,95 | đạt |
| B3_naturalness | 1.0 (n=100) | ≥ 80% câu đạt ≥ 3 | đạt |
| A3_aspect_misses | 0.1146 (n=96) | báo cáo | — |

Chi tiết: `human/preaudit_report/report.json`.
