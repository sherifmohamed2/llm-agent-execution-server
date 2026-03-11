from __future__ import annotations
from typing import Any

from app.core.constants import Limits
from app.core.exceptions import ForbiddenError
from app.domain.interfaces.memory_store import MemoryStoreInterface
from app.domain.models.session import Message
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class MemoryService:
    def __init__(self, store: MemoryStoreInterface) -> None:
        self._store = store

    async def load_messages(self, session_id: str) -> list[Message]:
        raw = await self._store.get_messages(session_id)
        messages = []
        for item in raw:
            messages.append(
                Message(
                    role=item.get("role", "user"),
                    content=item.get("content", ""),
                    name=item.get("name"),
                    tool_call_id=item.get("tool_call_id"),
                    metadata=item.get("metadata", {}),
                )
            )
        return messages

    async def append_user_message(self, session_id: str, content: str) -> None:
        await self._store.append_message(
            session_id, {"role": "user", "content": content}
        )

    async def append_assistant_message(self, session_id: str, content: str) -> None:
        await self._store.append_message(
            session_id, {"role": "assistant", "content": content}
        )

    async def append_assistant_tool_calls(
        self, session_id: str, tool_calls: list[dict[str, Any]]
    ) -> None:
        """
        Persist an assistant message that declares tool calls (OpenAI-style).
        This is required so that subsequent `tool` messages are valid for providers
        that enforce tool-call message ordering.
        """
        await self._store.append_message(
            session_id,
            {
                "role": "assistant",
                "content": "",
                "metadata": {"tool_calls": tool_calls},
            },
        )

    async def append_tool_message(
        self, session_id: str, content: str, tool_call_id: str | None = None, name: str | None = None
    ) -> None:
        msg: dict[str, Any] = {"role": "tool", "content": content}
        if tool_call_id:
            msg["tool_call_id"] = tool_call_id
        if name:
            msg["name"] = name
        await self._store.append_message(session_id, msg)

    async def get_summary(self, session_id: str) -> str | None:
        return await self._store.get_summary(session_id)

    async def save_summary(self, session_id: str, summary: str) -> None:
        await self._store.save_summary(session_id, summary)

    async def trim_if_needed(self, session_id: str) -> None:
        messages = await self._store.get_messages(session_id)
        if len(messages) > Limits.MAX_MESSAGES_PER_SESSION:
            await self._store.trim_messages(
                session_id, Limits.MAX_MESSAGES_PER_SESSION
            )
            logger.info("memory_trimmed", session_id=session_id)

    async def get_message_count(self, session_id: str) -> int:
        messages = await self._store.get_messages(session_id)
        return len(messages)

    async def verify_or_bind_session_owner(self, session_id: str, user_id: str) -> None:
        """
        On first use of a session, atomically bind the authenticated user as the
        owner.  On every subsequent use, verify the caller is still that owner.
        Raises ForbiddenError if the session belongs to a different user.
        """
        was_set = await self._store.set_session_owner_if_unset(session_id, user_id)
        if not was_set:
            existing_owner = await self._store.get_session_owner(session_id)
            if existing_owner != user_id:
                logger.warning(
                    "session_owner_mismatch",
                    session_id=session_id,
                    expected_owner=existing_owner,
                    requesting_user=user_id,
                )
                raise ForbiddenError("Session belongs to a different user")

    async def record_tool_call(
        self, session_id: str, tool_record: dict[str, Any]
    ) -> None:
        await self._store.append_tool_history(session_id, tool_record)
