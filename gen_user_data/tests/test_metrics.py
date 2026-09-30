"""Unit test metrics: so kết quả với ví dụ tính tay.

Chạy: cd gen_user_data && python -m pytest tests/ -q
Hoặc không có pytest: python tests/test_metrics.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from metrics import (  # noqa: E402
    average_precision,
    cosine_similarity,
    dcg_at_k,
    hit_rate_at_k,
    jaccard_similarity,
    map_at_k,
    mrr,
    ndcg_at_k,
    recall_at_k,
)
from metrics.ranking import reciprocal_rank  # noqa: E402


def approx(a, b, tol=1e-6):
    return abs(a - b) < tol


def test_dcg_and_ndcg():
    # relevance gains: item A=3, B=2, C=3, D=0, E=1
    rel = {"A": 3, "B": 2, "C": 3, "D": 0, "E": 1}
    ranked = ["A", "B", "C", "D", "E"]
    # DCG = 3/log2(2) + 2/log2(3) + 3/log2(4) + 0 + 1/log2(6)
    expected_dcg = 3 + 2 / math.log2(3) + 3 / 2 + 1 / math.log2(6)
    assert approx(dcg_at_k(ranked, rel, 5), expected_dcg)
    # NDCG với ranking hoàn hảo (theo gain) != 1 vì thứ tự đã gần tối ưu
    assert 0.9 < ndcg_at_k(ranked, rel, 5) <= 1.0
    # NDCG của ranking lý tưởng = 1.0
    ideal = ["A", "C", "B", "E", "D"]
    assert approx(ndcg_at_k(ideal, rel, 5), 1.0)


def test_ndcg_empty_relevance():
    assert ndcg_at_k(["A", "B"], {}, 5) == 0.0


def test_reciprocal_rank_and_mrr():
    assert approx(reciprocal_rank(["A", "B", "C"], {"C"}), 1 / 3)
    assert reciprocal_rank(["A", "B"], {"Z"}) == 0.0
    # MRR: q1 relevant tại rank1 (1.0), q2 relevant tại rank2 (0.5) -> 0.75
    ranked = [["A", "B"], ["X", "Y"]]
    relev = [{"A"}, {"Y"}]
    assert approx(mrr(ranked, relev), 0.75)


def test_hit_rate_and_recall():
    ranked = ["A", "B", "C", "D"]
    rel = {"C", "E"}
    assert hit_rate_at_k(ranked, rel, 3) == 1.0   # C ở top-3
    assert hit_rate_at_k(ranked, rel, 2) == 0.0   # top-2 = A,B không có
    assert approx(recall_at_k(ranked, rel, 4), 0.5)  # thu hồi 1/2 relevant


def test_average_precision_and_map():
    # relevant = {A, C}; ranked A,B,C,D
    # hits: rank1 A -> 1/1; rank3 C -> 2/3 ; AP = (1 + 2/3)/2 = 0.8333
    ap = average_precision(["A", "B", "C", "D"], {"A", "C"})
    assert approx(ap, (1 + 2 / 3) / 2)
    m = map_at_k([["A", "B", "C", "D"], ["X", "Y"]], [{"A", "C"}, {"Y"}])
    assert approx(m, (ap + 0.5) / 2)


def test_cosine_and_jaccard():
    assert approx(cosine_similarity([1, 0], [1, 0]), 1.0)
    assert approx(cosine_similarity([1, 0], [0, 1]), 0.0)
    assert cosine_similarity([0, 0], [1, 1]) == 0.0
    assert approx(jaccard_similarity({"pool", "gym"}, {"pool", "park"}), 1 / 3)
    assert jaccard_similarity(set(), set()) == 1.0


def _run_all():
    fns = [v for k, v in globals().items() if k.startswith("test_")]
    passed = 0
    for fn in fns:
        fn()
        passed += 1
        print(f"  PASS {fn.__name__}")
    print(f"\n{passed}/{len(fns)} tests passed.")


if __name__ == "__main__":
    _run_all()
