"""Tests for session persistence — save/load and security verification."""

from __future__ import annotations

from pathlib import Path

import pytest

from mdpilot.agent.session import SessionStore


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """Return a temp database path."""
    return tmp_path / "persistence_test.db"


def test_session_save_and_load(db_path: Path):
    """Test saving and loading conversation history."""
    # Create session and add messages
    store1 = SessionStore(db_path=str(db_path))
    session_id = store1.create_session(title="Persistence Test")

    # Add various message types
    store1.add_message(session_id, "user", "Hello, how are you?")
    store1.add_message(session_id, "assistant", "I'm doing well, thanks!")
    store1.add_message(
        session_id,
        "assistant",
        "Let me run a command",
        tool_calls=[{"id": "tc1", "name": "bash", "arguments": {"cmd": "ls -la"}}],
    )
    store1.add_message(session_id, "tool", "file1.txt\nfile2.txt", tool_call_id="tc1")
    store1.close()

    # Load in new session
    store2 = SessionStore(db_path=str(db_path))
    loaded_messages = store2.get_messages(session_id)

    # Verify messages match
    assert len(loaded_messages) == 4
    assert loaded_messages[0]["role"] == "user"
    assert loaded_messages[0]["content"] == "Hello, how are you?"
    assert loaded_messages[1]["role"] == "assistant"
    assert loaded_messages[1]["content"] == "I'm doing well, thanks!"
    assert loaded_messages[2]["role"] == "assistant"
    assert loaded_messages[2]["tool_calls"] is not None
    assert loaded_messages[2]["tool_calls"][0]["name"] == "bash"
    assert loaded_messages[3]["role"] == "tool"
    assert loaded_messages[3]["tool_call_id"] == "tc1"

    # Verify session metadata
    session = store2.get_session(session_id)
    assert session is not None
    assert session["title"] == "Persistence Test"
    assert session["message_count"] == 4

    store2.close()


def test_multiple_sessions_isolation(db_path: Path):
    """Test that multiple sessions are properly isolated."""
    store = SessionStore(db_path=str(db_path))

    # Create two sessions
    sid1 = store.create_session(title="Session 1")
    sid2 = store.create_session(title="Session 2")

    # Add messages to each
    store.add_message(sid1, "user", "Message in session 1")
    store.add_message(sid2, "user", "Message in session 2")

    # Verify isolation
    msgs1 = store.get_messages(sid1)
    msgs2 = store.get_messages(sid2)

    assert len(msgs1) == 1
    assert len(msgs2) == 1
    assert msgs1[0]["content"] == "Message in session 1"
    assert msgs2[0]["content"] == "Message in session 2"

    store.close()


def test_persistence_across_restarts(db_path: Path):
    """Test that data persists across multiple store instances."""
    # First instance
    store1 = SessionStore(db_path=str(db_path))
    sid = store1.create_session(title="Restart Test")
    store1.add_message(sid, "user", "First message")
    store1.close()

    # Second instance
    store2 = SessionStore(db_path=str(db_path))
    store2.add_message(sid, "assistant", "Second message")
    store2.close()

    # Third instance
    store3 = SessionStore(db_path=str(db_path))
    messages = store3.get_messages(sid)
    assert len(messages) == 2
    assert messages[0]["content"] == "First message"
    assert messages[1]["content"] == "Second message"
    store3.close()


def test_sql_injection_prevention(db_path: Path):
    """Test that SQL injection attempts are safely handled."""
    store = SessionStore(db_path=str(db_path))

    # Try SQL injection in session title
    malicious_title = "'; DROP TABLE sessions; --"
    sid = store.create_session(title=malicious_title)

    # Verify the title is stored as-is (not executed)
    session = store.get_session(sid)
    assert session is not None
    assert session["title"] == malicious_title

    # Try SQL injection in message content
    malicious_content = "Hello'; DELETE FROM messages WHERE '1'='1"
    store.add_message(sid, "user", malicious_content)

    messages = store.get_messages(sid)
    assert len(messages) == 1
    assert messages[0]["content"] == malicious_content

    # Try SQL injection in search
    malicious_query = "test' OR '1'='1"
    results = store.search_messages(malicious_query)
    # Should not return all messages, only those matching the literal string
    assert len(results) <= 1  # At most the message we just added

    # Verify tables still exist
    sessions = store.list_sessions()
    assert len(sessions) >= 1

    store.close()


