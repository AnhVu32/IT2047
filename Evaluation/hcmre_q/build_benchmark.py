"""HCMRE-Q: an independent query–relevance benchmark for the IT2047 search system.

Design goals (see Evaluation/docs/04_KET_QUA_V4_VA_HAN_CHE.md §5.4 for why v4 is not enough):
  1. Relevance labels come ONLY from listing attributes / measured distances /
     audited labeling functions (corpus.py) -- never from ranker.py.
  2. Queries are written as Vietnamese users type them (4 surface styles), without
     consulting the parser's regex or alias tables.
  3. Splits are made by query and are *frame-disjoint*: a sentence frame used in
     test never appears in train/val, so a model trained on train cannot simply
     memorise phrasing patterns.

Outputs (in --out):
  queries.jsonl   one query per line: qid, split, family, style, frame_id, text, gold
  qrels.tsv       TREC format "qid 0 doc_id grade" for grade >= 1 (grade 0 implicit)
  corpus_attributes.csv   label-side attribute table (one row per listing)
  stats.json      split / family / style / label-distribution statistics
"""
from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

import corpus as C

SEED = 20261010
SPLIT_FRACTIONS = {"train": 0.6, "val": 0.2, "test": 0.2}
FAMILY_COUNTS = {"F1_structured": 170, "F2_structured_plus": 60, "F3_proximity": 120,
                 "F4_aspect": 150, "F5_landmark": 50, "F6_subtype": 50}
STYLE_WEIGHTS = {"S1": 0.30, "S2": 0.20, "S3": 0.25, "S4": 0.25}
MAX_EXACT, MAX_RELEVANT = 50, 150

# Default radius (km, driving) behind an implicit "gần X" for each amenity category.
IMPLICIT_AMENITY_KM = {"school": 1.0, "market": 1.0, "supermarket": 1.0, "park": 1.0,
                       "bus_stop": 0.5, "hospital": 2.0, "mall": 2.0, "metro": 2.0,
                       "college_university": 2.0}
EXPLICIT_AMENITY_KM = {"metro": [1.0, 2.0, 3.0, 5.0], "hospital": [1.0, 2.0, 3.0],
                       "mall": [1.0, 2.0, 3.0], "college_university": [1.0, 2.0, 3.0],
                       "default": [0.3, 0.5, 1.0, 1.5, 2.0]}
# Default radius (km, straight line) behind "gần <landmark>".
LANDMARK_KM = {"ben_thanh": 2.0, "tan_son_nhat": 3.0, "landmark81": 2.0,
               "phu_my_hung": 2.0, "dhqg": 3.0}
THU_DUC_GROUP = ["Thành Phố Thủ Đức", "Quận 2", "Quận 9"]

# ---------------------------------------------------------------------------
# Verbalisers
# ---------------------------------------------------------------------------
DIGIT_WORDS = {1: "một", 2: "hai", 3: "ba", 4: "bốn", 5: "năm", 6: "sáu", 7: "bảy",
               8: "tám", 9: "chín", 10: "mười"}


def int_words(n: int) -> str:
    if n in DIGIT_WORDS:
        return DIGIT_WORDS[n]
    if n < 20:
        unit = {5: "lăm", 1: "một"}.get(n - 10, DIGIT_WORDS[n - 10])
        return f"mười {unit}"
    if n < 100:
        tens, unit = divmod(n, 10)
        tail = "" if unit == 0 else " " + {1: "mốt", 5: "lăm"}.get(unit, DIGIT_WORDS[unit])
        return f"{DIGIT_WORDS[tens]} mươi{tail}"
    return str(n)


def num_s1(x: float, rng) -> str:
    if float(x).is_integer():
        return str(int(x))
    text = f"{x:.1f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") if rng.random() < 0.5 else text


def price_s3(x: float, rng) -> str:
    whole = int(x)
    frac = round((x - whole) * 10)
    unit = rng.choice(["tỷ", "ty", "tỏi"])
    if frac == 0:
        return rng.choice([f"{whole}{unit}", f"{whole} {unit}"])
    return rng.choice([f"{whole}ty{frac}", f"{whole} tỷ {frac}", f"{whole}.{frac}ty"])


def price_s4(x: float, rng) -> str:
    whole = int(x)
    frac = round((x - whole) * 10)
    head = int_words(whole) if rng.random() < 0.6 else str(whole)
    if frac == 0:
        return f"{head} tỷ"
    if frac == 5:
        return f"{head} tỷ rưỡi"
    return f"{head} tỷ {DIGIT_WORDS.get(frac, str(frac)) if rng.random() < 0.5 else frac}"


