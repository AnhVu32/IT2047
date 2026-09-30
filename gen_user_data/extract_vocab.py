"""Rút trích vocabulary (category) thật từ Data/Final_Data.csv.

Dùng CSV chứ KHÔNG dùng Final_Data.json làm nguồn: CSV là bản đã qua ETL,
field đã đổi tên tiếng Anh (property_type, legal_status, furnishing,
district, house_direction, balcony_direction) và legal_status/furnishing đã
được canonicalize sẵn thành nhãn ngắn — khác hẳn "Pháp lý"/"Nội thất" bên
JSON vốn là free text người đăng tự gõ. pandas.read_csv tự xử lý đúng các
field multi-line có quote (description) nên không cần regex định vị cột
như lúc kiểm tra thủ công qua Grep.

Sinh ra:
  * config/districts_real.json — toàn bộ giá trị "district" kèm tần suất.
  * config/vocab_report.json — value_counts đầy đủ cho property_type,
    legal_status, furnishing, house_direction, balcony_direction — để phát
    hiện giá trị hiếm/lạ nếu Data/Final_Data.csv được crawl/ETL lại sau này
    (lần chạy gần nhất xác nhận legal_status đóng đúng 4 giá trị, kể cả
    "Không rõ" — xem config/vocab_real_data.py).

Không chạy được trong phiên hiện tại (sandbox hết dung lượng đĩa) — chạy
bằng:

    cd gen_user_data && python extract_vocab.py
"""
from __future__ import annotations

import json
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
FINAL_DATA_CSV = os.path.join(REPO_ROOT, "Data", "Final_Data.csv")
CONFIG_DIR = os.path.join(HERE, "config")

CATEGORICAL_FIELDS = [
    "property_type",
    "legal_status",
    "furnishing",
    "house_direction",
    "balcony_direction",
    "listing_type",
]


def main() -> None:
    df = pd.read_csv(FINAL_DATA_CSV)
    print(f"[extract_vocab] {len(df)} bản ghi từ {FINAL_DATA_CSV}")

    os.makedirs(CONFIG_DIR, exist_ok=True)

    report = {}
    for field in CATEGORICAL_FIELDS:
        if field not in df.columns:
            print(f"  (bỏ qua, không có cột '{field}')")
            continue
        vc = df[field].value_counts(dropna=False)
        report[field] = {str(k): int(v) for k, v in vc.items()}
        print(f"\n=== {field} ({vc.shape[0]} giá trị khác nhau, tổng {vc.sum()}) ===")
        print(vc.to_string())

    with open(os.path.join(CONFIG_DIR, "vocab_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("\n[extract_vocab] -> config/vocab_report.json")

    if "district" in df.columns:
        vc = df["district"].value_counts(dropna=False)
        out = {str(k): int(v) for k, v in vc.items()}
        with open(os.path.join(CONFIG_DIR, "districts_real.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"[extract_vocab] {len(out)} quận/huyện/phường/xã khác nhau -> "
              f"config/districts_real.json")

    # Amenity/accessibility/view fields đã có sẵn tên chuẩn trong schemas.py
    # (AMENITY_FIELDS/ACCESSIBILITY_FIELDS/VIEW_FIELDS) — chỉ cần xác nhận
    # không có giá trị null/thiếu ngoài 0/1.
    try:
        from schemas import AMENITY_FIELDS, ACCESSIBILITY_FIELDS, VIEW_FIELDS
        bool_fields = [f for f in AMENITY_FIELDS + ACCESSIBILITY_FIELDS + VIEW_FIELDS if f in df.columns]
        bad = {f: df[f].dropna().unique().tolist() for f in bool_fields
               if not set(df[f].dropna().unique().tolist()) <= {0, 1}}
        if bad:
            print(f"\n[extract_vocab] CẢNH BÁO — field boolean có giá trị lạ ngoài 0/1: {bad}")
        else:
            print(f"\n[extract_vocab] {len(bool_fields)} field boolean đều sạch (chỉ 0/1).")
    except ImportError:
        pass


if __name__ == "__main__":
    main()
