"""Giai doan 0 (EVAL_PLAN.md muc 4): offline, KHONG tinh metric — chi validate
cau truc ground truth va chuan bi cac DataFrame de Giai doan 1 dung lai.

    cd Evaluation && python run_validate.py
"""
from __future__ import annotations

from collections import Counter

import adapters as A


def main() -> None:
    events = A.load_events()
    interactions = A.load_interactions()
    users = A.load_users()
    listings = A.load_listings()

    print(f"[validate] events={len(events)} interactions={len(interactions)} "
          f"users={len(users)} listings={len(listings)}")

    # --- structural checks -------------------------------------------------
    k_counts = Counter(A.ground_truth_k(ev) for ev in events)
    print(f"[validate] ground-truth size per event (len(recommended_items)): {dict(k_counts)}")

    bad_rank = 0
    bad_subset = 0
    bad_listing_ref = 0
    for ev in events:
        ranks = sorted(item["rank"] for item in ev["recommended_items"])
        if ranks != list(range(len(ranks))):
            bad_rank += 1
        rec_ids = {int(item["listing_id"]) for item in ev["recommended_items"]}
        llm_ids = {int(k) for k in ev["llm_output"]}
        if not llm_ids.issubset(rec_ids):
            bad_subset += 1
        if not rec_ids.issubset(listings.keys()):
            bad_listing_ref += 1
    print(f"[validate] events with non-contiguous rank: {bad_rank}/{len(events)}")
    print(f"[validate] events where llm_output NOT subset of recommended_items: {bad_subset}/{len(events)}")
    print(f"[validate] events referencing listing_id outside catalog: {bad_listing_ref}/{len(events)}")

    orphan_interactions = sum(
        1 for it in interactions
        if it.get("result_set_id") and it["result_set_id"] not in {ev["result_set_id"] for ev in events}
    )
    print(f"[validate] interactions with result_set_id not found in events: {orphan_interactions}/{len(interactions)}")

    missing_user_id = sum(1 for ev in events if not ev.get("user_id"))
    print(f"[validate] events with no user_id (needed for Group F serendipity): {missing_user_id}/{len(events)}")

    # --- build the DataFrames Giai doan 1 will reuse, just to confirm they build ---
    true_df = A.ground_truth_df(events)
    feat_df = A.item_feature_df(listings)
    train_df = A.interactions_train_df(interactions)
    catalog_df = A.catalog_universe_df(listings)
    print(f"[validate] ground_truth_df rows={len(true_df)} "
          f"unique result_set_id={true_df['userID'].nunique()} unique listing={true_df['itemID'].nunique()}")
    print(f"[validate] item_feature_df rows={len(feat_df)} (feature vector length="
          f"{len(feat_df['features'].iloc[0]) if len(feat_df) else 0})")
    print(f"[validate] interactions_train_df rows={len(train_df)} unique real user_id={train_df['userID'].nunique()}")
    print(f"[validate] catalog_universe_df rows={len(catalog_df)}")

    # --- descriptive stats (no metric, just distribution) ------------------
    segment_counts = Counter(users[ev["user_id"]]["segment"] for ev in events if ev.get("user_id") in users)
    intent_counts = Counter(users[ev["user_id"]]["primary_intent"] for ev in events if ev.get("user_id") in users)
    action_counts = Counter(it["action_type"] for it in interactions)
    print(f"[validate] events by user segment: {dict(segment_counts)}")
    print(f"[validate] events by user primary_intent: {dict(intent_counts)}")
    print(f"[validate] interactions by action_type: {dict(action_counts)}")

    events_by_user = A.events_by_user(events)
    print(f"[validate] real users with >=1 event (usable for Group F serendipity): {len(events_by_user)}")

    print("[validate] OK — data is structurally sound. Run run_eval.py next (needs backend up).")


if __name__ == "__main__":
    main()
