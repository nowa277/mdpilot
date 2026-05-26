"""Tests for ParallelExecutor."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from mdpilot.agent.dependency_graph import ToolNode
from mdpilot.agent.events import EventEmitter
from mdpilot.agent.parallel_executor import (
    ExecutionConfig,
    ExecutionResult,
    ParallelExecutor,
)
from mdpilot.tools.dispatcher import ToolDispatcher
from mdpilot.tools.registry import ToolRegistry
from mdpilot.types import ToolCall, ToolMeta, ToolOutput


@pytest.fixture
def mock_registry():
    """Create a mock tool registry."""
    registry = MagicMock(spec=ToolRegistry)
    return registry


@pytest.fixture
def mock_dispatcher():
    """Create a mock tool dispatcher."""
    dispatcher = MagicMock(spec=ToolDispatcher)
    dispatcher.execute = AsyncMock(return_value=ToolOutput(output="success"))
    return dispatcher


@pytest.fixture
def event_emitter():
    """Create an event emitter."""
    return EventEmitter()


@pytest.fixture
def default_config():
    """Create default execution config."""
    return ExecutionConfig(
        max_concurrent_tools=4,
        max_memory_mb=8192,
        max_gpu_tools=1,
        enable_parallel=True
    )


@pytest.fixture
def executor(mock_dispatcher, mock_registry, default_config, event_emitter):
    """Create a ParallelExecutor instance."""
    return ParallelExecutor(
        dispatcher=mock_dispatcher,
        registry=mock_registry,
        config=default_config,
        events=event_emitter
    )


# ============================================================================
# Task 11: Core Structure and Configuration Tests
# ============================================================================

def test_execution_config_creation():
    """Test ExecutionConfig dataclass creation."""
    config = ExecutionConfig(
        max_concurrent_tools=8,
        max_memory_mb=16384,
        max_gpu_tools=2,
        enable_parallel=True
    )

    assert config.max_concurrent_tools == 8
    assert config.max_memory_mb == 16384
    assert config.max_gpu_tools == 2
    assert config.enable_parallel is True


def test_execution_config_defaults():
    """Test ExecutionConfig default values."""
    config = ExecutionConfig()

    assert config.max_concurrent_tools == 4
    assert config.max_memory_mb == 8192
    assert config.max_gpu_tools == 1
    assert config.enable_parallel is True


def test_execution_result_creation():
    """Test ExecutionResult dataclass creation."""
    tool_call = ToolCall(id="tool_1", name="test_tool", arguments={})
    output = ToolOutput(output="test output")

    result = ExecutionResult(
        tool_id="tool_1",
        tool_call=tool_call,
        output=output,
        start_time=1000.0,
        end_time=1005.0,
        wave_id=0
    )

    assert result.tool_id == "tool_1"
    assert result.tool_call == tool_call
    assert result.output == output
    assert result.start_time == 1000.0
    assert result.end_time == 1005.0
    assert result.wave_id == 0


def test_parallel_executor_initialization(executor, mock_dispatcher, mock_registry, default_config, event_emitter):
    """Test ParallelExecutor initialization."""
    assert executor._dispatcher == mock_dispatcher
    assert executor._registry == mock_registry
    assert executor._config == default_config
    assert executor._events == event_emitter
    assert executor._progress_tracker is None
    assert "global" in executor._semaphores
    assert "gpu" in executor._semaphores


# ============================================================================
# Task 12: Semaphore Creation Tests
# ============================================================================

def test_create_semaphores_default_config(executor):
    """Test semaphore creation with default config."""
    semaphores = executor._semaphores

    assert "global" in semaphores
    assert "gpu" in semaphores
    assert isinstance(semaphores["global"], asyncio.Semaphore)
    assert isinstance(semaphores["gpu"], asyncio.Semaphore)


def test_create_semaphores_custom_config():
    """Test semaphore creation with custom config."""
    config = ExecutionConfig(
        max_concurrent_tools=8,
        max_gpu_tools=2
    )
    executor = ParallelExecutor(
        dispatcher=MagicMock(spec=ToolDispatcher),
        registry=MagicMock(spec=ToolRegistry),
        config=config,
        events=EventEmitter()
    )

    semaphores = executor._semaphores

    # Verify semaphores are created with correct limits
    assert "global" in semaphores
    assert "gpu" in semaphores

    # Test that semaphores have correct capacity by acquiring them
    global_sem = semaphores["global"]
    gpu_sem = semaphores["gpu"]

    # Global semaphore should allow 8 concurrent acquisitions
    assert global_sem._value == 8

    # GPU semaphore should allow 2 concurrent acquisitions
    assert gpu_sem._value == 2


def test_semaphore_limits_enforced():
    """Test that semaphore limits are enforced."""
    config = ExecutionConfig(max_concurrent_tools=2, max_gpu_tools=1)
    executor = ParallelExecutor(
        dispatcher=MagicMock(spec=ToolDispatcher),
        registry=MagicMock(spec=ToolRegistry),
        config=config,
        events=EventEmitter()
    )

    global_sem = executor._semaphores["global"]
    gpu_sem = executor._semaphores["gpu"]

    assert global_sem._value == 2
    assert gpu_sem._value == 1


# ============================================================================
# Task 13: Single Tool Execution Tests
# ============================================================================

@pytest.mark.asyncio
async def test_execute_single_tool_non_gpu(executor, mock_dispatcher, mock_registry):
    """Test executing a single non-GPU tool."""
    # Setup
    tool_call = ToolCall(id="tool_1", name="pdb4amber", arguments={"input_pdb": "test.pdb"})
    node = ToolNode(
        tool_id="tool_1",
        tool_call=tool_call,
        input_files={"test.pdb"},
        output_files={"test_clean.pdb"},
        explicit_deps=[]
    )

    # Mock registry to return non-GPU tool
    tool_meta = ToolMeta(
        name="pdb4amber",
        description="Clean PDB",
        parameters={},
        resource_requirements={"gpu": False}
    )
    mock_registry.get.return_value = (tool_meta, lambda: None)

    # Mock dispatcher
    expected_output = ToolOutput(output="PDB cleaned successfully")
    mock_dispatcher.execute.return_value = expected_output

    # Execute
    result = await executor._execute_single_tool(node, wave_id=0)

    # Verify
    assert result.tool_id == "tool_1"
    assert result.tool_call == tool_call
    assert result.output == expected_output
    assert result.wave_id == 0
    assert result.end_time > result.start_time
    mock_dispatcher.execute.assert_called_once_with(tool_call)


@pytest.mark.asyncio
async def test_execute_single_tool_gpu(executor, mock_dispatcher, mock_registry):
    """Test executing a single GPU tool."""
    # Setup
    tool_call = ToolCall(id="tool_1", name="pmemd_cuda", arguments={})
    node = ToolNode(
        tool_id="tool_1",
        tool_call=tool_call,
        input_files=set(),
        output_files=set(),
        explicit_deps=[]
    )

    # Mock registry to return GPU tool
    tool_meta = ToolMeta(
        name="pmemd_cuda",
        description="Run MD with GPU",
        parameters={},
        resource_requirements={"gpu": True}
    )
    mock_registry.get.return_value = (tool_meta, lambda: None)

    # Mock dispatcher
    expected_output = ToolOutput(output="MD simulation complete")
    mock_dispatcher.execute.return_value = expected_output

    # Execute
    result = await executor._execute_single_tool(node, wave_id=0)

    # Verify
    assert result.tool_id == "tool_1"
    assert result.output == expected_output
    assert result.wave_id == 0
    mock_dispatcher.execute.assert_called_once_with(tool_call)


@pytest.mark.asyncio
async def test_execute_single_tool_no_metadata(executor, mock_dispatcher, mock_registry):
    """Test executing a tool when registry returns None (no metadata)."""
    # Setup
    tool_call = ToolCall(id="tool_1", name="unknown_tool", arguments={})
    node = ToolNode(
        tool_id="tool_1",
        tool_call=tool_call,
        input_files=set(),
        output_files=set(),
        explicit_deps=[]
    )

    # Mock registry to return None (tool not found)
    mock_registry.get.return_value = None

    # Mock dispatcher
    expected_output = ToolOutput(output="Tool executed")
    mock_dispatcher.execute.return_value = expected_output

    # Execute (should treat as non-GPU tool)
    result = await executor._execute_single_tool(node, wave_id=0)

    # Verify
    assert result.tool_id == "tool_1"
    assert result.output == expected_output
    mock_dispatcher.execute.assert_called_once_with(tool_call)


@pytest.mark.asyncio
async def test_execute_single_tool_timing(executor, mock_dispatcher, mock_registry):
    """Test that execution timing is recorded correctly."""
    # Setup
    tool_call = ToolCall(id="tool_1", name="test_tool", arguments={})
    node = ToolNode(
        tool_id="tool_1",
        tool_call=tool_call,
        input_files=set(),
        output_files=set(),
        explicit_deps=[]
    )

    # Mock registry
    mock_registry.get.return_value = None

    # Mock dispatcher with delay
    async def delayed_execute(call):
        await asyncio.sleep(0.1)
        return ToolOutput(output="done")

    mock_dispatcher.execute = delayed_execute

    # Execute
    result = await executor._execute_single_tool(node, wave_id=0)

    # Verify timing
    duration = result.end_time - result.start_time
    assert duration >= 0.1
    assert duration < 0.2  # Should not take too long


@pytest.mark.asyncio
async def test_execute_single_tool_with_error(executor, mock_dispatcher, mock_registry):
    """Test executing a tool that returns an error."""
    # Setup
    tool_call = ToolCall(id="tool_1", name="test_tool", arguments={})
    node = ToolNode(
        tool_id="tool_1",
        tool_call=tool_call,
        input_files=set(),
        output_files=set(),
        explicit_deps=[]
    )

    # Mock registry
    mock_registry.get.return_value = None

    # Mock dispatcher to return error
    error_output = ToolOutput(
        output="",
        success=False,
        error="File not found"
    )
    mock_dispatcher.execute.return_value = error_output

    # Execute
    result = await executor._execute_single_tool(node, wave_id=0)

    # Verify
    assert result.output.success is False
    assert result.output.error == "File not found"


@pytest.mark.asyncio
async def test_concurrent_tool_execution_respects_global_limit(mock_dispatcher, mock_registry, event_emitter):
    """Test that concurrent execution respects global semaphore limit."""
    # Create executor with limit of 2 concurrent tools
    config = ExecutionConfig(max_concurrent_tools=2)
    executor = ParallelExecutor(
        dispatcher=mock_dispatcher,
        registry=mock_registry,
        config=config,
        events=event_emitter
    )

    # Mock registry
    mock_registry.get.return_value = None

    # Track concurrent executions
    concurrent_count = 0
    max_concurrent = 0
    lock = asyncio.Lock()

    async def tracked_execute(call):
        nonlocal concurrent_count, max_concurrent
        async with lock:
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)

        await asyncio.sleep(0.05)

        async with lock:
            concurrent_count -= 1

        return ToolOutput(output="done")

    mock_dispatcher.execute = tracked_execute

    # Create 5 tool nodes
    nodes = [
        ToolNode(
            tool_id=f"tool_{i}",
            tool_call=ToolCall(id=f"tool_{i}", name="test_tool", arguments={}),
            input_files=set(),
            output_files=set(),
            explicit_deps=[]
        )
        for i in range(5)
    ]

    # Execute all tools concurrently
    tasks = [executor._execute_single_tool(node, wave_id=0) for node in nodes]
    await asyncio.gather(*tasks)

    # Verify that max concurrent was limited to 2
    assert max_concurrent <= 2


@pytest.mark.asyncio
async def test_concurrent_gpu_tools_respect_gpu_limit(mock_dispatcher, mock_registry, event_emitter):
    """Test that concurrent GPU tools respect GPU semaphore limit."""
    # Create executor with GPU limit of 1
    config = ExecutionConfig(max_concurrent_tools=4, max_gpu_tools=1)
    executor = ParallelExecutor(
        dispatcher=mock_dispatcher,
        registry=mock_registry,
        config=config,
        events=event_emitter
    )

    # Mock registry to return GPU tool
    tool_meta = ToolMeta(
        name="pmemd_cuda",
        description="GPU tool",
        parameters={},
        resource_requirements={"gpu": True}
    )
    mock_registry.get.return_value = (tool_meta, lambda: None)

    # Track concurrent GPU executions
    concurrent_gpu_count = 0
    max_concurrent_gpu = 0
    lock = asyncio.Lock()

    async def tracked_execute(call):
        nonlocal concurrent_gpu_count, max_concurrent_gpu
        async with lock:
            concurrent_gpu_count += 1
            max_concurrent_gpu = max(max_concurrent_gpu, concurrent_gpu_count)

        await asyncio.sleep(0.05)

        async with lock:
            concurrent_gpu_count -= 1

        return ToolOutput(output="done")

    mock_dispatcher.execute = tracked_execute

    # Create 3 GPU tool nodes
    nodes = [
        ToolNode(
            tool_id=f"gpu_tool_{i}",
            tool_call=ToolCall(id=f"gpu_tool_{i}", name="pmemd_cuda", arguments={}),
            input_files=set(),
            output_files=set(),
            explicit_deps=[]
        )
        for i in range(3)
    ]

    # Execute all GPU tools concurrently
    tasks = [executor._execute_single_tool(node, wave_id=0) for node in nodes]
    await asyncio.gather(*tasks)

    # Verify that max concurrent GPU tools was limited to 1
    assert max_concurrent_gpu == 1


@pytest.mark.asyncio
async def test_mixed_gpu_non_gpu_execution(mock_dispatcher, mock_registry, event_emitter):
    """Test executing mix of GPU and non-GPU tools."""
    config = ExecutionConfig(max_concurrent_tools=4, max_gpu_tools=1)
    executor = ParallelExecutor(
        dispatcher=mock_dispatcher,
        registry=mock_registry,
        config=config,
        events=event_emitter
    )

    # Mock registry to return different metadata based on tool name
    def get_tool_meta(name):
        if "gpu" in name:
            return (
                ToolMeta(
                    name=name,
                    description="GPU tool",
                    parameters={},
                    resource_requirements={"gpu": True}
                ),
                lambda: None
            )
        else:
            return (
                ToolMeta(
                    name=name,
                    description="CPU tool",
                    parameters={},
                    resource_requirements={"gpu": False}
                ),
                lambda: None
            )

    mock_registry.get.side_effect = get_tool_meta

    # Mock dispatcher
    mock_dispatcher.execute = AsyncMock(return_value=ToolOutput(output="done"))

    # Create mix of GPU and non-GPU tools
    nodes = [
        ToolNode(
            tool_id="cpu_1",
            tool_call=ToolCall(id="cpu_1", name="pdb4amber", arguments={}),
            input_files=set(),
            output_files=set(),
            explicit_deps=[]
        ),
        ToolNode(
            tool_id="gpu_1",
            tool_call=ToolCall(id="gpu_1", name="pmemd_gpu", arguments={}),
            input_files=set(),
            output_files=set(),
            explicit_deps=[]
        ),
        ToolNode(
            tool_id="cpu_2",
            tool_call=ToolCall(id="cpu_2", name="tleap", arguments={}),
            input_files=set(),
            output_files=set(),
            explicit_deps=[]
        ),
    ]

    # Execute all tools
    tasks = [executor._execute_single_tool(node, wave_id=0) for node in nodes]
    results = await asyncio.gather(*tasks)

    # Verify all tools executed
    assert len(results) == 3
    assert all(r.output.output == "done" for r in results)


# ============================================================================
# Task 14: Wave Execution Tests
# ============================================================================

@pytest.mark.asyncio
async def test_execute_wave_single_tool(executor, mock_dispatcher, mock_registry, event_emitter):
    """Test executing a wave with a single tool."""
    from mdpilot.agent.dependency_graph import ExecutionWave

    # Setup
    tool_call = ToolCall(id="tool_1", name="test_tool", arguments={})
    node = ToolNode(
        tool_id="tool_1",
        tool_call=tool_call,
        input_files=set(),
        output_files=set(),
        explicit_deps=[]
    )
    wave = ExecutionWave(wave_id=0, tools=[node])

    # Mock registry
    mock_registry.get.return_value = None

    # Mock dispatcher
    expected_output = ToolOutput(output="success")
    mock_dispatcher.execute.return_value = expected_output

    # Track events
    events_received = []
    event_emitter.on("parallel.wave_start", lambda event: events_received.append(("start", event.data)))
    event_emitter.on("parallel.wave_complete", lambda event: events_received.append(("complete", event.data)))

    # Execute
    results = await executor.execute_wave(wave, wave_id=0)

    # Verify results
    assert len(results) == 1
    assert results[0].tool_id == "tool_1"
    assert results[0].output == expected_output
    assert results[0].wave_id == 0

    # Verify events
    assert len(events_received) == 2
    assert events_received[0][0] == "start"
    assert events_received[0][1]["wave_id"] == 0
    assert events_received[0][1]["tool_count"] == 1
    assert events_received[0][1]["tools"] == ["test_tool"]

    assert events_received[1][0] == "complete"
    assert events_received[1][1]["wave_id"] == 0
    assert events_received[1][1]["success_count"] == 1
    assert events_received[1][1]["failure_count"] == 0


@pytest.mark.asyncio
async def test_execute_wave_multiple_tools(executor, mock_dispatcher, mock_registry, event_emitter):
    """Test executing a wave with multiple tools in parallel."""
    from mdpilot.agent.dependency_graph import ExecutionWave

    # Setup multiple tools
    nodes = [
        ToolNode(
            tool_id=f"tool_{i}",
            tool_call=ToolCall(id=f"tool_{i}", name=f"test_tool_{i}", arguments={}),
            input_files=set(),
            output_files=set(),
            explicit_deps=[]
        )
        for i in range(3)
    ]
    wave = ExecutionWave(wave_id=0, tools=nodes)

    # Mock registry
    mock_registry.get.return_value = None

    # Mock dispatcher
    mock_dispatcher.execute = AsyncMock(return_value=ToolOutput(output="success"))

    # Execute
    results = await executor.execute_wave(wave, wave_id=0)

    # Verify all tools executed
    assert len(results) == 3
    assert all(r.output.output == "success" for r in results)
    assert all(r.wave_id == 0 for r in results)

    # Verify all tools were called
    assert mock_dispatcher.execute.call_count == 3


@pytest.mark.asyncio
async def test_execute_wave_with_exception(executor, mock_dispatcher, mock_registry, event_emitter):
    """Test wave execution handles exceptions and converts to failed results."""
    from mdpilot.agent.dependency_graph import ExecutionWave

    # Setup
    nodes = [
        ToolNode(
            tool_id="tool_1",
            tool_call=ToolCall(id="tool_1", name="test_tool_1", arguments={}),
            input_files=set(),
            output_files=set(),
            explicit_deps=[]
        ),
        ToolNode(
            tool_id="tool_2",
            tool_call=ToolCall(id="tool_2", name="test_tool_2", arguments={}),
            input_files=set(),
            output_files=set(),
            explicit_deps=[]
        ),
    ]
    wave = ExecutionWave(wave_id=0, tools=nodes)

    # Mock registry
    mock_registry.get.return_value = None

    # Mock dispatcher - first succeeds, second raises exception
    call_count = 0
    async def mock_execute(call):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ToolOutput(output="success")
        else:
            raise RuntimeError("Tool execution failed")

    mock_dispatcher.execute = mock_execute

    # Track events
    events_received = []
    event_emitter.on("parallel.wave_complete", lambda event: events_received.append(event.data))

    # Execute
    results = await executor.execute_wave(wave, wave_id=0)

    # Verify results
    assert len(results) == 2

    # First tool should succeed
    assert results[0].output.success is True
    assert results[0].output.output == "success"

    # Second tool should have failed result
    assert results[1].output.success is False
    assert "Tool execution failed" in results[1].output.error

    # Verify event shows 1 success, 1 failure
    assert len(events_received) == 1
    assert events_received[0]["success_count"] == 1
    assert events_received[0]["failure_count"] == 1


@pytest.mark.asyncio
async def test_execute_wave_emits_correct_events(executor, mock_dispatcher, mock_registry, event_emitter):
    """Test that wave execution emits correct start and complete events."""
    from mdpilot.agent.dependency_graph import ExecutionWave

    # Setup
    nodes = [
        ToolNode(
            tool_id=f"tool_{i}",
            tool_call=ToolCall(id=f"tool_{i}", name=f"test_tool_{i}", arguments={}),
            input_files=set(),
            output_files=set(),
            explicit_deps=[]
        )
        for i in range(2)
    ]
    wave = ExecutionWave(wave_id=5, tools=nodes)

    # Mock registry and dispatcher
    mock_registry.get.return_value = None
    mock_dispatcher.execute = AsyncMock(return_value=ToolOutput(output="success"))

    # Track events
    start_events = []
    complete_events = []
    event_emitter.on("parallel.wave_start", lambda event: start_events.append(event.data))
    event_emitter.on("parallel.wave_complete", lambda event: complete_events.append(event.data))

    # Execute
    await executor.execute_wave(wave, wave_id=5)

    # Verify start event
    assert len(start_events) == 1
    assert start_events[0]["wave_id"] == 5
    assert start_events[0]["tool_count"] == 2
    assert start_events[0]["tools"] == ["test_tool_0", "test_tool_1"]

    # Verify complete event
    assert len(complete_events) == 1
    assert complete_events[0]["wave_id"] == 5
    assert complete_events[0]["success_count"] == 2
    assert complete_events[0]["failure_count"] == 0
    assert "duration_sec" in complete_events[0]
    assert complete_events[0]["duration_sec"] >= 0


@pytest.mark.asyncio
async def test_execute_wave_parallel_speedup(executor, mock_dispatcher, mock_registry):
    """Test that wave execution runs tools in parallel (speedup verification)."""
    from mdpilot.agent.dependency_graph import ExecutionWave
    import time

    # Setup 3 tools that each take 0.1 seconds
    nodes = [
        ToolNode(
            tool_id=f"tool_{i}",
            tool_call=ToolCall(id=f"tool_{i}", name="test_tool", arguments={}),
            input_files=set(),
            output_files=set(),
            explicit_deps=[]
        )
        for i in range(3)
    ]
    wave = ExecutionWave(wave_id=0, tools=nodes)

    # Mock registry
    mock_registry.get.return_value = None

    # Mock dispatcher with delay
    async def delayed_execute(call):
        await asyncio.sleep(0.1)
        return ToolOutput(output="success")

    mock_dispatcher.execute = delayed_execute

    # Execute and measure time
    start = time.time()
    results = await executor.execute_wave(wave, wave_id=0)
    duration = time.time() - start

    # Verify results
    assert len(results) == 3

    # Verify parallel execution (should take ~0.1s, not 0.3s)
    # Allow some overhead, but should be much less than sequential
    assert duration < 0.25  # Should be closer to 0.1s than 0.3s


# ============================================================================
# Task 15: Main execute_parallel Method Tests
# ============================================================================

@pytest.mark.asyncio
async def test_execute_parallel_single_tool(executor, mock_dispatcher, mock_registry):
    """Test execute_parallel with a single tool."""
    # Setup
    tools = [
        ("test_tool", "Test tool", {"arg": "value"})
    ]

    # Mock registry
    tool_meta = ToolMeta(
        name="test_tool",
        description="Test tool",
        parameters={},
        depends_on=[]
    )
    mock_registry.get.return_value = (tool_meta, lambda: None)

    # Mock dispatcher
    mock_dispatcher.execute = AsyncMock(return_value=ToolOutput(output="success"))

    # Execute
    results = await executor.execute_parallel(tools)

    # Verify
    assert len(results) == 1
    assert results[0].tool_id == "step_1"
    assert results[0].tool_call.name == "test_tool"
    assert results[0].output.output == "success"


@pytest.mark.asyncio
async def test_execute_parallel_independent_tools(executor, mock_dispatcher, mock_registry, event_emitter):
    """Test execute_parallel with independent tools (all in one wave)."""
    # Setup - 3 independent tools
    tools = [
        ("tool_a", "Tool A", {}),
        ("tool_b", "Tool B", {}),
        ("tool_c", "Tool C", {}),
    ]

    # Mock registry - all tools have no dependencies
    tool_meta = ToolMeta(
        name="test",
        description="Test",
        parameters={},
        depends_on=[]
    )
    mock_registry.get.return_value = (tool_meta, lambda: None)

    # Mock dispatcher
    mock_dispatcher.execute = AsyncMock(return_value=ToolOutput(output="success"))

    # Track wave events
    wave_starts = []
    event_emitter.on("parallel.wave_start", lambda event: wave_starts.append(event.data))

    # Execute
    results = await executor.execute_parallel(tools)

    # Verify all tools executed
    assert len(results) == 3
    assert all(r.output.output == "success" for r in results)

    # Verify all in same wave (wave_id=0)
    assert all(r.wave_id == 0 for r in results)

    # Verify only one wave
    assert len(wave_starts) == 1
    assert wave_starts[0]["tool_count"] == 3


@pytest.mark.asyncio
async def test_execute_parallel_with_dependencies(executor, mock_dispatcher, mock_registry, event_emitter):
    """Test execute_parallel with tools that have dependencies."""
    # Setup - tool_b depends on tool_a
    tools = [
        ("tool_a", "Tool A", {"output": "file_a.txt"}),
        ("tool_b", "Tool B", {"input": "file_a.txt"}),
    ]

    # Mock registry
    def get_tool_meta(name):
        if name == "tool_a":
            return (
                ToolMeta(
                    name="tool_a",
                    description="Tool A",
                    parameters={},
                    depends_on=[]
                ),
                lambda: None
            )
        else:
            return (
                ToolMeta(
                    name="tool_b",
                    description="Tool B",
                    parameters={},
                    depends_on=[]
                ),
                lambda: None
            )

    mock_registry.get.side_effect = get_tool_meta

    # Mock dispatcher
    mock_dispatcher.execute = AsyncMock(return_value=ToolOutput(output="success"))

    # Track wave events
    wave_starts = []
    event_emitter.on("parallel.wave_start", lambda event: wave_starts.append(event.data))

    # Execute
    results = await executor.execute_parallel(tools)

    # Verify all tools executed
    assert len(results) == 2

    # Verify execution order - tool_a in wave 0, tool_b in wave 1
    tool_a_result = next(r for r in results if r.tool_call.name == "tool_a")
    tool_b_result = next(r for r in results if r.tool_call.name == "tool_b")

    assert tool_a_result.wave_id == 0
    assert tool_b_result.wave_id == 1

    # Verify two waves
    assert len(wave_starts) == 2


@pytest.mark.asyncio
async def test_execute_parallel_complex_dependencies(executor, mock_dispatcher, mock_registry, event_emitter):
    """Test execute_parallel with complex dependency graph."""
    # Setup - diamond dependency pattern
    # tool_a -> tool_b -> tool_d
    #        -> tool_c -> tool_d
    tools = [
        ("tool_a", "Tool A", {"output": "file_a.txt"}),
        ("tool_b", "Tool B", {"input": "file_a.txt", "output": "file_b.txt"}),
        ("tool_c", "Tool C", {"input": "file_a.txt", "output": "file_c.txt"}),
        ("tool_d", "Tool D", {"input": "file_b.txt"}),  # Only depends on file_b
    ]

    # Mock registry
    tool_meta = ToolMeta(
        name="test",
        description="Test",
        parameters={},
        depends_on=[]
    )
    mock_registry.get.return_value = (tool_meta, lambda: None)

    # Mock dispatcher
    mock_dispatcher.execute = AsyncMock(return_value=ToolOutput(output="success"))

    # Track wave events
    wave_starts = []
    event_emitter.on("parallel.wave_start", lambda event: wave_starts.append(event.data))

    # Execute
    results = await executor.execute_parallel(tools)

    # Verify all tools executed
    assert len(results) == 4

    # Verify wave structure
    # Wave 0: tool_a
    # Wave 1: tool_b, tool_c (parallel)
    # Wave 2: tool_d
    tool_a = next(r for r in results if r.tool_call.name == "tool_a")
    tool_b = next(r for r in results if r.tool_call.name == "tool_b")
    tool_c = next(r for r in results if r.tool_call.name == "tool_c")
    tool_d = next(r for r in results if r.tool_call.name == "tool_d")

    assert tool_a.wave_id == 0
    assert tool_b.wave_id == 1
    assert tool_c.wave_id == 1  # Parallel with tool_b
    assert tool_d.wave_id == 2

    # Verify 3 waves
    assert len(wave_starts) == 3


@pytest.mark.asyncio
async def test_execute_parallel_with_unknown_tool(executor, mock_dispatcher, mock_registry):
    """Test execute_parallel with tool not in registry."""
    # Setup
    tools = [
        ("unknown_tool", "Unknown tool", {})
    ]

    # Mock registry to return None
    mock_registry.get.return_value = None

    # Mock dispatcher
    mock_dispatcher.execute = AsyncMock(return_value=ToolOutput(output="success"))

    # Execute - should create default ToolMeta
    results = await executor.execute_parallel(tools)

    # Verify
    assert len(results) == 1
    assert results[0].tool_call.name == "unknown_tool"


@pytest.mark.asyncio
async def test_execute_parallel_performance_speedup(executor, mock_dispatcher, mock_registry):
    """Test that execute_parallel achieves speedup with independent tools."""
    import time

    # Setup - 3 independent tools that each take 0.1 seconds
    tools = [
        ("tool_a", "Tool A", {}),
        ("tool_b", "Tool B", {}),
        ("tool_c", "Tool C", {}),
    ]

    # Mock registry
    tool_meta = ToolMeta(
        name="test",
        description="Test",
        parameters={},
        depends_on=[]
    )
    mock_registry.get.return_value = (tool_meta, lambda: None)

    # Mock dispatcher with delay
    async def delayed_execute(call):
        await asyncio.sleep(0.1)
        return ToolOutput(output="success")

    mock_dispatcher.execute = delayed_execute

    # Execute and measure time
    start = time.time()
    results = await executor.execute_parallel(tools)
    duration = time.time() - start

    # Verify results
    assert len(results) == 3

    # Verify parallel speedup (should take ~0.1s, not 0.3s)
    assert duration < 0.25  # Should be closer to 0.1s than 0.3s


@pytest.mark.asyncio
async def test_execute_parallel_aggregates_results(executor, mock_dispatcher, mock_registry):
    """Test that execute_parallel returns aggregated results from all waves."""
    # Setup - 2 waves
    tools = [
        ("tool_a", "Tool A", {"output": "file_a.txt"}),
        ("tool_b", "Tool B", {"input": "file_a.txt"}),
        ("tool_c", "Tool C", {}),  # Independent, will be in wave 0
    ]

    # Mock registry
    tool_meta = ToolMeta(
        name="test",
        description="Test",
        parameters={},
        depends_on=[]
    )
    mock_registry.get.return_value = (tool_meta, lambda: None)

    # Mock dispatcher
    call_count = 0
    async def mock_execute(call):
        nonlocal call_count
        call_count += 1
        return ToolOutput(output=f"result_{call_count}")

    mock_dispatcher.execute = mock_execute

    # Execute
    results = await executor.execute_parallel(tools)

    # Verify all results aggregated
    assert len(results) == 3
    assert all(r.output.success for r in results)

    # Verify results contain outputs from all tools
    outputs = [r.output.output for r in results]
    assert "result_1" in outputs
    assert "result_2" in outputs
    assert "result_3" in outputs