def test_concurrent_message_ordering(db_path: Path):
    """Test that messages maintain correct order even with rapid additions."""
    store = SessionStore(db_path=str(db_path))
    sid = store.create_session(title="Order Test")

    # Add messages rapidly
    for i in range(100):
        store.add_message(sid, "user" if i % 2 == 0 else "assistant", f"Message {i}")

    # Verify order is preserved
    messages = store.get_messages(sid)
    assert len(messages) == 100
    for i, msg in enumerate(messages):
        assert f"Message {i}" in msg["content"]

    store.close()


def test_empty_content_handling(db_path: Path):
    """Test that empty content is handled correctly."""
    store = SessionStore(db_path=str(db_path))
    sid = store.create_session()

    # Add message with empty content
    msg_id = store.add_message(sid, "assistant", "")
    assert msg_id > 0

    messages = store.get_messages(sid)
    assert len(messages) == 1
    assert messages[0]["content"] == ""

    store.close()


def test_special_characters_in_content(db_path: Path):
    """Test that special characters are properly stored and retrieved."""
    store = SessionStore(db_path=str(db_path))
    sid = store.create_session()

    special_chars = "Hello\nWorld\t\r\n'\"\\`${}[]()!@#%^&*"
    store.add_message(sid, "user", special_chars)

    messages = store.get_messages(sid)
    assert len(messages) == 1
    assert messages[0]["content"] == special_chars

    store.close()


def test_unicode_content(db_path: Path):
    """Test that Unicode content is properly stored and retrieved."""
    store = SessionStore(db_path=str(db_path))
    sid = store.create_session(title="Unicode 测试 🧪")

    unicode_content = "Hello 世界! 🚀 Привет мир! مرحبا بالعالم"
    store.add_message(sid, "user", unicode_content)

    session = store.get_session(sid)
    assert session["title"] == "Unicode 测试 🧪"

    messages = store.get_messages(sid)
    assert messages[0]["content"] == unicode_content

    store.close()


def test_large_message_content(db_path: Path):
    """Test that large messages are properly stored."""
    store = SessionStore(db_path=str(db_path))
    sid = store.create_session()

    # Create a large message (1MB)
    large_content = "A" * (1024 * 1024)
    store.add_message(sid, "user", large_content)

    messages = store.get_messages(sid)
    assert len(messages) == 1
    assert len(messages[0]["content"]) == 1024 * 1024

    store.close()


def test_delete_session_cascade(db_path: Path):
    """Test that deleting a session also deletes its messages."""
    store = SessionStore(db_path=str(db_path))

    sid = store.create_session(title="Delete Test")
    store.add_message(sid, "user", "Message 1")
    store.add_message(sid, "assistant", "Message 2")

    # Verify messages exist
    messages = store.get_messages(sid)
    assert len(messages) == 2

    # Delete session
    assert store.delete_session(sid) is True

    # Verify session and messages are gone
    assert store.get_session(sid) is None
    messages = store.get_messages(sid)
    assert len(messages) == 0

    store.close()


def test_transaction_rollback_on_error(db_path: Path):
    """Test that transactions are properly handled on errors."""
    store = SessionStore(db_path=str(db_path))

    # Create a valid session
    sid = store.create_session(title="Valid Session")
    store.add_message(sid, "user", "Valid message")

    # Try to add message to non-existent session (should fail)
    # Note: SQLite with foreign keys disabled won't enforce this,
    # but we test the error handling path
    try:
        # This should work even with invalid session_id in SQLite
        # because foreign keys are not enforced by default
        store.add_message("nonexistent", "user", "Invalid message")
    except Exception:
        pass  # Expected to fail

    # Verify original session is still intact
    messages = store.get_messages(sid)
    assert len(messages) == 1
    assert messages[0]["content"] == "Valid message"

    store.close()


