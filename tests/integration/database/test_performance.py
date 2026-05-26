"""Performance benchmarks for database operations."""

import uuid

import pytest

from mdpilot.config.schema import DatabaseConfig
from mdpilot.database.base import Base
from mdpilot.database.engine import dispose_engine, get_engine, init_db
from mdpilot.database.repositories import ChatRepository, MessageRepository, TaskRepository
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
class TestDatabasePerformance:
    """Performance benchmarks for database operations."""

    async def test_chat_creation_performance(self, initialized_db, benchmark):
        """Benchmark chat creation."""
        async def create_chat():
            async with get_session() as session:
                repo = ChatRepository(session)
                chat = await repo.create({"title": "Benchmark Chat"})
                await session.commit()
                return chat

        result = await benchmark(create_chat)
        assert result is not None

    async def test_message_creation_performance(self, initialized_db, benchmark):
        """Benchmark message creation."""
        # Setup: Create a chat
        async with get_session() as session:
            repo = ChatRepository(session)
            chat = await repo.create({"title": "Test Chat"})
            await session.commit()
            chat_id = chat.id

        async def create_message():
            async with get_session() as session:
                repo = MessageRepository(session)
                message = await repo.create({
                    "chat_id": chat_id,
                    "role": "user",
                    "content": "Benchmark message"
                })
                await session.commit()
                return message

        result = await benchmark(create_message)
        assert result is not None

    async def test_task_creation_performance(self, initialized_db, benchmark):
        """Benchmark task creation."""
        async def create_task():
            async with get_session() as session:
                repo = TaskRepository(session)
                task = await repo.create({
                    "task_type": "benchmark_task",
                    "parameters": {"key": "value"},
                    "user_id": "benchmark_user"
                })
                await session.commit()
                return task

        result = await benchmark(create_task)
        assert result is not None

    async def test_query_by_id_performance(self, initialized_db, benchmark):
        """Benchmark query by ID."""
        # Setup: Create a chat
        async with get_session() as session:
            repo = ChatRepository(session)
            chat = await repo.create({"title": "Test Chat"})
            await session.commit()
            chat_id = chat.id

        async def query_by_id():
            async with get_session() as session:
                repo = ChatRepository(session)
                return await repo.get_by_id(chat_id)

        result = await benchmark(query_by_id)
        assert result is not None

    async def test_pagination_performance(self, initialized_db, benchmark):
        """Benchmark pagination query."""
        # Setup: Create multiple chats
        async with get_session() as session:
            repo = ChatRepository(session)
            for i in range(100):
                await repo.create({"title": f"Chat {i}"})
            await session.commit()

        async def paginate():
            async with get_session() as session:
                repo = ChatRepository(session)
                return await repo.get_all(skip=0, limit=20)

        result = await benchmark(paginate)
        assert len(result) == 20

    async def test_search_performance(self, initialized_db, benchmark):
        """Benchmark search query."""
        # Setup: Create multiple chats
        async with get_session() as session:
            repo = ChatRepository(session)
            for i in range(50):
                await repo.create({"title": f"Python Chat {i}" if i % 2 == 0 else f"Java Chat {i}"})
            await session.commit()

        async def search():
            async with get_session() as session:
                repo = ChatRepository(session)
                return await repo.search_by_title("Python")

        result = await benchmark(search)
        assert len(result) == 25

    async def test_filter_by_status_performance(self, initialized_db, benchmark):
        """Benchmark filter by status query."""
        # Setup: Create multiple tasks
        async with get_session() as session:
            repo = TaskRepository(session)
            for i in range(100):
                await repo.create({
                    "task_type": f"task_{i}",
                    "parameters": {},
                    "user_id": "test_user",
                    "status": "pending" if i % 2 == 0 else "running"
                })
            await session.commit()

        async def filter_by_status():
            async with get_session() as session:
                repo = TaskRepository(session)
                return await repo.get_by_status("pending")

        result = await benchmark(filter_by_status)
        assert len(result) == 50

    async def test_eager_loading_performance(self, initialized_db, benchmark):
        """Benchmark eager loading of relationships."""
        # Setup: Create chat with messages
        async with get_session() as session:
            chat_repo = ChatRepository(session)
            msg_repo = MessageRepository(session)

            chat = await chat_repo.create({"title": "Chat with Messages"})
            await session.commit()

            for i in range(20):
                await msg_repo.create({
                    "chat_id": chat.id,
                    "role": "user",
                    "content": f"Message {i}"
                })
            await session.commit()
            chat_id = chat.id

        async def eager_load():
            async with get_session() as session:
                repo = ChatRepository(session)
                return await repo.get_with_messages(chat_id)

        result = await benchmark(eager_load)
        assert len(result.messages) == 20

    async def test_bulk_insert_performance(self, initialized_db, benchmark):
        """Benchmark bulk insert operations."""
        async def bulk_insert():
            async with get_session() as session:
                repo = ChatRepository(session)
                for i in range(50):
                    await repo.create({"title": f"Bulk Chat {i}"})
                await session.commit()

        await benchmark(bulk_insert)

    async def test_transaction_commit_performance(self, initialized_db, benchmark):
        """Benchmark transaction commit."""
        async def commit_transaction():
            async with get_session() as session:
                repo = ChatRepository(session)
                chat = await repo.create({"title": "Transaction Test"})
                await session.commit()
                return chat

        result = await benchmark(commit_transaction)
        assert result is not None


