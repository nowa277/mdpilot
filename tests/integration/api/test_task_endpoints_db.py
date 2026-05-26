"""End-to-end integration tests for Task API with database."""

import asyncio

import pytest
from httpx import AsyncClient

from mdpilot.api.app import create_app
from mdpilot.config.schema import DatabaseConfig
from mdpilot.database.base import Base
from mdpilot.database.engine import dispose_engine, get_engine, init_db


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


@pytest.fixture
async def client(initialized_db):
    """Create async test client with database."""
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
class TestTaskEndpointsWithDatabase:
    """End-to-end tests for Task API with database."""

    async def test_create_and_retrieve_task(self, client):
        """Test creating and retrieving a task."""
        # Create task
        create_response = await client.post(
            "/api/v1/tasks",
            json={
                "task_type": "test_task",
                "parameters": {"key": "value"},
                "user_id": "test_user"
            }
        )
        assert create_response.status_code == 201
        task_data = create_response.json()
        task_id = task_data["id"]

        # Retrieve task
        get_response = await client.get(f"/api/v1/tasks/{task_id}")
        assert get_response.status_code == 200
        retrieved = get_response.json()
        assert retrieved["id"] == task_id
        assert retrieved["task_type"] == "test_task"
        assert retrieved["status"] == "pending"

    async def test_list_tasks(self, client):
        """Test listing tasks with pagination."""
        # Create multiple tasks
        for i in range(5):
            await client.post(
                "/api/v1/tasks",
                json={
                    "task_type": f"task_{i}",
                    "parameters": {},
                    "user_id": "test_user"
                }
            )

        # List tasks
        response = await client.get("/api/v1/tasks?skip=0&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 5
        assert data["total"] == 5

    async def test_filter_tasks_by_status(self, client):
        """Test filtering tasks by status."""
        # Create tasks with different statuses
        await client.post(
            "/api/v1/tasks",
            json={
                "task_type": "task1",
                "parameters": {},
                "user_id": "user1",
                "status": "pending"
            }
        )
        await client.post(
            "/api/v1/tasks",
            json={
                "task_type": "task2",
                "parameters": {},
                "user_id": "user1",
                "status": "running"
            }
        )

        # Filter by status
        response = await client.get("/api/v1/tasks?status=pending")
        assert response.status_code == 200
        data = response.json()
        assert all(t["status"] == "pending" for t in data["tasks"])

    async def test_filter_tasks_by_user(self, client):
        """Test filtering tasks by user."""
        # Create tasks for different users
        await client.post(
            "/api/v1/tasks",
            json={
                "task_type": "task1",
                "parameters": {},
                "user_id": "user1"
            }
        )
        await client.post(
            "/api/v1/tasks",
            json={
                "task_type": "task2",
                "parameters": {},
                "user_id": "user2"
            }
        )

        # Filter by user
        response = await client.get("/api/v1/tasks?user_id=user1")
        assert response.status_code == 200
        data = response.json()
        assert all(t["user_id"] == "user1" for t in data["tasks"])

    async def test_update_task_status(self, client):
        """Test updating task status."""
        # Create task
        create_response = await client.post(
            "/api/v1/tasks",
            json={
                "task_type": "test_task",
                "parameters": {},
                "user_id": "test_user"
            }
        )
        task_id = create_response.json()["id"]

        # Update status
        update_response = await client.patch(
            f"/api/v1/tasks/{task_id}/status",
            json={"status": "running"}
        )
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["status"] == "running"

    async def test_task_lifecycle(self, client):
        """Test complete task lifecycle."""
        # Create
        create_response = await client.post(
            "/api/v1/tasks",
            json={
                "task_type": "lifecycle_test",
                "parameters": {"test": "data"},
                "user_id": "test_user"
            }
        )
        task_id = create_response.json()["id"]

        # Start
        await client.patch(
            f"/api/v1/tasks/{task_id}/status",
            json={"status": "running"}
        )

        # Complete
        complete_response = await client.patch(
            f"/api/v1/tasks/{task_id}/status",
            json={"status": "completed"}
        )
        assert complete_response.json()["status"] == "completed"

    async def test_task_with_chat(self, client):
        """Test task associated with chat."""
        # Create chat first
        chat_response = await client.post(
            "/api/v1/chats",
            json={"title": "Task Chat"}
        )
        chat_id = chat_response.json()["id"]

        # Create task with chat
        task_response = await client.post(
            "/api/v1/tasks",
            json={
                "task_type": "chat_task",
                "parameters": {},
                "user_id": "test_user",
                "chat_id": chat_id
            }
        )
        assert task_response.status_code == 201
        task = task_response.json()
        assert task["chat_id"] == chat_id

    async def test_task_not_found(self, client):
        """Test 404 for non-existent task."""
        response = await client.get("/api/v1/tasks/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    async def test_task_validation(self, client):
        """Test task validation."""
        # Missing required fields
        response = await client.post(
            "/api/v1/tasks",
            json={"task_type": "test"}
        )
        assert response.status_code == 422

    async def test_pagination(self, client):
        """Test pagination for tasks."""
        # Create many tasks
        for i in range(15):
            await client.post(
                "/api/v1/tasks",
                json={
                    "task_type": f"task_{i}",
                    "parameters": {},
                    "user_id": "test_user"
                }
            )

        # Page 1
        page1 = await client.get("/api/v1/tasks?skip=0&limit=5")
        assert len(page1.json()["tasks"]) == 5

        # Page 2
        page2 = await client.get("/api/v1/tasks?skip=5&limit=5")
        assert len(page2.json()["tasks"]) == 5

        # Page 3
        page3 = await client.get("/api/v1/tasks?skip=10&limit=5")
        assert len(page3.json()["tasks"]) == 5

    async def test_task_ordering(self, client):
        """Test tasks are ordered by created_at descending."""
        # Create tasks
        task_ids = []
        for i in range(3):
            response = await client.post(
                "/api/v1/tasks",
                json={
                    "task_type": f"task_{i}",
                    "parameters": {},
                    "user_id": "test_user"
                }
            )
            task_ids.append(response.json()["id"])
            await asyncio.sleep(0.01)  # Small delay to ensure different timestamps

        # List tasks
        response = await client.get("/api/v1/tasks")
        tasks = response.json()["tasks"]

        # Most recent first
        assert tasks[0]["id"] == task_ids[-1]

    async def test_concurrent_task_creation(self, client):
        """Test concurrent task creation."""
        # Create tasks concurrently
        tasks = [
            client.post(
                "/api/v1/tasks",
                json={
                    "task_type": f"task_{i}",
                    "parameters": {},
                    "user_id": "test_user"
                }
            )
            for i in range(5)
        ]
        responses = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r.status_code == 201 for r in responses)

        # Verify all tasks exist
        get_response = await client.get("/api/v1/tasks")
        assert len(get_response.json()["tasks"]) == 5

    async def test_task_with_error(self, client):
        """Test task with error information."""
        # Create task
        create_response = await client.post(
            "/api/v1/tasks",
            json={
                "task_type": "failing_task",
                "parameters": {},
                "user_id": "test_user"
            }
        )
        task_id = create_response.json()["id"]

        # Update to failed with error
        update_response = await client.patch(
            f"/api/v1/tasks/{task_id}/status",
            json={
                "status": "failed",
                "error": "Task failed due to timeout"
            }
        )
        assert update_response.status_code == 200
        task = update_response.json()
        assert task["status"] == "failed"
        assert task["error"] == "Task failed due to timeout"

    async def test_task_with_result(self, client):
        """Test task with result data."""
        # Create task
        create_response = await client.post(
            "/api/v1/tasks",
            json={
                "task_type": "completed_task",
                "parameters": {},
                "user_id": "test_user"
            }
        )
        task_id = create_response.json()["id"]

        # Update to completed with result
        result_data = {"output": "Success", "items": 100}
        update_response = await client.patch(
            f"/api/v1/tasks/{task_id}/status",
            json={
                "status": "completed",
                "result": result_data
            }
        )
        assert update_response.status_code == 200
        task = update_response.json()
        assert task["result"] == result_data
