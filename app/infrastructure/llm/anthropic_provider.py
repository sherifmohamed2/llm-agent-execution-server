from __future__ import annotations
from typing import Any

from app.core.config import settings
from app.core.exceptions import LLMProviderError
from app.domain.interfaces.llm_provider import LLMProviderInterface
from app.domain.models.llm_response import LLMResponse
from app.domain.models.session import Message
from app.domain.models.tool_call import ToolCallRequest
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class AnthropicProvider(LLMProviderInterface):
    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or settings.anthropic_api_key
        if not key:
            raise LLMProviderError("Anthropic API key is not configured")
        try:
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=key)
        except ImportError:
            raise LLMProviderError("anthropic package is not installed")

    def provider_name(self) -> str:
        return "anthropic"

    async def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        model_name = model or settings.anthropic_model_name
        try:
            system_prompt, api_messages = self._format_messages(messages)
            kwargs: dict[str, Any] = {
                "model": model_name,
                "max_tokens": 1024,
                "messages": api_messages,
            }
            if system_prompt:
                kwargs["system"] = system_prompt
            if tools:
                kwargs["tools"] = self._convert_tools(tools)

            response = await self._client.messages.create(**kwargs)
            return self._parse_response(response, model_name)

        except LLMProviderError:
            raise
        except Exception as exc:
            logger.error("anthropic_generate_failed", error=str(exc), model=model_name)
            raise LLMProviderError(f"Anthropic API call failed: {exc}")

    @staticmethod
    def _format_messages(
        messages: list[Message],
    ) -> tuple[str, list[dict[str, Any]]]:
        system_prompt = ""
        api_messages = []
        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
            else:
                api_messages.append({"role": msg.role, "content": msg.content})
        return system_prompt, api_messages

    @staticmethod
    def _convert_tools(openai_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        anthropic_tools = []
        for t in openai_tools:
            func = t.get("function", {})
            anthropic_tools.append(
                {
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {}),
                }
            )
        return anthropic_tools

    @staticmethod
    def _parse_response(response: Any, model_name: str) -> LLMResponse:
        content_text = ""
        tool_calls: list[ToolCallRequest] = []

        for block in response.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCallRequest(
                        tool_name=block.name,
                        arguments=block.input if isinstance(block.input, dict) else {},
                        call_id=block.id,
                    )
                )

        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            }

        return LLMResponse(
            content=content_text or None,
            tool_calls=tool_calls,
            model=model_name,
            provider="anthropic",
            usage=usage,
            finish_reason=response.stop_reason or "stop",
        )
