from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any

from app.domain.models.tool_call import ToolCallResult


class ToolInterface(ABC):
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def description(self) -> str:
        ...

    @abstractmethod
    def parameters_schema(self) -> dict[str, Any]:
        ...

    @abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> ToolCallResult:
        ...
