from __future__ import annotations
from pydantic import BaseModel
from typing import Any


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    details: Any = None
    trace_id: str | None = None
    timestamp: str | None = None
