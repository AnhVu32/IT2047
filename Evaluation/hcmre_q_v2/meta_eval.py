"""Automated meta-evaluation of HCMRE-Q v2 (PROTOCOL.md §7: B1, B4, C1–C4, E1 + label statistics).

The human checks (A2–A6, B2, B3) are in human/, the reliability checks (D1–D5) in eval_benchmark.py,
A1 in check_labels.py. This script does not import build_benchmark.py: its round-trip reader (B1) reads the
query text back on its own.

    python meta_eval.py --data data --out results/meta_eval.json [--skip-determinism]
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import itertools
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency

import runlog

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def norm(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).replace("đ", "d").replace("Đ", "D")
    return re.sub(r"\s+", " ", text.lower()).strip()


# =========================================================================== B1 round-trip reader
# Two views of a query: `ta` = lower-case with diacritics (tầm ≠ tám, tôi ≠ tỏi, số ≠ sổ) and `t` = without them.
# Number words only occur in accented text (style S4); S2 is accent-free but uses digits only.
UNITS = {"một": 1, "hai": 2, "ba": 3, "bốn": 4, "năm": 5, "sáu": 6, "bảy": 7, "tám": 8, "chín": 9}
TAIL = {**UNITS, "mốt": 1, "lăm": 5}
NUMW = r"(?:một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|mươi|mốt|lăm)"
DIG = r"(?<![\w.,])\d+(?:[.,]\d+)?"      # not inside "m2", "x2" or another number
LETTER = r"a-zà-ỹđ"


def lower(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text or "").lower()).strip()


def words_value(words: list[str]):
    """Vietnamese number words (1..99) -> int, or None."""
    w = [x for x in words if x]
    if not w:
        return None
    if w[0] == "mười":
        if len(w) == 1:
            return 10
        return 10 + TAIL[w[1]] if len(w) == 2 and w[1] in TAIL else None
    if w[0] in UNITS:
        if len(w) == 1:
            return UNITS[w[0]]
        if w[1] == "mươi":
            if len(w) == 2:
                return UNITS[w[0]] * 10
            return UNITS[w[0]] * 10 + TAIL[w[2]] if len(w) == 3 and w[2] in TAIL else None
    return None


def fnum(s: str) -> float:
    return float(s.replace(",", "."))


def tail_value(rest: str | None, half: str | None) -> float:
    if half:
        return 0.5
    if rest:
        return (int(rest) if rest.isdigit() else TAIL.get(rest, 0)) / 10
    return 0.0


UNIT = rf"(?:tỷ|ty|tỏi)(?![{LETTER}])"
TAIL_RE = rf"(?:\s*(rưỡi|ruoi)(?![{LETTER}])|\s*(\d|{NUMW})(?!\d|[.,]\d|[{LETTER}]))?"


def money_values(ta: str) -> list[float]:
    vals = []
    for m in re.finditer(rf"({DIG})\s*{UNIT}{TAIL_RE}", ta):
        vals.append(round(fnum(m.group(1)) + tail_value(m.group(3), m.group(2)), 4))
    for m in re.finditer(rf"((?:{NUMW}\s)*{NUMW})\s+{UNIT}{TAIL_RE}", ta):
        v = words_value(m.group(1).split())
        if v is not None:
            vals.append(round(v + tail_value(m.group(3), m.group(2)), 4))
    for m in re.finditer(rf"({DIG})\s*(?:-|đến|den|tới|toi)\s*({DIG})\s*{UNIT}", ta):    # "4 - 6.5 tỷ"
        vals += [round(fnum(m.group(1)), 4), round(fnum(m.group(2)), 4)]
    return vals


def has_money(ta: str) -> bool:
    return bool(re.search(rf"(?<![{LETTER}])(?:tỷ|tỏi)(?![{LETTER}])|\d\s*{UNIT}|(?<![{LETTER}])ty(?![{LETTER}])", ta))


def distance_values(ta: str) -> list[float]:
    out = [fnum(m.group(1)) for m in re.finditer(rf"({DIG})\s*(?:km|cây số|cay so)(?![{LETTER}])", ta)]
    out += [int(m.group(1)) / 1000 for m in
            re.finditer(rf"(\d{{2,4}})\s*(?:m|mét|met)(?![{LETTER}0-9²])(?!\s*(?:vuông|vuong))", ta)]
    out += [{"ba": 0.3, "năm": 0.5}[m.group(1)] for m in re.finditer(r"\b(ba|năm) trăm mét", ta)]
    return [round(x, 4) for x in out]


def int_values(ta: str, unit: str) -> list[int]:
    out = [int(m.group(1)) for m in re.finditer(rf"(\d+)\s*{unit}", ta)]
    for m in re.finditer(rf"((?:{NUMW}\s)*{NUMW})\s+{unit}", ta):
        v = words_value(m.group(1).split())
        if v is not None:
            out.append(v)
    return out


TYPE_RE = {"Căn hộ": r"can ho|chung cu|\bch\b|\bchcc\b|\bcc\b", "Nhà đất": r"\bnha\b",
           "Nhà mặt phố": r"mat pho|mat tien|\bmt\b|\bmtkd\b", "Biệt thự/Liền kề": r"biet thu|lien ke",
           "Shophouse": r"shophouse|nha pho thuong mai"}
AMENITY_RE = {"school": r"\btruong\b(?! (?:dai hoc|dh\b))", "college_university": r"dai hoc|\bdh\b",
              "metro": r"metro", "market": r"\bcho\b(?! (?:con|tien|nguoi|be|minh)\b)", "supermarket": r"sieu thi",
              "park": r"cong vien", "hospital": r"benh vien|\bbv\b", "mall": r"trung tam thuong mai|\btttm\b",
              "bus_stop": r"xe buyt|\bbus\b"}
LANDMARK_RE = {"ben_thanh": r"cho ben thanh", "tan_son_nhat": r"san bay", "landmark81": r"landmark ?81|\blm81\b",
               "phu_my_hung": r"phu my hung|\bpmh\b", "dhqg": r"lang dai hoc|lang dh|dhqg|dh quoc gia"}
ASPECT_RE = {"hem_xe_hoi": r"hem xe hoi|hem o ?to|\bhxh\b|o to do cua|xe hoi (?:vao|dau)|o to vao",
             "dong_tien": r"dong tien|cho thue|\bchdv\b|can ho dich vu|hd thue|nguoi thue",
             "can_goc": r"\bgoc\b", "nha_moi": r"moi xay|xay moi|moi 100|con moi|moi hoan thien",
             "view_song": r"\bsong\b", "thang_may_nha": r"thang may", "san_vuon": r"san vuon|co vuon",
             "ho_boi": r"ho boi|be boi"}
MAX_WORDS = r"(?:duoi|toi da|khong qua|do lai|tro xuong|max|<|trong vong|do xuong)"
TITLE_RE = rf"(?<![{LETTER}])sổ(?![{LETTER}])|(?:\bco|\bda co) so\b|\bso hong\b"


def location_found(t: str, loc: dict, collisions: set) -> bool:
    if loc["kind"] == "ward":
        _, name = loc["value"].split(" ", 1)
        n = re.escape(norm(name))
        hits = list(re.finditer(rf"(?<![a-z]){n}(?![a-z])", t))
        if not hits:
            return False
        if name in collisions:
            pre = r"(?:phuong|xa)\s$|(?:\bp|\bx)\.\s?$|\bp\s$"
            return any(re.search(pre, t[max(0, h.start() - 8):h.start()]) for h in hits)
        return True
    value = loc["value"]
    if value == "Thành Phố Thủ Đức":
        return bool(re.search(r"(?:\btp\.?|thanh pho)\s?thu duc", t))
    for p in ("Thành Phố ", "Quận ", "Huyện "):
        if value.startswith(p):
            name = norm(value[len(p):])
            if name.isdigit():
                return bool(re.search(rf"(?:quan|\bq\.?)\s?{name}(?!\d)", t))
            if name in {norm(c) for c in collisions}:
                return bool(re.search(rf"(?:quan|huyen|thanh pho|\btp\.?|\bq\.|\bh\.|\bq)\s?{re.escape(name)}", t))
            return name in t
    return norm(value) in t


def round_trip(q: dict, collisions: set) -> list[str]:
    """Problems found when reading the query back (empty = faithful)."""
    ta, g, bad = lower(q["text"]), q["gold"], []
    t = norm(q["text"])
    type_key = g.get("subtype") or g["property_type"]
    if not re.search(TYPE_RE[type_key], t):
        bad.append("type")
    loc = g.get("location")
    if loc and not location_found(t, loc, collisions):
        bad.append("location")
    if loc and loc.get("with_former") and not location_found(t, {"kind": "former_area", "value": loc["with_former"]},
                                                             collisions):
        bad.append("dual_mention")
    if not loc and re.search(r"\bphuong\b|\bquan\b|\bp\.|\bq\d", t):
        bad.append("extra_location")
    gp = g.get("price")
    if gp:
        vals = money_values(ta)
        want = [gp["min"], gp["max"]] if "min" in gp else [gp.get("max", gp.get("target"))]
        if not all(any(abs(v - w) < 1e-6 for v in vals) for w in want):
            bad.append(f"price {want} not in {vals}")
        elif "max" in gp and "min" not in gp and not re.search(MAX_WORDS, t):
            bad.append("price_kind")
        elif len(set(vals)) != len(set(want)):
            bad.append(f"price_extra_value {vals}")
    elif has_money(ta):
        bad.append("extra_price")
    if g.get("beds"):
        if int_values(ta, r"(?:pn|phòng ngủ|phong ngu)") != [g["beds"]["value"]]:
            bad.append("beds")
    elif re.search(r"pn\b|phong ngu", t):
        bad.append("extra_beds")
    if g.get("area_min"):
        if int_values(ta, r"(?:m2|m²|mét vuông|met vuong)") != [g["area_min"]]:
            bad.append("area")
    elif re.search(r"m2|m²|met vuong", t):
        bad.append("extra_area")
    dist = distance_values(ta)
    tm = t                                    # place names ("Chợ Quán", "Long Trường") are not amenity words
    for place in [loc["value"], loc.get("with_former") or ""] if loc else []:
        if place:
            tm = re.sub(rf"(?<![a-z]){re.escape(norm(place.split(' ', 1)[1] if ' ' in place else place))}(?![a-z])", " ", tm)
    for key, table in (("amenity", AMENITY_RE), ("landmark", LANDMARK_RE)):
        item = g.get(key)
        if item:
            name = item["category"] if key == "amenity" else item["name"]
            if not re.search(table[name], tm):
                bad.append(key)
            others = [k for k, rx in table.items() if k != name and re.search(rx, tm)
                      and not (key == "landmark" and k == "ben_thanh")]
            if others:
                bad.append(f"extra_{key} {others}")
            if item["explicit"] and dist != [item["max_km"]]:
                bad.append(f"{key}_distance {item['max_km']} vs {dist}")
            if not item["explicit"] and dist:
                bad.append(f"{key}_extra_distance")
    if not g.get("amenity") and not g.get("landmark") and dist:
        bad.append("extra_distance")
    for a, rx in ASPECT_RE.items():
        present = bool(re.search(rx, tm))
        if a in g.get("aspects", []) and not present:
            bad.append(f"aspect {a}")
        if a not in g.get("aspects", []) and present:
            bad.append(f"extra_aspect {a}")
    if bool(g.get("has_title")) != bool(re.search(TITLE_RE, ta)):
        bad.append("title")
    if bool(g.get("full_furniture")) != bool(re.search(r"noi that|\bnt\b", t)):
        bad.append("furniture")
    return bad

# =========================================================================== C checks
def char_ngrams(text: str, n: int = 3) -> set:
    t = f" {norm(text)} "
    return {t[i:i + n] for i in range(len(t) - n + 1)}


def imports_of(path: Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
    return out


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


OUTPUT_FILES = ("queries.jsonl", "qrels.tsv", "corpus_attributes.csv", "stats.json")


# =========================================================================== main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="results/meta_eval.json")
    ap.add_argument("--skip-determinism", action="store_true")
    args = ap.parse_args()
    data = Path(args.data)
    qs = [json.loads(line) for line in open(data / "queries.jsonl", encoding="utf-8")]
    stats = json.load(open(data / "stats.json", encoding="utf-8"))
    collisions = set(stats["name_collisions"])
    corpus = pd.read_csv(data / "corpus_attributes.csv", low_memory=False)
    qrels = defaultdict(dict)
    for line in open(data / "qrels.tsv", encoding="utf-8"):
        qid, _, doc, g = line.split()
        qrels[qid][int(doc)] = int(g)
    report = {}

    # ---- B1
    runlog.stage('B1 read the gold constraints back from the text')
    problems = {q["qid"]: round_trip(q, collisions) for q in qs}
    failed = {k: v for k, v in problems.items() if v}
    report["B1_round_trip"] = {"passed": not failed, "queries": len(qs), "failed": len(failed),
                               "examples": [{"qid": k, "text": next(q["text"] for q in qs if q["qid"] == k), "problems": v}
                                            for k, v in list(failed.items())[:15]]}

    # ---- B4 diversity
    runlog.stage('B4 diversity')
    toks = [norm(q["text"]).split() for q in qs]
    uni = Counter(itertools.chain.from_iterable(toks))
    bi = Counter(itertools.chain.from_iterable(zip(t, t[1:]) for t in toks))
    lens = np.array([len(t) for t in toks])
    report["B4_diversity"] = {"distinct_1": round(len(uni) / sum(uni.values()), 4), "distinct_2": round(len(bi) / sum(bi.values()), 4),
                              "unique_texts": len({q["text"] for q in qs}), "frames_used": len({q["frame_id"] for q in qs}),
                              "length_words": {"mean": round(float(lens.mean()), 2), "p10": float(np.percentile(lens, 10)),
                                               "p90": float(np.percentile(lens, 90))}}

    # ---- C1 disjointness
    runlog.stage('C1 split disjointness')
    by_split = defaultdict(list)
    for q in qs:
        by_split[q["split"]].append(q)
    seeds = {s: {q["seed_doc_id"] for q in v} for s, v in by_split.items()}
    frames = {s: {q["frame_id"] for q in v} for s, v in by_split.items()}
    viol = {
        "duplicate_qids": len(qs) - len({q["qid"] for q in qs}),
        "duplicate_texts": len(qs) - len({q["text"] for q in qs}),
        "seed_overlap": sum(len(seeds[a] & seeds[b]) for a, b in itertools.combinations(sorted(seeds), 2)),
        "test_frames_in_train_or_val": len(frames["test"] & (frames["train"] | frames["val"])),
        "val_frames_in_train": len(frames["val"] & frames["train"]),
    }
    report["C1_disjointness"] = {"passed": sum(viol.values()) == 0, **viol}

    # ---- C2 near duplicates across splits
    runlog.stage('C2 near duplicates across splits')
    grams = {q["qid"]: char_ngrams(q["text"]) for q in qs}
    near = 0
    for q in by_split["test"] + by_split["val"]:
        for p in by_split["train"] + (by_split["val"] if q["split"] == "test" else []):
            a, b = grams[q["qid"]], grams[p["qid"]]
            if len(a & b) / len(a | b) >= 0.9:
                near += 1
                break
    report["C2_near_duplicates"] = {"queries_with_near_duplicate_in_earlier_split": near,
                                    "rate": round(near / (len(by_split["test"]) + len(by_split["val"])), 4),
                                    "passed": near / (len(by_split["test"]) + len(by_split["val"])) <= 0.01}

    # ---- C3 no backend import in the label / query code
    runlog.stage('C3 no backend import')
    files = [HERE / "corpus.py", HERE / "build_benchmark.py", HERE / "check_labels.py", REPO / "Data/v3/pipeline/price_text.py"]
    found = {str(f.relative_to(REPO)): sorted(m for m in imports_of(f) if m.split(".")[0] in ("backend", "src"))
             for f in files}
    report["C3_independence"] = {"passed": not any(found.values()), "backend_imports": found}

    # ---- C4 balance
    runlog.stage('C4 balance between splits')
    df = pd.DataFrame(qs)
    report["C4_balance"] = {}
    for col in ("family", "style", "loc_kind"):
        tab = pd.crosstab(df[col], df["split"])
        chi2, p, dof, _ = chi2_contingency(tab)
        report["C4_balance"][col] = {"chi2": round(float(chi2), 3), "dof": int(dof), "p": round(float(p), 4),
                                     "table": tab.to_dict()}

    # ---- label statistics (context for A3/A4 and D5)
    runlog.stage('label statistics')
    attrs = corpus.set_index("doc_id")
    rel_docs = [(q["qid"], d, g) for q in qs for d, g in qrels[q["qid"]].items()]
    rel = pd.DataFrame(rel_docs, columns=["qid", "doc_id", "grade"]).join(attrs, on="doc_id")
    fallback = {}
    for col in ("price_src", "bedrooms_src", "has_title_src", "full_furniture_src"):
        fallback[col] = round(float((rel[col] == "text").mean()), 4)
    report["label_statistics"] = {
        "qrels_rows": len(rel),
        "grade_counts": rel["grade"].value_counts().sort_index().to_dict(),
        "share_of_relevant_pairs_using_text_fallback": fallback,
        "share_of_relevant_pairs_on_ward_coord_outlier": round(float(rel["ward_coord_outlier"].mean()), 4),
        "share_of_relevant_pairs_from_new_crawl": round(float((rel["source"] != "old").mean()), 4),
        "corpus_share_new_crawl": round(float((corpus["source"] != "old").mean()), 4),
        "queries_by_location_kind": df["loc_kind"].value_counts().to_dict(),
        "ward_share": round(float((df["loc_kind"] == "ward").mean()), 4),
        "ward_share_of_located": round(float((df["loc_kind"] == "ward").sum() / (df["loc_kind"] != "none").sum()), 4),
    }

    # ---- E1 determinism
    runlog.stage('E1 determinism: regenerate the data 3 times (PYTHONHASHSEED 0, 1, 12345) — the slow part, a few minutes')
    if not args.skip_determinism:
        ref = {f: sha256(data / f) for f in OUTPUT_FILES}
        runs = {}
        for seed in ("0", "1", "12345"):
            with tempfile.TemporaryDirectory() as tmp:
                runlog.info(f"   build_benchmark.py with PYTHONHASHSEED={seed}")
                env = dict(os.environ, PYTHONHASHSEED=seed, HCMRE_NO_LOG="1")
                subprocess.run([sys.executable, str(HERE / "build_benchmark.py"), "--out", tmp], env=env, check=True,
                               cwd=HERE, stdout=subprocess.DEVNULL)
                runs[seed] = {f: sha256(Path(tmp) / f) == ref[f] for f in OUTPUT_FILES}
        report["E1_determinism"] = {"passed": all(all(v.values()) for v in runs.values()), "runs": runs,
                                    "sha256": ref}

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(report, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for key, val in report.items():
        flag = val.get("passed") if isinstance(val, dict) else None
        print(f"{key:28} {'' if flag is None else ('PASS' if flag else 'FAIL')}")
    print(json.dumps({k: v for k, v in report.items() if k in ("B1_round_trip", "C1_disjointness", "C2_near_duplicates")},
                     ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    runlog.run("meta_eval", main)
