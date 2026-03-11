from __future__ import annotations
from app.core.config import settings
from app.core.exceptions import LLMProviderError
from app.domain.enums.llm_provider import LLMProviderName
from app.domain.interfaces.llm_provider import LLMProviderInterface
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


def create_llm_provider(provider_name: str | None = None) -> LLMProviderInterface:
    raw = (provider_name or settings.default_llm_provider)
    name = (raw or "").strip().lower().replace("-", "_")

    # Allow common aliases from env/config
    if name in {"openai_api", "openai_api_key", "openai_key", "openai_provider", "openaiapi"}:
        name = LLMProviderName.OPENAI.value
    elif name in {"anthropic_api", "claude", "claude_api", "anthropic_provider"}:
        name = LLMProviderName.ANTHROPIC.value
    elif name in {"google", "google_gemini", "gemini_api", "google_genai"}:
        name = LLMProviderName.GEMINI.value

    if name == LLMProviderName.OPENAI.value:
        if not settings.openai_api_key:
            raise LLMProviderError("OpenAI API key is not configured. Set OPENAI_API_KEY.")
        from app.infrastructure.llm.openai_provider import OpenAIProvider
        return OpenAIProvider()

    if name == LLMProviderName.ANTHROPIC.value:
        if not settings.anthropic_api_key:
            raise LLMProviderError("Anthropic API key is not configured. Set ANTHROPIC_API_KEY.")
        from app.infrastructure.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider()

    if name == LLMProviderName.GEMINI.value:
        if not settings.gemini_api_key:
            raise LLMProviderError("Gemini API key is not configured. Set GEMINI_API_KEY.")
        from app.infrastructure.llm.gemini_provider import GeminiProvider
        return GeminiProvider()

    raise LLMProviderError(
        f"Unsupported LLM provider: {raw!r}. Use DEFAULT_LLM_PROVIDER=openai|anthropic|gemini"
    )