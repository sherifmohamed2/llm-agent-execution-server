from __future__ import annotations
from app.application.dto.execution_result import ExecutionResult
from app.application.services.memory_service import MemoryService
from app.application.services.orchestrator import Orchestrator
from app.core.exceptions import BadRequestError
from app.core.utils import generate_session_id, generate_trace_id, sanitize_task, validate_user_id


class ExecuteTaskUseCase:
    def __init__(self, orchestrator: Orchestrator, memory_service: MemoryService) -> None:
        self._orchestrator = orchestrator
        self._memory = memory_service

    async def run(
        self,
        user_id: str,
        task: str,
        session_id: str | None = None,
    ) -> ExecutionResult:
        try:
            user_id = validate_user_id(user_id)
        except ValueError as exc:
            raise BadRequestError(str(exc))

        try:
            task = sanitize_task(task)
        except ValueError as exc:
            raise BadRequestError(str(exc))

        session_id = session_id or generate_session_id()
        trace_id = generate_trace_id()

        # Bind or verify session ownership before touching any session data.
        await self._memory.verify_or_bind_session_owner(session_id, user_id)

        return await self._orchestrator.execute(
            user_id=user_id,
            task=task,
            session_id=session_id,
            trace_id=trace_id,
        )
