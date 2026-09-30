"""Evaluation metrics cho hệ thống gợi ý BĐS.

Nhóm ưu tiên (theo recsys_kg_rag_guide.md):
  * ranking:   ndcg_at_k, mrr, map_at_k           (QUAN TRỌNG NHẤT)
  * retrieval: hit_rate_at_k, recall_at_k          (cho bước candidate generation)
  * similarity: cosine_similarity, jaccard_similarity (cho "BĐS tương tự")

Bỏ qua RMSE/MAE (BĐS không có rating 1-5 sao).
"""
from .ranking import dcg_at_k, ndcg_at_k, mrr, average_precision, map_at_k
from .retrieval import hit_rate_at_k, recall_at_k, precision_at_k
from .similarity import (
    cosine_similarity, jaccard_similarity, euclidean_distance,
    manhattan_distance, pearson_correlation,
)

__all__ = [
    "dcg_at_k", "ndcg_at_k", "mrr", "average_precision", "map_at_k",
    "hit_rate_at_k", "recall_at_k", "precision_at_k",
    "cosine_similarity", "jaccard_similarity", "euclidean_distance",
    "manhattan_distance", "pearson_correlation",
]
