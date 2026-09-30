"""Driver: sinh toàn bộ dataset + build KG trong một lệnh.

    cd gen_user_data && python generate_all.py

Thứ tự: catalog(listings) -> users -> interactions -> KG.
Sau đó chạy `python run_eval.py` để đánh giá.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catalog import build_catalog, save_catalog, load_catalog  # noqa: E402
from generation.generate_users import generate_users, save_users, _report as report_users  # noqa: E402
from generation.generate_interactions import (  # noqa: E402
    generate_interactions,
    save_interactions,
    _report as report_interactions,
)
from generation.llm_client import LLMClient  # noqa: E402
from generation.enrich import enrich_personas, enrich_descriptions  # noqa: E402

# Giới hạn số listing sinh description bằng LLM (tránh tốn token). 0 = không sinh.
LLM_MAX_LISTINGS_DESC = int(os.getenv("LLM_MAX_LISTINGS_DESC", "150"))


def main(limit_listings: int | None = None):
    llm = LLMClient()
    print(f"[llm] {llm.status()}")

    print("== 1/4 Building listing catalog (real listing_ids) ==")
    catalog = build_catalog(limit=limit_listings)
    seg = {}
    for l in catalog:
        seg[l.budget_group] = seg.get(l.budget_group, 0) + 1
    print(f"  {len(catalog)} listings; segments={ {k: round(v/len(catalog),3) for k,v in seg.items()} }")

    print("\n== 2/4 Generating users ==")
    from catalog import derive_pools
    pools = derive_pools(catalog)   # quận & loại BĐS THẬT -> user preference khớp listing
    users = generate_users(pools=pools)
    if llm.enabled:
        n = enrich_personas(users, llm)
        print(f"  [llm] persona: {n}/{len(users)} user")
    save_users(users)
    report_users(users)

    print("\n== 3/4 Generating interactions ==")
    interactions = generate_interactions(users, catalog)
    save_interactions(interactions)
    report_interactions(interactions)

    # LLM mô tả CHỈ các listing được tương tác (có nghĩa hơn 150 căn đầu ngẫu nhiên).
    if llm.enabled and LLM_MAX_LISTINGS_DESC > 0:
        interacted = {it.listing_id for it in interactions}
        subset = [l for l in catalog if l.listing_id in interacted]
        n = enrich_descriptions(subset, llm, limit=LLM_MAX_LISTINGS_DESC)
        print(f"  [llm] description: {n}/{len(subset)} listing được tương tác "
              f"(giới hạn LLM_MAX_LISTINGS_DESC={LLM_MAX_LISTINGS_DESC})")
    save_catalog(catalog)

    print("\n== 4/5 Similarity matrix -> edges + kiểm chứng hành vi ==")
    import similarity_kg
    similarity_kg.main()

    print("\n== 5/5 Building knowledge graph (gồm cạnh similarity) ==")
    # import trễ để tránh vòng phụ thuộc khi chỉ dùng generator
    from kg.build_kg import build, _write_csv, _write_cypher
    nodes, edges = build(users, catalog, interactions)
    _write_csv(nodes, edges)
    _write_cypher(nodes, edges)
    print(f"  {len(nodes)} nodes, {len(edges)} edges")

    print("\nDone. Chạy `python run_eval.py` để đánh giá.")


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit_listings=lim)
