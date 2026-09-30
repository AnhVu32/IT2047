"""Replay a raw_query through the live backend (HTTP, see EVAL_PLAN.md mục 7 câu 2:
chose HTTP over in-process since the backend already runs in Docker) to get
`pred` for evaluation.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

import config as C


class LiveSearchError(RuntimeError):
    pass


def search(raw_query: str, top_k: int, filters: Optional[Dict[str, Any]] = None,
           timeout: float = 120.0) -> List[Dict[str, Any]]:
    """POST /v1/search and return [{listing_id, score, rank}, ...] ranked by the
    live system. `score` = `final_score` from src/search/ranker.py (the blended
    rank score the live system actually sorts by), not just semantic/text score.
    """
    payload = {"query": raw_query, "top_k": top_k, "page": 1, "filters": filters or {}}
    resp = requests.post(C.SEARCH_ENDPOINT, json=payload, timeout=timeout)
    resp.raise_for_status()
    body = resp.json()
    if body.get("status") != "success":
        raise LiveSearchError(f"backend returned non-success: {body.get('errors')}")

    results = body["data"]["results"]
    out = []
    for rank, item in enumerate(results):
        out.append({
            "listing_id": int(item["listing_id"]),
            "score": float(item.get("final_score", 0.0)),
            "rank": rank,
        })
    return out


def health_check() -> bool:
    try:
        resp = requests.get(C.BACKEND_URL + "/", timeout=5.0)
        return resp.status_code == 200
    except requests.RequestException:
        return False
