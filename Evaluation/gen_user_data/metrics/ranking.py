"""Ranking metrics: NDCG@K, MRR, MAP.

Quy ước chung:
  * `ranked_ids`: list listing_id theo THỨ TỰ hệ thống gợi ý (rank 1 trước).
  * `relevance`: dict {listing_id -> gain}. Gain > 0 nghĩa là relevant; với dữ
    liệu BĐS ta dùng implicit_score (contact/save/... ) làm gain (graded relevance).
  * Các listing không có trong `relevance` coi như gain = 0 (không liên quan).
"""
from __future__ import annotations

import math
from typing import Dict, List, Sequence


def dcg_at_k(ranked_ids: Sequence, relevance: Dict, k: int) -> float:
    """Discounted Cumulative Gain @K. Discount log2(rank+1), rank bắt đầu từ 1."""
    dcg = 0.0
    for i, item in enumerate(ranked_ids[:k]):
        gain = float(relevance.get(item, 0.0))
        if gain:
            dcg += gain / math.log2(i + 2)  # i=0 -> log2(2)=1
    return dcg


def ndcg_at_k(ranked_ids: Sequence, relevance: Dict, k: int) -> float:
    """Normalized DCG@K in [0,1]. Chia cho DCG lý tưởng (ideal ordering)."""
    dcg = dcg_at_k(ranked_ids, relevance, k)
    ideal_ids = [item for item, _ in sorted(
        relevance.items(), key=lambda kv: kv[1], reverse=True)]
    idcg = dcg_at_k(ideal_ids, relevance, k)
    if idcg == 0.0:
        return 0.0
    return dcg / idcg


def reciprocal_rank(ranked_ids: Sequence, relevant_set: set, k: int | None = None) -> float:
    """Reciprocal rank của item relevant ĐẦU TIÊN. 0 nếu không có trong top-k."""
    limit = len(ranked_ids) if k is None else k
    for i, item in enumerate(ranked_ids[:limit]):
        if item in relevant_set:
            return 1.0 / (i + 1)
    return 0.0


def mrr(list_of_ranked: Sequence[Sequence], list_of_relevant: Sequence[set],
        k: int | None = None) -> float:
    """Mean Reciprocal Rank trên nhiều truy vấn/user."""
    if not list_of_ranked:
        return 0.0
    rrs = [reciprocal_rank(r, rel, k)
           for r, rel in zip(list_of_ranked, list_of_relevant)]
    return sum(rrs) / len(rrs)


def average_precision(ranked_ids: Sequence, relevant_set: set, k: int | None = None) -> float:
    """Average Precision cho một truy vấn (binary relevance)."""
    if not relevant_set:
        return 0.0
    limit = len(ranked_ids) if k is None else k
    hits = 0
    ap = 0.0
    for i, item in enumerate(ranked_ids[:limit]):
        if item in relevant_set:
            hits += 1
            ap += hits / (i + 1)
    denom = min(len(relevant_set), limit)
    return ap / denom if denom else 0.0


def map_at_k(list_of_ranked: Sequence[Sequence], list_of_relevant: Sequence[set],
             k: int | None = None) -> float:
    """Mean Average Precision @K trên nhiều truy vấn."""
    if not list_of_ranked:
        return 0.0
    aps = [average_precision(r, rel, k)
           for r, rel in zip(list_of_ranked, list_of_relevant)]
    return sum(aps) / len(aps)
