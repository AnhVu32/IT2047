"""Run the search systems on HCMRE-Q v2, compute the metrics and the reliability checks D1–D5 (PROTOCOL.md §6–7).

    python eval_benchmark.py --data data --snapshot snapshot --out results [--embedding-tag qwen3-embedding-4b]
    python eval_benchmark.py --grade-policy near_first --out results_near_first    # PROTOCOL §7 A5 fallback

Grade policy: ward_first (default, the pre-registered primary metric) uses qrels.tsv as published;
near_first swaps grades 1 and 2 — the rule PROTOCOL §7 prescribes for the primary metric if check A5 fails.

Date: the ranker's freshness_score depends on today's date, so the replicas run with a frozen date (--today,
default 2026-10-28 = the published results). To compare with a live run (run_live.py), pass the date of that run
(the backend container runs on Asia/Ho_Chi_Minh time):
    python eval_benchmark.py --embedding-tag qwen3-embedding-4b --today 2026-11-05 --out results_dl_1105

Systems (offline; the backend code is imported, not re-written, for the production replicas)
  random            uniform random ranking (mean of 5 permutations)
  bm25 / bm25_noaccent   Okapi BM25 on search_text, with / without diacritics
  tfidf_char        cosine on character 3–5-gram TF-IDF, no diacritics (needs scikit-learn)
  pg_fts            production lexical score only (snapshot/fts_scores.csv), newest first on ties
  prod_nodl         production pipeline without embeddings: RuleBasedQueryParser -> top-500 by FTS score
                    (newest first) -> ranker.rank_candidates -> diversify (LLM parser off)
  prod_nodl_graph   + Neo4j candidates and graph_score, replicated from Data/v3/graph
  bm25_rule         BM25-noaccent top-500 candidates + the same production ranker
  oracle_constraints  diagnostic upper bound: knows the gold constraints, ranks by a simple satisfaction score
  with query/document embeddings (embed_benchmark.py): dense, prod_dl, prod_dl_graph, rrf_bm25_dense

Metrics: nDCG@10 (gain 2^g − 1, g ∈ 0..3); P@10, MRR@10, Success@10, Recall@100 on grade-3 listings;
WardP@10 on ward queries. Outputs: results/summary.json, per_query_metrics.csv, reliability.json, runs.jsonl.gz.
"""
from __future__ import annotations

import argparse
import gzip
import itertools
import json
import math
import os
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.stats import kendalltau

import build_benchmark as B
import corpus as C
import runlog

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
K_CANDIDATES = 500
TODAY = date(2026, 10, 28)          # frozen so freshness_score is reproducible (--today overrides it)
METRICS = ["ndcg@10", "p@10", "mrr@10", "success@10", "recall@100"]


# =========================================================================== data
def load(data: Path, snap: Path, tag: str | None):
    queries = [json.loads(line) for line in open(data / "queries.jsonl", encoding="utf-8")]
    qrels = defaultdict(dict)
    for line in open(data / "qrels.tsv", encoding="utf-8"):
        qid, _, doc, g = line.split()
        qrels[qid][int(doc)] = int(g)
    attrs = pd.read_csv(data / "corpus_attributes.csv", low_memory=False)
    props = pd.read_csv(snap / "properties.csv.gz", low_memory=False, keep_default_na=False, na_values=[""])
    props = props.sort_values("doc_id").reset_index(drop=True)
    assert (props["doc_id"].values == attrs.sort_values("doc_id")["doc_id"].values).all()
    evidence = pd.read_csv(snap / "amenity_evidence.csv.gz", dtype={"listing_id": str})
    fts = pd.read_csv(snap / "fts_scores.csv")
    q_emb = d_emb = None
    if tag and (snap / f"query_embeddings_{tag}.npy").exists():
        q_emb = np.load(snap / f"query_embeddings_{tag}.npy").astype(np.float32)
        d_emb = np.load(snap / f"doc_embeddings_{tag}.npy").astype(np.float32)
        meta = json.load(open(snap / f"embeddings_{tag}.json", encoding="utf-8"))
        assert meta["qids"] == [q["qid"] for q in queries] and meta["doc_ids"] == props["doc_id"].tolist()
    return queries, qrels, attrs, props, evidence, fts, q_emb, d_emb


