"""Create conversation + message tables for persisted, multi-turn chat.

Revision ID: 20260803_0003
Revises: 20260803_0002
Create Date: 2026-08-03
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260803_0003"
down_revision: Union[str, None] = "20260803_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id),
            title VARCHAR(255),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id BIGSERIAL PRIMARY KEY,
            conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role VARCHAR(16) NOT NULL,
            content TEXT,
            results JSONB,
            parsed_query JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_messages_conversation "
        "ON messages (conversation_id, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_conversations_user "
        "ON conversations (user_id, updated_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS messages")
    op.execute("DROP TABLE IF EXISTS conversations")
