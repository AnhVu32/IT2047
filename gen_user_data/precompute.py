"""Tính sẵn (precompute) artifact phục vụ QUERY về sau.

Từ dữ liệu đã sinh (listings / interactions / similarity + embeddings.pkl thật),
tính trước những thứ đắt để lúc query chỉ việc tra cứu -> nhanh & tốt hơn:

  1. popularity   : điểm phổ biến mỗi listing + top-N theo district/segment/intent
                    -> cold-start, fallback ranking, tie-break.
  2. content_neighbors : top-K BĐS tương tự theo EMBEDDING thật (cosine)
                    -> tính năng "BĐS tương tự", mở rộng candidate tức thì.
  3. co_engagement : item-item từ HÀNH VI ("user contact X cũng contact Y")
                    -> gợi ý theo hành vi, bổ sung cho content.
  4. query_expansion : mỗi attribute (amenity/criteria/location) -> attribute liên
                    quan (từ similarity matrix) -> nới rộng truy vấn
                    ("gần trường" cũng xét "kids_playground", "near_park"...).
  5. segment_affinity : amenity nào quan trọng theo segment×intent -> prior cá nhân hoá.

Đầu ra: data/precomputed/*.json  +  bảng tra cứu trong data/warehouse.sqlite.
Idempotent: ghi đè file + INSERT OR REPLACE bảng.

    cd gen_user_data && python precompute.py
"""
from __future__ import annotations

import json
import os
import sqlite3
from collections import defaultdict
from typing import Dict, List

import numpy as np

from schemas import Interaction, Listing

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
OUT_DIR = os.path.join(DATA_DIR, "precomputed")
KG_DIR = os.path.join(DATA_DIR, "kg")
DB_PATH = os.path.join(DATA_DIR, "warehouse.sqlite")
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
EMBEDDINGS_PKL = os.path.join(REPO_ROOT, "backend", "src", "data", "embeddings.pkl")

TOP_K = 20
POSITIVE_ACTIONS = {"save", "share", "contact"}
QUERY_EXPANSION_MIN_W = 0.25


def _read(name, model=None):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        data = json.load(f)
    return [model(**r) for r in data] if model else data


def _write(name, obj):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 1) Popularity priors
# ---------------------------------------------------------------------------
def compute_popularity(listings: List[Listing], interactions: List[Interaction]):
    listing_by_id = {l.listing_id: l for l in listings}
    pop = defaultdict(float)
    for it in interactions:
        pop[it.listing_id] += it.implicit_score
    # chuẩn hoá [0,1]
    mx = max(pop.values()) if pop else 1.0
    pop_norm = {lid: round(v / mx, 4) for lid, v in pop.items()}

    def top_by(keyfn, n=20):
        buckets = defaultdict(list)
        for lid, score in pop.items():
            l = listing_by_id.get(lid)
            if l:
                buckets[keyfn(l)].append((lid, score))
        return {k: [lid for lid, _ in sorted(v, key=lambda x: x[1], reverse=True)[:n]]
                for k, v in buckets.items()}

    return {
        "per_listing": pop_norm,  # prior ranking / tie-break
        "top_by_district": top_by(lambda l: l.district),
        "top_by_segment": top_by(lambda l: l.budget_group),
        "global_top": [lid for lid, _ in sorted(pop.items(), key=lambda x: x[1], reverse=True)[:50]],
    }


# ---------------------------------------------------------------------------
# 2) Content neighbors (embeddings thật)
# ---------------------------------------------------------------------------
def compute_content_neighbors(listings: List[Listing], k=TOP_K):
    import pandas as pd

    valid = {l.listing_id for l in listings}
    df = pd.read_pickle(EMBEDDINGS_PKL)
    df = df[df["listing_id"].isin(valid)]
    # embeddings.pkl có vài listing_id trùng -> dedup để tránh chính nó lọt vào neighbor
    df = df.drop_duplicates(subset="listing_id").reset_index(drop=True)
    ids = [int(x) for x in df["listing_id"]]
    feat = [c for c in df.columns if c != "listing_id"]
    M = df[feat].to_numpy(dtype=np.float32)
    norm = np.linalg.norm(M, axis=1, keepdims=True)
    norm[norm == 0] = 1.0
    M = M / norm

    neighbors: Dict[int, List[dict]] = {}
    # theo lô để không giữ ma trận NxN
    B = 256
    with np.errstate(all="ignore"):
        for s in range(0, len(ids), B):
            block = M[s:s + B] @ M.T  # (b, N)
            for r in range(block.shape[0]):
                row = block[r]
                gi = s + r
                row[gi] = -1.0  # bỏ chính nó
                top = np.argpartition(-row, k)[:k]
                top = top[np.argsort(-row[top])]
                neighbors[ids[gi]] = [{"listing_id": ids[j], "sim": round(float(row[j]), 4)}
                                      for j in top if ids[j] != ids[gi]]
    return neighbors


# ---------------------------------------------------------------------------
# 3) Co-engagement item-item (hành vi)
# ---------------------------------------------------------------------------
def compute_co_engagement(interactions: List[Interaction], k=TOP_K):
    # user -> tập listing tương tác tích cực (có trọng số)
    by_user = defaultdict(dict)
    for it in interactions:
        if it.action_type in POSITIVE_ACTIONS:
            by_user[it.user_id][it.listing_id] = max(
                by_user[it.user_id].get(it.listing_id, 0.0), it.implicit_score)

    co = defaultdict(lambda: defaultdict(float))
    for _, items in by_user.items():
        lids = list(items)
        for i in range(len(lids)):
            for j in range(i + 1, len(lids)):
                a, b = lids[i], lids[j]
                w = min(items[a], items[b])  # đồng-quan-tâm mạnh nhất bởi trọng số nhỏ hơn
                co[a][b] += w
                co[b][a] += w
    out = {}
    for a, nbrs in co.items():
        top = sorted(nbrs.items(), key=lambda x: x[1], reverse=True)[:k]
        out[a] = [{"listing_id": b, "score": round(w, 3)} for b, w in top]
    return out


