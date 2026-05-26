"""Tests for session storage."""

import pytest
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, patch


class TestSessionStore:
    """Test SessionStore class."""
    
    def test_init_creates_db(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        assert db_path.exists()
        store.close()
    
    def test_init_creates_parent_dirs(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "subdir" / "test.db"
        store = SessionStore(db_path)
        
        assert db_path.parent.exists()
        store.close()
    
    def test_init_creates_tables(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        conn = store._get_conn()
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        
        assert "sessions" in tables
        assert "messages" in tables
        store.close()
    
    def test_get_conn_returns_same_connection(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        conn1 = store._get_conn()
        conn2 = store._get_conn()
        
        assert conn1 is conn2
        store.close()
    
    def test_get_conn_sets_pragmas(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        conn = store._get_conn()
        
        fk_result = conn.execute("PRAGMA foreign_keys").fetchone()
        assert fk_result[0] == 1
        
        journal_result = conn.execute("PRAGMA journal_mode").fetchone()
        assert journal_result[0] == "wal"
        
        store.close()
    
    def test_transaction_commits_on_success(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        session_id = store.create_session("test")
        
        with store.transaction() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, "user", "test", datetime.now(timezone.utc).isoformat())
            )
        
        messages = store.get_messages(session_id)
        assert len(messages) == 1
        store.close()
    
    def test_transaction_rolls_back_on_error(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        session_id = store.create_session("test")
        
        with pytest.raises(sqlite3.IntegrityError):
            with store.transaction() as conn:
                conn.execute(
                    "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                    (session_id, "user", "test", datetime.now(timezone.utc).isoformat())
                )
                conn.execute("INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                            (session_id, "duplicate", "2024-01-01", "2024-01-01"))
        
        messages = store.get_messages(session_id)
        assert len(messages) == 0
        store.close()
    
    def test_close(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        store.close()
        
        assert store._conn is None
    
    def test_close_error_handling(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        store._conn = Mock()
        store._conn.close = Mock(side_effect=Exception("close failed"))
        
        with pytest.raises(Exception, match="close failed"):
            store.close()
    
    def test_create_session(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        session_id = store.create_session("Test Session")
        
        assert session_id is not None
        assert len(session_id) == 12
        
        session = store.get_session(session_id)
        assert session["title"] == "Test Session"
        store.close()
    
    def test_create_session_default_title(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        session_id = store.create_session()
        
        session = store.get_session(session_id)
        assert session["title"] == ""
        store.close()
    
    def test_list_sessions(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        id1 = store.create_session("Session 1")
        id2 = store.create_session("Session 2")
        
        sessions = store.list_sessions()
        
        assert len(sessions) == 2
        assert sessions[0]["id"] == id2
        assert sessions[1]["id"] == id1
        store.close()
    
    def test_list_sessions_with_limit(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        for i in range(5):
            store.create_session(f"Session {i}")
        
        sessions = store.list_sessions(limit=3)
        
        assert len(sessions) == 3
        store.close()
    
    def test_get_session_exists(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        session_id = store.create_session("Test")
        
        session = store.get_session(session_id)
        
        assert session is not None
        assert session["id"] == session_id
        assert session["title"] == "Test"
        assert "created_at" in session
        assert "updated_at" in session
        assert session["message_count"] == 0
        store.close()
    
    def test_get_session_not_exists(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        session = store.get_session("nonexistent")
        
        assert session is None
        store.close()
    
    def test_delete_session(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        session_id = store.create_session("Test")
        store.add_message(session_id, "user", "Hello")
        
        result = store.delete_session(session_id)
        
        assert result is True
        assert store.get_session(session_id) is None
        assert len(store.get_messages(session_id)) == 0
        store.close()
    
    def test_delete_session_not_exists(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        result = store.delete_session("nonexistent")
        
        assert result is False
        store.close()
    
    def test_update_session_title(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        session_id = store.create_session("Old Title")
        
        store.update_session_title(session_id, "New Title")
        
        session = store.get_session(session_id)
        assert session["title"] == "New Title"
        store.close()
    
    def test_add_message(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        session_id = store.create_session("Test")
        
        msg_id = store.add_message(session_id, "user", "Hello")
        
        assert msg_id is not None
        messages = store.get_messages(session_id)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"
        store.close()
    
    def test_add_message_with_tool_calls(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        session_id = store.create_session("Test")
        tool_calls = [{"id": "call_1", "function": {"name": "test"}}]
        
        store.add_message(session_id, "assistant", "Using tool", tool_calls=tool_calls)
        
        messages = store.get_messages(session_id)
        assert len(messages) == 1
        assert messages[0]["tool_calls"] == tool_calls
        store.close()
    
    def test_add_message_with_tool_call_id(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        session_id = store.create_session("Test")
        
        store.add_message(session_id, "tool", "Result", tool_call_id="call_1")
        
        messages = store.get_messages(session_id)
        assert len(messages) == 1
        assert messages[0]["tool_call_id"] == "call_1"
        store.close()
    
    def test_get_messages(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        session_id = store.create_session("Test")
        store.add_message(session_id, "user", "Message 1")
        store.add_message(session_id, "assistant", "Message 2")
        
        messages = store.get_messages(session_id)
        
        assert len(messages) == 2
        assert messages[0]["content"] == "Message 1"
        assert messages[1]["content"] == "Message 2"
        store.close()
    
    def test_get_messages_with_limit(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        session_id = store.create_session("Test")
        for i in range(5):
            store.add_message(session_id, "user", f"Message {i}")
        
        messages = store.get_messages(session_id, limit=3)
        
        assert len(messages) == 3
        store.close()
    
    def test_get_messages_with_offset(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        session_id = store.create_session("Test")
        for i in range(5):
            store.add_message(session_id, "user", f"Message {i}")
        
        messages = store.get_messages(session_id, offset=2)
        
        assert len(messages) == 3
        assert messages[0]["content"] == "Message 2"
        store.close()
    
    def test_get_recent_messages(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        session_id = store.create_session("Test")
        for i in range(10):
            store.add_message(session_id, "user", f"Message {i}")
        
        messages = store.get_recent_messages(session_id, count=3)
        
        assert len(messages) == 3
        assert messages[0]["content"] == "Message 7"
        assert messages[2]["content"] == "Message 9"
        store.close()
    
    def test_export_session(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        session_id = store.create_session("Test")
        store.add_message(session_id, "user", "Hello")
        
        exported = store.export_session(session_id)
        
        assert exported["id"] == session_id
        assert exported["title"] == "Test"
        assert len(exported["messages"]) == 1
        store.close()
    
    def test_export_session_not_exists(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        exported = store.export_session("nonexistent")
        
        assert exported == {}
        store.close()
    
    def test_search_messages(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        session_id = store.create_session("Test")
        store.add_message(session_id, "user", "Hello world")
        store.add_message(session_id, "user", "Goodbye")
        
        results = store.search_messages("world")
        
        assert len(results) == 1
        assert results[0]["content"] == "Hello world"
        store.close()
    
    def test_search_messages_with_limit(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        session_id = store.create_session("Test")
        for i in range(5):
            store.add_message(session_id, "user", f"test message {i}")
        
        results = store.search_messages("test", limit=3)
        
        assert len(results) == 3
        store.close()
    
    def test_count_messages(self, tmp_path):
        from mdpilot.agent.session import SessionStore
        
        db_path = tmp_path / "test.db"
        store = SessionStore(db_path)
        
        session_id = store.create_session("Test")
        store.add_message(session_id, "user", "Message 1")
        store.add_message(session_id, "user", "Message 2")
        
        count = store._count_messages(session_id)
        
        assert count == 2
        store.close()