def price_phrase(kind: str, gold_price: dict, style: str, rng) -> str:
    if style in ("S1", "S2"):
        n = lambda v: num_s1(v, rng)
        if kind == "max":
            return rng.choice(["dưới {} tỷ", "tối đa {} tỷ", "không quá {} tỷ", "{} tỷ đổ lại",
                               "từ {} tỷ trở xuống"]).format(n(gold_price["max"]))
        if kind == "target":
            return rng.choice(["khoảng {} tỷ", "tầm {} tỷ", "{} tỷ", "cỡ {} tỷ",
                               "quanh {} tỷ"]).format(n(gold_price["target"]))
        return rng.choice(["từ {} đến {} tỷ", "{} - {} tỷ", "trong khoảng {} tới {} tỷ"]).format(
            n(gold_price["min"]), n(gold_price["max"]))
    if style == "S3":
        if kind == "max":
            return rng.choice(["<{}", "dưới {}", "max {}", "{} đổ lại"]).format(price_s3(gold_price["max"], rng))
        if kind == "target":
            return rng.choice(["~{}", "tầm {}", "{}", "khoảng {}"]).format(price_s3(gold_price["target"], rng))
        lo, hi = gold_price["min"], gold_price["max"]
        unit = rng.choice(["tỷ", "ty"])
        fmt = lambda v: f"{v:g}"
        return rng.choice([f"{fmt(lo)}-{fmt(hi)}{unit}", f"{fmt(lo)}-{fmt(hi)} {unit}", f"từ {fmt(lo)} đến {fmt(hi)}{unit}"])
    # S4 conversational
    if kind == "max":
        return rng.choice(["không quá {}", "dưới {}", "{} đổ lại", "tầm {} đổ xuống",
                           "trong vòng {}"]).format(price_s4(gold_price["max"], rng))
    if kind == "target":
        return rng.choice(["khoảng {}", "tầm {}", "loanh quanh {}", "cỡ {}"]).format(
            price_s4(gold_price["target"], rng))
    return rng.choice(["từ {} tới {}", "trong khoảng {} đến {}"]).format(
        price_s4(gold_price["min"], rng), price_s4(gold_price["max"], rng))


def beds_phrase(kind: str, b: int, style: str, rng) -> str:
    if style in ("S1", "S2"):
        if kind == "exact":
            return rng.choice([f"{b} phòng ngủ", f"{b} PN"])
        return rng.choice([f"từ {b} phòng ngủ", f"ít nhất {b} phòng ngủ", f"{b} phòng ngủ trở lên"])
    if style == "S3":
        return rng.choice([f"{b}PN", f"{b}pn"]) if kind == "exact" else f"{b}PN+"
    if kind == "exact":
        return f"{int_words(b)} phòng ngủ"
    return rng.choice([f"tối thiểu {int_words(b)} phòng ngủ", f"đủ {int_words(b)} phòng ngủ trở lên"])


def area_phrase(a: int, style: str, rng) -> str:
    if style in ("S1", "S2"):
        return rng.choice([f"diện tích từ {a} m²", f"trên {a}m2", f"rộng từ {a} m2 trở lên", f"tối thiểu {a} m²"])
    if style == "S3":
        return rng.choice([f">{a}m2", f"DT>{a}m2", f"dt {a}m2+"])
    return rng.choice([f"rộng tầm {int_words(a) if a < 100 else a} mét vuông trở lên",
                       f"diện tích không dưới {a} mét vuông"])


def dist_text(km: float, style: str, rng) -> str:
    if km < 1:
        m = int(round(km * 1000))
        if style == "S4":
            return {300: "ba trăm mét", 500: "năm trăm mét"}.get(m, f"{m} mét")
        return rng.choice([f"{m}m", f"{m} m"])
    v = f"{km:g}"
    if style in ("S1", "S2"):
        v = v.replace(".", ",") if rng.random() < 0.4 else v
    return rng.choice([f"{v}km", f"{v} km"]) if style != "S4" else f"{v} cây số"


AMENITY_NAMES = {
    "S1": {"school": ["trường học", "trường"], "metro": ["ga metro", "metro"], "market": ["chợ"],
           "supermarket": ["siêu thị"], "park": ["công viên"], "hospital": ["bệnh viện"],
           "mall": ["trung tâm thương mại", "TTTM"], "college_university": ["trường đại học", "đại học"],
           "bus_stop": ["trạm xe buýt", "trạm bus"]},
    "S3": {"school": ["trường"], "metro": ["metro", "ga metro"], "market": ["chợ"],
           "supermarket": ["siêu thị"], "park": ["công viên"], "hospital": ["BV", "bệnh viện"],
           "mall": ["TTTM"], "college_university": ["ĐH", "trường ĐH"], "bus_stop": ["trạm bus"]},
    "S4": {"school": ["trường học"], "metro": ["ga metro", "tuyến metro"], "market": ["chợ"],
           "supermarket": ["siêu thị"], "park": ["công viên"], "hospital": ["bệnh viện"],
           "mall": ["trung tâm thương mại"], "college_university": ["trường đại học"],
           "bus_stop": ["trạm xe buýt"]},
}
AMENITY_PURPOSE = {"school": "cho con đi học", "metro": "đi làm bằng metro", "market": "đi chợ",
                   "supermarket": "mua sắm", "park": "tập thể dục", "hospital": "tiện khám chữa bệnh",
                   "mall": "mua sắm cuối tuần", "college_university": "đi học", "bus_stop": "đi xe buýt"}


