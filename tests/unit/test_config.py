"""
Unit tests for Settings startup validation.

Ensures the JWT secret strength check works correctly:
- production rejects default / short secrets
- development / testing allow placeholder secrets
"""
from __future__ import annotations
import pytest
from pydantic import ValidationError


def _make_settings(**kwargs):
    """Create a fresh Settings instance with explicit overrides (no .env read)."""
    from app.core.config import Settings

    # Prevent the .env file from influencing test-time Settings instances.
    return Settings.model_validate(
        {
            "app_name": "test-app",
            "environment": "production",
            "jwt_secret": "a" * 32,  # valid default, overridden per test
            **kwargs,
        }
    )


class TestJwtSecretValidation:
    def test_production_rejects_default_placeholder(self):
        with pytest.raises(ValidationError, match="default placeholder"):
            _make_settings(environment="production", jwt_secret="change-me-in-production")

    def test_production_rejects_empty_secret(self):
        with pytest.raises(ValidationError):
            _make_settings(environment="production", jwt_secret="")

    def test_production_rejects_short_secret(self):
        with pytest.raises(ValidationError, match="at least 32 bytes"):
            _make_settings(environment="production", jwt_secret="tooshort")

    def test_production_rejects_known_weak_values(self):
        for weak in ("secret", "password", "changeme", "test"):
            with pytest.raises(ValidationError):
                _make_settings(environment="production", jwt_secret=weak)

    def test_production_accepts_strong_secret(self):
        strong = "a1b2c3d4e5f6" * 4  # 48 chars > 32 bytes
        s = _make_settings(environment="production", jwt_secret=strong)
        assert s.jwt_secret == strong

    def test_development_allows_default_placeholder(self):
        s = _make_settings(environment="development", jwt_secret="change-me-in-production")
        assert s.jwt_secret == "change-me-in-production"

    def test_dev_alias_allows_default_placeholder(self):
        s = _make_settings(environment="dev", jwt_secret="change-me-in-production")
        assert s.jwt_secret == "change-me-in-production"

    def test_testing_allows_default_placeholder(self):
        s = _make_settings(environment="testing", jwt_secret="change-me-in-production")
        assert s.jwt_secret == "change-me-in-production"

    def test_test_alias_allows_default_placeholder(self):
        s = _make_settings(environment="test", jwt_secret="change-me-in-production")
        assert s.jwt_secret == "change-me-in-production"

    def test_production_exactly_32_bytes_is_accepted(self):
        secret_32 = "x" * 32
        s = _make_settings(environment="production", jwt_secret=secret_32)
        assert len(s.jwt_secret) == 32