# ---------------------------------------------------------------------------
# 4) Query expansion (từ similarity matrix)
# ---------------------------------------------------------------------------
def compute_query_expansion(min_w=QUERY_EXPANSION_MIN_W):
    exp: Dict[str, List[dict]] = defaultdict(list)
    for fname in ("similarity_edges.json", "location_similarity_edges.json"):
        path = os.path.join(KG_DIR, fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for e in json.load(f):
                if e["weight"] < min_w:
                    continue
                exp[e["attr_a"]].append({"attr": e["attr_b"], "weight": e["weight"], "group": e["group"]})
                exp[e["attr_b"]].append({"attr": e["attr_a"], "weight": e["weight"], "group": e["group"]})
    for a in exp:
        exp[a] = sorted(exp[a], key=lambda x: x["weight"], reverse=True)
    return dict(exp)


# ---------------------------------------------------------------------------
# 5) Segment × intent -> amenity affinity
# ---------------------------------------------------------------------------
def compute_segment_affinity(listings: List[Listing], interactions: List[Interaction]):
    listing_by_id = {l.listing_id: l for l in listings}
    # user segment/intent lấy từ context (budget_group, inferred_intent)
    acc = defaultdict(lambda: defaultdict(float))
    cnt = defaultdict(float)
    for it in interactions:
        l = listing_by_id.get(it.listing_id)
        if not l:
            continue
        key = f"{it.context.budget_group}|{it.context.inferred_intent}"
        cnt[key] += it.implicit_score
        for a, v in l.features.items():
            if v:
                acc[key][a] += it.implicit_score
    out = {}
    for key, amen in acc.items():
        total = cnt[key] or 1.0
        ranked = sorted(((a, s / total) for a, s in amen.items()),
                        key=lambda x: x[1], reverse=True)
        out[key] = [{"amenity": a, "affinity": round(s, 4)} for a, s in ranked[:10]]
    return out


# ---------------------------------------------------------------------------
# SQLite: bảng tra cứu query-time
# ---------------------------------------------------------------------------
def write_sqlite(popularity, content_nb, query_exp):
    if not os.path.exists(DB_PATH):
        os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS pc_popularity (listing_id INTEGER PRIMARY KEY, score REAL);
        CREATE TABLE IF NOT EXISTS pc_item_neighbor (
            listing_id INTEGER, rank INTEGER, neighbor_id INTEGER, sim REAL,
            PRIMARY KEY (listing_id, rank));
        CREATE TABLE IF NOT EXISTS pc_query_expansion (
            attr TEXT, related TEXT, weight REAL, grp TEXT,
            PRIMARY KEY (attr, related));
        """
    )
    conn.execute("DELETE FROM pc_popularity")
    conn.executemany("INSERT OR REPLACE INTO pc_popularity VALUES (?,?)",
                     list(popularity["per_listing"].items()))
    conn.execute("DELETE FROM pc_item_neighbor")
    rows = [(lid, r, nb["listing_id"], nb["sim"])
            for lid, nbrs in content_nb.items() for r, nb in enumerate(nbrs)]
    conn.executemany("INSERT OR REPLACE INTO pc_item_neighbor VALUES (?,?,?,?)", rows)
    conn.execute("DELETE FROM pc_query_expansion")
    qrows = [(a, e["attr"], e["weight"], e["group"])
             for a, exps in query_exp.items() for e in exps]
    conn.executemany("INSERT OR REPLACE INTO pc_query_expansion VALUES (?,?,?,?)", qrows)
    conn.commit()
    conn.close()
    return len(rows), len(qrows)


def main():
    listings = _read("listings.json", Listing)
    interactions = _read("interactions.json", Interaction)

    print("[precompute] 1/5 popularity ...")
    popularity = compute_popularity(listings, interactions)
    _write("popularity.json", popularity)

    print("[precompute] 2/5 content neighbors (embeddings) ...")
    content_nb = compute_content_neighbors(listings)
    _write("content_neighbors.json", {str(k): v for k, v in content_nb.items()})

    print("[precompute] 3/5 co-engagement (behavior) ...")
    co = compute_co_engagement(interactions)
    _write("co_engagement.json", {str(k): v for k, v in co.items()})

    print("[precompute] 4/5 query expansion + segment affinity ...")
    qexp = compute_query_expansion()
    _write("query_expansion.json", qexp)
    seg = compute_segment_affinity(listings, interactions)
    _write("segment_affinity.json", seg)

    print("[precompute] 5/5 SQLite lookup tables ...")
    n_nb, n_qe = write_sqlite(popularity, content_nb, qexp)

    print("\n== precompute HOÀN TẤT ==")
    print(f"  popularity      : {len(popularity['per_listing'])} listing có điểm; "
          f"top theo {len(popularity['top_by_district'])} quận, {len(popularity['top_by_segment'])} segment")
    print(f"  content_neighbors: {len(content_nb)} listing × top-{TOP_K}")
    print(f"  co_engagement   : {len(co)} listing có hàng xóm hành vi")
    print(f"  query_expansion : {len(qexp)} attribute có mở rộng")
    print(f"  segment_affinity: {len(seg)} nhóm (segment×intent)")
    print(f"  SQLite          : pc_item_neighbor={n_nb} rows, pc_query_expansion={n_qe} rows")
    print(f"  -> {OUT_DIR}/*.json  +  {DB_PATH}")


if __name__ == "__main__":
    main()
