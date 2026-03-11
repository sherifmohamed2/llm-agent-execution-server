from __future__ import annotations
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.constants import Defaults, RedisKeys
from app.core.exceptions import MemoryStoreError
from app.core.utils import safe_json_dumps, safe_json_loads
from app.domain.interfaces.memory_store import MemoryStoreInterface
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class RedisMemoryStore(MemoryStoreInterface):
    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url or settings.redis_url
        self._client: aioredis.Redis | None = None

    async def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(
                self._redis_url, decode_responses=True
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def ping(self) -> bool:
        try:
            client = await self._get_client()
            return await client.ping()
        except Exception:
            return False

    async def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        try:
            client = await self._get_client()
            key = RedisKeys.messages(session_id)
            raw_messages = await client.lrange(key, 0, -1)
            messages = []
            for raw in raw_messages:
                parsed = safe_json_loads(raw)
                if parsed:
                    messages.append(parsed)
            return messages
        except Exception as exc:
            logger.error("redis_get_messages_failed", session_id=session_id, error=str(exc))
            raise MemoryStoreError(f"Failed to get messages: {exc}")

    async def append_message(self, session_id: str, message: dict[str, Any]) -> None:
        try:
            client = await self._get_client()
            key = RedisKeys.messages(session_id)
            await client.rpush(key, safe_json_dumps(message))
            await client.expire(key, Defaults.SESSION_TTL_SECONDS)
        except Exception as exc:
            logger.error("redis_append_message_failed", session_id=session_id, error=str(exc))
            raise MemoryStoreError(f"Failed to append message: {exc}")

    async def get_summary(self, session_id: str) -> str | None:
        try:
            client = await self._get_client()
            key = RedisKeys.summary(session_id)
            return await client.get(key)
        except Exception as exc:
            logger.error("redis_get_summary_failed", session_id=session_id, error=str(exc))
            raise MemoryStoreError(f"Failed to get summary: {exc}")

    async def save_summary(self, session_id: str, summary: str) -> None:
        try:
            client = await self._get_client()
            key = RedisKeys.summary(session_id)
            await client.set(key, summary, ex=Defaults.SESSION_TTL_SECONDS)
        except Exception as exc:
            logger.error("redis_save_summary_failed", session_id=session_id, error=str(exc))
            raise MemoryStoreError(f"Failed to save summary: {exc}")

    async def append_tool_history(
        self, session_id: str, tool_record: dict[str, Any]
    ) -> None:
        try:
            client = await self._get_client()
            key = RedisKeys.tool_history(session_id)
            await client.rpush(key, safe_json_dumps(tool_record))
            await client.expire(key, Defaults.SESSION_TTL_SECONDS)
        except Exception as exc:
            logger.error("redis_append_tool_history_failed", session_id=session_id, error=str(exc))
            raise MemoryStoreError(f"Failed to append tool history: {exc}")

    async def trim_messages(self, session_id: str, keep_last: int) -> None:
        try:
            client = await self._get_client()
            key = RedisKeys.messages(session_id)
            total = await client.llen(key)
            if total > keep_last:
                await client.ltrim(key, total - keep_last, -1)
        except Exception as exc:
            logger.error("redis_trim_messages_failed", session_id=session_id, error=str(exc))
            raise MemoryStoreError(f"Failed to trim messages: {exc}")

    async def get_session_owner(self, session_id: str) -> str | None:
        try:
            client = await self._get_client()
            return await client.get(RedisKeys.session_owner(session_id))
        except Exception as exc:
            logger.error("redis_get_session_owner_failed", session_id=session_id, error=str(exc))
            raise MemoryStoreError(f"Failed to get session owner: {exc}")

    async def set_session_owner_if_unset(self, session_id: str, user_id: str) -> bool:
        """Atomically claim the session owner (SET NX). Returns True when first set."""
        try:
            client = await self._get_client()
            result = await client.set(
                RedisKeys.session_owner(session_id),
                user_id,
                ex=Defaults.SESSION_TTL_SECONDS,
                nx=True,
            )
            return result is not None
        except Exception as exc:
            logger.error("redis_set_session_owner_failed", session_id=session_id, error=str(exc))
            raise MemoryStoreError(f"Failed to set session owner: {exc}")
