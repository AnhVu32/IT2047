"""Store safe LangGraph routing/tool metadata with chat messages.

Revision ID: 20260805_0005
Revises: 20260803_0004
Create Date: 2026-08-05
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260805_0005"
down_revision: Union[str, None] = "20260803_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE messages ADD COLUMN IF NOT EXISTS agent_metadata JSONB "
        "NOT NULL DEFAULT '{}'::jsonb"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE messages DROP COLUMN IF EXISTS agent_metadata")
