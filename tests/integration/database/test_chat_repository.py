"""Integration tests for ChatRepository with real database operations."""

import uuid
from datetime import datetime

import pytest

from mdpilot.config.schema import DatabaseConfig
from mdpilot.database.base import Base
from mdpilot.database.engine import dispose_engine, get_engine, init_db
from mdpilot.database.repositories import ChatRepository, MessageRepository
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
class TestChatRepositoryIntegration:
    """Integration tests for ChatRepository."""

    async def test_full_chat_lifecycle(self, initialized_db):
        """Test complete chat lifecycle: create, read, update, delete."""
        async with get_session() as session:
            repo = ChatRepository(session)

            # Create
            chat = await repo.create({"title": "Integration Test Chat"})
            await session.commit()
            chat_id = chat.id

            # Read
            retrieved = await repo.get_by_id(chat_id)
            assert retrieved is not None
            assert retrieved.title == "Integration Test Chat"

            # Update
            updated = await repo.update(chat_id, {"title": "Updated Chat"})
            await session.commit()
            assert updated.title == "Updated Chat"

            # Delete
            deleted = await repo.delete(chat_id)
            await session.commit()
            assert deleted is True

            # Verify deletion
            result = await repo.get_by_id(chat_id)
            assert result is None

    async def test_chat_with_messages_integration(self, initialized_db):
        """Test chat with messages relationship."""
        async with get_session() as session:
            chat_repo = ChatRepository(session)
            msg_repo = MessageRepository(session)

            # Create chat
            chat = await chat_repo.create({"title": "Chat with Messages"})
            await session.commit()

            # Add messages
            for i in range(5):
                await msg_repo.create({
                    "chat_id": chat.id,
                    "role": "user" if i % 2 == 0 else "assistant",
                    "content": f"Message {i}",
                })
            await session.commit()

            # Retrieve with messages
            chat_with_msgs = await chat_repo.get_with_messages(chat.id)
            assert chat_with_msgs is not None
            assert len(chat_with_msgs.messages) == 5

            # Verify order
            for i, msg in enumerate(chat_with_msgs.messages):
                assert msg.content == f"Message {i}"

    async def test_concurrent_chat_operations(self, initialized_db):
        """Test concurrent chat operations."""
        async with get_session() as session1:
            async with get_session() as session2:
                repo1 = ChatRepository(session1)
                repo2 = ChatRepository(session2)

                # Create in session1
                chat = await repo1.create({"title": "Concurrent Test"})
                await session1.commit()

                # Read in session2
                retrieved = await repo2.get_by_id(chat.id)
                assert retrieved is not None
                assert retrieved.title == "Concurrent Test"

    async def test_search_performance(self, initialized_db):
        """Test search performance with multiple chats."""
        async with get_session() as session:
            repo = ChatRepository(session)

            # Create multiple chats
            for i in range(20):
                await repo.create({
                    "title": f"Python Chat {i}" if i % 2 == 0 else f"Java Chat {i}"
                })
            await session.commit()

            # Search
            python_chats = await repo.search_by_title("Python")
            assert len(python_chats) == 10

            java_chats = await repo.search_by_title("Java")
            assert len(java_chats) == 10

    async def test_pagination_consistency(self, initialized_db):
        """Test pagination returns consistent results."""
        async with get_session() as session:
            repo = ChatRepository(session)

            # Create chats
            created_ids = []
            for i in range(15):
                chat = await repo.create({"title": f"Chat {i:02d}"})
                created_ids.append(chat.id)
            await session.commit()

            # Paginate
            page1 = await repo.get_all(skip=0, limit=5)
            page2 = await repo.get_all(skip=5, limit=5)
            page3 = await repo.get_all(skip=10, limit=5)

            assert len(page1) == 5
            assert len(page2) == 5
            assert len(page3) == 5

            # Verify no duplicates
            all_ids = [c.id for c in page1 + page2 + page3]
            assert len(all_ids) == len(set(all_ids))

    async def test_cascade_delete_integration(self, initialized_db):
        """Test cascade delete removes messages."""
        async with get_session() as session:
            chat_repo = ChatRepository(session)
            msg_repo = MessageRepository(session)

            # Create chat with messages
            chat = await chat_repo.create({"title": "To Delete"})
            await session.commit()

            message_ids = []
            for i in range(3):
                msg = await msg_repo.create({
                    "chat_id": chat.id,
                    "role": "user",
                    "content": f"Message {i}",
                })
                message_ids.append(msg.id)
            await session.commit()

            # Delete chat
            await chat_repo.delete(chat.id)
            await session.commit()

            # Verify messages are gone
            for msg_id in message_ids:
                result = await msg_repo.get_by_id(msg_id)
                assert result is None

    async def test_transaction_rollback_integration(self, initialized_db):
        """Test transaction rollback behavior."""
        async with get_session() as session:
            repo = ChatRepository(session)

            # Create chat but don't commit
            chat = await repo.create({"title": "Rollback Test"})
            chat_id = chat.id
            # Session ends without commit

        # Verify chat doesn't exist
        async with get_session() as session:
            repo = ChatRepository(session)
            result = await repo.get_by_id(chat_id)
            assert result is None

    async def test_get_recent_chats(self, initialized_db):
        """Test retrieving recent chats."""
        async with get_session() as session:
            repo = ChatRepository(session)

            # Create chats
            for i in range(10):
                await repo.create({"title": f"Chat {i}"})
            await session.commit()

            # Get recent
            recent = await repo.get_recent(limit=5)
            assert len(recent) == 5

            # Verify ordering (most recent first)
            for i in range(len(recent) - 1):
                assert recent[i].created_at >= recent[i + 1].created_at

    async def test_count_accuracy(self, initialized_db):
        """Test count returns accurate results."""
        async with get_session() as session:
            repo = ChatRepository(session)

            # Initially empty
            assert await repo.count() == 0

            # Add chats
            for i in range(7):
                await repo.create({"title": f"Chat {i}"})
            await session.commit()

            assert await repo.count() == 7

            # Delete some
            chats = await repo.get_all(skip=0, limit=3)
            for chat in chats:
                await repo.delete(chat.id)
            await session.commit()

            assert await repo.count() == 4
