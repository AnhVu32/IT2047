"""Draw the human-validation samples H1–H5 of PROTOCOL.md §7 (fixed seed).

    python human/make_samples.py          # after build_benchmark.py and eval_benchmark.py (H3 uses the BM25 run)

Writes human/tasks/<task>.csv (what the annotator sees, open them in human/annotate.html) and
human/keys/<task>_key.csv (automatic labels — annotators must NOT open this folder).
"""
from __future__ import annotations

import csv
import gzip
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import check_labels as CL  # noqa: E402  (independent re-implementation of PROTOCOL §5; only annotates the H4 key)
import corpus as C  # noqa: E402
import runlog  # noqa: E402

SEED = 20261029
DATA, RESULTS = ROOT / "data", ROOT / "results"
TASKS, KEYS = HERE / "tasks", HERE / "keys"
# Items the AI assistant read while pre-auditing an earlier draft of the kit and revising the generator / labelling
# functions (PROTOCOL.md §9, items 5 and 7). They are kept out of the human samples, which must be fresh.
PREAUDIT = HERE / "preaudit_items.json"


def task_rng(task: str) -> random.Random:
    """One random stream per task, so redrawing one sample never changes another."""
    return random.Random(f"{SEED}-{task}")

ASPECT_VI = {"hem_xe_hoi": "hẻm xe hơi / ô tô vào tới cửa nhà",
             "dong_tien": "đang có dòng tiền cho thuê (đang cho thuê, có hợp đồng thuê) hoặc là CHDV / nhà trọ",
             "can_goc": "căn góc / lô góc, hai mặt tiền hoặc hai mặt thoáng", "nha_moi": "nhà mới xây / mới hoàn thiện / mới bàn giao",
             "view_song": "view sông, nhìn ra sông", "thang_may_nha": "nhà có thang máy",
             "san_vuon": "có sân vườn", "ho_boi": "có hồ bơi (của căn nhà hoặc của dự án)"}
LOOSE = {"hem_xe_hoi": r"\bhem\b|o ?to|xe hoi", "dong_tien": r"thue|thu nhap|kinh doanh", "can_goc": r"\bgoc\b|mat tien",
         "nha_moi": r"\bmoi\b", "view_song": r"\bsong\b|\bkenh\b", "thang_may_nha": r"\bthang\b",
         "san_vuon": r"\bvuon\b|\bsan\b", "ho_boi": r"\bboi\b|\bho\b"}
CAT_VI = {"school": "trường học", "bus_stop": "trạm xe buýt", "supermarket": "siêu thị", "market": "chợ", "park": "công viên",
          "college_university": "trường đại học", "hospital": "bệnh viện", "mall": "trung tâm thương mại", "metro": "ga metro"}
LANDMARK_VI = {"ben_thanh": "chợ Bến Thành", "tan_son_nhat": "sân bay Tân Sơn Nhất", "landmark81": "Landmark 81",
               "phu_my_hung": "Phú Mỹ Hưng", "dhqg": "Làng Đại học Thủ Đức"}
TYPE_VI = {"Căn hộ": "căn hộ chung cư", "Nhà đất": "nhà (nhà riêng/nhà phố/nhà đất)", "Nhà mặt phố": "nhà mặt phố/mặt tiền",
           "Biệt thự/Liền kề": "biệt thự/liền kề", "Shophouse": "shophouse/nhà phố thương mại"}


def off_constraint(doc: dict, gold: dict) -> str:
    """The one soft constraint a grade-2 listing misses (inside its tolerance band), with its direction.
    Deterministic: draws no random numbers, so adding it to the H4 key leaves every sample unchanged."""
    names = [k for k in ("price", "area_min", "beds", "amenity", "landmark") if k in gold]   # order of CL.soft_status
    status = CL.soft_status(doc, gold)
    off = [n for n, s in zip(names, status) if s == "band"]
    assert len(off) == 1 and "fail" not in status, (doc["doc_id"], status)
    name = off[0]
    if name == "price":
        g, p = gold["price"], doc["price"]
        over = p > g["max"] if "max" in g else p > g["target"]
        return "price_over" if over else "price_under"
    if name == "beds":
        return "beds_extra" if doc["bedrooms"] > gold["beds"]["value"] else "beds_short"
    return {"area_min": "area_short", "amenity": "distance", "landmark": "distance"}[name]


