"""Similarity Matrix & Criteria -> cạnh KG + KIỂM CHỨNG với hành vi thực.

Nhiệm vụ (task 1.3): KHÔNG nạp ma trận nguyên si. Ta:
  1. Chuyển ma trận tương đồng tiêu chí (declared) thành EDGE cho KG:
       {"attr_a": ..., "attr_b": ..., "weight": ...}
     - amenity↔amenity: từ backend/.../knowledge.py SIMILARITY_MATRIX
       (cùng tên field với listings -> map thẳng vào Amenity node).
     - criteria↔criteria (ngữ nghĩa tiếng Việt): từ
       crawl_data/similarity_matrix_v2.py (CRITERIA + SIMILARITY_PAIRS).
  2. Tính similarity EMPIRICAL từ hành vi (interactions):
     - amenity: cosine trên ma trận user×amenity-affinity.
     - location (quận↔quận): cosine trên ma trận user×district-engagement.
  3. KIỂM CHỨNG declared vs empirical: tương quan Spearman + liệt kê cặp lệch
     nhiều nhất -> kết luận ma trận có phản ánh hành vi không.
  4. Xuất cạnh cho KG: similarity_edges.json (declared) +
     location_similarity_edges.json (derived từ hành vi).

Chạy: cd gen_user_data && python similarity_kg.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from collections import defaultdict
from typing import Dict, List, Tuple

import numpy as np

from schemas import Interaction, Listing, UserProfile

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
KG_DIR = os.path.join(DATA_DIR, "kg")
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
BACKEND_SRC = os.path.join(REPO_ROOT, "backend", "src")
CRAWL_SIM = os.path.join(REPO_ROOT, "crawl_data", "similarity_matrix_v2.py")


# ---------------------------------------------------------------------------
# 1) Declared matrices -> edges
# ---------------------------------------------------------------------------
def load_declared_amenity_edges() -> List[dict]:
    """SIMILARITY_MATRIX (amenity↔amenity) từ knowledge.py."""
    if BACKEND_SRC not in sys.path:
        sys.path.insert(0, BACKEND_SRC)
    from services.inference.knowledge import SIMILARITY_MATRIX  # type: ignore
    return [{"attr_a": a, "attr_b": b, "weight": round(float(w), 3),
             "group": "amenity", "source": "knowledge.py"}
            for (a, b), w in SIMILARITY_MATRIX.items()]


def load_declared_criteria_edges() -> Tuple[List[dict], Dict[str, str]]:
    """CRITERIA + SIMILARITY_PAIRS (ngữ nghĩa) từ crawl_data/similarity_matrix_v2.py."""
    spec = importlib.util.spec_from_file_location("sim_v2", CRAWL_SIM)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    edges = [{"attr_a": a, "attr_b": b, "weight": round(float(w), 3),
              "group": "criteria", "source": "similarity_matrix_v2.py"}
             for (a, b, w) in mod.SIMILARITY_PAIRS]
    return edges, dict(mod.CRITERIA)


# ---------------------------------------------------------------------------
# 2) Empirical similarity từ hành vi
# ---------------------------------------------------------------------------
def _amenities_of(listing: Listing) -> List[str]:
    return [f for f, v in listing.features.items() if v]


def empirical_amenity_similarity(interactions: List[Interaction],
                                 listings: List[Listing]) -> Dict[Tuple[str, str], float]:
    """Cosine giữa các amenity trên ma trận user×amenity-affinity.

    affinity[user][amenity] = tổng implicit_score các listing user tương tác mà
    có amenity đó. Hai amenity 'giống nhau về hành vi' nếu cùng được nhóm user
    quan tâm.
    """
    listing_by_id = {l.listing_id: l for l in listings}
    amenities = sorted({f for l in listings for f in _amenities_of(l)})
    a_idx = {a: i for i, a in enumerate(amenities)}
    users = sorted({it.user_id for it in interactions})
    u_idx = {u: i for i, u in enumerate(users)}

    M = np.zeros((len(users), len(amenities)))
    for it in interactions:
        l = listing_by_id.get(it.listing_id)
        if not l:
            continue
        ui = u_idx[it.user_id]
        for a in _amenities_of(l):
            M[ui, a_idx[a]] += it.implicit_score

    # cosine giữa các cột (amenity)
    col_norm = np.linalg.norm(M, axis=0)
    col_norm[col_norm == 0] = 1.0
    Mn = M / col_norm
    with np.errstate(all="ignore"):
        sim = Mn.T @ Mn  # amenity × amenity
    out = {}
    for i, a in enumerate(amenities):
        for j, b in enumerate(amenities):
            if i < j:
                out[(a, b)] = float(sim[i, j])
    return out


def empirical_location_similarity(interactions: List[Interaction],
                                  listings: List[Listing]) -> Dict[Tuple[str, str], float]:
    """Cosine giữa các quận trên ma trận user×district-engagement."""
    listing_by_id = {l.listing_id: l for l in listings}
    districts = sorted({l.district for l in listings})
    d_idx = {d: i for i, d in enumerate(districts)}
    users = sorted({it.user_id for it in interactions})
    u_idx = {u: i for i, u in enumerate(users)}

    M = np.zeros((len(users), len(districts)))
    for it in interactions:
        l = listing_by_id.get(it.listing_id)
        if not l:
            continue
        M[u_idx[it.user_id], d_idx[l.district]] += it.implicit_score

    col_norm = np.linalg.norm(M, axis=0)
    col_norm[col_norm == 0] = 1.0
    Mn = M / col_norm
    with np.errstate(all="ignore"):
        sim = Mn.T @ Mn
    out = {}
    for i, a in enumerate(districts):
        for j, b in enumerate(districts):
            if i < j:
                out[(a, b)] = float(sim[i, j])
    return out


# ---------------------------------------------------------------------------
# 3) Kiểm chứng declared vs empirical
# ---------------------------------------------------------------------------
def _spearman(x: List[float], y: List[float]) -> float:
    """Hệ số tương quan hạng Spearman (không cần scipy)."""
    if len(x) < 3:
        return 0.0

    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = rank(x), rank(y)
    n = len(x)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sx = (sum((a - mx) ** 2 for a in rx)) ** 0.5
    sy = (sum((b - my) ** 2 for b in ry)) ** 0.5
    return cov / (sx * sy) if sx and sy else 0.0


def validate(declared_edges: List[dict],
             empirical: Dict[Tuple[str, str], float]) -> dict:
    """So từng cặp declared với empirical (đã rescale về [0,1] bằng min-max)."""
    vals = list(empirical.values())
    lo, hi = (min(vals), max(vals)) if vals else (0.0, 1.0)
    rng = (hi - lo) or 1.0

    def emp_norm(a, b):
        raw = empirical.get((a, b), empirical.get((b, a)))
        if raw is None:
            return None
        return (raw - lo) / rng

    rows, dx, dy = [], [], []
    for e in declared_edges:
        en = emp_norm(e["attr_a"], e["attr_b"])
        if en is None:
            continue
        diff = abs(e["weight"] - en)
        rows.append({"pair": f'{e["attr_a"]}↔{e["attr_b"]}',
                     "declared": e["weight"], "empirical": round(en, 3),
                     "abs_diff": round(diff, 3)})
        dx.append(e["weight"])
        dy.append(en)

    rows.sort(key=lambda r: r["abs_diff"], reverse=True)
    rho = round(_spearman(dx, dy), 3)
    covered = len(rows)
    agree = sum(1 for r in rows if r["abs_diff"] <= 0.2)
    return {
        "pairs_compared": covered,
        "spearman_declared_vs_behavior": rho,
        "agree_within_0.2": agree,
        "agree_ratio": round(agree / covered, 3) if covered else 0.0,
        "top_disagreements": rows[:10],
    }


# ---------------------------------------------------------------------------
# 4) Location edges từ hành vi (giống ví dụ quận_9 ↔ quận_2)
# ---------------------------------------------------------------------------
def location_edges_from_behavior(loc_sim: Dict[Tuple[str, str], float],
                                 top_per_node: int = 3,
                                 min_weight: float = 0.15) -> List[dict]:
    by_node = defaultdict(list)
    for (a, b), w in loc_sim.items():
        by_node[a].append((b, w))
        by_node[b].append((a, w))
    seen, edges = set(), []
    for node, nbrs in by_node.items():
        for b, w in sorted(nbrs, key=lambda x: x[1], reverse=True)[:top_per_node]:
            if w < min_weight:
                continue
            key = tuple(sorted((node, b)))
            if key in seen:
                continue
            seen.add(key)
            edges.append({"attr_a": key[0], "attr_b": key[1],
                          "weight": round(w, 3), "group": "location",
                          "source": "behavior(interactions)"})
    return edges


def _load(name, model):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return [model(**row) for row in json.load(f)]


def main():
    listings = _load("listings.json", Listing)
    interactions = _load("interactions.json", Interaction)
    os.makedirs(KG_DIR, exist_ok=True)

    # 1) declared edges
    amenity_edges = load_declared_amenity_edges()
    criteria_edges, criteria_labels = load_declared_criteria_edges()
    declared = amenity_edges + criteria_edges
    with open(os.path.join(KG_DIR, "similarity_edges.json"), "w", encoding="utf-8") as f:
        json.dump(declared, f, ensure_ascii=False, indent=2)

    # 2) empirical
    emp_amenity = empirical_amenity_similarity(interactions, listings)
    emp_location = empirical_location_similarity(interactions, listings)

    # 3) validate (amenity là nhóm có cùng tên field -> so được)
    report = validate(amenity_edges, emp_amenity)

    # 4) location edges từ hành vi
    loc_edges = location_edges_from_behavior(emp_location)
    with open(os.path.join(KG_DIR, "location_similarity_edges.json"), "w", encoding="utf-8") as f:
        json.dump(loc_edges, f, ensure_ascii=False, indent=2)

    with open(os.path.join(DATA_DIR, "similarity_validation.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # --- report ---
    print(f"[sim] declared edges: {len(amenity_edges)} amenity + {len(criteria_edges)} criteria "
          f"-> {os.path.join(KG_DIR, 'similarity_edges.json')}")
    print(f"[sim] location edges (từ hành vi): {len(loc_edges)} "
          f"-> {os.path.join(KG_DIR, 'location_similarity_edges.json')}")
    print("\n=== KIỂM CHỨNG amenity: declared (knowledge.py) vs hành vi ===")
    print(f"  cặp so được         : {report['pairs_compared']}")
    print(f"  Spearman ρ          : {report['spearman_declared_vs_behavior']}  "
          f"(≈0 => ma trận KHÔNG khớp hành vi; ~1 => khớp)")
    print(f"  khớp (|Δ|<=0.2)     : {report['agree_within_0.2']}/{report['pairs_compared']} "
          f"({report['agree_ratio']})")
    print("  Top cặp lệch nhất (declared vs empirical):")
    for r in report["top_disagreements"][:6]:
        print(f"    - {r['pair']:<34} declared={r['declared']:<5} empirical={r['empirical']:<5} Δ={r['abs_diff']}")
    print("\n  Ví dụ location edges (từ hành vi):")
    for e in loc_edges[:5]:
        print(f"    - {e['attr_a']} ↔ {e['attr_b']}  w={e['weight']}")
    return report


if __name__ == "__main__":
    main()
