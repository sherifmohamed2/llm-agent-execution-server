from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.infrastructure.security.jwt import create_token


@pytest.fixture
def token():
    return create_token(user_id="test_user", role="user")


@pytest.fixture
def headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _mock_redis_store():
    """Create a mock RedisMemoryStore for tests that bypass real Redis."""
    mock = AsyncMock()
    mock.get_messages = AsyncMock(return_value=[])
    mock.append_message = AsyncMock()
    mock.get_summary = AsyncMock(return_value=None)
    mock.save_summary = AsyncMock()
    mock.append_tool_history = AsyncMock()
    mock.trim_messages = AsyncMock()
    mock.ping = AsyncMock(return_value=True)
    mock.close = AsyncMock()
    # Session owner methods 
    mock.set_session_owner_if_unset = AsyncMock(return_value=True)
    mock.get_session_owner = AsyncMock(return_value=None)
    return mock


@pytest.mark.asyncio
async def test_execute_math_task(headers, fake_llm_provider):
    mock_store = _mock_redis_store()

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
                json={"user_id": "test_user", "task": "Calculate 25 * 4"},
                headers=headers,
            )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["session_id"]
    assert data["response"]
    assert data["trace_id"]


@pytest.mark.asyncio
async def test_execute_search_task(headers, fake_llm_provider):
    mock_store = _mock_redis_store()

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
                json={"user_id": "test_user", "task": "Search for Python tutorials"},
                headers=headers,
            )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_execute_invalid_user_id(headers):
    with patch(
        "app.api.middleware.rate_limit.RateLimitMiddleware._check_rate_limit",
        return_value=True,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
            response = await client.post(
                "/api/v1/execute",
                json={"user_id": "", "task": "Hello"},
                headers=headers,
            )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_execute_missing_task(headers):
    with patch(
        "app.api.middleware.rate_limit.RateLimitMiddleware._check_rate_limit",
        return_value=True,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
            response = await client.post(
                "/api/v1/execute",
                json={"user_id": "test_user"},
                headers=headers,
            )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_execute_extra_fields_rejected(headers):
    with patch(
        "app.api.middleware.rate_limit.RateLimitMiddleware._check_rate_limit",
        return_value=True,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
            response = await client.post(
                "/api/v1/execute",
                json={"user_id": "test_user", "task": "Hello", "extra": "field"},
                headers=headers,
            )

    assert response.status_code == 422
