"""Chat models."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ChatSessionCreate(BaseModel):
    """Request model for creating a chat session."""

    user_id: str
    metadata: Optional[dict[str, Any]] = None


class ChatSession(BaseModel):
    """Chat session model."""

    session_id: str
    user_id: str
    status: str = "active"
    created_at: datetime
    metadata: Optional[dict[str, Any]] = None


class MessageCreate(BaseModel):
    """Request model for creating a message."""

    content: str
    role: str = Field(..., pattern="^(user|assistant|system)$")


class Message(BaseModel):
    """Message model."""

    message_id: str
    session_id: str
    content: str
    role: str
    created_at: datetime


class MessageHistory(BaseModel):
    """Message history response."""

    messages: list[Message]
    total: int
    limit: int
    offset: int
