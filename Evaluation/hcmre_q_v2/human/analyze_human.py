"""Score the human checks A2–A6, B2, B3 of PROTOCOL.md §7 against the pre-registered thresholds.

    python human/analyze_human.py                 # reads human/answers/answers_<task>_<annotator>.csv
    python human/analyze_human.py --answers human/answers_preaudit --out human/preaudit_report \
        --title "TIỀN KIỂM ĐỊNH BỞI AI — tạm thời, không thay thế người chấm"

Several annotators per task are allowed: the decision uses the first annotator in alphabetical order unless
--primary is given, and agreement between annotators is reported (Cohen's κ; quadratic-weighted κ for H3).
Writes <out>/report.json and <out>/REPORT.md (default: human/). Standard library + pandas only.
Breakdowns marked "exploratory" are not part of the pre-registered decision rules.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runlog  # noqa: E402

HERE = Path(__file__).resolve().parent
# H1 mixes the precision sample (key auto = 1, check A2) and the keyword-negative sample (auto = 0, check A3).
TASK_FILES = {"H1": "H1_aspects", "H2": "H2_queries", "H3": "H3_graded_pairs", "H4": "H4_ward_priority",
              "H5": "H5_price_corrections"}


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (round(centre - half, 4), round(centre + half, 4))


def binom_greater(k: int, n: int) -> float:
    """P(X >= k), X ~ Binomial(n, 0.5) — one-sided sign test."""
    return sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n


def kappa(a: list, b: list, labels: list, weighted: bool = False) -> float:
    idx = {l: i for i, l in enumerate(labels)}
    k, n = len(labels), len(a)
    if n == 0:
        return float("nan")
    obs = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[idx[x]][idx[y]] += 1
    ra = [sum(r) for r in obs]
    cb = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    w = [[((i - j) ** 2) / ((k - 1) ** 2) if weighted else float(i != j) for j in range(k)] for i in range(k)]
    num = sum(w[i][j] * obs[i][j] for i in range(k) for j in range(k))
    den = sum(w[i][j] * ra[i] * cb[j] / n for i in range(k) for j in range(k))
    return round(1 - num / den, 4) if den else float("nan")


def load_answers(folder: Path) -> dict:
    out = defaultdict(dict)
    for path in sorted(folder.glob("answers_*.csv")):
        m = re.match(r"answers_(.+)_([^_]+)\.csv$", path.name)
        if not m:
            continue
        task = next((t for t, f in TASK_FILES.items() if f == m.group(1)), None)
        if task:
            df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
            out[task][m.group(2)] = df[df["answer"] != ""].set_index("item_id")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers", default=str(HERE / "answers"))
    ap.add_argument("--primary", help="annotator whose answers decide the thresholds")
    ap.add_argument("--out", default=str(HERE), help="folder for report.json and REPORT.md")
    ap.add_argument("--title", default="", help="extra line under the report heading, e.g. who produced the answers")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    answers = load_answers(Path(args.answers))
    keys = {t: pd.read_csv(HERE / "keys" / f"{f}_key.csv", dtype=str).set_index("item_id") for t, f in TASK_FILES.items()}
    # listings shown to the AI assistant while it developed the labelling functions (PROTOCOL.md §9.7); H1 excludes
    # them by construction, for H3/H4 a sensitivity check without them is reported (exploratory)
    preaudit = HERE / "preaudit_items.json"
    lf_dev = {str(x) for x in json.load(open(preaudit, encoding="utf-8")).get("lf_dev", [])} if preaudit.exists() else set()
    rep = {"annotators": {t: sorted(v) for t, v in answers.items()}}

    def primary(task):
        who = sorted(answers.get(task, {}))
        if not who:
            return None, None
        name = args.primary if args.primary in who else who[0]
        return name, answers[task][name].join(keys[task], how="inner")

    # A2 / A3 aspects (one blind file; the key says which sample each listing came from)
    who, h1 = primary("H1")
    d = None if h1 is None else h1[h1["auto"] == "1"]
    if d is not None:
        d = d[d["answer"].isin(["0", "1"])]
        per = d.groupby("aspect")["answer"].apply(lambda s: (int((s == "1").sum()), len(s))).to_dict()
        k, n = int((d["answer"] == "1").sum()), len(d)
        lo, hi = wilson(k, n)
        failing = [a for a, (ok, tot) in per.items() if tot - ok > 3]
        rep["A2_aspect_precision"] = {"annotator": who, "precision": round(k / n, 4) if n else None, "n": n,
                                      "wilson95": [lo, hi], "per_aspect": {a: f"{ok}/{tot}" for a, (ok, tot) in per.items()},
                                      "aspects_to_drop": failing,
                                      "passed": n > 0 and k / n >= 0.90 and lo >= 0.80 and not failing}
    d = None if h1 is None else h1[h1["auto"] == "0"]
    if d is not None:
        d = d[d["answer"].isin(["0", "1"])]
        rep["A3_aspect_misses"] = {"annotator": who, "n": len(d),
                                   "share_of_keyword_negatives_that_are_positive": round(float((d["answer"] == "1").mean()), 4),
                                   "per_aspect": d.groupby("aspect")["answer"].apply(lambda s: f"{(s == '1').sum()}/{len(s)}").to_dict()}

    # A4 graded labels
    who, d = primary("H3")
    if d is not None:
        d = d[d["answer"].isin(["0", "1", "2", "3"])]
        human, auto = d["answer"].astype(int).tolist(), d["auto_grade"].astype(int).tolist()
        kw = kappa(human, auto, [0, 1, 2, 3], weighted=True)
        zero = d[d["auto_grade"] == "0"]
        fn = int((zero["answer"].astype(int) >= 2).sum())
        rep["A4_graded_agreement"] = {"annotator": who, "n": len(d), "weighted_kappa": kw,
                                      "confusion_human_x_auto": pd.crosstab(d["answer"], d["auto_grade"]).to_dict(orient="index"),
                                      "false_negative_rate": round(fn / len(zero), 4) if len(zero) else None,
                                      "false_negative_wilson95": wilson(fn, len(zero)),
                                      "by_stratum_mean_human": d.groupby("stratum")["answer"].apply(
                                          lambda s: round(s.astype(int).mean(), 3)).to_dict(),
                                      "exact_agreement": round(float((d["answer"] == d["auto_grade"]).mean()), 4),
                                      "large_disagreements_(|human-auto|>=2)": d[
                                          (d["answer"].astype(int) - d["auto_grade"].astype(int)).abs() >= 2]
                                      .apply(lambda r: f"{r.name}: người {r['answer']} / máy {r['auto_grade']}", axis=1).tolist(),
                                      "passed": kw >= 0.60}
        clean = d[~d["listing_id"].isin(lf_dev)]
        rep["A4_graded_agreement"]["exploratory_without_lf_dev_listings"] = {
            "n": len(clean), "weighted_kappa": kappa(clean["answer"].astype(int).tolist(),
                                                     clean["auto_grade"].astype(int).tolist(), [0, 1, 2, 3], weighted=True)}

    # A5 ward priority
    who, d = primary("H4")
    if d is not None:
        d = d[d["answer"].isin(["A", "B", "="])]
        pick = d.apply(lambda r: r[r["answer"]] if r["answer"] in ("A", "B") else "tie", axis=1)
        k, n = int((pick == "in_ward_one_off").sum()), int((pick != "tie").sum())
        share = k / n if n else float("nan")
        p = binom_greater(k, n) if n else float("nan")
        rep["A5_ward_priority"] = {"annotator": who, "pairs": len(d), "ties": int((pick == "tie").sum()),
                                   "prefer_in_ward": k, "decisive": n, "share": round(share, 4), "wilson95": wilson(k, n),
                                   "sign_test_p_one_sided": round(p, 5),
                                   "passed": n > 0 and share >= 0.70 and p < 0.05,
                                   "decision": "giữ chính sách ưu tiên phường" if (n and share >= 0.70 and p < 0.05)
                                   else "đổi chỗ mức 1 ↔ 2 cho thước đo chính, báo cáo cả hai"}
        if "in_ward_off" in d.columns:     # exploratory: which slightly-missed constraint makes people leave the ward
            by = {}
            for off, g in d.assign(pick=pick).groupby("in_ward_off"):
                kk, nn = int((g["pick"] == "in_ward_one_off").sum()), int((g["pick"] != "tie").sum())
                by[off] = f"{kk}/{nn} chọn tin trong phường"
            rep["A5_ward_priority"]["exploratory_by_in_ward_off"] = by
        keep = ~(d["A_listing"].isin(lf_dev) | d["B_listing"].isin(lf_dev))
        pk = pick[keep]
        kk, nn = int((pk == "in_ward_one_off").sum()), int((pk != "tie").sum())
        rep["A5_ward_priority"]["exploratory_without_lf_dev_listings"] = {
            "pairs": int(keep.sum()), "prefer_in_ward": kk, "decisive": nn, "share": round(kk / nn, 4) if nn else None}

    # A6 errata
    who, d = primary("H5")
    if d is not None:
        d = d[d["answer"].isin(["0", "1"])]
        k, n = int((d["answer"] == "1").sum()), len(d)
        lo, hi = wilson(k, n)
        rep["A6_price_corrections"] = {"annotator": who, "n": n, "precision": round(k / n, 4) if n else None,
                                       "wilson95": [lo, hi],
                                       "by_rule": d.groupby("rule")["answer"].apply(lambda s: f"{(s == '1').sum()}/{len(s)}").to_dict(),
                                       "wrong_items": d[d["answer"] == "0"].index.tolist(),
                                       "passed": n > 0 and k / n >= 0.95 and lo >= 0.85}

    # B2 / B3 queries
    who, d = primary("H2")
    if d is not None:
        d = d[d["answer"].isin(["0", "1"])]
        k, n = int((d["answer"] == "1").sum()), len(d)
        nat = pd.to_numeric(d["naturalness"], errors="coerce").dropna()
        rep["B2_faithfulness"] = {"annotator": who, "n": n, "faithful": round(k / n, 4) if n else None, "wilson95": wilson(k, n),
                                  "unfaithful_items": d[d["answer"] == "0"].index.tolist(), "passed": n > 0 and k / n >= 0.95}
        rep["B3_naturalness"] = {"n": int(len(nat)), "share_ge_3": round(float((nat >= 3).mean()), 4) if len(nat) else None,
                                 "mean": round(float(nat.mean()), 3) if len(nat) else None,
                                 "mean_by_style": d.assign(n=pd.to_numeric(d["naturalness"], errors="coerce"))
                                 .groupby("style")["n"].mean().round(3).to_dict(),
                                 "passed": bool(len(nat)) and float((nat >= 3).mean()) >= 0.80}

    # agreement between annotators
    agree = {}
    for task, by in answers.items():
        names = sorted(by)
        for a, b in [(names[i], names[j]) for i in range(len(names)) for j in range(i + 1, len(names))]:
            j = by[a][["answer"]].join(by[b][["answer"]], lsuffix="_a", rsuffix="_b", how="inner")
            labels = sorted(set(j["answer_a"]) | set(j["answer_b"]))
            if task == "H3":
                j = j[j["answer_a"].isin(list("0123")) & j["answer_b"].isin(list("0123"))]
                k_ = kappa(j["answer_a"].astype(int).tolist(), j["answer_b"].astype(int).tolist(), [0, 1, 2, 3], True)
            else:
                k_ = kappa(j["answer_a"].tolist(), j["answer_b"].tolist(), labels)
            agree[f"{task}:{a}~{b}"] = {"n": len(j), "kappa": k_,
                                        "raw_agreement": round(float((j["answer_a"] == j["answer_b"]).mean()), 4) if len(j) else None}
    rep["inter_annotator"] = agree

    if args.title:
        rep["title"] = args.title
    json.dump(rep, open(out / "report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    lines = ["# Kết quả kiểm định bằng người (tự sinh bởi analyze_human.py)", ""]
    if args.title:
        lines += [f"**{args.title}**", ""]
    lines += ["| Mã | Kết quả | Ngưỡng đăng ký trước | Đạt |", "|---|---|---|---|"]
    show = {"A2_aspect_precision": ("precision", "≥ 0,90 và cận dưới Wilson ≥ 0,80"),
            "A4_graded_agreement": ("weighted_kappa", "κ có trọng số ≥ 0,60"),
            "A5_ward_priority": ("share", "≥ 0,70 và p < 0,05"),
            "A6_price_corrections": ("precision", "≥ 0,95 và cận dưới Wilson ≥ 0,85"),
            "B2_faithfulness": ("faithful", "≥ 0,95"), "B3_naturalness": ("share_ge_3", "≥ 80% câu đạt ≥ 3")}
    for key, (field, rule) in show.items():
        if key in rep:
            r = rep[key]
            lines.append(f"| {key} | {r.get(field)} (n={r.get('n', r.get('decisive'))}) | {rule} | {'đạt' if r['passed'] else 'KHÔNG đạt'} |")
    for key in ("A3_aspect_misses",):
        if key in rep:
            lines.append(f"| {key} | {rep[key]['share_of_keyword_negatives_that_are_positive']} (n={rep[key]['n']}) | báo cáo | — |")
    try:
        detail = (out / "report.json").resolve().relative_to(HERE.parent)
    except ValueError:
        detail = out / "report.json"
    lines += ["", f"Chi tiết: `{detail.as_posix()}`."]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    runlog.run("analyze_human", main)
