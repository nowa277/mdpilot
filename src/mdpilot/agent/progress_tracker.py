"""Progress tracking for parallel tool execution."""

from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Optional

from mdpilot.agent.dependency_graph import ExecutionWave
from mdpilot.agent.events import (
    PARALLEL_TOOL_COMPLETE,
    PARALLEL_TOOL_ERROR,
    PARALLEL_TOOL_START,
    PARALLEL_WAVE_COMPLETE,
    PARALLEL_WAVE_START,
    Event,
)


@dataclass
class ToolProgress:
    """Progress information for a single tool."""

    tool_id: str
    status: str  # "pending", "running", "completed", "failed"
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error: Optional[str] = None


class ProgressTracker:
    """Tracks progress of parallel tool execution and iteration progress."""

    def __init__(self, total_tools: int = 0, total_steps: Optional[int] = None):
        """Initialize progress tracker.

        Args:
            total_tools: Total number of tools to track (for parallel execution)
            total_steps: Total number of steps/iterations (for overall progress)
        """
        self._total_tools = total_tools
        self._completed_tools = 0
        self._failed_tools = 0
        self._tool_progress: dict[str, ToolProgress] = {}
        self._lock = Lock()
        
        # Iteration progress tracking
        self._total_steps = total_steps
        self._current_step = 0
        self._stage = "initializing"

    def start_wave(self, wave: ExecutionWave) -> Event:
        """Record wave start and return event.

        Args:
            wave: The execution wave starting

        Returns:
            Event for wave start
        """
        return Event(
            type=PARALLEL_WAVE_START,
            data={
                "wave_id": wave.wave_id,
                "tool_count": len(wave.tools),
                "tool_ids": [node.tool_call.id for node in wave.tools],
            },
        )

    def start_tool(self, tool_id: str) -> Event:
        """Record tool start and return event.

        Args:
            tool_id: ID of the tool starting

        Returns:
            Event for tool start
        """
        with self._lock:
            self._tool_progress[tool_id] = ToolProgress(
                tool_id=tool_id, status="running", start_time=datetime.now()
            )

        return Event(
            type=PARALLEL_TOOL_START,
            data={"tool_id": tool_id, "progress": self.get_progress()},
        )

    def complete_tool(self, tool_id: str) -> Event:
        """Record tool completion and return event.

        Args:
            tool_id: ID of the tool completing

        Returns:
            Event for tool completion
        """
        with self._lock:
            if tool_id in self._tool_progress:
                self._tool_progress[tool_id].status = "completed"
                self._tool_progress[tool_id].end_time = datetime.now()
            self._completed_tools += 1

        return Event(
            type=PARALLEL_TOOL_COMPLETE,
            data={"tool_id": tool_id, "progress": self.get_progress()},
        )

    def fail_tool(self, tool_id: str, error: str) -> Event:
        """Record tool failure and return event.

        Args:
            tool_id: ID of the tool failing
            error: Error message

        Returns:
            Event for tool failure
        """
        with self._lock:
            if tool_id in self._tool_progress:
                self._tool_progress[tool_id].status = "failed"
                self._tool_progress[tool_id].end_time = datetime.now()
                self._tool_progress[tool_id].error = error
            self._failed_tools += 1

        return Event(
            type=PARALLEL_TOOL_ERROR,
            data={"tool_id": tool_id, "error": error, "progress": self.get_progress()},
        )

    def complete_wave(self, wave: ExecutionWave) -> Event:
        """Record wave completion and return event.

        Args:
            wave: The execution wave completing

        Returns:
            Event for wave completion
        """
        return Event(
            type=PARALLEL_WAVE_COMPLETE,
            data={
                "wave_id": wave.wave_id,
                "tool_count": len(wave.tools),
                "progress": self.get_progress(),
            },
        )

    def get_progress(self) -> float:
        """Calculate progress percentage (0.0 to 1.0).

        Returns:
            Progress as a float between 0.0 and 1.0
        """
        if self._total_tools == 0:
            return 1.0
        return (self._completed_tools + self._failed_tools) / self._total_tools

    def update(self, step: int, stage: str) -> None:
        """Update current step and stage.
        
        Args:
            step: Current step number
            stage: Current stage description
        """
        with self._lock:
            self._current_step = step
            self._stage = stage

    @property
    def percentage(self) -> Optional[float]:
        """Calculate progress percentage.
        
        Returns:
            Progress percentage (0-100) or None if total_steps not set
        """
        with self._lock:
            if self._total_steps is None or self._total_steps == 0:
                return None
            return min(100.0, (self._current_step / self._total_steps) * 100)

    @property
    def stage(self) -> str:
        """Get current stage description.
        
        Returns:
            Current stage string
        """
        with self._lock:
            return self._stage