def amenity_phrase(cat: str, km: float, explicit: bool, style: str, rng) -> str:
    names = AMENITY_NAMES["S1" if style == "S2" else style][cat]
    name = rng.choice(names)
    if style in ("S1", "S2"):
        if explicit:
            return rng.choice(["cách {n} không quá {d}", "cách {n} dưới {d}", "{n} trong vòng {d}"]).format(
                n=name, d=dist_text(km, style, rng))
        return rng.choice(["gần {n}", "gần {n} cho tiện"]).format(n=name)
    if style == "S3":
        if explicit:
            return rng.choice(["cách {n} <{d}", "gần {n} {d}"]).format(n=name, d=dist_text(km, style, rng))
        return f"gần {name}"
    if explicit:
        return rng.choice(["{n} cách nhà tầm {d} thôi", "đi chưa tới {d} là tới {n}"]).format(
            n=name, d=dist_text(km, style, rng))
    return f"gần {name} {AMENITY_PURPOSE[cat]}"


LANDMARK_NAMES = {
    "ben_thanh": {"S1": ["chợ Bến Thành"], "S3": ["chợ Bến Thành"], "S4": ["chợ Bến Thành"]},
    "tan_son_nhat": {"S1": ["sân bay Tân Sơn Nhất", "sân bay"], "S3": ["sân bay TSN", "sân bay"],
                     "S4": ["sân bay Tân Sơn Nhất"]},
    "landmark81": {"S1": ["Landmark 81", "tòa Landmark 81"], "S3": ["LM81", "Landmark81"],
                   "S4": ["tòa Landmark 81"]},
    "phu_my_hung": {"S1": ["Phú Mỹ Hưng", "khu Phú Mỹ Hưng"], "S3": ["PMH"], "S4": ["khu đô thị Phú Mỹ Hưng"]},
    "dhqg": {"S1": ["Làng Đại học Thủ Đức", "ĐH Quốc gia TP.HCM"], "S3": ["làng ĐH", "ĐHQG"],
             "S4": ["làng đại học"]},
}


def landmark_phrase(name: str, km: float, explicit: bool, style: str, rng) -> str:
    label = rng.choice(LANDMARK_NAMES[name]["S1" if style == "S2" else style])
    if explicit:
        if style == "S3":
            return f"cách {label} <{dist_text(km, style, rng)}"
        if style == "S4":
            return f"cách {label} chừng {dist_text(km, style, rng)} trở lại"
        return f"cách {label} không quá {dist_text(km, style, rng)}"
    return f"gần {label}"


ASPECT_PHRASES = {
    "hem_xe_hoi": {"S1": ["hẻm xe hơi", "hẻm ô tô", "ô tô đỗ cửa", "hẻm xe hơi vào tận nhà"],
                   "S3": ["HXH", "hxh", "hẻm oto"],
                   "S4": ["trong hẻm rộng cho ô tô vào được", "xe hơi đậu được trước cửa"]},
    "dong_tien": {"S1": ["đang có dòng tiền cho thuê", "phù hợp đầu tư cho thuê", "phù hợp làm căn hộ dịch vụ"],
                  "S3": ["CHDV", "dòng tiền", "có HĐ thuê"],
                  "S4": ["mua về cho thuê lấy dòng tiền", "đang có người thuê sẵn"]},
    "can_goc": {"S1": ["góc 2 mặt tiền", "lô góc", "căn góc"], "S3": ["góc 2MT", "lô góc", "căn góc"],
                "S4": ["ở vị trí góc hai mặt tiền"]},
    "can_goc@Căn hộ": {"S1": ["góc", "căn góc"], "S3": ["căn góc", "góc"], "S4": ["căn góc thoáng hai mặt"]},
    "nha_moi": {"S1": ["mới xây", "xây mới", "mới 100%"], "S3": ["mới 100%", "mới xây"],
                "S4": ["mới xây, dọn vào ở ngay", "còn mới, không phải sửa sang"]},
    "view_song": {"S1": ["view sông", "nhìn ra sông", "hướng sông"], "S3": ["view sông"],
                  "S4": ["có view nhìn ra sông"]},
    "thang_may_nha": {"S1": ["có thang máy"], "S3": ["có thang máy", "thang máy"],
                      "S4": ["có thang máy cho người già"]},
    "san_vuon": {"S1": ["có sân vườn", "có vườn"], "S3": ["sân vườn"], "S4": ["có khoảng sân vườn trồng cây"]},
    "ho_boi": {"S1": ["có hồ bơi", "có bể bơi"], "S3": ["có hồ bơi"], "S4": ["có hồ bơi cho bọn trẻ"]},
}

TYPE_PHRASES = {
    "Căn hộ": {"S1": ["căn hộ", "căn hộ chung cư", "chung cư"], "S3": ["CH", "CHCC", "căn hộ", "cc"],
               "S4": ["căn hộ", "một căn chung cư", "căn hộ chung cư"]},
    "Nhà đất": {"S1": ["nhà", "nhà riêng", "nhà phố", "nhà ở"], "S3": ["nhà", "nhà phố"],
                "S4": ["một căn nhà", "nhà riêng", "nhà"]},
    "Nhà mặt phố": {"S1": ["nhà mặt phố", "nhà mặt tiền", "nhà mặt tiền đường"], "S3": ["nhà MT", "nhà mặt tiền", "MTKD"],
                    "S4": ["nhà mặt tiền đường để kinh doanh"]},
    "Biệt thự/Liền kề": {"S1": ["biệt thự", "nhà liền kề", "biệt thự liền kề"], "S3": ["biệt thự", "BT liền kề"],
                         "S4": ["một căn biệt thự"]},
    "Shophouse": {"S1": ["shophouse", "nhà phố thương mại"], "S3": ["shophouse"], "S4": ["một căn shophouse"]},
}
LEGAL_PHRASES = {"S1": ["sổ hồng riêng", "đã có sổ hồng riêng"], "S3": ["SHR", "sổ hồng riêng"],
                 "S4": ["giấy tờ sổ hồng riêng đầy đủ"]}
