"""Rich-based progress display manager."""

from __future__ import annotations

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from mdpilot.ui.progress_tracker import STAGE_INFO_MAP, TaskProgressTracker


class RichProgressManager:
    """Manages Rich progress display for multiple tasks."""
    
    def __init__(self, tracker: TaskProgressTracker):
        self.tracker = tracker
        self.console = Console()
        self.progress: Progress | None = None
        self._rich_tasks: dict[str, TaskID] = {}
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False
    
    def start(self) -> None:
        """Start the progress display."""
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            TimeElapsedColumn(),
            console=self.console
        )
        self.progress.start()
    
    def stop(self) -> None:
        """Stop the progress display."""
        if self.progress:
            self.progress.stop()
            self.progress = None
    
    def refresh(self) -> None:
        """Refresh the progress display with current tracker state."""
        if not self.progress:
            return
        
        all_tasks = self.tracker.get_all_tasks()
        
        for task_id, task_progress in all_tasks.items():
            stage_info = STAGE_INFO_MAP.get(task_progress.stage)
            if not stage_info:
                continue
            
            description = (
                f"[{stage_info.color}]{stage_info.icon} "
                f"{task_progress.message}[/{stage_info.color}]"
            )
            
            if task_id not in self._rich_tasks:
                self._rich_tasks[task_id] = self.progress.add_task(
                    description,
                    total=100
                )
            
            self.progress.update(
                self._rich_tasks[task_id],
                description=description,
                completed=task_progress.percent
            )