def apply_grade_policy(qrels: dict, policy: str) -> dict:
    """ward_first: qrels as published. near_first: grade 1 (near the area, every constraint met) and grade 2 (in the
    area, one constraint slightly off) trade places — the fallback of PROTOCOL §7 A5."""
    if policy == "ward_first":
        return qrels
    if policy != "near_first":
        raise ValueError(policy)
    out = defaultdict(dict)
    for q, rel in qrels.items():
        out[q] = {d: (2 if g == 1 else 1 if g == 2 else g) for d, g in rel.items()}
    return out


# =========================================================================== metrics
def metrics_for(ranked: list[int], rel: dict[int, int], ward_of: dict | None = None, ward: str | None = None) -> dict:
    gains = [rel.get(d, 0) for d in ranked]
    dcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(gains[:10]))
    ideal = sorted(rel.values(), reverse=True)
    idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal[:10]))
    exact = {d for d, g in rel.items() if g == 3}
    first = next((i for i, g in enumerate(gains[:10]) if g == 3), None)
    out = {"ndcg@10": dcg / idcg if idcg > 0 else 0.0,
           "p@10": sum(1 for g in gains[:10] if g == 3) / 10,
           "mrr@10": 1.0 / (first + 1) if first is not None else 0.0,
           "success@10": 1.0 if first is not None else 0.0,
           "recall@100": len(exact & set(ranked[:100])) / len(exact) if exact else 0.0}
    if ward is not None:
        top = ranked[:10]
        out["wardp@10"] = sum(1 for d in top if ward_of.get(d) == ward) / 10
    return out


# =========================================================================== lexical baselines
TOKEN = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str, accents: bool) -> list[str]:
    text = (text or "").lower()
    return TOKEN.findall(text if accents else C.strip_accents(text).lower())


class BM25:
    def __init__(self, docs: list[str], accents: bool, k1: float = 1.2, b: float = 0.75):
        self.accents = accents
        toks = [tokenize(d, accents) for d in docs]
        vocab, rows, cols, vals = {}, [], [], []
        for i, t in enumerate(toks):
            counts = defaultdict(int)
            for w in t:
                counts[w] += 1
            for w, c in counts.items():
                rows.append(i)
                cols.append(vocab.setdefault(w, len(vocab)))
                vals.append(c)
        tf = sparse.coo_matrix((vals, (rows, cols)), shape=(len(docs), len(vocab)), dtype=np.float32)
        dl = np.array([len(t) for t in toks], dtype=np.float32)
        df = np.bincount(cols, minlength=len(vocab))
        self.idf = np.log(1 + (len(docs) - df + 0.5) / (df + 0.5)).astype(np.float32)
        w = tf.data * (k1 + 1) / (tf.data + k1 * (1 - b + b * dl[tf.row] / dl.mean()))
        self.mat = sparse.csc_matrix((w, (tf.row, tf.col)), shape=tf.shape)
        self.vocab = vocab

    def scores(self, query: str) -> np.ndarray:
        ids = [self.vocab[w] for w in set(tokenize(query, self.accents)) if w in self.vocab]
        if not ids:
            return np.zeros(self.mat.shape[0], dtype=np.float32)
        return np.asarray(self.mat[:, ids] @ self.idf[ids]).ravel()


class CharTfidf:
    def __init__(self, docs: list[str]):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True,
                                   preprocessor=lambda t: C.strip_accents(t or "").lower())
        self.mat = self.vec.fit_transform(docs)

    def scores(self, query: str) -> np.ndarray:
        return np.asarray((self.mat @ self.vec.transform([query]).T).todense()).ravel()