FURN_PHRASES = {"S1": ["đầy đủ nội thất", "full nội thất"], "S3": ["full NT", "full nội thất"],
                "S4": ["có sẵn nội thất, chỉ việc dọn vào"]}


def ward_phrase(ward: str, style: str, rng) -> str:
    prefix, name = ward.split(" ", 1)
    p_lower = prefix.lower()
    if style in ("S1", "S2"):
        return rng.choice([f"{p_lower} {name}", f"{prefix} {name}"] + ([f"P. {name}"] if prefix == "Phường" else []))
    if style == "S3":
        short = "P." if prefix == "Phường" else "X."
        return rng.choice([f"{short}{name}", f"{short} {name}", name])
    return rng.choice([f"khu {name}", f"{p_lower} {name}"])


def former_phrase(area: str, style: str, rng) -> str:
    if area == "Thủ Đức":
        return rng.choice({"S1": ["TP Thủ Đức", "thành phố Thủ Đức", "Thủ Đức"], "S2": ["TP Thủ Đức", "Thủ Đức"],
                           "S3": ["TP.Thủ Đức", "Thủ Đức"], "S4": ["khu Thủ Đức", "Thủ Đức"]}[style])
    prefix, name = area.split(" ", 1) if not area.startswith("Thành Phố") else ("Thành Phố", area[len("Thành Phố "):])
    numeric = name.isdigit()
    if style in ("S1", "S2"):
        options = [f"{prefix.lower()} {name}", f"{prefix} {name}"]
        if not numeric:
            options.append(name)
        if prefix == "Thành Phố":
            options = [f"TP {name}", name]
        return rng.choice(options)
    if style == "S3":
        if prefix == "Quận":
            return rng.choice([f"Q{name}", f"Q.{name}"] if numeric else [f"Q.{name}", name])
        if prefix == "Huyện":
            return rng.choice([f"H.{name}", name])
        return rng.choice([f"TP.{name}", name])
    if prefix == "Quận":
        return rng.choice([f"quận {name} cũ", f"Quận {name}"] if numeric else [name, f"quận {name} cũ"])
    return name


# ---------------------------------------------------------------------------
# Sentence frames. S2 re-uses S1 frames (accent-stripped), so the frame split is
# shared. Slots: T type, A aspect, B bedrooms, S area, L location, M amenity,
# K landmark, G legal, F furnishing, P price.
# ---------------------------------------------------------------------------
def fr(lead, order, conn=None, sep=" ", tail=""):
    return dict(lead=lead, order=order, conn=conn or {}, sep=sep, tail=tail)


