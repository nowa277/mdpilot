"""End-to-end integration tests for Chat API with database."""

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
class TestChatEndpointsWithDatabase:
    """End-to-end tests for Chat API with database."""

    async def test_create_and_retrieve_chat(self, client):
        """Test creating and retrieving a chat."""
        # Create chat
        create_response = await client.post(
            "/api/v1/chats",
            json={"title": "Test Chat"}
        )
        assert create_response.status_code == 201
        chat_data = create_response.json()
        chat_id = chat_data["id"]

        # Retrieve chat
        get_response = await client.get(f"/api/v1/chats/{chat_id}")
        assert get_response.status_code == 200
        retrieved = get_response.json()
        assert retrieved["id"] == chat_id
        assert retrieved["title"] == "Test Chat"

    async def test_list_chats(self, client):
        """Test listing chats with pagination."""
        # Create multiple chats
        for i in range(5):
            await client.post(
                "/api/v1/chats",
                json={"title": f"Chat {i}"}
            )

        # List chats
        response = await client.get("/api/v1/chats?skip=0&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["chats"]) == 5
        assert data["total"] == 5

    async def test_update_chat(self, client):
        """Test updating a chat."""
        # Create chat
        create_response = await client.post(
            "/api/v1/chats",
            json={"title": "Original Title"}
        )
        chat_id = create_response.json()["id"]

        # Update chat
        update_response = await client.put(
            f"/api/v1/chats/{chat_id}",
            json={"title": "Updated Title"}
        )
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["title"] == "Updated Title"

    async def test_delete_chat(self, client):
        """Test deleting a chat."""
        # Create chat
        create_response = await client.post(
            "/api/v1/chats",
            json={"title": "To Delete"}
        )
        chat_id = create_response.json()["id"]

        # Delete chat
        delete_response = await client.delete(f"/api/v1/chats/{chat_id}")
        assert delete_response.status_code == 204

        # Verify deletion
        get_response = await client.get(f"/api/v1/chats/{chat_id}")
        assert get_response.status_code == 404

    async def test_add_message_to_chat(self, client):
        """Test adding messages to a chat."""
        # Create chat
        create_response = await client.post(
            "/api/v1/chats",
            json={"title": "Chat with Messages"}
        )
        chat_id = create_response.json()["id"]

        # Add message
        msg_response = await client.post(
            f"/api/v1/chats/{chat_id}/messages",
            json={"role": "user", "content": "Hello!"}
        )
        assert msg_response.status_code == 201
        message = msg_response.json()
        assert message["content"] == "Hello!"
        assert message["role"] == "user"

    async def test_get_chat_messages(self, client):
        """Test retrieving messages for a chat."""
        # Create chat
        create_response = await client.post(
            "/api/v1/chats",
            json={"title": "Chat"}
        )
        chat_id = create_response.json()["id"]

        # Add messages
        for i in range(3):
            await client.post(
                f"/api/v1/chats/{chat_id}/messages",
                json={"role": "user", "content": f"Message {i}"}
            )

        # Get messages
        response = await client.get(f"/api/v1/chats/{chat_id}/messages")
        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 3

    async def test_search_chats(self, client):
        """Test searching chats by title."""
        # Create chats
        await client.post("/api/v1/chats", json={"title": "Python Tutorial"})
        await client.post("/api/v1/chats", json={"title": "Java Guide"})
        await client.post("/api/v1/chats", json={"title": "Python Advanced"})

        # Search
        response = await client.get("/api/v1/chats/search?q=Python")
        assert response.status_code == 200
        data = response.json()
        assert len(data["chats"]) == 2

    async def test_chat_not_found(self, client):
        """Test 404 for non-existent chat."""
        response = await client.get("/api/v1/chats/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    async def test_message_validation(self, client):
        """Test message validation."""
        # Create chat
        create_response = await client.post(
            "/api/v1/chats",
            json={"title": "Chat"}
        )
        chat_id = create_response.json()["id"]

        # Invalid role
        response = await client.post(
            f"/api/v1/chats/{chat_id}/messages",
            json={"role": "invalid", "content": "Test"}
        )
        assert response.status_code == 422

    async def test_pagination(self, client):
        """Test pagination for chats."""
        # Create many chats
        for i in range(15):
            await client.post("/api/v1/chats", json={"title": f"Chat {i}"})

        # Page 1
        page1 = await client.get("/api/v1/chats?skip=0&limit=5")
        assert len(page1.json()["chats"]) == 5

        # Page 2
        page2 = await client.get("/api/v1/chats?skip=5&limit=5")
        assert len(page2.json()["chats"]) == 5

        # Page 3
        page3 = await client.get("/api/v1/chats?skip=10&limit=5")
        assert len(page3.json()["chats"]) == 5

    async def test_cascade_delete_messages(self, client):
        """Test that deleting chat deletes messages."""
        # Create chat with messages
        create_response = await client.post(
            "/api/v1/chats",
            json={"title": "Chat"}
        )
        chat_id = create_response.json()["id"]

        # Add messages
        msg_response = await client.post(
            f"/api/v1/chats/{chat_id}/messages",
            json={"role": "user", "content": "Test"}
        )
        message_id = msg_response.json()["id"]

        # Delete chat
        await client.delete(f"/api/v1/chats/{chat_id}")

        # Verify message is gone
        msg_get = await client.get(f"/api/v1/messages/{message_id}")
        assert msg_get.status_code == 404

    async def test_concurrent_message_creation(self, client):
        """Test concurrent message creation."""
        # Create chat
        create_response = await client.post(
            "/api/v1/chats",
            json={"title": "Concurrent Test"}
        )
        chat_id = create_response.json()["id"]

        # Add messages concurrently (simulated)
        import asyncio
        tasks = [
            client.post(
                f"/api/v1/chats/{chat_id}/messages",
                json={"role": "user", "content": f"Message {i}"}
            )
            for i in range(5)
        ]
        responses = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r.status_code == 201 for r in responses)

        # Verify all messages exist
        get_response = await client.get(f"/api/v1/chats/{chat_id}/messages")
        assert len(get_response.json()["messages"]) == 5
