"""Task model for SQLAlchemy."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, CheckConstraint, DateTime, Float, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mdpilot.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from mdpilot.database.models.chat import Chat


class Task(Base, TimestampMixin):
    """Task model.

    Represents a background task with status tracking and optional chat association.

    Attributes:
        id: Unique identifier for the task
        task_type: Type of task being executed (indexed for filtering)
        parameters: JSON parameters for the task (required)
        user_id: User who created the task (indexed for filtering)
        chat_id: Optional foreign key to associated chat session
        status: Current status of the task (pending, running, completed, failed, cancelled)
        result: Optional JSON result data when task completes
        error: Optional error message if task fails
        extra_data: Optional JSON data for extensibility (maps to API's metadata)
        created_at: Timestamp when the task was created (from TimestampMixin)
        updated_at: Timestamp when the task was last updated (from TimestampMixin)
        started_at: Optional timestamp when task execution started
        completed_at: Optional timestamp when task execution completed
        chat: Optional relationship to the associated chat session
    """

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    task_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    parameters: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    chat_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("chats.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        default="pending",
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    agent_session_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    progress_percentage: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        default=0.0,
    )
    current_stage: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationship to chat (optional)
    chat: Mapped["Chat | None"] = relationship(
        "Chat",
        back_populates="tasks",
    )

    # Constraints and indexes
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="valid_status",
        ),
        Index("ix_tasks_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        """String representation of Task."""
        return f"<Task(id={self.id}, task_type={self.task_type!r}, status={self.status!r}, user_id={self.user_id!r})>"
