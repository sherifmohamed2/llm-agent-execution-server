from __future__ import annotations
from app.core.exceptions import ForbiddenError
from app.domain.enums.user_role import UserRole


def require_role(user_role: str, allowed_roles: list[UserRole]) -> None:
    if user_role not in [r.value for r in allowed_roles]:
        raise ForbiddenError(f"Role '{user_role}' is not authorized for this action")


def is_admin(user_role: str) -> bool:
    return user_role == UserRole.ADMIN.value


def is_internal(user_role: str) -> bool:
    return user_role == UserRole.INTERNAL.value


def can_execute(user_role: str) -> bool:
    return user_role in {
        UserRole.USER.value,
        UserRole.ADMIN.value,
        UserRole.INTERNAL.value,
    }
