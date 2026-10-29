"""Check A1 of PROTOCOL.md: recompute every grade from the published files only and compare with qrels.tsv.

Written from the text of PROTOCOL.md §3 and §5, without importing build_benchmark.py or corpus.py, in a
different style (per-document rules instead of vectorised masks). Inputs: corpus_attributes.csv,
queries.jsonl, qrels.tsv. Any disagreement is printed and makes the exit code 1.

    python check_labels.py --data data
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import runlog

EARTH_KM = 6371.0088
NEAR = 1.0
THU_DUC = ["Thành Phố Thủ Đức", "Quận 2", "Quận 9"]


def num(x: str):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def load_docs(path: Path) -> list[dict]:
    docs = []
    with open(path, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            lat, lon = num(r["lat"]), num(r["lon"])
            d = {"doc_id": int(r["doc_id"]), "property_type": r["property_type"], "subtype": r["subtype"],
                 "ward": r["ward"], "former_area": r["former_area"],
                 "reliable": r["coords_reliable"] == "True" and lat is not None and lon is not None,
                 "lat": lat if lat is not None else float("nan"), "lon": lon if lon is not None else float("nan")}
            for k in ("price", "area", "bedrooms", "has_title", "full_furniture"):
                d[k] = num(r[k])
            for k, v in r.items():
                if k.startswith(("drive_", "dist_")):
                    d[k] = num(v)
                elif v in ("True", "False") and k not in ("coords_reliable", "ward_coord_outlier"):
                    d[k] = v == "True"
            docs.append(d)
    return docs


def great_circle(lat1, lon1, lat2, lon2):
    """Vectorised haversine (km); the only numpy in this file."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    h = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_KM * np.arcsin(np.sqrt(h))


def core_members(docs, field, names):
    """PROTOCOL §3: per area, drop points farther than max(2 km, median + 5*1.4826*MAD) from the median centre."""
    members = []
    for name in names:
        pts = [d for d in docs if d[field] == name and d["reliable"]]
        if len(pts) < 5:
            members += pts
            continue
        clat = float(np.median([d["lat"] for d in pts]))
        clon = float(np.median([d["lon"] for d in pts]))
        dist = great_circle(np.array([d["lat"] for d in pts]), np.array([d["lon"] for d in pts]), clat, clon)
        med = float(np.median(dist))
        mad = float(np.median(np.abs(dist - med)))
        limit = max(2.0, med + 5 * 1.4826 * mad)
        members += [d for d, x in zip(pts, dist) if x <= limit]
    return members


def area_status(docs, field, names):
    """doc_id -> 'in' | 'near' | 'out'."""
    core = core_members(docs, field, names)
    clat = np.array([d["lat"] for d in core])
    clon = np.array([d["lon"] for d in core])
    out = {}
    for d in docs:
        if d[field] in names:
            out[d["doc_id"]] = "in"
        elif d["reliable"] and len(core) and float(great_circle(d["lat"], d["lon"], clat, clon).min()) <= NEAR:
            out[d["doc_id"]] = "near"
        else:
            out[d["doc_id"]] = "out"
    return out


def le(a, b) -> bool:
    """a <= b for the inclusive bounds of PROTOCOL §5, robust to binary floating point (4.4 vs 1.1 * 4.0)."""
    return round(a - b, 9) <= 0


def soft_status(d, gold):
    """List of 'ok' / 'band' / 'fail' for each soft constraint of the query."""
    res = []
    if "price" in gold:
        p, g = d["price"], gold["price"]
        if p is None:
            res.append("fail")
        elif "min" in g and "max" in g:
            res.append("ok" if le(g["min"], p) and le(p, g["max"]) else
                       ("band" if le(0.85 * g["min"], p) and le(p, 1.15 * g["max"]) else "fail"))
        elif "max" in g:
            res.append("ok" if le(p, g["max"]) else ("band" if le(p, 1.15 * g["max"]) else "fail"))
        else:
            dev = abs(p - g["target"]) / g["target"]
            res.append("ok" if le(dev, 0.10) else ("band" if le(dev, 0.20) else "fail"))
    if "area_min" in gold:
        a = d["area"]
        res.append("fail" if a is None else ("ok" if le(gold["area_min"], a) else
                                             ("band" if le(0.85 * gold["area_min"], a) else "fail")))
    if "beds" in gold:
        b, v, kind = d["bedrooms"], gold["beds"]["value"], gold["beds"]["kind"]
        if b is None:
            res.append("fail")
        elif kind == "exact":
            res.append("ok" if b == v else ("band" if b == v + 1 else "fail"))
        else:
            res.append("ok" if b >= v else ("band" if b == v - 1 else "fail"))
    for key, col in (("amenity", "drive_{}_km"), ("landmark", "dist_{}_km")):
        if key in gold:
            g = gold[key]
            x = d[col.format(g["category"] if key == "amenity" else g["name"])]
            res.append("fail" if x is None else ("ok" if le(x, g["max_km"]) else ("band" if le(x, 1.5 * g["max_km"]) else "fail")))
    return res


def hard_status(d, gold) -> bool:
    if gold.get("property_type") and d["property_type"] != gold["property_type"]:
        return False
    if gold.get("subtype") and d["subtype"] != gold["subtype"]:
        return False
    if gold.get("has_title") and d["has_title"] != 1:
        return False
    if gold.get("full_furniture") and d["full_furniture"] != 1:
        return False
    return all(d.get(a) is True for a in gold.get("aspects", []))


def grade(d, gold, where) -> int:
    if not hard_status(d, gold):
        return 0
    s = soft_status(d, gold)
    if "fail" in s:
        return 0
    bands = s.count("band")
    if where is None:                      # query without location
        return 3 if bands == 0 else (2 if bands == 1 else 0)
    w = where[d["doc_id"]]
    if w == "in":
        return 3 if bands == 0 else (2 if bands == 1 else 0)
    if w == "near" and bands == 0:
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    args = ap.parse_args()
    data = Path(args.data)
    docs = load_docs(data / "corpus_attributes.csv")
    queries = [json.loads(line) for line in open(data / "queries.jsonl", encoding="utf-8")]
    qrels = defaultdict(dict)
    for line in open(data / "qrels.tsv", encoding="utf-8"):
        qid, _, doc, g = line.split()
        qrels[qid][int(doc)] = int(g)
    runlog.stage(f"re-grade {len(queries)} queries × {len(docs)} listings from the protocol text")
    cache, mismatches, counts = {}, [], Counter()
    for q in runlog.progress(queries, "queries"):
        gold, where = q["gold"], None
        loc = gold.get("location")
        if loc:
            if loc["kind"] == "ward":
                key = ("ward", (loc["value"],))
            else:
                key = ("former_area", tuple(THU_DUC) if loc["value"] == "Thành Phố Thủ Đức" else (loc["value"],))
            if key not in cache:
                cache[key] = area_status(docs, key[0], key[1])
            where = cache[key]
        for d in docs:
            g = grade(d, gold, where)
            counts[g] += 1
            if g != qrels[q["qid"]].get(d["doc_id"], 0):
                mismatches.append((q["qid"], d["doc_id"], g, qrels[q["qid"]].get(d["doc_id"], 0)))
    total = len(queries) * len(docs)
    print(f"A1: {total:,} (query, listing) pairs re-graded; grade counts {dict(sorted(counts.items()))}")
    if mismatches:
        print(f"A1 FAILED: {len(mismatches)} mismatches, e.g. {mismatches[:10]}")
        sys.exit(1)
    print("A1 passed: 100% agreement with qrels.tsv")


if __name__ == "__main__":
    runlog.run("check_labels", main)