def write(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def fmt(v, unit="", nd=2):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "không có"
    v = float(v)
    return (f"{v:.{nd}f}".rstrip("0").rstrip(".") + unit) if not v.is_integer() else f"{int(v)}{unit}"


def gold_text(g: dict) -> str:
    parts = [f"Loại: {TYPE_VI[g.get('subtype') or g['property_type']]}"]
    loc = g.get("location")
    if loc:
        if loc["kind"] == "ward":
            extra = f" (câu có nhắc thêm {loc['with_former']} cũ — chỉ để mô tả)" if loc.get("with_former") else ""
            parts.append(f"Vị trí: {loc['value']}{extra}")
        else:
            v = loc["value"] + (" (gồm Quận 2, Quận 9 cũ)" if loc["value"] == "Thành Phố Thủ Đức" else "")
            parts.append(f"Vị trí: quận/huyện/thành phố cũ {v}")
    p = g.get("price")
    if p:
        parts.append("Giá: " + (f"từ {fmt(p['min'])} đến {fmt(p['max'])} tỷ" if "min" in p else
                                (f"tối đa {fmt(p['max'])} tỷ" if "max" in p else f"khoảng {fmt(p['target'])} tỷ")))
    if g.get("beds"):
        b = g["beds"]
        parts.append(f"Phòng ngủ: {'đúng' if b['kind'] == 'exact' else 'ít nhất'} {b['value']}")
    if g.get("area_min"):
        parts.append(f"Diện tích: ít nhất {g['area_min']} m²")
    if g.get("has_title"):
        parts.append("Pháp lý: đã có sổ")
    if g.get("full_furniture"):
        parts.append("Nội thất: đầy đủ")
    if g.get("amenity"):
        a = g["amenity"]
        parts.append(f"Gần {CAT_VI[a['category']]}" + (f", cách không quá {fmt(a['max_km'])} km" if a["explicit"] else ""))
    if g.get("landmark"):
        k = g["landmark"]
        parts.append(f"Gần {LANDMARK_VI[k['name']]}" + (f", cách không quá {fmt(k['max_km'])} km" if k["explicit"] else ""))
    for a in g.get("aspects", []):
        parts.append(f"Đặc điểm: {ASPECT_VI[a]}")
    return " | ".join(parts)


def listing_card(r, text, g: dict | None = None, loc=None, attrs=None) -> dict:
    """What the annotator sees about one listing (the listing page + measured facts a map would show)."""
    card = {"show_title": text["title"], "show_description": text["description"][:1500],
            "show_facts": " | ".join([
                f"Loại: {r['property_type']} ({r['subtype']})", f"Giá: {fmt(r['price'], ' tỷ', 3)}",
                f"Diện tích: {fmt(r['area'], ' m²', 1)}", f"Phòng ngủ: {fmt(r['bedrooms'])}",
                f"Pháp lý: {text['legal_status'] or 'không ghi'}", f"Nội thất: {text['furnishing'] or 'không ghi'}",
                f"Địa chỉ: {r['ward']} (quận/huyện cũ: {r['former_area']})"])}
    if g:
        facts = []
        if g.get("amenity"):
            cat = g["amenity"]["category"]
            facts.append(f"Đường lái xe tới {CAT_VI[cat]} gần nhất: {fmt(r[f'drive_{cat}_km'], ' km')}")
        if g.get("landmark"):
            name = g["landmark"]["name"]
            facts.append(f"Đường chim bay tới {LANDMARK_VI[name]}: {fmt(r[f'dist_{name}_km'], ' km')}")
        if g.get("location") and loc is not None:
            kind, values = C.location_values(g["location"])
            inside, _ = loc.masks(kind, values)
            i = attrs.index.get_loc(r.name)
            if not inside[i]:
                core = C.area_core(attrs, kind, values)
                d = C.haversine_km(r["lat"], r["lon"], attrs.loc[core, "lat"].values, attrs.loc[core, "lon"].values)
                where = g["location"]["value"]
                facts.append(f"Không thuộc {where}; cách khu vực có tin đăng của {where} khoảng "
                             f"{fmt(float(np.min(d)) if len(d) and r['coords_reliable'] else None, ' km')}")
        card["show_measured"] = " | ".join(facts) if facts else ""
    return card


def main():
    seen = json.load(open(PREAUDIT, encoding="utf-8")) if PREAUDIT.exists() else {}
    seen_docs = set(seen.get("H1", [])) | set(seen.get("H1r", [])) | set(seen.get("lf_dev", []))
    seen_qids = set(seen.get("H2", []))
    attrs = pd.read_csv(DATA / "corpus_attributes.csv", low_memory=False).set_index("doc_id", drop=False)
    master = pd.read_csv(C.V3 / "master_v3.csv", low_memory=False,
                         usecols=["listing_id", "title", "description", "legal_status", "furnishing"])
    master = master.fillna("").set_index("listing_id")
    queries = [json.loads(line) for line in open(DATA / "queries.jsonl", encoding="utf-8")]
    qrels = defaultdict(dict)
    for line in open(DATA / "qrels.tsv", encoding="utf-8"):
        qid, _, doc, g = line.split()
        qrels[qid][int(doc)] = int(g)
    loc = C.Locator(attrs.reset_index(drop=True))
    attrs_r = attrs.reset_index(drop=True)

    # ---------------- H1 aspects: precision sample (auto = 1) and keyword-negative sample (auto = 0, "H1r") mixed in
    # one file with neutral item ids, so the annotator cannot tell which listings the labelling function accepted.
    rng = task_rng("H1")
    h1, h1k = [], []
    for aspect, spec in C.ASPECTS.items():
        pos = attrs[attrs[aspect].astype(bool) & ~attrs.index.isin(list(seen_docs))]
        picks = []
        for src in (["old"], ["new", "both"]):
            sub = sorted(pos[pos["source"].isin(src)].index)
            picks += rng.sample(sub, min(6, len(sub)))
        if len(picks) < 12:
            rest = sorted(set(pos.index) - set(picks))
            picks += rng.sample(rest, 12 - len(picks))
        loose = re.compile(LOOSE[aspect])
        neg_pool = sorted(d for d in attrs.index if not attrs.at[d, aspect] and attrs.at[d, "property_type"] in spec["types"]
                          and d not in seen_docs
                          and loose.search(C.norm(f"{master.at[d, 'title']} . {master.at[d, 'description']}")))
        negs = rng.sample(neg_pool, 12)
        for auto, docs in ((1, picks), (0, negs)):
            for d in docs:
                item = f"H1-{aspect}-{d}"
                text = master.loc[d]
                h1.append({"task": "H1", "item_id": item, "show_question": f"Tin này có đặc điểm: {ASPECT_VI[aspect]}?",
                           "show_title": text["title"], "show_description": text["description"][:2500]})
                h1k.append({"item_id": item, "aspect": aspect, "listing_id": d, "source": attrs.at[d, "source"],
                            "auto": auto})
    rng.shuffle(h1)

    # ---------------- H2 queries (25 per style)
    rng = task_rng("H2")
    h2, h2k = [], []
    for style in ("S1", "S2", "S3", "S4"):
        for q in rng.sample([q for q in queries if q["style"] == style and q["qid"] not in seen_qids], 25):
            h2.append({"task": "H2", "item_id": f"H2-{q['qid']}", "show_query": q["text"], "show_criteria": gold_text(q["gold"])})
            h2k.append({"item_id": f"H2-{q['qid']}", "qid": q["qid"], "style": style, "family": q["family"]})
    rng.shuffle(h2)

    # ---------------- H3 graded pairs (30 test queries x up to 5 listings)
    bm25 = {}
    runs_path = RESULTS / "runs.jsonl.gz"
    if runs_path.exists():
        with gzip.open(runs_path, "rt", encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                if r["system"] == "bm25_noaccent":
                    bm25[r["qid"]] = r["ranking"]
    rng = task_rng("H3")
    h3, h3k = [], []
    test = [q for q in queries if q["split"] == "test"]
    for q in rng.sample(test, 30):
        rel = qrels[q["qid"]]
        chosen = []
        for grade in (3, 2, 1):
            docs = sorted(d for d, g in rel.items() if g == grade)
            if docs:
                chosen.append((rng.choice(docs), f"grade{grade}"))
        g = q["gold"]
        zero = attrs[~attrs.index.isin(list(rel))]
        if g.get("location"):
            kind, values = C.location_values(g["location"])
            same = sorted(zero[zero[kind].isin(values)].index)
        else:
            same = sorted(zero[zero["property_type"] == g["property_type"]].index)
        if same:
            chosen.append((rng.choice(same), "grade0_same_area"))
        top0 = next((d for d in bm25.get(q["qid"], []) if rel.get(d, 0) == 0 and d not in [c for c, _ in chosen]), None)
        if top0 is not None:
            chosen.append((top0, "grade0_bm25_top"))
        rng.shuffle(chosen)
        for d, stratum in chosen:
            item = f"H3-{q['qid']}-{d}"
            h3.append({"task": "H3", "item_id": item, "show_query": q["text"],
                       **listing_card(attrs.loc[d], master.loc[d], g, loc, attrs_r.set_index("doc_id", drop=False))})
            h3k.append({"item_id": item, "qid": q["qid"], "listing_id": d, "auto_grade": rel.get(d, 0), "stratum": stratum})

    # ---------------- H4 ward-priority pairs
    rng = task_rng("H4")
    h4, h4k = [], []
    docs_cl = {d["doc_id"]: d for d in CL.load_docs(DATA / "corpus_attributes.csv")}
    cands = [q for q in queries if q["loc_kind"] == "ward" and q["n2"] > 0 and q["n1"] > 0]
    for q in rng.sample(cands, min(60, len(cands))):
        rel = qrels[q["qid"]]
        a = rng.choice(sorted(d for d, g in rel.items() if g == 2))
        b = rng.choice(sorted(d for d, g in rel.items() if g == 1))
        order = [("A", a, "in_ward_one_off"), ("B", b, "near_all_ok")]
        if rng.random() < 0.5:
            order = [("A", b, "near_all_ok"), ("B", a, "in_ward_one_off")]
        ix = attrs_r.set_index("doc_id", drop=False)
        row = {"task": "H4", "item_id": f"H4-{q['qid']}", "show_query": q["text"]}
        for label, d, _ in order:
            card = listing_card(attrs.loc[d], master.loc[d], q["gold"], loc, ix)
            row.update({f"show_{label}_{k[5:]}": v for k, v in card.items()})
        h4.append(row)
        h4k.append({"item_id": f"H4-{q['qid']}", "qid": q["qid"], "A": order[0][2], "B": order[1][2],
                    "A_listing": order[0][1], "B_listing": order[1][1],
                    "in_ward_off": off_constraint(docs_cl[a], q["gold"])})

    # ---------------- H5 price corrections of errata v3.1
    corr = pd.read_csv(C.V3 / "reports" / "v3_1_corrections.csv")
    corr = corr[corr["field"] == "price_range"]
    rng = task_rng("H5")
    picks = []
    for rule, n in (("price_manual", 7), ("price_R2_unknown", 13), ("price_R1_recover", 40)):
        sub = corr[corr["rule"] == rule].sort_values("listing_id")
        picks += rng.sample(sub.to_dict("records"), min(n, len(sub)))
    h5, h5k = [], []
    for r in picks:
        d = int(r["listing_id"])
        text = master.loc[d]
        new = "không xác định (để trống)" if pd.isna(r["new"]) else f"{fmt(r['new'], nd=3)} tỷ"
        item = f"H5-{d}"
        h5.append({"task": "H5", "item_id": item, "show_title": text["title"], "show_description": text["description"][:2500],
                   "show_old_price": f"{fmt(r['old'], nd=3)} tỷ", "show_new_price": new,
                   "show_question": "Giá MỚI có đúng là giá bán mà tin đăng nêu không? (giá trống = tin không nêu giá bán)"})
        h5k.append({"item_id": item, "listing_id": d, "rule": r["rule"], "old": r["old"], "new": r["new"]})
    rng.shuffle(h5)

    for name, rows, keys in (("H1_aspects", h1, h1k), ("H2_queries", h2, h2k),
                             ("H3_graded_pairs", h3, h3k), ("H4_ward_priority", h4, h4k), ("H5_price_corrections", h5, h5k)):
        write(TASKS / f"{name}.csv", rows)
        write(KEYS / f"{name}_key.csv", keys)
        print(f"{name}: {len(rows)} items")


if __name__ == "__main__":
    runlog.run("make_samples", main)
