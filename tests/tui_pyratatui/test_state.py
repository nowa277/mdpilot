"""Tests for state management."""
import pytest
from mdpilot.tui_pyratatui.state import Message, StreamingState, UIState, AppState


def test_message_creation():
    """Test Message model creation."""
    msg = Message(role="user", content="Hello")
    
    assert msg.role == "user"
    assert msg.content == "Hello"
    assert msg.timestamp is not None


def test_message_assistant():
    """Test assistant message creation."""
    msg = Message(role="assistant", content="Hi there")
    
    assert msg.role == "assistant"
    assert msg.content == "Hi there"


def test_streaming_state():
    """Test StreamingState model."""
    state = StreamingState(is_streaming=True, current_chunk="test")
    
    assert state.is_streaming is True
    assert state.current_chunk == "test"


def test_ui_state():
    """Test UIState model."""
    ui = UIState(show_welcome=True, input_buffer="test input")
    
    assert ui.show_welcome is True
    assert ui.input_buffer == "test input"


def test_app_state_initialization():
    """Test AppState initializes with defaults."""
    state = AppState()
    
    assert state.messages == []
    assert state.streaming.is_streaming is False
    assert state.ui.show_welcome is True
    assert state.ui.input_buffer == ""


def test_app_state_add_message():
    """Test adding messages to AppState."""
    state = AppState()
    
    msg = Message(role="user", content="Test")
    state.messages.append(msg)
    
    assert len(state.messages) == 1
    assert state.messages[0].content == "Test"


def test_app_state_connection():
    """Test connection state tracking."""
    state = AppState()
    
    assert hasattr(state, 'connected')
    assert isinstance(state.connected, bool)
