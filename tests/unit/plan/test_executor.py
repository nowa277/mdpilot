"""Tests for PlanExecutor."""
import pytest
from unittest.mock import AsyncMock, Mock

from mdpilot.agent.events import EventEmitter
from mdpilot.plan_legacy.executor import PlanExecutor, STEP_START, STEP_RESULT
from mdpilot.plan_legacy.schema import Plan, PlanStep
from mdpilot.types import ToolOutput


@pytest.fixture
def mock_dispatcher():
    """Create mock ToolDispatcher."""
    return AsyncMock()


@pytest.fixture
def events():
    """Create EventEmitter."""
    return EventEmitter()


@pytest.fixture
def executor(mock_dispatcher, events):
    """Create PlanExecutor instance."""
    return PlanExecutor(dispatcher=mock_dispatcher, events=events)


# ============================================================================
# Initialization Tests
# ============================================================================

class TestPlanExecutorInit:
    """Test PlanExecutor initialization."""
    
    def test_init_stores_dispatcher(self, mock_dispatcher, events):
        """Test initialization stores dispatcher."""
        executor = PlanExecutor(dispatcher=mock_dispatcher, events=events)
        assert executor._dispatcher == mock_dispatcher
    
    def test_init_stores_events(self, mock_dispatcher, events):
        """Test initialization stores event emitter."""
        executor = PlanExecutor(dispatcher=mock_dispatcher, events=events)
        assert executor._events == events
    
    def test_init_cancelled_false(self, mock_dispatcher, events):
        """Test initialization sets cancelled to False."""
        executor = PlanExecutor(dispatcher=mock_dispatcher, events=events)
        assert executor._cancelled is False


# ============================================================================
# Cancel Tests
# ============================================================================

class TestPlanExecutorCancel:
    """Test cancel functionality."""
    
    def test_cancel_sets_flag(self, executor):
        """Test cancel sets cancelled flag."""
        executor.cancel()
        assert executor._cancelled is True
    
    def test_cancel_idempotent(self, executor):
        """Test cancel can be called multiple times."""
        executor.cancel()
        executor.cancel()
        assert executor._cancelled is True


# ============================================================================
# Execute Tests - Success Path
# ============================================================================

class TestPlanExecutorExecuteSuccess:
    """Test successful plan execution."""
    
    @pytest.mark.asyncio
    async def test_execute_empty_plan(self, executor):
        """Test executing empty plan."""
        plan = Plan(goal="Empty", steps=[])
        
        result = await executor.execute(plan)
        
        assert result.success is True
        assert result.error is None
        assert result.results == {}
    
    @pytest.mark.asyncio
    async def test_execute_single_step(self, executor, mock_dispatcher):
        """Test executing plan with single step."""
        step = PlanStep(
            id=1,
            description="Run tool",
            tool="bash_run",
            arguments={"command": "ls"},
            depends_on=[],
        )
        plan = Plan(goal="Test", steps=[step])
        
        mock_dispatcher.execute = AsyncMock(
            return_value=ToolOutput(output="file1.txt", success=True)
        )
        
        result = await executor.execute(plan)
        
        assert result.success is True
        assert result.error is None
        assert 1 in result.results
        assert result.results[1].output == "file1.txt"
        assert step.status == "completed"
    
    @pytest.mark.asyncio
    async def test_execute_multiple_steps(self, executor, mock_dispatcher):
        """Test executing plan with multiple steps."""
        steps = [
            PlanStep(id=1, description="Step 1", tool="tool1", arguments={}, depends_on=[]),
            PlanStep(id=2, description="Step 2", tool="tool2", arguments={}, depends_on=[]),
            PlanStep(id=3, description="Step 3", tool="tool3", arguments={}, depends_on=[]),
        ]
        plan = Plan(goal="Multi-step", steps=steps)
        
        mock_dispatcher.execute = AsyncMock(
            side_effect=[
                ToolOutput(output="result1", success=True),
                ToolOutput(output="result2", success=True),
                ToolOutput(output="result3", success=True),
            ]
        )
        
        result = await executor.execute(plan)
        
        assert result.success is True
        assert len(result.results) == 3
        assert all(step.status == "completed" for step in steps)
    
    @pytest.mark.asyncio
    async def test_execute_with_dependencies(self, executor, mock_dispatcher):
        """Test executing plan with step dependencies."""
        steps = [
            PlanStep(id=1, description="Step 1", tool="tool1", arguments={}, depends_on=[]),
            PlanStep(id=2, description="Step 2", tool="tool2", arguments={}, depends_on=[1]),
            PlanStep(id=3, description="Step 3", tool="tool3", arguments={}, depends_on=[1, 2]),
        ]
        plan = Plan(goal="Dependencies", steps=steps)
        
        mock_dispatcher.execute = AsyncMock(
            side_effect=[
                ToolOutput(output="result1", success=True),
                ToolOutput(output="result2", success=True),
                ToolOutput(output="result3", success=True),
            ]
        )
        
        result = await executor.execute(plan)
        
        assert result.success is True
        assert len(result.results) == 3


