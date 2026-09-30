"""Persisted and guest multi-turn chat backed by the LangGraph agent service."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from src.services.agent import chat_agent_service
from src.services.auth.dependencies import get_current_user, get_current_user_optional
from src.services.chat import repository


router = APIRouter()
_HISTORY_MESSAGES = 20
_CONTEXT_LISTINGS = 20


class ClientHistoryTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant", "ai"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)
    conversation_id: Optional[int] = None
    top_k: int = Field(default=3, ge=1, le=20)
    filters: Dict[str, Any] = Field(default_factory=dict)
    # Guest-only state. Authenticated callers are always rebuilt from the
    # server-owned conversation/checkpoint to prevent history tampering.
    history: List[ClientHistoryTurn] = Field(default_factory=list, max_length=_HISTORY_MESSAGES)
    context_listing_ids: List[str] = Field(default_factory=list, max_length=_CONTEXT_LISTINGS)
    context_parsed_query: Optional[Dict[str, Any]] = None


def _history_from_messages(messages: list[dict]) -> list[dict]:
    """Turn stored rows into bounded text history for first graph checkpoint seed."""
    history = []
    for row in messages:
        content = (row.get("content") or "").strip()
        if not content:
            continue
        role = "assistant" if row.get("role") == "assistant" else "user"
        history.append({"role": role, "content": content})
    return history[-_HISTORY_MESSAGES:]


def _latest_recommendation(messages: list[dict]) -> tuple[list[dict], Optional[dict]]:
    """Find the latest trusted server-side recommendation context."""
    for row in reversed(messages):
        results = row.get("results")
        if isinstance(results, list) and results:
            parsed = row.get("parsed_query")
            return results, parsed if isinstance(parsed, dict) else None
    return [], None


@router.post("", summary="Send a LangGraph multi-agent chat message")
async def chat(
    data: ChatRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    user_id = current_user["id"] if current_user else None
    conversation_id: Optional[int] = None
    history: list[dict]
    latest_results: list[dict]
    latest_parsed_query: Optional[dict]

    if user_id is not None:
        if data.conversation_id is not None:
            conversation = await run_in_threadpool(
                repository.get_conversation, data.conversation_id, user_id
            )
            if conversation is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Không tìm thấy cuộc trò chuyện",
                )
            conversation_id = data.conversation_id
            prior = await run_in_threadpool(
                repository.get_recent_messages, conversation_id, _HISTORY_MESSAGES
            )
        else:
            conversation = await run_in_threadpool(
                repository.create_conversation, user_id, data.message[:80]
            )
            conversation_id = conversation["id"]
            prior = []
        history = _history_from_messages(prior)
        latest_results, latest_parsed_query = _latest_recommendation(prior)
        await run_in_threadpool(
            repository.add_message, conversation_id, "user", data.message
        )
    else:
        if data.conversation_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Khách chưa đăng nhập không dùng conversation_id",
            )
        history = [turn.model_dump() for turn in data.history]
        latest_results = await chat_agent_service.hydrate_guest_context(data.context_listing_ids)
        latest_parsed_query = data.context_parsed_query

    try:
        result = await chat_agent_service.run(
            message=data.message,
            history=history,
            latest_results=latest_results,
            latest_parsed_query=latest_parsed_query,
            filters=data.filters,
            top_k=data.top_k,
            user_id=user_id,
            conversation_id=conversation_id,
        )
    except Exception as exc:  # noqa: BLE001 - hide infrastructure details from clients
        logger.exception("LangGraph chat failed for conversation {}", conversation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Đã xảy ra lỗi khi xử lý cuộc trò chuyện. Vui lòng thử lại sau.",
        ) from exc

    if conversation_id is not None:
        await run_in_threadpool(
            repository.add_message,
            conversation_id,
            "assistant",
            result["assistant_answer"],
            result["results"] if result["search_performed"] else None,
            result["parsed_query"] if result["search_performed"] else None,
            result["agent_metadata"],
        )
        await run_in_threadpool(repository.touch_conversation, conversation_id)

    payload = {
        "conversation_id": conversation_id,
        "query": data.message,
        **result,
    }
    return {"data": payload, "errors": [], "status": "success"}


@router.get("/conversations", summary="List the current user's conversations")
async def list_conversations(current_user: dict = Depends(get_current_user)):
    rows = await run_in_threadpool(repository.list_conversations, current_user["id"])
    return {"data": rows, "errors": [], "status": "success"}


@router.get("/conversations/{conversation_id}", summary="Full message history of a conversation")
async def get_conversation(conversation_id: int, current_user: dict = Depends(get_current_user)):
    conversation = await run_in_threadpool(
        repository.get_conversation, conversation_id, current_user["id"]
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cuộc trò chuyện")
    messages = await run_in_threadpool(repository.get_messages, conversation_id)
    return {
        "data": {"conversation": conversation, "messages": messages},
        "errors": [],
        "status": "success",
    }
