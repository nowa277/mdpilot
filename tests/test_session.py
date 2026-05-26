"""Tests for Session persistence — SQLite-backed conversation history."""

from __future__ import annotations

from pathlib import Path

import pytest

from mdpilot.agent.session import SessionStore


@pytest.fixture()
def store(tmp_path: Path) -> SessionStore:
    """Create a SessionStore with a temp database."""
    db = tmp_path / "test_sessions.db"
    return SessionStore(db_path=str(db))


# ------------------------------------------------------------------ #
# Session CRUD
# ------------------------------------------------------------------ #

class TestSessionCRUD:
    def test_create_session(self, store: SessionStore):
        sid = store.create_session(title="Test Session")
        assert len(sid) == 12
        session = store.get_session(sid)
        assert session is not None
        assert session["title"] == "Test Session"

    def test_create_session_default_title(self, store: SessionStore):
        sid = store.create_session()
        session = store.get_session(sid)
        assert session["title"] == ""

    def test_list_sessions(self, store: SessionStore):
        s1 = store.create_session(title="First")
        s2 = store.create_session(title="Second")
        sessions = store.list_sessions()
        assert len(sessions) == 2
        # Newest first
        assert sessions[0]["title"] == "Second"

    def test_list_sessions_limit(self, store: SessionStore):
        for i in range(10):
            store.create_session(title=f"Session {i}")
        sessions = store.list_sessions(limit=3)
        assert len(sessions) == 3

    def test_delete_session(self, store: SessionStore):
        sid = store.create_session(title="Delete me")
        assert store.delete_session(sid) is True
        assert store.get_session(sid) is None

    def test_delete_nonexistent(self, store: SessionStore):
        assert store.delete_session("nonexistent") is False

    def test_update_title(self, store: SessionStore):
        sid = store.create_session(title="Old")
        store.update_session_title(sid, "New")
        session = store.get_session(sid)
        assert session["title"] == "New"

    def test_get_nonexistent(self, store: SessionStore):
        assert store.get_session("nonexistent") is None


# ------------------------------------------------------------------ #
# Message CRUD
# ------------------------------------------------------------------ #

class TestMessageCRUD:
    def test_add_message(self, store: SessionStore):
        sid = store.create_session()
        msg_id = store.add_message(sid, "user", "Hello")
        assert msg_id > 0

    def test_get_messages(self, store: SessionStore):
        sid = store.create_session()
        store.add_message(sid, "user", "Hello")
        store.add_message(sid, "assistant", "Hi there")
        store.add_message(sid, "user", "How are you?")
        messages = store.get_messages(sid)
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[1]["content"] == "Hi there"

    def test_get_messages_with_tool_calls(self, store: SessionStore):
        sid = store.create_session()
        store.add_message(
            sid, "assistant", "Running tool",
            tool_calls=[{"id": "tc1", "name": "bash_run", "arguments": {"cmd": "ls"}}],
        )
        store.add_message(
            sid, "tool", "file1.txt\nfile2.txt",
            tool_call_id="tc1",
        )
        messages = store.get_messages(sid)
        assert len(messages) == 2
        assert messages[0]["tool_calls"] is not None
        assert messages[0]["tool_calls"][0]["name"] == "bash_run"
        assert messages[1]["tool_call_id"] == "tc1"

    def test_get_recent_messages(self, store: SessionStore):
        sid = store.create_session()
        for i in range(20):
            store.add_message(sid, "user", f"Message {i}")
        recent = store.get_recent_messages(sid, count=5)
        assert len(recent) == 5
        assert "Message 19" in recent[-1]["content"]

    def test_message_count(self, store: SessionStore):
        sid = store.create_session()
        store.add_message(sid, "user", "msg1")
        store.add_message(sid, "assistant", "msg2")
        session = store.get_session(sid)
        assert session["message_count"] == 2


# ------------------------------------------------------------------ #
# Search
# ------------------------------------------------------------------ #

class TestSearch:
    def test_search_messages(self, store: SessionStore):
        sid = store.create_session(title="MD Session")
        store.add_message(sid, "user", "How to run MD simulation with sander?")
        store.add_message(sid, "assistant", "Use sander -O -i min.in ...")
        store.add_message(sid, "user", "What force field for DNA?")

        results = store.search_messages("sander")
        assert len(results) >= 1
        assert any("sander" in r["content"].lower() for r in results)

    def test_search_no_results(self, store: SessionStore):
        sid = store.create_session()
        store.add_message(sid, "user", "Hello")
        results = store.search_messages("quantum")
        assert len(results) == 0


# ------------------------------------------------------------------ #
# Export
# ------------------------------------------------------------------ #

class TestExport:
    def test_export_session(self, store: SessionStore):
        sid = store.create_session(title="Export Test")
        store.add_message(sid, "user", "Hello")
        store.add_message(sid, "assistant", "Hi")
        exported = store.export_session(sid)
        assert exported["title"] == "Export Test"
        assert len(exported["messages"]) == 2

    def test_export_nonexistent(self, store: SessionStore):
        exported = store.export_session("nonexistent")
        assert exported == {}


# ------------------------------------------------------------------ #
# Lifecycle
# ------------------------------------------------------------------ #

class TestLifecycle:
    def test_close(self, store: SessionStore):
        store.close()
        # Should be able to reopen
        store._get_conn()
        sid = store.create_session()
        assert sid is not None

    def test_db_directory_created(self, tmp_path: Path):
        db = tmp_path / "subdir" / "deep" / "test.db"
        s = SessionStore(db_path=str(db))
        sid = s.create_session()
        assert sid is not None
        assert db.exists()