# ============================================================================
# Execute Tests - Failure Path
# ============================================================================

class TestPlanExecutorExecuteFailure:
    """Test plan execution failures."""
    
    @pytest.mark.asyncio
    async def test_execute_step_failure(self, executor, mock_dispatcher):
        """Test execution stops on step failure."""
        steps = [
            PlanStep(id=1, description="Step 1", tool="tool1", arguments={}, depends_on=[]),
            PlanStep(id=2, description="Step 2", tool="tool2", arguments={}, depends_on=[]),
        ]
        plan = Plan(goal="Failure", steps=steps)
        
        mock_dispatcher.execute = AsyncMock(
            return_value=ToolOutput(output="", success=False, error="Tool failed")
        )
        
        result = await executor.execute(plan)
        
        assert result.success is False
        assert "failed" in result.error.lower()
        assert steps[0].status == "failed"
        assert len(result.results) == 1
    
    @pytest.mark.asyncio
    async def test_execute_unmet_dependencies(self, executor, mock_dispatcher):
        """Test execution fails with unmet dependencies."""
        steps = [
            PlanStep(id=1, description="Step 1", tool="tool1", arguments={}, depends_on=[]),
            PlanStep(id=2, description="Step 2", tool="tool2", arguments={}, depends_on=[99]),
        ]
        plan = Plan(goal="Bad deps", steps=steps)
        
        mock_dispatcher.execute = AsyncMock(
            return_value=ToolOutput(output="result1", success=True)
        )
        
        result = await executor.execute(plan)
        
        assert result.success is False
        assert "unmet dependencies" in result.error.lower()
        assert "99" in result.error
    
    @pytest.mark.asyncio
    async def test_execute_cancelled(self, executor, mock_dispatcher):
        """Test execution stops when cancelled."""
        steps = [
            PlanStep(id=1, description="Step 1", tool="tool1", arguments={}, depends_on=[]),
            PlanStep(id=2, description="Step 2", tool="tool2", arguments={}, depends_on=[]),
        ]
        plan = Plan(goal="Cancelled", steps=steps)
        
        async def execute_and_cancel(call):
            executor.cancel()
            return ToolOutput(output="result1", success=True)
        
        mock_dispatcher.execute = AsyncMock(side_effect=execute_and_cancel)
        
        result = await executor.execute(plan)
        
        assert result.success is False
        assert "cancelled" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_execute_second_step_fails(self, executor, mock_dispatcher):
        """Test execution stops when second step fails."""
        steps = [
            PlanStep(id=1, description="Step 1", tool="tool1", arguments={}, depends_on=[]),
            PlanStep(id=2, description="Step 2", tool="tool2", arguments={}, depends_on=[]),
            PlanStep(id=3, description="Step 3", tool="tool3", arguments={}, depends_on=[]),
        ]
        plan = Plan(goal="Second fails", steps=steps)
        
        mock_dispatcher.execute = AsyncMock(
            side_effect=[
                ToolOutput(output="result1", success=True),
                ToolOutput(output="", success=False, error="Step 2 failed"),
            ]
        )
        
        result = await executor.execute(plan)
        
        assert result.success is False
        assert "step 2" in result.error.lower()
        assert steps[0].status == "completed"
        assert steps[1].status == "failed"
        assert steps[2].status == "pending"
        assert len(result.results) == 2


