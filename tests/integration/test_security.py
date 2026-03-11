"""
Security regression tests.

Covers:
- body.user_id mismatch with JWT sub  => 403
- Session owner mismatch (IDOR)        => 403
- Legitimate owner re-access           => 200
- Auth error response does not expose internal token details
"""
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.infrastructure.security.jwt import create_token


def _mock_redis_store(*, owner: str | None = None, set_owner_returns: bool = True):
    """
    Build a minimal mock store for security tests.

    owner              – value returned by get_session_owner (simulates an existing owner)
    set_owner_returns  – True  → SET NX succeeded (first use, no prior owner)
                         False → SET NX failed (key already existed, check get_session_owner)
    """
    mock = AsyncMock()
    mock.get_messages = AsyncMock(return_value=[])
    mock.append_message = AsyncMock()
    mock.get_summary = AsyncMock(return_value=None)
    mock.save_summary = AsyncMock()
    mock.append_tool_history = AsyncMock()
    mock.trim_messages = AsyncMock()
    mock.ping = AsyncMock(return_value=True)
    mock.close = AsyncMock()
    mock.set_session_owner_if_unset = AsyncMock(return_value=set_owner_returns)
    mock.get_session_owner = AsyncMock(return_value=owner)
    return mock


# ---------------------------------------------------------------------------
# 1. body.user_id != JWT sub  →  403
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_body_user_id_mismatch_jwt_sub_returns_403():
    """Providing a body user_id that differs from the JWT subject must return 403."""
    token = create_token(user_id="alice", role="user")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    with patch(
        "app.api.middleware.rate_limit.RateLimitMiddleware._check_rate_limit",
        return_value=True,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
            response = await client.post(
                "/api/v1/execute",
                json={"user_id": "bob", "task": "Hello"},  # bob ≠ alice (JWT)
                headers=headers,
            )

    assert response.status_code == 403
    data = response.json()
    assert data["error_code"] == "FORBIDDEN"


# ---------------------------------------------------------------------------
# 2. Session owner mismatch (IDOR)  →  403
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_session_owner_mismatch_returns_403(fake_llm_provider):
    """A session owned by alice cannot be accessed by bob."""
    bob_token = create_token(user_id="bob", role="user")
    bob_headers = {"Authorization": f"Bearer {bob_token}", "Content-Type": "application/json"}

    # The session is already owned by alice; SET NX returns False
    mock_store = _mock_redis_store(owner="alice", set_owner_returns=False)

    with patch("app.api.routes.execute.RedisMemoryStore", return_value=mock_store), patch(
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
                json={"task": "Hello", "session_id": "alice-owned-session"},
                headers=bob_headers,
            )

    assert response.status_code == 403
    data = response.json()
    assert data["error_code"] == "FORBIDDEN"


# ---------------------------------------------------------------------------
# 3. Legitimate owner re-access  →  200
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_session_owner_access_returns_200(fake_llm_provider):
    """The session owner can access their own session on subsequent requests."""
    alice_token = create_token(user_id="alice", role="user")
    alice_headers = {
        "Authorization": f"Bearer {alice_token}",
        "Content-Type": "application/json",
    }

    # SET NX returned False (session existed), but the owner IS alice
    mock_store = _mock_redis_store(owner="alice", set_owner_returns=False)

    with patch("app.api.routes.execute.RedisMemoryStore", return_value=mock_store), patch(
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
                json={"task": "What was my earlier task?", "session_id": "alice-session"},
                headers=alice_headers,
            )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"


# ---------------------------------------------------------------------------
# 4. No body.user_id needed  →  JWT sub is used automatically
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_request_without_body_user_id_uses_jwt_sub(fake_llm_provider):
    """Omitting body.user_id is now valid; the JWT subject is used as the identity."""
    token = create_token(user_id="charlie", role="user")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    mock_store = _mock_redis_store()

    with patch("app.api.routes.execute.RedisMemoryStore", return_value=mock_store), patch(
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
                json={"task": "Hello without user_id in body"},
                headers=headers,
            )

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# 5. Auth error response hygiene
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auth_failure_response_is_generic():
    """
    A bad JWT must return a short, generic 401 message.
    No stack traces, no JWT library internals, no token parsing details.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        response = await client.post(
            "/api/v1/execute",
            json={"task": "Hello"},
            headers={
                "Authorization": (
                    "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
                    ".eyJzdWIiOiJ4In0"
                    ".bad_signature_here"
                )
            },
        )

    assert response.status_code == 401
    data = response.json()
    assert data["error_code"] == "UNAUTHORIZED"
    msg = data["message"]
    # Must be a short, opaque message — no internal details
    assert len(msg) < 100
    assert "Traceback" not in msg
    assert "Exception" not in msg
    assert "decode" not in msg.lower()
    assert "signature" not in msg.lower()