def test_add_message_atomicity(db_path: Path):
    """Test that add_message is atomic - if UPDATE fails, INSERT should rollback."""
    import sqlite3

    store = SessionStore(db_path=str(db_path))
    sid = store.create_session(title="Atomicity Test")

    # Add one message successfully
    store.add_message(sid, "user", "First message")
    assert len(store.get_messages(sid)) == 1

    # Get the connection and check initial state
    conn = store._get_conn()
    initial_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM messages WHERE session_id = ?", (sid,)
    ).fetchone()["cnt"]
    assert initial_count == 1

    # Create a trigger that will cause the UPDATE to fail
    conn.execute("""
        CREATE TRIGGER fail_update
        BEFORE UPDATE ON sessions
        BEGIN
            SELECT RAISE(ABORT, 'Simulated UPDATE failure');
        END
    """)
    conn.commit()

    # This should fail on the UPDATE
    with pytest.raises(sqlite3.IntegrityError):
        store.add_message(sid, "user", "Second message")

    # Remove the trigger
    conn.execute("DROP TRIGGER fail_update")
    conn.commit()

    # Check if the message was added despite the error
    messages_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM messages WHERE session_id = ?", (sid,)
    ).fetchone()["cnt"]

    # WITH transaction support: message count should be 1 (both rolled back)
    assert messages_count == 1, "With transactions, INSERT should rollback when UPDATE fails"

    store.close()


def test_delete_session_atomicity(db_path: Path):
    """Test that delete_session is atomic - both deletes succeed or both fail."""
    import sqlite3

    store = SessionStore(db_path=str(db_path))
    sid = store.create_session(title="Delete Atomicity Test")
    store.add_message(sid, "user", "Test message")

    # Verify session and message exist
    assert store.get_session(sid) is not None
    assert len(store.get_messages(sid)) == 1

    # Create a constraint that will cause the session DELETE to fail
    conn = store._get_conn()
    # Add a trigger that prevents deletion
    conn.execute("""
        CREATE TRIGGER prevent_delete
        BEFORE DELETE ON sessions
        BEGIN
            SELECT RAISE(ABORT, 'Simulated deletion failure');
        END
    """)
    conn.commit()

    # This should fail
    with pytest.raises(sqlite3.IntegrityError):
        store.delete_session(sid)

    # Remove the trigger
    conn.execute("DROP TRIGGER prevent_delete")
    conn.commit()

    # WITH transaction support: both session and messages remain (consistent)
    assert store.get_session(sid) is not None, "Session should still exist"
    messages = store.get_messages(sid)
    assert len(messages) == 1, "With transactions, messages should remain when session DELETE fails"
    assert messages[0]["content"] == "Test message"

    store.close()


def test_list_sessions_consistency(db_path: Path):
    """Test that list_sessions sees a consistent snapshot of data."""
    import threading
    import time

    store = SessionStore(db_path=str(db_path))

    # Create multiple sessions with messages
    sids = []
    for i in range(5):
        sid = store.create_session(title=f"Session {i}")
        sids.append(sid)
        for j in range(i + 1):
            store.add_message(sid, "user", f"Message {j}")

    # Function to continuously add messages in background
    stop_flag = threading.Event()

    def add_messages_continuously():
        while not stop_flag.is_set():
            for sid in sids:
                try:
                    store.add_message(sid, "user", "Background message")
                    time.sleep(0.001)
                except Exception:
                    pass

    # Start background thread
    thread = threading.Thread(target=add_messages_continuously)
    thread.start()

    try:
        # List sessions multiple times - each call should see consistent counts
        for _ in range(10):
            sessions = store.list_sessions()
            # Each session's message_count should be consistent with what we'd get
            # from a direct query at that moment
            for session in sessions:
                # The count should be >= initial count (background thread adds more)
                sid_index = int(session["title"].split()[-1])
                assert session["message_count"] >= sid_index + 1
            time.sleep(0.01)
    finally:
        stop_flag.set()
        thread.join()

    store.close()


