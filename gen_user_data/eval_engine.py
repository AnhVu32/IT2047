"""Adapter dùng TRỰC TIẾP thư viện metric của repo đã clone.

Repo: ../Evaluation-Metrics-for-Recommendation-Systems (aryan-jadon) — bundle
thư viện Microsoft `recommenders`. Các hàm metric trong
`recommenders/evaluation/python_evaluation.py` chỉ cần numpy/pandas/sklearn
(không cần Spark/TF/torch — những cái đó chỉ cho benchmark MovieLens của repo).

Adapter này:
  * chèn đường dẫn repo vào sys.path,
  * expose `evaluate_ranking(rating_true, rating_pred, k)` trả về NDCG/MAP/MRR/
    Recall/Precision từ ĐÚNG hàm của repo,
  * nếu không tìm thấy repo -> raise, run_eval sẽ fallback sang metrics/ nội bộ.

Định dạng DataFrame (theo API recommenders):
  rating_true: [userID, itemID, rating]      # ground-truth relevant + gain
  rating_pred: [userID, itemID, prediction]  # điểm recommender cho candidate
"""
from __future__ import annotations

import os
import sys
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "Evaluation-Metrics-for-Recommendation-Systems"))

_LIB = None


def _load_lib():
    global _LIB
    if _LIB is not None:
        return _LIB
    if not os.path.isdir(REPO):
        raise FileNotFoundError(
            f"Chưa clone repo metric tại {REPO}. "
            "Chạy: git clone https://github.com/aryan-jadon/"
            "Evaluation-Metrics-for-Recommendation-Systems.git"
        )
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    from recommenders.evaluation import python_evaluation as pe  # type: ignore
    _LIB = pe
    return pe


# Cột chuẩn của recommenders
USER_COL, ITEM_COL, RATING_COL, PRED_COL = "userID", "itemID", "rating", "prediction"


def evaluate_ranking(rating_true, rating_pred, k: int) -> dict:
    """Gọi đúng các hàm metric của repo. NDCG dùng score_type='raw' để tôn
    trọng implicit_score (graded relevance) đúng tinh thần guide."""
    pe = _load_lib()
    common = dict(col_user=USER_COL, col_item=ITEM_COL, col_prediction=PRED_COL,
                  col_rating=RATING_COL, relevancy_method="top_k", k=k)
    with warnings.catch_warnings():
        # nuốt FutureWarning groupby.agg của pandas mới (không ảnh hưởng kết quả)
        warnings.simplefilter("ignore")
        return {
            f"NDCG@{k}": round(pe.ndcg_at_k(rating_true, rating_pred,
                                            score_type="raw", **common), 4),
            f"MRR@{k}": round(pe.mrr_at_k(rating_true, rating_pred, **common), 4),
            f"Recall@{k}": round(pe.recall_at_k(rating_true, rating_pred, **common), 4),
            f"Precision@{k}": round(pe.precision_at_k(rating_true, rating_pred, **common), 4),
            f"MAP@{k}": round(pe.map_at_k(rating_true, rating_pred, **common), 4),
        }


def available() -> bool:
    try:
        _load_lib()
        return True
    except Exception:
        return False
