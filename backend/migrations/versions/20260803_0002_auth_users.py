"""Create the users table for username/password authentication.

Revision ID: 20260803_0002
Revises: 20260730_0001
Create Date: 2026-08-03

Simple username + password accounts (no email). A stable ``users.id`` lets chat
history and feedback/personalization key off an authenticated user.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260803_0002"
down_revision: Union[str, None] = "20260730_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            username VARCHAR(64) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            display_name VARCHAR(255),
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS users")
