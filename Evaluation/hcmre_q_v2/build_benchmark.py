"""HCMRE-Q v2: 1,000 Vietnamese queries with graded (0-3), ward-first relevance labels over Data/v3 (v3.1).

Definitions: PROTOCOL.md. Labels come only from corpus.py (no backend import).

    python build_benchmark.py --out data

Outputs (--out):
  queries.jsonl          qid, split, family, style, frame_id, loc_kind, text, gold, seed_doc_id, n3/n2/n1
  qrels.tsv              TREC "qid 0 doc_id grade" for grade >= 1 (doc_id = listing_id)
  corpus_attributes.csv  the label-side attribute table
  stats.json             counts per split / family / style / location kind, label distribution
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

import corpus as C
import runlog

SEED = 20261028
SPLITS = {"train": 0.6, "val": 0.2, "test": 0.2}
FAMILY_COUNTS = {"F1_structured": 280, "F2_structured_plus": 100, "F3_proximity": 200,
                 "F4_aspect": 240, "F5_landmark": 80, "F6_subtype": 100}
LOC_MIX = {  # P(ward), P(former district), P(no location)
    "F1_structured": (0.80, 0.20, 0.0), "F2_structured_plus": (0.80, 0.20, 0.0),
    "F3_proximity": (0.75, 0.15, 0.10), "F4_aspect": (0.75, 0.15, 0.10),
    "F5_landmark": (0.0, 0.0, 1.0), "F6_subtype": (0.70, 0.20, 0.10)}
STYLE_WEIGHTS = {"S1": 0.30, "S2": 0.20, "S3": 0.25, "S4": 0.25}
FRAMES_PER_SPLIT = {"train": 7, "val": 2, "test": 3}
MAX_EXACT, MAX_RELEVANT = 50, 200
MIN_WARD_LISTINGS, MIN_FORMER_LISTINGS = 10, 20
MIN_SEED_PRICE = 1.0
DUAL_MENTION_P = 0.15

IMPLICIT_AMENITY_KM = {"school": 1.0, "market": 1.0, "supermarket": 1.0, "park": 1.0, "bus_stop": 0.5,
                       "hospital": 2.0, "mall": 2.0, "metro": 2.0, "college_university": 2.0}
EXPLICIT_AMENITY_KM = {"metro": [1.0, 2.0, 3.0], "bus_stop": [0.3, 0.5, 1.0], "hospital": [1.0, 2.0, 3.0],
                       "mall": [1.0, 2.0, 3.0], "college_university": [1.0, 2.0, 3.0],
                       "school": [0.3, 0.5, 1.0, 1.5, 2.0], "market": [0.3, 0.5, 1.0, 1.5, 2.0],
                       "supermarket": [0.3, 0.5, 1.0, 1.5, 2.0], "park": [0.3, 0.5, 1.0, 1.5, 2.0]}
LANDMARK_KM = {"ben_thanh": 2.0, "tan_son_nhat": 3.0, "landmark81": 2.0, "phu_my_hung": 2.0, "dhqg": 3.0}
TOL = {"price_max": 0.15, "price_target_ok": 0.10, "price_target_band": 0.10, "price_range": 0.15,
       "area": 0.15, "distance": 0.5}
EPS = 1e-9   # the bounds of PROTOCOL §5 are inclusive: 4.4 is within 10% of 4.0 although |4.4-4.0|/4.0 > 0.1 in floats


# =========================================================================== relevance (PROTOCOL §5)
def soft_constraints(c: pd.DataFrame, gold: dict, tol_scale: float = 1.0):
    """List of (ok, band) boolean arrays, band excluding ok; NaN attribute -> neither."""
    out = []
    t = {k: v * tol_scale for k, v in TOL.items()}
    gp = gold.get("price")
    if gp:
        p = c["price"].values
        valid = ~np.isnan(p)
        if "min" in gp and "max" in gp:
            ok = valid & (p >= gp["min"] - EPS) & (p <= gp["max"] + EPS)
            band = valid & (p >= gp["min"] * (1 - t["price_range"]) - EPS) & (p <= gp["max"] * (1 + t["price_range"]) + EPS)
        elif "max" in gp:
            ok = valid & (p <= gp["max"] + EPS)
            band = valid & (p <= gp["max"] * (1 + t["price_max"]) + EPS)
        else:
            dev = np.abs(p - gp["target"]) / gp["target"]
            ok = valid & (dev <= TOL["price_target_ok"] + EPS)
            band = valid & (dev <= TOL["price_target_ok"] + t["price_target_band"] + EPS)
        out.append((ok, band & ~ok))
    if gold.get("area_min"):
        a = c["area"].values
        valid = ~np.isnan(a)
        ok = valid & (a >= gold["area_min"] - EPS)
        out.append((ok, valid & (a >= gold["area_min"] * (1 - t["area"]) - EPS) & ~ok))
    if gold.get("beds"):
        b = c["bedrooms"].values
        valid = ~np.isnan(b)
        v = gold["beds"]["value"]
        if gold["beds"]["kind"] == "exact":
            out.append((valid & (b == v), valid & (b == v + 1)))
        else:
            out.append((valid & (b >= v), valid & (b == v - 1)))
    for key, col in (("amenity", lambda g: f"drive_{g['category']}_km"), ("landmark", lambda g: f"dist_{g['name']}_km")):
        g = gold.get(key)
        if g:
            d = c[col(g)].values
            valid = ~np.isnan(d)
            ok = valid & (d <= g["max_km"] + EPS)
            out.append((ok, valid & (d <= g["max_km"] * (1 + t["distance"]) + EPS) & ~ok))
    return out


def hard_ok(c: pd.DataFrame, gold: dict) -> np.ndarray:
    ok = np.ones(len(c), dtype=bool)
    if gold.get("property_type"):
        ok &= c["property_type"].values == gold["property_type"]
    if gold.get("subtype"):
        ok &= c["subtype"].values == gold["subtype"]
    if gold.get("has_title"):
        ok &= c["has_title"].values == 1
    if gold.get("full_furniture"):
        ok &= c["full_furniture"].values == 1
    for aspect in gold.get("aspects", []):
        ok &= c[aspect].values.astype(bool)
    return ok


def grades(c: pd.DataFrame, gold: dict, loc: C.Locator, near_km: float = C.NEAR_KM, tol_scale: float = 1.0,
           exclude: np.ndarray | None = None) -> np.ndarray:
    hard = hard_ok(c, gold)
    fail = np.zeros(len(c), dtype=bool)
    n_band = np.zeros(len(c), dtype=int)
    for ok, band in soft_constraints(c, gold, tol_scale):
        fail |= ~ok & ~band
        n_band += band
    all_ok, one_off = ~fail & (n_band == 0), ~fail & (n_band == 1)
    g = np.zeros(len(c), dtype=np.int8)
    if gold.get("location"):
        kind, values = C.location_values(gold["location"])
        inside, near = loc.masks(kind, values, near_km)
        g[hard & inside & all_ok] = 3
        g[hard & inside & one_off] = 2
        g[hard & near & all_ok] = 1
    else:
        g[hard & all_ok] = 3
        g[hard & one_off] = 2
    if exclude is not None:
        g[exclude] = 0
    return g


# =========================================================================== verbalisers
DIGIT_WORDS = {1: "một", 2: "hai", 3: "ba", 4: "bốn", 5: "năm", 6: "sáu", 7: "bảy", 8: "tám", 9: "chín", 10: "mười"}


def int_words(n: int) -> str:
    if n in DIGIT_WORDS:
        return DIGIT_WORDS[n]
    if 10 < n < 20:
        return "mười " + {5: "lăm", 1: "một"}.get(n - 10, DIGIT_WORDS[n - 10])
    if 20 <= n < 100:
        tens, unit = divmod(n, 10)
        return f"{DIGIT_WORDS[tens]} mươi" + ("" if unit == 0 else " " + {1: "mốt", 5: "lăm"}.get(unit, DIGIT_WORDS[unit]))
    return str(n)


# Surface fixes after the pre-audit (PROTOCOL.md §9, item 5) are written so that they draw exactly the same random
# numbers as before: gold constraints, seeds and qrels stay byte-identical, only the wording of some queries changes.
def num_s1(x: float, rng, comma: bool | None = None) -> tuple[str, bool | None]:
    """'8.5' or '8,5'. `comma` forces the separator so both ends of a range are written alike."""
    if float(x).is_integer():
        return str(int(x)), comma
    text = f"{x:.2f}".rstrip("0").rstrip(".")
    drawn = rng.random() < 0.5
    use = drawn if comma is None else comma
    return (text.replace(".", ",") if use else text), use


def price_s3(x: float, rng) -> str:
    whole, frac = int(x), round((x - int(x)) * 10)
    unit = rng.choice(["tỷ", "ty", "tỏi"])
    if frac == 0:
        return rng.choice([f"{whole}{unit}", f"{whole} {unit}"])
    return rng.choice([f"{whole}ty{frac}", f"{whole} tỷ {frac}", f"{whole}.{frac}ty"])


def price_s4(x: float, rng, words: bool | None = None) -> tuple[str, bool]:
    """Spoken price: 'sáu tỷ hai' or '6 tỷ 2'. The tail follows the head, and `words` forces the style so both ends
    of a range read alike."""
    whole, frac = int(x), round((x - int(x)) * 10)
    drawn = rng.random() < 0.6
    use = drawn if words is None else words
    head = int_words(whole) if use else str(whole)
    if frac == 0:
        return f"{head} tỷ", use
    if frac == 5:
        return f"{head} tỷ rưỡi", use
    rng.random()                      # the tail style used to be drawn here; kept so the random stream is unchanged
    return f"{head} tỷ {DIGIT_WORDS.get(frac, str(frac)) if use else frac}", use


def price_phrase(gp: dict, style: str, rng) -> str:
    kind = "range" if ("min" in gp and "max" in gp) else ("max" if "max" in gp else "target")
    if style in ("S1", "S2"):
        if kind == "max":
            return rng.choice(["dưới {} tỷ", "tối đa {} tỷ", "không quá {} tỷ", "{} tỷ đổ lại",
                               "từ {} tỷ trở xuống"]).format(num_s1(gp["max"], rng)[0])
        if kind == "target":
            return rng.choice(["khoảng {} tỷ", "tầm {} tỷ", "{} tỷ", "cỡ {} tỷ", "quanh {} tỷ"]).format(
                num_s1(gp["target"], rng)[0])
        tpl = rng.choice(["từ {} đến {} tỷ", "{} - {} tỷ", "trong khoảng {} tới {} tỷ"])
        lo, comma = num_s1(gp["min"], rng)
        return tpl.format(lo, num_s1(gp["max"], rng, comma)[0])
    if style == "S3":
        if kind == "max":
            return rng.choice(["<{}", "dưới {}", "max {}", "{} đổ lại"]).format(price_s3(gp["max"], rng))
        if kind == "target":
            return rng.choice(["~{}", "tầm {}", "{}", "khoảng {}"]).format(price_s3(gp["target"], rng))
        unit, f = rng.choice(["tỷ", "ty"]), (lambda v: f"{v:g}")
        return rng.choice([f"{f(gp['min'])}-{f(gp['max'])}{unit}", f"{f(gp['min'])}-{f(gp['max'])} {unit}",
                           f"từ {f(gp['min'])} đến {f(gp['max'])}{unit}"])
    if kind == "max":
        return rng.choice(["không quá {}", "dưới {}", "{} đổ lại", "tầm {} đổ xuống", "trong vòng {}"]).format(
            price_s4(gp["max"], rng)[0])
    if kind == "target":
        return rng.choice(["khoảng {}", "tầm {}", "loanh quanh {}", "cỡ {}"]).format(price_s4(gp["target"], rng)[0])
    tpl = rng.choice(["từ {} tới {}", "trong khoảng {} đến {}"])
    lo, words = price_s4(gp["min"], rng)
    return tpl.format(lo, price_s4(gp["max"], rng, words)[0])


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
    return rng.choice([f"rộng tầm {int_words(a) if a < 100 else a} mét vuông trở lên", f"diện tích không dưới {a} mét vuông"])


def dist_text(km: float, style: str, rng) -> str:
    if km < 1:
        m = int(round(km * 1000))
        if style == "S4":
            return {300: "ba trăm mét", 500: "năm trăm mét"}.get(m, f"{m} mét")
        return rng.choice([f"{m}m", f"{m} m"])
    v = f"{km:g}"
    if style in ("S1", "S2") and rng.random() < 0.4:
        v = v.replace(".", ",")
    return rng.choice([f"{v}km", f"{v} km"]) if style != "S4" else f"{v} cây số"


AMENITY_NAMES = {
    "S1": {"school": ["trường học", "trường"], "metro": ["ga metro", "metro"], "market": ["chợ"],
           "supermarket": ["siêu thị"], "park": ["công viên"], "hospital": ["bệnh viện"],
           "mall": ["trung tâm thương mại", "TTTM"], "college_university": ["trường đại học", "đại học"],
           "bus_stop": ["trạm xe buýt", "trạm bus"]},
    "S3": {"school": ["trường"], "metro": ["metro", "ga metro"], "market": ["chợ"], "supermarket": ["siêu thị"],
           "park": ["công viên"], "hospital": ["BV", "bệnh viện"], "mall": ["TTTM"],
           "college_university": ["ĐH", "trường ĐH"], "bus_stop": ["trạm bus"]},
    "S4": {"school": ["trường học"], "metro": ["ga metro", "tuyến metro"], "market": ["chợ"], "supermarket": ["siêu thị"],
           "park": ["công viên"], "hospital": ["bệnh viện"], "mall": ["trung tâm thương mại"],
           "college_university": ["trường đại học"], "bus_stop": ["trạm xe buýt"]},
}
AMENITY_PURPOSE = {"school": "cho con đi học", "metro": "cho tiện đi làm", "market": "cho tiện đi chợ",
                   "supermarket": "cho tiện mua sắm", "park": "để tập thể dục", "hospital": "cho tiện khám chữa bệnh",
                   "mall": "để cuối tuần đi mua sắm", "college_university": "cho tiện đi học", "bus_stop": "cho tiện đi lại"}


def amenity_phrase(a: dict, style: str, rng) -> str:
    name = rng.choice(AMENITY_NAMES["S1" if style == "S2" else style][a["category"]])
    if style in ("S1", "S2"):
        if a["explicit"]:
            return rng.choice(["cách {n} không quá {d}", "cách {n} dưới {d}", "có {n} trong vòng {d}"]).format(
                n=name, d=dist_text(a["max_km"], style, rng))
        return rng.choice(["gần {n}", "gần {n} cho tiện"]).format(n=name)
    if style == "S3":
        if a["explicit"]:
            return rng.choice(["cách {n} <{d}", "gần {n} {d}"]).format(n=name, d=dist_text(a["max_km"], style, rng))
        return f"gần {name}"
    if a["explicit"]:
        return rng.choice(["có {n} cách nhà tầm {d} thôi", "đi chưa tới {d} là tới {n}"]).format(
            n=name, d=dist_text(a["max_km"], style, rng))
    return f"gần {name} {AMENITY_PURPOSE[a['category']]}"


LANDMARK_NAMES = {
    "ben_thanh": {"S1": ["chợ Bến Thành"], "S3": ["chợ Bến Thành"], "S4": ["chợ Bến Thành"]},
    "tan_son_nhat": {"S1": ["sân bay Tân Sơn Nhất", "sân bay"], "S3": ["sân bay TSN", "sân bay"], "S4": ["sân bay Tân Sơn Nhất"]},
    "landmark81": {"S1": ["Landmark 81", "tòa Landmark 81"], "S3": ["LM81", "Landmark81"], "S4": ["tòa Landmark 81"]},
    "phu_my_hung": {"S1": ["Phú Mỹ Hưng", "khu Phú Mỹ Hưng"], "S3": ["PMH"], "S4": ["khu đô thị Phú Mỹ Hưng"]},
    "dhqg": {"S1": ["Làng Đại học Thủ Đức", "ĐH Quốc gia TP.HCM"], "S3": ["làng ĐH", "ĐHQG"], "S4": ["làng đại học"]},
}


def landmark_phrase(k: dict, style: str, rng) -> str:
    label = rng.choice(LANDMARK_NAMES[k["name"]]["S1" if style == "S2" else style])
    if k["explicit"]:
        if style == "S3":
            return f"cách {label} <{dist_text(k['max_km'], style, rng)}"
        if style == "S4":
            return f"cách {label} chừng {dist_text(k['max_km'], style, rng)} trở lại"
        return f"cách {label} không quá {dist_text(k['max_km'], style, rng)}"
    return f"gần {label}"


ASPECT_PHRASES = {
    "hem_xe_hoi": {"S1": ["hẻm xe hơi", "hẻm ô tô", "ô tô đỗ cửa", "hẻm xe hơi vào tận nhà"], "S3": ["HXH", "hxh", "hẻm oto"],
                   "S4": ["trong hẻm rộng cho ô tô vào được", "xe hơi đậu được trước cửa"]},
    "dong_tien": {"S1": ["đang có dòng tiền cho thuê", "đang cho thuê có thu nhập", "đang khai thác căn hộ dịch vụ"],
                  "S3": ["CHDV", "dòng tiền", "có HĐ thuê"], "S4": ["mua về là có dòng tiền cho thuê ngay", "đang có người thuê sẵn"]},
    "can_goc": {"S1": ["góc 2 mặt tiền", "lô góc", "căn góc"], "S3": ["góc 2MT", "lô góc", "căn góc"],
                "S4": ["ở vị trí góc hai mặt tiền"]},
    "can_goc@Căn hộ": {"S1": ["góc", "căn góc"], "S3": ["căn góc", "góc"], "S4": ["căn góc thoáng hai mặt"]},
    "nha_moi": {"S1": ["mới xây", "xây mới", "mới 100%"], "S3": ["mới 100%", "mới xây"],
                "S4": ["mới xây, dọn vào ở ngay", "mới hoàn thiện, không phải sửa sang"]},
    "view_song": {"S1": ["view sông", "nhìn ra sông", "hướng sông"], "S3": ["view sông"], "S4": ["có view nhìn ra sông"]},
    "thang_may_nha": {"S1": ["có thang máy"], "S3": ["có thang máy", "thang máy"], "S4": ["có thang máy cho người già"]},
    "san_vuon": {"S1": ["có sân vườn", "có vườn"], "S3": ["sân vườn"], "S4": ["có khoảng sân vườn trồng cây"]},
    "ho_boi": {"S1": ["có hồ bơi", "có bể bơi"], "S3": ["có hồ bơi"], "S4": ["có hồ bơi cho bọn trẻ"]},
}
TYPE_PHRASES = {
    "Căn hộ": {"S1": ["căn hộ", "căn hộ chung cư", "chung cư"], "S3": ["CH", "CHCC", "căn hộ", "cc"],
               "S4": ["căn hộ", "một căn chung cư", "căn hộ chung cư"]},
    "Nhà đất": {"S1": ["nhà", "nhà riêng", "nhà phố", "nhà ở"], "S3": ["nhà", "nhà phố"], "S4": ["một căn nhà", "nhà riêng", "nhà"]},
    "Nhà mặt phố": {"S1": ["nhà mặt phố", "nhà mặt tiền", "nhà mặt tiền đường"], "S3": ["nhà MT", "nhà mặt tiền", "MTKD"],
                    "S4": ["nhà mặt tiền đường để kinh doanh"]},
    "Biệt thự/Liền kề": {"S1": ["biệt thự", "nhà liền kề", "biệt thự liền kề"], "S3": ["biệt thự", "BT liền kề"],
                         "S4": ["một căn biệt thự"]},
    "Shophouse": {"S1": ["shophouse", "nhà phố thương mại"], "S3": ["shophouse"], "S4": ["một căn shophouse"]},
}
TITLE_PHRASES = {"S1": ["đã có sổ hồng", "có sổ hồng", "đã có sổ"], "S3": ["có sổ", "sổ hồng", "đã có sổ"],
                 "S4": ["giấy tờ đầy đủ, đã có sổ hồng"]}
FURN_PHRASES = {"S1": ["đầy đủ nội thất", "full nội thất"], "S3": ["full NT", "full nội thất"],
                "S4": ["có sẵn nội thất, chỉ việc dọn vào"]}


class Names:
    """Ward / former-district surface forms. A bare name is used only when it is not ambiguous."""

    def __init__(self, c: pd.DataFrame):
        self.ward_base = {w: w.split(" ", 1)[1] for w in c["ward"].unique()}
        self.former_base = {f: self.strip_former(f) for f in c["former_area"].unique()}
        bases_f = set(self.former_base.values()) | {"Thủ Đức"}
        bases_w = set(self.ward_base.values())
        self.ward_needs_prefix = {w for w, b in self.ward_base.items() if b in bases_f}
        self.former_needs_prefix = {f for f, b in self.former_base.items() if b in bases_w}
        self.collisions = sorted(bases_f & bases_w)

    @staticmethod
    def strip_former(f: str) -> str:
        for p in ("Thành Phố ", "Thành phố ", "Quận ", "Huyện ", "Thị Xã ", "Thị xã "):
            if f.startswith(p):
                return f[len(p):]
        return f

    def ward(self, ward: str, style: str, rng) -> str:
        prefix, name = ward.split(" ", 1)
        bare_ok = ward not in self.ward_needs_prefix
        if prefix == "Xã":
            opts = {"S1": [f"xã {name}", f"Xã {name}"], "S3": [f"xã {name}", f"X.{name}"], "S4": [f"xã {name}"]}
        else:
            opts = {"S1": [f"phường {name}", f"Phường {name}", f"P. {name}"], "S3": [f"P.{name}", f"P {name}", f"p.{name}"],
                    "S4": [f"phường {name}"]}
        o = list(opts["S1" if style == "S2" else style])
        if bare_ok:
            o += {"S1": [name], "S2": [name], "S3": [name], "S4": [f"khu {name}"]}[style]
        return rng.choice(o)

    def former(self, area: str, style: str, rng, with_old: bool = False) -> str:
        if area == "Thành Phố Thủ Đức":
            return rng.choice({"S1": ["TP Thủ Đức", "thành phố Thủ Đức"], "S2": ["TP Thủ Đức", "thành phố Thủ Đức"],
                               "S3": ["TP.Thủ Đức", "TP Thủ Đức"], "S4": ["thành phố Thủ Đức", "khu TP Thủ Đức"]}[style])
        name = self.former_base[area]
        prefix = area[: -len(name)].strip()
        numeric = name.isdigit()
        bare_ok = area not in self.former_needs_prefix and not numeric
        if prefix.lower() == "thành phố":
            o = {"S1": [f"TP {name}", f"thành phố {name}"], "S3": [f"TP.{name}", f"TP {name}"], "S4": [f"thành phố {name}"]}
        elif prefix == "Quận":
            o = {"S1": [f"quận {name}", f"Quận {name}"], "S3": [f"Q{name}", f"Q.{name}"] if numeric else [f"Q.{name}", f"Q {name}"],
                 "S4": [f"quận {name}", f"quận {name} cũ"]}
        else:  # Huyện
            o = {"S1": [f"huyện {name}", f"Huyện {name}"], "S3": [f"H.{name}", f"huyện {name}"], "S4": [f"huyện {name}"]}
        opts = list(o["S1" if style == "S2" else style])
        if bare_ok:
            opts.append(name)
        text = rng.choice(opts)
        if (with_old or (style in ("S1", "S2", "S4") and rng.random() < 0.2)) and not text.endswith(" cũ"):
            text += " cũ"
        return text


def frame(lead, order, conn=None, sep=" ", tail=""):
    return dict(lead=lead, order=order, conn=conn or {}, sep=sep, tail=tail)


FRAMES = {
    "S1": [
        frame("", ["T", "A", "B", "L", "M", "K", "S", "G", "F", "P"], {"L": "ở", "P": "giá"}),
        frame("Tìm", ["T", "A", "B", "L", "P", "M", "K", "S", "G", "F"], {"L": "tại"}),
        frame("Cần mua", ["T", "A", "L", "B", "S", "G", "F", "M", "K", "P"], {"L": "khu vực", "P": "giá"}, sep=", "),
        frame("Bán", ["T", "A", "B", "S", "L", "M", "K", "G", "F", "P"], {"L": "ở", "P": "giá"}),
        frame("Tôi muốn mua", ["T", "A", "B", "L", "P", "M", "K", "S", "G", "F"], {"L": "ở"}, sep=", ", tail="."),
        frame("Có", ["T", "A", "L", "B", "M", "K", "S", "G", "F", "P"], {"T+": "nào", "L": "ở", "P": "giá"}, tail=" không?"),
        frame("Danh sách", ["T", "A", "L", "P", "B", "M", "K", "S", "G", "F"], {"L": "tại"}),
        frame("Gợi ý", ["T", "A", "B", "L", "M", "K", "S", "G", "F", "P"], {"L": "ở", "P": "trong tầm"}),
        frame("", ["L", "T", "A", "B", "M", "K", "S", "G", "F", "P"]),
        frame("Mua", ["T", "A", "L", "P", "B", "S", "G", "F", "M", "K"], {"L": "ở"}),
        frame("Cần tìm", ["T", "A", "B", "L", "M", "K", "S", "G", "F", "P"], {"L": "thuộc", "P": "giá"}, sep=", "),
        frame("Xin thông tin", ["T", "A", "L", "B", "M", "K", "S", "G", "F", "P"], {"L": "tại", "P": "giá"}, tail="."),
    ],
    "S3": [
        frame("", ["T", "B", "A", "L", "P", "M", "K", "S", "G", "F"]),
        frame("cần mua", ["T", "A", "L", "P", "B", "M", "K", "S", "G", "F"]),
        frame("", ["T", "A", "L", "B", "S", "G", "F", "M", "K", "P"], sep=" - "),
        frame("tìm", ["T", "B", "A", "L", "M", "K", "S", "G", "F", "P"]),
        frame("mua", ["T", "L", "A", "B", "P", "M", "K", "S", "G", "F"], sep=", "),
        frame("", ["P", "T", "B", "A", "L", "M", "K", "S", "G", "F"]),
        frame("bán", ["T", "A", "B", "S", "L", "P", "M", "K", "G", "F"]),
        frame("", ["L", "T", "A", "B", "P", "M", "K", "S", "G", "F"]),
        frame("cần tìm", ["T", "A", "B", "S", "G", "F", "L", "M", "K", "P"]),
        frame("hỏi mua", ["T", "L", "B", "A", "M", "K", "S", "G", "F", "P"], sep=", "),
        frame("ai có", ["T", "L", "B", "A", "P", "M", "K", "S", "G", "F"], tail=" ib"),
        frame("cần gấp", ["T", "A", "B", "L", "S", "G", "F", "M", "K", "P"], sep=", "),
    ],
    "S4": [
        frame("Mình đang tìm", ["T", "A", "L", "B", "M", "K", "S", "G", "F", "P"], {"L": "ở", "P": "ngân sách"}, sep=", ", tail="."),
        frame("Gia đình mình cần mua", ["T", "B", "A", "L", "M", "K", "S", "G", "F", "P"], {"L": "ở", "P": "tài chính"},
              sep=", ", tail=", có căn nào phù hợp không?"),
        frame("Anh chị tư vấn giúp em", ["T", "A", "L", "P", "B", "M", "K", "S", "G", "F"], {"L": "ở", "P": "giá"}, tail=" với ạ."),
        frame("Em cần", ["T", "A", "B", "L", "M", "K", "S", "G", "F", "P"], {"L": "bên"}, sep=", ", tail=" ạ."),
        frame("Có", ["T", "A", "L", "M", "K", "B", "S", "G", "F", "P"], {"T+": "nào", "L": "ở", "P": "mà giá"}, tail=" không ạ?"),
        frame("Tôi muốn tìm", ["T", "A", "L", "P", "B", "M", "K", "S", "G", "F"], {"L": "ở", "P": "với mức giá"}, tail="."),
        frame("Cho mình xem", ["T", "A", "B", "L", "M", "K", "S", "G", "F", "P"], {"L": "khu", "P": "giá"}, tail=" nhé."),
        frame("Đang cần mua", ["T", "A", "L", "B", "M", "K", "S", "G", "F", "P"], {"L": "ở", "P": "vốn"}, sep=", ",
              tail=", ai có giới thiệu giúp."),
        frame("Vợ chồng mình muốn mua", ["T", "B", "L", "A", "M", "K", "S", "G", "F", "P"], {"L": "ở", "P": "giá"}, sep=", ", tail="."),
        frame("Nhờ tìm giúp", ["T", "A", "L", "B", "M", "K", "S", "G", "F", "P"], {"L": "khu", "P": "giá"}, sep=", ", tail=" nha."),
        frame("Mình muốn hỏi còn", ["T", "A", "L", "B", "M", "K", "S", "G", "F", "P"], {"T+": "nào", "L": "ở", "P": "giá"},
              tail=" không ạ?"),
        frame("Nhà mình đang tìm", ["T", "B", "A", "L", "M", "K", "S", "G", "F", "P"], {"L": "quanh", "P": "ngân sách"}, sep=", ",
              tail=", nhờ mọi người giới thiệu."),
    ],
}


NUMBER_START = ("một ", "hai ", "ba ", "bốn ", "năm ", "sáu ", "bảy ", "tám ", "chín ", "mười ")
QUALIFIED_PRICE = re.compile(r"(?:trong khoảng|khoảng|từ|dưới|tối đa|không quá|cỡ|quanh|tầm) ")


def render(fr: dict, slots: dict) -> str:
    parts = []
    for key in fr["order"]:
        phrase = slots.get(key)
        if not phrase:
            continue
        conn = fr["conn"].get(key, "")
        # connector clashes found in the pre-audit (PROTOCOL.md §9, item 5)
        if key == "P" and conn == "trong tầm" and QUALIFIED_PRICE.match(phrase):
            conn = "giá"                                   # not "trong tầm trong khoảng 5 tới 8 tỷ"
        if key == "L" and conn == "ở" and parts and re.search(r"(?:^|\s)ở(?: ngay| nào)?$", parts[-1][1]):
            conn = "tại"                                   # not "nhà ở, ở quận 8", "nhà ở nào ở X", "dọn vào ở ngay ở X"
        if key == "T" and fr["conn"].get("T+") == "nào" and phrase.startswith("một "):
            phrase = phrase[len("một "):]                  # "có căn nhà nào", not "có một căn nhà nào"
        text = f"{conn} {phrase}".strip() if conn else phrase
        if key == "T" and fr["conn"].get("T+"):
            text = f"{text} {fr['conn']['T+']}"
        parts.append((key, text))
    body = parts[0][1] if parts else ""
    for (prev, _), (key, part) in zip(parts, parts[1:]):
        sep = " " if fr["sep"] == " " else fr["sep"]
        # "6 tỷ 3 phòng ngủ" would read as 6,3 tỷ: separate a price from a following number
        if prev == "P" and sep == " " and (part[:1].isdigit() or part.lower().startswith(NUMBER_START)):
            sep = ", "
        body += sep + part
    sentence = f"{fr['lead']} {body}".strip() + fr["tail"]
    words = sentence.split()
    words = [w for i, w in enumerate(words) if i == 0 or w.lower() != words[i - 1].lower()]  # "khu khu"
    sentence = " ".join(words)
    return sentence[0].upper() + sentence[1:] if fr["lead"] else sentence


def verbalise(gold: dict, style: str, names: Names, rng) -> dict:
    vs = "S1" if style == "S2" else style
    slots = {"T": rng.choice(TYPE_PHRASES[gold.get("subtype") or gold["property_type"]][vs])}
    if gold.get("aspects"):
        slots["A"] = " ".join(rng.choice(ASPECT_PHRASES.get(f"{a}@{gold['property_type']}", ASPECT_PHRASES[a])[vs])
                              for a in gold["aspects"])
    if gold.get("beds"):
        slots["B"] = beds_phrase(gold["beds"]["kind"], gold["beds"]["value"], style, rng)
    if gold.get("area_min"):
        slots["S"] = area_phrase(gold["area_min"], style, rng)
    loc = gold.get("location")
    if loc:
        if loc["kind"] == "ward":
            text = names.ward(loc["value"], style, rng)
            if loc.get("with_former"):
                old = names.former(loc["with_former"], style, rng, with_old=True)
                text = rng.choice([f"{text} ({old})", f"{text}, {old}"])
            slots["L"] = text
        else:
            slots["L"] = names.former(loc["value"], style, rng)
    if gold.get("amenity"):
        slots["M"] = amenity_phrase(gold["amenity"], style, rng)
    if gold.get("landmark"):
        slots["K"] = landmark_phrase(gold["landmark"], style, rng)
    if gold.get("has_title"):
        slots["G"] = rng.choice(TITLE_PHRASES[vs])
    if gold.get("full_furniture"):
        slots["F"] = rng.choice(FURN_PHRASES[vs])
    if gold.get("price"):
        slots["P"] = price_phrase(gold["price"], style, rng)
    return slots


# =========================================================================== gold constraints from a seed listing
def round_up(x: float, step: float) -> float:
    return math.ceil(x / step - 1e-9) * step


def price_step(x: float) -> float:
    return 0.5 if x < 10 else (1.0 if x < 30 else 5.0)


def beds_gold(b: float) -> dict:
    """'exactly b bedrooms', or 'at least 4' for a seed with more than 4 (so the seed always satisfies its own query)."""
    v = int(min(b, 4))
    return {"kind": "exact" if v == b else "min", "value": v}


def make_price(p: float, rng) -> dict:
    kind = rng.choices(["max", "target", "range"], weights=[0.5, 0.3, 0.2])[0]
    step = price_step(p)
    if kind == "max":
        return {"max": round(round_up(p * rng.uniform(1.0, 1.25), step), 2)}
    if kind == "target":
        t = round(round(p / step) * step, 2)
        if abs(p - t) / t > 0.10:
            t = round(p, 1)
        return {"target": t}
    lo = max(step, math.floor(p * rng.uniform(0.75, 0.95) / step) * step)
    return {"min": round(lo, 2), "max": round(round_up(p * rng.uniform(1.05, 1.25), step), 2)}


class Builder:
    def __init__(self, c: pd.DataFrame, rng):
        self.c, self.rng = c, rng
        wc, fc = c["ward"].value_counts(), c["former_area"].value_counts()
        self.wards = set(wc[wc >= MIN_WARD_LISTINGS].index)
        self.formers = set(fc[fc >= MIN_FORMER_LISTINGS].index)

    def location(self, seed, kind: str):
        if kind == "ward":
            if seed["ward"] not in self.wards:
                return None
            loc = {"kind": "ward", "value": seed["ward"]}
            if self.rng.random() < DUAL_MENTION_P:
                loc["with_former"] = seed["former_area"]
            return loc
        if kind == "former_area":
            fa = seed["former_area"]
            if fa in C.THU_DUC_GROUP:
                fa = "Thành Phố Thủ Đức"
            if fa not in self.formers:
                return None
            return {"kind": "former_area", "value": fa}
        return False   # no location

    def price(self, seed, p_use: float):
        if self.rng.random() >= p_use:
            return None
        if not (seed["price"] >= MIN_SEED_PRICE):
            return "invalid"
        return make_price(float(seed["price"]), self.rng)

    def build(self, family: str, pool: pd.DataFrame, loc_kind: str):
        rng, gold = self.rng, {}
        if family in ("F1_structured", "F2_structured_plus"):
            ptype = rng.choices(["Căn hộ", "Nhà đất"], weights=[0.35, 0.65])[0]
            cand = pool[pool["property_type"] == ptype]
            seed = cand.iloc[rng.randrange(len(cand))]
            gold["property_type"] = ptype
            price = self.price(seed, 1.0)
            if price == "invalid":
                return None
            gold["price"] = price
            if not np.isnan(seed["bedrooms"]) and rng.random() < (0.75 if ptype == "Căn hộ" else 0.35):
                b = int(min(seed["bedrooms"], 4))
                gold["beds"] = {"kind": "exact" if (b == seed["bedrooms"] and rng.random() < 0.6) else "min", "value": b}
            if family == "F2_structured_plus":
                extras = ["has_title"] + (["full_furniture"] if ptype == "Căn hộ" else []) + \
                         (["area"] if ptype == "Nhà đất" and seed["area"] >= 30 else [])
                for extra in rng.sample(extras, k=min(len(extras), rng.choice([1, 2]))):
                    if extra == "area":
                        gold["area_min"] = int(max(10, math.floor(seed["area"] * rng.uniform(0.8, 1.0) / 5) * 5))
                    elif seed[extra] != 1:
                        return None
                    else:
                        gold[extra] = True
        elif family == "F3_proximity":
            cat = rng.choices(list(IMPLICIT_AMENITY_KM), weights=[20, 15, 10, 10, 5, 10, 10, 15, 5])[0]
            ptype = rng.choices(["Căn hộ", "Nhà đất"], weights=[0.35, 0.65])[0]
            cand = pool[pool["property_type"] == ptype]
            seed = cand.iloc[rng.randrange(len(cand))]
            dist = seed[f"drive_{cat}_km"]
            if np.isnan(dist):
                return None
            explicit = rng.random() < 0.55
            if explicit:
                ok = [s for s in EXPLICIT_AMENITY_KM[cat] if s >= dist]
                if not ok:
                    return None
                km = ok[min(len(ok) - 1, 1 if rng.random() < 0.3 else 0)]
            else:
                km = IMPLICIT_AMENITY_KM[cat]
                if dist > km:
                    return None
            gold.update(property_type=ptype, amenity={"category": cat, "max_km": km, "explicit": explicit})
            price = self.price(seed, 0.6)
            if price == "invalid":
                return None
            gold["price"] = price
        elif family == "F4_aspect":
            aspect = rng.choices(list(C.ASPECTS), weights=[20, 15, 15, 15, 10, 10, 5, 10])[0]
            cand = pool[pool[aspect].astype(bool)]
            if cand.empty:
                return None
            seed = cand.iloc[rng.randrange(len(cand))]
            gold.update(property_type=seed["property_type"], aspects=[aspect])
            price = self.price(seed, 0.6)
            if price == "invalid":
                return None
            gold["price"] = price
            if seed["property_type"] == "Căn hộ" and not np.isnan(seed["bedrooms"]) and rng.random() < 0.3:
                gold["beds"] = beds_gold(seed["bedrooms"])
        elif family == "F5_landmark":
            name = rng.choice(list(C.LANDMARKS))
            explicit = rng.random() < 0.4
            km = rng.choice([1.0, 2.0, 3.0]) if explicit else LANDMARK_KM[name]
            cand = pool[pool[f"dist_{name}_km"] <= km]
            if cand.empty:
                return None
            seed = cand.iloc[rng.randrange(len(cand))]
            gold.update(property_type=seed["property_type"], landmark={"name": name, "max_km": km, "explicit": explicit})
            price = self.price(seed, 0.7)
            if price == "invalid":
                return None
            gold["price"] = price
            if seed["property_type"] == "Căn hộ" and not np.isnan(seed["bedrooms"]) and rng.random() < 0.4:
                gold["beds"] = beds_gold(seed["bedrooms"])
        elif family == "F6_subtype":
            subtype = rng.choices(["Nhà mặt phố", "Biệt thự/Liền kề", "Shophouse"], weights=[0.6, 0.3, 0.1])[0]
            cand = pool[pool["subtype"] == subtype]
            if cand.empty:
                return None
            seed = cand.iloc[rng.randrange(len(cand))]
            gold.update(property_type=seed["property_type"], subtype=subtype)
            price = self.price(seed, 0.7)
            if price == "invalid":
                return None
            gold["price"] = price
            if subtype != "Shophouse" and seed["area"] >= 30 and rng.random() < 0.3:
                gold["area_min"] = int(max(10, math.floor(seed["area"] * rng.uniform(0.8, 1.0) / 5) * 5))
        else:
            raise ValueError(family)
        loc = self.location(seed, loc_kind)
        if loc is None:
            return None
        if loc:
            gold["location"] = loc
        gold = {k: v for k, v in gold.items() if v is not None}
        return gold, int(seed["doc_id"])


# =========================================================================== generation
def quotas(n: int, mix: tuple) -> dict:
    """Largest-remainder allocation of n queries to (ward, former_area, none)."""
    kinds = ("ward", "former_area", "none")
    raw = [n * p for p in mix]
    out = [int(math.floor(x)) for x in raw]
    for i in sorted(range(3), key=lambda i: (-(raw[i] - out[i]), i))[: n - sum(out)]:
        out[i] += 1
    return {k: v for k, v in zip(kinds, out) if v > 0}


def split_frames(rng) -> dict:
    out = {}
    for style in ("S1", "S3", "S4"):
        ids = list(range(len(FRAMES[style])))
        rng.shuffle(ids)
        k_tr, k_va = FRAMES_PER_SPLIT["train"], FRAMES_PER_SPLIT["val"]
        for i, fid in enumerate(ids):
            out[(style, fid)] = "train" if i < k_tr else ("val" if i < k_tr + k_va else "test")
    out.update({("S2", fid): out[("S1", fid)] for fid in range(len(FRAMES["S1"]))})
    return out


def generate(c: pd.DataFrame, out_dir: Path) -> list[dict]:
    rng = random.Random(SEED)
    loc = C.Locator(c)
    names = Names(c)
    frame_split = split_frames(rng)
    doc_ids = sorted(c["doc_id"].tolist())
    rng.shuffle(doc_ids)
    n = len(doc_ids)
    seed_split = {d: ("train" if i < 0.6 * n else ("val" if i < 0.8 * n else "test")) for i, d in enumerate(doc_ids)}
    c = c.assign(seed_split=c["doc_id"].map(seed_split))
    builder = Builder(c, rng)
    pos = {d: i for i, d in enumerate(c["doc_id"].values)}

    queries, seen = [], set()
    for family, total in FAMILY_COUNTS.items():
        for split, frac in SPLITS.items():
            pool = c[c["seed_split"] == split]
            for loc_kind, target in quotas(int(round(total * frac)), LOC_MIX[family]).items():
                made = fill_stratum(c, pool, builder, loc, names, frame_split, rng, family, split, loc_kind, target,
                                    pos, seen, queries)
                if made < target:
                    raise SystemExit(f"{family}/{split}/{loc_kind}: only {made}/{target} queries")
    order = {"train": 0, "val": 1, "test": 2}
    queries.sort(key=lambda q: (order[q["split"]], q["family"]))   # stable: generation order inside a group
    for i, q in enumerate(queries, 1):
        q["qid"] = f"v2q{i:04d}"
    write_outputs(c.drop(columns=["seed_split"]), queries, frame_split, out_dir, names)
    return queries


def fill_stratum(c, pool, builder, loc, names, frame_split, rng, family, split, loc_kind, target, pos, seen, queries):
    made, attempts = 0, 0
    while made < target and attempts < target * 3000:
        attempts += 1
        style = rng.choices(list(STYLE_WEIGHTS), weights=list(STYLE_WEIGHTS.values()))[0]
        fid = rng.choice(sorted(f for (st, f), sp in frame_split.items() if st == style and sp == split))
        built = builder.build(family, pool, loc_kind)
        if built is None:
            continue
        gold, seed_id = built
        g = grades(c, gold, loc)
        if g[pos[seed_id]] != 3:
            raise AssertionError(f"seed {seed_id} is not grade 3 for {gold}")
        n3, n2, n1 = int((g == 3).sum()), int((g == 2).sum()), int((g == 1).sum())
        if not (1 <= n3 <= MAX_EXACT and n3 + n2 + n1 <= MAX_RELEVANT):
            continue
        text = render(FRAMES["S1" if style == "S2" else style][fid], verbalise(gold, style, names, rng))
        if style == "S2":
            text = C.strip_accents(text).lower()
        if text in seen:
            continue
        seen.add(text)
        queries.append(dict(qid="", split=split, family=family, style=style,
                            frame_id=f"{'S1' if style == 'S2' else style}-{fid}", loc_kind=loc_kind, text=text,
                            gold=gold, seed_doc_id=seed_id, n3=n3, n2=n2, n1=n1, grades=g))
        made += 1
    return made


def write_outputs(c, queries, frame_split, out_dir: Path, names: Names):
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "queries.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for q in queries:
            fh.write(json.dumps({k: v for k, v in q.items() if k != "grades"}, ensure_ascii=False, sort_keys=False) + "\n")
    doc_ids = c["doc_id"].values
    with open(out_dir / "qrels.tsv", "w", encoding="utf-8", newline="\n") as fh:
        for q in queries:
            for d, g in zip(doc_ids, q["grades"]):
                if g > 0:
                    fh.write(f"{q['qid']}\t0\t{d}\t{int(g)}\n")
    c.to_csv(out_dir / "corpus_attributes.csv", index=False, lineterminator="\n")
    stats = {"n_queries": len(queries), "n_docs": int(len(c)), "seed": SEED,
             "by_split": dict(Counter(q["split"] for q in queries)),
             "by_split_family": {s: dict(Counter(q["family"] for q in queries if q["split"] == s)) for s in SPLITS},
             "by_split_style": {s: dict(Counter(q["style"] for q in queries if q["split"] == s)) for s in SPLITS},
             "by_split_location": {s: dict(Counter(q["loc_kind"] for q in queries if q["split"] == s)) for s in SPLITS},
             "dual_mention": sum(1 for q in queries if q["gold"].get("location", {}).get("with_former")),
             "label_distribution": {}, "relevant_per_query": {},
             "frames": {f"{k[0]}-{k[1]}": v for k, v in sorted(frame_split.items())},
             "name_collisions": names.collisions}
    for s in SPLITS:
        gs = np.concatenate([q["grades"] for q in queries if q["split"] == s])
        stats["label_distribution"][s] = {str(k): int((gs == k).sum()) for k in (0, 1, 2, 3)}
        for key in ("n3", "n2", "n1"):
            v = np.array([q[key] for q in queries if q["split"] == s])
            stats["relevant_per_query"].setdefault(s, {})[key] = {
                "mean": round(float(v.mean()), 2), "median": float(np.median(v)), "min": int(v.min()), "max": int(v.max())}
    with open(out_dir / "stats.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(stats, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data")
    args = ap.parse_args()

    def _main():
        runlog.stage("build the label-side attribute table from Data/v3/master_v3.csv (corpus.py)")
        corpus = C.build_corpus()
        runlog.stage(f"generate queries and grade all {len(corpus)} listings for each (seed {SEED}) -> {args.out}")
        generate(corpus, Path(args.out))
        runlog.stage("done")
        print(json.dumps(json.load(open(Path(args.out) / "stats.json", encoding="utf-8")), ensure_ascii=False, indent=1)[:2500])

    runlog.run("build_benchmark", _main)
