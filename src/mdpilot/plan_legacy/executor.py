"""Plan executor — runs a Plan step by step with event emission."""

from __future__ import annotations

from typing import Any

from mdpilot.agent.events import EventEmitter
from mdpilot.plan_legacy.schema import Plan, PlanResult, PlanStep
from mdpilot.tools.dispatcher import ToolDispatcher
from mdpilot.types import ToolCall, ToolOutput


STEP_START = "step_start"
STEP_RESULT = "step_result"


class PlanExecutor:
    """Executes a Plan, emitting events for each step transition.

    Parameters
    ----------
    dispatcher : ToolDispatcher
        Dispatcher used to execute individual tool calls.
    events : EventEmitter
        Event emitter for publishing step lifecycle events.
    """

    def __init__(
        self,
        dispatcher: ToolDispatcher,
        events: EventEmitter,
    ) -> None:
        self._dispatcher = dispatcher
        self._events = events
        self._cancelled = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def cancel(self) -> None:
        """Request cancellation of the current execution.

        The executor will stop accepting new steps after the current one finishes.
        """
        self._cancelled = True

    async def execute(self, plan: Plan) -> PlanResult:
        """Execute all steps in a plan in dependency order.

        Parameters
        ----------
        plan : Plan
            The plan to execute.

        Returns
        -------
        PlanResult
            Outcome containing step results and overall success status.
        """
        results: dict[int, ToolOutput] = {}
        completed_ids: set[int] = set()

        for step in plan.steps:
            # Check cancellation before starting a new step
            if self._cancelled:
                return self._build_result(plan, results, success=False, error="Cancelled by user")

            # Check dependencies
            missing = [d for d in step.depends_on if d not in completed_ids]
            if missing:
                return self._build_result(
                    plan,
                    results,
                    success=False,
                    error=f"Step {step.id} has unmet dependencies: {missing}",
                )

            # Mark step as running
            step.status = "running"
            self._events.emit(
                STEP_START,
                step_id=step.id,
                description=step.description,
                tool=step.tool,
                arguments=step.arguments,
            )

            # Execute the tool
            tool_output = await self._execute_step(step)

            # Store result
            results[step.id] = tool_output

            # Update step status based on result
            if tool_output.success:
                step.status = "completed"
                completed_ids.add(step.id)
            else:
                step.status = "failed"
                self._events.emit(
                    STEP_RESULT,
                    step_id=step.id,
                    success=False,
                    output=tool_output.output,
                    error=tool_output.error,
                )
                return self._build_result(
                    plan,
                    results,
                    success=False,
                    error=f"Step {step.id} ({step.tool}) failed: {tool_output.error}",
                )

            self._events.emit(
                STEP_RESULT,
                step_id=step.id,
                success=True,
                output=tool_output.output,
            )

        return self._build_result(plan, results, success=True)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _execute_step(self, step: PlanStep) -> ToolOutput:
        """Execute a single step via the dispatcher."""
        call = ToolCall(
            id=f"plan-step-{step.id}",
            name=step.tool,
            arguments=step.arguments,
        )
        return await self._dispatcher.execute(call)

    def _build_result(
        self,
        plan: Plan,
        results: dict[int, ToolOutput],
        success: bool,
        error: str | None = None,
    ) -> PlanResult:
        """Build a PlanResult from the current execution state."""
        return PlanResult(plan=plan, results=results, success=success, error=error)
