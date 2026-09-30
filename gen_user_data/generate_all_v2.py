"""Driver sinh dữ liệu SCHEMA V2 (song song v1, KHÔNG xoá data cũ).

    cd gen_user_data && python generate_all_v2.py

Cần: data/listings.json (chạy generate_all.py / catalog.py trước) — listings thật
dùng chung cho cả v1 & v2. Sinh ra:
  data/users_v2.json · data/recommendation_events_v2.json · data/interactions_v2.json

Bật LLM: USE_LLM=1 + GROQ_API_KEY (sinh raw_query + explanation top-3).
"""
from __future__ import annotations

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catalog import build_catalog, save_catalog, load_catalog, LISTINGS_PATH  # noqa: E402
from generation.llm_client import LLMClient  # noqa: E402
from generation.gen_v2 import (  # noqa: E402
    generate_users_v2,
    generate_events_interactions_v2,
    save,
)


def main():
    llm = LLMClient()
    print(f"[llm] {llm.status()}")

    if os.path.exists(LISTINGS_PATH):
        catalog = load_catalog()
        print(f"== dùng listings.json sẵn có: {len(catalog)} listing thật ==")
    else:
        print("== chưa có listings.json -> build từ Final_Data.csv ==")
        catalog = build_catalog()
        save_catalog(catalog)

    print("\n== 1/2 Users v2 ==")
    users = generate_users_v2(catalog)
    save(users, "users_v2.json")
    seg = Counter(u.segment for u in users)
    intent = Counter(u.primary_intent for u in users)
    # đếm demographic đã được suy luận (confidence>0)
    known = Counter()
    for u in users:
        for f in ("age_group", "marital_status", "children", "income_level"):
            if getattr(u.inferred_attributes, f).value is not None:
                known[f] += 1
    print(f"  {len(users)} users -> data/users_v2.json")
    print(f"  segment: {dict(seg)}")
    print(f"  inferred đã biết: { {k: f'{v}/{len(users)}' for k, v in known.items()} }")

    print("\n== 2/2 RecommendationEvents + Interactions v2 ==")
    events, interactions = generate_events_interactions_v2(users, catalog, llm=llm)
    save(events, "recommendation_events_v2.json")
    save(interactions, "interactions_v2.json")
    act = Counter(it.action_type for it in interactions)
    n_llm = sum(len(e.llm_output) for e in events)
    print(f"  {len(events)} events -> data/recommendation_events_v2.json")
    print(f"    (top-{len(events[0].recommended_items) if events else 0}/event · llm_output tổng {n_llm} explanation, top-3/event)")
    print(f"  {len(interactions)} interactions -> data/interactions_v2.json")
    print(f"    action: {dict(act)}")
    # kiểm FK
    rs_ids = {e.result_set_id for e in events}
    dangling = sum(1 for it in interactions if it.result_set_id not in rs_ids)
    print(f"    interaction có result_set_id hợp lệ: {len(interactions) - dangling}/{len(interactions)}")

    print("\nDone. Data v1 (users.json/interactions.json) giữ nguyên; v2 nằm ở *_v2.json.")


if __name__ == "__main__":
    main()