def rank_by(scores: np.ndarray, doc_ids: np.ndarray, tiebreak: np.ndarray | None = None, k: int = 100) -> list[int]:
    order = np.argsort(-scores, kind="stable") if tiebreak is None else np.lexsort((-tiebreak, -scores))
    return [int(doc_ids[i]) for i in order[:k]]


# =========================================================================== oracle (diagnostic)
def oracle_constraints(attrs: pd.DataFrame, gold: dict, loc: C.Locator) -> list[int]:
    """Knows the constraints; ranks by (hard ok, location, #soft satisfied, closeness). Not the grade function."""
    hard = B.hard_ok(attrs, gold).astype(int)
    soft = B.soft_constraints(attrs, gold)
    n_ok = sum(ok.astype(int) for ok, _ in soft) if soft else np.zeros(len(attrs), dtype=int)
    n_band = sum(band.astype(int) for _, band in soft) if soft else np.zeros(len(attrs), dtype=int)
    if gold.get("location"):
        kind, values = C.location_values(gold["location"])
        inside, near = loc.masks(kind, values)
        place = 2 * inside.astype(int) + near.astype(int)
    else:
        place = np.zeros(len(attrs), dtype=int)
    price_dev = np.zeros(len(attrs))
    if gold.get("price"):
        gp, p = gold["price"], attrs["price"].values
        ref = gp.get("target", gp.get("max"))
        price_dev = np.nan_to_num(np.abs(p - ref) / ref, nan=9.0)
    order = np.lexsort((attrs["doc_id"].values, price_dev, -n_band, -n_ok, -place, -hard))
    return [int(attrs["doc_id"].values[i]) for i in order[:100]]


# =========================================================================== production replica
def _f(v):
    try:
        if v is None or v == "" or (isinstance(v, float) and math.isnan(v)):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


