"""Chat model for SQLAlchemy."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mdpilot.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from mdpilot.database.models.message import Message
    from mdpilot.database.models.task import Task


class Chat(Base, TimestampMixin):
    """Chat session model.

    Represents a chat session with associated messages.

    Attributes:
        id: Unique identifier for the chat session
        title: Title of the chat session (indexed for search)
        extra_data: Optional JSON data for extensibility
        created_at: Timestamp when the chat was created (from TimestampMixin)
        updated_at: Timestamp when the chat was last updated (from TimestampMixin)
        messages: Relationship to associated messages
    """

    __tablename__ = "chats"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # Relationship to messages
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="chat",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    # Relationship to tasks
    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="chat",
        order_by="Task.created_at",
    )

    # Indexes for query optimization
    __table_args__ = (
        Index("ix_chats_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        """String representation of Chat."""
        return f"<Chat(id={self.id}, title={self.title!r})>"