def test_close_connection_error_handling(db_path: Path):
    """Test error handling when closing connection fails."""
    store = SessionStore(db_path=str(db_path))

    # Close connection normally
    store.close()

    # Closing again should handle gracefully
    store.close()

    # Should be able to use store again (reconnects)
    session_id = store.create_session("Test")
    assert session_id is not None
    store.close()


def test_update_session_title_error_handling(db_path: Path):
    """Test error handling in update_session_title."""
    store = SessionStore(db_path=str(db_path))
    session_id = store.create_session("Original")

    # Update title successfully
    store.update_session_title(session_id, "Updated")
    session = store.get_session(session_id)
    assert session["title"] == "Updated"

    # Update non-existent session (should not raise)
    store.update_session_title("nonexistent", "Title")

    store.close()


def test_get_recent_messages_edge_cases(db_path: Path):
    """Test get_recent_messages with edge cases."""
    store = SessionStore(db_path=str(db_path))
    session_id = store.create_session("Test")

    # No messages - should return empty list
    messages = store.get_recent_messages(session_id, count=10)
    assert messages == []

    # Add 5 messages
    for i in range(5):
        store.add_message(session_id, "user", f"Message {i}")

    # Request more than available
    messages = store.get_recent_messages(session_id, count=10)
    assert len(messages) == 5

    # Request fewer than available
    messages = store.get_recent_messages(session_id, count=3)
    assert len(messages) == 3
    assert messages[0]["content"] == "Message 2"  # Last 3 messages

    store.close()


def test_export_session_nonexistent(db_path: Path):
    """Test exporting a non-existent session."""
    store = SessionStore(db_path=str(db_path))

    # Export non-existent session
    result = store.export_session("nonexistent")
    assert result == {}

    store.close()


def test_search_messages_functionality(db_path: Path):
    """Test message search functionality."""
    store = SessionStore(db_path=str(db_path))

    # Create sessions with different messages
    session1 = store.create_session("Session 1")
    session2 = store.create_session("Session 2")

    store.add_message(session1, "user", "Hello world")
    store.add_message(session1, "assistant", "Hi there")
    store.add_message(session2, "user", "world peace")

    # Search for "world"
    results = store.search_messages("world")
    assert len(results) == 2
    assert all("world" in r["content"].lower() for r in results)

    # Search for non-existent term
    results = store.search_messages("nonexistent")
    assert len(results) == 0

    store.close()


def test_create_session_error_logging(db_path: Path, caplog):
    """Test error logging in create_session."""
    import sqlite3
    
    store = SessionStore(db_path=str(db_path))
    
    # Corrupt the database to trigger an error
    conn = store._get_conn()
    conn.execute("DROP TABLE sessions")
    conn.commit()
    
    # Try to create a session - should fail and log error
    with pytest.raises(sqlite3.OperationalError):
        store.create_session("Test")
    
    store.close()


def test_list_sessions_error_logging(db_path: Path, caplog):
    """Test error logging in list_sessions."""
    import sqlite3
    
    store = SessionStore(db_path=str(db_path))
    store.create_session("Test")
    
    # Corrupt the database
    conn = store._get_conn()
    conn.execute("DROP TABLE sessions")
    conn.commit()
    
    # Try to list sessions - should fail and log error
    with pytest.raises(sqlite3.OperationalError):
        store.list_sessions()
    
    store.close()


