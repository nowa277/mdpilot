"""Base repository class with common CRUD operations."""

from __future__ import annotations

from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdpilot.database.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base repository with common CRUD operations.

    This generic repository provides standard database operations for any
    SQLAlchemy model. Specific repositories should inherit from this class
    and add domain-specific query methods.

    Type Parameters:
        ModelType: The SQLAlchemy model class this repository manages.

    Args:
        session: The async database session to use for operations.
        model: The SQLAlchemy model class.

    Note:
        This repository does not manage session lifecycle. The caller is
        responsible for committing transactions and closing the session.
    """

    def __init__(self, session: AsyncSession, model: type[ModelType]) -> None:
        """Initialize the repository.

        Args:
            session: The async database session.
            model: The SQLAlchemy model class.
        """
        self.session = session
        self.model = model

    async def create(self, data: dict[str, Any]) -> ModelType:
        """Create a new record.

        Args:
            data: Dictionary of field values for the new record.

        Returns:
            The created model instance.

        Note:
            The caller must commit the session for changes to persist.
        """
        instance = self.model(**data)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def get_by_id(self, id: UUID) -> ModelType | None:
        """Get a record by its ID.

        Args:
            id: The UUID of the record to retrieve.

        Returns:
            The model instance if found, None otherwise.
        """
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[ModelType]:
        """Get all records with pagination.

        Args:
            skip: Number of records to skip (default: 0).
            limit: Maximum number of records to return (default: 100).

        Returns:
            List of model instances.
        """
        result = await self.session.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def update(self, id: UUID, data: dict[str, Any]) -> ModelType | None:
        """Update a record by its ID.

        Args:
            id: The UUID of the record to update.
            data: Dictionary of field values to update.

        Returns:
            The updated model instance if found, None otherwise.

        Note:
            The caller must commit the session for changes to persist.
        """
        instance = await self.get_by_id(id)
        if instance is None:
            return None

        for key, value in data.items():
            if hasattr(instance, key):
                setattr(instance, key, value)

        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def delete(self, id: UUID) -> bool:
        """Delete a record by its ID.

        Args:
            id: The UUID of the record to delete.

        Returns:
            True if the record was deleted, False if not found.

        Note:
            The caller must commit the session for changes to persist.
        """
        instance = await self.get_by_id(id)
        if instance is None:
            return False

        await self.session.delete(instance)
        await self.session.flush()
        return True

    async def count(self) -> int:
        """Count total number of records.

        Returns:
            The total count of records in the table.
        """
        result = await self.session.execute(
            select(func.count()).select_from(self.model)
        )
        return result.scalar_one()
