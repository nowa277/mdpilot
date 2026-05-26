"""Tests for database-backed ChatService."""

import uuid

import pytest
from sqlalchemy.exc import SQLAlchemyError

from mdpilot.api.services.chat_service import ChatService
from mdpilot.config.schema import DatabaseConfig
from mdpilot.database.base import Base
from mdpilot.database.engine import dispose_engine, get_engine, init_db
from mdpilot.database.session import get_session


@pytest.fixture
def sqlite_config():
    """Create an in-memory SQLite configuration for testing."""
    return DatabaseConfig(
        url="sqlite+aiosqlite:///:memory:",
        echo=False,
    )


@pytest.fixture
async def initialized_db(sqlite_config):
    """Initialize database and create tables."""
    init_db(sqlite_config)

    # Create tables
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    await dispose_engine()


@pytest.mark.asyncio
class TestChatService:
    """Tests for ChatService."""

    async def test_create_session(self, initialized_db):
        """Test creating a chat session."""
        async with get_session() as session:
            service = ChatService(session)
            chat_session = await service.create_session(
                user_id="user123",
                metadata={"source": "test"},
            )
            await session.commit()

            assert chat_session.session_id is not None
            assert chat_session.user_id == "user123"
            assert chat_session.status == "active"
            assert chat_session.metadata == {"source": "test"}
            assert chat_session.created_at is not None

    async def test_create_session_without_metadata(self, initialized_db):
        """Test creating a chat session without metadata."""
        async with get_session() as session:
            service = ChatService(session)
            chat_session = await service.create_session(user_id="user456")
            await session.commit()

            assert chat_session.session_id is not None
            assert chat_session.user_id == "user456"
            assert chat_session.metadata is None

    async def test_get_session(self, initialized_db):
        """Test retrieving a chat session."""
        async with get_session() as session:
            service = ChatService(session)

            # Create session
            created = await service.create_session(
                user_id="user123",
                metadata={"key": "value"},
            )
            await session.commit()

            # Retrieve session
            retrieved = await service.get_session(created.session_id)

            assert retrieved is not None
            assert retrieved.session_id == created.session_id
            assert retrieved.user_id == "user123"
            assert retrieved.status == "active"

    async def test_get_session_not_found(self, initialized_db):
        """Test retrieving a non-existent session."""
        async with get_session() as session:
            service = ChatService(session)
            result = await service.get_session(str(uuid.uuid4()))
            assert result is None

    async def test_get_session_invalid_uuid(self, initialized_db):
        """Test retrieving a session with invalid UUID."""
        async with get_session() as session:
            service = ChatService(session)
            result = await service.get_session("invalid-uuid")
            assert result is None

    async def test_add_message(self, initialized_db):
        """Test adding a message to a session."""
        async with get_session() as session:
            service = ChatService(session)

            # Create session
            chat_session = await service.create_session(user_id="user123")
            await session.commit()

            # Add message
            message = await service.add_message(
                session_id=chat_session.session_id,
                content="Hello, world!",
                role="user",
            )
            await session.commit()

            assert message is not None
            assert message.message_id is not None
            assert message.session_id == chat_session.session_id
            assert message.content == "Hello, world!"
            assert message.role == "user"
            assert message.created_at is not None

    async def test_add_message_to_nonexistent_session(self, initialized_db):
        """Test adding a message to a non-existent session."""
        async with get_session() as session:
            service = ChatService(session)

            message = await service.add_message(
                session_id=str(uuid.uuid4()),
                content="Hello",
                role="user",
            )

            assert message is None

    async def test_add_multiple_messages(self, initialized_db):
        """Test adding multiple messages to a session."""
        async with get_session() as session:
            service = ChatService(session)

            # Create session
            chat_session = await service.create_session(user_id="user123")
            await session.commit()

            # Add multiple messages
            msg1 = await service.add_message(
                session_id=chat_session.session_id,
                content="First message",
                role="user",
            )
            await session.commit()

            msg2 = await service.add_message(
                session_id=chat_session.session_id,
                content="Second message",
                role="assistant",
            )
            await session.commit()

            assert msg1 is not None
            assert msg2 is not None
            assert msg1.message_id != msg2.message_id

    async def test_get_messages(self, initialized_db):
        """Test retrieving messages for a session."""
        async with get_session() as session:
            service = ChatService(session)

            # Create session and add messages
            chat_session = await service.create_session(user_id="user123")
            await session.commit()

            for i in range(5):
                await service.add_message(
                    session_id=chat_session.session_id,
                    content=f"Message {i}",
                    role="user" if i % 2 == 0 else "assistant",
                )
            await session.commit()

            # Get messages
            result = await service.get_messages(chat_session.session_id)

            assert result is not None
            messages, total = result
            assert len(messages) == 5
            assert total == 5
            assert messages[0].content == "Message 0"
            assert messages[4].content == "Message 4"

    async def test_get_messages_with_pagination(self, initialized_db):
        """Test retrieving messages with pagination."""
        async with get_session() as session:
            service = ChatService(session)

            # Create session and add messages
            chat_session = await service.create_session(user_id="user123")
            await session.commit()

            for i in range(10):
                await service.add_message(
                    session_id=chat_session.session_id,
                    content=f"Message {i}",
                    role="user",
                )
            await session.commit()

            # Get first page
            result = await service.get_messages(
                chat_session.session_id,
                limit=5,
                offset=0,
            )

            assert result is not None
            messages, total = result
            assert len(messages) == 5
            assert total == 10
            assert messages[0].content == "Message 0"

            # Get second page
            result = await service.get_messages(
                chat_session.session_id,
                limit=5,
                offset=5,
            )

            assert result is not None
            messages, total = result
            assert len(messages) == 5
            assert total == 10
            assert messages[0].content == "Message 5"

    async def test_get_messages_for_nonexistent_session(self, initialized_db):
        """Test retrieving messages for a non-existent session."""
        async with get_session() as session:
            service = ChatService(session)
            result = await service.get_messages(str(uuid.uuid4()))
            assert result is None

    async def test_get_messages_empty_session(self, initialized_db):
        """Test retrieving messages from an empty session."""
        async with get_session() as session:
            service = ChatService(session)

            # Create session without messages
            chat_session = await service.create_session(user_id="user123")
            await session.commit()

            # Get messages
            result = await service.get_messages(chat_session.session_id)

            assert result is not None
            messages, total = result
            assert len(messages) == 0
            assert total == 0
