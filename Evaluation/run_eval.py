"""Giai doan 1 (EVAL_PLAN.md muc 4): live eval — can backend dang chay.

Voi moi trong ~488 event (ground truth v3, ward-tiered — xem
gen_user_data/generation/gen_v3.py): replay raw_query qua HybridSearchService
that (HTTP toi localhost:8001, xem live_client.py) de lay `pred`, roi tinh 25
metric (Nhom A-G, muc 3) so voi `recommended_items` (ground truth) va hanh vi
that trong interactions_v3_claude.json.

Truong hop 1 (chi dung raw_query, khong set filter sidebar): KHONG gui
`filters` len backend — chi gui raw_query text, backend tu suy ra
preference_filters (chi anh huong ranking, khong bao gio loai bo candidate).
Xem docstring fetch_live_results() ben duoi.

    cd Evaluation && python run_eval.py [--limit N] [--k K]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import warnings
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# reco_metrics_lib is an unmodified vendored copy (see NOTICE.md) using a
# pandas .agg({...}) dict pattern that's deprecated but still correct on the
# pandas version here — silence the noise instead of patching vendored code.
warnings.filterwarnings("ignore", category=FutureWarning, module="recommenders.*")

import adapters as A
import config as C
import live_client

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "reco_metrics_lib"))
from recommenders.evaluation import python_evaluation as pe  # noqa: E402


def fetch_live_results(events, limit=None):
    """Call the live backend for each event's raw_query. Returns
    {result_set_id: [{listing_id, score, rank}, ...]} plus per-event errors.

    Sends NO explicit `filters` — only `raw_query` text. The backend's own
    parser (rule-based + LLM) infers district/price/bedrooms from the text
    into `preference_filters`, which only affects ranking and never excludes
    candidates (backend/src/search/query_parser.py, PR "feat/llm-agentic").
    Explicit `filters` still go to `hard_filters`, a strict SQL AND with no
    fallback — sending them would let a single bad value zero out results,
    making the run un-scoreable.
    """
    subset = events[:limit] if limit else events
    live_results = {}
    errors = []
    started = time.time()
    for i, ev in enumerate(subset, 1):
        k = A.ground_truth_k(ev)
        try:
            live_results[ev["result_set_id"]] = live_client.search(
                ev["context"]["raw_query"], top_k=k,
            )
        except Exception as exc:  # noqa: BLE001 — one bad query must not kill the run
            errors.append({"result_set_id": ev["result_set_id"], "error": str(exc)})
        if i % 50 == 0 or i == len(subset):
            elapsed = time.time() - started
            print(f"[eval] queried {i}/{len(subset)} ({elapsed:.1f}s, {elapsed / i:.2f}s/query)")
    if errors:
        print(f"[eval] {len(errors)}/{len(subset)} queries failed (see results json for detail)")
    return live_results, errors


def safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def group_a_ranking(true_df, pred_df, k):
    kwargs = dict(rating_true=true_df, rating_pred=pred_df, col_user="userID",
                  col_item="itemID", col_prediction="prediction", relevancy_method="top_k", k=k)
    return {
        f"precision_at_{k}": safe(pe.precision_at_k, **kwargs),
        f"recall_at_{k}": safe(pe.recall_at_k, **kwargs),
        f"ndcg_at_{k}": safe(pe.ndcg_at_k, **{**kwargs, "score_type": "raw"}),
        f"map_at_{k}": safe(pe.map_at_k, **kwargs),
        f"mrr_at_{k}": safe(pe.mrr_at_k, **kwargs),
        f"arhr_at_{k}": safe(pe.arhr_at_k, **kwargs),
        f"average_precision_at_{k}": safe(pe.average_precision_at_k, **kwargs),
        f"average_recall_at_{k}": safe(pe.average_recall_at_k, **kwargs),
    }


def group_bc_rating_classification(pair_df):
    if pair_df.empty:
        return {"note": "no interaction had its listing_id present in that event's live results"}
    true_rating = pair_df[["userID", "itemID"]].assign(rating=pair_df["true_rating"])
    true_label = pair_df[["userID", "itemID"]].assign(rating=pair_df["positive_label"])
    pred = pair_df[["userID", "itemID"]].assign(prediction=pair_df["pred_score"])
    kwargs = dict(col_user="userID", col_item="itemID", col_rating="rating", col_prediction="prediction")
    out = {
        "n_pairs": int(len(pair_df)),
        "rmse": safe(pe.rmse, true_rating, pred, **kwargs),
        "mae": safe(pe.mae, true_rating, pred, **kwargs),
        "mse": safe(pe.mse, true_rating, pred, **kwargs),
        "rsquared": safe(pe.rsquared, true_rating, pred, **kwargs),
        "exp_var": safe(pe.exp_var, true_rating, pred, **kwargs),
        "mape": safe(pe.mape, true_rating, pred, **kwargs),
    }
    if pair_df["positive_label"].nunique() < 2:
        out["auc"] = out["logloss"] = "skipped: only one class present in positive_label"
    else:
        out["auc"] = safe(pe.auc, true_label, pred, **kwargs)
        out["logloss"] = safe(pe.logloss, true_label, pred, **kwargs)
    return out


def group_d_diversity(train_df, reco_df, feat_df):
    # Restrict item_feature_df to items actually in reco_df — see
    # adapters.filter_item_features docstring for why this matters (perf).
    scoped_feat_df = A.filter_item_features(feat_df, reco_df["itemID"])
    kwargs = dict(train_df=train_df, reco_df=reco_df, item_feature_df=scoped_feat_df,
                  item_sim_measure="item_feature_vector", col_user="userID", col_item="itemID")
    return {"diversity": safe(pe.diversity, **kwargs)}


def group_e_novelty(train_df, reco_df):
    kwargs = dict(train_df=train_df, reco_df=reco_df, col_user="userID", col_item="itemID")
    return {"novelty": safe(pe.novelty, **kwargs)}


def group_f_serendipity(events, live_results, interactions_train_df, feat_df):
    events_by_user = A.events_by_user(events)
    reco_rows = []
    for user_id, user_events in events_by_user.items():
        seen = set()
        for ev in user_events:
            for item in live_results.get(ev["result_set_id"], []):
                key = (user_id, int(item["listing_id"]))
                if key not in seen:
                    seen.add(key)
                    reco_rows.append({"userID": user_id, "itemID": int(item["listing_id"])})
    if not reco_rows:
        return {"note": "no live results available for any user"}
    reco_df = pd.DataFrame(reco_rows).drop_duplicates()

    before = len(reco_df)
    reco_df = reco_df.merge(interactions_train_df, on=["userID", "itemID"], how="left", indicator=True)
    reco_df = reco_df[reco_df["_merge"] == "left_only"].drop(columns="_merge")
    dropped = before - len(reco_df)

    # user_item_serendipity() also needs similarity between reco items and
    # each user's OWN interacted items, so scope to both sets — see
    # adapters.filter_item_features docstring for why this matters (perf).
    relevant_ids = pd.concat([reco_df["itemID"], interactions_train_df["itemID"]]).unique()
    scoped_feat_df = A.filter_item_features(feat_df, relevant_ids)
    kwargs = dict(train_df=interactions_train_df, reco_df=reco_df, item_feature_df=scoped_feat_df,
                  item_sim_measure="item_feature_vector", col_user="userID", col_item="itemID")
    result = safe(pe.serendipity, **kwargs)
    return {
        "serendipity": result,
        "n_users": int(reco_df["userID"].nunique()),
        "dropped_already_interacted_pairs": int(dropped),
    }


def group_g_coverage(catalog_df, reco_df):
    kwargs = dict(train_df=catalog_df, reco_df=reco_df, col_user="userID", col_item="itemID")
    return {
        "catalog_coverage": safe(pe.catalog_coverage, **kwargs),
        "distributional_coverage": safe(pe.distributional_coverage, **kwargs),
    }


def breakdown_by(events, true_df, pred_df, users, key_fn, k):
    """NDCG@k per breakdown value (e.g. per segment / per intent)."""
    rsid_to_key = {}
    for ev in events:
        user = users.get(ev.get("user_id"))
        if user is not None:
            rsid_to_key[ev["result_set_id"]] = key_fn(user)
    out = {}
    for value in sorted(set(rsid_to_key.values())):
        rsids = {rsid for rsid, v in rsid_to_key.items() if v == value}
        t = true_df[true_df["userID"].isin(rsids)]
        p = pred_df[pred_df["userID"].isin(rsids)]
        if t.empty or p.empty:
            continue
        out[value] = safe(pe.ndcg_at_k, rating_true=t, rating_pred=p, col_user="userID",
                           col_item="itemID", col_prediction="prediction", relevancy_method="top_k",
                           k=k, score_type="raw")
    return out


def per_query_detail(used_events, live_results):
    """Raw_query + ground truth + live pred for every event, so results can be
    inspected/compared by hand instead of only reading aggregate metrics.
    """
    rows = []
    for ev in used_events:
        rsid = ev["result_set_id"]
        gt_items = ev["recommended_items"]
        pred_items = live_results[rsid]
        gt_ids = [int(it["listing_id"]) for it in gt_items]
        pred_ids = [it["listing_id"] for it in pred_items]
        hit_ids = [lid for lid in gt_ids if lid in pred_ids]
        rows.append({
            "result_set_id": rsid,
            "user_id": ev.get("user_id"),
            "raw_query": ev["context"]["raw_query"],
            # filters_applied describes what ground truth was built for — NOT
            # what was sent to the live system (see fetch_live_results docstring:
            # no explicit filters are sent, only raw_query text).
            "filters_applied": ev["context"].get("filters_applied"),
            "ground_truth": [{"listing_id": it["listing_id"], "rank": it["rank"], "score": it["score"]}
                              for it in gt_items],
            "llm_output_picks": [int(k) for k in ev["llm_output"]],
            "live_pred": pred_items,
            "n_hits": len(hit_ids),
            "hit_listing_ids": hit_ids,
            "hit_positions_in_pred": {lid: pred_ids.index(lid) for lid in hit_ids},
        })
    return rows


def write_per_query_csv(rows, path):
    import csv
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["result_set_id", "user_id", "raw_query", "n_hits", "hit_listing_ids",
                          "ground_truth_listing_ids", "live_pred_listing_ids"])
        for r in rows:
            writer.writerow([
                r["result_set_id"], r["user_id"], r["raw_query"], r["n_hits"],
                ";".join(map(str, r["hit_listing_ids"])),
                ";".join(str(g["listing_id"]) for g in r["ground_truth"]),
                ";".join(str(p["listing_id"]) for p in r["live_pred"]),
            ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Only replay the first N events (smoke test)")
    parser.add_argument("--k", type=int, default=None, help="Override k (default: ground-truth size per event)")
    parser.add_argument("--ids", type=str, default=None,
                         help="Comma-separated result_set_id list — only replay these events "
                              "(e.g. to retry ones that errored in a previous run)")
    args = parser.parse_args()

    if not live_client.health_check():
        print(f"[eval] backend not reachable at {C.BACKEND_URL} — start it first (docker compose up -d backend)")
        sys.exit(1)

    events = A.load_events()
    if args.ids:
        id_set = {i.strip() for i in args.ids.split(",") if i.strip()}
        events = [ev for ev in events if ev["result_set_id"] in id_set]
        missing = id_set - {ev["result_set_id"] for ev in events}
        print(f"[eval] --ids filter: {len(events)}/{len(id_set)} matched"
              + (f" (not found: {sorted(missing)})" if missing else ""))
    interactions = A.load_interactions()
    users = A.load_users()
    listings = A.load_listings()

    k_counts = Counter(A.ground_truth_k(ev) for ev in events)
    k = args.k or max(k_counts)
    print(f"[eval] ground-truth size per event: {dict(k_counts)} -> using k={k}")

    live_results, errors = fetch_live_results(events, limit=args.limit)
    used_events = events[: args.limit] if args.limit else events
    used_events = [ev for ev in used_events if ev["result_set_id"] in live_results]
    print(f"[eval] usable events (live query succeeded): {len(used_events)}/{len(events) if not args.limit else args.limit}")

    true_df = A.ground_truth_df(used_events)
    pred_df = A.pred_df_by_query(live_results)
    feat_df = A.item_feature_df(listings)
    interactions_train_df = A.interactions_train_df(interactions)
    catalog_df = A.catalog_universe_df(listings)
    pair_df = A.interaction_rating_pairs(interactions, live_results)
    reco_df_query = pred_df[["userID", "itemID"]].drop_duplicates()

    print("[eval] computing metrics...")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "backend_url": C.BACKEND_URL,
        "k": k,
        "n_events_total": len(events),
        "n_events_used": len(used_events),
        "n_query_errors": len(errors),
        "group_a_ranking": group_a_ranking(true_df, pred_df, k),
        "group_bc_rating_classification": group_bc_rating_classification(pair_df),
        "group_d_diversity": group_d_diversity(interactions_train_df, reco_df_query, feat_df),
        "group_e_novelty": group_e_novelty(interactions_train_df, reco_df_query),
        "group_f_serendipity": group_f_serendipity(used_events, live_results, interactions_train_df, feat_df),
        "group_g_coverage": group_g_coverage(catalog_df, reco_df_query),
        "breakdown_ndcg_by_segment": breakdown_by(used_events, true_df, pred_df, users, lambda u: u["segment"], k),
        "breakdown_ndcg_by_intent": breakdown_by(used_events, true_df, pred_df, users, lambda u: u["primary_intent"], k),
        "query_errors": errors[:20],
    }

    per_query = per_query_detail(used_events, live_results)

    # One subfolder per run (timestamp + event count) instead of flat files —
    # keeps results/ navigable across many runs (smoke tests, partial, full).
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    run_dir = C.RESULTS_DIR / f"{stamp}_n{len(used_events)}"
    run_dir.mkdir(parents=True, exist_ok=True)

    out_path = run_dir / "summary.json"
    json.dump(report, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2, default=float)
    print(f"[eval] written -> {out_path}")

    per_query_path = run_dir / "per_query.json"
    json.dump(per_query, open(per_query_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2, default=float)
    print(f"[eval] written -> {per_query_path} ({len(per_query)} queries: raw_query + ground_truth + live_pred + hits)")

    csv_path = run_dir / "per_query.csv"
    write_per_query_csv(per_query, csv_path)
    print(f"[eval] written -> {csv_path} (flat view for spreadsheet)")

    print("\n=== Nhom A - Ranking/Accuracy ===")
    for k_, v in report["group_a_ranking"].items():
        print(f"  {k_}: {v}")
    print("\n=== Nhom B/C - Rating/Classification ===")
    for k_, v in report["group_bc_rating_classification"].items():
        print(f"  {k_}: {v}")
    print("\n=== Nhom D/E/F/G - Diversity/Novelty/Serendipity/Coverage ===")
    for group in ("group_d_diversity", "group_e_novelty", "group_f_serendipity", "group_g_coverage"):
        for k_, v in report[group].items():
            print(f"  {group}.{k_}: {v}")
    print("\n=== Breakdown NDCG theo segment ===")
    for k_, v in report["breakdown_ndcg_by_segment"].items():
        print(f"  {k_}: {v}")
    print("\n=== Breakdown NDCG theo intent ===")
    for k_, v in report["breakdown_ndcg_by_intent"].items():
        print(f"  {k_}: {v}")


if __name__ == "__main__":
    main()
