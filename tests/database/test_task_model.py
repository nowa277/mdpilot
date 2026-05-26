"""Tests for Task SQLAlchemy model."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from mdpilot.config.schema import DatabaseConfig
from mdpilot.database.base import Base
from mdpilot.database.engine import dispose_engine, get_engine, init_db
from mdpilot.database.models import Chat, Task
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
class TestTaskModel:
    """Tests for Task model."""

    async def test_create_task(self, initialized_db):
        """Test creating a task."""
        async with get_session() as session:
            task = Task(
                task_type="structure_prediction",
                parameters={"protein_id": "P12345"},
                user_id="user123",
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)

            assert task.id is not None
            assert isinstance(task.id, uuid.UUID)
            assert task.task_type == "structure_prediction"
            assert task.parameters == {"protein_id": "P12345"}
            assert task.user_id == "user123"
            assert task.chat_id is None
            assert task.status == "pending"
            assert task.result is None
            assert task.error is None
            assert task.extra_data is None
            assert isinstance(task.created_at, datetime)
            assert isinstance(task.updated_at, datetime)
            assert task.started_at is None
            assert task.completed_at is None

    async def test_create_task_with_chat(self, initialized_db):
        """Test creating a task associated with a chat."""
        async with get_session() as session:
            # Create chat first
            chat = Chat(title="Test Chat")
            session.add(chat)
            await session.commit()
            await session.refresh(chat)

            # Create task with chat_id
            task = Task(
                task_type="analysis",
                parameters={"data": "test"},
                user_id="user123",
                chat_id=chat.id,
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)

            assert task.chat_id == chat.id
            assert task.chat is not None
            assert task.chat.id == chat.id

    async def test_create_task_with_all_fields(self, initialized_db):
        """Test creating a task with all optional fields."""
        async with get_session() as session:
            now = datetime.now(timezone.utc)
            task = Task(
                task_type="simulation",
                parameters={"steps": 1000},
                user_id="user456",
                status="completed",
                result={"output": "success"},
                error=None,
                extra_data={"priority": "high"},
                started_at=now,
                completed_at=now,
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)

            assert task.status == "completed"
            assert task.result == {"output": "success"}
            assert task.extra_data == {"priority": "high"}
            assert task.started_at is not None
            assert task.completed_at is not None

    async def test_task_required_fields(self, initialized_db):
        """Test that required fields are enforced."""
        async with get_session() as session:
            # Missing task_type
            task = Task(
                parameters={"data": "test"},
                user_id="user123",
            )
            session.add(task)

            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_task_parameters_required(self, initialized_db):
        """Test that parameters field is required."""
        async with get_session() as session:
            # Missing parameters
            task = Task(
                task_type="test",
                user_id="user123",
            )
            session.add(task)

            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_task_user_id_required(self, initialized_db):
        """Test that user_id field is required."""
        async with get_session() as session:
            # Missing user_id
            task = Task(
                task_type="test",
                parameters={"data": "test"},
            )
            session.add(task)

            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_task_valid_statuses(self, initialized_db):
        """Test that only valid statuses are accepted."""
        async with get_session() as session:
            # Test valid statuses
            valid_statuses = ["pending", "running", "completed", "failed", "cancelled"]
            for status in valid_statuses:
                task = Task(
                    task_type="test",
                    parameters={"data": "test"},
                    user_id="user123",
                    status=status,
                )
                session.add(task)
                await session.commit()
                await session.refresh(task)
                assert task.status == status

    async def test_task_invalid_status(self, initialized_db):
        """Test that invalid statuses are rejected."""
        async with get_session() as session:
            task = Task(
                task_type="test",
                parameters={"data": "test"},
                user_id="user123",
                status="invalid_status",
            )
            session.add(task)

            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_task_default_status(self, initialized_db):
        """Test that status defaults to 'pending'."""
        async with get_session() as session:
            task = Task(
                task_type="test",
                parameters={"data": "test"},
                user_id="user123",
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)

            assert task.status == "pending"

    async def test_task_json_fields(self, initialized_db):
        """Test JSON field serialization."""
        async with get_session() as session:
            complex_params = {
                "protein_id": "P12345",
                "options": {
                    "temperature": 300,
                    "steps": 1000,
                },
                "tags": ["important", "urgent"],
            }
            complex_result = {
                "status": "success",
                "metrics": {"accuracy": 0.95},
            }
            complex_metadata = {
                "source": "api",
                "version": "1.0",
            }

            task = Task(
                task_type="test",
                parameters=complex_params,
                user_id="user123",
                result=complex_result,
                extra_data=complex_metadata,
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)

            assert task.parameters == complex_params
            assert task.parameters["options"]["temperature"] == 300
            assert "important" in task.parameters["tags"]
            assert task.result == complex_result
            assert task.result["metrics"]["accuracy"] == 0.95
            assert task.extra_data == complex_metadata
            assert task.extra_data["version"] == "1.0"

    async def test_task_error_field(self, initialized_db):
        """Test error field for failed tasks."""
        async with get_session() as session:
            error_message = "Task failed due to invalid input parameters"
            task = Task(
                task_type="test",
                parameters={"data": "test"},
                user_id="user123",
                status="failed",
                error=error_message,
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)

            assert task.error == error_message
            assert task.status == "failed"

    async def test_task_timestamps(self, initialized_db):
        """Test that timestamps are automatically set."""
        async with get_session() as session:
            task = Task(
                task_type="test",
                parameters={"data": "test"},
                user_id="user123",
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)

            assert task.created_at is not None
            assert task.updated_at is not None
            assert task.created_at <= task.updated_at

    async def test_task_execution_timestamps(self, initialized_db):
        """Test started_at and completed_at timestamps."""
        async with get_session() as session:
            start_time = datetime.now(timezone.utc)
            task = Task(
                task_type="test",
                parameters={"data": "test"},
                user_id="user123",
                status="running",
                started_at=start_time,
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)

            # SQLite doesn't preserve timezone, so compare without timezone
            assert task.started_at.replace(tzinfo=timezone.utc) == start_time
            assert task.completed_at is None

            # Update to completed
            end_time = datetime.now(timezone.utc)
            task.status = "completed"
            task.completed_at = end_time
            await session.commit()
            await session.refresh(task)

            assert task.completed_at.replace(tzinfo=timezone.utc) == end_time
            assert task.started_at <= task.completed_at

    async def test_task_repr(self, initialized_db):
        """Test Task string representation."""
        async with get_session() as session:
            task = Task(
                task_type="test_task",
                parameters={"data": "test"},
                user_id="user123",
                status="running",
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)

            repr_str = repr(task)
            assert "Task" in repr_str
            assert str(task.id) in repr_str
            assert "test_task" in repr_str
            assert "running" in repr_str
            assert "user123" in repr_str


@pytest.mark.asyncio
class TestTaskChatRelationship:
    """Tests for Task-Chat relationship."""

    async def test_task_chat_relationship(self, initialized_db):
        """Test that task.chat relationship works."""
        async with get_session() as session:
            # Create chat and task
            chat = Chat(title="Test Chat")
            session.add(chat)
            await session.commit()
            await session.refresh(chat)

            task = Task(
                task_type="test",
                parameters={"data": "test"},
                user_id="user123",
                chat_id=chat.id,
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)

            # Check relationship
            assert task.chat is not None
            assert task.chat.id == chat.id
            assert task.chat.title == "Test Chat"

    async def test_chat_tasks_relationship(self, initialized_db):
        """Test that chat.tasks relationship works."""
        async with get_session() as session:
            # Create chat
            chat = Chat(title="Test Chat")
            session.add(chat)
            await session.commit()
            await session.refresh(chat)

            # Create tasks
            task1 = Task(
                task_type="task1",
                parameters={"data": "test1"},
                user_id="user123",
                chat_id=chat.id,
            )
            task2 = Task(
                task_type="task2",
                parameters={"data": "test2"},
                user_id="user123",
                chat_id=chat.id,
            )
            session.add_all([task1, task2])
            await session.commit()

            # Query chat with tasks eagerly loaded
            result = await session.execute(
                select(Chat)
                .where(Chat.id == chat.id)
                .options(selectinload(Chat.tasks))
            )
            chat_with_tasks = result.scalar_one()

            assert len(chat_with_tasks.tasks) == 2
            assert chat_with_tasks.tasks[0].task_type == "task1"
            assert chat_with_tasks.tasks[1].task_type == "task2"

    async def test_task_without_chat(self, initialized_db):
        """Test that tasks can exist without a chat."""
        async with get_session() as session:
            task = Task(
                task_type="standalone",
                parameters={"data": "test"},
                user_id="user123",
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)

            assert task.chat_id is None
            assert task.chat is None

    async def test_chat_deletion_sets_null(self, initialized_db):
        """Test that deleting a chat sets task.chat_id to NULL."""
        async with get_session() as session:
            # Create chat with task
            chat = Chat(title="Test Chat")
            session.add(chat)
            await session.commit()
            await session.refresh(chat)

            task = Task(
                task_type="test",
                parameters={"data": "test"},
                user_id="user123",
                chat_id=chat.id,
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)

            task_id = task.id
            assert task.chat_id == chat.id

            # Delete chat
            await session.delete(chat)
            await session.commit()

            # Verify task still exists but chat_id is NULL
            result = await session.execute(
                select(Task).where(Task.id == task_id)
            )
            task_after_delete = result.scalar_one()
            assert task_after_delete.chat_id is None

    async def test_tasks_ordered_by_created_at(self, initialized_db):
        """Test that tasks are ordered by created_at."""
        async with get_session() as session:
            # Create chat
            chat = Chat(title="Test Chat")
            session.add(chat)
            await session.commit()
            await session.refresh(chat)

            # Create tasks in reverse order
            task2 = Task(
                task_type="second",
                parameters={"data": "test2"},
                user_id="user123",
                chat_id=chat.id,
            )
            session.add(task2)
            await session.commit()

            task1 = Task(
                task_type="first",
                parameters={"data": "test1"},
                user_id="user123",
                chat_id=chat.id,
            )
            session.add(task1)
            await session.commit()

            # Query chat with tasks eagerly loaded
            result = await session.execute(
                select(Chat)
                .where(Chat.id == chat.id)
                .options(selectinload(Chat.tasks))
            )
            chat_with_tasks = result.scalar_one()

            # Tasks should be ordered by created_at
            assert len(chat_with_tasks.tasks) == 2
            # The first created task should come first
            assert chat_with_tasks.tasks[0].task_type == "second"
            assert chat_with_tasks.tasks[1].task_type == "first"


@pytest.mark.asyncio
class TestTaskIndexes:
    """Tests for Task model indexes."""

    async def test_task_type_index(self, initialized_db):
        """Test that task_type is indexed for filtering."""
        async with get_session() as session:
            # Create multiple tasks
            task1 = Task(
                task_type="structure_prediction",
                parameters={"data": "test1"},
                user_id="user123",
            )
            task2 = Task(
                task_type="simulation",
                parameters={"data": "test2"},
                user_id="user123",
            )
            task3 = Task(
                task_type="structure_prediction",
                parameters={"data": "test3"},
                user_id="user123",
            )
            session.add_all([task1, task2, task3])
            await session.commit()

            # Query by task_type (should use index)
            result = await session.execute(
                select(Task).where(Task.task_type == "structure_prediction")
            )
            tasks = result.scalars().all()
            assert len(tasks) == 2

    async def test_user_id_index(self, initialized_db):
        """Test that user_id is indexed for filtering."""
        async with get_session() as session:
            # Create tasks for different users
            task1 = Task(
                task_type="test",
                parameters={"data": "test1"},
                user_id="user123",
            )
            task2 = Task(
                task_type="test",
                parameters={"data": "test2"},
                user_id="user456",
            )
            task3 = Task(
                task_type="test",
                parameters={"data": "test3"},
                user_id="user123",
            )
            session.add_all([task1, task2, task3])
            await session.commit()

            # Query by user_id (should use index)
            result = await session.execute(
                select(Task).where(Task.user_id == "user123")
            )
            tasks = result.scalars().all()
            assert len(tasks) == 2

    async def test_status_index(self, initialized_db):
        """Test that status is indexed for filtering."""
        async with get_session() as session:
            # Create tasks with different statuses
            task1 = Task(
                task_type="test",
                parameters={"data": "test1"},
                user_id="user123",
                status="pending",
            )
            task2 = Task(
                task_type="test",
                parameters={"data": "test2"},
                user_id="user123",
                status="running",
            )
            task3 = Task(
                task_type="test",
                parameters={"data": "test3"},
                user_id="user123",
                status="pending",
            )
            session.add_all([task1, task2, task3])
            await session.commit()

            # Query by status (should use index)
            result = await session.execute(
                select(Task).where(Task.status == "pending")
            )
            tasks = result.scalars().all()
            assert len(tasks) == 2

    async def test_chat_id_index(self, initialized_db):
        """Test that chat_id is indexed for filtering."""
        async with get_session() as session:
            # Create chats and tasks
            chat1 = Chat(title="Chat 1")
            chat2 = Chat(title="Chat 2")
            session.add_all([chat1, chat2])
            await session.commit()
            await session.refresh(chat1)
            await session.refresh(chat2)

            task1 = Task(
                task_type="test",
                parameters={"data": "test1"},
                user_id="user123",
                chat_id=chat1.id,
            )
            task2 = Task(
                task_type="test",
                parameters={"data": "test2"},
                user_id="user123",
                chat_id=chat1.id,
            )
            task3 = Task(
                task_type="test",
                parameters={"data": "test3"},
                user_id="user123",
                chat_id=chat2.id,
            )
            session.add_all([task1, task2, task3])
            await session.commit()

            # Query by chat_id (should use index)
            result = await session.execute(
                select(Task).where(Task.chat_id == chat1.id)
            )
            tasks = result.scalars().all()
            assert len(tasks) == 2

    async def test_created_at_index(self, initialized_db):
        """Test that created_at is indexed for sorting."""
        async with get_session() as session:
            # Create multiple tasks
            task1 = Task(
                task_type="test",
                parameters={"data": "test1"},
                user_id="user123",
            )
            task2 = Task(
                task_type="test",
                parameters={"data": "test2"},
                user_id="user123",
            )
            task3 = Task(
                task_type="test",
                parameters={"data": "test3"},
                user_id="user123",
            )
            session.add_all([task1, task2, task3])
            await session.commit()

            # Query ordered by created_at (should use index)
            result = await session.execute(
                select(Task).order_by(Task.created_at.desc())
            )
            tasks = result.scalars().all()
            assert len(tasks) == 3