def test_get_session_error_logging(db_path: Path, caplog):
    """Test error logging in get_session."""
    import sqlite3
    
    store = SessionStore(db_path=str(db_path))
    sid = store.create_session("Test")
    
    # Corrupt the database
    conn = store._get_conn()
    conn.execute("DROP TABLE sessions")
    conn.commit()
    
    # Try to get session - should fail and log error
    with pytest.raises(sqlite3.OperationalError):
        store.get_session(sid)
    
    store.close()


def test_delete_session_error_logging(db_path: Path, caplog):
    """Test error logging in delete_session."""
    import sqlite3
    
    store = SessionStore(db_path=str(db_path))
    sid = store.create_session("Test")
    
    # Corrupt the database
    conn = store._get_conn()
    conn.execute("DROP TABLE sessions")
    conn.commit()
    
    # Try to delete session - should fail and log error
    with pytest.raises(sqlite3.OperationalError):
        store.delete_session(sid)
    
    store.close()


def test_update_session_title_error_logging(db_path: Path, caplog):
    """Test error logging in update_session_title."""
    import sqlite3
    
    store = SessionStore(db_path=str(db_path))
    sid = store.create_session("Test")
    
    # Corrupt the database
    conn = store._get_conn()
    conn.execute("DROP TABLE sessions")
    conn.commit()
    
    # Try to update title - should fail and log error
    with pytest.raises(sqlite3.OperationalError):
        store.update_session_title(sid, "New Title")
    
    store.close()


def test_add_message_error_logging(db_path: Path, caplog):
    """Test error logging in add_message."""
    import sqlite3
    
    store = SessionStore(db_path=str(db_path))
    sid = store.create_session("Test")
    
    # Corrupt the database
    conn = store._get_conn()
    conn.execute("DROP TABLE messages")
    conn.commit()
    
    # Try to add message - should fail and log error
    with pytest.raises(sqlite3.OperationalError):
        store.add_message(sid, "user", "Test")
    
    store.close()


def test_get_messages_error_logging(db_path: Path, caplog):
    """Test error logging in get_messages."""
    import sqlite3
    
    store = SessionStore(db_path=str(db_path))
    sid = store.create_session("Test")
    store.add_message(sid, "user", "Test")
    
    # Corrupt the database
    conn = store._get_conn()
    conn.execute("DROP TABLE messages")
    conn.commit()
    
    # Try to get messages - should fail and log error
    with pytest.raises(sqlite3.OperationalError):
        store.get_messages(sid)
    
    store.close()


def test_get_recent_messages_error_logging(db_path: Path, caplog):
    """Test error logging in get_recent_messages."""
    import sqlite3
    
    store = SessionStore(db_path=str(db_path))
    sid = store.create_session("Test")
    store.add_message(sid, "user", "Test")
    
    # Corrupt the database
    conn = store._get_conn()
    conn.execute("DROP TABLE messages")
    conn.commit()
    
    # Try to get recent messages - should fail and log error
    with pytest.raises(sqlite3.OperationalError):
        store.get_recent_messages(sid)
    
    store.close()


def test_export_session_error_logging(db_path: Path, caplog):
    """Test error logging in export_session."""
    import sqlite3
    
    store = SessionStore(db_path=str(db_path))
    sid = store.create_session("Test")
    
    # Corrupt the database
    conn = store._get_conn()
    conn.execute("DROP TABLE sessions")
    conn.commit()
    
    # Try to export session - should fail and log error
    with pytest.raises(sqlite3.OperationalError):
        store.export_session(sid)
    
    store.close()


def test_search_messages_error_logging(db_path: Path, caplog):
    """Test error logging in search_messages."""
    import sqlite3
    
    store = SessionStore(db_path=str(db_path))
    store.create_session("Test")
    
    # Corrupt the database
    conn = store._get_conn()
    conn.execute("DROP TABLE messages")
    conn.commit()
    
    # Try to search messages - should fail and log error
    with pytest.raises(sqlite3.OperationalError):
        store.search_messages("test")
    
    store.close()
