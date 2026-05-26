"""Progress tracking data models for task execution."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

from mdpilot.types import ProgressStage, TaskProgress


@dataclass
class StageInfo:
    """Information about a progress stage."""
    name: str
    description: str
    icon: str
    color: str


STAGE_INFO_MAP: dict[ProgressStage, StageInfo] = {
    ProgressStage.QUEUED: StageInfo(
        name="Queued",
        description="Task queued for execution",
        icon="⏳",
        color="yellow"
    ),
    ProgressStage.PREPARING: StageInfo(
        name="Preparing",
        description="Preparing task environment",
        icon="📦",
        color="cyan"
    ),
    ProgressStage.RUNNING: StageInfo(
        name="Running",
        description="Task is running",
        icon="🔄",
        color="blue"
    ),
    ProgressStage.EXECUTING: StageInfo(
        name="Executing",
        description="Executing main task",
        icon="⚙️",
        color="blue"
    ),
    ProgressStage.PROCESSING: StageInfo(
        name="Processing",
        description="Processing results",
        icon="🔧",
        color="magenta"
    ),
    ProgressStage.PARSING: StageInfo(
        name="Parsing",
        description="Parsing output",
        icon="📝",
        color="magenta"
    ),
    ProgressStage.COMPLETED: StageInfo(
        name="Completed",
        description="Task completed successfully",
        icon="✓",
        color="green"
    ),
    ProgressStage.FAILED: StageInfo(
        name="Failed",
        description="Task failed",
        icon="✗",
        color="red"
    ),
    ProgressStage.TIMEOUT: StageInfo(
        name="Timeout",
        description="Task timed out",
        icon="⏱",
        color="red"
    ),
}


class TaskProgressTracker:
    """Thread-safe tracker for multiple task progress states."""
    
    def __init__(self):
        self._tasks: dict[str, TaskProgress] = {}
        self._lock = Lock()
    
    def add_task(self, task_id: str, title: str, total_steps: int) -> None:
        """Add a new task to track."""
        from datetime import datetime
        
        with self._lock:
            self._tasks[task_id] = TaskProgress(
                task_id=task_id,
                stage=ProgressStage.QUEUED,
                current_step=0,
                total_steps=total_steps,
                percent=0,
                message=title,
                timestamp=datetime.now()
            )
    
    def update_progress(self, task_id: str, progress: TaskProgress) -> None:
        """Update progress for a task."""
        with self._lock:
            self._tasks[task_id] = progress
    
    def get_progress(self, task_id: str) -> TaskProgress | None:
        """Get current progress for a task."""
        with self._lock:
            return self._tasks.get(task_id)
    
    def remove_task(self, task_id: str) -> None:
        """Remove a task from tracking."""
        with self._lock:
            self._tasks.pop(task_id, None)
    
    def get_all_tasks(self) -> dict[str, TaskProgress]:
        """Get all tracked tasks."""
        with self._lock:
            return self._tasks.copy()
