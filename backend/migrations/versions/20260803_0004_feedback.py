"""Create feedback tables: interactions + recommendation_events.

Revision ID: 20260803_0004
Revises: 20260803_0003
Create Date: 2026-08-03

Column shapes mirror gen_user_data/data/csv/{interactions,recommendation_events_v2}.csv
so the offline eval tooling stays compatible, but these tables hold live data.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260803_0004"
down_revision: Union[str, None] = "20260803_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS interactions (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id),
            session_id VARCHAR(64),
            listing_id BIGINT,
            action_type VARCHAR(32) NOT NULL,
            source VARCHAR(32),
            dwell_time_seconds DOUBLE PRECISION,
            implicit_score DOUBLE PRECISION,
            raw_query TEXT,
            conversation_id BIGINT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS recommendation_events (
            id BIGSERIAL PRIMARY KEY,
            result_set_id VARCHAR(64),
            user_id BIGINT,
            session_id VARCHAR(64),
            conversation_id BIGINT,
            raw_query TEXT,
            algorithm_version VARCHAR(64),
            listing_id BIGINT,
            retrieval_rank INTEGER,
            score DOUBLE PRECISION,
            llm_chosen BOOLEAN,
            llm_rank INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_interactions_user "
        "ON interactions (user_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_recommendation_events_user "
        "ON recommendation_events (user_id, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS recommendation_events")
    op.execute("DROP TABLE IF EXISTS interactions")
