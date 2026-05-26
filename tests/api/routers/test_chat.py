"""Tests for Chat Management API."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client."""
    from mdpilot.api.app import create_app

    app = create_app()
    return TestClient(app)


def test_create_chat_session(client):
    """Test creating a new chat session."""
    response = client.post(
        "/api/v1/chat/sessions",
        json={"user_id": "test_user", "metadata": {"source": "test"}},
    )
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert data["user_id"] == "test_user"
    assert data["status"] == "active"
    assert "created_at" in data


def test_send_message(client):
    """Test sending a message to a chat session."""
    # Create session first
    session_response = client.post(
        "/api/v1/chat/sessions",
        json={"user_id": "test_user"},
    )
    session_id = session_response.json()["session_id"]

    # Send message
    response = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "Hello, MDPilot!", "role": "user"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "message_id" in data
    assert data["content"] == "Hello, MDPilot!"
    assert data["role"] == "user"
    assert data["session_id"] == session_id


def test_get_message_history(client):
    """Test retrieving message history."""
    # Create session and send messages
    session_response = client.post(
        "/api/v1/chat/sessions",
        json={"user_id": "test_user"},
    )
    session_id = session_response.json()["session_id"]

    client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "Message 1", "role": "user"},
    )
    client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "Response 1", "role": "assistant"},
    )

    # Get history
    response = client.get(f"/api/v1/chat/sessions/{session_id}/messages")
    assert response.status_code == 200
    data = response.json()
    assert "messages" in data
    assert len(data["messages"]) == 2
    assert data["messages"][0]["content"] == "Message 1"
    assert data["messages"][1]["content"] == "Response 1"


def test_get_nonexistent_session(client):
    """Test getting messages from nonexistent session."""
    response = client.get("/api/v1/chat/sessions/nonexistent/messages")
    assert response.status_code == 404


def test_send_message_to_nonexistent_session(client):
    """Test sending message to nonexistent session."""
    response = client.post(
        "/api/v1/chat/sessions/nonexistent/messages",
        json={"content": "Hello", "role": "user"},
    )
    assert response.status_code == 404


def test_message_pagination(client):
    """Test message history pagination."""
    # Create session and send multiple messages
    session_response = client.post(
        "/api/v1/chat/sessions",
        json={"user_id": "test_user"},
    )
    session_id = session_response.json()["session_id"]

    for i in range(5):
        client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"content": f"Message {i}", "role": "user"},
        )

    # Get paginated history
    response = client.get(
        f"/api/v1/chat/sessions/{session_id}/messages",
        params={"limit": 2, "offset": 1},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["messages"]) == 2
    assert data["messages"][0]["content"] == "Message 1"
    assert data["total"] == 5