# ============================================================================
# Event Emission Tests
# ============================================================================

class TestPlanExecutorEvents:
    """Test event emission during execution."""
    
    @pytest.mark.asyncio
    async def test_emits_step_start(self, executor, mock_dispatcher, events):
        """Test STEP_START event is emitted."""
        step = PlanStep(
            id=1,
            description="Test step",
            tool="bash_run",
            arguments={"command": "ls"},
            depends_on=[],
        )
        plan = Plan(goal="Test", steps=[step])
        
        mock_dispatcher.execute = AsyncMock(
            return_value=ToolOutput(output="result", success=True)
        )
        
        start_events = []
        events.on(STEP_START, lambda e: start_events.append(e.data))
        
        await executor.execute(plan)
        
        assert len(start_events) == 1
        assert start_events[0]["step_id"] == 1
        assert start_events[0]["description"] == "Test step"
        assert start_events[0]["tool"] == "bash_run"
    
    @pytest.mark.asyncio
    async def test_emits_step_result_success(self, executor, mock_dispatcher, events):
        """Test STEP_RESULT event is emitted on success."""
        step = PlanStep(id=1, description="Test", tool="tool1", arguments={}, depends_on=[])
        plan = Plan(goal="Test", steps=[step])
        
        mock_dispatcher.execute = AsyncMock(
            return_value=ToolOutput(output="success output", success=True)
        )
        
        result_events = []
        events.on(STEP_RESULT, lambda e: result_events.append(e.data))
        
        await executor.execute(plan)
        
        assert len(result_events) == 1
        assert result_events[0]["step_id"] == 1
        assert result_events[0]["success"] is True
        assert result_events[0]["output"] == "success output"
    
    @pytest.mark.asyncio
    async def test_emits_step_result_failure(self, executor, mock_dispatcher, events):
        """Test STEP_RESULT event is emitted on failure."""
        step = PlanStep(id=1, description="Test", tool="tool1", arguments={}, depends_on=[])
        plan = Plan(goal="Test", steps=[step])
        
        mock_dispatcher.execute = AsyncMock(
            return_value=ToolOutput(output="", success=False, error="Tool error")
        )
        
        result_events = []
        events.on(STEP_RESULT, lambda e: result_events.append(e.data))
        
        await executor.execute(plan)
        
        assert len(result_events) == 1
        assert result_events[0]["step_id"] == 1
        assert result_events[0]["success"] is False
        assert result_events[0]["error"] == "Tool error"
    
    @pytest.mark.asyncio
    async def test_emits_events_for_all_steps(self, executor, mock_dispatcher, events):
        """Test events are emitted for all executed steps."""
        steps = [
            PlanStep(id=1, description="Step 1", tool="tool1", arguments={}, depends_on=[]),
            PlanStep(id=2, description="Step 2", tool="tool2", arguments={}, depends_on=[]),
        ]
        plan = Plan(goal="Multi", steps=steps)
        
        mock_dispatcher.execute = AsyncMock(
            side_effect=[
                ToolOutput(output="result1", success=True),
                ToolOutput(output="result2", success=True),
            ]
        )
        
        start_events = []
        result_events = []
        events.on(STEP_START, lambda e: start_events.append(e.data))
        events.on(STEP_RESULT, lambda e: result_events.append(e.data))
        
        await executor.execute(plan)
        
        assert len(start_events) == 2
        assert len(result_events) == 2


