"""Tests for repository pattern implementation."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from mdpilot.config.schema import DatabaseConfig
from mdpilot.database.base import Base
from mdpilot.database.engine import dispose_engine, get_engine, init_db
from mdpilot.database.models import Chat, Message, Task
from mdpilot.database.repositories import (
    ChatRepository,
    MessageRepository,
    TaskRepository,
)
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
class TestChatRepository:
    """Tests for ChatRepository."""

    async def test_create_chat(self, initialized_db):
        """Test creating a chat through repository."""
        async with get_session() as session:
            repo = ChatRepository(session)
            chat = await repo.create({"title": "Test Chat"})
            await session.commit()

            assert chat.id is not None
            assert isinstance(chat.id, uuid.UUID)
            assert chat.title == "Test Chat"
            assert chat.extra_data is None

    async def test_create_chat_with_extra_data(self, initialized_db):
        """Test creating a chat with extra_data."""
        async with get_session() as session:
            repo = ChatRepository(session)
            extra_data = {"user_id": "user123", "tags": ["important"]}
            chat = await repo.create({
                "title": "Chat with Metadata",
                "extra_data": extra_data,
            })
            await session.commit()

            assert chat.extra_data == extra_data

    async def test_get_by_id(self, initialized_db):
        """Test retrieving a chat by ID."""
        async with get_session() as session:
            repo = ChatRepository(session)
            chat = await repo.create({"title": "Test Chat"})
            await session.commit()

            retrieved = await repo.get_by_id(chat.id)
            assert retrieved is not None
            assert retrieved.id == chat.id
            assert retrieved.title == "Test Chat"

    async def test_get_by_id_not_found(self, initialized_db):
        """Test retrieving a non-existent chat."""
        async with get_session() as session:
            repo = ChatRepository(session)
            result = await repo.get_by_id(uuid.uuid4())
            assert result is None

    async def test_get_all(self, initialized_db):
        """Test retrieving all chats with pagination."""
        async with get_session() as session:
            repo = ChatRepository(session)

            # Create multiple chats
            for i in range(5):
                await repo.create({"title": f"Chat {i}"})
            await session.commit()

            # Get all chats
            chats = await repo.get_all(skip=0, limit=10)
            assert len(chats) == 5

    async def test_get_all_pagination(self, initialized_db):
        """Test pagination in get_all."""
        async with get_session() as session:
            repo = ChatRepository(session)

            # Create multiple chats
            for i in range(10):
                await repo.create({"title": f"Chat {i}"})
            await session.commit()

            # Test pagination
            page1 = await repo.get_all(skip=0, limit=5)
            page2 = await repo.get_all(skip=5, limit=5)

            assert len(page1) == 5
            assert len(page2) == 5
            assert page1[0].id != page2[0].id

    async def test_update(self, initialized_db):
        """Test updating a chat."""
        async with get_session() as session:
            repo = ChatRepository(session)
            chat = await repo.create({"title": "Original Title"})
            await session.commit()

            updated = await repo.update(chat.id, {"title": "Updated Title"})
            await session.commit()

            assert updated is not None
            assert updated.title == "Updated Title"

    async def test_update_not_found(self, initialized_db):
        """Test updating a non-existent chat."""
        async with get_session() as session:
            repo = ChatRepository(session)
            result = await repo.update(uuid.uuid4(), {"title": "New Title"})
            assert result is None

    async def test_delete(self, initialized_db):
        """Test deleting a chat."""
        async with get_session() as session:
            repo = ChatRepository(session)
            chat = await repo.create({"title": "To Delete"})
            await session.commit()

            deleted = await repo.delete(chat.id)
            await session.commit()

            assert deleted is True

            # Verify it's gone
            result = await repo.get_by_id(chat.id)
            assert result is None

    async def test_delete_not_found(self, initialized_db):
        """Test deleting a non-existent chat."""
        async with get_session() as session:
            repo = ChatRepository(session)
            result = await repo.delete(uuid.uuid4())
            assert result is False

    async def test_count(self, initialized_db):
        """Test counting chats."""
        async with get_session() as session:
            repo = ChatRepository(session)

            # Initially empty
            count = await repo.count()
            assert count == 0

            # Create some chats
            for i in range(3):
                await repo.create({"title": f"Chat {i}"})
            await session.commit()

            count = await repo.count()
            assert count == 3

    async def test_search_by_title(self, initialized_db):
        """Test searching chats by title."""
        async with get_session() as session:
            repo = ChatRepository(session)

            await repo.create({"title": "Python Programming"})
            await repo.create({"title": "Java Development"})
            await repo.create({"title": "Python Data Science"})
            await session.commit()

            results = await repo.search_by_title("Python")
            assert len(results) == 2
            assert all("Python" in chat.title for chat in results)

    async def test_search_by_title_case_insensitive(self, initialized_db):
        """Test case-insensitive title search."""
        async with get_session() as session:
            repo = ChatRepository(session)

            await repo.create({"title": "Python Programming"})
            await session.commit()

            results = await repo.search_by_title("python")
            assert len(results) == 1

    async def test_search_by_title_no_results(self, initialized_db):
        """Test search with no matching results."""
        async with get_session() as session:
            repo = ChatRepository(session)

            await repo.create({"title": "Python Programming"})
            await session.commit()

            results = await repo.search_by_title("Ruby")
            assert len(results) == 0

    async def test_get_with_messages(self, initialized_db):
        """Test retrieving a chat with messages eagerly loaded."""
        async with get_session() as session:
            chat_repo = ChatRepository(session)
            msg_repo = MessageRepository(session)

            # Create chat with messages
            chat = await chat_repo.create({"title": "Chat with Messages"})
            await msg_repo.create({
                "chat_id": chat.id,
                "role": "user",
                "content": "Hello",
            })
            await msg_repo.create({
                "chat_id": chat.id,
                "role": "assistant",
                "content": "Hi there!",
            })
            await session.commit()

            # Get chat with messages
            result = await chat_repo.get_with_messages(chat.id)
            assert result is not None
            assert len(result.messages) == 2
            assert result.messages[0].content == "Hello"
            assert result.messages[1].content == "Hi there!"

    async def test_get_with_messages_not_found(self, initialized_db):
        """Test get_with_messages for non-existent chat."""
        async with get_session() as session:
            repo = ChatRepository(session)
            result = await repo.get_with_messages(uuid.uuid4())
            assert result is None

    async def test_get_recent(self, initialized_db):
        """Test retrieving recent chats."""
        async with get_session() as session:
            repo = ChatRepository(session)

            # Create chats
            for i in range(5):
                await repo.create({"title": f"Chat {i}"})
            await session.commit()

            recent = await repo.get_recent(limit=3)
            assert len(recent) == 3
            # Should be ordered by created_at descending
            assert recent[0].created_at >= recent[1].created_at
            assert recent[1].created_at >= recent[2].created_at


@pytest.mark.asyncio
class TestMessageRepository:
    """Tests for MessageRepository."""

    async def test_create_message(self, initialized_db):
        """Test creating a message through repository."""
        async with get_session() as session:
            chat_repo = ChatRepository(session)
            msg_repo = MessageRepository(session)

            chat = await chat_repo.create({"title": "Test Chat"})
            message = await msg_repo.create({
                "chat_id": chat.id,
                "role": "user",
                "content": "Hello, world!",
            })
            await session.commit()

            assert message.id is not None
            assert message.chat_id == chat.id
            assert message.role == "user"
            assert message.content == "Hello, world!"

    async def test_get_by_id(self, initialized_db):
        """Test retrieving a message by ID."""
        async with get_session() as session:
            chat_repo = ChatRepository(session)
            msg_repo = MessageRepository(session)

            chat = await chat_repo.create({"title": "Test Chat"})
            message = await msg_repo.create({
                "chat_id": chat.id,
                "role": "user",
                "content": "Test message",
            })
            await session.commit()

            retrieved = await msg_repo.get_by_id(message.id)
            assert retrieved is not None
            assert retrieved.id == message.id
            assert retrieved.content == "Test message"

    async def test_get_by_chat_id(self, initialized_db):
        """Test retrieving messages for a specific chat."""
        async with get_session() as session:
            chat_repo = ChatRepository(session)
            msg_repo = MessageRepository(session)

            chat1 = await chat_repo.create({"title": "Chat 1"})
            chat2 = await chat_repo.create({"title": "Chat 2"})

            # Create messages for chat1
            await msg_repo.create({
                "chat_id": chat1.id,
                "role": "user",
                "content": "Message 1",
            })
            await msg_repo.create({
                "chat_id": chat1.id,
                "role": "assistant",
                "content": "Message 2",
            })

            # Create message for chat2
            await msg_repo.create({
                "chat_id": chat2.id,
                "role": "user",
                "content": "Message 3",
            })
            await session.commit()

            messages = await msg_repo.get_by_chat_id(chat1.id)
            assert len(messages) == 2
            assert all(msg.chat_id == chat1.id for msg in messages)

    async def test_get_by_chat_id_pagination(self, initialized_db):
        """Test pagination in get_by_chat_id."""
        async with get_session() as session:
            chat_repo = ChatRepository(session)
            msg_repo = MessageRepository(session)

            chat = await chat_repo.create({"title": "Test Chat"})

            # Create multiple messages
            for i in range(10):
                await msg_repo.create({
                    "chat_id": chat.id,
                    "role": "user",
                    "content": f"Message {i}",
                })
            await session.commit()

            page1 = await msg_repo.get_by_chat_id(chat.id, skip=0, limit=5)
            page2 = await msg_repo.get_by_chat_id(chat.id, skip=5, limit=5)

            assert len(page1) == 5
            assert len(page2) == 5

    async def test_get_by_chat_id_ordered(self, initialized_db):
        """Test that messages are ordered by created_at."""
        async with get_session() as session:
            chat_repo = ChatRepository(session)
            msg_repo = MessageRepository(session)

            chat = await chat_repo.create({"title": "Test Chat"})

            msg1 = await msg_repo.create({
                "chat_id": chat.id,
                "role": "user",
                "content": "First",
            })
            msg2 = await msg_repo.create({
                "chat_id": chat.id,
                "role": "assistant",
                "content": "Second",
            })
            await session.commit()

            messages = await msg_repo.get_by_chat_id(chat.id)
            assert messages[0].id == msg1.id
            assert messages[1].id == msg2.id

    async def test_count_by_chat_id(self, initialized_db):
        """Test counting messages for a specific chat."""
        async with get_session() as session:
            chat_repo = ChatRepository(session)
            msg_repo = MessageRepository(session)

            chat = await chat_repo.create({"title": "Test Chat"})

            # Initially no messages
            count = await msg_repo.count_by_chat_id(chat.id)
            assert count == 0

            # Create messages
            for i in range(3):
                await msg_repo.create({
                    "chat_id": chat.id,
                    "role": "user",
                    "content": f"Message {i}",
                })
            await session.commit()

            count = await msg_repo.count_by_chat_id(chat.id)
            assert count == 3

    async def test_delete_by_chat_id(self, initialized_db):
        """Test deleting all messages for a specific chat."""
        async with get_session() as session:
            chat_repo = ChatRepository(session)
            msg_repo = MessageRepository(session)

            chat = await chat_repo.create({"title": "Test Chat"})

            # Create messages
            for i in range(3):
                await msg_repo.create({
                    "chat_id": chat.id,
                    "role": "user",
                    "content": f"Message {i}",
                })
            await session.commit()

            # Delete all messages
            deleted_count = await msg_repo.delete_by_chat_id(chat.id)
            await session.commit()

            assert deleted_count == 3

            # Verify they're gone
            messages = await msg_repo.get_by_chat_id(chat.id)
            assert len(messages) == 0

    async def test_delete_by_chat_id_no_messages(self, initialized_db):
        """Test delete_by_chat_id when chat has no messages."""
        async with get_session() as session:
            chat_repo = ChatRepository(session)
            msg_repo = MessageRepository(session)

            chat = await chat_repo.create({"title": "Empty Chat"})
            await session.commit()

            deleted_count = await msg_repo.delete_by_chat_id(chat.id)
            assert deleted_count == 0

    async def test_cascade_delete(self, initialized_db):
        """Test that messages are deleted when chat is deleted."""
        async with get_session() as session:
            chat_repo = ChatRepository(session)
            msg_repo = MessageRepository(session)

            chat = await chat_repo.create({"title": "Test Chat"})
            message = await msg_repo.create({
                "chat_id": chat.id,
                "role": "user",
                "content": "Test message",
            })
            await session.commit()

            # Delete the chat
            await chat_repo.delete(chat.id)
            await session.commit()

            # Message should be gone
            result = await msg_repo.get_by_id(message.id)
            assert result is None


@pytest.mark.asyncio
class TestTaskRepository:
    """Tests for TaskRepository."""

    async def test_create_task(self, initialized_db):
        """Test creating a task through repository."""
        async with get_session() as session:
            repo = TaskRepository(session)
            task = await repo.create({
                "task_type": "test_task",
                "parameters": {"key": "value"},
                "user_id": "user123",
                "status": "pending",
            })
            await session.commit()

            assert task.id is not None
            assert task.task_type == "test_task"
            assert task.parameters == {"key": "value"}
            assert task.user_id == "user123"
            assert task.status == "pending"

    async def test_create_task_with_chat(self, initialized_db):
        """Test creating a task associated with a chat."""
        async with get_session() as session:
            chat_repo = ChatRepository(session)
            task_repo = TaskRepository(session)

            chat = await chat_repo.create({"title": "Test Chat"})
            task = await task_repo.create({
                "task_type": "test_task",
                "parameters": {"key": "value"},
                "user_id": "user123",
                "chat_id": chat.id,
            })
            await session.commit()

            assert task.chat_id == chat.id

    async def test_get_by_status(self, initialized_db):
        """Test retrieving tasks by status."""
        async with get_session() as session:
            repo = TaskRepository(session)

            await repo.create({
                "task_type": "task1",
                "parameters": {},
                "user_id": "user123",
                "status": "pending",
            })
            await repo.create({
                "task_type": "task2",
                "parameters": {},
                "user_id": "user123",
                "status": "running",
            })
            await repo.create({
                "task_type": "task3",
                "parameters": {},
                "user_id": "user123",
                "status": "pending",
            })
            await session.commit()

            pending_tasks = await repo.get_by_status("pending")
            assert len(pending_tasks) == 2
            assert all(task.status == "pending" for task in pending_tasks)

    async def test_get_by_status_ordered(self, initialized_db):
        """Test that tasks are ordered by created_at descending."""
        async with get_session() as session:
            repo = TaskRepository(session)

            task1 = await repo.create({
                "task_type": "task1",
                "parameters": {},
                "user_id": "user123",
                "status": "pending",
            })
            task2 = await repo.create({
                "task_type": "task2",
                "parameters": {},
                "user_id": "user123",
                "status": "pending",
            })
            await session.commit()

            tasks = await repo.get_by_status("pending")
            # Most recent first
            assert tasks[0].id == task2.id
            assert tasks[1].id == task1.id

    async def test_get_by_chat_id(self, initialized_db):
        """Test retrieving tasks by chat ID."""
        async with get_session() as session:
            chat_repo = ChatRepository(session)
            task_repo = TaskRepository(session)

            chat1 = await chat_repo.create({"title": "Chat 1"})
            chat2 = await chat_repo.create({"title": "Chat 2"})

            await task_repo.create({
                "task_type": "task1",
                "parameters": {},
                "user_id": "user123",
                "chat_id": chat1.id,
            })
            await task_repo.create({
                "task_type": "task2",
                "parameters": {},
                "user_id": "user123",
                "chat_id": chat1.id,
            })
            await task_repo.create({
                "task_type": "task3",
                "parameters": {},
                "user_id": "user123",
                "chat_id": chat2.id,
            })
            await session.commit()

            tasks = await task_repo.get_by_chat_id(chat1.id)
            assert len(tasks) == 2
            assert all(task.chat_id == chat1.id for task in tasks)

    async def test_update_status(self, initialized_db):
        """Test updating task status."""
        async with get_session() as session:
            repo = TaskRepository(session)

            task = await repo.create({
                "task_type": "test_task",
                "parameters": {},
                "user_id": "user123",
                "status": "pending",
            })
            await session.commit()

            updated = await repo.update_status(task.id, "running")
            await session.commit()

            assert updated is not None
            assert updated.status == "running"

    async def test_update_status_not_found(self, initialized_db):
        """Test updating status of non-existent task."""
        async with get_session() as session:
            repo = TaskRepository(session)
            result = await repo.update_status(uuid.uuid4(), "running")
            assert result is None

    async def test_get_by_user_id(self, initialized_db):
        """Test retrieving tasks by user ID."""
        async with get_session() as session:
            repo = TaskRepository(session)

            await repo.create({
                "task_type": "task1",
                "parameters": {},
                "user_id": "user123",
            })
            await repo.create({
                "task_type": "task2",
                "parameters": {},
                "user_id": "user456",
            })
            await repo.create({
                "task_type": "task3",
                "parameters": {},
                "user_id": "user123",
            })
            await session.commit()

            tasks = await repo.get_by_user_id("user123")
            assert len(tasks) == 2
            assert all(task.user_id == "user123" for task in tasks)

    async def test_get_by_user_id_pagination(self, initialized_db):
        """Test pagination in get_by_user_id."""
        async with get_session() as session:
            repo = TaskRepository(session)

            # Create multiple tasks
            for i in range(10):
                await repo.create({
                    "task_type": f"task{i}",
                    "parameters": {},
                    "user_id": "user123",
                })
            await session.commit()

            page1 = await repo.get_by_user_id("user123", skip=0, limit=5)
            page2 = await repo.get_by_user_id("user123", skip=5, limit=5)

            assert len(page1) == 5
            assert len(page2) == 5

    async def test_task_without_chat(self, initialized_db):
        """Test creating a task without a chat association."""
        async with get_session() as session:
            repo = TaskRepository(session)

            task = await repo.create({
                "task_type": "standalone_task",
                "parameters": {},
                "user_id": "user123",
            })
            await session.commit()

            assert task.chat_id is None

    async def test_transaction_rollback(self, initialized_db):
        """Test that changes are rolled back on error."""
        async with get_session() as session:
            repo = TaskRepository(session)

            task = await repo.create({
                "task_type": "test_task",
                "parameters": {},
                "user_id": "user123",
            })
            # Don't commit

        # In a new session, task should not exist
        async with get_session() as session:
            repo = TaskRepository(session)
            result = await repo.get_by_id(task.id)
            assert result is None
