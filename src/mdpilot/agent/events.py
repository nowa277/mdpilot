"""Event system — typed pub/sub for the ReAct loop."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


# ----------------------------------------------------------------------------------
# Predefined event types
# ----------------------------------------------------------------------------------

ITERATION_START = "iteration_start"
TOOL_CALL = "tool_call"
TOOL_RESULT = "tool_result"
LLM_RESPONSE = "llm_response"
LOOP_END = "loop_end"
ERROR = "error"
PROGRESS_UPDATE = "progress_update"

# Parallel execution events
PARALLEL_WAVE_START = "parallel.wave_start"
PARALLEL_WAVE_COMPLETE = "parallel.wave_complete"
PARALLEL_TOOL_START = "parallel.tool_start"
PARALLEL_TOOL_COMPLETE = "parallel.tool_complete"
PARALLEL_TOOL_ERROR = "parallel.tool_error"

# High-level orchestrator events (for frontend consumption)
TOOL_STARTED = "tool_started"
TOOL_RUNNING = "tool_running"
TOOL_COMPLETED = "tool_completed"
TOOL_FAILED = "tool_failed"


# ----------------------------------------------------------------------------------
# Event dataclass
# ----------------------------------------------------------------------------------

@dataclass
class Event:
    """A single typed event emitted by the ReAct loop.

    Attributes
    ----------
    type : str
        Event type identifier (e.g. ``"tool_call"``).
    data : dict
        Arbitrary payload associated with the event.
    timestamp : float
        Unix timestamp when the event was created.
    """

    type: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


# ----------------------------------------------------------------------------------
# EventEmitter
# ----------------------------------------------------------------------------------

class EventEmitter:
    """Minimal synchronous pub/sub event emitter.

    Example::

        emitter = EventEmitter()
        emitter.on("tool_call", lambda e: print(e.data))
        emitter.emit("tool_call", tool_name="bash", args={})
        emitter.off("tool_call", my_callback)
    """

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable[[Event], None]]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def on(
        self,
        event_type: str,
        callback: Callable[[Event], None],
    ) -> Callable[[], None]:
        """Register *callback* for *event_type*.

        Returns a no-argument function that deregisters the callback.
        """
        self._listeners.setdefault(event_type, []).append(callback)
        return lambda: self.off(event_type, callback)

    def off(
        self,
        event_type: str,
        callback: Callable[[Event], None],
    ) -> None:
        """Remove *callback* from the *event_type* listener list."""
        self._listeners.get(event_type, []).remove(callback)

    def emit(self, event_type: str, **data: Any) -> None:
        """Fire all callbacks registered for *event_type*.

        Parameters
        ----------
        event_type : str
            The event type string.
        **data : Any
            Keyword arguments become ``Event.data``.
        """
        event = Event(type=event_type, data=data)
        for listener in self._listeners.get(event_type, []):
            listener(event)

    def once(
        self,
        event_type: str,
        callback: Callable[[Event], None],
    ) -> None:
        """Register a callback that fires at most once, then self-deregisters."""
        def wrapper(event: Event) -> None:
            self.off(event_type, wrapper)
            callback(event)

        self.on(event_type, wrapper)
