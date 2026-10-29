"""Evaluate the RUNNING search API (POST /v1/search) on HCMRE-Q v2 — the system exactly as deployed
(LLM parser if configured, embeddings, Neo4j, ranker).

    python run_live.py --base-url http://localhost:8001 --split test --out results/live_test
    python run_live.py --base-url http://localhost:8001 --out results/live_all        # all 1,000 queries

Standard library only for the requests; numpy/pandas for the scores. Responses are cached in <out>/responses.jsonl,
so an interrupted run resumes where it stopped (use a new --out for every backend configuration). Before the run,
the backend must hold the v3.1 data (Data/v3/patches/v3_1_postgres.sql + build_search_index.py) — otherwise the
labels and the database disagree.

Replica check: when <offline dir>/runs.jsonl.gz exists, every offline system is compared ranking by ranking with
the live API (summary.json → replica_fidelity). The offline replica that corresponds to the live configuration is
prod_nodl / prod_nodl_graph / prod_dl / prod_dl_graph (semantic search off/on × Neo4j off/on); it should give the
same top-10 when the offline run uses the same data, the same vectors and the same date (eval_benchmark.py --today).
"""
from __future__ import annotations

import argparse
import gzip
import json
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

import runlog
from eval_benchmark import METRICS, apply_grade_policy, holm, metrics_for, randomization_test

HERE = Path(__file__).resolve().parent
REPLICA = {(False, False): "prod_nodl", (False, True): "prod_nodl_graph", (True, False): "prod_dl",
           (True, True): "prod_dl_graph"}       # (semantic_enabled, graph_enabled) -> offline replica
PUBLISHED_TODAY = "2026-10-28"                  # date of offline results written before --today existed


