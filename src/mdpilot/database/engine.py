"""Async database engine and session factory for SQLAlchemy 2.0."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from mdpilot.config.schema import DatabaseConfig

# Global engine and session factory instances
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def create_engine(config: DatabaseConfig) -> AsyncEngine:
    """Create an async SQLAlchemy engine from configuration.

    Args:
        config: Database configuration object.

    Returns:
        Configured async engine instance.
    """
    engine_kwargs = {
        "echo": config.echo,
        "pool_pre_ping": True,  # Enable connection health checks
    }

    # Only add pool parameters for databases that support them
    # SQLite uses NullPool or StaticPool and doesn't support these parameters
    if not config.url.startswith("sqlite"):
        engine_kwargs.update({
            "pool_size": config.pool_size,
            "max_overflow": config.max_overflow,
            "pool_timeout": config.pool_timeout,
            "pool_recycle": config.pool_recycle,
        })

    return create_async_engine(config.url, **engine_kwargs)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory from an engine.

    Args:
        engine: Async SQLAlchemy engine.

    Returns:
        Configured async session factory.
    """
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


def init_db(config: DatabaseConfig) -> None:
    """Initialize the global database engine and session factory.

    This should be called once at application startup.

    Args:
        config: Database configuration object.
    """
    global _engine, _session_factory

    _engine = create_engine(config)
    _session_factory = create_session_factory(_engine)


def get_engine() -> AsyncEngine:
    """Get the global database engine.

    Returns:
        The global async engine instance.

    Raises:
        RuntimeError: If the engine has not been initialized.
    """
    if _engine is None:
        raise RuntimeError(
            "Database engine not initialized. Call init_db() first."
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get the global session factory.

    Returns:
        The global async session factory.

    Raises:
        RuntimeError: If the session factory has not been initialized.
    """
    if _session_factory is None:
        raise RuntimeError(
            "Session factory not initialized. Call init_db() first."
        )
    return _session_factory


async def dispose_engine() -> None:
    """Dispose of the global database engine.

    This should be called at application shutdown to cleanly close
    all database connections.
    """
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
