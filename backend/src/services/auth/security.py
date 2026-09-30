"""Password hashing and JWT helpers for simple username/password auth.

A single access token (no refresh) keeps the flow minimal. All config is read
through ``config_value`` (env-first, then ``.env``) so it stays consistent with
the rest of the settings and is safe for the planned config refactor.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from src.settings.config import config_value


_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Default to a 7-day token so there is nothing to refresh; overridable via env.
_DEFAULT_EXPIRE_MINUTES = 60 * 24 * 7


def _is_debug() -> bool:
    return str(config_value("DEBUG", "false")).lower() in {"1", "true", "yes"}


def _secret_key() -> str:
    secret = config_value("ACCESS_TOKEN_SECRET_KEY")
    if not secret or secret == "changeme":
        # A default/empty secret makes tokens trivially forgeable. Tolerate it only
        # in debug so local dev still works; fail loudly everywhere else.
        if _is_debug():
            return secret or "changeme"
        raise RuntimeError(
            "ACCESS_TOKEN_SECRET_KEY is not set. Refusing to sign or verify JWTs with a "
            "default secret outside debug mode — set ACCESS_TOKEN_SECRET_KEY in the environment."
        )
    return secret


def _algorithm() -> str:
    return config_value("ALGORITHM", "HS256") or "HS256"


def _expire_minutes() -> int:
    try:
        return int(config_value("ACCESS_TOKEN_EXPIRE_MINUTES", _DEFAULT_EXPIRE_MINUTES))
    except (TypeError, ValueError):
        return _DEFAULT_EXPIRE_MINUTES


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd_context.verify(password, password_hash)
    except ValueError:
        return False


def create_access_token(user_id: int, username: str) -> str:
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "iat": now,
        "exp": now + timedelta(minutes=_expire_minutes()),
    }
    return jwt.encode(payload, _secret_key(), algorithm=_algorithm())


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Return the token payload, or ``None`` if it is invalid/expired/unconfigured.

    Fails closed: a missing secret (RuntimeError from ``_secret_key``) yields an
    unauthenticated result rather than a crash, while ``create_access_token`` still
    raises so the misconfiguration surfaces at login/register.
    """
    try:
        return jwt.decode(token, _secret_key(), algorithms=[_algorithm()])
    except (JWTError, RuntimeError):
        return None
