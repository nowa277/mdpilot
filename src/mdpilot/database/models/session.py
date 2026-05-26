"""Agent session model for persistence."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from mdpilot.database.base import Base, TimestampMixin


class AgentSession(Base, TimestampMixin):
    """Agent session model for persisting ReActLoop state.
    
    Stores conversation context and budget state to enable session recovery
    after server restart.
    
    Attributes:
        id: Unique session identifier (UUID string)
        context_messages: JSON array of conversation messages
        system_prompt: Current system prompt text
        iteration_count: Current iteration number
        max_iterations: Maximum allowed iterations
        created_at: Timestamp when session was created (from TimestampMixin)
        updated_at: Timestamp when session was last updated (from TimestampMixin)
    """

    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    context_messages: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    system_prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    iteration_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    max_iterations: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
