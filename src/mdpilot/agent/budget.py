"""BudgetTracker — iteration guard for the ReAct loop."""

from __future__ import annotations


class BudgetTracker:
    """Tracks iteration count against hard limit.

    Parameters
    -------
    max_iterations : int
        Maximum number of ReAct loop iterations (user prompt → LLM → tools).
    """

    def __init__(self, max_iterations: int) -> None:
        self._max_iterations = max_iterations
        self._iteration = 0

    @property
    def iteration(self) -> int:
        """Current iteration count (1-based after first iteration)."""
        return self._iteration
    @property
    def remaining(self) -> int:
        """Return remaining iterations."""
        return max(0, self._max_iterations - self._iteration)

    def increment(self) -> None:
        """Advance the iteration counter by one."""
        self._iteration += 1

    def can_continue(self) -> bool:
        """Return ``True`` if iteration limit is within bounds."""
        return self._iteration < self._max_iterations
