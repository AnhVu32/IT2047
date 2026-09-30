from __future__ import annotations

from statistics import mean
from typing import Dict, List, Optional, Tuple, Any

from src.services.inference.knowledge import (
    ACCESSIBILITY_FIELDS,
    ALL_SIMILARITIES,
    AMENITY_FIELDS,
    PROFILE_RULES,
    STRUCTURAL_BOOLEAN_FIELDS,
    VIEW_FIELDS,
)


def infer_profile(request: dict) -> Dict[str, str]:
    profile: Dict[str, str] = {}
    for label, rules in PROFILE_RULES.items():
        for value, condition in rules:
            if condition(request):
                profile[label] = value
                break
    requested_features = set([])
    inferred_traits: List[str] = []
    if request['bedrooms'] and request['bedrooms'] >= 2 and (
        "near_school" in requested_features or "kids_playground" in requested_features
    ):
        inferred_traits.append("family")
    if {"near_metro", "near_bus", "near_highway"} & requested_features:
        inferred_traits.append("mobility_oriented")
    if {"gym", "pool", "park"} & requested_features:
        inferred_traits.append("wellness_oriented")
    if {"security_24h", "parking"} & requested_features:
        inferred_traits.append("security_oriented")

    profile["customer_type"] = inferred_traits[0] if inferred_traits else "general"
    if inferred_traits:
        profile["customer_traits"] = ", ".join(inferred_traits)
    return profile


def passes_hard_filters(payload: dict, request: dict) -> bool:
    checks = [
        request["min_price"] is None or (
            payload.get("price_range") is not None and payload.get("price_range") >= request["min_price"]),
        request["max_price"] is None or (
            payload.get("price_range") is not None and payload.get("price_range") <= request["max_price"]),
        request["min_area"] is None or (
            payload.get("area") is not None and payload.get("area") >= request["min_area"]),
        request["max_area"] is None or (
            payload.get("area") is not None and payload.get("area") <= request["max_area"]),
        request["bedrooms"] is None or (
            payload.get("bedrooms") is not None and payload.get("bedrooms") >= request["bedrooms"]),
        request["bathrooms"] is None or (
            payload.get("bathrooms") is not None and payload.get("bathrooms") >= request["bathrooms"]),
        request["legal_status"] is None or payload.get(
            "legal_status") == request["legal_status"],
        request.get("furniture") is None or payload.get(
            "furnishing") == request.get("furniture"),
        request["house_direction"] is None or payload.get(
            "house_direction") == request["house_direction"],
        request["balcony_direction"] is None or payload.get(
            "balcony_direction") == request["balcony_direction"],
    ]
    # Apply boolean "must-have" filters (frontend sends 0/1; backend treats only True as requested)
    for feature in (
        request.get("must_have_features", [])
        + request.get("nice_to_have_features", [])
    ):
        # Only enforce strict filter for explicitly requested boolean features
        if request.get(feature) is True:
            checks.append(payload.get(feature) is True)
    return all(checks)


def closeness(value: Optional[float], lower: Optional[float], upper: Optional[float]) -> float:
    if value is None:
        return 0.0
    if lower is None and upper is None:
        return 0.0
    if lower is not None and upper is not None:
        midpoint = (lower + upper) / 2
        spread = max((upper - lower) / 2, 1)
        return max(0.0, 1 - abs(value - midpoint) / spread)
    if lower is not None:
        return 1.0 if value >= lower else max(0.0, value / max(lower, 1))
    return 1.0 if upper is not None and value <= upper else max(0.0, upper / max(value, 1))


def exact_or_similar_match(feature: str, payload: dict) -> Tuple[float, Optional[str]]:
    if payload.get(feature):
        return 1.0, feature
    alternatives = [
        (other, score) for (left, other), score in ALL_SIMILARITIES.items() if left == feature and payload.get(other)
    ]
    if not alternatives:
        return 0.0, None
    best_feature, best_score = max(alternatives, key=lambda item: item[1])
    return best_score, best_feature


def score_feature_group(features: List[str], payload: dict, requested_features: List[str]) -> Tuple[float, List[str], List[str]]:
    relevant = [feature for feature in requested_features if feature in features]
    if not relevant:
        return 0.0, [], []
    matched: list[str] = []
    partial: list[str] = []
    scores: list[float] = []
    for feature in relevant:
        score, matched_feature = exact_or_similar_match(feature, payload)
        scores.append(score)
        if score >= 1:
            matched.append(feature)
        elif score > 0:
            partial.append(f"{feature}~{matched_feature}")
    return mean(scores), matched, partial


