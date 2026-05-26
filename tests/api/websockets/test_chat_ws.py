"""Tests for WebSocket chat functionality."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client."""
    from mdpilot.api.app import create_app

    app = create_app()
    return TestClient(app)


def test_websocket_chat_connection(client):
    """Test WebSocket chat connection."""
    with client.websocket_connect("/ws/chat/test_session") as websocket:
        # Connection should be established
        data = websocket.receive_json()
        assert data["type"] == "connection"
        assert data["message"] == "Connected to chat session: test_session"


def test_websocket_chat_send_receive(client):
    """Test sending and receiving messages via WebSocket."""
    with client.websocket_connect("/ws/chat/test_session") as websocket:
        # Skip connection message
        websocket.receive_json()

        # Send a message
        websocket.send_json({
            "type": "message",
            "content": "Hello via WebSocket",
            "role": "user"
        })

        # Receive echo
        response = websocket.receive_json()
        assert response["type"] == "message"
        assert response["content"] == "Hello via WebSocket"
        assert response["role"] == "user"


def test_websocket_chat_invalid_message(client):
    """Test handling invalid message format."""
    with client.websocket_connect("/ws/chat/test_session") as websocket:
        # Skip connection message
        websocket.receive_json()

        # Send invalid message
        websocket.send_json({"invalid": "data"})

        # Should receive error
        response = websocket.receive_json()
        assert response["type"] == "error"


def test_websocket_chat_multiple_clients(client):
    """Test multiple clients connecting to same session."""
    with client.websocket_connect("/ws/chat/test_session") as ws1:
        ws1.receive_json()  # Skip connection message

        with client.websocket_connect("/ws/chat/test_session") as ws2:
            ws2.receive_json()  # Skip connection message

            # Send from first client
            ws1.send_json({
                "type": "message",
                "content": "Hello from client 1",
                "role": "user"
            })

            # Both should receive the message
            msg1 = ws1.receive_json()
            msg2 = ws2.receive_json()

            assert msg1["content"] == "Hello from client 1"
            assert msg2["content"] == "Hello from client 1"
