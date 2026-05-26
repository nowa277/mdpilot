"""Session management utilities for database operations."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from mdpilot.database.engine import get_session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session as an async context manager.

    This is the primary way to obtain a database session for operations.
    The session is automatically rolled back on error. You must explicitly
    commit changes using await session.commit() for them to persist.

    Usage:
        async with get_session() as session:
            # Perform database operations
            result = await session.execute(query)
            await session.commit()  # Required to persist changes

    Yields:
        An async database session.

    Raises:
        RuntimeError: If the session factory has not been initialized.
    """
    factory = get_session_factory()
    session = factory()

    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_session_dependency() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for injecting database sessions.

    This function is designed to be used as a FastAPI dependency to provide
    database sessions to route handlers.

    Usage:
        @app.get("/items")
        async def get_items(session: AsyncSession = Depends(get_session_dependency)):
            result = await session.execute(select(Item))
            return result.scalars().all()

    Yields:
        An async database session.
    """
    async with get_session() as session:
        yield session
