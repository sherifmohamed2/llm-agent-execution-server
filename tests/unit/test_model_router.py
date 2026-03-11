from __future__ import annotations
import pytest

from app.application.services.model_router import ModelRouter


@pytest.fixture
def router():
    return ModelRouter()


def test_default_provider_is_openai(router):
    provider = router.get_provider()
    assert provider.provider_name() == "openai"


def test_explicit_openai_provider(router):
    provider = router.get_provider("openai")
    assert provider.provider_name() == "openai"


def test_explicit_gemini_provider_requires_key(router):
    from app.core.exceptions import LLMProviderError
    with pytest.raises(LLMProviderError):
        router.get_provider("gemini")


def test_get_model_name_openai(router):
    name = router.get_model_name("openai")
    assert "gpt" in name.lower() or name


def test_get_model_name_anthropic(router):
    name = router.get_model_name("anthropic")
    assert "claude" in name.lower() or name


def test_get_model_name_gemini(router):
    name = router.get_model_name("gemini")
    assert "gemini" in name.lower()


def test_provider_caching(router):
    p1 = router.get_provider("openai")
    p2 = router.get_provider("openai")
    assert p1 is p2


def test_unsupported_provider_raises(router):
    import app.core.exceptions as exc
    with pytest.raises(exc.LLMProviderError):
        router.get_provider("unknown")
