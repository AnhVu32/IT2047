"""Evaluate retrieval systems on the HCMRE-Q benchmark.

Systems
  random          uniform random ranking (lower bound, mean of 5 seeds)
  bm25            Okapi BM25 on the production search_text (diacritic-sensitive)
  bm25_noaccent   same, both sides accent-stripped (diacritic-insensitive)
  pg_fts          production lexical score only: ts_rank_cd('simple', plainto_tsquery)
  prod_nodl       production pipeline WITHOUT deep learning (embedding API off):
                  RuleBasedQueryParser -> top-500 FTS candidates -> ranker.rank_candidates
                  -> diversify (3 per 150 m cluster)   [backend code imported, not re-written]
  prod_nodl_graph same + Neo4j candidates/graph_score replicated from the V2 graph package
  bm25_rule       traditional hybrid: BM25-noaccent candidates (top-500) + the same
                  production ranker, BM25 (min-max per query) used as the text signal
  --- requires query embeddings (embed_queries.py, run where the embedding API lives) ---
  dense           cosine(query, listing) with the production document vectors
  prod_dl         full production pipeline: semantic_score from embeddings (+FTS, rules)
  prod_dl_graph   full production pipeline + Neo4j
  rrf_bm25_dense  reciprocal-rank fusion of bm25_noaccent and dense (k=60)

Metrics (graded qrels: 2 exact, 1 partial): nDCG@10 (gain 2^g-1), P@10, MRR@10,
Success@10 and Recall@100 (binary metrics count grade-2 docs only).
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

import corpus as C

K_CANDIDATES = 500
TODAY = date(2026, 10, 10)  # frozen so freshness_score is reproducible


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
def load_benchmark(bench: Path):
    queries = [json.loads(line) for line in open(bench / "queries.jsonl", encoding="utf-8")]
    qrels = defaultdict(dict)
    for line in open(bench / "qrels.tsv", encoding="utf-8"):
        qid, _, doc_id, grade = line.split()
        qrels[qid][int(doc_id)] = int(grade)
    return queries, qrels


def load_snapshot(snap: Path, tag: str):
    props = pd.read_csv(snap / "properties_snapshot.csv.gz", low_memory=False)
    props = props.sort_values("id").reset_index(drop=True)
    lad = pd.read_csv(snap / "listing_amenity_distances.csv.gz", low_memory=False)
    fts = pd.read_csv(snap / "fts_scores.csv")
    # document vectors: re-encoded corpus for this model if present, else the vectors
    # stored in the PostgreSQL backup (text-embedding-qwen3-embedding-0.6b)
    emb_path = snap / f"doc_embeddings_{tag}.npy"
    if not emb_path.exists() and tag == "qwen3-embedding-0.6b":
        emb_path = snap / "qwen3_0.6b_doc_embeddings.npy"
    doc_emb = np.load(emb_path).astype(np.float32) if emb_path.exists() else None
    return props, lad, fts, doc_emb


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------
def metrics_for(ranked: list[int], rel: dict[int, int], k: int = 10) -> dict:
    gains = [rel.get(d, 0) for d in ranked]
    dcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(gains[:k]))
    ideal = sorted(rel.values(), reverse=True)
    idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal[:k]))
    exact = {d for d, g in rel.items() if g == 2}
    first = next((i for i, g in enumerate(gains[:k]) if g == 2), None)
    return {
        "ndcg@10": dcg / idcg if idcg > 0 else 0.0,
        "p@10": sum(1 for g in gains[:k] if g == 2) / k,
        "mrr@10": 1.0 / (first + 1) if first is not None else 0.0,
        "success@10": 1.0 if first is not None else 0.0,
        "recall@100": len(exact & set(ranked[:100])) / len(exact) if exact else 0.0,
    }


# ---------------------------------------------------------------------------
# lexical baselines
# ---------------------------------------------------------------------------
TOKEN = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str, accents: bool) -> list[str]:
    text = (text or "").lower()
    if not accents:
        text = C.strip_accents(text).lower()
    return TOKEN.findall(text)


class BM25:
    def __init__(self, docs: list[str], accents: bool, k1: float = 1.2, b: float = 0.75):
        self.accents = accents
        toks = [tokenize(d, accents) for d in docs]
        vocab = {}
        rows, cols, vals = [], [], []
        for i, t in enumerate(toks):
            counts = defaultdict(int)
            for w in t:
                counts[w] += 1
            for w, c in counts.items():
                j = vocab.setdefault(w, len(vocab))
                rows.append(i)
                cols.append(j)
                vals.append(c)
        tf = sparse.csr_matrix((vals, (rows, cols)), shape=(len(docs), len(vocab)), dtype=np.float32)
        dl = np.array([len(t) for t in toks], dtype=np.float32)
        avgdl = dl.mean()
        df = np.bincount(cols, minlength=len(vocab))
        n = len(docs)
        self.idf = np.log(1 + (n - df + 0.5) / (df + 0.5)).astype(np.float32)
        tf = tf.tocoo()
        denom = tf.data + k1 * (1 - b + b * dl[tf.row] / avgdl)
        w = tf.data * (k1 + 1) / denom
        self.mat = sparse.csc_matrix((w, (tf.row, tf.col)), shape=(n, len(vocab)))
        self.vocab = vocab

    def scores(self, query: str) -> np.ndarray:
        ids = [self.vocab[w] for w in set(tokenize(query, self.accents)) if w in self.vocab]
        if not ids:
            return np.zeros(self.mat.shape[0], dtype=np.float32)
        return np.asarray(self.mat[:, ids] @ self.idf[ids]).ravel()


def rank_by(scores: np.ndarray, doc_ids: np.ndarray, tiebreak: np.ndarray | None = None, k: int = 100) -> list[int]:
    if tiebreak is None:
        order = np.argsort(-scores, kind="stable")
    else:
        order = np.lexsort((-tiebreak, -scores))
    return [int(doc_ids[i]) for i in order[:k]]


# ---------------------------------------------------------------------------
# production pipeline replication (imports the real backend modules)
# ---------------------------------------------------------------------------
class Production:
    def __init__(self, repo: Path, props: pd.DataFrame, lad: pd.DataFrame):
        sys.path.insert(0, str(repo / "backend"))
        from src.search import ranker  # noqa: E402
        from src.search.graph_repository import Neo4jGraphRepository, GRAPH_FEATURE_CATEGORIES  # noqa: E402
        from src.search.normalizer import FEATURE_ALIASES  # noqa: E402
        from src.search.query_parser import RuleBasedQueryParser  # noqa: E402

        class _FrozenDate(date):
            @classmethod
            def today(cls):
                return TODAY

        ranker.date = _FrozenDate
        self.ranker = ranker
        self.parser = RuleBasedQueryParser()
        self.score_graph_record = Neo4jGraphRepository._score_record
        self.graph_feature_categories = GRAPH_FEATURE_CATEGORIES
        self.feature_aliases = FEATURE_ALIASES
        self.props = props
        self.doc_ids = props["id"].astype(int).values
        self.created = pd.to_datetime(props["created_at"]).values.astype("int64")
        self.items = [self._item(r) for r in props.to_dict("records")]
        evidence = defaultdict(list)
        for r in lad.to_dict("records"):
            if int(r["rank"]) <= 1:
                evidence[str(r["listing_id"])].append({
                    "category": r["category"], "name": r["amenity_name"],
                    "driving_distance_km": _f(r["driving_distance_km"]),
                    "driving_duration_min": _f(r["driving_duration_min"]),
                    "threshold_km": _f(r["threshold_km"]),
                })
        for item in self.items:
            item["amenity_evidence"] = evidence.get(str(item["listing_id"]), [])
        self._graph_index(repo)

    @staticmethod
    def _item(r: dict) -> dict:
        item = dict(r)
        for key in ("price_range", "area", "area_price_history", "frontage", "access_road", "coordinate_confidence"):
            item[key] = _f(item.get(key))
        for key in ("bedrooms", "bathrooms"):
            v = _f(item.get(key))
            item[key] = None if v is None else int(v)
        for key in C.BOOL_FEATURES:
            item[key] = item.get(key) in ("t", True, "true", 1)
        item["posted_date"] = str(item.get("posted_date") or "")
        return item

    def _graph_index(self, repo: Path):
        v2 = repo / "Data" / "real_estate_graph_ready_v2_address_mapping"
        nodes = pd.read_csv(v2 / "neo4j_listing_nodes.csv", low_memory=False)
        nodes.columns = [c.split(":")[0] for c in nodes.columns]
        wards = pd.read_csv(v2 / "neo4j_ward_nodes.csv")
        wards.columns = [c.split(":")[0] for c in wards.columns]
        in_ward = pd.read_csv(v2 / "neo4j_listing_in_ward_relationships.csv", encoding="utf-8-sig")
        in_ward.columns = ["listing_node_id", "ward_id", "type"]
        in_former = pd.read_csv(v2 / "neo4j_listing_in_former_area_relationships.csv", encoding="utf-8-sig")
        in_former.columns = ["listing_node_id", "former_area_id", "type"]
        former = pd.read_csv(v2 / "neo4j_former_admin_area_nodes.csv")
        former.columns = [c.split(":")[0] for c in former.columns]
        near = pd.read_csv(v2 / "neo4j_listing_near_amenity_relationships.csv", encoding="utf-8-sig")
        near.columns = [c.split(":")[0] if c.split(":")[0] else c for c in near.columns]
        near = near.rename(columns={near.columns[0]: "listing_node_id", near.columns[1]: "amenity_id"})
        amen = pd.read_csv(v2 / "neo4j_amenity_nodes.csv", low_memory=False)
        amen.columns = [c.split(":")[0] for c in amen.columns]
        amen_name = dict(zip(amen["amenity_id"], amen["name"]))
        ward_name = dict(zip(wards["ward_id"], wards["name"]))
        former_name = dict(zip(former["former_area_id"], former["name"]))
        node_wards = in_ward.groupby("listing_node_id")["ward_id"].apply(lambda s: [ward_name[x] for x in s]).to_dict()
        node_former = in_former.groupby("listing_node_id")["former_area_id"].apply(lambda s: [former_name[x] for x in s]).to_dict()
        node_amen = defaultdict(list)
        for r in near.to_dict("records"):
            node_amen[r["listing_node_id"]].append({
                "category": r["category"], "name": amen_name.get(r["amenity_id"]),
                "driving_distance_km": _f(r["driving_distance_km"]),
                "driving_duration_min": _f(r["driving_duration_min"]),
                "threshold_km": _f(r.get("threshold_km")),
            })
        nodes["posted_date"] = pd.to_datetime(nodes["posted_date"])
        # Cypher: ORDER BY posted_date DESC LIMIT 500 (ties: import order)
        nodes["import_order"] = np.arange(len(nodes))
        self.graph_nodes = nodes.sort_values(["posted_date", "import_order"], ascending=[False, True])
        self.node_wards, self.node_former, self.node_amen = node_wards, node_former, node_amen
        flags = [f for f in self.feature_aliases if f not in self.graph_feature_categories and f in nodes.columns]
        self.node_flags = {r["listing_node_id"]: {f: str(r[f]).lower() == "true" for f in flags}
                           for r in nodes[["listing_node_id", *flags]].to_dict("records")}

    def graph_candidates(self, parsed, limit: int = K_CANDIDATES) -> dict:
        requested = {*parsed.hard_filters.required_features, *parsed.preference_filters.required_features,
                     *(p.value for p in parsed.soft_preferences if p.type == "feature" and p.value)}
        pref_features = sorted(requested & (set(self.feature_aliases) - set(self.graph_feature_categories)))
        cats = {a.amenity_category for a in parsed.amenity_filters}
        for feature in requested:
            cats.update(self.graph_feature_categories.get(feature, set()))
        out = {}
        for r in self.graph_nodes.head(limit).to_dict("records"):
            nid = r["listing_node_id"]
            amenities = [a for a in self.node_amen.get(nid, []) if not cats or a["category"] in cats]
            record = {
                "listing_id": str(r["listing_id"]), "listing_node_id": nid,
                "wards": self.node_wards.get(nid, []), "amenities": amenities,
                "matched_features": [f for f in pref_features if self.node_flags.get(nid, {}).get(f)],
                "former_admin_area": (self.node_former.get(nid) or [r.get("former_admin_area")])[0],
                "geo_cluster_150m": r.get("geo_cluster_150m"),
            }
            scored = self.score_graph_record(record, parsed)
            current = out.get(scored["listing_id"])
            if current is None or scored["graph_score"] > current["graph_score"]:
                out[scored["listing_id"]] = scored
        return out

    def rank(self, query: str, text_scores: np.ndarray, semantic: np.ndarray | None, use_graph: bool,
             text_rank_scores: np.ndarray | None = None, top_k: int = 100):
        parsed = self.parser.parse(query, top_k=min(top_k, 100))
        order_scores = text_rank_scores if text_rank_scores is not None else text_scores
        if semantic is not None:
            order = np.lexsort((-order_scores, -semantic))
        else:
            order = np.lexsort((-self.created, -order_scores))
        cand_idx = list(order[:K_CANDIDATES])
        graph_map = self.graph_candidates(parsed) if use_graph else {}
        if graph_map:
            have = set(cand_idx)
            extra = [i for i, lid in enumerate(self.props["listing_id"].astype(str).values)
                     if lid in graph_map and i not in have]
            cand_idx += extra
        items = []
        for i in cand_idx:
            item = dict(self.items[i])
            item["text_score"] = float(text_scores[i])
            item["semantic_score"] = float(semantic[i]) if semantic is not None else 0.0
            g = graph_map.get(str(item["listing_id"]))
            item["graph_score"] = g["graph_score"] if g else 0.5
            items.append(item)
        ranked = self.ranker.rank_candidates(items, parsed, None)
        selected = self.ranker.diversify(ranked, top_k)[:top_k]
        return [int(it["id"]) for it in selected], parsed


def _f(v):
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)) or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# parser slot accuracy (traditional NLU vs gold constraints)
# ---------------------------------------------------------------------------
GOLD_TO_PARSER_CAT = {"school": "school", "college_university": "school", "supermarket": "mall", "mall": "mall",
                      "market": "market", "park": "park", "hospital": "hospital", "metro": "metro", "bus_stop": "bus"}
GOLD_TO_FEATURE = {"school": "near_school", "college_university": "near_school", "supermarket": "near_mall",
                   "mall": "near_mall", "market": "near_market", "park": "near_park", "hospital": "near_hospital",
                   "metro": "near_metro", "bus_stop": "near_bus"}
ASPECT_TO_FEATURE = {"view_song": "river_view", "thang_may_nha": "elevator", "ho_boi": "pool", "san_vuon": "garden"}


def _loc_terms(values):
    out = set()
    for v in values:
        if not v:
            continue
        n = C.norm(v)
        out.add(n)
        out.add(re.sub(r"^(?:phuong|xa|quan|huyen|thi xa|thanh pho|tp)\s+", "", n))
    return out


def slot_report(gold: dict, parsed) -> dict:
    pf = parsed.preference_filters
    res = {}
    if gold.get("property_type"):
        res["type"] = set(pf.property_types) == {gold["property_type"]}
    if gold.get("ward") or gold.get("former_area"):
        want = _loc_terms([gold["ward"]] if gold.get("ward") else gold["former_area"])
        got = _loc_terms([*pf.districts, *pf.former_admin_areas])
        res["location"] = bool(want & got)
    gp = gold.get("price")
    if gp:
        p = pf.price
        if "min" in gp and "max" in gp:
            res["price"] = p.min is not None and p.max is not None and abs(p.min - gp["min"]) < 1e-6 and abs(p.max - gp["max"]) < 1e-6
        elif "max" in gp:
            res["price"] = p.max is not None and abs(p.max - gp["max"]) < 1e-6 and p.min is None
        else:
            res["price"] = p.target is not None and abs(p.target - gp["target"]) < 1e-6
    if gold.get("beds"):
        res["bedrooms"] = pf.bedrooms.min == gold["beds"]["value"]
    if gold.get("area_min"):
        res["area"] = pf.area.min is not None and abs(pf.area.min - gold["area_min"]) < 1e-6
    if gold.get("amenity"):
        a = gold["amenity"]
        cat = GOLD_TO_PARSER_CAT[a["category"]]
        filt = [f for f in parsed.amenity_filters if f.amenity_category == cat]
        if a["explicit"]:
            res["amenity"] = any(f.max_driving_distance_km is not None and abs(f.max_driving_distance_km - a["max_km"]) < 1e-6 for f in filt)
        else:
            feats = {p.value for p in parsed.soft_preferences if p.type == "feature"}
            res["amenity"] = bool(filt) or GOLD_TO_FEATURE[a["category"]] in feats
    for aspect in gold.get("aspects", []):
        feats = {p.value for p in parsed.soft_preferences if p.type == "feature"}
        res["aspect"] = ASPECT_TO_FEATURE.get(aspect) in feats if aspect in ASPECT_TO_FEATURE else False
    if gold.get("landmark"):
        res["landmark"] = False  # not representable in ParsedSearchQuery
    if gold.get("legal"):
        res["legal"] = "Sổ hồng riêng" in pf.legal_statuses
    if gold.get("furnishing"):
        res["furnishing"] = bool(set(pf.furnishings) & {"Đầy đủ", "Cao cấp"})
    return res


# ---------------------------------------------------------------------------
def evaluate(args):
    repo, bench, snap = Path(args.repo), Path(args.bench), Path(args.snapshot)
    queries, qrels = load_benchmark(bench)
    props, lad, fts, doc_emb = load_snapshot(snap, args.embedding_tag)
    doc_ids = props["id"].astype(int).values
    idx_of = {d: i for i, d in enumerate(doc_ids)}
    created = pd.to_datetime(props["created_at"]).values.astype("int64")
    texts = props["search_text"].fillna("").tolist()

    fts_by_q = defaultdict(dict)
    for r in fts.itertuples(index=False):
        fts_by_q[r.qid][int(r.doc_id)] = float(r.text_score)

    q_emb = None
    q_path = snap / f"query_embeddings_{args.embedding_tag}.npy"
    if q_path.exists():
        q_emb = np.load(q_path).astype(np.float32)
        meta = json.load(open(q_path.with_suffix(".json"), encoding="utf-8"))
        assert meta["qids"] == [q["qid"] for q in queries], "query embedding order mismatch"
        assert doc_emb is not None and doc_emb.shape[1] == q_emb.shape[1], "missing/mismatched document vectors"
    print(f"queries={len(queries)} docs={len(doc_ids)} dense={'yes' if q_emb is not None else 'no (pending)'}")

    bm25 = BM25(texts, accents=True)
    bm25_na = BM25(texts, accents=False)
    prod = Production(repo, props, lad)

    runs = defaultdict(dict)
    parsed_cache, slots = {}, {}
    rng = np.random.default_rng(0)
    for qi, q in enumerate(queries):
        qid, text = q["qid"], q["text"]
        ts = np.zeros(len(doc_ids), dtype=np.float32)
        for d, s in fts_by_q.get(qid, {}).items():
            ts[idx_of[d]] = s
        runs["random"][qid] = [[int(doc_ids[i]) for i in rng.permutation(len(doc_ids))[:100]] for _ in range(5)]
        s_bm25 = bm25.scores(text)
        s_bm25na = bm25_na.scores(text)
        runs["bm25"][qid] = rank_by(s_bm25, doc_ids)
        runs["bm25_noaccent"][qid] = rank_by(s_bm25na, doc_ids)
        runs["pg_fts"][qid] = rank_by(ts, doc_ids, tiebreak=created)
        ranked, parsed = prod.rank(text, ts, None, use_graph=False)
        runs["prod_nodl"][qid] = ranked
        runs["prod_nodl_graph"][qid] = prod.rank(text, ts, None, use_graph=True)[0]
        norm_bm25 = s_bm25na / s_bm25na.max() if s_bm25na.max() > 0 else s_bm25na
        runs["bm25_rule"][qid] = prod.rank(text, norm_bm25.astype(np.float32), None, use_graph=False)[0]
        slots[qid] = slot_report(q["gold"], parsed)
        if q_emb is not None:
            sem = doc_emb @ q_emb[qi]
            runs["dense"][qid] = rank_by(sem, doc_ids)
            runs["prod_dl"][qid] = prod.rank(text, ts, sem, use_graph=False)[0]
            runs["prod_dl_graph"][qid] = prod.rank(text, ts, sem, use_graph=True)[0]
            r1 = {d: r for r, d in enumerate(runs["bm25_noaccent"][qid])}
            r2 = {d: r for r, d in enumerate(rank_by(sem, doc_ids, k=1000))}
            fused = defaultdict(float)
            for rr in (r1, r2):
                for d, r in rr.items():
                    fused[d] += 1.0 / (60 + r + 1)
            runs["rrf_bm25_dense"][qid] = [d for d, _ in sorted(fused.items(), key=lambda x: -x[1])[:100]]
        if (qi + 1) % 100 == 0:
            print(f"  {qi + 1}/{len(queries)}")

    # ---- aggregate
    rows = []
    for system, by_q in runs.items():
        for q in queries:
            rel = qrels[q["qid"]]
            if system == "random":
                ms = [metrics_for(r, rel) for r in by_q[q["qid"]]]
                m = {k: float(np.mean([x[k] for x in ms])) for k in ms[0]}
            else:
                m = metrics_for(by_q[q["qid"]], rel)
            rows.append({"system": system, "qid": q["qid"], "split": q["split"], "family": q["family"],
                         "style": q["style"], **m})
    per_query = pd.DataFrame(rows)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    per_query.to_csv(out / "per_query_metrics.csv", index=False)

    metric_cols = ["ndcg@10", "p@10", "mrr@10", "success@10", "recall@100"]
    summary = {}
    for split in ("test", "val", "train", "all"):
        sub = per_query if split == "all" else per_query[per_query["split"] == split]
        summary[split] = sub.groupby("system")[metric_cols].mean().round(4).to_dict(orient="index")
    test = per_query[per_query["split"] == "test"]
    summary["test_by_family_ndcg"] = test.pivot_table(index="system", columns="family", values="ndcg@10").round(4).to_dict(orient="index")
    summary["test_by_style_ndcg"] = test.pivot_table(index="system", columns="style", values="ndcg@10").round(4).to_dict(orient="index")
    allq = per_query
    summary["all_by_style_ndcg"] = allq.pivot_table(index="system", columns="style", values="ndcg@10").round(4).to_dict(orient="index")
    summary["all_by_family_ndcg"] = allq.pivot_table(index="system", columns="family", values="ndcg@10").round(4).to_dict(orient="index")

    # bootstrap 95% CI for test nDCG@10
    ci = {}
    brng = np.random.default_rng(1)
    for system in test["system"].unique():
        v = test[test["system"] == system].sort_values("qid")["ndcg@10"].values
        boots = [brng.choice(v, size=len(v), replace=True).mean() for _ in range(2000)]
        ci[system] = [round(float(np.percentile(boots, 2.5)), 4), round(float(np.percentile(boots, 97.5)), 4)]
    summary["test_ndcg_ci95"] = ci

    # parser slot accuracy
    slot_rows = []
    for q in queries:
        for slot, ok in slots[q["qid"]].items():
            slot_rows.append({"qid": q["qid"], "style": q["style"], "family": q["family"], "slot": slot, "ok": int(ok)})
    sd = pd.DataFrame(slot_rows)
    sd.to_csv(out / "parser_slots.csv", index=False)
    full = sd.groupby(["qid", "style"])["ok"].min().reset_index()
    summary["parser_slot_accuracy"] = {
        "by_slot": sd.groupby("slot")["ok"].agg(["mean", "count"]).round(4).to_dict(orient="index"),
        "by_style": sd.groupby("style")["ok"].mean().round(4).to_dict(),
        "by_slot_style": sd.pivot_table(index="slot", columns="style", values="ok").round(4).to_dict(orient="index"),
        "query_fully_parsed": float(full["ok"].mean().round(4)),
        "query_fully_parsed_by_style": full.groupby("style")["ok"].mean().round(4).to_dict(),
    }
    summary["fts_queries_with_any_match"] = int(sum(1 for q in queries if fts_by_q.get(q["qid"])))
    summary["dense_available"] = q_emb is not None
    json.dump(summary, open(out / "summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps(summary["test"], indent=1))
    print(json.dumps(summary["parser_slot_accuracy"], ensure_ascii=False, indent=1)[:2500])
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="IT2047 repository root")
    ap.add_argument("--bench", default="benchmark")
    ap.add_argument("--snapshot", default="snapshot", help="folder with files extracted from the PostgreSQL backup")
    ap.add_argument("--embedding-tag", default="qwen3-embedding-0.6b",
                    help="tag written by embed_benchmark.py (model name without 'text-embedding-')")
    ap.add_argument("--out", default="results")
    evaluate(ap.parse_args())
