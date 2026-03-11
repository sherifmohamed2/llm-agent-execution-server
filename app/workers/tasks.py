from __future__ import annotations
import asyncio
from typing import Any

from app.infrastructure.logging.logger import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(bind=True, name="summarize_session_memory", max_retries=3)
def summarize_session_memory(self, session_id: str) -> dict[str, Any]:
    """
    Background task to summarize session memory when it exceeds threshold.
    Uses the LLM to compress older messages into a summary.
    """
    try:
        logger.info("summarize_task_started", session_id=session_id)
        result = asyncio.get_event_loop().run_until_complete(
            _run_summarization(session_id)
        )
        logger.info("summarize_task_completed", session_id=session_id)
        return result
    except Exception as exc:
        logger.error("summarize_task_failed", session_id=session_id, error=str(exc))
        raise self.retry(exc=exc, countdown=30)


async def _run_summarization(session_id: str) -> dict[str, Any]:
    from app.application.services.memory_service import MemoryService
    from app.infrastructure.memory.redis_store import RedisMemoryStore

    store = RedisMemoryStore()
    memory_service = MemoryService(store)

    messages = await memory_service.load_messages(session_id)

    if len(messages) < 10:
        await store.close()
        return {"session_id": session_id, "action": "skipped", "reason": "not enough messages"}

    content_parts = []
    for msg in messages[:-5]:
        content_parts.append(f"{msg.role}: {msg.content[:200]}")
    summary_text = "Previous conversation summary: " + " | ".join(content_parts)

    await memory_service.save_summary(session_id, summary_text)
    await memory_service.trim_if_needed(session_id)
    await store.close()

    return {"session_id": session_id, "action": "summarized", "message_count": len(messages)}
