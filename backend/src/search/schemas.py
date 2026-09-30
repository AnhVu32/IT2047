from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# A bare/approximate numeric target ("5 tỷ", "70m2") is matched as a soft band of
# ±this fraction rather than an exact value. Shared by the retrieval filter and the
# ranker's graded target tolerance so filtering and ranking stay consistent.
DEFAULT_NUMERIC_TOLERANCE = 0.15


class NumericRange(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None
    target: Optional[float] = None

    @model_validator(mode="after")
    def validate_range(self):
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("min must be less than or equal to max")
        return self


def numeric_bounds(rng, tolerance: Optional[float] = DEFAULT_NUMERIC_TOLERANCE):
    """Effective (lower, upper) filter bounds for a numeric range.

    Explicit min/max are returned unchanged. A lone approximate ``target`` expands
    to a ±``tolerance`` band; ``tolerance=None`` drops the target so it does not
    filter at all (used by zero-result relaxation).
    """
    lower, upper = rng.min, rng.max
    target = getattr(rng, "target", None)
    if lower is None and upper is None and target is not None and tolerance is not None:
        lower = target * (1 - tolerance)
        upper = target * (1 + tolerance)
    return lower, upper


class IntegerRange(BaseModel):
    min: Optional[int] = None
    max: Optional[int] = None
    target: Optional[int] = None


class AmenityDistanceFilter(BaseModel):
    amenity_category: str
    max_driving_distance_km: Optional[float] = None
    max_duration_min: Optional[float] = None
    required: bool = True


class SoftPreference(BaseModel):
    type: str
    value: Optional[str] = None
    amenity_category: Optional[str] = None
    weight: float = Field(default=0.5, ge=0, le=1)


class RankingProfile(str, Enum):
    BALANCED = "BALANCED"
    LOCATION_FIRST = "LOCATION_FIRST"
    AMENITY_FIRST = "AMENITY_FIRST"
    PRICE_FIRST = "PRICE_FIRST"
    SEMANTIC_FIRST = "SEMANTIC_FIRST"
    INVESTMENT = "INVESTMENT"
    FAMILY = "FAMILY"


class HardFilters(BaseModel):
    price: NumericRange = Field(default_factory=NumericRange)
    area: NumericRange = Field(default_factory=NumericRange)
    bedrooms: IntegerRange = Field(default_factory=IntegerRange)
    bathrooms: IntegerRange = Field(default_factory=IntegerRange)
    property_types: List[str] = Field(default_factory=list)
    excluded_property_types: List[str] = Field(default_factory=list)
    districts: List[str] = Field(default_factory=list)
    former_admin_areas: List[str] = Field(default_factory=list)
    legal_statuses: List[str] = Field(default_factory=list)
    furnishings: List[str] = Field(default_factory=list)
    house_directions: List[str] = Field(default_factory=list)
    balcony_directions: List[str] = Field(default_factory=list)
    required_features: List[str] = Field(default_factory=list)
    excluded_features: List[str] = Field(default_factory=list)


class ParsedSearchQuery(BaseModel):
    intent: str = "property_search"
    # Only filters supplied through the UI/API filter payload belong here. These
    # are applied in repository WHERE clauses and are therefore strict.
    hard_filters: HardFilters = Field(default_factory=HardFilters)
    # Constraints inferred from free-form text belong here. They influence
    # ranking but never remove a candidate during retrieval.
    preference_filters: HardFilters = Field(default_factory=HardFilters)
    amenity_filters: List[AmenityDistanceFilter] = Field(default_factory=list)
    soft_preferences: List[SoftPreference] = Field(default_factory=list)
    semantic_query: str = ""
    negative_preferences: List[str] = Field(default_factory=list)
    ranking_profile: RankingProfile = RankingProfile.BALANCED
    sort: str = "relevance"
    top_k: int = Field(default=20, ge=1, le=100)
    protected_constraints: List[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=20, ge=1, le=100)
    page: int = Field(default=1, ge=1)
    debug: bool = False
    filters: Dict[str, Any] = Field(default_factory=dict)


class ParseRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=20, ge=1, le=100)


class SimilarRequest(BaseModel):
    top_k: int = Field(default=10, ge=1, le=50)
