"""Integration tests for TaskRepository with real database operations."""

import uuid

import pytest

from mdpilot.config.schema import DatabaseConfig
from mdpilot.database.base import Base
from mdpilot.database.engine import dispose_engine, get_engine, init_db
from mdpilot.database.repositories import ChatRepository, TaskRepository
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
class TestTaskRepositoryIntegration:
    """Integration tests for TaskRepository."""

    async def test_full_task_lifecycle(self, initialized_db):
        """Test complete task lifecycle: create, read, update, delete."""
        async with get_session() as session:
            repo = TaskRepository(session)

            # Create
            task = await repo.create({
                "task_type": "integration_test",
                "parameters": {"test": "data"},
                "user_id": "test_user",
                "status": "pending",
            })
            await session.commit()
            task_id = task.id

            # Read
            retrieved = await repo.get_by_id(task_id)
            assert retrieved is not None
            assert retrieved.task_type == "integration_test"
            assert retrieved.status == "pending"

            # Update status
            updated = await repo.update_status(task_id, "running")
            await session.commit()
            assert updated.status == "running"

            # Update to completed
            completed = await repo.update_status(task_id, "completed")
            await session.commit()
            assert completed.status == "completed"

            # Delete
            deleted = await repo.delete(task_id)
            await session.commit()
            assert deleted is True

    async def test_task_with_chat_integration(self, initialized_db):
        """Test task associated with chat."""
        async with get_session() as session:
            chat_repo = ChatRepository(session)
            task_repo = TaskRepository(session)

            # Create chat
            chat = await chat_repo.create({"title": "Task Chat"})
            await session.commit()

            # Create tasks for chat
            for i in range(3):
                await task_repo.create({
                    "task_type": f"task_{i}",
                    "parameters": {"index": i},
                    "user_id": "test_user",
                    "chat_id": chat.id,
                })
            await session.commit()

            # Retrieve tasks by chat
            tasks = await task_repo.get_by_chat_id(chat.id)
            assert len(tasks) == 3
            assert all(t.chat_id == chat.id for t in tasks)

    async def test_filter_by_status(self, initialized_db):
        """Test filtering tasks by status."""
        async with get_session() as session:
            repo = TaskRepository(session)

            # Create tasks with different statuses
            statuses = ["pending", "running", "completed", "failed", "pending"]
            for i, status in enumerate(statuses):
                await repo.create({
                    "task_type": f"task_{i}",
                    "parameters": {},
                    "user_id": "test_user",
                    "status": status,
                })
            await session.commit()

            # Filter by status
            pending = await repo.get_by_status("pending")
            assert len(pending) == 2

            running = await repo.get_by_status("running")
            assert len(running) == 1

            completed = await repo.get_by_status("completed")
            assert len(completed) == 1

            failed = await repo.get_by_status("failed")
            assert len(failed) == 1

    async def test_filter_by_user(self, initialized_db):
        """Test filtering tasks by user."""
        async with get_session() as session:
            repo = TaskRepository(session)

            # Create tasks for different users
            users = ["user1", "user2", "user1", "user3", "user1"]
            for i, user in enumerate(users):
                await repo.create({
                    "task_type": f"task_{i}",
                    "parameters": {},
                    "user_id": user,
                })
            await session.commit()

            # Filter by user
            user1_tasks = await repo.get_by_user_id("user1")
            assert len(user1_tasks) == 3

            user2_tasks = await repo.get_by_user_id("user2")
            assert len(user2_tasks) == 1

            user3_tasks = await repo.get_by_user_id("user3")
            assert len(user3_tasks) == 1

    async def test_task_ordering(self, initialized_db):
        """Test tasks are ordered by created_at descending."""
        async with get_session() as session:
            repo = TaskRepository(session)

            # Create tasks
            task_ids = []
            for i in range(5):
                task = await repo.create({
                    "task_type": f"task_{i}",
                    "parameters": {},
                    "user_id": "test_user",
                    "status": "pending",
                })
                task_ids.append(task.id)
            await session.commit()

            # Get by status
            tasks = await repo.get_by_status("pending")

            # Verify ordering (most recent first)
            assert tasks[0].id == task_ids[-1]
            assert tasks[-1].id == task_ids[0]

    async def test_status_transitions(self, initialized_db):
        """Test task status transitions."""
        async with get_session() as session:
            repo = TaskRepository(session)

            # Create task
            task = await repo.create({
                "task_type": "status_test",
                "parameters": {},
                "user_id": "test_user",
                "status": "pending",
            })
            await session.commit()

            # Transition: pending -> running
            task = await repo.update_status(task.id, "running")
            await session.commit()
            assert task.status == "running"

            # Transition: running -> completed
            task = await repo.update_status(task.id, "completed")
            await session.commit()
            assert task.status == "completed"

            # Verify final state
            final = await repo.get_by_id(task.id)
            assert final.status == "completed"

    async def test_task_with_error(self, initialized_db):
        """Test task with error information."""
        async with get_session() as session:
            repo = TaskRepository(session)

            # Create task with error
            task = await repo.create({
                "task_type": "failing_task",
                "parameters": {},
                "user_id": "test_user",
                "status": "failed",
                "error": "Task failed due to timeout",
            })
            await session.commit()

            # Retrieve and verify
            retrieved = await repo.get_by_id(task.id)
            assert retrieved.status == "failed"
            assert retrieved.error == "Task failed due to timeout"

    async def test_task_with_result(self, initialized_db):
        """Test task with result data."""
        async with get_session() as session:
            repo = TaskRepository(session)

            # Create task with result
            result_data = {
                "output": "Success",
                "metrics": {"duration": 1.5, "items_processed": 100}
            }
            task = await repo.create({
                "task_type": "completed_task",
                "parameters": {},
                "user_id": "test_user",
                "status": "completed",
                "result": result_data,
            })
            await session.commit()

            # Retrieve and verify
            retrieved = await repo.get_by_id(task.id)
            assert retrieved.result == result_data
            assert retrieved.result["metrics"]["duration"] == 1.5

    async def test_pagination_with_filters(self, initialized_db):
        """Test pagination combined with filters."""
        async with get_session() as session:
            repo = TaskRepository(session)

            # Create many tasks for one user
            for i in range(15):
                await repo.create({
                    "task_type": f"task_{i}",
                    "parameters": {},
                    "user_id": "test_user",
                })
            await session.commit()

            # Paginate
            page1 = await repo.get_by_user_id("test_user", skip=0, limit=5)
            page2 = await repo.get_by_user_id("test_user", skip=5, limit=5)
            page3 = await repo.get_by_user_id("test_user", skip=10, limit=5)

            assert len(page1) == 5
            assert len(page2) == 5
            assert len(page3) == 5

            # Verify no duplicates
            all_ids = [t.id for t in page1 + page2 + page3]
            assert len(all_ids) == len(set(all_ids))

    async def test_concurrent_status_updates(self, initialized_db):
        """Test concurrent status updates."""
        async with get_session() as session:
            repo = TaskRepository(session)

            # Create task
            task = await repo.create({
                "task_type": "concurrent_test",
                "parameters": {},
                "user_id": "test_user",
                "status": "pending",
            })
            await session.commit()
            task_id = task.id

        # Update in separate sessions
        async with get_session() as session1:
            repo1 = TaskRepository(session1)
            await repo1.update_status(task_id, "running")
            await session1.commit()

        async with get_session() as session2:
            repo2 = TaskRepository(session2)
            task = await repo2.get_by_id(task_id)
            assert task.status == "running"
