"""Tests for database engine and session factory."""

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from mdpilot.config.schema import DatabaseConfig
from mdpilot.database.engine import (
    create_engine,
    create_session_factory,
    dispose_engine,
    get_engine,
    get_session_factory,
    init_db,
)


@pytest.fixture
def db_config():
    """Create a test database configuration."""
    return DatabaseConfig(
        url="postgresql+asyncpg://test:test@localhost:5432/test_mdpilot",
        echo=False,
        pool_size=3,
        max_overflow=5,
        pool_timeout=20,
        pool_recycle=1800,
    )


@pytest.fixture
def sqlite_config():
    """Create an in-memory SQLite configuration for testing."""
    return DatabaseConfig(
        url="sqlite+aiosqlite:///:memory:",
        echo=False,
        pool_size=1,
        max_overflow=0,
        pool_timeout=10,
        pool_recycle=3600,
    )


class TestEngineCreation:
    """Tests for engine creation."""

    def test_create_engine_returns_async_engine(self, db_config):
        """Test that create_engine returns an AsyncEngine instance."""
        engine = create_engine(db_config)
        assert isinstance(engine, AsyncEngine)
        assert engine.url.database == "test_mdpilot"

    def test_create_engine_with_sqlite(self, sqlite_config):
        """Test engine creation with SQLite."""
        engine = create_engine(sqlite_config)
        assert isinstance(engine, AsyncEngine)
        assert "sqlite" in str(engine.url)

    def test_create_engine_applies_pool_settings(self, db_config):
        """Test that pool settings are applied correctly."""
        engine = create_engine(db_config)
        # PostgreSQL uses QueuePool which has these attributes
        assert engine.pool.size() == db_config.pool_size
        assert engine.pool._max_overflow == db_config.max_overflow
        assert engine.pool._timeout == db_config.pool_timeout
        assert engine.pool._recycle == db_config.pool_recycle

    def test_create_engine_with_echo(self):
        """Test engine creation with echo enabled."""
        config = DatabaseConfig(
            url="sqlite+aiosqlite:///:memory:",
            echo=True,
        )
        engine = create_engine(config)
        assert engine.echo is True


class TestSessionFactory:
    """Tests for session factory creation."""

    def test_create_session_factory_returns_sessionmaker(self, sqlite_config):
        """Test that create_session_factory returns a sessionmaker."""
        engine = create_engine(sqlite_config)
        factory = create_session_factory(engine)
        assert isinstance(factory, async_sessionmaker)

    def test_session_factory_creates_async_sessions(self, sqlite_config):
        """Test that the factory creates AsyncSession instances."""
        engine = create_engine(sqlite_config)
        factory = create_session_factory(engine)
        session = factory()
        assert isinstance(session, AsyncSession)
        # Clean up
        import asyncio
        asyncio.run(session.close())

    def test_session_factory_settings(self, sqlite_config):
        """Test that session factory has correct settings."""
        engine = create_engine(sqlite_config)
        factory = create_session_factory(engine)

        # Check factory configuration
        assert factory.kw.get("expire_on_commit") is False
        assert factory.kw.get("autoflush") is False
        assert factory.kw.get("autocommit") is False


class TestGlobalEngineManagement:
    """Tests for global engine and session factory management."""

    @pytest.fixture(autouse=True)
    async def cleanup(self):
        """Clean up global state after each test."""
        yield
        await dispose_engine()

    def test_init_db_initializes_globals(self, sqlite_config):
        """Test that init_db initializes global engine and factory."""
        init_db(sqlite_config)

        engine = get_engine()
        factory = get_session_factory()

        assert isinstance(engine, AsyncEngine)
        assert isinstance(factory, async_sessionmaker)

    def test_get_engine_raises_without_init(self):
        """Test that get_engine raises RuntimeError if not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            get_engine()

    def test_get_session_factory_raises_without_init(self):
        """Test that get_session_factory raises RuntimeError if not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            get_session_factory()

    async def test_dispose_engine_cleans_up(self, sqlite_config):
        """Test that dispose_engine cleans up global state."""
        init_db(sqlite_config)

        # Verify initialized
        engine = get_engine()
        assert engine is not None

        # Dispose
        await dispose_engine()

        # Verify cleaned up
        with pytest.raises(RuntimeError):
            get_engine()

        with pytest.raises(RuntimeError):
            get_session_factory()

    async def test_multiple_init_db_calls(self, sqlite_config):
        """Test that multiple init_db calls replace the previous engine."""
        init_db(sqlite_config)
        first_engine = get_engine()

        # Initialize again with different config
        new_config = DatabaseConfig(
            url="sqlite+aiosqlite:///:memory:",
            pool_size=10,
        )
        init_db(new_config)
        second_engine = get_engine()

        # Should be different instances
        assert first_engine is not second_engine


class TestConnectionPooling:
    """Tests for connection pool behavior."""

    @pytest.fixture(autouse=True)
    async def cleanup(self):
        """Clean up global state after each test."""
        yield
        await dispose_engine()

    async def test_pool_size_limit(self):
        """Test that connection pool respects size limits for PostgreSQL."""
        config = DatabaseConfig(
            url="postgresql+asyncpg://test:test@localhost:5432/test_mdpilot",
            pool_size=2,
            max_overflow=1,
        )
        engine = create_engine(config)

        # Verify pool settings are applied
        assert engine.pool.size() == 2
        assert engine.pool._max_overflow == 1

    async def test_pool_timeout_configuration(self):
        """Test that pool timeout is configured correctly."""
        config = DatabaseConfig(
            url="postgresql+asyncpg://test:test@localhost:5432/test_mdpilot",
            pool_timeout=5,
        )
        engine = create_engine(config)
        assert engine.pool._timeout == 5

    async def test_pool_recycle_configuration(self):
        """Test that pool recycle is configured correctly."""
        config = DatabaseConfig(
            url="postgresql+asyncpg://test:test@localhost:5432/test_mdpilot",
            pool_recycle=600,
        )
        engine = create_engine(config)
        assert engine.pool._recycle == 600
