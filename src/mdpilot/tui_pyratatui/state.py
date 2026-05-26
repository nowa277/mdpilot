"""
State management for MDPilot TUI.

Uses Pydantic models for type-safe state management.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from mdpilot.config.loader import load_config


class Message(BaseModel):
    """
    Chat message model.
    
    Attributes:
        role: Message role ('user' or 'assistant')
        content: Message content text
        timestamp: Message creation timestamp
    """
    model_config = ConfigDict(frozen=False)
    
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)


class StreamingState(BaseModel):
    """
    LLM streaming state.
    
    Attributes:
        is_streaming: Whether currently receiving streamed response
        current_chunk: Current streaming chunk being received
        buffer: Accumulated streaming buffer
    """
    model_config = ConfigDict(frozen=False)
    
    is_streaming: bool = False
    current_chunk: str = ""
    buffer: str = ""


class UIState(BaseModel):
    """
    UI component state.
    
    Attributes:
        show_welcome: Whether to show welcome panel
        input_buffer: Current input text buffer
        scroll_offset: Messages area scroll offset
        cursor_position: Input cursor position
    """
    model_config = ConfigDict(frozen=False)
    
    show_welcome: bool = True
    input_buffer: str = ""
    scroll_offset: int = 0
    cursor_position: int = 0


class AppState(BaseModel):
    """
    Global application state.
    
    Central state container for the entire TUI application.
    
    Attributes:
        messages: List of chat messages
        streaming: LLM streaming state
        ui: UI component state
        connected: WebSocket connection status
        session_id: Current chat session ID
        model_name: LLM model name
        tokens_used: Total tokens used in session
    """
    model_config = ConfigDict(frozen=False, arbitrary_types_allowed=True)
    
    messages: List[Message] = Field(default_factory=list)
    streaming: StreamingState = Field(default_factory=StreamingState)
    ui: UIState = Field(default_factory=UIState)
    connected: bool = False
    session_id: Optional[str] = None
    model_name: str = Field(default_factory=lambda: load_config().provider.model)
    tokens_used: int = 0
