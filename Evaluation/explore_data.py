"""Read-only exploration of the datasets that back the evaluation plan.

Only reads files under Data/ and gen_user_data/ (repo root, one level up from
this Evaluation/ folder) — writes nothing outside Evaluation/.

    cd Evaluation && python explore_data.py
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
GEN_DATA = os.path.join(REPO_ROOT, "gen_user_data", "data")


def main() -> None:
    users = json.load(open(os.path.join(GEN_DATA, "users_v2.json"), encoding="utf-8"))
    inter = json.load(open(os.path.join(GEN_DATA, "interactions_v2_claude.json"), encoding="utf-8"))
    events = json.load(open(os.path.join(GEN_DATA, "recommendation_events_v2_claude.json"), encoding="utf-8"))
    listings = json.load(open(os.path.join(GEN_DATA, "listings.json"), encoding="utf-8"))

    print("users_v2.json:", len(users))
    print("interactions_v2_claude.json:", len(inter))
    print("recommendation_events_v2_claude.json:", len(events))
    print("listings.json (catalog):", len(listings))

    lst_ids = {l["listing_id"] for l in listings}
    print("unique listing ids in catalog:", len(lst_ids))

    ev_ids = set()
    for e in events:
        for r in e["recommended_items"]:
            ev_ids.add(r["listing_id"])
    print("unique listing ids referenced in recommendation_events:", len(ev_ids))
    print("all referenced ids inside catalog?", ev_ids.issubset(lst_ids))

    picked_ids = set()
    for e in events:
        picked_ids.update(int(k) for k in e["llm_output"])
    print("unique listing ids ever picked as ground-truth top-3:", len(picked_ids))

    algo_versions = {}
    for e in events:
        algo_versions[e["algorithm_version"]] = algo_versions.get(e["algorithm_version"], 0) + 1
    print("algorithm_version breakdown:", algo_versions)

    action_counts = {}
    for it in inter:
        action_counts[it["action_type"]] = action_counts.get(it["action_type"], 0) + 1
    print("interaction action_type breakdown:", action_counts)

    with_rsid = sum(1 for it in inter if it.get("result_set_id"))
    print(f"interactions with result_set_id (linked to a recommendation event): {with_rsid}/{len(inter)}")

    print()
    print("sample listing (catalog):")
    print(json.dumps(listings[0], ensure_ascii=False, indent=2)[:1200])

    print()
    print("sample user (v2):")
    print(json.dumps(users[0], ensure_ascii=False, indent=2)[:1200])


if __name__ == "__main__":
    main()
