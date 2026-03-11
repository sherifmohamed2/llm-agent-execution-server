from __future__ import annotations
class APIConstants:
    V1_PREFIX = "/api/v1"
    EXECUTE_PATH = "/execute"
    HEALTH_PATH = "/health"


class HeaderConstants:
    REQUEST_ID = "X-Request-ID"
    TRACE_ID = "X-Trace-ID"
    AUTHORIZATION = "Authorization"
    BEARER_PREFIX = "Bearer "


class RedisKeys:
    SESSION_MESSAGES = "session:{session_id}:messages"
    SESSION_SUMMARY = "session:{session_id}:summary"
    SESSION_TOOL_HISTORY = "session:{session_id}:tool_history"
    SESSION_OWNER = "session:{session_id}:owner"
    RATE_LIMIT = "rate_limit:{user_id}:{window}"

    @classmethod
    def messages(cls, session_id: str) -> str:
        return cls.SESSION_MESSAGES.format(session_id=session_id)

    @classmethod
    def summary(cls, session_id: str) -> str:
        return cls.SESSION_SUMMARY.format(session_id=session_id)

    @classmethod
    def tool_history(cls, session_id: str) -> str:
        return cls.SESSION_TOOL_HISTORY.format(session_id=session_id)

    @classmethod
    def session_owner(cls, session_id: str) -> str:
        return cls.SESSION_OWNER.format(session_id=session_id)

    @classmethod
    def rate_limit(cls, user_id: str, window: str) -> str:
        return cls.RATE_LIMIT.format(user_id=user_id, window=window)


class Limits:
    MAX_TASK_LENGTH = 4096
    MAX_USER_ID_LENGTH = 128
    MAX_MESSAGES_PER_SESSION = 50
    MAX_TOOL_CALLS_PER_TURN = 5
    CONTEXT_WINDOW_TOKENS = 8192
    SUMMARY_TRIGGER_TOKENS = 6000


class Defaults:
    SESSION_TTL_SECONDS = 3600
    TOOL_TIMEOUT_SECONDS = 15
    MAX_SEARCH_RESULTS = 5


class LogEvents:
    REQUEST_STARTED = "request_started"
    REQUEST_COMPLETED = "request_completed"
    TOOL_CALLED = "tool_called"
    TOOL_SUCCEEDED = "tool_succeeded"
    TOOL_FAILED = "tool_failed"
    LLM_CALLED = "llm_called"
    LLM_RESPONDED = "llm_responded"
    MEMORY_LOADED = "memory_loaded"
    MEMORY_SAVED = "memory_saved"
    AUTH_FAILED = "auth_failed"
    RATE_LIMITED = "rate_limited"