ALL = ["T", "A", "B", "S", "L", "M", "K", "G", "F", "P"]
FRAMES = {
    "S1": [
        fr("", ["T", "A", "B", "L", "M", "K", "S", "G", "F", "P"], {"L": "ở", "P": "giá"}),
        fr("Tìm", ["T", "A", "B", "L", "P", "M", "K", "S", "G", "F"], {"L": "tại"}),
        fr("Cần mua", ["T", "A", "L", "B", "S", "G", "F", "M", "K", "P"], {"L": "khu vực", "P": "giá"}, sep=", "),
        fr("Bán", ["T", "A", "B", "S", "L", "M", "K", "G", "F", "P"], {"P": "giá"}),
        fr("Tôi muốn mua", ["T", "A", "B", "L", "P", "M", "K", "S", "G", "F"], {"L": "ở"}, sep=", ", tail="."),
        fr("Có", ["T", "A", "L", "B", "M", "K", "S", "G", "F", "P"], {"T+": "nào", "L": "ở", "P": "giá"}, tail=" không?"),
        fr("Danh sách", ["T", "A", "L", "P", "B", "M", "K", "S", "G", "F"], {"L": "tại"}),
        fr("Gợi ý", ["T", "A", "B", "L", "M", "K", "S", "G", "F", "P"], {"L": "ở", "P": "trong tầm"}),
        fr("", ["L", "T", "A", "B", "M", "K", "S", "G", "F", "P"]),
        fr("Mua", ["T", "A", "L", "P", "B", "S", "G", "F", "M", "K"], {"L": "ở"}),
    ],
    "S3": [
        fr("", ["T", "B", "A", "L", "P", "M", "K", "S", "G", "F"]),
        fr("cần mua", ["T", "A", "L", "P", "B", "M", "K", "S", "G", "F"]),
        fr("", ["T", "A", "L", "B", "S", "G", "F", "M", "K", "P"], sep=" - "),
        fr("tìm", ["T", "B", "A", "L", "M", "K", "S", "G", "F", "P"]),
        fr("mua", ["T", "L", "A", "B", "P", "M", "K", "S", "G", "F"], sep=", "),
        fr("", ["P", "T", "B", "A", "L", "M", "K", "S", "G", "F"]),
        fr("bán", ["T", "A", "B", "S", "L", "P", "M", "K", "G", "F"]),
        fr("", ["L", "T", "A", "B", "P", "M", "K", "S", "G", "F"]),
        fr("cần tìm", ["T", "A", "B", "S", "G", "F", "L", "M", "K", "P"], sep=" "),
        fr("hỏi mua", ["T", "L", "B", "A", "M", "K", "S", "G", "F", "P"], sep=", "),
    ],
    "S4": [
        fr("Mình đang tìm", ["T", "A", "L", "B", "M", "K", "S", "G", "F", "P"], {"L": "ở", "P": "ngân sách"}, sep=", ", tail="."),
        fr("Gia đình mình cần mua", ["T", "B", "A", "L", "M", "K", "S", "G", "F", "P"], {"L": "ở", "P": "tài chính"},
           sep=", ", tail=", có căn nào phù hợp không?"),
        fr("Anh chị tư vấn giúp em", ["T", "A", "L", "P", "B", "M", "K", "S", "G", "F"], {"L": "ở", "P": "giá"}, tail=" với ạ."),
        fr("Em cần", ["T", "A", "B", "L", "M", "K", "S", "G", "F", "P"], {"L": "bên"}, sep=", ", tail=" ạ."),
        fr("Có", ["T", "A", "L", "M", "K", "B", "S", "G", "F", "P"], {"T+": "nào", "L": "ở", "P": "mà giá"}, tail=" không ạ?"),
        fr("Tôi muốn tìm", ["T", "A", "L", "P", "B", "M", "K", "S", "G", "F"], {"L": "ở", "P": "với mức giá"}, tail="."),
        fr("Cho mình xem", ["T", "A", "B", "L", "M", "K", "S", "G", "F", "P"], {"L": "khu", "P": "giá"}, tail=" nhé."),
        fr("Đang cần mua", ["T", "A", "L", "B", "M", "K", "S", "G", "F", "P"], {"L": "ở", "P": "vốn"}, sep=", ",
           tail=", ai có giới thiệu giúp."),
        fr("Vợ chồng mình muốn mua", ["T", "B", "L", "A", "M", "K", "S", "G", "F", "P"], {"L": "ở", "P": "giá"}, sep=", ", tail="."),
        fr("Nhờ tìm giúp", ["T", "A", "L", "B", "M", "K", "S", "G", "F", "P"], {"L": "khu", "P": "giá"}, sep=", ", tail=" nha."),
    ],
}


def render(frame: dict, slots: dict) -> str:
    parts = []
    for key in frame["order"]:
        phrase = slots.get(key)
        if not phrase:
            continue
        conn = frame["conn"].get(key, "")
        text = f"{conn} {phrase}".strip() if conn else phrase
        if key == "T" and frame["conn"].get("T+"):
            text = f"{text} {frame['conn']['T+']}"
        parts.append(text)
    body = parts[0] if parts else ""
    for part in parts[1:]:
        # keep the type/aspect/bedroom block tight; separators go between larger units
        body += (" " if frame["sep"] == " " else frame["sep"]) + part
    sentence = f"{frame['lead']} {body}".strip() + frame["tail"]
    words = sentence.split()
    # drop an accidental repeated connector ("khu khu", "giá giá")
    words = [w for i, w in enumerate(words) if i == 0 or w.lower() != words[i - 1].lower()]
    sentence = " ".join(words)
    return sentence[0].upper() + sentence[1:] if frame["lead"] else sentence


# ---------------------------------------------------------------------------
# Relevance (graded): 2 = satisfies all constraints, 1 = all hard constraints and
# exactly one soft constraint inside its tolerance band, 0 otherwise.
# ---------------------------------------------------------------------------
def grades(c: pd.DataFrame, gold: dict, ward_former: dict) -> np.ndarray:
    n = len(c)
    hard_ok = np.ones(n, dtype=bool)
    partial = np.zeros(n, dtype=int)

    def soft(ok, near):
        nonlocal hard_ok, partial
        hard_ok &= ok | near
        partial += (~ok & near).astype(int)

    if gold.get("property_type"):
        hard_ok &= c["property_type"].values == gold["property_type"]
    if gold.get("subtype"):
        hard_ok &= c["subtype"].values == gold["subtype"]
    if gold.get("ward"):
        ok = c["ward"].values == gold["ward"]
        near = np.isin(c["former_area"].values, list(ward_former[gold["ward"]]))
        soft(ok, near)
    if gold.get("former_area"):
        hard_ok &= np.isin(c["former_area"].values, gold["former_area"])
    price = c["price"].values
    gp = gold.get("price") or {}
    if "max" in gp and "min" not in gp:
        soft(price <= gp["max"], price <= gp["max"] * 1.15)
    elif "min" in gp and "max" in gp:
        ok = (price >= gp["min"]) & (price <= gp["max"])
        near = (price >= gp["min"] * 0.85) & (price <= gp["max"] * 1.15)
        soft(ok, near)
    elif "target" in gp:
        dev = np.abs(price - gp["target"]) / gp["target"]
        soft(dev <= 0.10, dev <= 0.20)
    if gold.get("area_min"):
        area = np.nan_to_num(c["area"].values, nan=-1)
        soft(area >= gold["area_min"], area >= gold["area_min"] * 0.85)
    if gold.get("beds"):
        beds = np.nan_to_num(c["bedrooms"].values, nan=-99)
        b = gold["beds"]["value"]
        if gold["beds"]["kind"] == "exact":
            soft(beds == b, beds == b + 1)
        else:
            soft(beds >= b, beds == b - 1)
    if gold.get("legal"):
        hard_ok &= c["legal_status"].values == gold["legal"]
    if gold.get("furnishing"):
        hard_ok &= np.isin(c["furnishing"].values, gold["furnishing"])
    if gold.get("amenity"):
        d = c[f"drive_{gold['amenity']['category']}_km"].values
        km = gold["amenity"]["max_km"]
        soft(d <= km, d <= km * 1.5)
    if gold.get("landmark"):
        d = c[f"dist_{gold['landmark']['name']}_km"].values
        km = gold["landmark"]["max_km"]
        soft(d <= km, d <= km * 1.5)
    for aspect in gold.get("aspects", []):
        hard_ok &= c[aspect].values.astype(bool)
    g = np.zeros(n, dtype=int)
    g[hard_ok & (partial == 0)] = 2
    g[hard_ok & (partial == 1)] = 1
    return g


