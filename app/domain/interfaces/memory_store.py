from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class MemoryStoreInterface(ABC):
    @abstractmethod
    async def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def append_message(self, session_id: str, message: dict[str, Any]) -> None:
        ...

    @abstractmethod
    async def get_summary(self, session_id: str) -> str | None:
        ...

    @abstractmethod
    async def save_summary(self, session_id: str, summary: str) -> None:
        ...

    @abstractmethod
    async def append_tool_history(
        self, session_id: str, tool_record: dict[str, Any]
    ) -> None:
        ...

    @abstractmethod
    async def trim_messages(self, session_id: str, keep_last: int) -> None:
        ...

    @abstractmethod
    async def get_session_owner(self, session_id: str) -> str | None:
        """Return the user_id that owns this session, or None if unset."""
        ...

    @abstractmethod
    async def set_session_owner_if_unset(self, session_id: str, user_id: str) -> bool:
        """
        Atomically set the session owner only if it has not been set yet (SET NX).
        Returns True if the value was written (first use), False if it already existed.
        """
        ...
