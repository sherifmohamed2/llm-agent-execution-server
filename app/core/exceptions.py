from __future__ import annotations
from typing import Any


class AppException(Exception):
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred"

    def __init__(self, message: str | None = None, details: Any = None):
        self.message = message or self.__class__.message
        self.details = details
        super().__init__(self.message)


class BadRequestError(AppException):
    status_code = 400
    error_code = "BAD_REQUEST"
    message = "Invalid request"


class UnauthorizedError(AppException):
    status_code = 401
    error_code = "UNAUTHORIZED"
    message = "Authentication required"


class ForbiddenError(AppException):
    status_code = 403
    error_code = "FORBIDDEN"
    message = "Access denied"


class RateLimitError(AppException):
    status_code = 429
    error_code = "RATE_LIMITED"
    message = "Rate limit exceeded"


class MemoryStoreError(AppException):
    status_code = 503
    error_code = "MEMORY_STORE_UNAVAILABLE"
    message = "Memory store is unavailable (Redis connection failed)"


class ToolNotFoundError(AppException):
    status_code = 404
    error_code = "TOOL_NOT_FOUND"
    message = "Requested tool not found"


class ToolValidationError(AppException):
    status_code = 422
    error_code = "TOOL_VALIDATION_ERROR"
    message = "Tool input validation failed"


class ToolExecutionError(AppException):
    status_code = 500
    error_code = "TOOL_EXECUTION_ERROR"
    message = "Tool execution failed"


class LLMProviderError(AppException):
    status_code = 502
    error_code = "LLM_PROVIDER_ERROR"
    message = "LLM provider request failed"


class InternalServerError(AppException):
    status_code = 500
    error_code = "INTERNAL_ERROR"
    message = "Internal server error"
