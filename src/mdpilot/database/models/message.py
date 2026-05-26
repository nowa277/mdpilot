"""Message model for SQLAlchemy."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mdpilot.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from mdpilot.database.models.chat import Chat


class Message(Base, TimestampMixin):
    """Message model.

    Represents a single message within a chat session.

    Attributes:
        id: Unique identifier for the message
        chat_id: Foreign key to the parent chat session
        role: Role of the message sender (user, assistant, or system)
        content: The message content
        extra_data: Optional JSON data for extensibility
        created_at: Timestamp when the message was created (from TimestampMixin)
        updated_at: Timestamp when the message was last updated (from TimestampMixin)
        chat: Relationship to the parent chat session
    """

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    chat_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # Relationship to chat
    chat: Mapped["Chat"] = relationship(
        "Chat",
        back_populates="messages",
    )

    # Constraints and indexes
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant', 'system')",
            name="valid_role",
        ),
        Index("ix_messages_chat_id_created_at", "chat_id", "created_at"),
    )

    def __repr__(self) -> str:
        """String representation of Message."""
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<Message(id={self.id}, chat_id={self.chat_id}, role={self.role!r}, content={content_preview!r})>"