class Production:
    def __init__(self, props: pd.DataFrame, evidence: pd.DataFrame):
        sys.path.insert(0, str(REPO / "backend"))
        from src.search import ranker  # noqa: E402
        from src.search.graph_repository import GRAPH_FEATURE_CATEGORIES, Neo4jGraphRepository  # noqa: E402
        from src.search.normalizer import FEATURE_ALIASES  # noqa: E402
        from src.search.query_parser import RuleBasedQueryParser  # noqa: E402

        class _FrozenDate(date):
            @classmethod
            def today(cls):
                return TODAY

        ranker.date = _FrozenDate
        self.ranker, self.parser = ranker, RuleBasedQueryParser()
        self.score_graph_record = Neo4jGraphRepository._score_record
        self.graph_feature_categories, self.feature_aliases = GRAPH_FEATURE_CATEGORIES, FEATURE_ALIASES
        self.doc_ids = props["doc_id"].values
        self.created = props["created_rank"].values
        ev = defaultdict(list)
        for r in evidence.to_dict("records"):
            ev[str(r["listing_id"])].append({"category": r["category"], "name": r["amenity_name"],
                                             "driving_distance_km": _f(r["driving_distance_km"]),
                                             "driving_duration_min": _f(r["driving_duration_min"]),
                                             "threshold_km": _f(r["threshold_km"])})
        self.items = []
        for r in props.to_dict("records"):
            item = {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in r.items()}
            item["id"] = int(r["doc_id"])
            for k in ("price_range", "area", "area_price_history", "frontage", "access_road", "coordinate_confidence"):
                item[k] = _f(item.get(k))
            for k in ("bedrooms", "bathrooms"):
                v = _f(item.get(k))
                item[k] = None if v is None else int(v)
            item["listing_id"] = int(item["listing_id"])
            item["amenity_evidence"] = ev.get(str(item["listing_id"]), [])
            self.items.append(item)
        self._graph_index()

    def _graph_index(self):
        g = REPO / "Data" / "v3" / "graph"
        rd = lambda name: pd.read_csv(g / name, low_memory=False, encoding="utf-8-sig")
        nodes = rd("neo4j_listing_nodes.csv")
        nodes.columns = [c.split(":")[0] for c in nodes.columns]
        wards = rd("neo4j_ward_nodes.csv")
        wards.columns = [c.split(":")[0] for c in wards.columns]
        former = rd("neo4j_former_admin_area_nodes.csv")
        former.columns = [c.split(":")[0] for c in former.columns]
        in_ward = rd("neo4j_listing_in_ward_relationships.csv")
        in_ward.columns = ["listing_node_id", "ward_id", "type"]
        in_former = rd("neo4j_listing_in_former_area_relationships.csv")
        in_former.columns = ["listing_node_id", "former_area_id", "type"]
        near = rd("neo4j_listing_near_amenity_relationships.csv")
        near = near.rename(columns={near.columns[0]: "listing_node_id", near.columns[1]: "amenity_id"})
        near.columns = [c.split(":")[0] if c.split(":")[0] else c for c in near.columns]
        amen = rd("neo4j_amenity_nodes.csv")
        amen.columns = [c.split(":")[0] for c in amen.columns]
        amen_name = dict(zip(amen["amenity_id"], amen["name"]))
        ward_name = dict(zip(wards["ward_id"], wards["name"]))
        former_name = dict(zip(former["former_area_id"], former["name"]))
        self.node_wards = in_ward.groupby("listing_node_id")["ward_id"].apply(lambda s: [ward_name[x] for x in s]).to_dict()
        self.node_former = in_former.groupby("listing_node_id")["former_area_id"].apply(
            lambda s: [former_name[x] for x in s]).to_dict()
        self.node_amen = defaultdict(list)
        for r in near.to_dict("records"):
            self.node_amen[r["listing_node_id"]].append({
                "category": r["category"], "name": amen_name.get(r["amenity_id"]),
                "driving_distance_km": _f(r.get("driving_distance_km")),
                "driving_duration_min": _f(r.get("driving_duration_min")), "threshold_km": _f(r.get("threshold_km"))})
        nodes["posted_date"] = pd.to_datetime(nodes["posted_date"])
        nodes["import_order"] = np.arange(len(nodes))      # Cypher ORDER BY posted_date DESC; ties: import order
        self.graph_nodes = nodes.sort_values(["posted_date", "import_order"], ascending=[False, True]).head(K_CANDIDATES)
        flags = [f for f in self.feature_aliases if f not in self.graph_feature_categories and f in nodes.columns]
        self.node_flags = {r["listing_node_id"]: {f: str(r[f]).lower() == "true" for f in flags}
                           for r in nodes[["listing_node_id", *flags]].to_dict("records")}
        self.pos = {int(d): i for i, d in enumerate(self.doc_ids)}

    def graph_candidates(self, parsed) -> dict:
        requested = {*parsed.hard_filters.required_features, *parsed.preference_filters.required_features,
                     *(p.value for p in parsed.soft_preferences if p.type == "feature" and p.value)}
        pref_features = sorted(requested & (set(self.feature_aliases) - set(self.graph_feature_categories)))
        cats = {a.amenity_category for a in parsed.amenity_filters}
        for feature in requested:
            cats.update(self.graph_feature_categories.get(feature, set()))
        out = {}
        for r in self.graph_nodes.to_dict("records"):
            nid = r["listing_node_id"]
            record = {"listing_id": str(r["listing_id"]), "listing_node_id": nid, "wards": self.node_wards.get(nid, []),
                      "amenities": [a for a in self.node_amen.get(nid, []) if not cats or a["category"] in cats],
                      "matched_features": [f for f in pref_features if self.node_flags.get(nid, {}).get(f)],
                      "former_admin_area": (self.node_former.get(nid) or [r.get("former_admin_area")])[0],
                      "geo_cluster_150m": r.get("geo_cluster_150m")}
            scored = self.score_graph_record(record, parsed)
            if scored["listing_id"] not in out or scored["graph_score"] > out[scored["listing_id"]]["graph_score"]:
                out[scored["listing_id"]] = scored
        return out

    def rank(self, query: str, text_scores: np.ndarray, semantic: np.ndarray | None, use_graph: bool,
             order_scores: np.ndarray | None = None, top_k: int = 100):
        parsed = self.parser.parse(query, top_k=min(top_k, 100))
        o = text_scores if order_scores is None else order_scores
        order = np.lexsort((-o, -semantic)) if semantic is not None else np.lexsort((-self.created, -o))
        cand = list(order[:K_CANDIDATES])
        graph_map = self.graph_candidates(parsed) if use_graph else {}
        if graph_map:
            have = set(cand)
            cand += [self.pos[int(lid)] for lid in graph_map if self.pos[int(lid)] not in have]
        items = []
        for i in cand:
            item = dict(self.items[i])
            item["text_score"] = float(text_scores[i])
            item["semantic_score"] = float(semantic[i]) if semantic is not None else 0.0
            g = graph_map.get(str(item["listing_id"]))
            item["graph_score"] = g["graph_score"] if g else 0.5
            items.append(item)
        ranked = self.ranker.rank_candidates(items, parsed, None)
        return [int(it["id"]) for it in self.ranker.diversify(ranked, top_k)[:top_k]], parsed


