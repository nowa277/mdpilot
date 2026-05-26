"""Integration tests for MDPilot TUI."""
import pytest
from mdpilot.tui_pyratatui.state import AppState, Message
from mdpilot.tui_pyratatui.theme import Theme
from mdpilot.tui_pyratatui.components.welcome_panel import WelcomePanel
from mdpilot.tui_pyratatui.components.messages_area import MessagesArea
from mdpilot.tui_pyratatui.components.input_area import InputArea
from mdpilot.tui_pyratatui.components.footer import Footer


def test_full_app_initialization():
    """Test full app initialization with all components."""
    state = AppState()
    theme = Theme()
    
    # Initialize all components
    welcome = WelcomePanel(state, theme)
    messages = MessagesArea(state, theme)
    input_area = InputArea(state, theme)
    footer = Footer(state, theme)
    
    # Verify components initialized
    assert welcome.state is state
    assert welcome.theme is theme
    assert messages.state is state
    assert input_area.state is state
    assert footer.state is state


def test_component_state_sharing():
    """Test components share the same state instance."""
    state = AppState()
    theme = Theme()
    
    welcome = WelcomePanel(state, theme)
    input_area = InputArea(state, theme)
    
    # Modify state via one component
    state.ui.input_buffer = "test"
    
    # Verify other component sees the change
    assert input_area.state.ui.input_buffer == "test"
    assert welcome.state.ui.input_buffer == "test"


def test_message_flow():
    """Test message creation and storage."""
    state = AppState()
    theme = Theme()
    input_area = InputArea(state, theme)
    
    # Simulate user input
    state.ui.input_buffer = "Hello"
    input_area._send_message()
    
    # Verify message was created
    assert len(state.messages) == 1
    assert state.messages[0].role == "user"
    assert state.messages[0].content == "Hello"
    
    # Verify input was cleared
    assert state.ui.input_buffer == ""


def test_welcome_panel_toggle():
    """Test welcome panel visibility toggle."""
    state = AppState()
    theme = Theme()
    welcome = WelcomePanel(state, theme)
    
    # Initial state
    assert state.ui.show_welcome is True
    
    # Simulate Tab key event
    class MockEvent:
        code = "tab"
    
    handled = welcome.handle_event(MockEvent())
    
    # Verify toggle
    assert handled is True
    assert state.ui.show_welcome is False
    
    # Toggle again
    welcome.handle_event(MockEvent())
    assert state.ui.show_welcome is True


def test_input_handling():
    """Test input area keyboard handling."""
    state = AppState()
    theme = Theme()
    input_area = InputArea(state, theme)
    
    # Simulate typing
    class CharEvent:
        code = "char"
        char = "a"
    
    input_area.handle_event(CharEvent())
    assert state.ui.input_buffer == "a"
    
    # Simulate backspace
    class BackspaceEvent:
        code = "backspace"
    
    input_area.handle_event(BackspaceEvent())
    assert state.ui.input_buffer == ""


def test_state_updates():
    """Test state updates propagate correctly."""
    state = AppState()
    
    # Add messages
    msg1 = Message(role="user", content="Hello")
    msg2 = Message(role="assistant", content="Hi")
    state.messages.append(msg1)
    state.messages.append(msg2)
    
    assert len(state.messages) == 2
    assert state.messages[0].role == "user"
    assert state.messages[1].role == "assistant"


def test_connection_state():
    """Test connection state tracking."""
    state = AppState()
    
    # Initial state
    assert state.connected is False
    
    # Simulate connection
    state.connected = True
    assert state.connected is True


def test_token_tracking():
    """Test token usage tracking."""
    state = AppState()
    
    # Initial tokens
    assert state.tokens_used == 0
    
    # Update tokens
    state.tokens_used = 1234
    assert state.tokens_used == 1234
