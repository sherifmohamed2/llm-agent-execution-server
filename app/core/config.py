from __future__ import annotations
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

# Environments where lax JWT secret rules apply (local dev / CI).
_DEV_ENVS = frozenset({"development", "dev", "testing", "test"})

# Well-known placeholder values that must never reach production.
_WEAK_JWT_SECRETS = frozenset({
    "change-me-in-production",
    "secret",
    "password",
    "jwt-secret",
    "changeme",
    "test",
    "",
})

# Minimum secret length (bytes) enforced outside dev/test.
_MIN_JWT_SECRET_BYTES = 32


class Settings(BaseSettings):
    app_name: str = Field(default="agent-execution-engine")
    app_version: str = Field(default="1.0.0")
    environment: str = Field(default="development")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    # Optional: also write structured logs to a file
    log_file_path: str = Field(default="logs/app.log")

    redis_url: str = Field(default="redis://localhost:6379/0")

    openai_api_key: str = Field(default="")
    anthropic_api_key: str = Field(default="")
    gemini_api_key: str = Field(default="")
    default_llm_provider: str = Field(default="openai")
    openai_model_name: str = Field(default="gpt-4o-mini")
    anthropic_model_name: str = Field(default="claude-3-5-sonnet-20241022")
    gemini_model_name: str = Field(default="gemini-1.5-flash")

    jwt_secret: str = Field(default="change-me-in-production")
    jwt_algorithm: str = Field(default="HS256")

    rate_limit_per_minute: int = Field(default=30)
    tool_timeout_seconds: int = Field(default=15)
    request_timeout_seconds: int = Field(default=30)

    celery_broker_url: str = Field(default="redis://localhost:6379/1")
    celery_result_backend: str = Field(default="redis://localhost:6379/2")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def _validate_jwt_secret_strength(self) -> "Settings":
        """Refuse to start in non-dev/test environments with a weak JWT secret."""
        if self.environment.lower() in _DEV_ENVS:
            return self

        secret = self.jwt_secret
        if not secret or secret.lower() in _WEAK_JWT_SECRETS:
            raise ValueError(
                "JWT_SECRET is set to a default placeholder value. "
                "Set JWT_SECRET to a strong, unique random string before deploying. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        if len(secret.encode("utf-8")) < _MIN_JWT_SECRET_BYTES:
            raise ValueError(
                f"JWT_SECRET must be at least {_MIN_JWT_SECRET_BYTES} bytes in "
                f"non-development environments (current: {len(secret.encode())} bytes). "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return self


settings = Settings()