# ---------------------------------------------------------------------------
# Gold constraint generators (seeded on a real listing => at least one exact hit)
# ---------------------------------------------------------------------------
def round_up(x: float, step: float) -> float:
    return math.ceil(x / step - 1e-9) * step


def price_step(x: float) -> float:
    return 0.5 if x < 10 else (1.0 if x < 30 else 5.0)


def make_price(seed_price: float, rng, kinds=("max", "target", "range"), weights=(0.5, 0.3, 0.2)) -> dict:
    kind = rng.choices(kinds, weights=weights)[0]
    step = price_step(seed_price)
    if kind == "max":
        return {"max": round(round_up(seed_price * rng.uniform(1.0, 1.25), step), 2)}
    if kind == "target":
        t = round(round(seed_price / step) * step, 2)
        if abs(seed_price - t) / t > 0.10:
            t = round(seed_price, 1)
        return {"target": t}
    lo = max(step, math.floor(seed_price * rng.uniform(0.75, 0.95) / step) * step)
    hi = round_up(seed_price * rng.uniform(1.05, 1.25), step)
    return {"min": round(lo, 2), "max": round(hi, 2)}


def price_kind(gp: dict) -> str:
    return "range" if ("min" in gp and "max" in gp) else ("max" if "max" in gp else "target")


def location_gold(seed, rng, ward_counts, p_ward: float):
    if rng.random() < p_ward and ward_counts.get(seed["ward"], 0) >= 10:
        return {"ward": seed["ward"]}, ("ward", seed["ward"])
    fa = seed["former_area"]
    if fa == "Thành Phố Thủ Đức":
        return {"former_area": THU_DUC_GROUP}, ("former", "Thủ Đức")
    return {"former_area": [fa]}, ("former", fa)


