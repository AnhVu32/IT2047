"""Pipeline đánh giá end-to-end cho hệ thống gợi ý BĐS.

Metric lấy TRỰC TIẾP từ repo đã clone
(../Evaluation-Metrics-for-Recommendation-Systems -> thư viện `recommenders`)
qua eval_engine.py: NDCG@K, MRR@K, Recall@K, Precision@K, MAP@K.
HitRate@K lấy từ module nội bộ metrics/ (repo không expose sẵn).
Nếu chưa clone repo -> tự fallback toàn bộ sang metrics/ nội bộ.

Các bước:
  1. Load users / listings / interactions.
  2. Temporal split (chống leakage), 80/20 theo timestamp.
  3. Với mỗi user có tín hiệu test: candidate pool = positives + N negatives
     lấy mẫu (giao thức sampled-negatives). Xếp hạng pool bằng score(user,item).
  4. Dựng rating_true (relevant + implicit_score) & rating_pred (điểm recommender)
     rồi chấm bằng thư viện repo.

Recommender baseline (score(user_id, listing_id) -> float):
  * popularity : tổng implicit_score train (global).
  * content    : relevance(user, listing) theo thuộc tính.
  * embed_cf   : cosine(profile embedding user, embedding listing) — embedding
                 thật trong backend/src/data/embeddings.pkl.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import Callable, Dict, List

import numpy as np
import pandas as pd

from schemas import Interaction, Listing, UserProfile
from generation.generate_interactions import relevance
import eval_engine
from metrics import hit_rate_at_k
# fallback nội bộ nếu chưa clone repo
from metrics import ndcg_at_k as _ndcg, mrr as _mrr, recall_at_k as _recall, \
    precision_at_k as _precision, map_at_k as _map

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
EMBEDDINGS_PKL = os.path.join(REPO_ROOT, "backend", "src", "data", "embeddings.pkl")

K = 10
POSITIVE_ACTIONS = {"save", "share", "contact"}
TRAIN_FRACTION = 0.8
NUM_NEG_SAMPLES = 100
EVAL_SEED = 20260723


def _load(name, model):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return [model(**row) for row in json.load(f)]


def temporal_split(interactions: List[Interaction], frac: float = TRAIN_FRACTION):
    ts_sorted = sorted(interactions, key=lambda x: x.timestamp)
    cut = int(len(ts_sorted) * frac)
    cutoff = ts_sorted[cut].timestamp if cut < len(ts_sorted) else ts_sorted[-1].timestamp
    train = [it for it in ts_sorted if it.timestamp < cutoff]
    test = [it for it in ts_sorted if it.timestamp >= cutoff]
    return train, test, cutoff


def build_ground_truth(test: List[Interaction]):
    relevant: Dict[str, set] = defaultdict(set)
    gains: Dict[str, Dict[int, float]] = defaultdict(dict)
    for it in test:
        if it.action_type in POSITIVE_ACTIONS:
            relevant[it.user_id].add(it.listing_id)
        prev = gains[it.user_id].get(it.listing_id, 0.0)
        gains[it.user_id][it.listing_id] = max(prev, it.implicit_score)
    return relevant, gains


# --- Recommenders: scorer(user_id, listing_id) -> float ---------------------
def make_popularity_scorer(train: List[Interaction]) -> Callable[[str, int], float]:
    pop = defaultdict(float)
    for it in train:
        pop[it.listing_id] += it.implicit_score
    return lambda uid, lid: pop.get(lid, 0.0)


def make_content_scorer(users, listings) -> Callable[[str, int], float]:
    user_by_id = {u.user_id: u for u in users}
    listing_by_id = {l.listing_id: l for l in listings}

    def score(uid: str, lid: int) -> float:
        u, l = user_by_id.get(uid), listing_by_id.get(lid)
        return 0.0 if (u is None or l is None) else relevance(u, l)

    return score


def make_embed_cf_scorer(train: List[Interaction]) -> Callable[[str, int], float]:
    df = pd.read_pickle(EMBEDDINGS_PKL)
    ids = [int(x) for x in df["listing_id"].tolist()]
    feat_cols = [c for c in df.columns if c != "listing_id"]
    mat = df[feat_cols].to_numpy(dtype=np.float64)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    mat = mat / norms
    id_to_row = {lid: i for i, lid in enumerate(ids)}

    dim = mat.shape[1]
    profiles: Dict[str, np.ndarray] = defaultdict(lambda: np.zeros(dim))
    for it in train:
        row = id_to_row.get(it.listing_id)
        if row is not None:
            profiles[it.user_id] += it.implicit_score * mat[row]
    for uid, p in list(profiles.items()):
        n = np.linalg.norm(p)
        if n > 0:
            profiles[uid] = p / n

    def score(uid: str, lid: int) -> float:
        row = id_to_row.get(lid)
        p = profiles.get(uid)
        return 0.0 if (row is None or p is None) else float(mat[row] @ p)

    return score


# --- Build ranked candidate pools -------------------------------------------
def build_ranked_pools(scorer, users_with_test, gains, seen_by_user, all_ids,
                       n_neg=NUM_NEG_SAMPLES):
    """Trả về dict {uid -> ranked list listing_id} trên candidate pool."""
    rng = np.random.default_rng(EVAL_SEED)
    all_ids_arr = np.array(all_ids)
    pools = {}
    for uid in users_with_test:
        pos = set(gains.get(uid, {}))
        if not pos:
            continue
        forbidden = seen_by_user.get(uid, set()) | pos
        neg_pool = all_ids_arr[~np.isin(all_ids_arr, list(forbidden))]
        n_take = min(n_neg, len(neg_pool))
        negs = rng.choice(neg_pool, size=n_take, replace=False).tolist()
        candidates = list(pos) + negs
        pools[uid] = sorted(candidates, key=lambda lid: scorer(uid, lid), reverse=True)
    return pools


# --- Scoring via cloned repo (with internal fallback) -----------------------
def evaluate_with_repo(pools, relevant, gains, k):
    true_rows, pred_rows = [], []
    for uid, ranked in pools.items():
        rel = relevant.get(uid, set())
        if not rel:
            continue
        for lid in rel:
            true_rows.append({"userID": uid, "itemID": lid,
                              "rating": gains[uid].get(lid, 1.0)})
        # prediction score = điểm giảm dần theo rank (đơn điệu với thứ hạng)
        for pos, lid in enumerate(ranked):
            pred_rows.append({"userID": uid, "itemID": lid,
                              "prediction": float(len(ranked) - pos)})
    rating_true = pd.DataFrame(true_rows)
    rating_pred = pd.DataFrame(pred_rows)
    res = eval_engine.evaluate_ranking(rating_true, rating_pred, k)
    # HitRate bổ sung (repo không expose)
    users_bin = [u for u in pools if relevant.get(u)]
    res[f"HitRate@{k}"] = round(
        sum(hit_rate_at_k(pools[u], relevant[u], k) for u in users_bin)
        / len(users_bin), 4) if users_bin else 0.0
    res["users_evaluated"] = len(users_bin)
    res["engine"] = "recommenders (cloned repo)"
    return res


def evaluate_internal(pools, relevant, gains, k):
    users_bin = [u for u in pools if relevant.get(u)]
    if not users_bin:
        return {"users_evaluated": 0, "engine": "internal metrics/"}
    ranked = [pools[u] for u in users_bin]
    rels = [relevant[u] for u in users_bin]
    ndcgs = [_ndcg(pools[u], gains[u], k) for u in users_bin]
    return {
        "users_evaluated": len(users_bin),
        f"NDCG@{k}": round(sum(ndcgs) / len(ndcgs), 4),
        f"MRR@{k}": round(_mrr(ranked, rels, k), 4),
        f"Recall@{k}": round(sum(_recall(r, s, k) for r, s in zip(ranked, rels)) / len(ranked), 4),
        f"Precision@{k}": round(sum(_precision(r, s, k) for r, s in zip(ranked, rels)) / len(ranked), 4),
        f"MAP@{k}": round(_map(ranked, rels, k), 4),
        f"HitRate@{k}": round(sum(hit_rate_at_k(r, s, k) for r, s in zip(ranked, rels)) / len(ranked), 4),
        "engine": "internal metrics/",
    }


def main():
    users = _load("users.json", UserProfile)
    listings = _load("listings.json", Listing)
    interactions = _load("interactions.json", Interaction)

    train, test, cutoff = temporal_split(interactions)
    use_repo = eval_engine.available()
    print(f"[eval] interactions={len(interactions)} train={len(train)} test={len(test)}")
    print(f"[eval] cutoff={cutoff} | protocol=sampled-negatives(N={NUM_NEG_SAMPLES}) K={K}")
    print(f"[eval] metric engine: {'recommenders (cloned repo)' if use_repo else 'internal metrics/ (repo chưa clone)'}")

    seen_by_user: Dict[str, set] = defaultdict(set)
    for it in train:
        seen_by_user[it.user_id].add(it.listing_id)

    all_ids = [l.listing_id for l in listings]
    relevant, gains = build_ground_truth(test)
    users_with_test = sorted(set(gains))

    scorers = {
        "popularity": make_popularity_scorer(train),
        "content": make_content_scorer(users, listings),
    }
    try:
        scorers["embed_cf"] = make_embed_cf_scorer(train)
    except FileNotFoundError as e:
        print(f"[eval] Bỏ qua embed_cf: {e}")

    results = {}
    for name, scorer in scorers.items():
        pools = build_ranked_pools(scorer, users_with_test, gains, seen_by_user, all_ids)
        results[name] = (evaluate_with_repo(pools, relevant, gains, K)
                         if use_repo else evaluate_internal(pools, relevant, gains, K))

    print("\n=== EVALUATION REPORT (K=%d, %d neg/user) ===" % (K, NUM_NEG_SAMPLES))
    for name, r in results.items():
        print(f"\n[{name}]  ({r.get('engine')})")
        for metric, val in r.items():
            if metric == "engine":
                continue
            print(f"  {metric:>18}: {val}")

    out_path = os.path.join(DATA_DIR, "eval_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"cutoff": cutoff, "k": K, "num_neg_samples": NUM_NEG_SAMPLES,
                   "results": results}, f, ensure_ascii=False, indent=2)
    print(f"\n[eval] saved -> {out_path}")
    return results


if __name__ == "__main__":
    main()
