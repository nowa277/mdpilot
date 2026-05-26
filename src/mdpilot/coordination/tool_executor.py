"""Tool execution with runtime guards."""

from typing import Any, Dict

from mdpilot.coordination.resource_guard import ResourceGuard
from mdpilot.coordination.types import (
    ExecutionResult,
    ExecutionSequence,
    ExecutionStatus,
    ResultStatus,
    ToolCall,
    ToolResult,
)


class ToolExecutor:
    """Executes tool sequences with runtime monitoring."""

    def __init__(self, tool_dispatcher: Any, resource_guard: ResourceGuard):
        """Initialize tool executor.

        Args:
            tool_dispatcher: Dispatcher for tool execution
            resource_guard: Runtime resource monitor
        """
        self.dispatcher = tool_dispatcher
        self.guard = resource_guard

    async def execute(self, sequence: ExecutionSequence) -> ExecutionResult:
        """Execute tool call sequence.

        Args:
            sequence: Sequence of tool calls to execute

        Returns:
            ExecutionResult with results from all tools
        """
        results = []

        for tool_call in sequence.calls:
            # Check resources
            if not self.guard.check_available(tool_call):
                return ExecutionResult(
                    sequence_id=sequence.plan_id,
                    status=ExecutionStatus.RESOURCE_EXHAUSTED,
                    results=results,
                    error="Insufficient resources for tool execution"
                )

            # Execute tool
            result = await self._execute_single(tool_call)
            results.append(result)

            # Stop on failure
            if result.status == ResultStatus.FAILED:
                return ExecutionResult(
                    sequence_id=sequence.plan_id,
                    status=ExecutionStatus.FAILED,
                    results=results,
                    error=result.error
                )

        # All succeeded
        return ExecutionResult(
            sequence_id=sequence.plan_id,
            status=ExecutionStatus.SUCCESS,
            results=results
        )

    async def _execute_single(self, tool_call: ToolCall) -> ToolResult:
        """Execute single tool call with monitoring.

        Args:
            tool_call: Tool call to execute

        Returns:
            ToolResult with execution outcome
        """
        try:
            # Execute tool
            output = await self._execute_tool(tool_call)

            # Record resource usage (simulated for now)
            actual_usage = self._measure_usage(tool_call, output)
            self.guard.record_usage(tool_call, actual_usage)

            return ToolResult(
                status=ResultStatus.SUCCESS,
                output=output,
                message=f"Tool {tool_call.tool_name} completed successfully"
            )
        except Exception as e:
            return self._handle_error(e, tool_call)

    async def _execute_tool(self, tool_call: ToolCall) -> Any:
        """Execute tool via dispatcher.

        Args:
            tool_call: Tool call to execute

        Returns:
            Tool output
        """
        if self.dispatcher:
            return await self.dispatcher.dispatch(tool_call.tool_name, tool_call.parameters)
        # Simulated execution for testing
        return {"status": "simulated", "tool": tool_call.tool_name}

    def _handle_error(self, error: Exception, tool_call: ToolCall) -> ToolResult:
        """Handle tool execution error.

        Args:
            error: Exception that occurred
            tool_call: Tool call that failed

        Returns:
            ToolResult with error information
        """
        return ToolResult(
            status=ResultStatus.FAILED,
            error=str(error),
            message=f"Tool {tool_call.tool_name} failed: {str(error)}"
        )

    def _measure_usage(self, tool_call: ToolCall, output: Any) -> Dict[str, float]:
        """Measure actual resource usage.

        Args:
            tool_call: Tool call that was executed
            output: Tool output

        Returns:
            Actual resource usage
        """
        # Simplified measurement - in production would use actual metrics
        base_usage = {
            "cpu_hours": 0.05,
            "memory_gb": 0.5,
            "disk_gb": 0.1
        }

        # Adjust based on tool type
        if tool_call.tool_name in ["minimize", "equilibrate", "production"]:
            base_usage["cpu_hours"] *= 2
            base_usage["memory_gb"] *= 2

        return base_usage
