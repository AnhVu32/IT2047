"""Parameterized SQL for conversations + messages.

JSONB columns are passed as JSON strings and cast with ``CAST(... AS jsonb)`` so
the driver never has to adapt Python dicts directly.
"""

from __future__ import annotations

import json
from typing import Any, List, Optional

from src.settings.event import postgres_client


def create_conversation(user_id: int, title: Optional[str]) -> dict:
    rows = postgres_client.fetch_write(
        "INSERT INTO conversations (user_id, title) VALUES (:user_id, :title) "
        "RETURNING id, title, created_at, updated_at",
        user_id=user_id,
        title=title,
    )
    return rows[0]


def list_conversations(user_id: int, limit: int = 50) -> List[dict]:
    return postgres_client.fetch_mappings(
        "SELECT id, title, created_at, updated_at FROM conversations "
        "WHERE user_id = :user_id ORDER BY updated_at DESC LIMIT :limit",
        user_id=user_id,
        limit=limit,
    )


def get_conversation(conversation_id: int, user_id: int) -> Optional[dict]:
    """Fetch a conversation only if it belongs to ``user_id`` (ownership guard)."""
    rows = postgres_client.fetch_mappings(
        "SELECT id, title, created_at, updated_at FROM conversations "
        "WHERE id = :conversation_id AND user_id = :user_id",
        conversation_id=conversation_id,
        user_id=user_id,
    )
    return rows[0] if rows else None


def add_message(
    conversation_id: int,
    role: str,
    content: Optional[str],
    results: Optional[Any] = None,
    parsed_query: Optional[Any] = None,
    agent_metadata: Optional[Any] = None,
) -> dict:
    rows = postgres_client.fetch_write(
        "INSERT INTO messages (conversation_id, role, content, results, parsed_query, agent_metadata) "
        "VALUES (:conversation_id, :role, :content, "
        "CAST(:results AS jsonb), CAST(:parsed_query AS jsonb), CAST(:agent_metadata AS jsonb)) "
        "RETURNING id, role, content, results, parsed_query, agent_metadata, created_at",
        conversation_id=conversation_id,
        role=role,
        content=content,
        results=json.dumps(results, ensure_ascii=False, default=str) if results is not None else None,
        parsed_query=json.dumps(parsed_query, ensure_ascii=False, default=str) if parsed_query is not None else None,
        agent_metadata=json.dumps(agent_metadata, ensure_ascii=False, default=str)
        if agent_metadata is not None
        else "{}",
    )
    return rows[0]


def get_messages(conversation_id: int) -> List[dict]:
    return postgres_client.fetch_mappings(
        "SELECT id, role, content, results, parsed_query, agent_metadata, created_at FROM messages "
        "WHERE conversation_id = :conversation_id ORDER BY created_at ASC, id ASC",
        conversation_id=conversation_id,
    )


def get_recent_messages(conversation_id: int, limit: int = 20) -> List[dict]:
    """Return the newest messages in chronological order for bounded agent context."""
    rows = postgres_client.fetch_mappings(
        "SELECT id, role, content, results, parsed_query, agent_metadata, created_at FROM "
        "(SELECT id, role, content, results, parsed_query, agent_metadata, created_at "
        "FROM messages WHERE conversation_id = :conversation_id "
        "ORDER BY created_at DESC, id DESC LIMIT :limit) recent "
        "ORDER BY created_at ASC, id ASC",
        conversation_id=conversation_id,
        limit=limit,
    )
    return rows


def touch_conversation(conversation_id: int, title: Optional[str] = None) -> None:
    if title is not None:
        postgres_client.execute_write(
            "UPDATE conversations SET updated_at = now(), "
            "title = COALESCE(title, :title) WHERE id = :conversation_id",
            conversation_id=conversation_id,
            title=title,
        )
    else:
        postgres_client.execute_write(
            "UPDATE conversations SET updated_at = now() WHERE id = :conversation_id",
            conversation_id=conversation_id,
        )