# =========================================================================== reliability (D1–D5)
def system_means(runs, qrels_by, qids, systems, ward_of, wards) -> dict:
    out = {}
    for s in systems:
        vals = []
        for q in qids:
            r = runs[s][q]
            if s == "random":
                vals.append(np.mean([metrics_for(x, qrels_by[q])["ndcg@10"] for x in r]))
            else:
                vals.append(metrics_for(r, qrels_by[q])["ndcg@10"])
        out[s] = np.array(vals)
    return out


def tau(a: dict, b: dict) -> float:
    keys = sorted(a)
    return float(kendalltau([a[k] for k in keys], [b[k] for k in keys]).statistic)


def randomization_test(x: np.ndarray, y: np.ndarray, rng, n: int = 10000) -> float:
    d = x - y
    obs = abs(d.mean())
    signs = rng.choice([-1.0, 1.0], size=(n, len(d)))
    return float(((np.abs((signs * d).mean(axis=1)) >= obs - 1e-12).sum() + 1) / (n + 1))


def holm(pvals: dict) -> dict:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m, out, running = len(items), {}, 0.0
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        out[k] = running
    return out


def reliability(runs, queries, qrels, attrs, systems, out_dir: Path, policy: str = "ward_first") -> dict:
    rng = np.random.default_rng(20261028)
    test = [q for q in queries if q["split"] == "test"]
    qids = [q["qid"] for q in test]
    ward_of = dict(zip(attrs["doc_id"], attrs["ward"]))
    per = system_means(runs, qrels, qids, systems, ward_of, None)
    means = {s: float(v.mean()) for s, v in per.items()}
    runlog.stage("reliability D1 sanity")
    rep = {"test_ndcg_means": {s: round(m, 4) for s, m in sorted(means.items(), key=lambda kv: -kv[1])}}

    # D1 sanity
    non_oracle = {s: m for s, m in means.items() if s not in ("oracle_constraints", "random")}
    best = max(non_oracle, key=non_oracle.get)
    rep["D1_sanity"] = {"oracle": round(means["oracle_constraints"], 4), "random": round(means["random"], 4),
                        "best_system": best, "best": round(means[best], 4),
                        "passed": means["oracle_constraints"] >= 0.90 and means["random"] <= 0.05
                        and means["oracle_constraints"] > means[best] > means["random"]}

    # D2 discriminative power (all pairs of real systems: oracle and random excluded)
    runlog.stage("reliability D2 discriminative power (paired randomization, 10,000 permutations per pair)")
    real = [s for s in systems if s not in ("oracle_constraints", "random")]
    pvals = {f"{a}|{b}": randomization_test(per[a], per[b], rng) for a, b in itertools.combinations(real, 2)}
    adj = holm(pvals)
    rep["D2_discriminative_power"] = {"pairs": len(pvals), "significant_holm_0.05": sum(p < 0.05 for p in adj.values()),
                                      "share": round(sum(p < 0.05 for p in adj.values()) / max(1, len(adj)), 4),
                                      "p_holm": {k: round(v, 5) for k, v in sorted(adj.items())}}

    # D3 split-half stability
    taus = []
    idx = np.arange(len(qids))
    runlog.stage("reliability D3 split-half stability (1,000 splits)")
    for _ in runlog.progress(range(1000), "D3 splits"):
        perm = rng.permutation(idx)
        h1, h2 = perm[: len(idx) // 2], perm[len(idx) // 2:]
        taus.append(tau({s: per[s][h1].mean() for s in real}, {s: per[s][h2].mean() for s in real}))
    rep["D3_split_half"] = {"mean_tau": round(float(np.nanmean(taus)), 4), "p05_tau": round(float(np.nanpercentile(taus, 5)), 4),
                            "passed": float(np.nanmean(taus)) >= 0.80}

    # D4 label noise: 10% of non-zero labels shifted by ±1
    base = {s: means[s] for s in real}
    noisy_taus = []
    runlog.stage("reliability D4 label noise (200 repetitions)")
    for _ in runlog.progress(range(200), "D4 repetitions"):
        noisy = {}
        for q in qids:
            rel = dict(qrels[q])
            for d in list(rel):
                if rng.random() < 0.10:
                    rel[d] = int(min(3, max(0, rel[d] + rng.choice([-1, 1]))))
            noisy[q] = rel
        m = system_means(runs, noisy, qids, real, ward_of, None)
        noisy_taus.append(tau(base, {s: float(v.mean()) for s, v in m.items()}))
    rep["D4_label_noise"] = {"mean_tau": round(float(np.mean(noisy_taus)), 4), "min_tau": round(float(np.min(noisy_taus)), 4),
                             "passed": float(np.mean(noisy_taus)) >= 0.80}

    # D5 parameter sensitivity (re-grade the test queries)
    loc = C.Locator(attrs.drop(columns=[c for c in attrs.columns if c == "seed_split"]))
    doc_ids = attrs["doc_id"].values
    outlier = attrs["ward_coord_outlier"].values.astype(bool)
    variants = {"near_0.5km": dict(near_km=0.5), "near_1.5km": dict(near_km=1.5), "tolerance_x0.5": dict(tol_scale=0.5),
                "tolerance_x1.5": dict(tol_scale=1.5), "swap_grades_1_2": "swap", "drop_ward_coord_outliers": "drop"}
    rep["D5_sensitivity"] = {}
    for name, kw in variants.items():
        runlog.stage(f"reliability D5 sensitivity: {name}")
        alt = {}
        for q in test:
            if kw == "drop":
                g = B.grades(attrs, q["gold"], loc, exclude=outlier)
            elif kw == "swap":
                g = B.grades(attrs, q["gold"], loc)
            else:
                g = B.grades(attrs, q["gold"], loc, **kw)
            # variants are expressed relative to the grade policy in use; "swap" moves to the other policy
            if (kw == "swap") != (policy == "near_first"):
                g = np.where(g == 1, 2, np.where(g == 2, 1, g))
            alt[q["qid"]] = {int(d): int(x) for d, x in zip(doc_ids, g) if x > 0}
        m = system_means(runs, alt, qids, real, ward_of, None)
        rep["D5_sensitivity"][name] = {"tau": round(tau(base, {s: float(v.mean()) for s, v in m.items()}), 4),
                                       "means": {s: round(float(v.mean()), 4) for s, v in m.items()}}
    json.dump(rep, open(out_dir / "reliability.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return rep


# =========================================================================== main
def evaluate(args):
    global TODAY
    TODAY = date.fromisoformat(args.today)      # read by _FrozenDate.today() inside the imported ranker
    data, snap, out = Path(args.data), Path(args.snapshot), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    runlog.stage(f"load data ({data}), snapshot ({snap}), embedding tag {args.embedding_tag}; today = {TODAY}")
    queries, qrels, attrs, props, evidence, fts, q_emb, d_emb = load(data, snap, args.embedding_tag)
    qrels = apply_grade_policy(qrels, args.grade_policy)
    attrs = attrs.sort_values("doc_id").reset_index(drop=True)
    doc_ids = props["doc_id"].values
    idx_of = {int(d): i for i, d in enumerate(doc_ids)}
    created = props["created_rank"].values
    texts = props["search_text"].fillna("").tolist()
    ward_of = dict(zip(attrs["doc_id"], attrs["ward"]))
    fts_by_q = defaultdict(dict)
    for r in fts.itertuples(index=False):
        fts_by_q[r.qid][int(r.doc_id)] = float(r.text_score)
    print(f"queries={len(queries)} docs={len(doc_ids)} dense={'yes' if q_emb is not None else 'no'}")

    runlog.stage("build indexes (BM25, TF-IDF) and the production replica")
    bm25, bm25_na = BM25(texts, True), BM25(texts, False)
    try:
        tfidf = CharTfidf(texts)
    except ImportError:
        tfidf = None
        print("scikit-learn not installed: tfidf_char skipped")
    prod = Production(props, evidence)
    loc = C.Locator(attrs)
    runs = defaultdict(dict)
    rng = np.random.default_rng(0)
    runlog.stage(f"run {'13' if q_emb is not None else '9'} systems on {len(queries)} queries")
    for qi, q in enumerate(runlog.progress(queries, "queries")):
        qid, text = q["qid"], q["text"]
        ts = np.zeros(len(doc_ids), dtype=np.float32)
        for d, s in fts_by_q.get(qid, {}).items():
            ts[idx_of[d]] = s
        runs["random"][qid] = [[int(doc_ids[i]) for i in rng.permutation(len(doc_ids))[:100]] for _ in range(5)]
        s_bm, s_na = bm25.scores(text), bm25_na.scores(text)
        runs["bm25"][qid] = rank_by(s_bm, doc_ids)
        runs["bm25_noaccent"][qid] = rank_by(s_na, doc_ids)
        if tfidf is not None:
            runs["tfidf_char"][qid] = rank_by(tfidf.scores(text), doc_ids)
        runs["pg_fts"][qid] = rank_by(ts, doc_ids, tiebreak=created)
        runs["prod_nodl"][qid] = prod.rank(text, ts, None, use_graph=False)[0]
        runs["prod_nodl_graph"][qid] = prod.rank(text, ts, None, use_graph=True)[0]
        norm_na = (s_na / s_na.max() if s_na.max() > 0 else s_na).astype(np.float32)
        runs["bm25_rule"][qid] = prod.rank(text, norm_na, None, use_graph=False)[0]
        runs["oracle_constraints"][qid] = oracle_constraints(attrs, q["gold"], loc)
        if q_emb is not None:
            sem = d_emb @ q_emb[qi]
            runs["dense"][qid] = rank_by(sem, doc_ids)
            runs["prod_dl"][qid] = prod.rank(text, ts, sem, use_graph=False)[0]
            runs["prod_dl_graph"][qid] = prod.rank(text, ts, sem, use_graph=True)[0]
            fused = defaultdict(float)
            for lst in (runs["bm25_noaccent"][qid], rank_by(sem, doc_ids, k=1000)):
                for r, d in enumerate(lst):
                    fused[d] += 1.0 / (60 + r + 1)
            runs["rrf_bm25_dense"][qid] = [d for d, _ in sorted(fused.items(), key=lambda x: (-x[1], x[0]))[:100]]

    runlog.stage("metrics per query, runs.jsonl.gz, summary")
    rows = []
    for system, by_q in runs.items():
        for q in queries:
            ward = q["gold"]["location"]["value"] if q["loc_kind"] == "ward" else None
            if system == "random":
                ms = [metrics_for(r, qrels[q["qid"]], ward_of, ward) for r in by_q[q["qid"]]]
                m = {k: float(np.mean([x[k] for x in ms])) for k in ms[0]}
            else:
                m = metrics_for(by_q[q["qid"]], qrels[q["qid"]], ward_of, ward)
            rows.append({"system": system, "qid": q["qid"], "split": q["split"], "family": q["family"],
                         "style": q["style"], "loc_kind": q["loc_kind"], **m})
    per_query = pd.DataFrame(rows)
    per_query.to_csv(out / "per_query_metrics.csv", index=False, lineterminator="\n")
    with gzip.GzipFile(out / "runs.jsonl.gz", "wb", mtime=0) as fh:       # mtime=0: same bytes on every run
        for system, by_q in runs.items():
            for qid, r in by_q.items():
                line = json.dumps({"system": system, "qid": qid, "ranking": r[0] if system == "random" else r}) + "\n"
                fh.write(line.encode("utf-8"))

    cols = METRICS + ["wardp@10"]
    summary = {"systems": sorted(runs), "dense_available": q_emb is not None, "grade_policy": args.grade_policy,
               "today": TODAY.isoformat()}
    for split in ("test", "val", "train", "all"):
        sub = per_query if split == "all" else per_query[per_query["split"] == split]
        summary[split] = sub.groupby("system")[cols].mean().round(4).to_dict(orient="index")
    test = per_query[per_query["split"] == "test"]
    for col in ("family", "style", "loc_kind"):
        summary[f"test_ndcg_by_{col}"] = test.pivot_table(index="system", columns=col, values="ndcg@10").round(4).to_dict(orient="index")
    ci, brng = {}, np.random.default_rng(1)
    for system in sorted(test["system"].unique()):
        v = test[test["system"] == system].sort_values("qid")["ndcg@10"].values
        boots = brng.choice(v, size=(10000, len(v)), replace=True).mean(axis=1)
        ci[system] = [round(float(np.percentile(boots, 2.5)), 4), round(float(np.percentile(boots, 97.5)), 4)]
    summary["test_ndcg_ci95"] = ci
    summary["fts_queries_with_any_match"] = int(sum(1 for q in queries if fts_by_q.get(q["qid"])))
    systems = [s for s in sorted(runs)]
    summary["reliability"] = reliability(runs, queries, qrels, attrs, systems, out, args.grade_policy)
    json.dump(summary, open(out / "summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    runlog.stage(f"done: results in {out}")
    print(json.dumps(summary["test"], indent=1))
    print(json.dumps({k: v for k, v in summary["reliability"].items() if k != "D2_discriminative_power"}, indent=1)[:3000])
    return summary


if __name__ == "__main__":
    # The order of ties deep in a ranking (bm25_rule, rank > 50) was observed to change with the string-hash seed,
    # probably through set iteration in the imported backend code. The metrics do not change, but runs.jsonl.gz does.
    # Run under a fixed seed so that every output file is identical from run to run.
    if os.environ.get("PYTHONHASHSEED") != "0":
        os.environ["PYTHONHASHSEED"] = "0"
        os.execv(sys.executable, [sys.executable, *sys.argv])
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--snapshot", default="snapshot")
    ap.add_argument("--out", default="results")
    ap.add_argument("--embedding-tag", default=None, help="tag written by embed_benchmark.py, e.g. qwen3-embedding-4b")
    ap.add_argument("--grade-policy", choices=["ward_first", "near_first"], default="ward_first",
                    help="near_first swaps grades 1 and 2 (PROTOCOL §7: the primary metric if check A5 fails)")
    ap.add_argument("--today", default=TODAY.isoformat(),
                    help="YYYY-MM-DD seen by the ranker's freshness_score; the date of a live run to compare with it")
    args = ap.parse_args()
    runlog.run("eval_benchmark", lambda: evaluate(args))
