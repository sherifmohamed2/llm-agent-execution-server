from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any


class ExecuteRequest(BaseModel):
    user_id: str | None = Field(
        default=None, min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_\-]+$"
    )
    task: str = Field(..., min_length=1, max_length=4096)
    session_id: str | None = Field(default=None, max_length=64)
    metadata: dict[str, Any] | None = Field(default=None)

    model_config = {"extra": "forbid"}


class ToolCallResponse(BaseModel):
    tool_name: str
    call_id: str | None = None
    status: str
    result: Any = None
    error: str | None = None
    duration_ms: float = 0.0


class MemoryUsageResponse(BaseModel):
    session_id: str
    message_count: int
    has_summary: bool


class ModelUsageResponse(BaseModel):
    provider: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ExecuteResponse(BaseModel):
    status: str
    session_id: str
    response: str
    tool_calls: list[ToolCallResponse] = Field(default_factory=list)
    memory: MemoryUsageResponse
    model_usage: ModelUsageResponse
    trace_id: str
    timestamp: str
