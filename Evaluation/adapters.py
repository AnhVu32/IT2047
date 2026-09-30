"""JSON ground truth -> pandas DataFrames matching the recommenders.evaluation
API contract (col_user/col_item/col_rating/col_prediction).

Ground truth semantics (see EVAL_PLAN.md mục 0): `recommended_items` (10/event,
ranked by a deterministic content-match score between user profile and
listing attributes — relevance_v2() in v2, content_score() in v3's
ward-tiered generator) IS the ground truth. `llm_output` is a downstream
explain/display layer, not used as a relevance label here.

Two different "col_user" keyings are used on purpose:
  - result_set_id (one event = one query) for Groups A/D/E/G: a query-level
    evaluation, matching how the dataset is actually query-shaped.
  - real user_id for Group F (serendipity): that metric joins reco_df against
    a SPECIFIC user's own interaction history, so it only makes sense keyed
    by the real user, not by query.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

import config as C


def load_events() -> List[dict]:
    return json.load(open(C.EVENTS_FILE, encoding="utf-8"))


def load_interactions() -> List[dict]:
    return json.load(open(C.INTERACTIONS_FILE, encoding="utf-8"))


def load_users() -> Dict[str, dict]:
    users = json.load(open(C.USERS_FILE, encoding="utf-8"))
    return {u["user_id"]: u for u in users}


def load_listings() -> Dict[int, dict]:
    listings = json.load(open(C.LISTINGS_FILE, encoding="utf-8"))
    return {l["listing_id"]: l for l in listings}


def ground_truth_k(event: dict) -> int:
    """Number of ground-truth items for this event — read from the data, never hardcoded."""
    return len(event["recommended_items"])


def ground_truth_df(events: List[dict]) -> pd.DataFrame:
    """true: (userID=result_set_id, itemID=listing_id, rating=relevance score)."""
    rows = []
    for ev in events:
        for item in ev["recommended_items"]:
            rows.append({
                "userID": ev["result_set_id"],
                "itemID": int(item["listing_id"]),
                "rating": float(item["score"]),
            })
    return pd.DataFrame(rows)


def pred_df_by_query(live_results: Dict[str, List[dict]]) -> pd.DataFrame:
    """pred: (userID=result_set_id, itemID=listing_id, prediction=final_score),
    built from live_client.search() output keyed by result_set_id.
    """
    rows = []
    for result_set_id, items in live_results.items():
        for item in items:
            rows.append({
                "userID": result_set_id,
                "itemID": int(item["listing_id"]),
                "prediction": float(item["score"]),
            })
    return pd.DataFrame(rows)


def item_feature_df(listings: Dict[int, dict]) -> pd.DataFrame:
    """(itemID, features=np.array) for diversity's item_feature_vector mode.

    149/3030 listings have every amenity flag false (an all-zero vector),
    which makes the library's cosine similarity divide by zero
    (np.linalg.norm(x.f1, 2) == 0). Appending a constant bias dimension (1.0)
    to every vector guarantees a non-zero norm without touching the vendored
    library, and barely perturbs cosine similarity between two genuinely
    non-zero vectors.
    """
    rows = []
    for listing_id, listing in listings.items():
        features = listing.get("features") or {}
        keys = sorted(features.keys())
        vector = np.array([1.0 if features[k] else 0.0 for k in keys] + [1.0])
        rows.append({"itemID": int(listing_id), "features": vector})
    return pd.DataFrame(rows)


def filter_item_features(feat_df: pd.DataFrame, item_ids) -> pd.DataFrame:
    """_get_item_feature_similarity() (python_evaluation.py) cross-joins
    item_feature_df with itself UNCONDITIONALLY (df1 x df2 on a constant key)
    before filtering down to the pairs it actually needs — passing the full
    3030-listing catalog makes it build a 3030*3030 ~= 9.2M row DataFrame and
    .apply() a Python-level dot product over every row, which pegs a CPU core
    for minutes even for a handful of events. Restricting item_feature_df to
    only the listing_ids actually in play (reco + train items) keeps that
    cross join small (O(n^2) on a few hundred/thousand items, not 3030).
    """
    ids = {int(i) for i in item_ids}
    return feat_df[feat_df["itemID"].isin(ids)].reset_index(drop=True)


def interactions_train_df(interactions: List[dict]) -> pd.DataFrame:
    """Real behavior history, keyed by real user_id — (userID, itemID), deduped."""
    rows = [{"userID": it["user_id"], "itemID": int(it["listing_id"])} for it in interactions]
    return pd.DataFrame(rows).drop_duplicates().reset_index(drop=True)


def catalog_universe_df(listings: Dict[int, dict]) -> pd.DataFrame:
    """One row per catalog listing, for catalog_coverage/distributional_coverage's
    `train_df` universe (distinct from interactions_train_df — see EVAL_PLAN.md
    mục 3, Nhóm G). userID is a placeholder that never collides with a real
    result_set_id/user_id, only present to satisfy the library's column checks.
    """
    return pd.DataFrame({
        "userID": ["_catalog_universe_"] * len(listings),
        "itemID": [int(lid) for lid in listings],
    })


def interaction_rating_pairs(
    interactions: List[dict],
    live_results: Dict[str, List[dict]],
) -> pd.DataFrame:
    """For Group B/C: join real behavior (implicit_score, positive-action label)
    against the live system's score for the SAME (result_set_id, listing_id).
    Only interactions whose listing was actually present in that event's live
    results can be scored — the rest are dropped (reported by the caller).
    """
    pred_lookup: Dict[tuple, float] = {}
    for result_set_id, items in live_results.items():
        for item in items:
            pred_lookup[(result_set_id, int(item["listing_id"]))] = float(item["score"])

    rows = []
    for it in interactions:
        rsid = it.get("result_set_id")
        if not rsid:
            continue
        key = (rsid, int(it["listing_id"]))
        if key not in pred_lookup:
            continue
        rows.append({
            "userID": rsid,
            "itemID": int(it["listing_id"]),
            "true_rating": float(it["implicit_score"]),
            "positive_label": 1.0 if it["action_type"] in C.POSITIVE_ACTIONS else 0.0,
            "pred_score": pred_lookup[key],
        })
    return pd.DataFrame(rows)


def events_by_user(events: List[dict]) -> Dict[str, List[dict]]:
    out: Dict[str, List[dict]] = {}
    for ev in events:
        uid = ev.get("user_id")
        if uid:
            out.setdefault(uid, []).append(ev)
    return out
