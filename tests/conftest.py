from __future__ import annotations
import os

os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("DEFAULT_LLM_PROVIDER", "openai")
os.environ.setdefault(
    "JWT_SECRET",
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
)
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("GEMINI_API_KEY", "")

import pytest
from app.infrastructure.security.jwt import create_token


@pytest.fixture
def valid_token() -> str:
    return create_token(user_id="test_user", role="user")


@pytest.fixture
def admin_token() -> str:
    return create_token(user_id="admin_user", role="admin")


@pytest.fixture
def auth_headers(valid_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {valid_token}"}


@pytest.fixture
def fake_llm_provider():
    """Minimal in-memory provider for integration tests that hit /execute."""
    from app.domain.models.llm_response import LLMResponse
    from app.domain.interfaces.llm_provider import LLMProviderInterface

    class FakeLLMProvider(LLMProviderInterface):
        def provider_name(self) -> str:
            return "openai"

        async def generate(self, messages, tools=None, model=None):
            return LLMResponse(
                content="Test response.",
                tool_calls=[],
                model=model or "gpt-4o-mini",
                provider="openai",
                usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                finish_reason="stop",
            )

    return FakeLLMProvider()
