from __future__ import annotations

import json
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from src.search.schemas import DEFAULT_NUMERIC_TOLERANCE, ParsedSearchQuery, numeric_bounds
from src.settings.event import postgres_client


# Alias for the shared tolerance so existing references keep working.
PRICE_AREA_TOLERANCE = DEFAULT_NUMERIC_TOLERANCE


BOOLEAN_COLUMNS = {
    "pool", "gym", "park", "bbq", "kids_playground", "sports_court",
    "security_24h", "reception", "elevator", "parking", "near_metro",
    "near_bus", "near_highway", "near_school", "near_hospital", "near_mall",
    "near_market", "near_park", "river_view", "park_view", "city_view",
    "balcony", "garden", "garage", "terrace",
}

# These textual flags are represented by measured relationships in Neo4j.
GRAPH_RELATIONSHIP_FEATURES = {
    "near_metro", "near_bus", "near_school", "near_hospital",
    "near_mall", "near_market", "near_park",
}

SELECT_COLUMNS = """
    p.id, p.listing_id, p.listing_type, p.posted_date, p.expiry_date,
    p.property_type, p.city_province, p.district, p.images, p.folder, p.title,
    p.address, p.old_address, p.location_link, p.latitude_longitude,
    p.description, p.area_price_history, p.price_range, p.area, p.bedrooms,
    p.bathrooms, p.legal_status, p.furnishing, p.balcony_direction,
    p.house_direction, p.pool, p.gym, p.park, p.bbq, p.kids_playground,
    p.sports_court, p.security_24h, p.reception, p.elevator, p.parking,
    p.near_metro, p.near_bus, p.near_highway, p.near_school, p.near_hospital,
    p.near_mall, p.near_market, p.near_park, p.river_view, p.park_view,
    p.city_view, p.balcony, p.garden, p.garage, p.terrace, p.frontage,
    p.access_road, p.metadata, p.updated_at, p.created_at,
    p.search_text, p.former_admin_area, p.geo_cluster_150m,
    p.data_quality_flags, p.coordinate_confidence
"""


def _json_safe(row: dict) -> dict:
    for key, value in list(row.items()):
        if isinstance(value, (datetime, date)):
            row[key] = value.isoformat()
        elif isinstance(value, str) and key == "amenity_evidence":
            try:
                row[key] = json.loads(value)
            except json.JSONDecodeError:
                row[key] = []
    row["amenity_evidence"] = row.get("amenity_evidence") or []
    return row


