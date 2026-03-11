from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Session:
    session_id: str
    user_id: str
    messages: list[Message] = field(default_factory=list)
    summary: str | None = None
    created_at: str | None = None
