from __future__ import annotations
import time

import redis.asyncio as aioredis
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.constants import RedisKeys
from app.core.utils import utc_now_iso
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_url: str | None = None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._redis_url = redis_url or settings.redis_url
        self._client: aioredis.Redis | None = None
        self._limit = settings.rate_limit_per_minute

    async def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(self._redis_url, decode_responses=True)
        return self._client

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in {"/api/v1/health", "/docs", "/openapi.json", "/redoc", "/"}:
            return await call_next(request)

        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            return await call_next(request)

        try:
            allowed = await self._check_rate_limit(user_id)
        except Exception as exc:
            logger.warning("rate_limit_check_failed", error=str(exc))
            return await call_next(request)

        if not allowed:
            logger.warning("rate_limit_exceeded", user_id=user_id)
            return JSONResponse(
                status_code=429,
                content={
                    "error_code": "RATE_LIMITED",
                    "message": f"Rate limit exceeded. Maximum {self._limit} requests per minute.",
                    "details": None,
                    "trace_id": getattr(request.state, "trace_id", None),
                    "timestamp": utc_now_iso(),
                },
            )

        return await call_next(request)

    async def _check_rate_limit(self, user_id: str) -> bool:
        client = await self._get_client()
        window = str(int(time.time()) // 60)
        key = RedisKeys.rate_limit(user_id, window)

        current = await client.incr(key)
        if current == 1:
            await client.expire(key, 60)

        return current <= self._limit