# ============================================================================
# Step Status Tests
# ============================================================================

class TestPlanExecutorStepStatus:
    """Test step status updates during execution."""
    
    @pytest.mark.asyncio
    async def test_step_status_running(self, executor, mock_dispatcher):
        """Test step status is set to running during execution."""
        step = PlanStep(id=1, description="Test", tool="tool1", arguments={}, depends_on=[])
        plan = Plan(goal="Test", steps=[step])
        
        async def check_status(call):
            assert step.status == "running"
            return ToolOutput(output="result", success=True)
        
        mock_dispatcher.execute = AsyncMock(side_effect=check_status)
        
        await executor.execute(plan)
    
    @pytest.mark.asyncio
    async def test_step_status_completed(self, executor, mock_dispatcher):
        """Test step status is set to completed on success."""
        step = PlanStep(id=1, description="Test", tool="tool1", arguments={}, depends_on=[])
        plan = Plan(goal="Test", steps=[step])
        
        mock_dispatcher.execute = AsyncMock(
            return_value=ToolOutput(output="result", success=True)
        )
        
        await executor.execute(plan)
        
        assert step.status == "completed"
    
    @pytest.mark.asyncio
    async def test_step_status_failed(self, executor, mock_dispatcher):
        """Test step status is set to failed on error."""
        step = PlanStep(id=1, description="Test", tool="tool1", arguments={}, depends_on=[])
        plan = Plan(goal="Test", steps=[step])
        
        mock_dispatcher.execute = AsyncMock(
            return_value=ToolOutput(output="", success=False, error="Error")
        )
        
        await executor.execute(plan)
        
        assert step.status == "failed"


# ============================================================================
# Integration Tests
# ============================================================================

class TestPlanExecutorIntegration:
    """Integration tests for complex scenarios."""
    
    @pytest.mark.asyncio
    async def test_complex_dependency_chain(self, executor, mock_dispatcher):
        """Test complex dependency chain execution."""
        steps = [
            PlanStep(id=1, description="Init", tool="tool1", arguments={}, depends_on=[]),
            PlanStep(id=2, description="Process A", tool="tool2", arguments={}, depends_on=[1]),
            PlanStep(id=3, description="Process B", tool="tool3", arguments={}, depends_on=[1]),
            PlanStep(id=4, description="Merge", tool="tool4", arguments={}, depends_on=[2, 3]),
        ]
        plan = Plan(goal="Complex", steps=steps)
        
        mock_dispatcher.execute = AsyncMock(
            side_effect=[
                ToolOutput(output="init", success=True),
                ToolOutput(output="processA", success=True),
                ToolOutput(output="processB", success=True),
                ToolOutput(output="merged", success=True),
            ]
        )
        
        result = await executor.execute(plan)
        
        assert result.success is True
        assert len(result.results) == 4
        assert all(step.status == "completed" for step in steps)
    
    @pytest.mark.asyncio
    async def test_partial_execution_with_cancellation(self, executor, mock_dispatcher):
        """Test partial execution when cancelled mid-way."""
        steps = [
            PlanStep(id=1, description="Step 1", tool="tool1", arguments={}, depends_on=[]),
            PlanStep(id=2, description="Step 2", tool="tool2", arguments={}, depends_on=[]),
            PlanStep(id=3, description="Step 3", tool="tool3", arguments={}, depends_on=[]),
        ]
        plan = Plan(goal="Partial", steps=steps)
        
        call_count = 0
        async def execute_with_cancel(call):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                executor.cancel()
            return ToolOutput(output=f"result{call_count}", success=True)
        
        mock_dispatcher.execute = AsyncMock(side_effect=execute_with_cancel)
        
        result = await executor.execute(plan)
        
        assert result.success is False
        assert "cancelled" in result.error.lower()
        assert len(result.results) == 2
        assert steps[0].status == "completed"
        assert steps[1].status == "completed"
        assert steps[2].status == "pending"
