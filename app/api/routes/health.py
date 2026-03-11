from __future__ import annotations
from fastapi import APIRouter

from app.core.config import settings
from app.core.utils import utc_now_iso
from app.infrastructure.memory.redis_store import RedisMemoryStore

router = APIRouter()


@router.get("/health")
async def health_check():
    redis_store = RedisMemoryStore()
    redis_ok = await redis_store.ping()
    await redis_store.close()

    return {
        "status": "healthy" if redis_ok else "degraded",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "checks": {
            "redis": "connected" if redis_ok else "unavailable",
            "llm_provider": settings.default_llm_provider,
        },
        "timestamp": utc_now_iso(),
    }
