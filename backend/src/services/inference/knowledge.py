from typing import Dict, Tuple


SIMILARITY_MATRIX: Dict[Tuple[str, str], float] = {
    ("garage", "parking"): 0.85,
    ("balcony", "terrace"): 0.65,
    ("garden", "near_park"): 0.40,
    ("garden", "park"): 0.35,
    ("gym", "sports_court"): 0.90,
    ("gym", "park"): 0.45,
    ("gym", "pool"): 0.35,
    ("park", "kids_playground"): 0.78,
    ("park", "bbq"): 0.42,
    ("kids_playground", "bbq"): 0.30,
    ("security_24h", "reception"): 0.55,
    ("pool", "park"): 0.32,
    ("sports_court", "park"): 0.38,
    ("near_metro", "near_bus"): 0.68,
    ("near_metro", "near_highway"): 0.44,
    ("near_bus", "near_highway"): 0.40,
    ("near_mall", "near_market"): 0.74,
    ("near_mall", "near_park"): 0.22,
    ("near_school", "near_park"): 0.28,
    ("near_school", "kids_playground"): 0.30,
    ("near_park", "park"): 0.52,
    ("river_view", "park_view"): 0.54,
    ("park_view", "city_view"): 0.26,
    ("elevator", "parking"): 0.25,
}

REVERSE_MATRIX = {(b, a): score for (a, b), score in SIMILARITY_MATRIX.items()}

ALL_SIMILARITIES = dict(SIMILARITY_MATRIX)
ALL_SIMILARITIES.update(REVERSE_MATRIX)

NUMERIC_FIELDS = ["price_billion", "area_sqm", "bedrooms", "bathrooms"]

AMENITY_FIELDS = [
    "bedrooms",
    "bathrooms",
    "balcony",
    "garden",
    "garage",
    "terrace",
    "pool",
    "gym",
    "park",
    "bbq",
    "kids_playground",
    "sports_court",
    "security_24h",
    "reception",
    "elevator",
    "parking",
]

ACCESSIBILITY_FIELDS = [
    "near_metro",
    "near_bus",
    "near_highway",
    "near_school",
    "near_hospital",
    "near_mall",
    "near_market",
    "near_park",
]

VIEW_FIELDS = ["river_view", "park_view", "city_view"]

STRUCTURAL_BOOLEAN_FIELDS = ["balcony", "garden", "garage", "terrace"]

PROFILE_RULES = {
    "budget_group": [
        ("affordable", lambda req: req['max_price']
         is not None and req['max_price'] <= 3),
        ("mid_range", lambda req: req['max_price']
         is not None and 3 < req['max_price'] <= 8),
        ("luxury", lambda req: req['max_price']
         is not None and req['max_price'] > 8),
    ],
    "area_preference": [
        ("compact", lambda req: req['min_area']
         is not None and req['min_area'] <= 60),
        ("medium", lambda req: req['min_area']
         is not None and 60 < req['min_area'] <= 90),
        ("large", lambda req: req['min_area']
         is not None and req['min_area'] > 90),
    ],
}
