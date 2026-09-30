"""Implicit-feedback scoring.

Weights follow the ordering used by the offline interactions dataset:
view < share < save < contact, with explicit thumbs as strong signals.
A short dwell bonus nudges long views above bounces.
"""

from __future__ import annotations

from typing import Optional


ACTION_BASE_SCORE = {
    "view": 0.20,
    "share": 0.55,
    "save": 0.70,
    "contact": 0.90,
    "thumbs_up": 1.00,
    "thumbs_down": -1.00,
    # Neutral: records that a previously-saved listing was un-saved. Scored 0 so it
    # is ignored by the profile (which filters implicit_score > 0) but still lets the
    # saved-state query see the removal.
    "unsave": 0.00,
}

VALID_ACTIONS = set(ACTION_BASE_SCORE)


def implicit_score(action_type: str, dwell_time_seconds: Optional[float]) -> float:
    base = ACTION_BASE_SCORE.get(action_type, 0.0)
    if action_type == "view" and dwell_time_seconds:
        # Up to +0.2 for a ~60s+ dwell; keeps views below an explicit save.
        base += min(max(dwell_time_seconds, 0.0) / 60.0, 1.0) * 0.20
    return round(base, 4)
