"""Tính lại metric từ live predictions ĐÃ CÓ (per_query.json của 1 lần chạy
run_eval.py trước đó) — KHÔNG gọi lại backend/LLM, nên chạy trong vài giây
thay vì vài giờ.

Dùng khi chỉ cần thử interactions/users khác (vd interactions_v4_claude.json
mới) mà ground truth (recommended_items) và live predictions không đổi —
đúng use case này vì Nhóm B/C/E/F đọc `interactions`, còn Nhóm A
(precision/recall/ndcg/map) chỉ phụ thuộc true_df/pred_df nên SẼ KHÔNG đổi
so với lần chạy gốc (in lại ở đây chỉ để đối chiếu).

    cd Evaluation && python recompute_from_cache.py --run-dir results/<timestamp>_n<N> [--interactions-file ...]

`--run-dir` chấp nhận nhiều thư mục (phân tách bởi dấu phẩy) — dùng khi
ghép 1 run gốc với 1 run retry (vd các event từng lỗi, chạy lại riêng qua
`run_eval.py --ids ...`) thành 1 báo cáo đầy đủ duy nhất.
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning, module="recommenders.*")

import adapters as A
import config as C

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "reco_metrics_lib"))

from run_eval import (  # noqa: E402 — tái dùng đúng hàm tính metric của run_eval.py
    group_a_ranking, group_bc_rating_classification, group_d_diversity,
    group_e_novelty, group_f_serendipity, group_g_coverage, breakdown_by,
    per_query_detail, write_per_query_csv,
)


def load_cached_live_results(run_dirs: list[Path]) -> dict:
    """Dựng lại live_results {result_set_id: [{listing_id, score, rank}, ...]}
    từ per_query.json của 1 hoặc nhiều lần run_eval.py trước — nguồn dữ liệu
    duy nhất thay thế cho việc gọi lại backend. Nhiều run_dir được GỘP (union
    theo result_set_id); dir sau đè dir trước nếu trùng id."""
    live_results: dict = {}
    for run_dir in run_dirs:
        rows = json.load(open(run_dir / "per_query.json", encoding="utf-8"))
        live_results.update({r["result_set_id"]: r["live_pred"] for r in rows})
    return live_results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True,
                         help="Thư mục kết quả run_eval.py trước (chứa per_query.json); "
                              "nhiều thư mục thì phân tách bởi dấu phẩy để gộp")
    parser.add_argument("--out-dir", default=None,
                         help="Thư mục ghi kết quả (mặc định: results/<timestamp>_n<N>_recomputed)")
    parser.add_argument("--interactions-file", default=None,
                         help="Đường dẫn interactions khác (mặc định: config.INTERACTIONS_FILE)")
    parser.add_argument("--k", type=int, default=None)
    args = parser.parse_args()

    run_dirs = [Path(p.strip()) for p in args.run_dir.split(",") if p.strip()]
    live_results = load_cached_live_results(run_dirs)
    print(f"[recompute] nạp {len(live_results)} live prediction từ {len(run_dirs)} thư mục "
          f"({', '.join(str(d) for d in run_dirs)}) — không gọi backend")

    events = A.load_events()
    interactions_path = Path(args.interactions_file) if args.interactions_file else C.INTERACTIONS_FILE
    interactions = json.load(open(interactions_path, encoding="utf-8"))
    print(f"[recompute] interactions: {interactions_path} ({len(interactions)} dòng)")
    users = A.load_users()
    listings = A.load_listings()

    used_events = [ev for ev in events if ev["result_set_id"] in live_results]
    print(f"[recompute] usable events: {len(used_events)}/{len(events)}")

    k_counts = Counter(A.ground_truth_k(ev) for ev in used_events)
    k = args.k or max(k_counts)

    true_df = A.ground_truth_df(used_events)
    pred_df = A.pred_df_by_query(live_results)
    feat_df = A.item_feature_df(listings)
    interactions_train_df = A.interactions_train_df(interactions)
    catalog_df = A.catalog_universe_df(listings)
    pair_df = A.interaction_rating_pairs(interactions, live_results)
    reco_df_query = pred_df[["userID", "itemID"]].drop_duplicates()

    print("[recompute] computing metrics...")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_run_dirs": [str(d) for d in run_dirs],
        "interactions_file": str(interactions_path),
        "k": k,
        "n_events_total": len(events),
        "n_events_used": len(used_events),
        "group_a_ranking": group_a_ranking(true_df, pred_df, k),
        "group_bc_rating_classification": group_bc_rating_classification(pair_df),
        "group_d_diversity": group_d_diversity(interactions_train_df, reco_df_query, feat_df),
        "group_e_novelty": group_e_novelty(interactions_train_df, reco_df_query),
        "group_f_serendipity": group_f_serendipity(used_events, live_results, interactions_train_df, feat_df),
        "group_g_coverage": group_g_coverage(catalog_df, reco_df_query),
        "breakdown_ndcg_by_segment": breakdown_by(used_events, true_df, pred_df, users, lambda u: u["segment"], k),
        "breakdown_ndcg_by_intent": breakdown_by(used_events, true_df, pred_df, users, lambda u: u["primary_intent"], k),
    }

    per_query = per_query_detail(used_events, live_results)

    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        out_dir = C.RESULTS_DIR / f"{stamp}_n{len(used_events)}_recomputed"
    out_dir.mkdir(parents=True, exist_ok=True)
    json.dump(report, open(out_dir / "summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2, default=float)
    json.dump(per_query, open(out_dir / "per_query.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2, default=float)
    write_per_query_csv(per_query, out_dir / "per_query.csv")
    print(f"[recompute] written -> {out_dir}")

    print("\n=== Nhom A - Ranking/Accuracy (KHÔNG đổi so với run gốc — chỉ phụ thuộc ground truth + live predictions) ===")
    for k_, v in report["group_a_ranking"].items():
        print(f"  {k_}: {v}")
    print("\n=== Nhom B/C - Rating/Classification (tính lại theo interactions mới) ===")
    for k_, v in report["group_bc_rating_classification"].items():
        print(f"  {k_}: {v}")
    print("\n=== Nhom D/E/F/G ===")
    for group in ("group_d_diversity", "group_e_novelty", "group_f_serendipity", "group_g_coverage"):
        for k_, v in report[group].items():
            print(f"  {group}.{k_}: {v}")


if __name__ == "__main__":
    main()