class SearchRepository:
    def embedding_coverage(self) -> Tuple[int, int]:
        rows = postgres_client.fetch_mappings(
            """
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE embedding IS NOT NULL) AS embedded
            FROM properties WHERE is_active = true AND is_deleted = false
            """
        )
        return (int(rows[0]["embedded"]), int(rows[0]["total"])) if rows else (0, 0)

    def _where(
        self,
        parsed: ParsedSearchQuery,
        *,
        include_amenities: bool = True,
        graph_validated: bool = False,
        numeric_tolerance: Optional[float] = PRICE_AREA_TOLERANCE,
    ) -> Tuple[List[str], Dict]:
        hard = parsed.hard_filters
        where = ["p.is_deleted = false", "p.is_active = true"]
        params: Dict = {}
        numeric = (
            ("price_range", "price", hard.price), ("area", "area", hard.area),
            ("bedrooms", "bedrooms", hard.bedrooms), ("bathrooms", "bathrooms", hard.bathrooms),
        )
        for column, key, value in numeric:
            # A lone approximate target becomes a soft ±tolerance band; explicit
            # min/max pass through unchanged. numeric_tolerance=None drops the band.
            lower, upper = numeric_bounds(value, numeric_tolerance)
            if lower is not None:
                where.append(f"p.{column} >= :{key}_min")
                params[f"{key}_min"] = lower
            if upper is not None:
                where.append(f"p.{column} <= :{key}_max")
                params[f"{key}_max"] = upper

        list_filters = (
            ("property_type", hard.property_types),
            ("district", [] if graph_validated else hard.districts),
            ("legal_status", hard.legal_statuses),
            ("furnishing", hard.furnishings), ("house_direction", hard.house_directions),
            ("balcony_direction", hard.balcony_directions),
        )
        for column, values in list_filters:
            if values:
                key = f"{column}_values"
                where.append(f"LOWER(p.{column}) = ANY(:{key})")
                params[key] = [value.lower() for value in values]
        if hard.former_admin_areas and not graph_validated:
            where.append("LOWER(p.former_admin_area) = ANY(:former_admin_area_values)")
            params["former_admin_area_values"] = [value.lower() for value in hard.former_admin_areas]
        if hard.excluded_property_types:
            where.append("NOT (LOWER(p.property_type) = ANY(:excluded_property_types))")
            params["excluded_property_types"] = [x.lower() for x in hard.excluded_property_types]

        for feature in hard.required_features:
            if graph_validated and feature in GRAPH_RELATIONSHIP_FEATURES:
                continue
            if feature in BOOLEAN_COLUMNS:
                where.append(f"p.{feature} IS TRUE")
        for feature in hard.excluded_features:
            if graph_validated and feature in GRAPH_RELATIONSHIP_FEATURES:
                continue
            if feature in BOOLEAN_COLUMNS:
                where.append(f"COALESCE(p.{feature}, false) IS FALSE")

        for index, amenity in enumerate(parsed.amenity_filters if include_amenities else []):
            if not amenity.required:
                continue
            conditions = ["lad.listing_id = p.listing_id::text", f"lad.category = :amenity_category_{index}"]
            params[f"amenity_category_{index}"] = amenity.amenity_category
            if amenity.max_driving_distance_km is not None:
                conditions.append(f"lad.driving_distance_km <= :amenity_distance_{index}")
                params[f"amenity_distance_{index}"] = amenity.max_driving_distance_km
            if amenity.max_duration_min is not None:
                conditions.append(f"lad.driving_duration_min <= :amenity_duration_{index}")
                params[f"amenity_duration_{index}"] = amenity.max_duration_min
            where.append("EXISTS (SELECT 1 FROM listing_amenity_distances lad WHERE " + " AND ".join(conditions) + ")")
        return where, params

    def search(
        self,
        parsed: ParsedSearchQuery,
        query_embedding: Optional[List[float]],
        candidate_limit: int = 1000,
        numeric_tolerance: Optional[float] = PRICE_AREA_TOLERANCE,
    ) -> List[dict]:
        where, params = self._where(parsed, numeric_tolerance=numeric_tolerance)
        params["candidate_limit"] = min(max(candidate_limit, parsed.top_k), 3000)
        params["text_query"] = parsed.semantic_query
        if query_embedding is not None:
            params["query_embedding"] = "[" + ",".join(f"{float(x):.8f}" for x in query_embedding) + "]"
            semantic_sql = "CASE WHEN p.embedding IS NULL THEN 0 ELSE 1 - (p.embedding <=> CAST(:query_embedding AS vector)) END"
            order_sql = "p.embedding <=> CAST(:query_embedding AS vector) NULLS LAST, text_score DESC"
        else:
            semantic_sql = "0.0"
            order_sql = "text_score DESC, p.created_at DESC"

        query = f"""
            SELECT {SELECT_COLUMNS},
                   {semantic_sql} AS semantic_score,
                   ts_rank_cd(to_tsvector('simple', COALESCE(p.search_text, '')),
                              plainto_tsquery('simple', :text_query)) AS text_score,
                   COALESCE((
                       SELECT json_agg(json_build_object(
                           'category', lad.category,
                           'name', lad.amenity_name,
                           'driving_distance_km', lad.driving_distance_km,
                           'driving_duration_min', lad.driving_duration_min,
                           'threshold_km', lad.threshold_km
                       ) ORDER BY lad.rank)
                       FROM listing_amenity_distances lad
                       WHERE lad.listing_id = p.listing_id::text AND lad.rank <= 1
                   ), '[]'::json) AS amenity_evidence
            FROM properties p
            WHERE {' AND '.join(where)}
            ORDER BY {order_sql}
            LIMIT :candidate_limit
        """
        return [_json_safe(row) for row in postgres_client.fetch_mappings(query, **params)]

    def fetch_graph_candidates(
        self,
        parsed: ParsedSearchQuery,
        listing_ids: List[str],
        query_embedding: Optional[List[float]],
    ) -> List[dict]:
        """Hydrate Neo4j candidates from the PostgreSQL source of truth."""
        if not listing_ids:
            return []
        where, params = self._where(parsed, include_amenities=False, graph_validated=True)
        params["graph_listing_ids"] = [int(value) for value in listing_ids if str(value).isdigit()]
        if not params["graph_listing_ids"]:
            return []
        where.append("p.listing_id = ANY(:graph_listing_ids)")
        if query_embedding is not None:
            params["query_embedding"] = "[" + ",".join(f"{float(x):.8f}" for x in query_embedding) + "]"
            semantic_sql = "CASE WHEN p.embedding IS NULL THEN 0 ELSE 1 - (p.embedding <=> CAST(:query_embedding AS vector)) END"
        else:
            semantic_sql = "0.0"
        params["text_query"] = parsed.semantic_query
        query = f"""
            SELECT {SELECT_COLUMNS},
                   {semantic_sql} AS semantic_score,
                   ts_rank_cd(to_tsvector('simple', COALESCE(p.search_text, '')),
                              plainto_tsquery('simple', :text_query)) AS text_score,
                   COALESCE((
                       SELECT json_agg(json_build_object(
                           'category', lad.category,
                           'name', lad.amenity_name,
                           'driving_distance_km', lad.driving_distance_km,
                           'driving_duration_min', lad.driving_duration_min,
                           'threshold_km', lad.threshold_km
                       ) ORDER BY lad.rank)
                       FROM listing_amenity_distances lad
                       WHERE lad.listing_id = p.listing_id::text AND lad.rank <= 1
                   ), '[]'::json) AS amenity_evidence
            FROM properties p
            WHERE {' AND '.join(where)}
        """
        return [_json_safe(row) for row in postgres_client.fetch_mappings(query, **params)]

    def count(self, parsed: ParsedSearchQuery, numeric_tolerance: Optional[float] = PRICE_AREA_TOLERANCE) -> int:
        where, params = self._where(parsed, numeric_tolerance=numeric_tolerance)
        rows = postgres_client.fetch_mappings(
            f"SELECT COUNT(*) AS total FROM properties p WHERE {' AND '.join(where)}", **params
        )
        return int(rows[0]["total"]) if rows else 0

    def similar(self, listing_id: str, limit: int = 10) -> List[dict]:
        query = f"""
            WITH source AS (
                SELECT embedding, property_type, listing_id FROM properties
                WHERE (id::text = :listing_id OR listing_id::text = :listing_id)
                  AND is_active = true AND is_deleted = false
                LIMIT 1
            )
            SELECT {SELECT_COLUMNS},
                   CASE WHEN p.embedding IS NULL OR source.embedding IS NULL THEN 0
                        ELSE 1 - (p.embedding <=> source.embedding) END AS semantic_score,
                   0.0 AS text_score, '[]'::json AS amenity_evidence
            FROM properties p CROSS JOIN source
            WHERE p.is_active = true AND p.is_deleted = false
              AND p.listing_id <> source.listing_id
              AND p.embedding IS NOT NULL AND source.embedding IS NOT NULL
            ORDER BY p.embedding <=> source.embedding
            LIMIT :limit
        """
        return [_json_safe(row) for row in postgres_client.fetch_mappings(query, listing_id=listing_id, limit=limit)]

    def get_by_listing_ids(self, listing_ids: List[str]) -> List[dict]:
        numeric_ids = [int(value) for value in listing_ids if str(value).isdigit()]
        if not numeric_ids:
            return []
        rows = postgres_client.fetch_mappings(
            f"""
            SELECT {SELECT_COLUMNS}, 0.0 AS semantic_score, 0.0 AS text_score,
                   '[]'::json AS amenity_evidence
            FROM properties p
            WHERE p.listing_id = ANY(:listing_ids)
              AND p.is_active = true AND p.is_deleted = false
            ORDER BY p.posted_date DESC NULLS LAST, p.id
            """,
            listing_ids=numeric_ids,
        )
        return [_json_safe(row) for row in rows]

    def get_property(self, property_id: str) -> Optional[dict]:
        rows = postgres_client.fetch_mappings(
            f"""
            SELECT {SELECT_COLUMNS}, 0.0 AS semantic_score, 0.0 AS text_score,
                   '[]'::json AS amenity_evidence
            FROM properties p
            WHERE (p.id::text = :property_id OR p.listing_id::text = :property_id)
              AND p.is_active = true AND p.is_deleted = false
            ORDER BY p.id
            LIMIT 1
            """,
            property_id=property_id,
        )
        return _json_safe(rows[0]) if rows else None


search_repository = SearchRepository()
