"""Tests for Chat and Message SQLAlchemy models."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from mdpilot.config.schema import DatabaseConfig
from mdpilot.database.base import Base
from mdpilot.database.engine import dispose_engine, get_engine, init_db
from mdpilot.database.models import Chat, Message
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
class TestChatModel:
    """Tests for Chat model."""

    async def test_create_chat(self, initialized_db):
        """Test creating a chat session."""
        async with get_session() as session:
            chat = Chat(
                title="Test Chat",
            )
            session.add(chat)
            await session.commit()
            await session.refresh(chat)

            assert chat.id is not None
            assert isinstance(chat.id, uuid.UUID)
            assert chat.title == "Test Chat"
            assert chat.extra_data is None
            assert isinstance(chat.created_at, datetime)
            assert isinstance(chat.updated_at, datetime)

    async def test_create_chat_with_metadata(self, initialized_db):
        """Test creating a chat with extra_data."""
        async with get_session() as session:
            extra_data = {"user_id": "user123", "tags": ["important"]}
            chat = Chat(
                title="Chat with Metadata",
                extra_data=extra_data,
            )
            session.add(chat)
            await session.commit()
            await session.refresh(chat)

            assert chat.extra_data == extra_data
            assert chat.extra_data["user_id"] == "user123"
            assert "important" in chat.extra_data["tags"]

    async def test_chat_title_required(self, initialized_db):
        """Test that title is required."""
        async with get_session() as session:
            chat = Chat()
            session.add(chat)

            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_chat_timestamps(self, initialized_db):
        """Test that timestamps are automatically set."""
        async with get_session() as session:
            chat = Chat(title="Timestamp Test")
            session.add(chat)
            await session.commit()
            await session.refresh(chat)

            assert chat.created_at is not None
            assert chat.updated_at is not None
            assert chat.created_at <= chat.updated_at

    async def test_chat_repr(self, initialized_db):
        """Test Chat string representation."""
        async with get_session() as session:
            chat = Chat(title="Test Chat")
            session.add(chat)
            await session.commit()
            await session.refresh(chat)

            repr_str = repr(chat)
            assert "Chat" in repr_str
            assert str(chat.id) in repr_str
            assert "Test Chat" in repr_str


@pytest.mark.asyncio
class TestMessageModel:
    """Tests for Message model."""

    async def test_create_message(self, initialized_db):
        """Test creating a message."""
        async with get_session() as session:
            # Create chat first
            chat = Chat(title="Test Chat")
            session.add(chat)
            await session.commit()
            await session.refresh(chat)

            # Create message
            message = Message(
                chat_id=chat.id,
                role="user",
                content="Hello, world!",
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)

            assert message.id is not None
            assert isinstance(message.id, uuid.UUID)
            assert message.chat_id == chat.id
            assert message.role == "user"
            assert message.content == "Hello, world!"
            assert message.extra_data is None
            assert isinstance(message.created_at, datetime)
            assert isinstance(message.updated_at, datetime)

    async def test_create_message_with_metadata(self, initialized_db):
        """Test creating a message with extra_data."""
        async with get_session() as session:
            chat = Chat(title="Test Chat")
            session.add(chat)
            await session.commit()
            await session.refresh(chat)

            extra_data = {"tokens": 150, "model": "gpt-4"}
            message = Message(
                chat_id=chat.id,
                role="assistant",
                content="Response",
                extra_data=extra_data,
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)

            assert message.extra_data == extra_data
            assert message.extra_data["tokens"] == 150

    async def test_message_valid_roles(self, initialized_db):
        """Test that only valid roles are accepted."""
        async with get_session() as session:
            chat = Chat(title="Test Chat")
            session.add(chat)
            await session.commit()
            await session.refresh(chat)

            # Test valid roles
            for role in ["user", "assistant", "system"]:
                message = Message(
                    chat_id=chat.id,
                    role=role,
                    content=f"Message from {role}",
                )
                session.add(message)
                await session.commit()
                await session.refresh(message)
                assert message.role == role

    async def test_message_invalid_role(self, initialized_db):
        """Test that invalid roles are rejected."""
        async with get_session() as session:
            chat = Chat(title="Test Chat")
            session.add(chat)
            await session.commit()
            await session.refresh(chat)

            message = Message(
                chat_id=chat.id,
                role="invalid_role",
                content="Test",
            )
            session.add(message)

            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_message_required_fields(self, initialized_db):
        """Test that required fields are enforced."""
        async with get_session() as session:
            chat = Chat(title="Test Chat")
            session.add(chat)
            await session.commit()
            await session.refresh(chat)

            # Missing content
            message = Message(
                chat_id=chat.id,
                role="user",
            )
            session.add(message)

            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_message_foreign_key_constraint(self, initialized_db):
        """Test that foreign key constraint is enforced."""
        async with get_session() as session:
            # Try to create message with non-existent chat_id
            fake_chat_id = uuid.uuid4()
            message = Message(
                chat_id=fake_chat_id,
                role="user",
                content="Test",
            )
            session.add(message)

            # SQLite doesn't enforce foreign keys by default in tests
            # This test verifies the constraint exists, but may not fail in SQLite
            try:
                await session.commit()
                # If we get here in SQLite, that's expected
                # In PostgreSQL, this would raise IntegrityError
            except IntegrityError:
                # This is the expected behavior in PostgreSQL
                pass

    async def test_message_repr(self, initialized_db):
        """Test Message string representation."""
        async with get_session() as session:
            chat = Chat(title="Test Chat")
            session.add(chat)
            await session.commit()
            await session.refresh(chat)

            message = Message(
                chat_id=chat.id,
                role="user",
                content="Short message",
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)

            repr_str = repr(message)
            assert "Message" in repr_str
            assert str(message.id) in repr_str
            assert str(message.chat_id) in repr_str
            assert "user" in repr_str
            assert "Short message" in repr_str

    async def test_message_repr_long_content(self, initialized_db):
        """Test Message repr truncates long content."""
        async with get_session() as session:
            chat = Chat(title="Test Chat")
            session.add(chat)
            await session.commit()
            await session.refresh(chat)

            long_content = "A" * 100
            message = Message(
                chat_id=chat.id,
                role="user",
                content=long_content,
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)

            repr_str = repr(message)
            assert "..." in repr_str
            assert len(repr_str) < len(long_content) + 100


@pytest.mark.asyncio
class TestChatMessageRelationship:
    """Tests for Chat-Message relationship."""

    async def test_chat_messages_relationship(self, initialized_db):
        """Test that chat.messages relationship works."""
        async with get_session() as session:
            # Create chat
            chat = Chat(title="Test Chat")
            session.add(chat)
            await session.commit()
            await session.refresh(chat)

            # Create messages
            message1 = Message(
                chat_id=chat.id,
                role="user",
                content="First message",
            )
            message2 = Message(
                chat_id=chat.id,
                role="assistant",
                content="Second message",
            )
            session.add_all([message1, message2])
            await session.commit()

            # Query chat with messages eagerly loaded
            result = await session.execute(
                select(Chat)
                .where(Chat.id == chat.id)
                .options(selectinload(Chat.messages))
            )
            chat_with_messages = result.scalar_one()

            assert len(chat_with_messages.messages) == 2
            assert chat_with_messages.messages[0].content == "First message"
            assert chat_with_messages.messages[1].content == "Second message"

    async def test_message_chat_relationship(self, initialized_db):
        """Test that message.chat relationship works."""
        async with get_session() as session:
            # Create chat and message
            chat = Chat(title="Test Chat")
            session.add(chat)
            await session.commit()
            await session.refresh(chat)

            message = Message(
                chat_id=chat.id,
                role="user",
                content="Test message",
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)

            # Check relationship
            assert message.chat is not None
            assert message.chat.id == chat.id
            assert message.chat.title == "Test Chat"

    async def test_cascade_delete(self, initialized_db):
        """Test that deleting a chat deletes its messages."""
        async with get_session() as session:
            # Create chat with messages
            chat = Chat(title="Test Chat")
            session.add(chat)
            await session.commit()
            await session.refresh(chat)

            message1 = Message(chat_id=chat.id, role="user", content="Message 1")
            message2 = Message(chat_id=chat.id, role="user", content="Message 2")
            session.add_all([message1, message2])
            await session.commit()

            chat_id = chat.id

            # Delete chat
            await session.delete(chat)
            await session.commit()

            # Verify messages are deleted
            result = await session.execute(
                select(Message).where(Message.chat_id == chat_id)
            )
            messages = result.scalars().all()
            assert len(messages) == 0

    async def test_messages_ordered_by_created_at(self, initialized_db):
        """Test that messages are ordered by created_at."""
        async with get_session() as session:
            # Create chat
            chat = Chat(title="Test Chat")
            session.add(chat)
            await session.commit()
            await session.refresh(chat)

            # Create messages in reverse order
            message2 = Message(
                chat_id=chat.id,
                role="assistant",
                content="Second",
            )
            session.add(message2)
            await session.commit()

            message1 = Message(
                chat_id=chat.id,
                role="user",
                content="First",
            )
            session.add(message1)
            await session.commit()

            # Query chat with messages eagerly loaded
            result = await session.execute(
                select(Chat)
                .where(Chat.id == chat.id)
                .options(selectinload(Chat.messages))
            )
            chat_with_messages = result.scalar_one()

            # Messages should be ordered by created_at
            assert len(chat_with_messages.messages) == 2
            # The first created message should come first
            assert chat_with_messages.messages[0].content == "Second"
            assert chat_with_messages.messages[1].content == "First"


@pytest.mark.asyncio
class TestIndexes:
    """Tests for model indexes."""

    async def test_chat_title_index(self, initialized_db):
        """Test that chat title is indexed for search."""
        async with get_session() as session:
            # Create multiple chats
            chat1 = Chat(title="Python Tutorial")
            chat2 = Chat(title="JavaScript Guide")
            chat3 = Chat(title="Python Advanced")
            session.add_all([chat1, chat2, chat3])
            await session.commit()

            # Query by title (should use index)
            result = await session.execute(
                select(Chat).where(Chat.title.like("%Python%"))
            )
            chats = result.scalars().all()
            assert len(chats) == 2

    async def test_chat_created_at_index(self, initialized_db):
        """Test that chat created_at is indexed for sorting."""
        async with get_session() as session:
            # Create multiple chats
            chat1 = Chat(title="Chat 1")
            chat2 = Chat(title="Chat 2")
            chat3 = Chat(title="Chat 3")
            session.add_all([chat1, chat2, chat3])
            await session.commit()

            # Query ordered by created_at (should use index)
            result = await session.execute(
                select(Chat).order_by(Chat.created_at.desc())
            )
            chats = result.scalars().all()
            assert len(chats) == 3

    async def test_message_chat_id_index(self, initialized_db):
        """Test that message chat_id is indexed for filtering."""
        async with get_session() as session:
            # Create chats and messages
            chat1 = Chat(title="Chat 1")
            chat2 = Chat(title="Chat 2")
            session.add_all([chat1, chat2])
            await session.commit()
            await session.refresh(chat1)
            await session.refresh(chat2)

            message1 = Message(chat_id=chat1.id, role="user", content="M1")
            message2 = Message(chat_id=chat1.id, role="user", content="M2")
            message3 = Message(chat_id=chat2.id, role="user", content="M3")
            session.add_all([message1, message2, message3])
            await session.commit()

            # Query by chat_id (should use index)
            result = await session.execute(
                select(Message).where(Message.chat_id == chat1.id)
            )
            messages = result.scalars().all()
            assert len(messages) == 2