def generate(corpus: pd.DataFrame, out_dir: Path) -> None:
    rng = random.Random(SEED)
    c = corpus
    ward_counts = c["ward"].value_counts().to_dict()
    former_counts = c["former_area"].value_counts().to_dict()
    ward_former = c.groupby("ward")["former_area"].apply(lambda s: set(s)).to_dict()

    # frame-disjoint split
    frame_split = {}
    for style in ("S1", "S3", "S4"):
        ids = list(range(len(FRAMES[style])))
        rng.shuffle(ids)
        k_train, k_val = int(round(0.6 * len(ids))), int(round(0.2 * len(ids)))
        for i, fid in enumerate(ids):
            frame_split[(style, fid)] = "train" if i < k_train else ("val" if i < k_train + k_val else "test")
    frame_split.update({("S2", fid): frame_split[("S1", fid)] for fid in range(len(FRAMES["S1"]))})

    # seed-disjoint split
    doc_ids = c["doc_id"].tolist()
    rng.shuffle(doc_ids)
    n = len(doc_ids)
    seed_split = {d: ("train" if i < 0.6 * n else ("val" if i < 0.8 * n else "test")) for i, d in enumerate(doc_ids)}
    c = c.assign(seed_split=c["doc_id"].map(seed_split))
    eligible_former = {fa for fa, k in former_counts.items() if k >= 20}

    queries, seen_text = [], set()
    qcount = 0
    for family, total in FAMILY_COUNTS.items():
        for split, frac in SPLIT_FRACTIONS.items():
            target = int(round(total * frac))
            made, attempts = 0, 0
            pool = c[(c["seed_split"] == split) & (c["former_area"].isin(eligible_former))]
            while made < target and attempts < target * 200:
                attempts += 1
                style = rng.choices(list(STYLE_WEIGHTS), weights=list(STYLE_WEIGHTS.values()))[0]
                fids = [fid for (st, fid), sp in frame_split.items() if st == style and sp == split]
                fid = rng.choice(fids)
                built = build_one(family, pool, rng, ward_counts)
                if built is None:
                    continue
                gold, seed_id, loc = built
                g = grades(corpus, gold, ward_former)
                n_exact, n_rel = int((g == 2).sum()), int((g >= 1).sum())
                if not (1 <= n_exact <= MAX_EXACT and n_rel <= MAX_RELEVANT):
                    continue
                slots = verbalise(gold, loc, style, rng)
                frame = FRAMES["S1" if style == "S2" else style][fid]
                text = render(frame, slots)
                if style == "S2":
                    text = C.strip_accents(text).lower()
                if text in seen_text:
                    continue
                seen_text.add(text)
                qcount += 1
                queries.append(dict(qid=f"q{qcount:04d}", split=split, family=family, style=style,
                                    frame_id=f"{'S1' if style == 'S2' else style}-{fid}", text=text, gold=gold,
                                    seed_doc_id=int(seed_id), n_exact=n_exact, n_partial=n_rel - n_exact,
                                    grades=g))
                made += 1
            if made < target:
                print(f"WARNING {family}/{split}: only {made}/{target}")

    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "queries.jsonl", "w", encoding="utf-8") as fh:
        for q in queries:
            row = {k: v for k, v in q.items() if k != "grades"}
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    with open(out_dir / "qrels.tsv", "w", encoding="utf-8") as fh:
        for q in queries:
            for doc_id, grade in zip(corpus["doc_id"].values, q["grades"]):
                if grade > 0:
                    fh.write(f"{q['qid']}\t0\t{doc_id}\t{grade}\n")
    corpus.to_csv(out_dir / "corpus_attributes.csv", index=False)

    # statistics
    stats = {"n_queries": len(queries), "n_docs": int(len(corpus)), "seed": SEED,
             "by_split": Counter(q["split"] for q in queries),
             "by_split_family": defaultdict(dict), "by_split_style": defaultdict(dict),
             "label_distribution": {}, "n_exact": {}, "frames": {f"{k[0]}-{k[1]}": v for k, v in frame_split.items()}}
    for q in queries:
        stats["by_split_family"][q["split"]][q["family"]] = stats["by_split_family"][q["split"]].get(q["family"], 0) + 1
        stats["by_split_style"][q["split"]][q["style"]] = stats["by_split_style"][q["split"]].get(q["style"], 0) + 1
    for split in SPLIT_FRACTIONS:
        gs = np.concatenate([q["grades"] for q in queries if q["split"] == split])
        stats["label_distribution"][split] = {str(k): int((gs == k).sum()) for k in (0, 1, 2)}
        ne = np.array([q["n_exact"] for q in queries if q["split"] == split])
        npart = np.array([q["n_partial"] for q in queries if q["split"] == split])
        stats["n_exact"][split] = {"mean": float(ne.mean()), "median": float(np.median(ne)), "min": int(ne.min()),
                                   "max": int(ne.max()), "partial_mean": float(npart.mean())}
    with open(out_dir / "stats.json", "w", encoding="utf-8") as fh:
        json.dump(stats, fh, ensure_ascii=False, indent=2, default=dict)
    print(json.dumps(stats, ensure_ascii=False, indent=1, default=dict)[:3000])


