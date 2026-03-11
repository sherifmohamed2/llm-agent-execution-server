from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any

from app.domain.models.llm_response import LLMResponse
from app.domain.models.session import Message


class LLMProviderInterface(ABC):
    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        ...

    @abstractmethod
    def provider_name(self) -> str:
        ...
