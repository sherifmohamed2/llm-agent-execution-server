from __future__ import annotations
import asyncio
import time
from typing import Any

from app.core.config import settings
from app.core.constants import LogEvents
from app.core.exceptions import ToolExecutionError
from app.domain.enums.status import ToolCallStatus
from app.domain.models.tool_call import ToolCallRequest, ToolCallResult
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.tools.registry import ToolRegistry

logger = get_logger(__name__)


class ToolService:
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def list_tool_schemas(self) -> list[dict[str, Any]]:
        return self._registry.list_schemas()

    async def execute_tool(
        self, request: ToolCallRequest, trace_id: str
    ) -> ToolCallResult:
        start = time.perf_counter()
        tool_name = request.tool_name

        logger.info(
            LogEvents.TOOL_CALLED,
            trace_id=trace_id,
            tool_name=tool_name,
            arguments=request.arguments,
        )

        try:
            tool = self._registry.get(tool_name)
            result = await asyncio.wait_for(
                tool.execute(request.arguments),
                timeout=settings.tool_timeout_seconds,
            )
            result.call_id = request.call_id
            duration_ms = (time.perf_counter() - start) * 1000
            result.duration_ms = round(duration_ms, 2)

            logger.info(
                LogEvents.TOOL_SUCCEEDED,
                trace_id=trace_id,
                tool_name=tool_name,
                duration_ms=result.duration_ms,
                status=result.status,
            )
            return result

        except asyncio.TimeoutError:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.warning(
                LogEvents.TOOL_FAILED,
                trace_id=trace_id,
                tool_name=tool_name,
                duration_ms=round(duration_ms, 2),
                status=ToolCallStatus.TIMEOUT.value,
            )
            return ToolCallResult(
                tool_name=tool_name,
                call_id=request.call_id,
                status=ToolCallStatus.TIMEOUT.value,
                error=f"Tool '{tool_name}' timed out after {settings.tool_timeout_seconds}s",
                duration_ms=round(duration_ms, 2),
            )
        except ToolExecutionError:
            raise
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error(
                LogEvents.TOOL_FAILED,
                trace_id=trace_id,
                tool_name=tool_name,
                duration_ms=round(duration_ms, 2),
                error=str(exc),
            )
            raise ToolExecutionError(f"Tool '{tool_name}' execution failed: {exc}")
