from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCallRequest:
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: str | None = None


@dataclass
class ToolCallResult:
    tool_name: str
    call_id: str | None
    status: str  # ToolCallStatus value
    result: Any = None
    error: str | None = None
    duration_ms: float = 0.0
