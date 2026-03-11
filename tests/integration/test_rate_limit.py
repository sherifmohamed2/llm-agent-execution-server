from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.infrastructure.security.jwt import create_token


@pytest.fixture
def token():
    return create_token(user_id="rate_test_user", role="user")


@pytest.fixture
def headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


@pytest.mark.asyncio
async def test_rate_limit_returns_429(headers):
    with patch(
        "app.api.middleware.rate_limit.RateLimitMiddleware._check_rate_limit",
        return_value=False,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
            response = await client.post(
                "/api/v1/execute",
                json={"user_id": "rate_test_user", "task": "Hello"},
                headers=headers,
            )

    assert response.status_code == 429
    data = response.json()
    assert data["error_code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_rate_limit_allows_within_limit(headers, fake_llm_provider):
    mock_store = AsyncMock()
    mock_store.get_messages = AsyncMock(return_value=[])
    mock_store.append_message = AsyncMock()
    mock_store.get_summary = AsyncMock(return_value=None)
    mock_store.append_tool_history = AsyncMock()
    mock_store.trim_messages = AsyncMock()

    with patch(
        "app.api.routes.execute.RedisMemoryStore", return_value=mock_store
    ), patch(
        "app.api.middleware.rate_limit.RateLimitMiddleware._check_rate_limit",
        return_value=True,
    ), patch(
        "app.application.services.model_router.create_llm_provider",
        return_value=fake_llm_provider,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
            response = await client.post(
                "/api/v1/execute",
                json={"user_id": "rate_test_user", "task": "Hello"},
                headers=headers,
            )

    assert response.status_code == 200
