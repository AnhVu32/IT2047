"""Driver sinh dữ liệu v3 (Plan A — ground truth theo phường/xã).

    cd gen_user_data && python generate_all_v3.py

Giữ nguyên v2. Sinh: data/users_v3.json · recommendation_events_v3.json ·
interactions_v3.json. Cần data/listings.json (chạy catalog/generate_all trước).
Bật LLM: USE_LLM=1 + GROQ_API_KEY.
"""
from __future__ import annotations

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catalog import build_catalog, save_catalog, load_catalog, LISTINGS_PATH  # noqa: E402
from generation.llm_client import LLMClient  # noqa: E402
from generation.gen_v2 import generate_users_v2, save  # noqa: E402
from generation.gen_v3 import generate_events_interactions_v3  # noqa: E402


def main():
    llm = LLMClient()
    print(f"[llm] {llm.status()}")

    if os.path.exists(LISTINGS_PATH):
        catalog = load_catalog()
        print(f"== listings.json: {len(catalog)} listing thật ==")
    else:
        print("== build listings từ Final_Data.csv ==")
        catalog = build_catalog()
        save_catalog(catalog)

    print("\n== 1/2 Users v3 ==")
    users = generate_users_v2(catalog)      # schema không đổi -> dùng lại
    save(users, "users_v3.json")
    print(f"  {len(users)} users -> data/users_v3.json")

    print("\n== 2/2 Events + Interactions v3 (ward-tiered ground truth) ==")
    events, interactions = generate_events_interactions_v3(users, catalog, llm=llm)
    save(events, "recommendation_events_v3.json")
    save(interactions, "interactions_v3.json")

    act = Counter(it.action_type for it in interactions)
    rs_ids = {e.result_set_id for e in events}
    dangling = sum(1 for it in interactions if it.result_set_id not in rs_ids)
    print(f"  {len(events)} events -> data/recommendation_events_v3.json")
    print(f"  {len(interactions)} interactions -> data/interactions_v3.json  action={dict(act)}")
    print(f"  interaction FK hợp lệ: {len(interactions) - dangling}/{len(interactions)}")
    print("\nDone. v2 giữ nguyên; v3 nằm ở *_v3.json.")


if __name__ == "__main__":
    main()
