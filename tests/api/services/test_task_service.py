"""Tests for database-backed TaskService."""

import uuid

import pytest

from mdpilot.api.services.task_service import TaskService
from mdpilot.config.schema import DatabaseConfig
from mdpilot.database.base import Base
from mdpilot.database.engine import dispose_engine, get_engine, init_db
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
class TestTaskService:
    """Tests for TaskService."""

    async def test_create_task(self, initialized_db):
        """Test creating a task."""
        async with get_session() as session:
            service = TaskService(session)
            task = await service.create_task(
                task_type="test_task",
                parameters={"param1": "value1"},
                user_id="user123",
                metadata={"source": "test"},
            )
            await session.commit()

            assert task.task_id is not None
            assert task.task_type == "test_task"
            assert task.parameters == {"param1": "value1"}
            assert task.user_id == "user123"
            assert task.status == "pending"
            assert task.metadata == {"source": "test"}
            assert task.created_at is not None
            assert task.updated_at is not None

    async def test_create_task_without_metadata(self, initialized_db):
        """Test creating a task without metadata."""
        async with get_session() as session:
            service = TaskService(session)
            task = await service.create_task(
                task_type="simple_task",
                parameters={"key": "value"},
                user_id="user456",
            )
            await session.commit()

            assert task.task_id is not None
            assert task.metadata is None

    async def test_get_task(self, initialized_db):
        """Test retrieving a task."""
        async with get_session() as session:
            service = TaskService(session)

            # Create task
            created = await service.create_task(
                task_type="test_task",
                parameters={"param": "value"},
                user_id="user123",
            )
            await session.commit()

            # Retrieve task
            retrieved = await service.get_task(created.task_id)

            assert retrieved is not None
            assert retrieved.task_id == created.task_id
            assert retrieved.task_type == "test_task"
            assert retrieved.user_id == "user123"
            assert retrieved.status == "pending"

    async def test_get_task_not_found(self, initialized_db):
        """Test retrieving a non-existent task."""
        async with get_session() as session:
            service = TaskService(session)
            result = await service.get_task(str(uuid.uuid4()))
            assert result is None

    async def test_get_task_invalid_uuid(self, initialized_db):
        """Test retrieving a task with invalid UUID."""
        async with get_session() as session:
            service = TaskService(session)
            result = await service.get_task("invalid-uuid")
            assert result is None

    async def test_list_tasks_no_filters(self, initialized_db):
        """Test listing all tasks without filters."""
        async with get_session() as session:
            service = TaskService(session)

            # Create multiple tasks
            for i in range(5):
                await service.create_task(
                    task_type=f"task_type_{i}",
                    parameters={"index": i},
                    user_id=f"user{i}",
                )
            await session.commit()

            # List all tasks
            tasks, total = await service.list_tasks()

            assert len(tasks) == 5
            assert total == 5

    async def test_list_tasks_filter_by_user(self, initialized_db):
        """Test listing tasks filtered by user_id."""
        async with get_session() as session:
            service = TaskService(session)

            # Create tasks for different users
            for i in range(3):
                await service.create_task(
                    task_type="task",
                    parameters={},
                    user_id="user1",
                )
            for i in range(2):
                await service.create_task(
                    task_type="task",
                    parameters={},
                    user_id="user2",
                )
            await session.commit()

            # List tasks for user1
            tasks, total = await service.list_tasks(user_id="user1")

            assert len(tasks) == 3
            assert total == 3
            assert all(t.user_id == "user1" for t in tasks)

    async def test_list_tasks_filter_by_status(self, initialized_db):
        """Test listing tasks filtered by status."""
        async with get_session() as session:
            service = TaskService(session)

            # Create tasks with different statuses
            task1 = await service.create_task(
                task_type="task",
                parameters={},
                user_id="user1",
            )
            await session.commit()

            # Cancel one task
            await service.cancel_task(task1.task_id)
            await session.commit()

            # Create more pending tasks
            await service.create_task(
                task_type="task",
                parameters={},
                user_id="user1",
            )
            await session.commit()

            # List pending tasks
            tasks, total = await service.list_tasks(status="pending")
            assert len(tasks) == 1
            assert total == 1
            assert all(t.status == "pending" for t in tasks)

            # List cancelled tasks
            tasks, total = await service.list_tasks(status="cancelled")
            assert len(tasks) == 1
            assert total == 1
            assert all(t.status == "cancelled" for t in tasks)

    async def test_list_tasks_filter_by_user_and_status(self, initialized_db):
        """Test listing tasks filtered by both user_id and status."""
        async with get_session() as session:
            service = TaskService(session)

            # Create tasks
            task1 = await service.create_task(
                task_type="task",
                parameters={},
                user_id="user1",
            )
            await session.commit()

            await service.create_task(
                task_type="task",
                parameters={},
                user_id="user1",
            )
            await session.commit()

            await service.create_task(
                task_type="task",
                parameters={},
                user_id="user2",
            )
            await session.commit()

            # Cancel one task for user1
            await service.cancel_task(task1.task_id)
            await session.commit()

            # List pending tasks for user1
            tasks, total = await service.list_tasks(
                user_id="user1",
                status="pending",
            )

            assert len(tasks) == 1
            assert total == 1
            assert tasks[0].user_id == "user1"
            assert tasks[0].status == "pending"

    async def test_list_tasks_with_pagination(self, initialized_db):
        """Test listing tasks with pagination."""
        async with get_session() as session:
            service = TaskService(session)

            # Create 10 tasks
            for i in range(10):
                await service.create_task(
                    task_type="task",
                    parameters={"index": i},
                    user_id="user1",
                )
            await session.commit()

            # Get first page
            tasks, total = await service.list_tasks(limit=5, offset=0)
            assert len(tasks) == 5
            assert total == 10

            # Get second page
            tasks, total = await service.list_tasks(limit=5, offset=5)
            assert len(tasks) == 5
            assert total == 10

    async def test_list_tasks_ordering(self, initialized_db):
        """Test that tasks are ordered by created_at descending."""
        async with get_session() as session:
            service = TaskService(session)

            # Create tasks
            task1 = await service.create_task(
                task_type="task1",
                parameters={},
                user_id="user1",
            )
            await session.commit()

            task2 = await service.create_task(
                task_type="task2",
                parameters={},
                user_id="user1",
            )
            await session.commit()

            task3 = await service.create_task(
                task_type="task3",
                parameters={},
                user_id="user1",
            )
            await session.commit()

            # List tasks
            tasks, total = await service.list_tasks()

            # Most recent should be first
            assert tasks[0].task_id == task3.task_id
            assert tasks[1].task_id == task2.task_id
            assert tasks[2].task_id == task1.task_id

    async def test_cancel_task(self, initialized_db):
        """Test cancelling a task."""
        async with get_session() as session:
            service = TaskService(session)

            # Create task
            task = await service.create_task(
                task_type="task",
                parameters={},
                user_id="user1",
            )
            await session.commit()

            assert task.status == "pending"

            # Cancel task
            cancelled = await service.cancel_task(task.task_id)
            await session.commit()

            assert cancelled is not None
            assert cancelled.task_id == task.task_id
            assert cancelled.status == "cancelled"

    async def test_cancel_task_not_found(self, initialized_db):
        """Test cancelling a non-existent task."""
        async with get_session() as session:
            service = TaskService(session)
            result = await service.cancel_task(str(uuid.uuid4()))
            assert result is None

    async def test_cancel_task_invalid_uuid(self, initialized_db):
        """Test cancelling a task with invalid UUID."""
        async with get_session() as session:
            service = TaskService(session)
            result = await service.cancel_task("invalid-uuid")
            assert result is None

    async def test_list_tasks_empty(self, initialized_db):
        """Test listing tasks when none exist."""
        async with get_session() as session:
            service = TaskService(session)
            tasks, total = await service.list_tasks()

            assert len(tasks) == 0
            assert total == 0
