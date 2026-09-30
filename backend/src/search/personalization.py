"""Build a lightweight per-user preference profile from feedback and score
candidates against it. Used to blend a personalization term into ranking.

A profile is derived from the user's recent positive interactions (weighted by
``implicit_score``): which districts / property types they engage with, their
typical price band, and listings they already saved or contacted.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def _normalize(weights: Dict[str, float]) -> Dict[str, float]:
    if not weights:
        return {}
    top = max(weights.values())
    if top <= 0:
        return {}
    return {key: round(value / top, 4) for key, value in weights.items()}


def build_user_profile(user_id: int) -> Optional[Dict[str, Any]]:
    """Return a preference profile, or ``None`` when there is no usable signal."""
    from src.services.feedback import repository as feedback_repository

    interactions = feedback_repository.get_recent_interactions(user_id)
    if not interactions:
        return None

    districts: Dict[str, float] = {}
    property_types: Dict[str, float] = {}
    saved_listing_ids: set[int] = set()
    price_weight_sum = 0.0
    price_weighted_total = 0.0

    for row in interactions:
        score = float(row.get("implicit_score") or 0.0)
        if score <= 0:
            continue
        district = row.get("district")
        if district:
            districts[district] = districts.get(district, 0.0) + score
        property_type = row.get("property_type")
        if property_type:
            property_types[property_type] = property_types.get(property_type, 0.0) + score
        price = row.get("price_range")
        if price is not None:
            price_weighted_total += float(price) * score
            price_weight_sum += score
        if row.get("action_type") in {"save", "contact"} and row.get("listing_id") is not None:
            saved_listing_ids.add(int(row["listing_id"]))

    price_center = (
        price_weighted_total / price_weight_sum if price_weight_sum > 0 else None
    )

    profile = {
        "districts": _normalize(districts),
        "property_types": _normalize(property_types),
        "price_center": price_center,
        "saved_listing_ids": saved_listing_ids,
    }
    if not any(
        [profile["districts"], profile["property_types"], price_center, saved_listing_ids]
    ):
        return None
    return profile


def score_item(item: dict, profile: Dict[str, Any]) -> float:
    """Personalization score in [0, 1] for a candidate given the user profile."""
    district_score = profile["districts"].get(item.get("district"), 0.0)
    type_score = profile["property_types"].get(item.get("property_type"), 0.0)

    price_score = 0.0
    center = profile.get("price_center")
    price = item.get("price_range")
    if center and price is not None:
        tolerance = max(center * 0.30, 1.0)
        price_score = max(0.0, 1.0 - abs(float(price) - center) / tolerance)

    saved_score = 0.0
    listing_id = item.get("listing_id")
    if listing_id is not None and int(listing_id) in profile["saved_listing_ids"]:
        saved_score = 1.0

    combined = (
        0.40 * district_score
        + 0.25 * type_score
        + 0.20 * price_score
        + 0.15 * saved_score
    )
    return max(0.0, min(1.0, combined))
