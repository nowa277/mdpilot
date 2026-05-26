"""Database module for MDPilot.

This module provides async database infrastructure using SQLAlchemy 2.0
and PostgreSQL with asyncpg driver.
"""

from mdpilot.database.base import Base, TimestampMixin
from mdpilot.database.engine import (
    create_engine,
    create_session_factory,
    dispose_engine,
    get_engine,
    get_session_factory,
    init_db,
)
from mdpilot.database.session import get_session, get_session_dependency

__all__ = [
    # Base classes
    "Base",
    "TimestampMixin",
    # Engine management
    "create_engine",
    "create_session_factory",
    "init_db",
    "get_engine",
    "get_session_factory",
    "dispose_engine",
    # Session management
    "get_session",
    "get_session_dependency",
]
