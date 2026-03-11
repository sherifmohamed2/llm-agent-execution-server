from __future__ import annotations
from datetime import timedelta
from typing import Any

import jwt

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.utils import utc_now


def create_token(
    user_id: str,
    role: str = "user",
    expires_delta: timedelta | None = None,
) -> str:
    now = utc_now()
    expire = now + (expires_delta or timedelta(hours=1))
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Token has expired")
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Invalid token")
