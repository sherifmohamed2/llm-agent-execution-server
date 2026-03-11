from __future__ import annotations
import json
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.exceptions import LLMProviderError
from app.domain.interfaces.llm_provider import LLMProviderInterface
from app.domain.models.llm_response import LLMResponse
from app.domain.models.session import Message
from app.domain.models.tool_call import ToolCallRequest
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class OpenAIProvider(LLMProviderInterface):
    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or settings.openai_api_key
        if not key:
            raise LLMProviderError("OpenAI API key is not configured")
        self._client = AsyncOpenAI(api_key=key)

    def provider_name(self) -> str:
        return "openai"

    async def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        model_name = model or settings.openai_model_name
        try:
            api_messages = self._format_messages(messages)
            kwargs: dict[str, Any] = {
                "model": model_name,
                "messages": api_messages,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            response = await self._client.chat.completions.create(**kwargs)
            return self._parse_response(response, model_name)

        except LLMProviderError:
            raise
        except Exception as exc:
            logger.error("openai_generate_failed", error=str(exc), model=model_name)
            raise LLMProviderError(f"OpenAI API call failed: {exc}")

    @staticmethod
    def _format_messages(messages: list[Message]) -> list[dict[str, Any]]:
        formatted = []
        pending_tool_call_ids: set[str] = set()
        for msg in messages:
            # OpenAI tool-calling rules:
            # - `tool` messages must directly respond to a preceding assistant message with `tool_calls`
            # - tool messages must include the matching `tool_call_id`
            if msg.role == "tool":
                if not msg.tool_call_id or msg.tool_call_id not in pending_tool_call_ids:
                    # Skip orphan tool messages (e.g., from older sessions) to avoid 400s
                    continue
                pending_tool_call_ids.discard(msg.tool_call_id)

            entry: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.name:
                entry["name"] = msg.name
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id

            tool_calls = (msg.metadata or {}).get("tool_calls")
            if msg.role == "assistant" and isinstance(tool_calls, list) and tool_calls:
                entry["content"] = None
                entry["tool_calls"] = tool_calls
                for tc in tool_calls:
                    tc_id = tc.get("id")
                    if isinstance(tc_id, str) and tc_id:
                        pending_tool_call_ids.add(tc_id)

            formatted.append(entry)
        return formatted

    @staticmethod
    def _parse_response(response: Any, model_name: str) -> LLMResponse:
        choice = response.choices[0]
        message = choice.message

        tool_calls: list[ToolCallRequest] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls.append(
                    ToolCallRequest(
                        tool_name=tc.function.name,
                        arguments=args,
                        call_id=tc.id,
                    )
                )

        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            model=model_name,
            provider="openai",
            usage=usage,
            finish_reason=choice.finish_reason or "stop",
        )
