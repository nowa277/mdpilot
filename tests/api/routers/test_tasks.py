"""Tests for Task Management API."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client."""
    from mdpilot.api.app import create_app

    app = create_app()
    return TestClient(app)


def test_create_task(client):
    """Test creating a new task."""
    response = client.post(
        "/api/v1/tasks",
        json={
            "task_type": "md_simulation",
            "parameters": {"pdb_id": "1ABC", "steps": 1000},
            "user_id": "test_user",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["task_type"] == "md_simulation"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_get_task_status(client):
    """Test getting task status."""
    # Create task first
    create_response = client.post(
        "/api/v1/tasks",
        json={
            "task_type": "md_simulation",
            "parameters": {"pdb_id": "1ABC"},
            "user_id": "test_user",
        },
    )
    task_id = create_response.json()["task_id"]

    # Get task status
    response = client.get(f"/api/v1/tasks/{task_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == task_id
    assert data["status"] in ["pending", "running", "completed", "failed", "cancelled"]


def test_list_tasks(client):
    """Test listing tasks."""
    # Create multiple tasks
    for i in range(3):
        client.post(
            "/api/v1/tasks",
            json={
                "task_type": "md_simulation",
                "parameters": {"pdb_id": f"1AB{i}"},
                "user_id": "test_user",
            },
        )

    # List tasks
    response = client.get("/api/v1/tasks")
    assert response.status_code == 200
    data = response.json()
    assert "tasks" in data
    assert len(data["tasks"]) >= 3
    assert "total" in data


def test_list_tasks_with_filters(client):
    """Test listing tasks with filters."""
    # Create tasks with different statuses
    client.post(
        "/api/v1/tasks",
        json={
            "task_type": "md_simulation",
            "parameters": {"pdb_id": "1ABC"},
            "user_id": "user1",
        },
    )

    # List tasks filtered by user
    response = client.get("/api/v1/tasks", params={"user_id": "user1"})
    assert response.status_code == 200
    data = response.json()
    assert all(task["user_id"] == "user1" for task in data["tasks"])


def test_cancel_task(client):
    """Test cancelling a task."""
    # Create task
    create_response = client.post(
        "/api/v1/tasks",
        json={
            "task_type": "md_simulation",
            "parameters": {"pdb_id": "1ABC"},
            "user_id": "test_user",
        },
    )
    task_id = create_response.json()["task_id"]

    # Cancel task
    response = client.post(f"/api/v1/tasks/{task_id}/cancel")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled"

    # Verify task is cancelled
    status_response = client.get(f"/api/v1/tasks/{task_id}")
    assert status_response.json()["status"] == "cancelled"


def test_get_nonexistent_task(client):
    """Test getting a nonexistent task."""
    response = client.get("/api/v1/tasks/nonexistent")
    assert response.status_code == 404


def test_cancel_nonexistent_task(client):
    """Test cancelling a nonexistent task."""
    response = client.post("/api/v1/tasks/nonexistent/cancel")
    assert response.status_code == 404


def test_task_pagination(client):
    """Test task list pagination."""
    # Create multiple tasks
    for i in range(5):
        client.post(
            "/api/v1/tasks",
            json={
                "task_type": "md_simulation",
                "parameters": {"pdb_id": f"1AB{i}"},
                "user_id": "test_user",
            },
        )

    # Get paginated list
    response = client.get("/api/v1/tasks", params={"limit": 2, "offset": 1})
    assert response.status_code == 200
    data = response.json()
    assert len(data["tasks"]) == 2
    assert data["total"] >= 5
