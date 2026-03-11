from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, patch, call
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.infrastructure.security.jwt import create_token


@pytest.fixture
def token():
    return create_token(user_id="memory_test_user", role="user")


@pytest.fixture
def headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _mock_redis_store_with_state():
    """Mock store that accumulates messages to simulate persistence."""
    stored_messages: list[dict] = []
    mock = AsyncMock()

    async def get_messages(session_id):
        return list(stored_messages)

    async def append_message(session_id, message):
        stored_messages.append(message)

    mock.get_messages = AsyncMock(side_effect=get_messages)
    mock.append_message = AsyncMock(side_effect=append_message)
    mock.get_summary = AsyncMock(return_value=None)
    mock.save_summary = AsyncMock()
    mock.append_tool_history = AsyncMock()
    mock.trim_messages = AsyncMock()
    mock.ping = AsyncMock(return_value=True)
    mock.close = AsyncMock()
    # Session owner (first-use: claim succeeds)
    mock.set_session_owner_if_unset = AsyncMock(return_value=True)
    mock.get_session_owner = AsyncMock(return_value=None)
    mock._stored = stored_messages
    return mock


@pytest.mark.asyncio
async def test_session_persists_messages(headers, fake_llm_provider):
    mock_store = _mock_redis_store_with_state()

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
            r1 = await client.post(
                "/api/v1/execute",
                json={
                    "user_id": "memory_test_user",
                    "task": "Hello, remember my name is Alice",
                    "session_id": "test_session_1",
                },
                headers=headers,
            )
            assert r1.status_code == 200
            data1 = r1.json()
            assert data1["session_id"] == "test_session_1"

            r2 = await client.post(
                "/api/v1/execute",
                json={
                    "user_id": "memory_test_user",
                    "task": "What was my name?",
                    "session_id": "test_session_1",
                },
                headers=headers,
            )
            assert r2.status_code == 200
            data2 = r2.json()
            assert data2["session_id"] == "test_session_1"

    assert mock_store.append_message.call_count >= 4

    stored = mock_store._stored
    roles = [m.get("role") for m in stored]
    assert "user" in roles
    assert "assistant" in roles


@pytest.mark.asyncio
async def test_different_sessions_are_independent(headers, fake_llm_provider):
    mock_store1 = _mock_redis_store_with_state()
    mock_store2 = _mock_redis_store_with_state()
    call_count = 0

    def factory_side_effect():
        nonlocal call_count
        call_count += 1
        return mock_store1 if call_count <= 1 else mock_store2

    with patch(
        "app.api.routes.execute.RedisMemoryStore", side_effect=lambda: factory_side_effect()
    ), patch(
        "app.api.middleware.rate_limit.RateLimitMiddleware._check_rate_limit",
        return_value=True,
    ), patch(
        "app.application.services.model_router.create_llm_provider",
        return_value=fake_llm_provider,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
            r1 = await client.post(
                "/api/v1/execute",
                json={
                    "user_id": "memory_test_user",
                    "task": "Session A message",
                    "session_id": "session_a",
                },
                headers=headers,
            )
            assert r1.status_code == 200

            r2 = await client.post(
                "/api/v1/execute",
                json={
                    "user_id": "memory_test_user",
                    "task": "Session B message",
                    "session_id": "session_b",
                },
                headers=headers,
            )
            assert r2.status_code == 200
