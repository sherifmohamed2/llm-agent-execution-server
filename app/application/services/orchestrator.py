from __future__ import annotations
import json
import time
from typing import Any

from app.application.dto.execution_result import ExecutionResult
from app.application.services.audit_service import AuditService
from app.application.services.memory_service import MemoryService
from app.application.services.model_router import ModelRouter
from app.application.services.tool_service import ToolService
from app.core.constants import Limits, LogEvents
from app.core.utils import utc_now_iso
from app.domain.enums.status import ExecutionStatus
from app.domain.models.session import Message
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "You are a helpful AI assistant with access to tools. "
    "Use the provided tools when appropriate to answer user questions. "
    "For math calculations, use the math tool. "
    "For information lookup, use the web_search tool."
)


class Orchestrator:
    def __init__(
        self,
        memory_service: MemoryService,
        tool_service: ToolService,
        model_router: ModelRouter,
        audit_service: AuditService,
    ) -> None:
        self._memory = memory_service
        self._tools = tool_service
        self._router = model_router
        self._audit = audit_service

    async def execute(
        self,
        user_id: str,
        task: str,
        session_id: str,
        trace_id: str,
    ) -> ExecutionResult:
        start = time.perf_counter()

        self._audit.log_execution_start(trace_id, user_id, session_id, task)

        history = await self._memory.load_messages(session_id)
        await self._memory.append_user_message(session_id, task)

        messages = self._assemble_messages(history, task)

        provider = self._router.get_provider()
        model_name = self._router.get_model_name()
        tool_schemas = self._tools.list_tool_schemas()

        logger.info(LogEvents.LLM_CALLED, trace_id=trace_id, provider=provider.provider_name(), model=model_name)
        llm_response = await provider.generate(messages, tools=tool_schemas, model=model_name)
        self._audit.log_llm_call(trace_id, provider.provider_name(), model_name, llm_response.usage)

        tool_call_results: list[dict[str, Any]] = []

        if llm_response.has_tool_calls:
            # Persist the assistant tool-call declaration (required by OpenAI-style tool calling)
            tool_calls_payload: list[dict[str, Any]] = []
            for tc in llm_response.tool_calls[: Limits.MAX_TOOL_CALLS_PER_TURN]:
                tool_calls_payload.append(
                    {
                        "id": tc.call_id,
                        "type": "function",
                        "function": {
                            "name": tc.tool_name,
                            "arguments": json.dumps(tc.arguments or {}, ensure_ascii=False),
                        },
                    }
                )

            if tool_calls_payload:
                await self._memory.append_assistant_tool_calls(session_id, tool_calls_payload)
                messages.append(
                    Message(
                        role="assistant",
                        content="",
                        metadata={"tool_calls": tool_calls_payload},
                    )
                )

            for tc_request in llm_response.tool_calls[: Limits.MAX_TOOL_CALLS_PER_TURN]:
                tc_result = await self._tools.execute_tool(tc_request, trace_id)

                result_data = tc_result.result if tc_result.result else tc_result.error
                tool_call_results.append(
                    {
                        "tool_name": tc_result.tool_name,
                        "call_id": tc_result.call_id,
                        "status": tc_result.status,
                        "result": tc_result.result,
                        "error": tc_result.error,
                        "duration_ms": tc_result.duration_ms,
                    }
                )

                await self._memory.record_tool_call(
                    session_id,
                    {
                        "trace_id": trace_id,
                        "tool_name": tc_result.tool_name,
                        "status": tc_result.status,
                        "duration_ms": tc_result.duration_ms,
                    },
                )

                tool_content = json.dumps(result_data, default=str) if result_data else ""
                await self._memory.append_tool_message(
                    session_id,
                    content=tool_content,
                    tool_call_id=tc_result.call_id,
                    name=tc_result.tool_name,
                )
                messages.append(
                    Message(
                        role="tool",
                        content=tool_content,
                        tool_call_id=tc_result.call_id,
                        name=tc_result.tool_name,
                    )
                )

            logger.info(LogEvents.LLM_CALLED, trace_id=trace_id, provider=provider.provider_name(), model=model_name, reason="follow_up_after_tools")
            llm_response = await provider.generate(messages, tools=tool_schemas, model=model_name)
            self._audit.log_llm_call(trace_id, provider.provider_name(), model_name, llm_response.usage)

        final_response = llm_response.content or "No response generated."
        await self._memory.append_assistant_message(session_id, final_response)

        await self._memory.trim_if_needed(session_id)

        message_count = await self._memory.get_message_count(session_id)
        summary = await self._memory.get_summary(session_id)

        duration_ms = (time.perf_counter() - start) * 1000
        status = ExecutionStatus.COMPLETED.value

        self._audit.log_execution_complete(
            trace_id=trace_id,
            session_id=session_id,
            status=status,
            tool_calls_count=len(tool_call_results),
            provider=provider.provider_name(),
            model=model_name,
            duration_ms=duration_ms,
        )

        return ExecutionResult(
            status=status,
            session_id=session_id,
            response=final_response,
            tool_calls=tool_call_results,
            message_count=message_count,
            has_summary=summary is not None,
            provider=provider.provider_name(),
            model=model_name,
            usage=llm_response.usage,
            trace_id=trace_id,
            timestamp=utc_now_iso(),
        )

    @staticmethod
    def _assemble_messages(history: list[Message], task: str) -> list[Message]:
        messages = [Message(role="system", content=SYSTEM_PROMPT)]
        messages.extend(history)
        messages.append(Message(role="user", content=task))
        return messages
