"""Tests for ToolExecutor."""

import pytest

from mdpilot.coordination.config import ResourceLimits
from mdpilot.coordination.resource_guard import ResourceGuard
from mdpilot.coordination.tool_executor import ToolExecutor
from mdpilot.coordination.types import (
    ExecutionSequence,
    ExecutionStatus,
    ResultStatus,
    ToolCall,
)


class MockDispatcher:
    """Mock tool dispatcher for testing."""

    def __init__(self, should_fail=False, fail_on_tool=None):
        self.should_fail = should_fail
        self.fail_on_tool = fail_on_tool
        self.calls = []

    async def dispatch(self, tool_name: str, parameters: dict):
        """Mock dispatch method."""
        self.calls.append((tool_name, parameters))

        if self.should_fail or (self.fail_on_tool and tool_name == self.fail_on_tool):
            raise RuntimeError(f"Tool {tool_name} failed")

        return {"status": "success", "tool": tool_name, "params": parameters}


class TestToolExecutor:
    """Test ToolExecutor functionality."""

    @pytest.mark.asyncio
    async def test_init(self):
        """Test ToolExecutor initialization."""
        dispatcher = MockDispatcher()
        limits = ResourceLimits()
        guard = ResourceGuard(limits)
        executor = ToolExecutor(dispatcher, guard)

        assert executor.dispatcher == dispatcher
        assert executor.guard == guard

    @pytest.mark.asyncio
    async def test_execute_single_tool(self):
        """Test executing a single tool."""
        dispatcher = MockDispatcher()
        limits = ResourceLimits()
        guard = ResourceGuard(limits)
        executor = ToolExecutor(dispatcher, guard)

        sequence = ExecutionSequence(
            plan_id="test-plan",
            calls=[ToolCall(tool_name="minimize", parameters={"steps": 1000})]
        )

        result = await executor.execute(sequence)

        assert result.status == ExecutionStatus.SUCCESS
        assert len(result.results) == 1
        assert result.results[0].status == ResultStatus.SUCCESS
        assert result.results[0].output["tool"] == "minimize"

    @pytest.mark.asyncio
    async def test_execute_multiple_tools(self):
        """Test executing multiple tools in sequence."""
        dispatcher = MockDispatcher()
        limits = ResourceLimits()
        guard = ResourceGuard(limits)
        executor = ToolExecutor(dispatcher, guard)

        sequence = ExecutionSequence(
            plan_id="test-plan",
            calls=[
                ToolCall(tool_name="minimize", parameters={"steps": 1000}),
                ToolCall(tool_name="equilibrate", parameters={"steps": 5000}),
                ToolCall(tool_name="analyze", parameters={"trajectory": "prod.nc"}),
            ]
        )

        result = await executor.execute(sequence)

        assert result.status == ExecutionStatus.SUCCESS
        assert len(result.results) == 3
        assert all(r.status == ResultStatus.SUCCESS for r in result.results)
        assert len(dispatcher.calls) == 3

    @pytest.mark.asyncio
    async def test_execute_resource_exhausted(self):
        """Test execution stops when resources exhausted."""
        dispatcher = MockDispatcher()
        limits = ResourceLimits(max_cpu_hours=1.0, max_memory_gb=4.0, max_disk_gb=2.0)
        guard = ResourceGuard(limits)
        executor = ToolExecutor(dispatcher, guard)

        # Use up resources
        guard.current_usage["memory_gb"] = 3.0

        sequence = ExecutionSequence(
            plan_id="test-plan",
            calls=[
                ToolCall(tool_name="minimize", parameters={}),  # Needs 2GB
            ]
        )

        result = await executor.execute(sequence)

        assert result.status == ExecutionStatus.RESOURCE_EXHAUSTED
        assert "Insufficient resources" in result.error
        assert len(result.results) == 0

    @pytest.mark.asyncio
    async def test_execute_tool_failure(self):
        """Test execution stops on tool failure."""
        dispatcher = MockDispatcher(should_fail=True)
        limits = ResourceLimits()
        guard = ResourceGuard(limits)
        executor = ToolExecutor(dispatcher, guard)

        sequence = ExecutionSequence(
            plan_id="test-plan",
            calls=[
                ToolCall(tool_name="minimize", parameters={}),
            ]
        )

        result = await executor.execute(sequence)

        assert result.status == ExecutionStatus.FAILED
        assert len(result.results) == 1
        assert result.results[0].status == ResultStatus.FAILED
        assert "failed" in result.results[0].error

    @pytest.mark.asyncio
    async def test_execute_partial_failure(self):
        """Test execution stops after first failure."""
        dispatcher = MockDispatcher(fail_on_tool="equilibrate")
        limits = ResourceLimits()
        guard = ResourceGuard(limits)
        executor = ToolExecutor(dispatcher, guard)

        sequence = ExecutionSequence(
            plan_id="test-plan",
            calls=[
                ToolCall(tool_name="minimize", parameters={}),
                ToolCall(tool_name="equilibrate", parameters={}),
                ToolCall(tool_name="analyze", parameters={}),
            ]
        )

        result = await executor.execute(sequence)

        assert result.status == ExecutionStatus.FAILED
        assert len(result.results) == 2  # Only first two executed
        assert result.results[0].status == ResultStatus.SUCCESS
        assert result.results[1].status == ResultStatus.FAILED
        assert len(dispatcher.calls) == 2  # Third tool not called

    @pytest.mark.asyncio
    async def test_execute_empty_sequence(self):
        """Test executing empty sequence."""
        dispatcher = MockDispatcher()
        limits = ResourceLimits()
        guard = ResourceGuard(limits)
        executor = ToolExecutor(dispatcher, guard)

        sequence = ExecutionSequence(plan_id="test-plan", calls=[])

        result = await executor.execute(sequence)

        assert result.status == ExecutionStatus.SUCCESS
        assert len(result.results) == 0

    @pytest.mark.asyncio
    async def test_execute_records_usage(self):
        """Test that execution records resource usage."""
        dispatcher = MockDispatcher()
        limits = ResourceLimits()
        guard = ResourceGuard(limits)
        executor = ToolExecutor(dispatcher, guard)

        initial_usage = guard.get_current_usage()

        sequence = ExecutionSequence(
            plan_id="test-plan",
            calls=[ToolCall(tool_name="minimize", parameters={})]
        )

        await executor.execute(sequence)

        final_usage = guard.get_current_usage()

        # Usage should have increased
        assert final_usage["cpu_hours"] > initial_usage["cpu_hours"]
        assert final_usage["memory_gb"] > initial_usage["memory_gb"]

    @pytest.mark.asyncio
    async def test_execute_without_dispatcher(self):
        """Test execution without dispatcher (simulated mode)."""
        limits = ResourceLimits()
        guard = ResourceGuard(limits)
        executor = ToolExecutor(None, guard)

        sequence = ExecutionSequence(
            plan_id="test-plan",
            calls=[ToolCall(tool_name="minimize", parameters={})]
        )

        result = await executor.execute(sequence)

        assert result.status == ExecutionStatus.SUCCESS
        assert len(result.results) == 1
        assert result.results[0].output["status"] == "simulated"

    @pytest.mark.asyncio
    async def test_execute_single_with_metadata(self):
        """Test executing tool with metadata."""
        dispatcher = MockDispatcher()
        limits = ResourceLimits()
        guard = ResourceGuard(limits)
        executor = ToolExecutor(dispatcher, guard)

        tool_call = ToolCall(
            tool_name="minimize",
            parameters={"steps": 1000},
            metadata={"priority": "high"}
        )

        result = await executor._execute_single(tool_call)

        assert result.status == ResultStatus.SUCCESS
        assert "completed successfully" in result.message

    @pytest.mark.asyncio
    async def test_handle_error(self):
        """Test error handling."""
        dispatcher = MockDispatcher()
        limits = ResourceLimits()
        guard = ResourceGuard(limits)
        executor = ToolExecutor(dispatcher, guard)

        tool_call = ToolCall(tool_name="minimize", parameters={})
        error = RuntimeError("Test error")

        result = executor._handle_error(error, tool_call)

        assert result.status == ResultStatus.FAILED
        assert "Test error" in result.error
        assert "failed" in result.message

    @pytest.mark.asyncio
    async def test_measure_usage_default(self):
        """Test measuring usage for default tool."""
        dispatcher = MockDispatcher()
        limits = ResourceLimits()
        guard = ResourceGuard(limits)
        executor = ToolExecutor(dispatcher, guard)

        tool_call = ToolCall(tool_name="analyze", parameters={})
        output = {"status": "success"}

        usage = executor._measure_usage(tool_call, output)

        assert usage["cpu_hours"] == 0.05
        assert usage["memory_gb"] == 0.5
        assert usage["disk_gb"] == 0.1

    @pytest.mark.asyncio
    async def test_measure_usage_heavy_tool(self):
        """Test measuring usage for heavy tool."""
        dispatcher = MockDispatcher()
        limits = ResourceLimits()
        guard = ResourceGuard(limits)
        executor = ToolExecutor(dispatcher, guard)

        tool_call = ToolCall(tool_name="minimize", parameters={})
        output = {"status": "success"}

        usage = executor._measure_usage(tool_call, output)

        # Heavy tools use 2x resources
        assert usage["cpu_hours"] == 0.1
        assert usage["memory_gb"] == 1.0

    @pytest.mark.asyncio
    async def test_execute_sequence_id_preserved(self):
        """Test that sequence ID is preserved in result."""
        dispatcher = MockDispatcher()
        limits = ResourceLimits()
        guard = ResourceGuard(limits)
        executor = ToolExecutor(dispatcher, guard)

        sequence = ExecutionSequence(
            plan_id="custom-plan-id-123",
            calls=[ToolCall(tool_name="minimize", parameters={})]
        )

        result = await executor.execute(sequence)

        assert result.sequence_id == "custom-plan-id-123"

    @pytest.mark.asyncio
    async def test_execute_complex_sequence(self):
        """Test executing complex multi-step sequence."""
        dispatcher = MockDispatcher()
        limits = ResourceLimits(max_cpu_hours=20.0, max_memory_gb=32.0, max_disk_gb=100.0)
        guard = ResourceGuard(limits)
        executor = ToolExecutor(dispatcher, guard)

        sequence = ExecutionSequence(
            plan_id="complex-plan",
            calls=[
                ToolCall(tool_name="prepare", parameters={"system": "protein"}),
                ToolCall(tool_name="minimize", parameters={"steps": 1000}),
                ToolCall(tool_name="equilibrate", parameters={"steps": 5000}),
                ToolCall(tool_name="production", parameters={"steps": 50000}),
                ToolCall(tool_name="analyze", parameters={"trajectory": "prod.nc"}),
            ]
        )

        result = await executor.execute(sequence)

        assert result.status == ExecutionStatus.SUCCESS
        assert len(result.results) == 5
        assert all(r.status == ResultStatus.SUCCESS for r in result.results)
        assert len(dispatcher.calls) == 5

        # Verify resource usage was tracked
        usage = guard.get_current_usage()
        assert usage["cpu_hours"] > 0
        assert usage["memory_gb"] > 0
