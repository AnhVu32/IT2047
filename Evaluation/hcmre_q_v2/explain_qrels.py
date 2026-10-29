"""Explain, constraint by constraint, why a listing got its grade for a query (PROTOCOL.md §5).

    # 1) every labelled pair (grade 1–3) -> data/qrels_explained.csv  (UTF-8 with BOM, opens in Excel)
    python explain_qrels.py
    # 2) one query on screen, or chosen listings of that query (grade 0 included: why it is NOT relevant)
    python explain_qrels.py --qid v2q0001
    python explain_qrels.py --qid v2q0801 --listing 46361337 46357969
    # 3) error analysis of a system: explain its top-k for every test query, count why results miss
    python explain_qrels.py --run results/runs.jsonl.gz --system prod_nodl --k 10
    python explain_qrels.py --run results/live_test/responses.jsonl --k 10        # a run_live.py cache

The grade is recomputed with the functions of check_labels.py (the independent re-implementation of the protocol)
and must equal qrels.tsv; the script stops if it does not. Nothing in data/qrels.tsv is changed.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

import check_labels as CL
import corpus as C
import runlog

HERE = Path(__file__).resolve().parent
ASPECT_VI = {"hem_xe_hoi": "hẻm xe hơi", "dong_tien": "dòng tiền", "can_goc": "căn góc", "nha_moi": "nhà mới",
             "view_song": "view sông", "thang_may_nha": "thang máy", "san_vuon": "sân vườn", "ho_boi": "hồ bơi"}
AMENITY_VI = {"school": "trường học", "bus_stop": "trạm xe buýt", "supermarket": "siêu thị", "market": "chợ",
              "park": "công viên", "college_university": "trường đại học", "hospital": "bệnh viện",
              "mall": "trung tâm thương mại", "metro": "ga metro"}
LANDMARK_VI = {"ben_thanh": "chợ Bến Thành", "tan_son_nhat": "sân bay Tân Sơn Nhất", "landmark81": "Landmark 81",
               "phu_my_hung": "Phú Mỹ Hưng", "dhqg": "ĐHQG"}
STATUS_VI = {"ok": "đạt", "band": "lệch nhẹ", "fail": "trượt"}
COLUMNS = ["qid", "split", "query", "listing_id", "grade", "ly_do",
           "property_type", "type_ok", "price", "price_src", "price_wanted", "price_status",
           "area", "area_wanted", "area_status", "bedrooms", "bedrooms_src", "beds_wanted", "beds_status",
           "location_wanted", "ward", "former_area", "location_status", "km_to_area",
           "amenity_wanted", "amenity_km", "amenity_status", "landmark_wanted", "landmark_km", "landmark_status",
           "aspects_wanted", "aspects_ok", "aspect_evidence", "subtype_wanted", "subtype",
           "has_title_wanted", "has_title", "full_furniture_wanted", "full_furniture", "ward_coord_outlier"]


def vn(x, nd=2) -> str:
    """Number with a Vietnamese decimal comma, without trailing zeros."""
    if x is None or (isinstance(x, float) and x != x):
        return "?"
    s = f"{x:.{nd}f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


# ----------------------------------------------------------------------------------------------- aspect evidence
def norm_with_map(text: str) -> tuple[str, list[int]]:
    """corpus.norm(text) together with, for each output character, its index in the original text."""
    out, idx, space = [], [], False
    for i, ch in enumerate(text):
        if ch.isspace():
            space = bool(out)
            continue
        base = "".join(c for c in unicodedata.normalize("NFD", ch) if not unicodedata.combining(c))
        base = base.replace("đ", "d").replace("Đ", "D").lower()
        if not base:
            continue
        if space:
            out.append(" ")
            idx.append(i - 1)
            space = False
        for c in base:
            out.append(c)
            idx.append(i)
    return "".join(out), idx


def aspect_evidence(text: str, aspect: str, prop_type: str) -> str:
    """The first passage where the labelling function of corpus.py fires (positive match not negated)."""
    tn, idx = norm_with_map(text)
    pos, neg, pos_by_type = C._ASPECT_RE[aspect]
    negatives = [(m.start(), m.end()) for m in neg.finditer(tn)]
    for m in pos_by_type.get(prop_type, pos).finditer(tn):
        p = m.start()
        if not any(s - 25 <= p <= e for s, e in negatives):
            a, b = idx[max(0, p - 45)], idx[min(len(idx) - 1, m.end() + 45)]
            return ("…" if a > 0 else "") + " ".join(text[a:b + 1].split()) + ("…" if b < len(text) - 1 else "")
    return ""


# ----------------------------------------------------------------------------------------------- explanation
class Explainer:
    def __init__(self, data: Path):
        self.docs = CL.load_docs(data / "corpus_attributes.csv")
        self.by_id = {d["doc_id"]: d for d in self.docs}
        attrs = pd.read_csv(data / "corpus_attributes.csv", low_memory=False)
        self.extra = attrs.set_index("doc_id")[["ward", "former_area", "price_src", "bedrooms_src",
                                                 "ward_coord_outlier"]].to_dict("index")
        self.queries = {q["qid"]: q for q in (json.loads(line) for line in open(data / "queries.jsonl", encoding="utf-8"))}
        self.qrels = defaultdict(dict)
        for line in open(data / "qrels.tsv", encoding="utf-8"):
            qid, _, doc, g = line.split()
            self.qrels[qid][int(doc)] = int(g)
        self.cache = {}
        self._texts = None

    def texts(self) -> dict:
        if self._texts is None:
            m = pd.read_csv(C.V3 / "master_v3.csv", usecols=["listing_id", "title", "description"], low_memory=False)
            self._texts = {int(r.listing_id): f"{r.title if r.title == r.title else ''} . "
                                              f"{r.description if r.description == r.description else ''}"
                           for r in m.itertuples(index=False)}
        return self._texts

    def area(self, loc: dict):
        """(status by doc_id, km from each listing to the nearest core listing of the area)."""
        if loc["kind"] == "ward":
            key = ("ward", (loc["value"],))
        else:
            key = ("former_area", tuple(CL.THU_DUC) if loc["value"] == "Thành Phố Thủ Đức" else (loc["value"],))
        if key not in self.cache:
            status = CL.area_status(self.docs, key[0], key[1])
            core = CL.core_members(self.docs, key[0], key[1])
            clat, clon = np.array([d["lat"] for d in core]), np.array([d["lon"] for d in core])
            km = {}
            for d in self.docs:
                if status[d["doc_id"]] != "in" and d["reliable"] and len(core):
                    km[d["doc_id"]] = float(CL.great_circle(d["lat"], d["lon"], clat, clon).min())
            self.cache[key] = (status, km)
        return self.cache[key]

    def explain(self, qid: str, doc_id: int) -> dict:
        q, d = self.queries[qid], self.by_id[doc_id]
        gold, x = q["gold"], self.extra[doc_id]
        row = {"qid": qid, "split": q["split"], "query": q["text"], "listing_id": doc_id,
               "property_type": d["property_type"], "price": d["price"], "price_src": x["price_src"],
               "area": d["area"], "bedrooms": d["bedrooms"], "bedrooms_src": x["bedrooms_src"],
               "ward": x["ward"], "former_area": x["former_area"], "subtype": d["subtype"],
               "has_title": d["has_title"], "full_furniture": d["full_furniture"],
               "ward_coord_outlier": x["ward_coord_outlier"]}
        hard_msgs, soft_msgs, n_band, failed = [], [], 0, False

        # hard constraints
        ok = d["property_type"] == gold["property_type"]
        row["type_ok"] = ok
        hard_msgs.append(f"{d['property_type']} {'✓' if ok else '✗ (hỏi ' + gold['property_type'] + ')'}")
        failed |= not ok
        if gold.get("subtype"):
            ok = d["subtype"] == gold["subtype"]
            row["subtype_wanted"] = gold["subtype"]
            hard_msgs.append(f"loại {d['subtype'] or '?'} {'✓' if ok else '✗ (hỏi ' + gold['subtype'] + ')'}")
            failed |= not ok
        for key, label in (("has_title", "sổ"), ("full_furniture", "full nội thất")):
            if gold.get(key):
                ok = d[key] == 1
                row[f"{key}_wanted"] = True
                hard_msgs.append(f"{label} {'✓' if ok else '✗'}")
                failed |= not ok
        if gold.get("aspects"):
            row["aspects_wanted"] = ", ".join(ASPECT_VI[a] for a in gold["aspects"])
            oks = [d.get(a) is True for a in gold["aspects"]]
            row["aspects_ok"] = all(oks)
            failed |= not all(oks)
            ev = [aspect_evidence(self.texts().get(doc_id, ""), a, d["property_type"]) for a, o in zip(gold["aspects"], oks) if o]
            row["aspect_evidence"] = " | ".join(e for e in ev if e)
            hard_msgs.append(", ".join(f"{ASPECT_VI[a]} {'✓' if o else '✗'}" for a, o in zip(gold["aspects"], oks)))

        # soft constraints (same order as check_labels.soft_status)
        def soft(key, sub):
            nonlocal n_band, failed
            st = CL.soft_status(d, {key: sub})[0]
            n_band += st == "band"
            failed |= st == "fail"
            return st

        if "price" in gold:
            g = gold["price"]
            want = (f"{vn(g['min'])}–{vn(g['max'])} tỷ" if "min" in g and "max" in g else
                    f"≤ {vn(g['max'])} tỷ" if "max" in g else f"khoảng {vn(g['target'])} tỷ")
            st = soft("price", g)
            row.update(price_wanted=want, price_status=STATUS_VI[st])
            soft_msgs.append(f"giá {vn(d['price'])} tỷ (hỏi {want}): {STATUS_VI[st]}" if d["price"] is not None
                             else f"không có giá (hỏi {want}): trượt")
        if "area_min" in gold:
            st = soft("area_min", gold["area_min"])
            row.update(area_wanted=f"≥ {vn(gold['area_min'])} m²", area_status=STATUS_VI[st])
            soft_msgs.append(f"{vn(d['area'], 1)} m² (hỏi ≥ {vn(gold['area_min'])}): {STATUS_VI[st]}")
        if "beds" in gold:
            b = gold["beds"]
            want = f"{'đúng' if b['kind'] == 'exact' else '≥'} {b['value']} PN"
            st = soft("beds", b)
            row.update(beds_wanted=want, beds_status=STATUS_VI[st])
            soft_msgs.append(f"{vn(d['bedrooms'], 0)} PN (hỏi {want}): {STATUS_VI[st]}")
        if "amenity" in gold:
            g = gold["amenity"]
            km = d.get(f"drive_{g['category']}_km")
            st = soft("amenity", g)
            row.update(amenity_wanted=f"{AMENITY_VI.get(g['category'], g['category'])} ≤ {vn(g['max_km'])} km",
                       amenity_km=km, amenity_status=STATUS_VI[st])
            soft_msgs.append(f"{AMENITY_VI.get(g['category'], g['category'])} cách {vn(km)} km lái xe "
                             f"(hỏi ≤ {vn(g['max_km'])}): {STATUS_VI[st]}")
        if "landmark" in gold:
            g = gold["landmark"]
            km = d.get(f"dist_{g['name']}_km")
            st = soft("landmark", g)
            row.update(landmark_wanted=f"{LANDMARK_VI.get(g['name'], g['name'])} ≤ {vn(g['max_km'])} km",
                       landmark_km=km, landmark_status=STATUS_VI[st])
            soft_msgs.append(f"{LANDMARK_VI.get(g['name'], g['name'])} cách {vn(km)} km đường chim bay "
                             f"(hỏi ≤ {vn(g['max_km'])}): {STATUS_VI[st]}")

        # location and grade (PROTOCOL §5)
        loc_msg, where = "", None
        if gold.get("location"):
            loc = gold["location"]
            status, kms = self.area(loc)
            where = status[doc_id]
            km = kms.get(doc_id)
            row.update(location_wanted=loc["value"], location_status={"in": "trong", "near": "sát (≤ 1 km)",
                                                                          "out": "ngoài"}[where], km_to_area=km)
            place = x["ward"] if loc["kind"] == "ward" else x["former_area"]
            loc_msg = (f"trong {loc['value']}" if where == "in" else
                       f"ở {place}, cách {loc['value']} {vn(km)} km" if km is not None else
                       f"ở {place}, toạ độ không đáng tin")
        grade = CL.grade(d, gold, None if where is None else self.area(gold["location"])[0])
        assert grade == self.qrels[qid].get(doc_id, 0), (qid, doc_id, grade, self.qrels[qid].get(doc_id, 0))
        row["grade"] = grade

        if failed:
            miss = [m for m in hard_msgs if "✗" in m] + [m for m in soft_msgs if m.endswith("trượt")]
            verdict = "mức 0: không thoả " + "; ".join(miss)
        elif n_band > 1:
            verdict = f"mức 0: lệch nhẹ {n_band} ràng buộc cùng lúc (chỉ chấp nhận 1)"
        elif where == "out":
            verdict = f"mức 0: ngoài khu vực hỏi ({loc_msg})"
        elif where == "near" and n_band:
            verdict = f"mức 0: sát khu vực ({loc_msg}) nhưng còn lệch nhẹ 1 ràng buộc"
        elif where == "near":
            verdict = f"mức 1: sát khu vực ({loc_msg}), đạt mọi ràng buộc khác"
        elif n_band:
            verdict = "mức 2: " + (f"{loc_msg}, " if loc_msg else "") + "lệch nhẹ 1 ràng buộc"
        else:
            verdict = "mức 3: " + (f"{loc_msg}, " if loc_msg else "") + "đạt mọi ràng buộc"
        row["ly_do"] = verdict + " — " + "; ".join(hard_msgs + soft_msgs)
        return row


def read_run(path: Path, system: str | None) -> dict:
    opener = gzip.open if path.suffix == ".gz" else open
    out = {}
    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if "system" in r and r["system"] != system:
                continue
            out[r["qid"]] = r["ranking"]
    if not out:
        raise SystemExit(f"no ranking for system {system!r} in {path}")
    return out


def write_csv(rows: list[dict], path: Path):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if v is None or (isinstance(v, float) and v != v) else
                            round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(HERE / "data"))
    ap.add_argument("--qid", help="explain one query on screen")
    ap.add_argument("--listing", type=int, nargs="*", help="with --qid: these listings only (any grade)")
    ap.add_argument("--run", help="runs.jsonl.gz of eval_benchmark.py, or responses.jsonl of run_live.py")
    ap.add_argument("--system", help="system name inside runs.jsonl.gz (not needed for responses.jsonl)")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--split", default="test", choices=["train", "val", "test", "all"])
    ap.add_argument("--out", help="output CSV (default: data/qrels_explained.csv, or next to --run)")
    args = ap.parse_args()

    runlog.stage("load corpus attributes, queries and qrels")
    ex = Explainer(Path(args.data))

    if args.qid:
        ids = args.listing or sorted(ex.qrels[args.qid], key=lambda d: (-ex.qrels[args.qid][d], d))
        q = ex.queries[args.qid]
        print(f"\n{args.qid} [{q['split']}] {q['text']}\n  ràng buộc vàng: {json.dumps(q['gold'], ensure_ascii=False)}\n")
        for d in ids:
            r = ex.explain(args.qid, d)
            print(f"  {d}: {r['ly_do']}")
            if r.get("aspect_evidence"):
                print(f"      đoạn văn: {r['aspect_evidence']}")
        return

    if args.run:
        run = read_run(Path(args.run), args.system)
        qids = [qid for qid, q in ex.queries.items() if args.split == "all" or q["split"] == args.split]
        name = args.system or "live"
        runlog.stage(f"explain the top-{args.k} of {name} for {len(qids)} {args.split} queries")
        rows = []
        for qid in runlog.progress(qids, "queries"):
            for rank, d in enumerate(run.get(qid, [])[:args.k], 1):
                rows.append({**ex.explain(qid, int(d)), "rank": rank})
        out = Path(args.out) if args.out else Path(args.run).parent / f"explained_{name}_top{args.k}.csv"
        COLUMNS.insert(4, "rank")
        write_csv(rows, out)
        grades = Counter(r["grade"] for r in rows)
        reasons = Counter()
        for r in rows:
            if r["grade"] == 0:
                head = r["ly_do"].split(" — ")[0]
                for key, label in (("type_ok", "sai loại nhà"), ("aspects_ok", "thiếu đặc điểm")):
                    if r.get(key) is False:
                        reasons[label] += 1
                for key, label in (("price_status", "trượt giá"), ("area_status", "trượt diện tích"),
                                   ("beds_status", "trượt số phòng"), ("amenity_status", "xa tiện ích"),
                                   ("landmark_status", "xa địa danh")):
                    if r.get(key) == "trượt":
                        reasons[label] += 1
                if r.get("location_status") == "ngoài":
                    reasons["ngoài khu vực hỏi"] += 1
                if "lệch nhẹ" in head:
                    reasons["đạt từng ràng buộc nhưng lệch nhẹ quá nhiều"] += 1
        n = len(rows)
        print(f"\n{name}: {n} kết quả top-{args.k}; mức 3/2/1/0 = "
              + " / ".join(f"{grades[g]} ({100 * grades[g] / max(1, n):.0f}%)" for g in (3, 2, 1, 0)))
        print("Vì sao các kết quả mức 0 không liên quan (một kết quả có thể có nhiều lý do):")
        for label, c in reasons.most_common():
            print(f"  {label:42} {c:6}  ({100 * c / max(1, grades[0]):.0f}% số kết quả mức 0)")
        print(f"\nChi tiết: {out}")
        return

    pairs = [(qid, d) for qid in ex.queries for d in sorted(ex.qrels[qid], key=lambda d: (-ex.qrels[qid][d], d))]
    runlog.stage(f"explain {len(pairs)} labelled pairs (grade 1–3)")
    rows = [ex.explain(qid, d) for qid, d in runlog.progress(pairs, "pairs")]
    out = Path(args.out) if args.out else Path(args.data) / "qrels_explained.csv"
    write_csv(rows, out)
    print(f"\n{len(rows)} cặp đã giải thích, mọi mức khớp qrels.tsv -> {out}")


if __name__ == "__main__":
    runlog.run("explain_qrels", main)
