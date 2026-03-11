from __future__ import annotations
import pytest

from app.core.utils import (
    estimate_tokens,
    generate_request_id,
    generate_session_id,
    generate_trace_id,
    sanitize_task,
    validate_user_id,
)


def test_generate_request_id():
    rid = generate_request_id()
    assert rid.startswith("req_")
    assert len(rid) > 4


def test_generate_session_id():
    sid = generate_session_id()
    assert sid.startswith("sess_")


def test_generate_trace_id():
    tid = generate_trace_id()
    assert tid.startswith("trace_")


def test_validate_user_id_valid():
    assert validate_user_id("user_123") == "user_123"


def test_validate_user_id_empty():
    with pytest.raises(ValueError):
        validate_user_id("")


def test_validate_user_id_invalid_chars():
    with pytest.raises(ValueError):
        validate_user_id("user@123!")


def test_sanitize_task_valid():
    assert sanitize_task("Calculate 2+2") == "Calculate 2+2"


def test_sanitize_task_empty():
    with pytest.raises(ValueError):
        sanitize_task("")


def test_sanitize_task_strips():
    assert sanitize_task("  hello  ") == "hello"


def test_estimate_tokens():
    tokens = estimate_tokens("Hello, this is a test message")
    assert tokens > 0
    assert isinstance(tokens, int)
