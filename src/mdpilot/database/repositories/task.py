"""Task repository with task-specific queries."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdpilot.database.models.task import Task
from mdpilot.database.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    """Repository for Task model with task-specific queries.

    Provides CRUD operations and specialized queries for tasks.

    Args:
        session: The async database session to use for operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the task repository.

        Args:
            session: The async database session.
        """
        super().__init__(session, Task)

    async def get_by_status(self, status: str) -> list[Task]:
        """Get all tasks with a specific status.

        Args:
            status: The status to filter by (pending, running, completed, failed, cancelled).

        Returns:
            List of tasks with the specified status, ordered by creation date descending.
        """
        result = await self.session.execute(
            select(Task)
            .where(Task.status == status)
            .order_by(desc(Task.created_at))
        )
        return list(result.scalars().all())

    async def get_by_chat_id(self, chat_id: UUID) -> list[Task]:
        """Get all tasks associated with a specific chat.

        Args:
            chat_id: The UUID of the chat.

        Returns:
            List of tasks for the chat, ordered by creation date descending.
        """
        result = await self.session.execute(
            select(Task)
            .where(Task.chat_id == chat_id)
            .order_by(desc(Task.created_at))
        )
        return list(result.scalars().all())

    async def update_status(self, task_id: UUID, status: str) -> Task | None:
        """Update the status of a task.

        Args:
            task_id: The UUID of the task to update.
            status: The new status value.

        Returns:
            The updated task instance if found, None otherwise.

        Note:
            The caller must commit the session for changes to persist.
        """
        return await self.update(task_id, {"status": status})

    async def get_by_user_id(
        self, user_id: str, skip: int = 0, limit: int = 100
    ) -> list[Task]:
        """Get tasks for a specific user with pagination.

        Args:
            user_id: The user ID to filter by.
            skip: Number of tasks to skip (default: 0).
            limit: Maximum number of tasks to return (default: 100).

        Returns:
            List of tasks for the user, ordered by creation date descending.
        """
        result = await self.session.execute(
            select(Task)
            .where(Task.user_id == user_id)
            .order_by(desc(Task.created_at))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
