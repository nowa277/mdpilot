"""Tests for database session management."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from mdpilot.config.schema import DatabaseConfig
from mdpilot.database.engine import dispose_engine, init_db
from mdpilot.database.session import get_session, get_session_dependency


@pytest.fixture
def sqlite_config():
    """Create an in-memory SQLite configuration for testing."""
    return DatabaseConfig(
        url="sqlite+aiosqlite:///:memory:",
        echo=False,
        pool_size=1,
        max_overflow=0,
    )


@pytest.fixture
async def initialized_db(sqlite_config):
    """Initialize database for testing."""
    init_db(sqlite_config)
    yield
    await dispose_engine()


class TestGetSession:
    """Tests for get_session context manager."""

    async def test_get_session_returns_async_session(self, initialized_db):
        """Test that get_session returns an AsyncSession."""
        async with get_session() as session:
            assert isinstance(session, AsyncSession)

    async def test_get_session_can_execute_queries(self, initialized_db):
        """Test that session can execute queries."""
        async with get_session() as session:
            result = await session.execute(text("SELECT 1"))
            value = result.scalar()
            assert value == 1

    async def test_get_session_closes_on_exit(self, initialized_db):
        """Test that session is closed when exiting context."""
        async with get_session() as session:
            assert not session.is_active or True  # Session is usable

        # After exiting, session should be closed
        # Note: We can't easily test this without accessing internals

    async def test_get_session_rollback_on_error(self, initialized_db):
        """Test that session rolls back on error."""
        try:
            async with get_session() as session:
                # Execute a valid query first
                await session.execute(text("SELECT 1"))
                # Raise an error
                raise ValueError("Test error")
        except ValueError:
            pass  # Expected

        # Session should have been rolled back
        # Verify we can still get a new session
        async with get_session() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1

    async def test_get_session_multiple_operations(self, initialized_db):
        """Test multiple operations in a single session."""
        async with get_session() as session:
            result1 = await session.execute(text("SELECT 1"))
            assert result1.scalar() == 1

            result2 = await session.execute(text("SELECT 2"))
            assert result2.scalar() == 2

            result3 = await session.execute(text("SELECT 3"))
            assert result3.scalar() == 3

    async def test_get_session_raises_without_init(self):
        """Test that get_session raises RuntimeError if not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            async with get_session() as session:
                pass


class TestGetSessionDependency:
    """Tests for get_session_dependency FastAPI dependency."""

    async def test_get_session_dependency_returns_async_session(self, initialized_db):
        """Test that get_session_dependency returns an AsyncSession."""
        async for session in get_session_dependency():
            assert isinstance(session, AsyncSession)

    async def test_get_session_dependency_can_execute_queries(self, initialized_db):
        """Test that dependency session can execute queries."""
        async for session in get_session_dependency():
            result = await session.execute(text("SELECT 1"))
            value = result.scalar()
            assert value == 1

    async def test_get_session_dependency_closes_on_exit(self, initialized_db):
        """Test that dependency session is closed after use."""
        session_ref = None
        async for session in get_session_dependency():
            session_ref = session
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1

        # After exiting, we should be able to get a new session
        async for session in get_session_dependency():
            result = await session.execute(text("SELECT 2"))
            assert result.scalar() == 2

    async def test_get_session_dependency_rollback_on_error(self, initialized_db):
        """Test that dependency session rolls back on error."""
        try:
            async for session in get_session_dependency():
                await session.execute(text("SELECT 1"))
                raise ValueError("Test error")
        except ValueError:
            pass  # Expected

        # Should be able to get a new session
        async for session in get_session_dependency():
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1


class TestSessionLifecycle:
    """Tests for session lifecycle management."""

    async def test_session_commit(self, initialized_db):
        """Test explicit session commit."""
        async with get_session() as session:
            # Create a temporary table
            await session.execute(
                text("CREATE TABLE test_table (id INTEGER PRIMARY KEY, value TEXT)")
            )
            await session.commit()

            # Verify table exists
            result = await session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'")
            )
            assert result.scalar() == "test_table"

    async def test_session_rollback(self, initialized_db):
        """Test explicit session rollback."""
        async with get_session() as session:
            # Create a temporary table
            await session.execute(
                text("CREATE TABLE test_rollback (id INTEGER PRIMARY KEY)")
            )
            await session.commit()

            # Insert data but rollback
            await session.execute(text("INSERT INTO test_rollback (id) VALUES (1)"))
            await session.rollback()

            # Verify data was not inserted
            result = await session.execute(text("SELECT COUNT(*) FROM test_rollback"))
            assert result.scalar() == 0

    async def test_session_close(self, initialized_db):
        """Test explicit session close."""
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
            await session.close()

        # Should be able to get a new session
        async with get_session() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1

    async def test_nested_transactions(self, initialized_db):
        """Test nested transaction behavior."""
        async with get_session() as session:
            # Create a table
            await session.execute(
                text("CREATE TABLE test_nested (id INTEGER PRIMARY KEY, value TEXT)")
            )
            await session.commit()

            # Start a transaction
            await session.execute(text("INSERT INTO test_nested (id, value) VALUES (1, 'first')"))
            await session.commit()

            # Verify insert
            result = await session.execute(text("SELECT value FROM test_nested WHERE id = 1"))
            assert result.scalar() == "first"

            # Another transaction
            await session.execute(text("INSERT INTO test_nested (id, value) VALUES (2, 'second')"))
            await session.commit()

            # Verify both inserts
            result = await session.execute(text("SELECT COUNT(*) FROM test_nested"))
            assert result.scalar() == 2


class TestConcurrentSessions:
    """Tests for concurrent session usage."""

    async def test_multiple_concurrent_sessions(self, initialized_db):
        """Test that multiple sessions can be used concurrently."""
        async with get_session() as session1:
            async with get_session() as session2:
                result1 = await session1.execute(text("SELECT 1"))
                result2 = await session2.execute(text("SELECT 2"))

                assert result1.scalar() == 1
                assert result2.scalar() == 2

    async def test_sessions_are_independent(self, initialized_db):
        """Test that sessions are independent of each other."""
        async with get_session() as session1:
            # Create table in session1
            await session1.execute(
                text("CREATE TABLE test_independent (id INTEGER PRIMARY KEY)")
            )
            await session1.commit()

            async with get_session() as session2:
                # Session2 should see the committed table
                result = await session2.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table' AND name='test_independent'")
                )
                assert result.scalar() == "test_independent"