def build_one(family: str, pool: pd.DataFrame, rng, ward_counts):
    if family in ("F1_structured", "F2_structured_plus"):
        ptype = rng.choices(["Căn hộ", "Nhà đất"], weights=[0.35, 0.65])[0]
        cand = pool[pool["property_type"] == ptype]
        seed = cand.iloc[rng.randrange(len(cand))]
        gold = {"property_type": ptype}
        loc_gold, loc = location_gold(seed, rng, ward_counts, p_ward=0.55)
        gold.update(loc_gold)
        gold["price"] = make_price(seed["price"], rng)
        p_beds = 0.75 if ptype == "Căn hộ" else 0.35
        if not pd.isna(seed["bedrooms"]) and rng.random() < p_beds:
            b = int(min(seed["bedrooms"], 4))
            kind = "exact" if (b == seed["bedrooms"] and rng.random() < 0.6) else "min"
            gold["beds"] = {"kind": kind, "value": b}
        if family == "F2_structured_plus":
            extras = ["legal", "furnishing"] + (["area"] if ptype == "Nhà đất" and seed["area"] >= 30 else [])
            for extra in rng.sample(extras, k=rng.choice([1, 2]) if len(extras) > 1 else 1):
                if extra == "legal":
                    if seed["legal_status"] != "Sổ hồng riêng":
                        return None
                    gold["legal"] = "Sổ hồng riêng"
                elif extra == "furnishing":
                    if seed["furnishing"] not in ("Đầy đủ", "Cao cấp"):
                        return None
                    gold["furnishing"] = ["Đầy đủ", "Cao cấp"]
                else:
                    gold["area_min"] = int(max(10, math.floor(seed["area"] * rng.uniform(0.8, 1.0) / 5) * 5))
        return gold, seed["doc_id"], loc

    if family == "F3_proximity":
        cat = rng.choices(list(IMPLICIT_AMENITY_KM), weights=[20, 15, 10, 10, 5, 10, 10, 15, 5])[0]
        ptype = rng.choices(["Căn hộ", "Nhà đất"], weights=[0.35, 0.65])[0]
        cand = pool[pool["property_type"] == ptype]
        seed = cand.iloc[rng.randrange(len(cand))]
        dist = seed[f"drive_{cat}_km"]
        explicit = rng.random() < 0.55
        if explicit:
            steps = EXPLICIT_AMENITY_KM.get(cat, EXPLICIT_AMENITY_KM["default"])
            ok = [s for s in steps if s >= dist]
            if not ok:
                return None
            km = ok[min(len(ok) - 1, 1 if rng.random() < 0.3 else 0)]
        else:
            km = IMPLICIT_AMENITY_KM[cat]
            if dist > km:
                return None
        gold = {"property_type": ptype, "amenity": {"category": cat, "max_km": km, "explicit": explicit}}
        loc_gold, loc = location_gold(seed, rng, ward_counts, p_ward=0.3)
        gold.update(loc_gold)
        if rng.random() < 0.6:
            gold["price"] = make_price(seed["price"], rng)
        return gold, seed["doc_id"], loc

    if family == "F4_aspect":
        aspect = rng.choices(list(C.ASPECTS), weights=[20, 15, 15, 15, 10, 10, 5, 10])[0]
        cand = pool[pool[aspect].astype(bool)]
        if cand.empty:
            return None
        seed = cand.iloc[rng.randrange(len(cand))]
        gold = {"property_type": seed["property_type"], "aspects": [aspect]}
        loc_gold, loc = location_gold(seed, rng, ward_counts, p_ward=0.3)
        gold.update(loc_gold)
        if rng.random() < 0.6:
            gold["price"] = make_price(seed["price"], rng)
        if seed["property_type"] == "Căn hộ" and not pd.isna(seed["bedrooms"]) and rng.random() < 0.3:
            gold["beds"] = {"kind": "exact", "value": int(min(seed["bedrooms"], 4))}
        return gold, seed["doc_id"], loc

    if family == "F5_landmark":
        name = rng.choice(list(C.LANDMARKS))
        explicit = rng.random() < 0.4
        km = rng.choice([1.0, 2.0, 3.0]) if explicit else LANDMARK_KM[name]
        cand = pool[pool[f"dist_{name}_km"] <= km]
        if cand.empty:
            return None
        seed = cand.iloc[rng.randrange(len(cand))]
        gold = {"property_type": seed["property_type"], "landmark": {"name": name, "max_km": km, "explicit": explicit}}
        if rng.random() < 0.7:
            gold["price"] = make_price(seed["price"], rng)
        if seed["property_type"] == "Căn hộ" and not pd.isna(seed["bedrooms"]) and rng.random() < 0.4:
            gold["beds"] = {"kind": "exact", "value": int(min(seed["bedrooms"], 4))}
        return gold, seed["doc_id"], None

    if family == "F6_subtype":
        subtype = rng.choices(["Nhà mặt phố", "Biệt thự/Liền kề", "Shophouse"], weights=[0.6, 0.3, 0.1])[0]
        cand = pool[pool["subtype"] == subtype]
        if cand.empty:
            return None
        seed = cand.iloc[rng.randrange(len(cand))]
        gold = {"property_type": seed["property_type"], "subtype": subtype}
        loc_gold, loc = location_gold(seed, rng, ward_counts, p_ward=0.15)
        gold.update(loc_gold)
        if rng.random() < 0.7:
            gold["price"] = make_price(seed["price"], rng)
        if subtype != "Shophouse" and seed["area"] >= 30 and rng.random() < 0.3:
            gold["area_min"] = int(max(10, math.floor(seed["area"] * rng.uniform(0.8, 1.0) / 5) * 5))
        return gold, seed["doc_id"], loc
    raise ValueError(family)


def verbalise(gold: dict, loc, style: str, rng) -> dict:
    vs = "S1" if style == "S2" else style
    slots = {}
    type_key = gold.get("subtype") or gold.get("property_type")
    slots["T"] = rng.choice(TYPE_PHRASES[type_key][vs])
    if gold.get("aspects"):
        def aspect_text(a):
            key = f"{a}@{gold.get('property_type')}"
            return rng.choice(ASPECT_PHRASES.get(key, ASPECT_PHRASES[a])[vs])
        slots["A"] = " ".join(aspect_text(a) for a in gold["aspects"])
    if gold.get("beds"):
        slots["B"] = beds_phrase(gold["beds"]["kind"], gold["beds"]["value"], style, rng)
    if gold.get("area_min"):
        slots["S"] = area_phrase(gold["area_min"], style, rng)
    if loc is not None:
        kind, value = loc
        slots["L"] = ward_phrase(value, style, rng) if kind == "ward" else former_phrase(value, style, rng)
    if gold.get("amenity"):
        a = gold["amenity"]
        slots["M"] = amenity_phrase(a["category"], a["max_km"], a["explicit"], style, rng)
    if gold.get("landmark"):
        k = gold["landmark"]
        slots["K"] = landmark_phrase(k["name"], k["max_km"], k["explicit"], style, rng)
    if gold.get("legal"):
        slots["G"] = rng.choice(LEGAL_PHRASES[vs])
    if gold.get("furnishing"):
        slots["F"] = rng.choice(FURN_PHRASES[vs])
    if gold.get("price"):
        slots["P"] = price_phrase(price_kind(gold["price"]), gold["price"], style, rng)
    return slots


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="benchmark_out")
    args = ap.parse_args()
    generate(C.build_corpus(), Path(args.out))
