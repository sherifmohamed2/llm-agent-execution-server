from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from app.domain.models.tool_call import ToolCallRequest


@dataclass
class LLMResponse:
    content: str | None = None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    model: str = ""
    provider: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    finish_reason: str = ""

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0
