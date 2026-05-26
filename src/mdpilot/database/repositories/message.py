"""Message repository with message-specific queries."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdpilot.database.models.message import Message
from mdpilot.database.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    """Repository for Message model with message-specific queries.

    Provides CRUD operations and specialized queries for messages.

    Args:
        session: The async database session to use for operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the message repository.

        Args:
            session: The async database session.
        """
        super().__init__(session, Message)

    async def get_by_chat_id(
        self, chat_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[Message]:
        """Get messages for a specific chat with pagination.

        Args:
            chat_id: The UUID of the chat.
            skip: Number of messages to skip (default: 0).
            limit: Maximum number of messages to return (default: 100).

        Returns:
            List of messages ordered by creation date.
        """
        result = await self.session.execute(
            select(Message)
            .where(Message.chat_id == chat_id)
            .order_by(Message.created_at)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_by_chat_id(self, chat_id: UUID) -> int:
        """Count messages for a specific chat.

        Args:
            chat_id: The UUID of the chat.

        Returns:
            The total count of messages in the chat.
        """
        result = await self.session.execute(
            select(func.count())
            .select_from(Message)
            .where(Message.chat_id == chat_id)
        )
        return result.scalar_one()

    async def delete_by_chat_id(self, chat_id: UUID) -> int:
        """Delete all messages for a specific chat.

        Args:
            chat_id: The UUID of the chat.

        Returns:
            The number of messages deleted.

        Note:
            The caller must commit the session for changes to persist.
        """
        result = await self.session.execute(
            delete(Message).where(Message.chat_id == chat_id)
        )
        return result.rowcount
