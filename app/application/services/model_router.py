from __future__ import annotations
from app.core.config import settings
from app.domain.interfaces.llm_provider import LLMProviderInterface
from app.infrastructure.llm.factory import create_llm_provider
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class ModelRouter:
    def __init__(self) -> None:
        self._providers: dict[str, LLMProviderInterface] = {}

    def get_provider(self, provider_name: str | None = None) -> LLMProviderInterface:
        name = (provider_name or settings.default_llm_provider).lower()

        if name in self._providers:
            return self._providers[name]

        provider = create_llm_provider(name)
        self._providers[name] = provider

        logger.info(
            "model_router_provider_created",
            provider=provider.provider_name(),
            requested=name,
        )
        return provider

    def get_model_name(self, provider_name: str | None = None) -> str:
        name = (provider_name or settings.default_llm_provider).lower()
        if name == "openai":
            return settings.openai_model_name
        elif name == "anthropic":
            return settings.anthropic_model_name
        elif name == "gemini":
            return settings.gemini_model_name
        return settings.openai_model_name
