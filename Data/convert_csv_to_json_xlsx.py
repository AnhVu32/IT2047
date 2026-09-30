"""Sinh lại Final_Data.json và Final_Data.xlsx TỪ Final_Data.csv.

Final_Data.csv được coi là bản chuẩn (đã ETL, category sạch: property_type,
legal_status, furnishing, district, house_direction, balcony_direction, và
25 cột boolean amenity/accessibility/view khớp đúng schema Postgres
`properties` mà backend dùng) — 2 file JSON/XLSX chỉ là 2 định dạng lưu trữ
khác của CÙNG dữ liệu này, không phải nguồn độc lập.

Dùng pandas.read_csv (không dùng regex thủ công) vì cột `description` chứa
xuống dòng/dấu phẩy/dấu ngoặc kép lồng nhau — chỉ parser CSV chuẩn (theo
RFC 4180) mới tách cột đúng 100%; regex định vị cột (như lúc kiểm tra vocab
thủ công) chỉ đúng gần đúng, không nên dùng để sinh dữ liệu thật.

Chạy:
    cd Data && pip install pandas openpyxl --break-system-packages
    python convert_csv_to_json_xlsx.py

Ghi đè trực tiếp Final_Data.json / Final_Data.xlsx hiện có (giữ nguyên tên
file, giữ nguyên Final_Data.csv không đổi).
"""
from __future__ import annotations

import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "Final_Data.csv")
JSON_PATH = os.path.join(HERE, "Final_Data.json")
XLSX_PATH = os.path.join(HERE, "Final_Data.xlsx")


def main() -> None:
    df = pd.read_csv(CSV_PATH)
    print(f"[convert] đọc {len(df)} dòng, {len(df.columns)} cột từ {CSV_PATH}")

    # --- JSON: giữ nguyên kiểu dữ liệu (int cho boolean 0/1, không ép NaN
    # thành chuỗi "nan") ---
    df.to_json(JSON_PATH, orient="records", force_ascii=False, indent=2)
    print(f"[convert] -> {JSON_PATH}")

    # --- XLSX: cần openpyxl. Excel giới hạn 1,048,576 dòng nên 3037 dòng
    # không vấn đề gì; cột description dài vẫn lưu được bình thường trong 1
    # cell (Excel giới hạn ~32,767 ký tự/cell — nên kiểm tra nếu có mô tả
    # vượt ngưỡng này thì bị cắt, cảnh báo bên dưới). ---
    max_len = df.astype(str).apply(lambda col: col.str.len().max())
    too_long = max_len[max_len > 32767]
    if not too_long.empty:
        print(f"[convert] CẢNH BÁO — cột vượt giới hạn 32767 ký tự/cell của Excel, "
              f"sẽ bị Excel cắt bớt: {too_long.to_dict()}")

    df.to_excel(XLSX_PATH, index=False, engine="openpyxl")
    print(f"[convert] -> {XLSX_PATH}")

    print("[convert] Xong. Final_Data.csv không bị thay đổi.")


if __name__ == "__main__":
    main()
