"""Database-backed chat service."""
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from mdpilot.api.models.chat import ChatSession, Message
from mdpilot.database.repositories.chat import ChatRepository
from mdpilot.database.repositories.message import MessageRepository

logger = logging.getLogger(__name__)


class ChatService:
    """Database-backed chat service for managing sessions and messages."""

    def __init__(self, session: AsyncSession):
        """Initialize the chat service.

        Args:
            session: The async database session to use for operations.
        """
        self.session = session
        self.chat_repo = ChatRepository(session)
        self.message_repo = MessageRepository(session)

    async def create_session(
        self, user_id: str, metadata: Optional[dict] = None
    ) -> ChatSession:
        """Create a new chat session.

        Args:
            user_id: The user ID creating the session.
            metadata: Optional metadata for the session.

        Returns:
            The created chat session.

        Raises:
            SQLAlchemyError: If database operation fails.
        """
        try:
            # Store user_id in extra_data since Chat model doesn't have user_id field
            extra_data = metadata.copy() if metadata else {}
            extra_data["user_id"] = user_id

            # Create chat with title from user_id (can be customized later)
            chat_data = {
                "title": f"Chat for {user_id}",
                "extra_data": extra_data,
            }
            chat = await self.chat_repo.create(chat_data)

            # Map DB model to API model
            return ChatSession(
                session_id=str(chat.id),
                user_id=user_id,
                status="active",
                created_at=chat.created_at,
                metadata=metadata,  # Return original metadata without user_id
            )
        except SQLAlchemyError as e:
            logger.error(f"Failed to create chat session: {e}")
            raise

    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get a chat session by ID.

        Args:
            session_id: The session ID to retrieve.

        Returns:
            The chat session if found, None otherwise.

        Raises:
            SQLAlchemyError: If database operation fails.
        """
        try:
            chat = await self.chat_repo.get_by_id(UUID(session_id))
            if chat is None:
                return None

            # Map DB model to API model
            # Extract user_id from extra_data or use a default
            user_id = (
                chat.extra_data.get("user_id", "unknown")
                if chat.extra_data
                else "unknown"
            )

            return ChatSession(
                session_id=str(chat.id),
                user_id=user_id,
                status="active",
                created_at=chat.created_at,
                metadata=chat.extra_data,
            )
        except (ValueError, SQLAlchemyError) as e:
            logger.error(f"Failed to get chat session {session_id}: {e}")
            return None

    async def add_message(
        self, session_id: str, content: str, role: str,
        extra_data: dict | None = None,
    ) -> Optional[Message]:
        """Add a message to a session.

        Args:
            session_id: The session ID to add the message to.
            content: The message content.
            role: The message role (user, assistant, system).
            extra_data: Optional JSON data to persist with the message.

        Returns:
            The created message if successful, None if session not found.

        Raises:
            SQLAlchemyError: If database operation fails.
        """
        try:
            # Verify session exists
            chat = await self.chat_repo.get_by_id(UUID(session_id))
            if chat is None:
                return None

            # Create message
            message_data = {
                "chat_id": chat.id,
                "content": content,
                "role": role,
            }
            if extra_data is not None:
                message_data["extra_data"] = extra_data
            message = await self.message_repo.create(message_data)

            # Map DB model to API model
            return Message(
                message_id=str(message.id),
                session_id=str(message.chat_id),
                content=message.content,
                role=message.role,
                created_at=message.created_at,
            )
        except (ValueError, IntegrityError) as e:
            logger.error(f"Failed to add message to session {session_id}: {e}")
            return None
        except SQLAlchemyError as e:
            logger.error(f"Database error adding message: {e}")
            raise

    async def get_messages(
        self, session_id: str, limit: int = 100, offset: int = 0
    ) -> Optional[tuple[list[Message], int]]:
        """Get messages for a session with pagination.

        Args:
            session_id: The session ID to get messages for.
            limit: Maximum number of messages to return.
            offset: Number of messages to skip.

        Returns:
            Tuple of (messages list, total count) if session exists, None otherwise.

        Raises:
            SQLAlchemyError: If database operation fails.
        """
        try:
            # Verify session exists
            chat = await self.chat_repo.get_by_id(UUID(session_id))
            if chat is None:
                return None

            # Get messages with pagination
            messages = await self.message_repo.get_by_chat_id(
                chat.id, skip=offset, limit=limit
            )
            total = await self.message_repo.count_by_chat_id(chat.id)

            # Map DB models to API models
            api_messages = [
                Message(
                    message_id=str(msg.id),
                    session_id=str(msg.chat_id),
                    content=msg.content,
                    role=msg.role,
                    created_at=msg.created_at,
                )
                for msg in messages
            ]

            return api_messages, total
        except (ValueError, SQLAlchemyError) as e:
            logger.error(f"Failed to get messages for session {session_id}: {e}")
            return None
