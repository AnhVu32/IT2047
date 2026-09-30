import os
import json
import math
from datetime import date, datetime

from loguru import logger

from src.settings.event import postgres_client


def repo_get_properties(
    query: str,
    min_price: float,
    max_price: float,
    min_area: float,
    max_area: float,
    bedrooms: int,
    bathrooms: int,
    legal_status: str,
    furniture: str,
    house_direction: str,
    balcony_direction: str,
    min_frontage: float,
    min_road_width: float,
    
    sort_by: str,
    sort_order: str,
    page: int,
    limit: int,
    property_type: str,
    district: str = None,
    pool: bool = None,
    gym: bool = None,
    park: bool = None,
    bbq: bool = None,
    kids_playground: bool = None,
    sports_court: bool = None,
    security_24h: bool = None,
    reception: bool = None,
    elevator: bool = None,
    parking: bool = None,
    near_metro: bool = None,
    near_bus: bool = None,
    near_highway: bool = None,
    near_school: bool = None,
    near_hospital: bool = None,
    near_mall: bool = None,
    near_market: bool = None,
    near_park: bool = None,
    river_view: bool = None,
    park_view: bool = None,
    city_view: bool = None,
    balcony: bool = None,
    garden: bool = None,
    garage: bool = None,
    terrace: bool = None,
):
    """
    Fetch properties from Postgres with filters, sorting, and pagination.

    Notes:
        - Uses parameterized SQL to avoid SQL injection.
        - Filters only apply when the corresponding parameter is not None/blank.
        - Always excludes deleted/inactive rows (is_deleted = false, is_active = true).

    Returns:
        Tuple[bool, dict | None, str | None]:
            - success flag
            - data payload: {"properties": [...], "total": int, "page": int, "limit": int, "num_pages": int}
            - error message (if any)
    """
    try:
        def _is_blank(value) -> bool:
            return value is None or (isinstance(value, str) and value.strip() == "")

        if page is None or page < 1:
            page = 1
        if limit is None or limit < 1:
            limit = 10

        where_clauses = ["is_deleted = false", "is_active = true"]
        params = {}

        if not _is_blank(query):
            params["q"] = f"%{query.strip()}%"
            where_clauses.append(
                "("
                "title ILIKE :q OR "
                "description ILIKE :q OR "
                "address ILIKE :q OR "
                "city_province ILIKE :q OR "
                "district ILIKE :q"
                ")"
            )

        if min_price is not None:
            where_clauses.append("price_range >= :min_price")
            params["min_price"] = min_price
        if max_price is not None:
            where_clauses.append("price_range <= :max_price")
            params["max_price"] = max_price

        if min_area is not None:
            where_clauses.append("area >= :min_area")
            params["min_area"] = min_area
        if max_area is not None:
            where_clauses.append("area <= :max_area")
            params["max_area"] = max_area

        if bedrooms is not None:
            where_clauses.append("bedrooms >= :bedrooms")
            params["bedrooms"] = bedrooms
        if bathrooms is not None:
            where_clauses.append("bathrooms >= :bathrooms")
            params["bathrooms"] = bathrooms

        if not _is_blank(legal_status):
            # Support multiple legal_status values separated by commas
            # Example input: "Sổ hồng riêng,Sổ chung"
            statuses = [
                s.strip()
                for s in str(legal_status).split(",")
                if not _is_blank(s)
            ]
            if len(statuses) == 1:
                where_clauses.append("LOWER(legal_status) = LOWER(:legal_status)")
                params["legal_status"] = statuses[0]
            elif len(statuses) > 1:
                placeholders = []
                for idx, value in enumerate(statuses):
                    key = f"legal_status_{idx}"
                    placeholders.append(f":{key}")
                    params[key] = value.lower()
                where_clauses.append(
                    f"LOWER(legal_status) IN ({', '.join(placeholders)})"
                )

        # API param is "furniture", DB column is "furnishing"
        if not _is_blank(furniture):
            furnishings = [
                s.strip()
                for s in str(furniture).split(",")
                if not _is_blank(s)
            ]
            if len(furnishings) == 1:
                where_clauses.append("LOWER(furnishing) = LOWER(:furnishing)")
                params["furnishing"] = furnishings[0]
            elif len(furnishings) > 1:
                placeholders = []
                for idx, value in enumerate(furnishings):
                    key = f"furnishing_{idx}"
                    placeholders.append(f":{key}")
                    params[key] = value.lower()
                where_clauses.append(
                    f"LOWER(furnishing) IN ({', '.join(placeholders)})"
                )

        if not _is_blank(house_direction):
            house_directions = [
                s.strip()
                for s in str(house_direction).split(",")
                if not _is_blank(s)
            ]
            if len(house_directions) == 1:
                where_clauses.append(
                    "LOWER(house_direction) = LOWER(:house_direction)"
                )
                params["house_direction"] = house_directions[0]
            elif len(house_directions) > 1:
                placeholders = []
                for idx, value in enumerate(house_directions):
                    key = f"house_direction_{idx}"
                    placeholders.append(f":{key}")
                    params[key] = value.lower()
                where_clauses.append(
                    f"LOWER(house_direction) IN ({', '.join(placeholders)})"
                )

        if not _is_blank(balcony_direction):
            balcony_directions = [
                s.strip()
                for s in str(balcony_direction).split(",")
                if not _is_blank(s)
            ]
            if len(balcony_directions) == 1:
                where_clauses.append(
                    "LOWER(balcony_direction) = LOWER(:balcony_direction)"
                )
                params["balcony_direction"] = balcony_directions[0]
            elif len(balcony_directions) > 1:
                placeholders = []
                for idx, value in enumerate(balcony_directions):
                    key = f"balcony_direction_{idx}"
                    placeholders.append(f":{key}")
                    params[key] = value.lower()
                where_clauses.append(
                    f"LOWER(balcony_direction) IN ({', '.join(placeholders)})"
                )

        if min_frontage is not None:
            where_clauses.append("frontage >= :min_frontage")
            params["min_frontage"] = min_frontage

        # API param is "min_road_width", DB column is "access_road"
        if min_road_width is not None:
            where_clauses.append("access_road >= :min_road_width")
            params["min_road_width"] = min_road_width

        if not _is_blank(property_type):
            # where_clauses.append("LOWER(property_type) = LOWER(:property_type)")
            # params["property_type"] = property_type.strip()
            property_types = [
                s.strip()
                for s in str(property_type).split(",")
                if not _is_blank(s)
            ]
            if len(property_types) == 1:
                where_clauses.append("LOWER(property_type) = LOWER(:property_type)")
                params["property_type"] = property_types[0]
            elif len(property_types) > 1:
                placeholders = []
                for idx, value in enumerate(property_types):
                    key = f"property_type_{idx}"
                    placeholders.append(f":{key}")
                    params[key] = value.lower()
                where_clauses.append(
                    f"LOWER(property_type) IN ({', '.join(placeholders)})"
                )

        if not _is_blank(district):
            districts = [
                s.strip()
                for s in str(district).split(",")
                if not _is_blank(s)
            ]
            if len(districts) == 1:
                where_clauses.append("LOWER(district) = LOWER(:district)")
                params["district"] = districts[0]
            elif len(districts) > 1:
                placeholders = []
                for idx, value in enumerate(districts):
                    key = f"district_{idx}"
                    placeholders.append(f":{key}")
                    params[key] = value.lower()
                where_clauses.append(
                    f"LOWER(district) IN ({', '.join(placeholders)})"
                )

        amenity_fields = [
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
            "near_metro",
            "near_bus",
            "near_highway",
            "near_school",
            "near_hospital",
            "near_mall",
            "near_market",
            "near_park",
            "river_view",
            "park_view",
            "city_view",
            "balcony",
            "garden",
            "garage",
            "terrace",
        ]
        local_vars = locals()
        for field in amenity_fields:
            value = local_vars.get(field)
            if value is not None:
                where_clauses.append(f"{field} = :{field}")
                params[field] = value

        where_sql = " AND ".join(where_clauses)

        sort_by = (sort_by or "newest").strip().lower()
        sort_order = (sort_order or "desc").strip().lower()
        sort_order_sql = "ASC" if sort_order == "asc" else "DESC"

        sort_map = {
            "newest": f"id {sort_order_sql}",
            "oldest": f"id {sort_order_sql}",
            "price_asc": "price_range ASC NULLS LAST",
            "price_desc": "price_range DESC NULLS LAST",
            "area_asc": "area ASC NULLS LAST",
            "area_desc": "area DESC NULLS LAST",
        }
        # logger.info(f"sort_by: {sort_by}, sort_order: {sort_order}")
        if sort_by == "oldest":
            order_by_sql = "created_at ASC"
        else:
            order_by_sql = sort_map.get(sort_by, f"created_at {sort_order_sql}")

        offset = (page - 1) * limit
        params["limit"] = limit
        params["offset"] = offset

        select_columns = """
            id,
            listing_id,
            listing_type,
            posted_date,
            expiry_date,
            property_type,
            city_province,
            district,
            images,
            folder,
            title,
            address,
            old_address,
            location_link,
            latitude_longitude,
            description,
            area_price_history,
            price_range,
            area,
            bedrooms,
            bathrooms,
            legal_status,
            furnishing,
            balcony_direction,
            house_direction,
            pool,
            gym,
            park,
            bbq,
            kids_playground,
            sports_court,
            security_24h,
            reception,
            elevator,
            parking,
            near_metro,
            near_bus,
            near_highway,
            near_school,
            near_hospital,
            near_mall,
            near_market,
            near_park,
            river_view,
            park_view,
            city_view,
            balcony,
            garden,
            garage,
            terrace,
            frontage,
            access_road,
            metadata,
            is_active,
            is_deleted,
            updated_at,
            created_at
        """.strip()

        raw_query_items = f"""
            SELECT {select_columns}
            FROM properties
            WHERE {where_sql}
            ORDER BY {order_by_sql}
            LIMIT :limit OFFSET :offset
        """

        raw_query_total = f"""
            SELECT COUNT(*) AS total
            FROM properties
            WHERE {where_sql}
        """

        rows = postgres_client.execute_raw_query(raw_query_items, **params)
        total_rows = postgres_client.execute_raw_query(raw_query_total, **params)

        total = int(total_rows[0][0]) if total_rows else 0
        num_pages = int(math.ceil(total / limit)) if limit > 0 else 0

        if not rows:
            return (
                True,
                {"properties": [], "total": total, "page": page, "limit": limit, "num_pages": num_pages},
                None,
            )

        column_names = [c.strip() for c in select_columns.split(",")]
        properties = [dict(zip(column_names, r)) for r in rows]

        # Ensure all values are JSON serializable (e.g. convert datetime/date to string)
        for item in properties:
            for key, value in list(item.items()):
                if isinstance(value, (datetime, date)):
                    item[key] = value.isoformat()

        return True, {
            "properties": properties,
            "total": total,
            "page": page,
            "limit": limit,
            "num_pages": num_pages,
        }, None
    except Exception as e:
        logger.error(e)
        return False, None, str(e)

def repo_add_log(
    user_id: int | None = None,
    action: str | None = None,
    content: str | None = None,
    metadata: dict | None = None,
    type: str = "INFO",
):
    """
    Insert a new log row into Postgres `public.logs`.

    Notes:
        - Uses parameterized SQL to avoid SQL injection.
        - `metadata` is stored as jsonb.

    Returns:
        Tuple[bool, dict | None, str | None]:
            - success flag
            - inserted row payload (at least contains `id`)
            - error message (if any)
    """
    try:
        data = postgres_client.execute_raw_query(
            """
            INSERT INTO logs (user_id, "action", "content", metadata, "type")
            VALUES (:user_id, :action, :content, :metadata, :type)
            RETURNING id, user_id, "action", "content", metadata, "type"
            """,
            user_id=user_id,
            action=action,
            content=content,
            metadata=json.dumps(metadata) if metadata is not None else None,
            type=type,
        )
        if not data:
            return False, None, "Failed to insert log"

        
        data_res = {
            "id": data[0][0],
            "user_id": data[0][1],
            "action": data[0][2],
            "content": data[0][3],
            "metadata": data[0][4],
            "type": data[0][5],
        }
        return True, data_res, None
    except Exception as e:
        logger.error(e)
        return False, None, str(e)