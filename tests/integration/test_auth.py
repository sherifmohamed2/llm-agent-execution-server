from __future__ import annotations
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_no_auth_returns_401():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        response = await client.post(
            "/api/v1/execute",
            json={"user_id": "test_user", "task": "Hello"},
        )
    assert response.status_code == 401
    data = response.json()
    assert data["error_code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_invalid_token_returns_401():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        response = await client.post(
            "/api/v1/execute",
            json={"user_id": "test_user", "task": "Hello"},
            headers={"Authorization": "Bearer invalid.token.here"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_missing_bearer_prefix_returns_401():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        response = await client.post(
            "/api/v1/execute",
            json={"user_id": "test_user", "task": "Hello"},
            headers={"Authorization": "some-token"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_health_does_not_require_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        response = await client.get("/api/v1/health")
    # May be 200 or 500 if Redis unavailable, but should not be 401
    assert response.status_code != 401