def post(url: str, payload: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8001")
    ap.add_argument("--data", default=str(HERE / "data"))
    ap.add_argument("--split", choices=["train", "val", "test", "all"], default="test")
    ap.add_argument("--top-k", type=int, default=100)
    ap.add_argument("--timeout", type=float, default=120)
    ap.add_argument("--offline", default=str(HERE / "results" / "per_query_metrics.csv"),
                    help="offline results to compare with: paired randomization test on this file, replica check "
                         "on the runs.jsonl.gz and summary.json next to it")
    ap.add_argument("--out", default=str(HERE / "results" / "live_test"))
    ap.add_argument("--grade-policy", choices=["ward_first", "near_first"], default="ward_first",
                    help="near_first swaps grades 1 and 2 (PROTOCOL §7 A5 fallback); compare only with offline "
                         "results computed under the same policy")
    args = ap.parse_args()

    data, out = Path(args.data), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    queries = [json.loads(line) for line in open(data / "queries.jsonl", encoding="utf-8")]
    if args.split != "all":
        queries = [q for q in queries if q["split"] == args.split]
    qrels = defaultdict(dict)
    for line in open(data / "qrels.tsv", encoding="utf-8"):
        qid, _, doc, g = line.split()
        qrels[qid][int(doc)] = int(g)
    qrels = apply_grade_policy(qrels, args.grade_policy)
    attrs = pd.read_csv(data / "corpus_attributes.csv", usecols=["doc_id", "ward"])
    ward_of = dict(zip(attrs["doc_id"], attrs["ward"]))

    cache_path = out / "responses.jsonl"
    done = {}
    if cache_path.exists():
        for line in open(cache_path, encoding="utf-8"):
            r = json.loads(line)
            done[r["qid"]] = r
    url = args.base_url.rstrip("/") + "/v1/search"
    todo = [q for q in queries if q["qid"] not in done]
    runlog.stage(f"POST {url}: {len(todo)} queries to send, {len(queries) - len(todo)} already in {cache_path}")
    with open(cache_path, "a", encoding="utf-8") as fh:
        for q in runlog.progress(todo, "queries", every_s=30):
            t0 = time.time()
            try:
                resp = post(url, {"query": q["text"], "top_k": args.top_k, "debug": True}, args.timeout)["data"]
            except (urllib.error.URLError, TimeoutError, KeyError) as exc:
                raise SystemExit(f"{q['qid']}: request failed ({exc}); fix the backend and run again to resume")
            rec = {"qid": q["qid"], "ranking": [int(r["listing_id"]) for r in resp["results"]],
                   "semantic_enabled": resp.get("semantic_enabled"), "graph_enabled": resp.get("graph_enabled"),
                   "total_candidates": resp.get("total_candidates"), "parsed_query": resp.get("parsed_query"),
                   "seconds": round(time.time() - t0, 3), "date": date.today().isoformat()}
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            done[q["qid"]] = rec

    runlog.stage("metrics, replica check and comparison with the offline results")
    unknown = {d for r in done.values() for d in r["ranking"]} - set(ward_of)
    if unknown:
        print(f"WARNING: {len(unknown)} returned listing_ids are not in the benchmark corpus (database ≠ Data/v3.1?)")
    sem_off = sum(1 for q in queries if not done[q["qid"]]["semantic_enabled"])
    if sem_off:
        print(f"WARNING: semantic search was OFF for {sem_off}/{len(queries)} queries (embedding coverage < 100%?)")
    configs = {(bool(done[q["qid"]]["semantic_enabled"]), bool(done[q["qid"]]["graph_enabled"])) for q in queries}
    replica = REPLICA[next(iter(configs))] if len(configs) == 1 else None
    if replica is None:
        print("WARNING: the backend configuration changed during the run (semantic/graph on for some queries only)")
    run_dates = sorted({done[q["qid"]].get("date") for q in queries} - {None})
    if len(run_dates) > 1:
        print(f"WARNING: the run spans several dates {run_dates}; freshness_score changed in between")

    rows = []
    for q in queries:
        ward = q["gold"]["location"]["value"] if q["loc_kind"] == "ward" else None
        rows.append({"system": "live", "qid": q["qid"], "split": q["split"], "family": q["family"], "style": q["style"],
                     "loc_kind": q["loc_kind"], **metrics_for(done[q["qid"]]["ranking"], qrels[q["qid"]], ward_of, ward)})
    per_q = pd.DataFrame(rows)
    per_q.to_csv(out / "per_query_metrics.csv", index=False, lineterminator="\n")
    cols = METRICS + ["wardp@10"]
    v = per_q["ndcg@10"].values
    boots = np.random.default_rng(1).choice(v, size=(10000, len(v)), replace=True).mean(axis=1)
    summary = {"queries": len(per_q), "split": args.split, "grade_policy": args.grade_policy,
               "mean": per_q[cols].mean().round(4).to_dict(),
               "ndcg_ci95": [round(float(np.percentile(boots, 2.5)), 4), round(float(np.percentile(boots, 97.5)), 4)],
               "ndcg_by_family": per_q.groupby("family")["ndcg@10"].mean().round(4).to_dict(),
               "ndcg_by_style": per_q.groupby("style")["ndcg@10"].mean().round(4).to_dict(),
               "ndcg_by_location": per_q.groupby("loc_kind")["ndcg@10"].mean().round(4).to_dict(),
               "semantic_off_queries": sem_off,
               "graph_off_queries": sum(1 for q in queries if not done[q["qid"]]["graph_enabled"]),
               "matching_offline_replica": replica, "run_dates": run_dates,
               "median_latency_s": float(np.median([done[q["qid"]]["seconds"] for q in queries]))}
    offline = Path(args.offline)
    off_summary = offline.parent / "summary.json"
    if off_summary.exists():
        meta = json.load(open(off_summary, encoding="utf-8"))
        off_policy, off_today = meta.get("grade_policy", "ward_first"), meta.get("today", PUBLISHED_TODAY)
        if off_policy != args.grade_policy:
            print(f"WARNING: offline results use grade policy {off_policy}, this run {args.grade_policy}: "
                  "the nDCG comparison below is not like for like")
        if run_dates and run_dates != [off_today]:
            print(f"NOTE: offline replicas ran with --today {off_today}, the live run on {', '.join(run_dates)}; "
                  f"for an exact replica check run eval_benchmark.py --today {run_dates[-1]}")
        summary["offline_run"] = {"path": str(offline.parent), "grade_policy": off_policy, "today": off_today}
    runs_path = offline.parent / "runs.jsonl.gz"
    if runs_path.exists():
        fid = defaultdict(lambda: [0, 0, 0.0, 0])          # identical top-10, identical top-100, overlap, queries
        wanted = {q["qid"] for q in queries}
        with gzip.open(runs_path, "rt", encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                if r["system"] in ("random", "oracle_constraints") or r["qid"] not in wanted:
                    continue
                a, b, f = done[r["qid"]]["ranking"], r["ranking"], fid[r["system"]]
                f[0] += a[:10] == b[:10]
                f[1] += a[:100] == b[:100]
                f[2] += len(set(a[:10]) & set(b[:10])) / max(1, min(10, max(len(a), len(b))))
                f[3] += 1
        summary["replica_fidelity"] = {s: {"queries": n, "top10_identical": t10, "top100_identical": t100,
                                           "mean_top10_overlap": round(ov / n, 4)}
                                       for s, (t10, t100, ov, n) in sorted(fid.items())}
        if replica in fid:
            t10, n = fid[replica][0], fid[replica][3]
            print(f"replica check: the live configuration corresponds to {replica}; identical top-10 on {t10}/{n} queries")
            if t10 < 0.95 * n:
                print("  differences usually come from: another date (--today), a database that is not v3.1, other "
                      "vectors (embed_benchmark.py --doc-vectors-from-db), or ties in the candidate order "
                      "(created_at without embeddings, posted_date in Neo4j) — see README")
        elif replica:
            print(f"NOTE: {replica} is not in {runs_path}; run embed_benchmark.py and eval_benchmark.py "
                  "--embedding-tag ... --out <dir> and pass --offline <dir>/per_query_metrics.csv for the replica check")
    if offline.exists():
        off = pd.read_csv(offline)
        off = off[off["qid"].isin(per_q["qid"])]
        live = per_q.set_index("qid")["ndcg@10"]
        rng, pvals, means = np.random.default_rng(7), {}, {}
        for system, g in off.groupby("system"):
            if system in ("random", "oracle_constraints"):
                continue
            other = g.set_index("qid")["ndcg@10"].reindex(live.index).values
            means[system] = round(float(other.mean()), 4)
            pvals[system] = randomization_test(live.values, other, rng)
        summary["vs_offline"] = {"live": round(float(live.mean()), 4), "offline_means": means,
                                 "p_holm": {k: round(p, 5) for k, p in holm(pvals).items()}}
    json.dump(summary, open(out / "summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    runlog.run("run_live", main)
