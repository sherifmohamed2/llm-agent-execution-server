from __future__ import annotations
import time
from typing import Any

from app.domain.enums.status import ToolCallStatus
from app.domain.enums.tool_name import ToolName
from app.domain.interfaces.tool import ToolInterface
from app.domain.models.tool_call import ToolCallResult

MOCK_RESULTS: dict[str, list[dict[str, str]]] = {
    "default": [
        {
            "title": "Wikipedia — General Knowledge",
            "url": "https://en.wikipedia.org/wiki/Main_Page",
            "snippet": "Wikipedia is a free online encyclopedia with articles on a wide range of topics.",
        },
        {
            "title": "Stack Overflow — Programming Q&A",
            "url": "https://stackoverflow.com",
            "snippet": "Stack Overflow is the largest online community for developers to learn and share knowledge.",
        },
    ],
    "python": [
        {
            "title": "Python.org — Official Python Documentation",
            "url": "https://docs.python.org/3/",
            "snippet": "The official Python documentation covers the standard library, language reference, and tutorials.",
        },
        {
            "title": "Real Python — Python Tutorials",
            "url": "https://realpython.com",
            "snippet": "Real Python provides tutorials, articles, and resources for Python developers at all levels.",
        },
    ],
    "ai": [
        {
            "title": "OpenAI — AI Research and Deployment",
            "url": "https://openai.com",
            "snippet": "OpenAI is an AI research company building safe and beneficial artificial general intelligence.",
        },
        {
            "title": "Anthropic — AI Safety Research",
            "url": "https://anthropic.com",
            "snippet": "Anthropic is an AI safety company focused on building reliable, interpretable AI systems.",
        },
    ],
}


class WebSearchTool(ToolInterface):
    def name(self) -> str:
        return ToolName.WEB_SEARCH.value

    def description(self) -> str:
        return "Search the web for information on a given query (mock implementation)."

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query string",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 3,
                },
            },
            "required": ["query"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolCallResult:
        start = time.perf_counter()
        query = arguments.get("query", "")
        max_results = min(arguments.get("max_results", 3), 5)

        if not query or not isinstance(query, str):
            return ToolCallResult(
                tool_name=self.name(),
                call_id=None,
                status=ToolCallStatus.VALIDATION_ERROR.value,
                error="Missing or invalid 'query' argument",
            )

        results = self._mock_search(query.lower(), max_results)
        duration_ms = (time.perf_counter() - start) * 1000

        return ToolCallResult(
            tool_name=self.name(),
            call_id=None,
            status=ToolCallStatus.SUCCESS.value,
            result={"query": query, "results": results, "count": len(results)},
            duration_ms=round(duration_ms, 2),
        )

    @staticmethod
    def _mock_search(query: str, max_results: int) -> list[dict[str, str]]:
        for keyword, results in MOCK_RESULTS.items():
            if keyword in query:
                return results[:max_results]
        return MOCK_RESULTS["default"][:max_results]
