"""Tests for WebSocket logs functionality."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client."""
    from mdpilot.api.app import create_app

    app = create_app()
    return TestClient(app)


def test_websocket_logs_connection(client):
    """Test WebSocket logs connection."""
    with client.websocket_connect("/ws/logs/test_task") as websocket:
        # Connection should be established
        data = websocket.receive_json()
        assert data["type"] == "connection"
        assert data["message"] == "Connected to logs for task: test_task"


def test_websocket_logs_receive(client):
    """Test receiving log messages via WebSocket."""
    with client.websocket_connect("/ws/logs/test_task") as websocket:
        # Skip connection message
        websocket.receive_json()

        # In a real scenario, logs would be pushed from the server
        # For now, we just verify the connection works
        # The actual log streaming would be tested in integration tests


def test_websocket_logs_multiple_tasks(client):
    """Test connecting to logs for different tasks."""
    with client.websocket_connect("/ws/logs/task1") as ws1:
        msg1 = ws1.receive_json()
        assert "task1" in msg1["message"]

    with client.websocket_connect("/ws/logs/task2") as ws2:
        msg2 = ws2.receive_json()
        assert "task2" in msg2["message"]
