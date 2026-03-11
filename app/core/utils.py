from __future__ import annotations
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.constants import Limits


def generate_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:16]}"


def generate_session_id() -> str:
    return f"sess_{uuid.uuid4().hex[:20]}"


def generate_trace_id() -> str:
    return f"trace_{uuid.uuid4().hex[:16]}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def safe_json_dumps(data: Any) -> str:
    return json.dumps(data, default=str, ensure_ascii=False)


def safe_json_loads(raw: str | bytes) -> Any:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 chars per token for English text."""
    return max(1, len(text) // 4)


def validate_user_id(user_id: str) -> str:
    user_id = user_id.strip()
    if not user_id:
        raise ValueError("user_id must not be empty")
    if len(user_id) > Limits.MAX_USER_ID_LENGTH:
        raise ValueError(f"user_id exceeds max length of {Limits.MAX_USER_ID_LENGTH}")
    if not re.match(r"^[a-zA-Z0-9_\-]+$", user_id):
        raise ValueError("user_id contains invalid characters")
    return user_id


def sanitize_task(task: str) -> str:
    task = task.strip()
    if not task:
        raise ValueError("task must not be empty")
    if len(task) > Limits.MAX_TASK_LENGTH:
        task = task[: Limits.MAX_TASK_LENGTH]
    return task
