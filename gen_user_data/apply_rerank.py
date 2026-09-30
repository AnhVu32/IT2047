"""Áp kết quả Claude-rerank (workflow) vào dữ liệu v2.

Đọc scratchpad/rerank/out_*.json (mỗi file: [{result_set_id, picks:[{listing_id,
explanation, comparison} x3]}]) rồi:
  1. recommendation_events_v2.json: thay llm_output = 3 căn Claude CHỌN (đúng thứ tự,
     kèm explanation/comparison), model_name="claude-agent-rerank",
     algorithm_version="claude_rerank_v2". recommended_items (10) giữ nguyên.
  2. interactions_v2.json: SINH LẠI — user chỉ tương tác trên 3 căn Claude chọn
     (deterministic seed). Event nào thiếu/lỗi pick -> giữ nguyên llm_output cũ.

    cd gen_user_data && python apply_rerank.py
"""
from __future__ import annotations

import json
import math
import os

import numpy as np

from config import distribution_config as C

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
# Must match prep_rerank.py's OUT_DIR (same RERANK_DIR env var override).
VER = os.environ.get("RERANK_VERSION", "v2")   # "v2" | "v3"
RERANK_DIR = os.environ.get("RERANK_DIR", os.path.join(HERE, "scratchpad", f"rerank_{VER}"))
SEED = C.RANDOM_SEED + 7
from datetime import datetime, timedelta, timezone
_WIN = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _load_picks() -> dict:
    picks = {}
    bad = 0
    for f in sorted(os.listdir(RERANK_DIR)):
        if not (f.startswith("out_") and f.endswith(".json")):
            continue
        try:
            for rec in json.load(open(os.path.join(RERANK_DIR, f), encoding="utf-8")):
                picks[rec["result_set_id"]] = rec["picks"]
        except Exception as e:
            bad += 1
            print(f"[apply] lỗi đọc {f}: {e}")
    print(f"[apply] nạp picks cho {len(picks)} event ({bad} file lỗi)")
    return picks


def _dwell(rng):
    d = min(float(rng.lognormal(C.DWELL_LOGNORMAL_MEAN, C.DWELL_LOGNORMAL_SIGMA)), C.DWELL_MAX_SECONDS)
    di = int(round(d))
    return di, di < C.BOUNCE_THRESHOLD_SECONDS


def _implicit(action, dwell):
    return round(C.ACTION_WEIGHTS[action] * min(1.0, math.log1p(dwell) / math.log1p(C.DWELL_SATURATION_SECONDS)), 3)


def main():
    events = json.load(open(os.path.join(DATA_DIR, f"recommendation_events_{VER}.json"), encoding="utf-8"))
    picks = _load_picks()
    if not picks:
        print("[apply] CHƯA có out_*.json — workflow xong chưa? Dừng.")
        return

    rng = np.random.default_rng(SEED)
    applied = 0
    new_interactions = []
    inter_c = 0
    valid_ids_by_ev = {ev["result_set_id"]: {r["listing_id"] for r in ev["recommended_items"]} for ev in events}

    for ev in events:
        rsid = ev["result_set_id"]
        p = picks.get(rsid)
        shown = None
        if p:
            # lọc pick hợp lệ (nằm trong 10 candidate), giữ tối đa 3, đúng thứ tự
            valid = valid_ids_by_ev[rsid]
            seen, clean = set(), []
            for item in p:
                lid = item.get("listing_id")
                if isinstance(lid, int) and lid in valid and lid not in seen:
                    seen.add(lid)
                    clean.append(item)
                if len(clean) >= 3:
                    break
            if clean:
                ev["llm_output"] = {str(it["listing_id"]): {
                    "explanation": str(it.get("explanation", "")).strip(),
                    "comparison": (str(it["comparison"]).strip() if it.get("comparison") else None),
                    "model_name": "claude-agent-rerank"} for it in clean}
                ev["algorithm_version"] = f"claude_rerank_{VER}"
                shown = [it["listing_id"] for it in clean]
                applied += 1
        if shown is None:
            shown = [int(k) for k in ev["llm_output"]]  # fallback giữ nguyên

        # sinh lại interactions trên nhóm shown (1..len(shown))
        rel_by_id = {r["listing_id"]: r["score"] for r in ev["recommended_items"]}
        ts = _WIN + timedelta(seconds=float(rng.uniform(0, 120 * 86400)))
        n_act = int(rng.integers(1, len(shown) + 1))
        rank_w = np.array([(rel_by_id.get(shown[r], 0) + 1e-3) / (r + 1) for r in range(len(shown))])
        rank_w = rank_w / rank_w.sum()
        chosen = rng.choice(len(shown), size=n_act, replace=False, p=rank_w)
        for r in sorted(chosen):
            lid = shown[r]
            dwell, bounce = _dwell(rng)
            strong = min(1.0, rel_by_id.get(lid, 0) * 1.5) * (1.0 / (r + 1)) ** 0.3
            base = np.array([C.ACTION_FREQ[a] for a in ["view", "save", "share", "contact"]])
            w = base * np.array([1.0, 1 + strong, 1 + strong, 1 + strong * 1.4]); w /= w.sum()
            action = str(rng.choice(["view", "save", "share", "contact"], p=w))
            if bounce:
                action = "view"
            new_interactions.append({
                "interaction_id": f"evt_{200000 + inter_c}", "result_set_id": rsid,
                "user_id": ev["user_id"], "session_id": ev["session_id"], "listing_id": int(lid),
                "rank_position": int(r), "action_type": action,
                "timestamp": (ts + timedelta(seconds=float(rng.uniform(5, 600)))).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "dwell_time_seconds": dwell,
                "source": str(rng.choice(list(C.SOURCE_WEIGHTS),
                                         p=np.array(list(C.SOURCE_WEIGHTS.values())) / sum(C.SOURCE_WEIGHTS.values()))),
                "implicit_score": _implicit(action, dwell), "is_bounce": bounce})
            inter_c += 1

    new_interactions.sort(key=lambda x: x["timestamp"])

    # validate lại theo schema v2 trước khi ghi
    import schemas_v2 as V2
    _ = [V2.RecommendationEvent(**e) for e in events]
    _ = [V2.Interaction(**it) for it in new_interactions]

    ev_out = os.path.join(DATA_DIR, f"recommendation_events_{VER}_claude.json")
    it_out = os.path.join(DATA_DIR, f"interactions_{VER}_claude.json")
    json.dump(events, open(ev_out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(new_interactions, open(it_out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"[apply] áp Claude-rerank cho {applied}/{len(events)} event "
          f"({len(events) - applied} giữ fallback)")
    print(f"[apply] sinh lại {len(new_interactions)} interaction trên nhóm 3 căn Claude chọn")
    print(f"[apply] validate schema v2 OK -> {ev_out}")
    print(f"[apply]                        -> {it_out}")
    print("[apply] Bản v2 gốc (recommendation_events_v2.json / interactions_v2.json) GIỮ NGUYÊN.")


if __name__ == "__main__":
    main()
