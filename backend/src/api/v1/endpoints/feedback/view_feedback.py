from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from starlette.concurrency import run_in_threadpool

from src.services.auth.dependencies import get_current_user, get_current_user_optional
from src.services.feedback import repository
from src.services.feedback.schemas import InteractionRequest
from src.services.feedback.scoring import implicit_score


router = APIRouter()


@router.get("/saved", summary="Listing IDs the current user has saved")
async def list_saved(current_user: dict = Depends(get_current_user)):
    listing_ids = await run_in_threadpool(repository.get_saved_listing_ids, current_user["id"])
    return {"data": listing_ids, "errors": [], "status": "success"}


@router.post("/interaction", summary="Record a user interaction (view/save/contact/share/thumbs)")
async def record_interaction(
    data: InteractionRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    action = data.normalized_action()
    if action is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"action_type không hợp lệ: {data.action_type}",
        )

    user_id = current_user["id"] if current_user else None
    # Anonymous callers must supply a session_id so their signal is still grouped.
    if user_id is None and not data.session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cần đăng nhập hoặc cung cấp session_id",
        )

    score = implicit_score(action, data.dwell_time_seconds)
    row = await run_in_threadpool(
        repository.insert_interaction,
        user_id,
        data.session_id,
        data.listing_id,
        action,
        data.source,
        data.dwell_time_seconds,
        score,
        data.raw_query,
        data.conversation_id,
    )
    return {
        "data": {"id": row["id"], "action_type": action, "implicit_score": score},
        "errors": [],
        "status": "success",
    }
