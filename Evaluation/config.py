"""Paths and settings shared by the Evaluation scripts."""
from __future__ import annotations

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
GEN_DATA_DIR = REPO_ROOT / "gen_user_data" / "data"

# v4 = v3 ward-tiered pool + raw_query rewritten so price/bedrooms/1 amenity
# are stated explicitly (not vague "rẻ một chút") and recommended_items
# re-selected with the real ranker.py criteria/feature scoring — see
# gen_user_data/generate_v4.py. TEMPORARY validation swap (Plan step 5.3);
# interactions/users still v3 (v4 only touches Group A ranking ground truth).
EVENTS_FILE = GEN_DATA_DIR / "recommendation_events_v4_claude.json"
INTERACTIONS_FILE = GEN_DATA_DIR / "interactions_v3_claude.json"
USERS_FILE = GEN_DATA_DIR / "users_v3.json"
LISTINGS_FILE = GEN_DATA_DIR / "listings.json"

BACKEND_URL = os.environ.get("EVAL_BACKEND_URL", "http://localhost:8001")
SEARCH_ENDPOINT = f"{BACKEND_URL}/v1/search"

RESULTS_DIR = HERE / "results"

POSITIVE_ACTIONS = {"save", "share", "contact"}
