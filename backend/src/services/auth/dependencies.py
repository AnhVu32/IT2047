"""FastAPI auth dependencies.

``get_current_user`` enforces a valid token; ``get_current_user_optional`` returns
``None`` for anonymous callers so existing public endpoints keep working.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool

from src.services.auth import repository
from src.services.auth.security import decode_token


_bearer = HTTPBearer(auto_error=False)


async def _user_from_credentials(
    credentials: Optional[HTTPAuthorizationCredentials],
) -> Optional[dict]:
    if credentials is None or not credentials.credentials:
        return None
    payload = decode_token(credentials.credentials)
    if not payload or not payload.get("sub"):
        return None
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        return None
    user = await run_in_threadpool(repository.get_by_id, user_id)
    if not user or not user.get("is_active", True):
        return None
    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[dict]:
    return await _user_from_credentials(credentials)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    user = await _user_from_credentials(credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Không có quyền truy cập hoặc phiên đăng nhập đã hết hạn",
        )
    return user
