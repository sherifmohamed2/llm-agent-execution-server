from __future__ import annotations
from fastapi import APIRouter, Request

from app.api.schemas.execute import (
    ExecuteRequest,
    ExecuteResponse,
    MemoryUsageResponse,
    ModelUsageResponse,
    ToolCallResponse,
)
from app.application.services.audit_service import AuditService
from app.application.services.memory_service import MemoryService
from app.application.services.model_router import ModelRouter
from app.application.services.orchestrator import Orchestrator
from app.application.services.tool_service import ToolService
from app.application.use_cases.execute_task import ExecuteTaskUseCase
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.infrastructure.memory.redis_store import RedisMemoryStore
from app.infrastructure.tools.registry import create_default_registry

router = APIRouter()


def _build_use_case() -> ExecuteTaskUseCase:
    memory_store = RedisMemoryStore()
    memory_service = MemoryService(memory_store)
    tool_registry = create_default_registry()
    tool_service = ToolService(tool_registry)
    model_router = ModelRouter()
    audit_service = AuditService()
    orchestrator = Orchestrator(memory_service, tool_service, model_router, audit_service)
    return ExecuteTaskUseCase(orchestrator, memory_service)


@router.post("/execute", response_model=ExecuteResponse)
async def execute_task(body: ExecuteRequest, request: Request):
    # accepted only for backward compatibility and must match the token subject.
    auth_user_id: str = getattr(request.state, "user_id", "")
    if not auth_user_id:
        raise UnauthorizedError("Authentication required")

    if body.user_id is not None and body.user_id != auth_user_id:
        raise ForbiddenError("body.user_id does not match authenticated identity")

    use_case = _build_use_case()

    result = await use_case.run(
        user_id=auth_user_id,
        task=body.task,
        session_id=body.session_id,
    )

    return ExecuteResponse(
        status=result.status,
        session_id=result.session_id,
        response=result.response,
        tool_calls=[
            ToolCallResponse(
                tool_name=tc["tool_name"],
                call_id=tc.get("call_id"),
                status=tc["status"],
                result=tc.get("result"),
                error=tc.get("error"),
                duration_ms=tc.get("duration_ms", 0),
            )
            for tc in result.tool_calls
        ],
        memory=MemoryUsageResponse(
            session_id=result.session_id,
            message_count=result.message_count,
            has_summary=result.has_summary,
        ),
        model_usage=ModelUsageResponse(
            provider=result.provider,
            model=result.model,
            prompt_tokens=result.usage.get("prompt_tokens"),
            completion_tokens=result.usage.get("completion_tokens"),
            total_tokens=result.usage.get("total_tokens"),
        ),
        trace_id=result.trace_id,
        timestamp=result.timestamp,
    )
