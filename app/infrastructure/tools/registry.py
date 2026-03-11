from __future__ import annotations
from typing import Any

from app.core.exceptions import ToolNotFoundError
from app.domain.interfaces.tool import ToolInterface
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.tools.math_tool import MathTool
from app.infrastructure.tools.web_search_tool import WebSearchTool

logger = get_logger(__name__)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolInterface] = {}

    def register(self, tool: ToolInterface) -> None:
        self._tools[tool.name()] = tool
        logger.info("tool_registered", tool_name=tool.name())

    def get(self, name: str) -> ToolInterface:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolNotFoundError(f"Tool '{name}' is not registered")
        return tool

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    def list_schemas(self) -> list[dict[str, Any]]:
        schemas = []
        for tool in self._tools.values():
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name(),
                        "description": tool.description(),
                        "parameters": tool.parameters_schema(),
                    },
                }
            )
        return schemas


def create_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(MathTool())
    registry.register(WebSearchTool())
    return registry
