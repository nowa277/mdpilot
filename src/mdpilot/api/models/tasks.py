"""Task models."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class TaskCreate(BaseModel):
    """Request model for creating a task."""

    task_type: str
    parameters: dict[str, Any]
    user_id: str
    metadata: Optional[dict[str, Any]] = None


class Task(BaseModel):
    """Task model."""

    task_id: str
    task_type: str
    parameters: dict[str, Any]
    user_id: str
    status: str = "pending"
    created_at: datetime
    updated_at: datetime
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class TaskList(BaseModel):
    """Task list response."""

    tasks: list[Task]
    total: int
    limit: int
    offset: int