def score_property(payload: dict, request: dict, profile: Dict[str, str]) -> Any:
    must_features = request.get("must_have_features", [])
    nice_features = request.get("nice_to_have_features", [])
    requested_features = must_features + nice_features

    structural_score = mean(
        [
            closeness(payload.get("area"),
                      request.get("min_area"), request.get("max_area")),
            closeness(payload.get("bedrooms"), request.get("bedrooms"), None),
            closeness(payload.get("bathrooms"),
                      request.get("bathrooms"), None),
        ]
    )
    budget_score = closeness(payload.get(
        "price_range"), request.get("min_price"), request.get("max_price"))
    amenity_score, amenity_matches, amenity_partial = score_feature_group(
        AMENITY_FIELDS, payload, requested_features)
    location_score, location_matches, location_partial = score_feature_group(
        ACCESSIBILITY_FIELDS, payload, requested_features
    )
    view_score, view_matches, view_partial = score_feature_group(
        VIEW_FIELDS, payload, requested_features)
    structural_bool_score, structural_matches, structural_partial = score_feature_group(
        STRUCTURAL_BOOLEAN_FIELDS, payload, requested_features
    )

    furnishing_score = 0.6
    if request.get("furniture"):
        furnishing_score = 1.0 if payload.get(
            "furnishing") == request.get("furniture") else 0.0

    legal_score = 0.6
    if request.get("legal_status"):
        legal_score = 1.0 if payload.get(
            "legal_status") == request.get("legal_status") else 0.0

    profile_bonus = 0.0
    profile_bonus_reason: Optional[str] = None
    if profile.get("customer_type") == "family" and (
        payload.get("near_school") or payload.get(
            "kids_playground") or (payload.get("bedrooms") or 0) >= 2
    ):
        profile_bonus = 0.08
        profile_bonus_reason = "Phù hợp hồ sơ gia đình"
    elif profile.get("customer_type") == "mobility_oriented" and (
        payload.get("near_metro") or payload.get(
            "near_bus") or payload.get("near_highway")
    ):
        profile_bonus = 0.08
        profile_bonus_reason = "Phù hợp hồ sơ ưu tiên kết nối"
    elif profile.get("budget_group") == "luxury" and (payload.get("price_range") or 0) >= 8:
        profile_bonus = 0.05
        profile_bonus_reason = "Nằm trong phân khúc cao cấp"
    elif profile.get("customer_type") == "wellness_oriented" and (
        payload.get("gym") or payload.get("pool") or payload.get("park")
    ):
        profile_bonus = 0.06
        profile_bonus_reason = "Phù hợp hồ sơ ưu tiên tiện ích sống khỏe"
    elif profile.get("customer_type") == "security_oriented" and (
        payload.get("security_24h") or payload.get("parking")
    ):
        profile_bonus = 0.06
        profile_bonus_reason = "Phù hợp hồ sơ ưu tiên an toàn và đỗ xe"

    hybrid_score = (
        budget_score * 0.24
        + structural_score * 0.24
        + structural_bool_score * 0.08
        + amenity_score * 0.18
        + location_score * 0.10
        + view_score * 0.06
        + furnishing_score * 0.04
        + legal_score * 0.04
        + profile_bonus
    )

    content_score = mean(
        [
            budget_score,
            structural_score,
            max(amenity_score, 0.01),
            max(location_score, 0.01),
            max(view_score, 0.01),
            max(structural_bool_score, 0.01),
        ]
    )
    baseline_score = mean([budget_score, structural_score, legal_score])

    matched_features = amenity_matches + \
        location_matches + view_matches + structural_matches
    partial_match_features = amenity_partial + \
        location_partial + view_partial + structural_partial
    exact_match_count = len(matched_features)
    partial_match_score = max(
        [0.0]
        + [exact_or_similar_match(feature, payload)[0]
           for feature in requested_features if feature not in matched_features]
    )
    property_relevance = "relevant" if exact_match_count > 0 or partial_match_score > 0 else "weak"

    explanation_parts = []
    if payload.get("price_range") is not None:
        explanation_parts.append(f"Giá {payload['price_range']:.2f} tỷ")
    if payload.get("area") is not None:
        explanation_parts.append(f"diện tích {payload['area']:.0f}m2")
    if matched_features:
        explanation_parts.append(
            f"khớp trực tiếp {', '.join(matched_features[:4])}")
    if partial_match_features:
        explanation_parts.append(
            f"bù tương đồng {', '.join(partial_match_features[:3])}")
    if request.get("furniture") and payload.get("furnishing") == request.get("furniture"):
        explanation_parts.append(f"nội thất {payload['furnishing'].lower()}")
    if request.get("legal_status") and payload.get("legal_status") == request.get("legal_status"):
        explanation_parts.append(f"pháp lý {payload['legal_status'].lower()}")
    explanation_parts.append(f"mức liên quan {property_relevance}")
    if profile_bonus_reason:
        explanation_parts.append(profile_bonus_reason.lower())

    return {
        "listing_id": payload["listing_id"],
        "overall_score": round(hybrid_score, 4),
        "matched_features": matched_features,
        "partial_match_features": partial_match_features,
        "score_breakdown": {
            "budget": round(budget_score, 4),
            "structural": round(structural_score, 4),
            "structural_features": round(structural_bool_score, 4),
            "amenities": round(amenity_score, 4),
            "location": round(location_score, 4),
            "view": round(view_score, 4),
            "legal": round(legal_score, 4),
            "furnishing": round(furnishing_score, 4),
            "exact_match_count": float(exact_match_count),
            "partial_match_score": round(partial_match_score, 4),
            "profile_bonus": round(profile_bonus, 4),
        },
        "explanation": ". ".join(explanation_parts) + ".",
        "method_scores": {
            "knowledge_hybrid": round(hybrid_score, 4),
            "content_based": round(content_score, 4),
            "baseline": round(baseline_score, 4),
        },
        "profile_bonus_reason": profile_bonus_reason,
        "property_payload": payload,
    }
