"""Similarity metrics cho module "Các BĐS tương tự" (item-to-item).

Đối chiếu repo tham chiếu (aryan-jadon/Evaluation-Metrics-for-Recommendation-Systems,
folder `similarity_metrics/` — torch_embedding_*_similarity.py). Repo triển khai
nhiều độ đo trên embedding: cosine, jaccard, euclidean, manhattan, pearson...
Ở đây implement bằng numpy (không cần torch), giữ đúng công thức chuẩn.

  * cosine / euclidean / manhattan / pearson: dùng cho vector embedding liên tục.
  * jaccard: dùng cho tập tính năng nhị phân (amenity/accessibility/view).

Guide khuyến nghị Cosine + Jaccard là hai độ đo chính cho BĐS.
"""
from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity in [-1, 1]. 0 nếu một vector là 0."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def jaccard_similarity(a: Iterable, b: Iterable) -> float:
    """Jaccard index |A∩B| / |A∪B| trên hai tập (vd tập amenity = True)."""
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    union = sa | sb
    if not union:
        return 0.0
    return len(sa & sb) / len(union)


def euclidean_distance(a: Sequence[float], b: Sequence[float]) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return float(np.linalg.norm(a - b))


def manhattan_distance(a: Sequence[float], b: Sequence[float]) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return float(np.sum(np.abs(a - b)))


def pearson_correlation(a: Sequence[float], b: Sequence[float]) -> float:
    """Hệ số tương quan Pearson in [-1, 1]."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.size < 2:
        return 0.0
    a = a - a.mean()
    b = b - b.mean()
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)
