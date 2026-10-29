"""Label-side attribute table of HCMRE-Q v2 (PROTOCOL.md §3) — one row per listing of Data/v3 (v3.1).

Every relevance label is computed from this table only. Nothing here imports backend/ (check C3).
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(os.environ.get("IT2047_ROOT", Path(__file__).resolve().parents[2]))
V3 = REPO / "Data" / "v3"
sys.path.insert(0, str(V3 / "pipeline"))
from price_text import stated_price  # noqa: E402  (Data/v3/pipeline, not backend)

MASTER_SHA256_V31 = "5b65c94dabd25a89f4b878c7b8e84948bf86b51da4394513f1bda19e5e82942d"

AMENITY_CATEGORIES = ["school", "bus_stop", "supermarket", "market", "park",
                      "college_university", "hospital", "mall", "metro"]
# Search radius (km, straight line) of the Top-5 amenity edges in Data/v3 (build_v3.py RADIUS)
AMENITY_RADIUS_KM = {"hospital": 7, "school": 3, "college_university": 7, "metro": 5, "mall": 7, "market": 3,
                     "supermarket": 3, "park": 5, "bus_stop": 2}

LANDMARKS = {  # approximate WGS84, as in v1
    "ben_thanh": (10.7725, 106.6980),       # Chợ Bến Thành
    "tan_son_nhat": (10.8185, 106.6588),    # Sân bay Tân Sơn Nhất
    "landmark81": (10.7949, 106.7218),      # Landmark 81
    "phu_my_hung": (10.7290, 106.7187),     # Phú Mỹ Hưng (Crescent Mall)
    "dhqg": (10.8700, 106.8030),            # Làng Đại học / ĐHQG TP.HCM
}

RELIABLE_COORDS = {"original_valid", "corrected_by_exact_address", "corrected_by_folder",
                   "imputed_exact_address", "imputed_same_listing_id"}
NEAR_KM = 1.0
CORE_FLOOR_KM, CORE_MAD_K = 2.0, 5.0
THU_DUC_GROUP = ("Thành Phố Thủ Đức", "Quận 2", "Quận 9")


# --------------------------------------------------------------------------- text helpers
def strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.replace("đ", "d").replace("Đ", "D")


def norm(text) -> str:
    text = strip_accents(str(text if text is not None and text == text else "")).lower()
    return re.sub(r"\s+", " ", text).strip()


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(np.asarray(lon2) - np.asarray(lon1)) / 2) ** 2
    return 2 * 6371.0088 * np.arcsin(np.sqrt(a))


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --------------------------------------------------------------------------- labeling functions
# v1 functions + one san_vuon negation (PROTOCOL §9 item 1) + the revision after the AI pre-audit of H1 (§9 item 5):
# dong_tien now requires an income-producing property, an apartment is a corner unit only when the unit itself is, and
# "convenient to install a lift", "a view from the embankment 150 m away", "suitable to build a garden house" are negated.
_DT_ASSET = r"(?:chdv|can ho dich vu|nha tro|phong tro|day tro|dong tien)"
ASPECTS = {
    "hem_xe_hoi": dict(
        pos=r"hem xe hoi|hem o ?to|\bhxh\b|hem xe tai|hem thong xe hoi|hem rong xe hoi|"
            r"(?:xe hoi|o ?to|oto) (?:do|dau|vao|ngu|tan|quay dau|tranh|ra vao)[a-z ]{0,12}(?:cua|nha|thoai mai)|"
            r"(?:xe hoi|o ?to|oto) (?:vao|toi|den) tan (?:noi|nha|cua)|"
            r"(?:xe hoi|o ?to|oto) (?:ngu|do) trong nha|gara (?:xe hoi|o ?to|oto)|"
            r"(?:xe hoi|o ?to|oto) (?:ne|tranh) nhau",
        neg=r"\b(?:cach|gan|sat|ra) hem xe hoi|\b(?:cach|gan|sat) duong xe hoi|hem xe may|hem ba gac",
        types={"Nhà đất"}),
    "dong_tien": dict(   # revised (§9 item 5): a CHDV / boarding house, a lease, a stated rent or income — not "suitable for"
        pos=r"\bchdv\b|can ho dich vu|\bday tro\b|\bnha tro\b|\bphong tro\b|"
            r"(?:co|san|dang co|kem|san co) (?:san )?dong tien|dong tien (?:co )?san\b|"
            r"dong tien:? (?:[a-z]+ ){0,3}(?:~ ?)?\d+(?:[.,]\d+)? ?(?:tr|trieu|ty|usd)\b|"
            r"thu nhap (?:on dinh|deu|hang thang|(?:hien tai|thuc te):? ?\d|\d)|\btn:? ?\d|hop dong thue|\bhdt\b|"
            r"\bhd thue\b|doanh thu (?:[a-z]+ ){0,2}\d|"
            r"(?<!de )(?<!thiet ke )dang cho (?:[a-z0-9]+ ){0,3}thue\b|(?<!de )dang khai thac|"
            r"cho thue (?:\d+[.,]?\d*) ?(?:tr|trieu)",
        neg=r"\bkhong (?:cho thue|kinh doanh)|"
            r"\b(?:phu hop|thich hop|ly tuong|thuan tien|du dinh)\b[^.!?*+;]{0,100}?" + _DT_ASSET + r"|"
            r"\b(?:phu hop|thich hop|ly tuong|(?<!dong )tien|thuan tien|co the|nen|du dinh|hoac)\s(?:(?:de|cho|thanh)\s)?"
            r"(?:xay|lam|mo|kinh doanh|dau tu|khai thac|cho thue|chuyen doi|cai tao|tao|giu)\b[a-z ,/&+-]{0,80}?"
            + _DT_ASSET + r"|"
            r"(?<!da )\bxay (?:moi |dung |lai )?(?:[a-z]+ ){0,2}(?:chdv|can ho dich vu|nha tro|phong tro|day tro)|"
            r"\b(?:co the|du kien|uoc tinh|kha nang|tiem nang) (?:[a-z]+ ){0,2}(?:cho thue|thu ve|thu nhap|doanh thu|dong tien)|"
            r"tiem nang[a-z ]{0,25}(?:dong tien|doanh thu|thu nhap|chdv|can ho dich vu)|"
            r"(?<!dang )\bkhai thac (?:[a-z]+ ){0,1}(?:chdv|can ho dich vu)|"
            r"\b(?:ctxd|gpxd|xin phep xay dung)\b[^.]{0,60}?(?:chdv|can ho dich vu|phong tro)|"
            r"\bphuong an (?:[a-z]+ ){0,3}(?:chdv|can ho dich vu)|"
            r"\b(?:thiet ke|mo hinh) (?:[a-z]+ ){0,2}(?:chdv|can ho dich vu)[a-z ,]{0,20}(?:co the|du kien|uoc tinh)",
        types={"Nhà đất"}),
    "can_goc": dict(
        pos=r"can goc|nha goc|lo goc|\bgoc 2 m|(?:^|[^0-9a-z.,])(?:2|hai) mat tien|(?:^|[^0-9a-z.,])2 ?mt\b|goc hai mat",
        # revised (§9 item 5): for an apartment "2 mặt tiền" is the project's plot, so only the unit itself counts
        pos_by_type={"Căn hộ": r"can goc|lo goc|\bgoc (?:2|hai) (?:view|mat thoang|ban cong|mat)|"
                               r"\bcan (?:[a-z0-9]+ ){0,3}(?:2|hai) ?(?:mat tien|mt)\b"},
        neg=r"khong phai can goc|quy hoach thanh goc|\bqh thanh goc|lo goc \d{3,}",
        types={"Nhà đất", "Căn hộ"}),
    "nha_moi": dict(
        pos=r"moi xay|moi 100|moi tinh|moi hoan thien|moi hoan cong|nha moi (?:dep )?(?:vao|o) (?:ngay|luon)|"
            r"moi ban giao|nha (?:dep )?xay moi\b(?! (?:theo|chia|cao tang|lai))",
        neg=r"\b(?:can|nen|thich hop|phu hop|hop|tien|mua|de|co the|hoac) xay moi|xay moi (?:hoan toan )?theo y",
        types={"Nhà đất", "Căn hộ"}),
    "view_song": dict(
        pos=r"view song|huong song|nhin (?:ra|thang ra|xuong) song|truc dien song|view ra song|"
            r"view (?:truc dien )?song sai gon|ban cong (?:nhin|huong) (?:ra )?song",
        neg=r"\bkhong (?:co )?view song|"
            r"\b(?:ra|toi|den|cach|gan|sat) (?:bo ke|bo song|ke|cong vien|ben)[a-z ]{0,15}view song",   # §9 item 5
        types={"Nhà đất", "Căn hộ"}),
    "thang_may_nha": dict(
        pos=r"thang may",
        neg=r"\b(?:khong|chua) (?:co )?thang may|\bcho (?:lap|gan) thang may|\b(?:khung|ho|o) (?:cho )?thang may|"
            r"\bcho thang may|\b(?:co the|de) (?:lap|gan) thang may|"
            r"\b(?:tien|thuan tien|san sang|chuan bi|du kien|co the|de|du dinh|chua) (?:[a-z]+ ){0,2}"   # §9 item 5
            r"(?:lap|gan|lap dat|lap them|lam) (?:them )?thang may|\bo thong gio[a-z0-9 ,.x]{0,30}thang may",
        types={"Nhà đất"}),
    "san_vuon": dict(
        pos=r"san vuon\b|nha vuon\b|co vuon\b|\bvuon (?:cay|rong|truoc|sau)\b|khoang vuon\b|biet thu vuon\b(?! la[in])",
        neg=r"\bkhong (?:co )?san vuon|thiet ke (?:gara/)?san vuon|xay (?:biet thu )?san vuon|hang xom.{0,40}san vuon|"
            r"(?:view|nhin)[a-z ]{0,25}(?:san|khoang) vuon|"
            r"(?:co the|phu hop|thich hop|ly tuong|(?<!dong )tien|thuan tien|de|nen) (?:de )?(?:lam|xay|mo|cai tao)"
            r"[a-z ,]{0,40}(?:san|nha|biet thu) vuon",   # v2 (§9 item 1), widened in §9 item 5
        types={"Nhà đất"}),
    "ho_boi": dict(
        pos=r"ho boi|be boi",
        neg=r"\b(?:gan|cach) ho boi|\bkhong (?:co )?ho boi",
        types={"Nhà đất", "Căn hộ"}),
}
_ASPECT_RE = {k: (re.compile(v["pos"]), re.compile(v["neg"]),
                  {t: re.compile(p) for t, p in v.get("pos_by_type", {}).items()}) for k, v in ASPECTS.items()}


def aspect_hits(text_norm: str, prop_type: str) -> dict:
    out = {}
    for name, (pos, neg, pos_by_type) in _ASPECT_RE.items():
        if prop_type not in ASPECTS[name]["types"]:
            out[name] = False
            continue
        positives = [m.start() for m in pos_by_type.get(prop_type, pos).finditer(text_norm)]
        negatives = [(m.start(), m.end()) for m in neg.finditer(text_norm)]
        out[name] = any(not any(s - 25 <= p <= e for s, e in negatives) for p in positives)
    return out


# --------------------------------------------------------------------------- attribute normalisers
LEGAL_NO = re.compile(r"cho so|dang lam so|chua co so|chua ra so|nop ho so|\bhdmb\b|hop dong mua ban|vi bang|giay tay|"
                      r"hop dong gop von|hop dong dat coc")
LEGAL_YES = re.compile(r"so hong|so do|co so|\bshr\b|so rieng|so chung|so san")
FURN_NO = re.compile(r"co ban|\bntcb\b|\bcb\b|\btho\b|khong (?:co )?noi that|nha trong|ban giao tho")
FURN_YES = re.compile(r"day du|full|cao cap|toan bo|\bxin\b|du noi that")
FURN_TEXT_YES = re.compile(r"full noi that|noi that day du|day du noi that|noi that cao cap|full nt\b|"
                           r"(?:tang|de lai) (?:lai )?(?:toan bo|full|het) noi that")
BEDS_TEXT = re.compile(r"(?<![\d.,])(\d{1,2})\s*(?:pn|phong ngu)\b")


def legal_value(raw, text_norm):
    t = norm(raw)
    if t and t not in ("khong ro", "nan"):
        if LEGAL_NO.search(t):
            return 0, "field"
        if LEGAL_YES.search(t):
            return 1, "field"
    if LEGAL_YES.search(text_norm) and not LEGAL_NO.search(text_norm):
        return 1, "text"
    return np.nan, ""


def furniture_value(raw, text_norm):
    t = norm(raw)
    if t and t != "nan":
        if FURN_NO.search(t):
            return 0, "field"
        if FURN_YES.search(t):
            return 1, "field"
    if FURN_TEXT_YES.search(text_norm) and not FURN_NO.search(text_norm):
        return 1, "text"
    return np.nan, ""


def bedrooms_value(raw, text_norm):
    try:
        v = float(raw)
        if v == v and v > 0:
            return v, "field"
    except (TypeError, ValueError):
        pass
    vals = {int(x) for x in BEDS_TEXT.findall(text_norm) if 1 <= int(x) <= 10}
    if len(vals) == 1:
        return float(vals.pop()), "text"
    return np.nan, ""


def subtype_from_folder(folder) -> str:
    part = str(folder).split("/")
    raw = re.sub(r"\s+tại.*", "", part[3] if len(part) > 3 else "").strip()
    return {"Nhà riêng": "Nhà riêng", "Căn hộ chung cư": "Căn hộ chung cư", "Nhà mặt phố": "Nhà mặt phố",
            "Nhà biệt thự, liền kề": "Biệt thự/Liền kề", "Shophouse, nhà phố thương mại": "Shophouse"}.get(raw, "Khác")


# --------------------------------------------------------------------------- corpus
def min_driving_km() -> pd.DataFrame:
    e = pd.read_csv(V3 / "listing_amenity_top5_edges.csv", usecols=["listing_node_id", "category", "driving_distance_km"],
                    dtype={"listing_node_id": str})
    d = e.groupby(["listing_node_id", "category"])["driving_distance_km"].min().unstack()
    d.index = d.index.astype(np.int64)
    return d.reindex(columns=AMENITY_CATEGORIES)


def build_corpus(check_hash: bool = True) -> pd.DataFrame:
    master = V3 / "master_v3.csv"
    if check_hash and sha256(master) != MASTER_SHA256_V31:
        raise SystemExit("Data/v3/master_v3.csv is not v3.1 — run Data/v3/pipeline/fix_v3_quality.py --apply first")
    m = pd.read_csv(master, low_memory=False, dtype={"area": str})
    drive = min_driving_km()
    rows = []
    for r in m.to_dict("records"):
        lid = int(r["listing_id"])
        title, desc = str(r["title"] or ""), str(r["description"] or "")
        text_norm = norm(f"{title} . {desc}")
        price = float(r["price_range"]) if pd.notna(r["price_range"]) else np.nan
        price_src = "field" if price == price else ""
        if price != price:
            tp = stated_price(title, desc)[0]
            if tp is not None:
                price, price_src = tp, "text"
        beds, beds_src = bedrooms_value(r["bedrooms"], text_norm)
        legal, legal_src = legal_value(r["legal_status"], text_norm)
        furn, furn_src = furniture_value(r["furnishing"], text_norm)
        reliable = r["coordinate_status"] in RELIABLE_COORDS and pd.notna(r["latitude"]) and pd.notna(r["longitude"])
        row = dict(doc_id=lid, listing_id=lid, source=r["source"], property_type=r["property_type"],
                   subtype=subtype_from_folder(r["Folder"]), ward=r["district"], former_area=r["former_admin_area"],
                   price=price, price_src=price_src, area=float(r["area"]), bedrooms=beds, bedrooms_src=beds_src,
                   has_title=legal, has_title_src=legal_src, full_furniture=furn, full_furniture_src=furn_src,
                   lat=float(r["latitude"]), lon=float(r["longitude"]), coords_reliable=bool(reliable),
                   posted_date=pd.to_datetime(r["posted_date"], format="%d/%m/%Y").date().isoformat())
        for cat in AMENITY_CATEGORIES:
            v = drive.at[lid, cat] if lid in drive.index else np.nan
            row[f"drive_{cat}_km"] = float(v) if pd.notna(v) else np.nan
        row.update(aspect_hits(text_norm, r["property_type"]))
        rows.append(row)
    c = pd.DataFrame(rows)
    for name, (lat, lon) in LANDMARKS.items():
        d = haversine_km(c["lat"].values, c["lon"].values, lat, lon).round(3)
        c[f"dist_{name}_km"] = np.where(c["coords_reliable"], d, np.nan)
    c["ward_coord_outlier"] = False
    for ward, idx in c.groupby("ward").groups.items():
        core = area_core(c, "ward", (ward,))
        rel = c.loc[idx, "coords_reliable"]
        c.loc[idx[rel.values], "ward_coord_outlier"] = ~c.loc[idx[rel.values]].index.isin(core)
    return c.sort_values("doc_id").reset_index(drop=True)


# --------------------------------------------------------------------------- location: cores and "near"
def area_core(c: pd.DataFrame, kind: str, values: tuple) -> pd.Index:
    """Index labels of the core listings of an area (PROTOCOL §3)."""
    out = []
    for v in values:
        sub = c[(c[kind] == v) & c["coords_reliable"]]
        if len(sub) < 5:
            out.extend(sub.index)
            continue
        lat0, lon0 = sub["lat"].median(), sub["lon"].median()
        d = haversine_km(sub["lat"].values, sub["lon"].values, lat0, lon0)
        med = np.median(d)
        mad = np.median(np.abs(d - med))
        out.extend(sub.index[d <= max(CORE_FLOOR_KM, med + CORE_MAD_K * 1.4826 * mad)])
    return pd.Index(out)


class Locator:
    """in-area / near-area masks over the corpus, cached per (kind, values, near_km)."""

    def __init__(self, c: pd.DataFrame):
        self.c = c
        self.lat, self.lon = c["lat"].values, c["lon"].values
        self.reliable = c["coords_reliable"].values

    @lru_cache(maxsize=None)
    def masks(self, kind: str, values: tuple, near_km: float = NEAR_KM):
        inside = np.isin(self.c[kind].values, list(values))
        core = area_core(self.c, kind, values)
        pos = self.c.index.get_indexer(core)
        best = np.full(len(self.c), np.inf)
        for start in range(0, len(pos), 256):
            p = pos[start:start + 256]
            d = haversine_km(self.lat[:, None], self.lon[:, None], self.lat[p][None, :], self.lon[p][None, :])
            best = np.minimum(best, d.min(axis=1))
        near = ~inside & self.reliable & (best <= near_km)
        return inside, near


def location_values(gold_loc: dict) -> tuple[str, tuple]:
    """('ward'|'former_area', values) of a gold location."""
    if gold_loc["kind"] == "ward":
        return "ward", (gold_loc["value"],)
    if gold_loc["value"] == "Thành Phố Thủ Đức":
        return "former_area", THU_DUC_GROUP
    return "former_area", (gold_loc["value"],)


if __name__ == "__main__":
    corpus = build_corpus()
    print(corpus.shape)
    print(corpus[list(ASPECTS)].sum().to_string())
    for col in ("price_src", "bedrooms_src", "has_title_src", "full_furniture_src", "subtype"):
        print(col, corpus[col].value_counts(dropna=False).to_dict())
    print("missing:", corpus[["price", "bedrooms", "has_title", "full_furniture"]].isna().sum().to_dict())
    print("ward_coord_outlier:", int(corpus["ward_coord_outlier"].sum()))
