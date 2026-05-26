"""Tests for the Plan-then-Execute engine."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from mdpilot.agent.events import EventEmitter
from mdpilot.llm.provider import LLMProvider
from mdpilot.plan_legacy import (
    Plan,
    PlanExecutor,
    PlanGenerator,
    PlanGenerationError,
    PlanResult,
    PlanStep,
)
from mdpilot.tools.dispatcher import ToolDispatcher
from mdpilot.tools.registry import ToolRegistry
from mdpilot.types import ToolCall, ToolOutput


# ---------------------------------------------------------------------------
# PlanStep and Plan model tests
# ---------------------------------------------------------------------------

def test_plan_step_defaults():
    """PlanStep must have correct default values."""
    step = PlanStep(id=1, description="test", tool="bash", arguments={})
    assert step.status == "pending"
    assert step.depends_on == []


def test_plan_step_full():
    """PlanStep must accept all fields."""
    step = PlanStep(
        id=3,
        description="Run analysis",
        tool="bash",
        arguments={"cmd": "ls"},
        depends_on=[1, 2],
        status="running",
    )
    assert step.id == 3
    assert step.description == "Run analysis"
    assert step.tool == "bash"
    assert step.arguments == {"cmd": "ls"}
    assert step.depends_on == [1, 2]
    assert step.status == "running"


def test_plan_model():
    """Plan must hold steps and metadata."""
    steps = [
        PlanStep(id=1, description="Step 1", tool="bash", arguments={}),
        PlanStep(id=2, description="Step 2", tool="bash", arguments={}, depends_on=[1]),
    ]
    plan = Plan(goal="Test goal", steps=steps, estimated_time="5 minutes")
    assert plan.goal == "Test goal"
    assert len(plan.steps) == 2
    assert plan.estimated_time == "5 minutes"


def test_plan_result_model():
    """PlanResult must hold plan, results, and status."""
    plan = Plan(goal="Test", steps=[])
    result = PlanResult(plan=plan, results={}, success=True)
    assert result.success is True
    assert result.error is None


def test_plan_result_failure():
    """PlanResult must capture failure state."""
    plan = Plan(goal="Test", steps=[])
    result = PlanResult(plan=plan, results={}, success=False, error="Step 1 failed")
    assert result.success is False
    assert result.error == "Step 1 failed"


# ---------------------------------------------------------------------------
# PlanGenerator tests
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_provider() -> MagicMock:
    """Create a mock LLMProvider."""
    provider = MagicMock(spec=LLMProvider)
    return provider


@pytest.fixture
def registry() -> ToolRegistry:
    """Create a registry with known tools."""
    reg = ToolRegistry()
    # Register a mock tool directly
    meta = MagicMock()
    meta.name = "bash"
    meta.description = "Run a bash command"
    meta.parameters = {
        "type": "object",
        "properties": {"cmd": {"type": "string"}},
        "required": ["cmd"],
    }
    reg._tools["bash"] = (meta, AsyncMock(return_value="ok"))

    meta2 = MagicMock()
    meta2.name = "read_file"
    meta2.description = "Read a file"
    meta2.parameters = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }
    reg._tools["read_file"] = (meta2, AsyncMock(return_value="content"))

    return reg


@pytest.mark.asyncio
async def test_generator_valid_plan(mock_provider, registry):
    """Generator must return a Plan from valid LLM JSON output."""
    plan_json = {
        "goal": "List files and read one",
        "steps": [
            {
                "description": "List files",
                "tool": "bash",
                "arguments": {"cmd": "ls"},
                "depends_on": [],
            },
            {
                "description": "Read a file",
                "tool": "read_file",
                "arguments": {"path": "test.txt"},
                "depends_on": [1],
            },
        ],
        "estimated_time": "1 minute",
    }

    mock_response = MagicMock()
    mock_response.content = '{"goal": "List files and read one", "steps": [{"description": "List files", "tool": "bash", "arguments": {"cmd": "ls"}, "depends_on": []}, {"description": "Read a file", "tool": "read_file", "arguments": {"path": "test.txt"}, "depends_on": [1]}], "estimated_time": "1 minute"}'
    mock_response.tool_calls = []
    mock_response.finish_reason = "stop"
    mock_response.usage_prompt_tokens = 100
    mock_response.usage_completion_tokens = 50
    mock_provider.chat_once = AsyncMock(return_value=mock_response)

    generator = PlanGenerator(provider=mock_provider, tool_registry=registry)
    plan = await generator.generate("List files and read one")

    assert isinstance(plan, Plan)
    assert plan.goal == "List files and read one"
    assert len(plan.steps) == 2
    assert plan.steps[0].tool == "bash"
    assert plan.steps[1].depends_on == [1]


@pytest.mark.asyncio
async def test_generator_invalid_json(mock_provider, registry):
    """Generator must raise PlanGenerationError on invalid JSON."""
    mock_response = MagicMock()
    mock_response.content = "not valid json at all"
    mock_response.tool_calls = []
    mock_response.finish_reason = "stop"
    mock_response.usage_prompt_tokens = 100
    mock_response.usage_completion_tokens = 50
    mock_provider.chat_once = AsyncMock(return_value=mock_response)

    generator = PlanGenerator(provider=mock_provider, tool_registry=registry)

    with pytest.raises(PlanGenerationError, match="invalid JSON"):
        await generator.generate("test goal")


@pytest.mark.asyncio
async def test_generator_unknown_tool(mock_provider, registry):
    """Generator must raise PlanGenerationError for unknown tool names."""
    plan_json = {
        "goal": "Test",
        "steps": [
            {
                "description": "Unknown step",
                "tool": "nonexistent_tool",
                "arguments": {},
                "depends_on": [],
            },
        ],
    }
    mock_response = MagicMock()
    mock_response.content = __import__("json").dumps(plan_json)
    mock_response.tool_calls = []
    mock_response.finish_reason = "stop"
    mock_response.usage_prompt_tokens = 100
    mock_response.usage_completion_tokens = 50
    mock_provider.chat_once = AsyncMock(return_value=mock_response)

    generator = PlanGenerator(provider=mock_provider, tool_registry=registry)

    with pytest.raises(PlanGenerationError, match="unknown tool"):
        await generator.generate("test goal")


@pytest.mark.asyncio
async def test_generator_invalid_dependency(mock_provider, registry):
    """Generator must raise PlanGenerationError for invalid dependency IDs."""
    plan_json = {
        "goal": "Test",
        "steps": [
            {
                "description": "Step 1",
                "tool": "bash",
                "arguments": {},
                "depends_on": [99],
            },
        ],
    }
    mock_response = MagicMock()
    mock_response.content = __import__("json").dumps(plan_json)
    mock_response.tool_calls = []
    mock_response.finish_reason = "stop"
    mock_response.usage_prompt_tokens = 100
    mock_response.usage_completion_tokens = 50
    mock_provider.chat_once = AsyncMock(return_value=mock_response)

    generator = PlanGenerator(provider=mock_provider, tool_registry=registry)

    with pytest.raises(PlanGenerationError, match="non-existent step ID"):
        await generator.generate("test goal")


@pytest.mark.asyncio
async def test_generator_strips_code_fences(mock_provider, registry):
    """Generator must handle JSON wrapped in markdown code fences."""
    mock_response = MagicMock()
    mock_response.content = '```json\n{"goal": "Test", "steps": []}\n```'
    mock_response.tool_calls = []
    mock_response.finish_reason = "stop"
    mock_response.usage_prompt_tokens = 100
    mock_response.usage_completion_tokens = 50
    mock_provider.chat_once = AsyncMock(return_value=mock_response)

    generator = PlanGenerator(provider=mock_provider, tool_registry=registry)
    plan = await generator.generate("Test")

    assert plan.goal == "Test"
    assert plan.steps == []


# ---------------------------------------------------------------------------
# PlanExecutor tests
# ---------------------------------------------------------------------------

@pytest.fixture
def executor_parts():
    """Create executor with mocked dispatcher."""
    dispatcher = MagicMock(spec=ToolDispatcher)
    events = EventEmitter()
    return dispatcher, events


@pytest.mark.asyncio
async def test_executor_simple_success(executor_parts):
    """Executor must run all steps and succeed."""
    dispatcher, events = executor_parts

    # Mock dispatcher.execute to return success
    dispatcher.execute = AsyncMock(
        side_effect=[
            ToolOutput(output="result1", success=True),
            ToolOutput(output="result2", success=True),
        ]
    )

    plan = Plan(
        goal="Simple two-step plan",
        steps=[
            PlanStep(id=1, description="Step 1", tool="bash", arguments={}),
            PlanStep(id=2, description="Step 2", tool="bash", arguments={}),
        ],
    )

    executor = PlanExecutor(dispatcher=dispatcher, events=events)
    result = await executor.execute(plan)

    assert result.success is True
    assert result.error is None
    assert len(result.results) == 2
    assert result.results[1].output == "result1"
    assert result.results[2].output == "result2"


@pytest.mark.asyncio
async def test_executor_dependency_chain(executor_parts):
    """Executor must respect dependency order."""
    dispatcher, events = executor_parts

    call_order: list[int] = []

    async def track_execute(call: ToolCall) -> ToolOutput:
        call_order.append(call.id)
        return ToolOutput(output=f"executed {call.id}", success=True)

    dispatcher.execute = AsyncMock(side_effect=track_execute)

    plan = Plan(
        goal="Dependency chain",
        steps=[
            PlanStep(id=1, description="First", tool="bash", arguments={}),
            PlanStep(id=2, description="Second", tool="bash", arguments={}, depends_on=[1]),
            PlanStep(id=3, description="Third", tool="bash", arguments={}, depends_on=[2]),
        ],
    )

    executor = PlanExecutor(dispatcher=dispatcher, events=events)
    result = await executor.execute(plan)

    assert result.success is True
    assert call_order == ["plan-step-1", "plan-step-2", "plan-step-3"]


@pytest.mark.asyncio
async def test_executor_step_failure_stops(executor_parts):
    """Executor must stop and return error on step failure."""
    dispatcher, events = executor_parts

    dispatcher.execute = AsyncMock(
        side_effect=[
            ToolOutput(output="ok", success=True),
            ToolOutput(output="", success=False, error="something went wrong"),
        ]
    )

    plan = Plan(
        goal="Failing plan",
        steps=[
            PlanStep(id=1, description="OK step", tool="bash", arguments={}),
            PlanStep(id=2, description="Failing step", tool="bash", arguments={}),
        ],
    )

    executor = PlanExecutor(dispatcher=dispatcher, events=events)
    result = await executor.execute(plan)

    assert result.success is False
    assert "something went wrong" in result.error
    # Both step results are recorded (failed step result is still stored)
    assert 1 in result.results
    assert 2 in result.results
    assert result.results[2].success is False


@pytest.mark.asyncio
async def test_executor_cancel(executor_parts):
    """Executor must stop when cancel is called."""
    dispatcher, events = executor_parts

    step_count = 0

    async def slow_execute(call: ToolCall) -> ToolOutput:
        nonlocal step_count
        step_count += 1
        await asyncio.sleep(0.1)
        return ToolOutput(output="done", success=True)

    dispatcher.execute = AsyncMock(side_effect=slow_execute)

    plan = Plan(
        goal="Long plan",
        steps=[
            PlanStep(id=1, description="Step 1", tool="bash", arguments={}),
            PlanStep(id=2, description="Step 2", tool="bash", arguments={}),
        ],
    )

    executor = PlanExecutor(dispatcher=dispatcher, events=events)

    # Start execution in background
    async def run():
        return await executor.execute(plan)

    task = asyncio.create_task(run())

    # Let step 1 start
    await asyncio.sleep(0.05)

    # Cancel
    executor.cancel()

    result = await task

    # Should be cancelled before step 2
    assert result.success is False
    assert "Cancelled" in result.error


@pytest.mark.asyncio
async def test_executor_unmet_dependency(executor_parts):
    """Executor must fail if a step has unmet dependencies."""
    dispatcher, events = executor_parts

    plan = Plan(
        goal="Bad dependencies",
        steps=[
            PlanStep(id=1, description="Orphan", tool="bash", arguments={}, depends_on=[2]),
        ],
    )

    executor = PlanExecutor(dispatcher=dispatcher, events=events)
    result = await executor.execute(plan)

    assert result.success is False
    assert "unmet dependencies" in result.error


@pytest.mark.asyncio
async def test_executor_events_emit_step_start(executor_parts):
    """Executor must emit STEP_START events before each step."""
    dispatcher, events = executor_parts

    dispatcher.execute = AsyncMock(return_value=ToolOutput(output="ok", success=True))

    plan = Plan(
        goal="Event test",
        steps=[
            PlanStep(id=1, description="Step 1", tool="bash", arguments={}),
        ],
    )

    step_started = False

    def on_step_start(event):
        nonlocal step_started
        step_started = True
        assert event.data["step_id"] == 1
        assert event.data["tool"] == "bash"

    events.on("step_start", on_step_start)

    executor = PlanExecutor(dispatcher=dispatcher, events=events)
    await executor.execute(plan)

    assert step_started is True
