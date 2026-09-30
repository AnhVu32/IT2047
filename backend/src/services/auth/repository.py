"""Parameterized SQL access for the ``users`` table.

Uses the ``postgres_client`` context-manager idiom (``fetch_mappings`` /
``fetch_write``) rather than the legacy ``execute_raw_query`` path.
"""

from __future__ import annotations

from typing import Optional

from src.settings.event import postgres_client


def get_by_username(username: str) -> Optional[dict]:
    rows = postgres_client.fetch_mappings(
        "SELECT id, username, password_hash, display_name, is_active "
        "FROM users WHERE username = :username",
        username=username,
    )
    return rows[0] if rows else None


def get_by_id(user_id: int) -> Optional[dict]:
    rows = postgres_client.fetch_mappings(
        "SELECT id, username, password_hash, display_name, is_active "
        "FROM users WHERE id = :user_id",
        user_id=user_id,
    )
    return rows[0] if rows else None


def create_user(username: str, password_hash: str, display_name: Optional[str]) -> dict:
    rows = postgres_client.fetch_write(
        "INSERT INTO users (username, password_hash, display_name) "
        "VALUES (:username, :password_hash, :display_name) "
        "RETURNING id, username, display_name",
        username=username,
        password_hash=password_hash,
        display_name=display_name,
    )
    return rows[0]
