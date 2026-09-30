from fastapi import APIRouter, Depends, HTTPException, status
from starlette.concurrency import run_in_threadpool

from src.services.auth import repository
from src.services.auth.dependencies import get_current_user
from src.services.auth.schemas import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    UserPublic,
)
from src.services.auth.security import (
    create_access_token,
    hash_password,
    verify_password,
)


router = APIRouter()


def _auth_response(user_id: int, username: str, display_name) -> dict:
    token = create_access_token(user_id, username)
    payload = AuthResponse(
        access_token=token,
        user=UserPublic(id=user_id, username=username, display_name=display_name),
    )
    return {"data": payload.model_dump(), "errors": [], "status": "success"}


@router.post("/register", summary="Register a username/password account")
async def register(data: RegisterRequest):
    existing = await run_in_threadpool(repository.get_by_username, data.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tên đăng nhập đã tồn tại",
        )
    user = await run_in_threadpool(
        repository.create_user,
        data.username,
        hash_password(data.password),
        data.display_name,
    )
    return _auth_response(user["id"], user["username"], user.get("display_name"))


@router.post("/login", summary="Log in with username/password")
async def login(data: LoginRequest):
    user = await run_in_threadpool(repository.get_by_username, data.username)
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên đăng nhập hoặc mật khẩu không đúng",
        )
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị vô hiệu hóa",
        )
    return _auth_response(user["id"], user["username"], user.get("display_name"))


@router.get("/me", summary="Get the current authenticated user")
async def me(current_user: dict = Depends(get_current_user)):
    payload = UserPublic(
        id=current_user["id"],
        username=current_user["username"],
        display_name=current_user.get("display_name"),
    )
    return {"data": payload.model_dump(), "errors": [], "status": "success"}
