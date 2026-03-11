from __future__ import annotations
from typing import Any

from app.core.constants import LogEvents
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class AuditService:
    def log_execution_start(
        self, trace_id: str, user_id: str, session_id: str, task: str
    ) -> None:
        logger.info(
            LogEvents.REQUEST_STARTED,
            trace_id=trace_id,
            user_id=user_id,
            session_id=session_id,
            task_length=len(task),
        )

    def log_execution_complete(
        self,
        trace_id: str,
        session_id: str,
        status: str,
        tool_calls_count: int,
        provider: str,
        model: str,
        duration_ms: float,
    ) -> None:
        logger.info(
            LogEvents.REQUEST_COMPLETED,
            trace_id=trace_id,
            session_id=session_id,
            status=status,
            tool_calls_count=tool_calls_count,
            provider=provider,
            model=model,
            duration_ms=round(duration_ms, 2),
        )

    def log_llm_call(
        self, trace_id: str, provider: str, model: str, usage: dict[str, Any]
    ) -> None:
        logger.info(
            LogEvents.LLM_CALLED,
            trace_id=trace_id,
            provider=provider,
            model=model,
            **usage,
        )
