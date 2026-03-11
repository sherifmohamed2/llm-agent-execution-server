from __future__ import annotations
from enum import Enum


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
    INTERNAL = "internal"
