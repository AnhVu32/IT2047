"""Chuẩn bị input cho workflow Claude-rerank: chia 1055 event thành batch file.

Mỗi batch chứa đủ thông tin để agent chọn 3/10 mà không cần đọc file khác:
user profile rút gọn + query + 10 ứng viên (thuộc tính + matched_features).

    cd gen_user_data && python prep_rerank.py
-> scratchpad/rerank/batch_XXX.json  (+ in ra tổng số batch)
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
# Override with RERANK_DIR env var if you want the batch/out files elsewhere
# (e.g. a Claude Code scratchpad); defaults to a repo-local, gitignored folder
# so the workflow runs the same on any machine after `git pull`.
VER = os.environ.get("RERANK_VERSION", "v2")   # "v2" | "v3"
OUT_DIR = os.environ.get("RERANK_DIR", os.path.join(HERE, "scratchpad", f"rerank_{VER}"))
BATCH = 30


def main():
    events = json.load(open(os.path.join(DATA_DIR, f"recommendation_events_{VER}.json"), encoding="utf-8"))
    users = {u["user_id"]: u for u in json.load(open(os.path.join(DATA_DIR, f"users_{VER}.json"), encoding="utf-8"))}
    listings = {l["listing_id"]: l for l in json.load(open(os.path.join(DATA_DIR, "listings.json"), encoding="utf-8"))}

    records = []
    for ev in events:
        u = users[ev["user_id"]]
        ep = u["explicit_preferences"]
        cands = []
        for r in ev["recommended_items"]:
            l = listings[r["listing_id"]]
            cands.append({
                "listing_id": l["listing_id"], "property_type": l["property_type"],
                "district": l["district"], "price_billion": l["price_billion"],
                "area_sqm": l["area_sqm"], "bedrooms": l["bedrooms"], "bathrooms": l["bathrooms"],
                "amenities": [f for f, v in l["features"].items() if v],
                "matched_features": r["matched_features"],
            })
        records.append({
            "result_set_id": ev["result_set_id"],
            "user": {
                "intent": u["primary_intent"], "budget_range": ep["budget_range"],
                "min_bedrooms": ep["min_bedrooms"],
                "preferred_districts": [d["value"] for d in ep["preferred_districts"]],
                "property_type": [p["value"] for p in ep["property_type"]],
                "liked_amenities": [(a["value"], a["weight"]) for a in ep["liked_amenities"]],
            },
            "query": ev["context"]["raw_query"],
            "candidates": cands,
        })

    os.makedirs(OUT_DIR, exist_ok=True)
    # dọn batch/out cũ
    for f in os.listdir(OUT_DIR):
        if f.startswith(("batch_", "out_")):
            os.remove(os.path.join(OUT_DIR, f))

    n_batch = 0
    for i in range(0, len(records), BATCH):
        chunk = records[i:i + BATCH]
        with open(os.path.join(OUT_DIR, f"batch_{n_batch:03d}.json"), "w", encoding="utf-8") as f:
            json.dump(chunk, f, ensure_ascii=False)
        n_batch += 1

    print(f"[prep] {len(records)} event -> {n_batch} batch ({BATCH}/batch) tại {OUT_DIR}")
    print(f"[prep] N_BATCHES={n_batch}")


if __name__ == "__main__":
    main()
