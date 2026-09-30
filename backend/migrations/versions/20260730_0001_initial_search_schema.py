"""Create the initial property search schema.

Revision ID: 20260730_0001
Revises:
Create Date: 2026-07-30

The IF NOT EXISTS clauses allow databases initialized by the former
001_pgvector_hybrid_search.sql startup hook to adopt Alembic without data loss.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260730_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS properties (
            id BIGSERIAL PRIMARY KEY,
            listing_id BIGINT NOT NULL,
            listing_type VARCHAR(255),
            posted_date DATE,
            expiry_date DATE,
            property_type VARCHAR(255),
            city_province VARCHAR(255),
            district VARCHAR(255),
            images JSONB NOT NULL DEFAULT '[]'::jsonb,
            folder TEXT,
            title TEXT,
            address TEXT,
            old_address TEXT,
            location_link TEXT,
            latitude_longitude TEXT,
            description TEXT,
            area_price_history DOUBLE PRECISION,
            price_range DOUBLE PRECISION,
            area DOUBLE PRECISION,
            bedrooms INTEGER,
            bathrooms INTEGER,
            legal_status VARCHAR(255),
            furnishing VARCHAR(255),
            balcony_direction VARCHAR(255),
            house_direction VARCHAR(255),
            pool BOOLEAN,
            gym BOOLEAN,
            park BOOLEAN,
            bbq BOOLEAN,
            kids_playground BOOLEAN,
            sports_court BOOLEAN,
            security_24h BOOLEAN,
            reception BOOLEAN,
            elevator BOOLEAN,
            parking BOOLEAN,
            near_metro BOOLEAN,
            near_bus BOOLEAN,
            near_highway BOOLEAN,
            near_school BOOLEAN,
            near_hospital BOOLEAN,
            near_mall BOOLEAN,
            near_market BOOLEAN,
            near_park BOOLEAN,
            river_view BOOLEAN,
            park_view BOOLEAN,
            city_view BOOLEAN,
            balcony BOOLEAN,
            garden BOOLEAN,
            garage BOOLEAN,
            terrace BOOLEAN,
            frontage DOUBLE PRECISION,
            access_road DOUBLE PRECISION,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            is_active BOOLEAN NOT NULL DEFAULT true,
            is_deleted BOOLEAN NOT NULL DEFAULT false,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS logs (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT,
            action VARCHAR(255),
            content TEXT,
            metadata JSONB,
            type VARCHAR(32),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute("ALTER TABLE properties ADD COLUMN IF NOT EXISTS search_text TEXT")
    op.execute("ALTER TABLE properties ADD COLUMN IF NOT EXISTS embedding vector(1024)")
    op.execute("ALTER TABLE properties ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(255)")
    op.execute("ALTER TABLE properties ADD COLUMN IF NOT EXISTS search_text_version VARCHAR(32)")
    op.execute("ALTER TABLE properties ADD COLUMN IF NOT EXISTS former_admin_area VARCHAR(255)")
    op.execute("ALTER TABLE properties ADD COLUMN IF NOT EXISTS geo_cluster_150m VARCHAR(255)")
    op.execute("ALTER TABLE properties ADD COLUMN IF NOT EXISTS data_quality_flags TEXT")
    op.execute("ALTER TABLE properties ADD COLUMN IF NOT EXISTS coordinate_confidence DOUBLE PRECISION")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS listing_amenity_distances (
            listing_id TEXT NOT NULL,
            listing_node_id TEXT NOT NULL,
            amenity_id TEXT NOT NULL,
            amenity_name TEXT,
            category VARCHAR(64) NOT NULL,
            rank INTEGER,
            is_nearest BOOLEAN,
            straight_line_km DOUBLE PRECISION,
            driving_distance_km DOUBLE PRECISION,
            driving_duration_min DOUBLE PRECISION,
            threshold_km DOUBLE PRECISION,
            PRIMARY KEY (listing_node_id, amenity_id)
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_properties_search_text_fts
        ON properties USING gin (to_tsvector('simple', COALESCE(search_text, '')))
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_properties_embedding_hnsw
        ON properties USING hnsw (embedding vector_cosine_ops)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_properties_search_hard_filters
        ON properties (is_active, is_deleted, property_type, district, price_range, area)
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_properties_listing_id ON properties (listing_id)"
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_listing_amenity_filter
        ON listing_amenity_distances
        (listing_id, category, driving_distance_km, driving_duration_min)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS listing_amenity_distances")
    op.execute("DROP TABLE IF EXISTS logs")
    op.execute("DROP TABLE IF EXISTS properties")
    # The vector extension may be shared by other schemas, so it is retained.
