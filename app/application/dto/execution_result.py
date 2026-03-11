from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionResult:
    status: str
    session_id: str
    response: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    message_count: int = 0
    has_summary: bool = False
    provider: str = ""
    model: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""
    timestamp: str = ""
