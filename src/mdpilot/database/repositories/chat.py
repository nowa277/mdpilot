"""Chat repository with chat-specific queries."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mdpilot.database.models.chat import Chat
from mdpilot.database.repositories.base import BaseRepository


class ChatRepository(BaseRepository[Chat]):
    """Repository for Chat model with chat-specific queries.

    Provides CRUD operations and specialized queries for chat sessions.

    Args:
        session: The async database session to use for operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the chat repository.

        Args:
            session: The async database session.
        """
        super().__init__(session, Chat)

    async def search_by_title(self, query: str) -> list[Chat]:
        """Search chats by title using case-insensitive matching.

        Args:
            query: The search query string.

        Returns:
            List of chats matching the search query.
        """
        result = await self.session.execute(
            select(Chat)
            .where(Chat.title.ilike(f"%{query}%"))
            .order_by(desc(Chat.created_at))
        )
        return list(result.scalars().all())

    async def get_with_messages(self, chat_id: UUID) -> Chat | None:
        """Get a chat with all its messages eagerly loaded.

        Args:
            chat_id: The UUID of the chat to retrieve.

        Returns:
            The chat instance with messages loaded, or None if not found.
        """
        result = await self.session.execute(
            select(Chat)
            .where(Chat.id == chat_id)
            .options(selectinload(Chat.messages))
        )
        return result.scalar_one_or_none()

    async def get_recent(self, limit: int = 10) -> list[Chat]:
        """Get the most recent chats.

        Args:
            limit: Maximum number of chats to return (default: 10).

        Returns:
            List of recent chats ordered by creation date descending.
        """
        result = await self.session.execute(
            select(Chat)
            .order_by(desc(Chat.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())
