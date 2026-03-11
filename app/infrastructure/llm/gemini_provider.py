from __future__ import annotations
import asyncio
from typing import Any

from app.core.config import settings
from app.core.exceptions import LLMProviderError
from app.domain.interfaces.llm_provider import LLMProviderInterface
from app.domain.models.llm_response import LLMResponse
from app.domain.models.session import Message
from app.domain.models.tool_call import ToolCallRequest
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class GeminiProvider(LLMProviderInterface):
    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or settings.gemini_api_key
        if not key:
            raise LLMProviderError("Gemini API key is not configured")
        try:
            import google.generativeai as genai
            genai.configure(api_key=key)
            self._genai = genai
        except ImportError:
            raise LLMProviderError("google-generativeai package is not installed")

    def provider_name(self) -> str:
        return "gemini"

    async def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        model_name = model or settings.gemini_model_name
        try:
            generative_model = self._genai.GenerativeModel(model_name)
            gemini_tools = self._convert_tools(tools) if tools else None
            contents = self._format_messages(messages)

            def _generate() -> Any:
                kwargs: dict[str, Any] = {"contents": contents}
                if gemini_tools:
                    kwargs["tools"] = gemini_tools
                return generative_model.generate_content(**kwargs)

            response = await asyncio.to_thread(_generate)
            return self._parse_response(response, model_name)

        except LLMProviderError:
            raise
        except Exception as exc:
            logger.error("gemini_generate_failed", error=str(exc), model=model_name)
            raise LLMProviderError(f"Gemini API call failed: {exc}")

    def _format_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        contents = []
        for msg in messages:
            if msg.role == "system":
                contents.append({"role": "user", "parts": [{"text": msg.content}]})
            elif msg.role == "user":
                contents.append({"role": "user", "parts": [{"text": msg.content}]})
            elif msg.role == "assistant":
                contents.append({"role": "model", "parts": [{"text": msg.content}]})
            elif msg.role == "tool":
                parts = [{"function_response": {"name": msg.name or "", "response": {"result": msg.content}}}]
                contents.append({"role": "user", "parts": parts})
            else:
                contents.append({"role": "user", "parts": [{"text": msg.content}]})
        return contents

    def _convert_tools(self, openai_tools: list[dict[str, Any]]) -> list[Any]:
        declarations = []
        for t in openai_tools:
            func = t.get("function", {})
            declarations.append(
                self._genai.protos.FunctionDeclaration(
                    name=func.get("name", ""),
                    description=func.get("description", ""),
                    parameters=func.get("parameters", {}),
                )
            )
        return [self._genai.protos.Tool(function_declarations=declarations)]

    def _parse_response(self, response: Any, model_name: str) -> LLMResponse:
        content_text = ""
        tool_calls: list[ToolCallRequest] = []
        usage = {}

        if not response.candidates:
            return LLMResponse(
                content="No response generated.",
                tool_calls=[],
                model=model_name,
                provider="gemini",
                usage=usage,
                finish_reason="stop",
            )

        candidate = response.candidates[0]
        if candidate.content and candidate.content.parts:
            for part in candidate.content.parts:
                if hasattr(part, "text") and part.text:
                    content_text += part.text
                if hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    args = dict(fc.args) if hasattr(fc, "args") and fc.args else {}
                    tool_calls.append(
                        ToolCallRequest(
                            tool_name=fc.name,
                            arguments=args,
                            call_id=getattr(fc, "id", None),
                        )
                    )

        if response.usage_metadata:
            um = response.usage_metadata
            usage = {
                "prompt_tokens": getattr(um, "prompt_token_count", 0) or 0,
                "completion_tokens": getattr(um, "candidates_token_count", 0) or 0,
                "total_tokens": getattr(um, "total_token_count", 0) or 0,
            }

        return LLMResponse(
            content=content_text or None,
            tool_calls=tool_calls,
            model=model_name,
            provider="gemini",
            usage=usage,
            finish_reason=getattr(candidate, "finish_reason", "stop") or "stop",
        )
