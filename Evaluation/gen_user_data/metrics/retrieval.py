"""Candidate-generation / retrieval metrics: Hit Rate@K, Recall@K, Precision@K.

Trong BĐS, Recall quan trọng hơn Precision (thà gợi ý dư còn hơn bỏ sót căn
nhà mơ ước). Dùng binary relevance: `relevant_set` = tập listing user thực sự
tương tác tích cực (vd contact/save) trong tập test.
"""
from __future__ import annotations

from typing import Sequence


def hit_rate_at_k(ranked_ids: Sequence, relevant_set: set, k: int) -> float:
    """1.0 nếu có ÍT NHẤT một item relevant trong top-k, ngược lại 0.0."""
    if not relevant_set:
        return 0.0
    return 1.0 if any(i in relevant_set for i in ranked_ids[:k]) else 0.0


def recall_at_k(ranked_ids: Sequence, relevant_set: set, k: int) -> float:
    """Tỷ lệ item relevant được thu hồi trong top-k."""
    if not relevant_set:
        return 0.0
    hits = sum(1 for i in ranked_ids[:k] if i in relevant_set)
    return hits / len(relevant_set)


def precision_at_k(ranked_ids: Sequence, relevant_set: set, k: int) -> float:
    """Tỷ lệ item trong top-k thực sự relevant."""
    if k <= 0:
        return 0.0
    hits = sum(1 for i in ranked_ids[:k] if i in relevant_set)
    return hits / k


def mean_over_users(fn, list_of_ranked, list_of_relevant, k: int) -> float:
    """Tiện ích: trung bình một metric trên nhiều user."""
    if not list_of_ranked:
        return 0.0
    vals = [fn(r, rel, k) for r, rel in zip(list_of_ranked, list_of_relevant)]
    return sum(vals) / len(vals)