@pytest.mark.asyncio
class TestConnectionPoolPerformance:
    """Performance benchmarks for connection pooling."""

    async def test_concurrent_connections(self, initialized_db, benchmark):
        """Benchmark concurrent database connections."""
        import asyncio

        async def concurrent_queries():
            tasks = []
            for i in range(10):
                async def query():
                    async with get_session() as session:
                        repo = ChatRepository(session)
                        chat = await repo.create({"title": f"Concurrent {i}"})
                        await session.commit()
                        return chat
                tasks.append(query())

            results = await asyncio.gather(*tasks)
            return results

        results = await benchmark(concurrent_queries)
        assert len(results) == 10

    async def test_connection_reuse(self, initialized_db, benchmark):
        """Benchmark connection reuse from pool."""
        async def reuse_connections():
            for i in range(20):
                async with get_session() as session:
                    repo = ChatRepository(session)
                    await repo.create({"title": f"Reuse {i}"})
                    await session.commit()

        await benchmark(reuse_connections)


@pytest.mark.asyncio
class TestQueryComplexity:
    """Benchmarks for complex query patterns."""

    async def test_join_query_performance(self, initialized_db, benchmark):
        """Benchmark query with joins."""
        # Setup: Create chat with messages
        async with get_session() as session:
            chat_repo = ChatRepository(session)
            msg_repo = MessageRepository(session)

            chat = await chat_repo.create({"title": "Join Test"})
            await session.commit()

            for i in range(10):
                await msg_repo.create({
                    "chat_id": chat.id,
                    "role": "user",
                    "content": f"Message {i}"
                })
            await session.commit()
            chat_id = chat.id

        async def join_query():
            async with get_session() as session:
                repo = ChatRepository(session)
                return await repo.get_with_messages(chat_id)

        result = await benchmark(join_query)
        assert result is not None

    async def test_count_query_performance(self, initialized_db, benchmark):
        """Benchmark count query."""
        # Setup: Create multiple chats
        async with get_session() as session:
            repo = ChatRepository(session)
            for i in range(100):
                await repo.create({"title": f"Count Chat {i}"})
            await session.commit()

        async def count_query():
            async with get_session() as session:
                repo = ChatRepository(session)
                return await repo.count()

        result = await benchmark(count_query)
        assert result == 100

    async def test_update_query_performance(self, initialized_db, benchmark):
        """Benchmark update query."""
        # Setup: Create a chat
        async with get_session() as session:
            repo = ChatRepository(session)
            chat = await repo.create({"title": "Original"})
            await session.commit()
            chat_id = chat.id

        async def update_query():
            async with get_session() as session:
                repo = ChatRepository(session)
                updated = await repo.update(chat_id, {"title": "Updated"})
                await session.commit()
                return updated

        result = await benchmark(update_query)
        assert result.title == "Updated"

    async def test_delete_query_performance(self, initialized_db, benchmark):
        """Benchmark delete query."""
        async def delete_query():
            # Create a chat
            async with get_session() as session:
                repo = ChatRepository(session)
                chat = await repo.create({"title": "To Delete"})
                await session.commit()
                chat_id = chat.id

            # Delete it
            async with get_session() as session:
                repo = ChatRepository(session)
                result = await repo.delete(chat_id)
                await session.commit()
                return result

        result = await benchmark(delete_query)
        assert result is True
